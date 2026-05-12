"""
Admin routes: Knowledge Base management for notes_agent, books_agent, video_agent.

All endpoints require:  Authorization: Bearer <ADMIN_SECRET_TOKEN>

Endpoints:
  POST   /api/admin/kb/upload              — upload source docs to local + Supabase
  GET    /api/admin/kb/docs                — list uploaded docs for an agent
  POST   /api/admin/kb/index              — trigger background re-indexing, returns job_id
  GET    /api/admin/kb/index/status       — poll job status by job_id
  DELETE /api/admin/kb/docs               — delete a source doc (requires re-index after)
  GET    /api/admin/kb/stats              — KB health stats for all agents
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

ALLOWED_AGENTS = {"notes_agent", "books_agent", "video_agent"}
KB_ROOT = Path("knowledge_base")
INDEX_ROOT = Path("faiss_index")
KB_STATUS_FILE = Path("kb_status.json")

# In-memory job tracker (fine for single-process; use Redis for multi-worker)
_jobs: dict[str, dict] = {}


# ─── Auth dependency ──────────────────────────────────────────────────────────

def verify_admin(authorization: str = Header(...)) -> None:
    token = authorization.removeprefix("Bearer ").strip()
    expected = os.environ.get("ADMIN_SECRET_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Admin token not configured on server.")
    if token != expected:
        raise HTTPException(status_code=403, detail="Unauthorized.")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _agent_doc_dir(agent_name: str) -> Path:
    return KB_ROOT / agent_name


def _agent_index_dir(agent_name: str) -> Path:
    return INDEX_ROOT / agent_name


def _load_kb_status() -> dict:
    if KB_STATUS_FILE.exists():
        try:
            return json.loads(KB_STATUS_FILE.read_text())
        except Exception:
            pass
    return {}


# ─── Pydantic models ─────────────────────────────────────────────────────────

class UploadDocsResponse(BaseModel):
    status: str
    agent: str
    files: list[str]
    supabase_paths: list[str]


class DocItem(BaseModel):
    name: str
    size_kb: float
    uploaded_at: str


class DocsListResponse(BaseModel):
    agent: str
    documents: list[DocItem]


class IndexRequest(BaseModel):
    agent_name: str  # agent name or "all"


class IndexStartResponse(BaseModel):
    status: str
    agent: str
    job_id: str


class IndexStatusResponse(BaseModel):
    job_id: str
    agent: str
    status: str  # "running" | "complete" | "failed"
    progress: str
    documents_processed: int
    total_documents: int
    chunks_created: int


class AgentStats(BaseModel):
    document_count: int
    index_exists: bool
    last_indexed: Optional[str]
    total_chunks: int


class KBStatsResponse(BaseModel):
    agents: dict[str, AgentStats]


# ─── Background indexing task ────────────────────────────────────────────────

def _run_index_job(job_id: str, agent_name: str) -> None:
    """Runs in a background thread via FastAPI BackgroundTasks."""
    job = _jobs[job_id]
    try:
        doc_dir = _agent_doc_dir(agent_name)
        docs = list(doc_dir.glob("*.pdf")) + list(doc_dir.glob("*.txt"))
        job["total_documents"] = len(docs)
        job["progress"] = f"Starting indexing for {agent_name} ({len(docs)} docs)..."

        # Use the Supabase-aware indexer (falls back to local if Supabase not configured)
        try:
            from src.tools.kb_ops_supabase import check_and_update_kb_index_supabase as do_index
        except ImportError:
            from src.tools.kb_ops import check_and_update_kb_index as do_index

        for i, doc in enumerate(docs, 1):
            job["progress"] = f"Parsing {i}/{len(docs)}: {doc.name}"
            job["documents_processed"] = i

        # Trigger the actual index build (checks staleness, rebuilds, uploads)
        success = do_index(agent_name)

        if success:
            # Count chunks from index if pkl exists
            chunks = 0
            pkl_path = Path("knowledge_base") / agent_name / "vector_store" / "index.pkl"
            if pkl_path.exists():
                try:
                    import pickle
                    with open(pkl_path, "rb") as f:
                        store = pickle.load(f)
                    chunks = len(store.get("documents", [])) if isinstance(store, dict) else 0
                except Exception:
                    pass
            job["chunks_created"] = chunks
            job["status"] = "complete"
            job["progress"] = f"Done. {len(docs)} documents indexed."
        else:
            job["status"] = "complete"
            job["progress"] = "Index is up to date — no reindex needed."

    except Exception as e:
        logger.error("Index job %s failed: %s", job_id, e)
        job["status"] = "failed"
        job["progress"] = f"Error: {e}"


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/kb/upload", response_model=UploadDocsResponse, dependencies=[Depends(verify_admin)])
async def upload_docs(
    agent_name: str = Form(...),
    files: list[UploadFile] = File(...),
):
    """Upload source documents (PDF/TXT) for an agent to local storage and Supabase."""
    if agent_name not in ALLOWED_AGENTS:
        raise HTTPException(status_code=400, detail=f"agent_name must be one of {sorted(ALLOWED_AGENTS)}")

    doc_dir = _agent_doc_dir(agent_name)
    doc_dir.mkdir(parents=True, exist_ok=True)

    saved_files: list[str] = []
    supabase_paths: list[str] = []

    for upload in files:
        fname = upload.filename or ""
        if not (fname.lower().endswith(".pdf") or fname.lower().endswith(".txt")):
            raise HTTPException(status_code=400, detail=f"Only PDF and TXT files allowed. Got: {fname}")

        content = await upload.read()
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"{fname} exceeds 50 MB limit.")

        local_path = doc_dir / fname
        with open(local_path, "wb") as f:
            f.write(content)
        saved_files.append(fname)
        logger.info("Saved source doc: %s", local_path)

        # Upload to Supabase saarthi-source-docs bucket
        remote_path = f"{agent_name}/{fname}"
        try:
            from src.tools.kb_ops_supabase import _get_client, _ensure_bucket
            client = _get_client()
            if client:
                SOURCE_BUCKET = "saarthi-source-docs"
                existing = [b.name for b in client.storage.list_buckets()]
                if SOURCE_BUCKET not in existing:
                    client.storage.create_bucket(SOURCE_BUCKET, options={"public": False})
                client.storage.from_(SOURCE_BUCKET).upload(
                    path=remote_path,
                    file=content,
                    file_options={"content-type": "application/octet-stream", "upsert": "true"},
                )
                supabase_paths.append(remote_path)
                logger.info("Uploaded source doc to Supabase: %s", remote_path)
        except Exception as e:
            logger.warning("Supabase source-doc upload failed for %s: %s", fname, e)

    return UploadDocsResponse(
        status="uploaded",
        agent=agent_name,
        files=saved_files,
        supabase_paths=supabase_paths,
    )


@router.get("/kb/docs", response_model=DocsListResponse, dependencies=[Depends(verify_admin)])
def list_docs(agent_name: str):
    """List all source documents currently stored for an agent."""
    if agent_name not in ALLOWED_AGENTS:
        raise HTTPException(status_code=400, detail=f"agent_name must be one of {sorted(ALLOWED_AGENTS)}")

    doc_dir = _agent_doc_dir(agent_name)
    docs: list[DocItem] = []
    if doc_dir.exists():
        for f in sorted(doc_dir.iterdir()):
            if f.suffix.lower() in {".pdf", ".txt"}:
                stat = f.stat()
                docs.append(DocItem(
                    name=f.name,
                    size_kb=round(stat.st_size / 1024, 1),
                    uploaded_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                ))
    return DocsListResponse(agent=agent_name, documents=docs)


@router.post("/kb/index", response_model=IndexStartResponse, dependencies=[Depends(verify_admin)])
def trigger_index(req: IndexRequest, background_tasks: BackgroundTasks):
    """Trigger re-indexing for one agent or all. Returns a job_id to poll status."""
    agents_to_index: list[str]
    if req.agent_name == "all":
        agents_to_index = sorted(ALLOWED_AGENTS)
    elif req.agent_name in ALLOWED_AGENTS:
        agents_to_index = [req.agent_name]
    else:
        raise HTTPException(status_code=400, detail=f"agent_name must be one of {sorted(ALLOWED_AGENTS)} or 'all'")

    # For "all", create one job per agent but return the first job_id
    first_job_id = None
    for agent in agents_to_index:
        job_id = str(uuid.uuid4())
        _jobs[job_id] = {
            "job_id": job_id,
            "agent": agent,
            "status": "running",
            "progress": "Queued...",
            "documents_processed": 0,
            "total_documents": 0,
            "chunks_created": 0,
        }
        background_tasks.add_task(_run_index_job, job_id, agent)
        if first_job_id is None:
            first_job_id = job_id
        logger.info("Queued index job %s for %s", job_id, agent)

    return IndexStartResponse(
        status="started",
        agent=req.agent_name,
        job_id=first_job_id,
    )


@router.get("/kb/index/status", response_model=IndexStatusResponse, dependencies=[Depends(verify_admin)])
def index_status(job_id: str):
    """Poll the status of an indexing job."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return IndexStatusResponse(**job)


