"""
Admin routes: Knowledge Base management for notes_agent, books_agent, video_agent.

All endpoints require:  Authorization: Bearer <ADMIN_SECRET_TOKEN>

Endpoints:
  POST   /api/admin/kb/upload         — upload source docs to local + Supabase
  GET    /api/admin/kb/docs           — list uploaded docs for an agent
  POST   /api/admin/kb/index          — trigger background re-indexing, returns job_id
  GET    /api/admin/kb/index/status   — poll job status by job_id
  DELETE /api/admin/kb/docs           — delete a source doc
  GET    /api/admin/kb/stats          — KB health stats for all agents
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
KB_STATUS_FILE = Path("kb_status.json")

# In-memory job tracker (fine for single-process)
_jobs: dict[str, dict] = {}


# ─── Auth ────────────────────────────────────────────────────────────────────

def verify_admin(authorization: str = Header(...)) -> None:
    token = authorization.removeprefix("Bearer ").strip()
    expected = os.environ.get("ADMIN_SECRET_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Admin token not configured on server.")
    if token != expected:
        raise HTTPException(status_code=403, detail="Unauthorized.")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _doc_dir(agent_name: str) -> Path:
    return KB_ROOT / agent_name

def _index_dir(agent_name: str) -> Path:
    return KB_ROOT / agent_name / "vector_store"

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


# ─── Background indexing ─────────────────────────────────────────────────────

def _run_index_job(job_id: str, agent_name: str) -> None:
    """
    Full indexing pipeline per admin_panel_spec.md:
      1. Load PDFs (via docling) + TXTs
      2. Split: chunk_size=512, overlap=64
      3. Embed: text-embedding-3-small
      4. Build FAISS index
      5. Save locally: knowledge_base/{agent}/vector_store/
      6. Upload to Supabase: saarthi-indexes bucket
    """
    job = _jobs[job_id]
    try:
        from langchain_community.document_loaders import TextLoader
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from langchain_openai import OpenAIEmbeddings
        from langchain_community.vectorstores import FAISS
        from langchain_core.documents import Document

        doc_dir = _doc_dir(agent_name)
        pdf_files = list(doc_dir.glob("*.pdf"))
        txt_files = list(doc_dir.glob("*.txt"))
        all_files = pdf_files + txt_files
        total = len(all_files)
        job["total_documents"] = total
        job["progress"] = f"Starting: found {total} documents"

        if total == 0:
            job["status"] = "failed"
            job["progress"] = f"No PDF or TXT files found in knowledge_base/{agent_name}/"
            return

        documents = []

        # Load PDFs via docling
        for i, pdf_path in enumerate(pdf_files, 1):
            job["progress"] = f"Parsing {i}/{total}: {pdf_path.name}"
            job["documents_processed"] = i
            try:
                from docling.document_converter import DocumentConverter
                converter = DocumentConverter()
                result = converter.convert(str(pdf_path))
                text = result.document.export_to_markdown()
                if text.strip():
                    documents.append(Document(
                        page_content=text,
                        metadata={"source": pdf_path.name}
                    ))
                    logger.info("Docling parsed %s (%d chars)", pdf_path.name, len(text))
                else:
                    logger.warning("Docling got no text from %s", pdf_path.name)
            except Exception as e:
                logger.error("Failed to parse %s: %s", pdf_path.name, e)

        # Load TXTs directly
        offset = len(pdf_files)
        for i, txt_path in enumerate(txt_files, 1):
            job["progress"] = f"Loading {offset + i}/{total}: {txt_path.name}"
            job["documents_processed"] = offset + i
            try:
                text = txt_path.read_text(encoding="utf-8").strip()
                if text:
                    documents.append(Document(
                        page_content=text,
                        metadata={"source": txt_path.name}
                    ))
            except Exception as e:
                logger.error("Failed to load %s: %s", txt_path.name, e)

        if not documents:
            job["status"] = "failed"
            job["progress"] = "No text could be extracted from any document."
            return

        # Split — spec: chunk_size=512, overlap=64
        job["progress"] = "Splitting documents into chunks..."
        splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=64)
        splits = splitter.split_documents(documents)
        job["chunks_created"] = len(splits)
        logger.info("%s: %d chunks created", agent_name, len(splits))

        # Embed — spec: text-embedding-3-small
        job["progress"] = f"Generating embeddings for {len(splits)} chunks..."
        embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        vector_store = FAISS.from_documents(documents=splits, embedding=embeddings)

        # Save locally
        index_path = _index_dir(agent_name)
        index_path.mkdir(parents=True, exist_ok=True)
        vector_store.save_local(str(index_path))
        logger.info("%s: FAISS index saved to %s", agent_name, index_path)

        # Update kb_status.json
        import time
        status = _load_kb_status()
        status[agent_name] = time.time()
        KB_STATUS_FILE.write_text(json.dumps(status))

        # Upload index to Supabase saarthi-indexes bucket
        job["progress"] = "Uploading index to Supabase Storage..."
        try:
            from src.tools.kb_ops_supabase import upload_kb_to_supabase
            uploaded = upload_kb_to_supabase(agent_name)
            if uploaded:
                logger.info("%s: index uploaded to Supabase", agent_name)
            else:
                logger.warning("%s: Supabase upload failed (local index still usable)", agent_name)
        except Exception as e:
            logger.warning("%s: Supabase upload error: %s", agent_name, e)

        job["status"] = "complete"
        job["progress"] = f"Done. {total} docs → {len(splits)} chunks. Index built and uploaded."

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
    """Upload PDFs/TXTs for an agent. Saves locally + uploads to saarthi-source-docs in Supabase."""
    if agent_name not in ALLOWED_AGENTS:
        raise HTTPException(status_code=400, detail=f"agent_name must be one of {sorted(ALLOWED_AGENTS)}")

    doc_dir = _doc_dir(agent_name)
    doc_dir.mkdir(parents=True, exist_ok=True)

    saved_files: list[str] = []
    supabase_paths: list[str] = []

    for upload in files:
        fname = upload.filename or ""
        if not (fname.lower().endswith(".pdf") or fname.lower().endswith(".txt")):
            raise HTTPException(status_code=400, detail=f"Only PDF and TXT allowed. Got: {fname}")
        content = await upload.read()
        if len(content) > 50 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"{fname} exceeds 50 MB limit.")

        local_path = doc_dir / fname
        local_path.write_bytes(content)
        saved_files.append(fname)
        logger.info("Saved source doc: %s", local_path)

        # Upload to Supabase saarthi-source-docs
        remote_path = f"{agent_name}/{fname}"
        try:
            from src.tools.kb_ops_supabase import _get_client
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
                logger.info("Uploaded to Supabase: %s/%s", SOURCE_BUCKET, remote_path)
        except Exception as e:
            logger.warning("Supabase upload failed for %s: %s", fname, e)

    return UploadDocsResponse(
        status="uploaded",
        agent=agent_name,
        files=saved_files,
        supabase_paths=supabase_paths,
    )


@router.get("/kb/docs", response_model=DocsListResponse, dependencies=[Depends(verify_admin)])
def list_docs(agent_name: str):
    """List all source documents for an agent."""
    if agent_name not in ALLOWED_AGENTS:
        raise HTTPException(status_code=400, detail=f"agent_name must be one of {sorted(ALLOWED_AGENTS)}")
    doc_dir = _doc_dir(agent_name)
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
    """Trigger re-indexing for one agent or all. Returns job_id to poll."""
    if req.agent_name == "all":
        agents = sorted(ALLOWED_AGENTS)
    elif req.agent_name in ALLOWED_AGENTS:
        agents = [req.agent_name]
    else:
        raise HTTPException(status_code=400, detail=f"agent_name must be one of {sorted(ALLOWED_AGENTS)} or 'all'")

    first_job_id = None
    for agent in agents:
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

    return IndexStartResponse(status="started", agent=req.agent_name, job_id=first_job_id)


@router.get("/kb/index/status", response_model=IndexStatusResponse, dependencies=[Depends(verify_admin)])
def index_status(job_id: str):
    """Poll indexing job status."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found.")
    return IndexStatusResponse(**job)


