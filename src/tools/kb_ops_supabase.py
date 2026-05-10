"""
kb_ops_supabase.py — Supabase Storage extension for the FAISS Knowledge Base.

This file ADDS Supabase Storage sync ON TOP of the existing kb_ops.py logic.
The original kb_ops.py is 100% untouched and still works independently.

How it works:
  1. App startup → if local FAISS index missing → download from Supabase Storage
  2. After KB reindex → automatically upload new index to Supabase Storage
  3. Graceful fallback → if Supabase unavailable, falls back to local FAISS silently

Supabase Storage bucket: 'saarthi-kb'  (auto-created if not present)

File layout inside bucket:
  notes_agent/index.faiss
  notes_agent/index.pkl
  books_agent/index.faiss
  books_agent/index.pkl
  video_agent/index.faiss
  video_agent/index.pkl

SETUP (one-time):
  1. Go to Supabase dashboard → Storage → Create bucket called 'saarthi-kb'
     (set it as Private)
  2. Make sure SUPABASE_URL and SUPABASE_KEY are in your .env file
  3. That's it — this module handles the rest automatically.
"""

import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── Config ────────────────────────────────────────────────────────────────
BUCKET_NAME = "saarthi-kb"
KB_STATUS_FILE = "kb_status.json"
INDEX_FILES = ["index.faiss", "index.pkl"]


# ─── Supabase Client ────────────────────────────────────────────────────────

def _get_client():
    """
    Returns a Supabase client using the SERVICE ROLE key.
    The service_role key bypasses RLS — required for Storage bucket operations.
    This is safe because this code only runs on your Python server, never in a browser.

    Add to your .env:
        SUPABASE_SERVICE_KEY=eyJhbGci...  (from Settings → API → service_role)
    Falls back to SUPABASE_KEY if SERVICE_KEY is not set (for backwards compat).
    """
    url = os.environ.get("SUPABASE_URL", "").strip()
    # Prefer service key for storage; fall back to anon key
    key = (
        os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
        or os.environ.get("SUPABASE_KEY", "").strip()
    )
    if not url or not key:
        logger.info("Supabase not configured. Skipping Storage operation.")
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as e:
        logger.warning(f"Supabase client init failed: {e}")
        return None


def _ensure_bucket(client) -> bool:
    """Ensures the storage bucket exists. Creates it if missing."""
    try:
        existing = [b.name for b in client.storage.list_buckets()]
        if BUCKET_NAME not in existing:
            client.storage.create_bucket(BUCKET_NAME, options={"public": False})
            logger.info(f"Created Supabase Storage bucket: '{BUCKET_NAME}'")
        return True
    except Exception as e:
        logger.warning(f"Could not ensure bucket '{BUCKET_NAME}': {e}")
        return False


def _local_index_path(agent_name: str) -> Path:
    return Path("knowledge_base") / agent_name / "vector_store"


# ─── Upload ─────────────────────────────────────────────────────────────────

def upload_kb_to_supabase(agent_name: str) -> bool:
    """
    Uploads the local FAISS index for an agent to Supabase Storage.
    Call this AFTER ingest_documents() succeeds in kb_ops.py.

    Local:   knowledge_base/{agent_name}/vector_store/index.faiss
    Remote:  saarthi-kb/{agent_name}/index.faiss

    Returns True if all files uploaded successfully.
    """
    client = _get_client()
    if not client:
        return False
    if not _ensure_bucket(client):
        return False

    local_dir = _local_index_path(agent_name)
    all_ok = True

    for filename in INDEX_FILES:
        local_path = local_dir / filename
        if not local_path.exists():
            logger.warning(f"Upload skipped — file not found: {local_path}")
            all_ok = False
            continue

        remote_path = f"{agent_name}/{filename}"
        try:
            with open(local_path, "rb") as f:
                file_bytes = f.read()

            # upsert = overwrite if exists, create if not
            client.storage.from_(BUCKET_NAME).upload(
                path=remote_path,
                file=file_bytes,
                file_options={
                    "content-type": "application/octet-stream",
                    "upsert": "true",
                }
            )
            size_kb = len(file_bytes) / 1024
            logger.info(f"Uploaded {remote_path} → Supabase Storage ({size_kb:.1f} KB)")
        except Exception as e:
            logger.error(f"Failed to upload {remote_path}: {e}")
            all_ok = False

    if all_ok:
        logger.info(f"✅ {agent_name}: FAISS index fully uploaded to Supabase Storage.")
    return all_ok


# ─── Download ───────────────────────────────────────────────────────────────

def download_kb_from_supabase(agent_name: str, force: bool = False) -> bool:
    """
    Downloads the FAISS index from Supabase Storage to local disk.
    Skips if local files already exist (unless force=True).

    Returns True if files were downloaded successfully, False otherwise.
    """
    local_dir = _local_index_path(agent_name)

    # Skip if already present locally and not forced
    if not force and all((local_dir / f).exists() for f in INDEX_FILES):
        logger.info(f"{agent_name}: Local FAISS index already exists — skipping download.")
        return False

    client = _get_client()
    if not client:
        return False

    logger.info(f"{agent_name}: Downloading FAISS index from Supabase Storage...")
    local_dir.mkdir(parents=True, exist_ok=True)
    success_count = 0

    for filename in INDEX_FILES:
        remote_path = f"{agent_name}/{filename}"
        local_path = local_dir / filename
        try:
            file_bytes = client.storage.from_(BUCKET_NAME).download(remote_path)
            with open(local_path, "wb") as f:
                f.write(file_bytes)
            size_kb = len(file_bytes) / 1024
            logger.info(f"Downloaded {remote_path} ({size_kb:.1f} KB) → {local_path}")
            success_count += 1
        except Exception as e:
            logger.warning(f"Could not download {remote_path}: {e}")

    if success_count == len(INDEX_FILES):
        logger.info(f"✅ {agent_name}: FAISS index downloaded from Supabase Storage.")
        return True
    elif success_count > 0:
        logger.warning(f"⚠️  {agent_name}: Partial download ({success_count}/{len(INDEX_FILES)} files).")
        return False
    else:
        logger.warning(f"❌ {agent_name}: No files found in Supabase Storage. Run KB update first.")
        return False


