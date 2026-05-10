"""
data_store.py — Supabase Storage integration for user-uploaded CSV datasets.

Links uploaded CSVs to their chat thread so when a user returns to a past
conversation, their dataset is automatically restored for analysis.

Storage layout in Supabase (bucket: 'saarthi-data'):
    {thread_id}/{filename}.csv

DB: threads table gets a 'dataset_name' column storing the CSV filename.

SQL to run once in Supabase:
    ALTER TABLE threads ADD COLUMN dataset_name TEXT;
"""

import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DATA_BUCKET = "saarthi-data"
TEMP_DIR = Path("temp_data")


# ─── Supabase client (service key) ────────────────────────────────────────

def _get_client():
    """Returns a Supabase client using service key, or None if not configured."""
    url = os.environ.get("SUPABASE_URL", "").strip()
    key = (
        os.environ.get("SUPABASE_SERVICE_KEY", "").strip()
        or os.environ.get("SUPABASE_KEY", "").strip()
    )
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception as e:
        logger.warning(f"Supabase client init failed: {e}")
        return None


def _ensure_bucket(client) -> bool:
    """Creates the saarthi-data bucket if it doesn't exist."""
    try:
        existing = [b.name for b in client.storage.list_buckets()]
        if DATA_BUCKET not in existing:
            client.storage.create_bucket(DATA_BUCKET, options={"public": False})
            logger.info(f"Created Supabase Storage bucket: '{DATA_BUCKET}'")
        return True
    except Exception as e:
        logger.warning(f"Could not ensure bucket '{DATA_BUCKET}': {e}")
        return False


# ─── Upload ────────────────────────────────────────────────────────────────

def upload_csv_to_supabase(thread_id: str, file_bytes: bytes, filename: str) -> bool:
    """
    Uploads a CSV file to Supabase Storage under the thread's folder.
    Also updates the thread record to store the dataset_name.

    Path in bucket: saarthi-data/{thread_id}/{filename}

    Returns True if successful, False otherwise.
    """
    client = _get_client()
    if not client:
        logger.info("Supabase not configured — CSV stored locally only.")
        return False

    if not _ensure_bucket(client):
        return False

    remote_path = f"{thread_id}/{filename}"
    try:
        client.storage.from_(DATA_BUCKET).upload(
            path=remote_path,
            file=file_bytes,
            file_options={"content-type": "text/csv", "upsert": "true"},
        )
        logger.info(f"Uploaded CSV to Supabase Storage: {remote_path}")
    except Exception as e:
        logger.error(f"CSV upload failed: {e}")
        return False

    # Link this CSV to the thread in the DB
    try:
        client.table("threads").update(
            {"dataset_name": filename}
        ).eq("id", thread_id).execute()
        logger.info(f"Linked dataset '{filename}' to thread {thread_id}")
    except Exception as e:
        logger.warning(f"Could not update thread dataset_name: {e}")
        # Still return True — the file IS uploaded even if linking failed

    return True


# ─── Download ──────────────────────────────────────────────────────────────

def download_csv_from_supabase(thread_id: str, filename: str) -> bool:
    """
    Downloads a CSV from Supabase Storage to local temp_data/ folder.
    Skips if the file already exists locally.

    Returns True if the file is available locally after this call.
    """
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    local_path = TEMP_DIR / filename

    # Already present locally — nothing to do
    if local_path.exists():
        logger.info(f"CSV already local: {local_path}")
        return True

    client = _get_client()
    if not client:
        logger.warning("Supabase not configured — cannot restore dataset.")
        return False

    remote_path = f"{thread_id}/{filename}"
    try:
        file_bytes = client.storage.from_(DATA_BUCKET).download(remote_path)
        with open(local_path, "wb") as f:
            f.write(file_bytes)
        size_kb = len(file_bytes) / 1024
        logger.info(f"Downloaded CSV from Supabase: {remote_path} ({size_kb:.1f} KB)")
        return True
    except Exception as e:
        logger.warning(f"Could not download CSV '{remote_path}': {e}")
        return False


# ─── Get dataset linked to a thread ───────────────────────────────────────

def get_thread_dataset(thread_id: str) -> Optional[str]:
    """
    Returns the dataset_name (CSV filename) linked to a thread, or None.
    """
    client = _get_client()
    if not client:
        return None
    try:
        res = (
            client.table("threads")
            .select("dataset_name")
            .eq("id", thread_id)
            .execute()
        )
        if res.data:
            return res.data[0].get("dataset_name")
    except Exception as e:
        logger.warning(f"Could not fetch dataset for thread {thread_id}: {e}")
    return None


# ─── Restore dataset when loading a thread ────────────────────────────────

def restore_dataset_for_thread(thread_id: str) -> Optional[str]:
    """
    Full restore flow: looks up dataset_name from DB, then downloads to temp_data/.
    Call this whenever a user switches to a past thread.

    Returns the filename if a dataset was restored, None if no dataset linked.
    """
    filename = get_thread_dataset(thread_id)
    if not filename:
        logger.info(f"Thread {thread_id} has no linked dataset.")
        return None

    success = download_csv_from_supabase(thread_id, filename)
    if success:
        logger.info(f"✅ Dataset '{filename}' restored for thread {thread_id}")
        return filename
    else:
        logger.warning(f"⚠️  Could not restore dataset '{filename}' for thread {thread_id}")
        return None