@router.delete("/kb/docs", dependencies=[Depends(verify_admin)])
def delete_doc(agent_name: str, filename: str):
    """Delete a source document. You must re-trigger indexing after deletion."""
    if agent_name not in ALLOWED_AGENTS:
        raise HTTPException(status_code=400, detail=f"agent_name must be one of {sorted(ALLOWED_AGENTS)}")

    local_path = _agent_doc_dir(agent_name) / filename
    if not local_path.exists():
        raise HTTPException(status_code=404, detail=f"{filename} not found for {agent_name}.")

    local_path.unlink()
    logger.info("Deleted source doc: %s", local_path)

    # Also remove from Supabase
    try:
        from src.tools.kb_ops_supabase import _get_client
        client = _get_client()
        if client:
            client.storage.from_("saarthi-source-docs").remove([f"{agent_name}/{filename}"])
            logger.info("Deleted from Supabase: saarthi-source-docs/%s/%s", agent_name, filename)
    except Exception as e:
        logger.warning("Supabase delete failed: %s", e)

    return {"status": "deleted", "agent": agent_name, "filename": filename}


@router.get("/kb/stats", response_model=KBStatsResponse, dependencies=[Depends(verify_admin)])
def kb_stats():
    """Return health stats for all agent knowledge bases."""
    kb_status = _load_kb_status()
    stats: dict[str, AgentStats] = {}

    for agent in sorted(ALLOWED_AGENTS):
        doc_dir = _agent_doc_dir(agent)
        doc_count = 0
        if doc_dir.exists():
            doc_count = sum(
                1 for f in doc_dir.iterdir()
                if f.suffix.lower() in {".pdf", ".txt"}
            )

        index_dir = Path("knowledge_base") / agent / "vector_store"
        index_exists = (index_dir / "index.faiss").exists() and (index_dir / "index.pkl").exists()

        last_ts = kb_status.get(agent)
        last_indexed = (
            datetime.fromtimestamp(float(last_ts), tz=timezone.utc).isoformat()
            if last_ts else None
        )

        # Best-effort chunk count from pkl
        chunks = 0
        pkl_path = index_dir / "index.pkl"
        if pkl_path.exists():
            try:
                import pickle
                with open(pkl_path, "rb") as f:
                    store = pickle.load(f)
                if isinstance(store, dict):
                    chunks = len(store.get("documents", []))
            except Exception:
                pass

        stats[agent] = AgentStats(
            document_count=doc_count,
            index_exists=index_exists,
            last_indexed=last_indexed,
            total_chunks=chunks,
        )

    return KBStatsResponse(agents=stats)