# ─── Startup Sync ───────────────────────────────────────────────────────────

def sync_kb_on_startup(agent_name: str) -> bool:
    """
    Call this on app startup for each RAG agent.
    Logic:
      - If local FAISS index exists → use it (no download needed)
      - If not → try to download from Supabase Storage
      - If Supabase also unavailable → return False (no index)

    Returns True if index is available and ready to use.
    """
    local_dir = _local_index_path(agent_name)
    local_ok = all((local_dir / f).exists() for f in INDEX_FILES)

    if local_ok:
        logger.info(f"{agent_name}: ✅ Local FAISS index ready.")
        return True

    logger.info(f"{agent_name}: No local index found. Attempting download from Supabase...")
    downloaded = download_kb_from_supabase(agent_name)

    if downloaded:
        return True

    logger.warning(
        f"{agent_name}: ⚠️  No index available locally or in Supabase. "
        f"Go to sidebar → 'Check for Updates' to build it."
    )
    return False


# ─── Enhanced check_and_update (drop-in upgrade) ────────────────────────────

def check_and_update_kb_index_supabase(agent_name: str) -> bool:
    """
    Enhanced version of check_and_update_kb_index() from kb_ops.py.

    Does everything the original does, PLUS:
      → Downloads index from Supabase if missing locally before checking
      → Uploads new index to Supabase after successful reindexing

    Same function signature and return value as the original — drop-in compatible.
    """
    # Step 1: Pull from Supabase if local index is missing
    local_dir = _local_index_path(agent_name)
    if not all((local_dir / f).exists() for f in INDEX_FILES):
        logger.info(f"{agent_name}: Local index missing. Trying Supabase download first...")
        download_kb_from_supabase(agent_name)

    # Step 2: Run original staleness check from kb_ops.py
    kb_path = Path("knowledge_base") / agent_name
    if not kb_path.exists():
        return False

    last_modified = 0.0
    has_files = False
    for ext in ["*.pdf", "*.txt"]:
        for file in kb_path.glob(ext):
            has_files = True
            mtime = file.stat().st_mtime
            if mtime > last_modified:
                last_modified = mtime

    if not has_files:
        return False

    # Load status file
    status = {}
    if os.path.exists(KB_STATUS_FILE):
        with open(KB_STATUS_FILE, "r") as f:
            try:
                status = json.load(f)
            except json.JSONDecodeError:
                pass

    prev_modified = status.get(agent_name, 0.0)
    index_missing = not all((local_dir / f).exists() for f in INDEX_FILES)

    if last_modified <= prev_modified and not index_missing:
        logger.info(f"{agent_name}: Index is up to date. No reindex needed.")
        return False

    # Step 3: Reindex using original kb_ops
    logger.info(f"{agent_name}: Reindexing...")
    from src.tools.kb_ops import ingest_documents
    success = ingest_documents(agent_name)

    if success:
        # Update status file
        status[agent_name] = last_modified
        with open(KB_STATUS_FILE, "w") as f:
            json.dump(status, f)

        # Step 4: Upload new index to Supabase
        logger.info(f"{agent_name}: Uploading new index to Supabase Storage...")
        uploaded = upload_kb_to_supabase(agent_name)
        if uploaded:
            logger.info(f"✅ {agent_name}: Reindexed and synced to Supabase.")
        else:
            logger.warning(f"⚠️  {agent_name}: Reindexed locally but Supabase upload failed. Will retry next time.")
        return True

    return False


# ─── Bulk helpers ───────────────────────────────────────────────────────────

ALL_RAG_AGENTS = ["notes_agent", "books_agent", "video_agent"]


def upload_all_agents() -> dict:
    """
    Uploads FAISS indexes for ALL agents to Supabase Storage.
    Run this once from your terminal to seed the cloud:

        python3 -c "from src.tools.kb_ops_supabase import upload_all_agents; upload_all_agents()"

    Returns dict of {agent_name: success_bool}
    """
    results = {}
    for agent in ALL_RAG_AGENTS:
        logger.info(f"--- Uploading {agent} ---")
        results[agent] = upload_kb_to_supabase(agent)
    return results


def download_all_agents(force: bool = False) -> dict:
    """
    Downloads FAISS indexes for ALL agents from Supabase Storage.
    Useful for setting up a fresh server deployment.

        python3 -c "from src.tools.kb_ops_supabase import download_all_agents; download_all_agents()"

    Returns dict of {agent_name: success_bool}
    """
    results = {}
    for agent in ALL_RAG_AGENTS:
        logger.info(f"--- Downloading {agent} ---")
        results[agent] = download_kb_from_supabase(agent, force=force)
    return results


def sync_all_on_startup() -> dict:
    """
    Startup check for all RAG agents.
    Add this to app.py to ensure indexes are ready before serving requests.

    Returns dict of {agent_name: is_ready_bool}
    """
    results = {}
    for agent in ALL_RAG_AGENTS:
        results[agent] = sync_kb_on_startup(agent)
    return results