@router.delete("/kb/docs", dependencies=[Depends(verify_admin)])
def delete_doc(agent_name: str, filename: str):
    """Delete a source document. Re-index required after deletion."""
    if agent_name not in ALLOWED_AGENTS:
        raise HTTPException(status_code=400, detail=f"agent_name must be one of {sorted(ALLOWED_AGENTS)}")
    local_path = _doc_dir(agent_name) / filename
    if not local_path.exists():
        raise HTTPException(status_code=404, detail=f"{filename} not found for {agent_name}.")
    local_path.unlink()
    logger.info("Deleted: %s", local_path)
    try:
        from src.tools.kb_ops_supabase import _get_client
        client = _get_client()
        if client:
            client.storage.from_("saarthi-source-docs").remove([f"{agent_name}/{filename}"])
    except Exception as e:
        logger.warning("Supabase delete failed: %s", e)
    return {"status": "deleted", "agent": agent_name, "filename": filename}


@router.get("/kb/stats", response_model=KBStatsResponse, dependencies=[Depends(verify_admin)])
def kb_stats():
    """KB health stats for all agents."""
    kb_status = _load_kb_status()
    stats: dict[str, AgentStats] = {}
    for agent in sorted(ALLOWED_AGENTS):
        doc_dir = _doc_dir(agent)
        doc_count = sum(
            1 for f in doc_dir.iterdir()
            if f.suffix.lower() in {".pdf", ".txt"}
        ) if doc_dir.exists() else 0

        idx = _index_dir(agent)
        index_exists = (idx / "index.faiss").exists() and (idx / "index.pkl").exists()

        last_ts = kb_status.get(agent)
        last_indexed = (
            datetime.fromtimestamp(float(last_ts), tz=timezone.utc).isoformat()
            if last_ts else None
        )

        chunks = 0
        pkl = idx / "index.pkl"
        if pkl.exists():
            try:
                import pickle
                store = pickle.loads(pkl.read_bytes())
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
