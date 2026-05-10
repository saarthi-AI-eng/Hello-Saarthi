"""
Saarthi LLM Backend — FastAPI Server
=====================================
Exposes ALL Saarthi AI features as REST APIs for frontend integration.

Run: uvicorn llm-backend.main:app --reload --port 8000
"""

import os
import sys
import uuid
import logging
import asyncio
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
import json

# ── Ensure project root is importable ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Load .env ──
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

# ── Logging ──
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("saarthi-api")

# ── Import Saarthi core modules ──
from src.orchestrator.graph import create_graph
from src.schemas.models import ExpertResponse, MindAgentResponse
from src.db.chat_store import (
    create_thread, list_threads, delete_thread,
    save_message, load_thread_messages, get_thread_title_from_query
)
from src.db.data_store import (
    upload_csv_to_supabase, restore_dataset_for_thread, get_thread_dataset
)

# ── Build the graph once at startup ──
GRAPH = create_graph()
logger.info("✅ LangGraph compiled and ready.")


# ═══════════════════════════════════════════════════════════════════
#  Pydantic Request / Response Models
# ═══════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    """Payload sent by frontend when user sends a message."""
    query: str = Field(..., description="User's question/prompt")
    thread_id: Optional[str] = Field(None, description="Supabase thread UUID. If None, a new thread is created.")
    mode: str = Field("planning", description="Agent mode: 'planning' (ReAct) or 'fast' (direct LLM)")
    mind_mode: bool = Field(False, description="If True, queries all RAG agents and synthesizes via Mind Agent")
    messages: List[Dict[str, str]] = Field(default_factory=list, description="Chat history [{role, content}]")


class CitationOut(BaseModel):
    source_file: str = ""
    page_number: int = 0
    snippet: str = ""


class MindCitationOut(BaseModel):
    number: int
    source_agent: str
    source_file: str
    snippet: str


class AgentResultOut(BaseModel):
    agent_name: str
    content: str
    sources: List[CitationOut] = []
    confidence_score: float = 0.0
    is_knowledge_present: bool = True
    react_trace: List[Dict[str, Any]] = []


class MindResultOut(BaseModel):
    content: str
    references: List[MindCitationOut] = []
    confidence_score: float = 0.0


class ChatResponse(BaseModel):
    """Full structured response returned to frontend after a query."""
    thread_id: str
    response_type: str = Field(description="'agent', 'multi_agent', or 'mind'")
    agents: List[AgentResultOut] = []
    mind: Optional[MindResultOut] = None
    execution_plan: List[Dict[str, str]] = []


class ThreadOut(BaseModel):
    id: str
    title: str
    created_at: str
    dataset_name: Optional[str] = None


class MessageOut(BaseModel):
    role: str
    content: str


class HealthOut(BaseModel):
    status: str
    graph_ready: bool
    agents: List[str]


class KBStatusOut(BaseModel):
    agent: str
    updated: bool


# ═══════════════════════════════════════════════════════════════════
#  FastAPI App
# ═══════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Saarthi LLM Backend",
    description="AI Multi-Agent Study Assistant — REST API",
    version="1.0.0",
)

# CORS — allow all for dev (your backend team can restrict later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Helper: serialize ExpertResponse / MindAgentResponse ─────────

def _serialize_expert(res, trace=None) -> AgentResultOut:
    """Converts an ExpertResponse pydantic model to our API model."""
    sources = []
    raw_sources = res.sources if hasattr(res, "sources") else res.get("sources", [])
    for s in raw_sources:
        sources.append(CitationOut(
            source_file=s.source_file if hasattr(s, "source_file") else s.get("source_file", ""),
            page_number=s.page_number if hasattr(s, "page_number") else s.get("page_number", 0),
            snippet=s.snippet if hasattr(s, "snippet") else s.get("snippet", ""),
        ))
    return AgentResultOut(
        agent_name=res.agent_name.value if hasattr(res.agent_name, "value") else str(res.agent_name),
        content=res.content if hasattr(res, "content") else res.get("content", ""),
        sources=sources,
        confidence_score=res.confidence_score if hasattr(res, "confidence_score") else res.get("confidence_score", 0.0),
        is_knowledge_present=res.is_knowledge_present if hasattr(res, "is_knowledge_present") else res.get("is_knowledge_present", True),
        react_trace=trace or [],
    )


def _serialize_mind(res) -> MindResultOut:
    refs = []
    raw_refs = res.references if hasattr(res, "references") else res.get("references", [])
    for r in raw_refs:
        refs.append(MindCitationOut(
            number=r.number if hasattr(r, "number") else r.get("number", 0),
            source_agent=r.source_agent if hasattr(r, "source_agent") else r.get("source_agent", ""),
            source_file=r.source_file if hasattr(r, "source_file") else r.get("source_file", ""),
            snippet=r.snippet if hasattr(r, "snippet") else r.get("snippet", ""),
        ))
    return MindResultOut(
        content=res.content if hasattr(res, "content") else res.get("content", ""),
        references=refs,
        confidence_score=res.confidence_score if hasattr(res, "confidence_score") else res.get("confidence_score", 0.0),
    )


# ═══════════════════════════════════════════════════════════════════
#  ENDPOINTS
# ═══════════════════════════════════════════════════════════════════


# ── 1. Health Check ───────────────────────────────────────────────

@app.get("/api/health", response_model=HealthOut, tags=["System"])
def health_check():
    """Server health check — confirms graph is compiled and ready."""
    return HealthOut(
        status="ok",
        graph_ready=GRAPH is not None,
        agents=[
            "notes_agent", "books_agent", "video_agent",
            "calculator_agent", "saarthi_agent", "data_analysis_agent",
            "mind_agent"
        ],
    )


# ── 2. Chat — Main Query Endpoint ────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse, tags=["Chat"])
def chat(req: ChatRequest):
    """
    Send a query to Saarthi. Handles:
    - Auto thread creation
    - User + assistant message persistence
    - Agent routing (single, multi, mind)
    - Returns structured response with agent results, sources, and traces
    """
    # Auto-create thread if needed
    thread_id = req.thread_id
    if not thread_id:
        title = get_thread_title_from_query(req.query)
        thread_id = create_thread(title)
        logger.info(f"Created thread: {thread_id}")

    # Save user message
    save_message(thread_id, "user", req.query)

    # Build chat history for graph
    messages = req.messages + [{"role": "user", "content": req.query}]

    # Invoke the graph
    initial_state = {
        "messages": messages,
        "query": req.query,
        "sub_queries": [],
        "current_expert": None,
        "results": {},
        "mind_mode": req.mind_mode,
    }

    try:
        result = GRAPH.invoke(initial_state)
    except Exception as e:
        logger.error(f"Graph invocation failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI processing failed: {str(e)}")

    outputs = result.get("results", {})
    execution_plan = []
    if "execution_plan" in outputs:
        execution_plan = outputs.pop("execution_plan")

    # Build response
    response_type = "agent"
    agents_out = []
    mind_out = None

    if "mind_agent" in outputs:
        response_type = "mind"
        mind_out = _serialize_mind(outputs["mind_agent"])
    else:
        # Collect all agent results
        agent_keys = [k for k in outputs.keys() if not k.endswith("_trace")]
        if len(agent_keys) > 1:
            response_type = "multi_agent"
        for ak in agent_keys:
            res = outputs[ak]
            trace = outputs.get(f"{ak}_trace", [])
            agents_out.append(_serialize_expert(res, trace))

    # Build full text for DB storage
    if mind_out:
        full_text = f"🧠 Mind Agent:\n{mind_out.content}"
    elif agents_out:
        full_text = "\n\n".join([f"**{a.agent_name}:**\n{a.content}" for a in agents_out])
    else:
        full_text = "Could not generate a response."

    # Save assistant message
    save_message(thread_id, "assistant", full_text)

    return ChatResponse(
        thread_id=thread_id,
        response_type=response_type,
        agents=agents_out,
        mind=mind_out,
        execution_plan=execution_plan,
    )


# ── 3. Streaming Chat (SSE) ──────────────────────────────────────

@app.post("/api/chat/stream", tags=["Chat"])
def chat_stream(req: ChatRequest):
    """
    Same as /api/chat but streams the response as Server-Sent Events (SSE).
    Events:
      - type=status    → {message: "Routing query..."}
      - type=agent     → {agent_name, content, sources, trace}
      - type=mind      → {content, references}
      - type=thread    → {thread_id}
      - type=done      → {}
      - type=error     → {message}
    """
    def event_generator():
        try:
            # Thread management
            thread_id = req.thread_id
            if not thread_id:
                title = get_thread_title_from_query(req.query)
                thread_id = create_thread(title)

            yield f"data: {json.dumps({'type': 'thread', 'thread_id': thread_id})}\n\n"
            yield f"data: {json.dumps({'type': 'status', 'message': 'Processing your query...'})}\n\n"

            save_message(thread_id, "user", req.query)

            messages = req.messages + [{"role": "user", "content": req.query}]
            initial_state = {
                "messages": messages,
                "query": req.query,
                "sub_queries": [],
                "current_expert": None,
                "results": {},
                "mind_mode": req.mind_mode,
            }

            if req.mind_mode:
                yield f"data: {json.dumps({'type': 'status', 'message': '🧠 Mind Mode: Querying all agents...'})}\n\n"

            result = GRAPH.invoke(initial_state)
            outputs = result.get("results", {})

            full_text_parts = []

            if "mind_agent" in outputs:
                mind_data = _serialize_mind(outputs["mind_agent"])
                yield f"data: {json.dumps({'type': 'mind', **mind_data.model_dump()})}\n\n"
                full_text_parts.append(f"🧠 Mind Agent:\n{mind_data.content}")
            else:
                agent_keys = [k for k in outputs.keys() if not k.endswith("_trace") and k != "execution_plan"]
                for ak in agent_keys:
                    res = outputs[ak]
                    trace = outputs.get(f"{ak}_trace", [])
                    agent_data = _serialize_expert(res, trace)
                    yield f"data: {json.dumps({'type': 'agent', **agent_data.model_dump()})}\n\n"
                    full_text_parts.append(f"**{agent_data.agent_name}:**\n{agent_data.content}")

            full_text = "\n\n".join(full_text_parts) if full_text_parts else "Could not generate a response."
            save_message(thread_id, "assistant", full_text)

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# ── 4. Thread Management ─────────────────────────────────────────

@app.get("/api/threads", response_model=List[ThreadOut], tags=["Threads"])
def get_threads():
    """List all chat threads, newest first."""
    threads = list_threads()
    return [
        ThreadOut(
            id=t["id"],
            title=t.get("title", "Untitled"),
            created_at=t.get("created_at", ""),
            dataset_name=t.get("dataset_name"),
        )
        for t in threads
    ]


@app.post("/api/threads", response_model=ThreadOut, tags=["Threads"])
def create_new_thread(title: str = "New Chat"):
    """Create a new empty chat thread."""
    thread_id = create_thread(title)
    return ThreadOut(id=thread_id, title=title, created_at="", dataset_name=None)


@app.delete("/api/threads/{thread_id}", tags=["Threads"])
def remove_thread(thread_id: str):
    """Delete a thread and all its messages."""
    delete_thread(thread_id)
    return {"status": "deleted", "thread_id": thread_id}


@app.get("/api/threads/{thread_id}/messages", response_model=List[MessageOut], tags=["Threads"])
def get_thread_messages(thread_id: str):
    """Load all messages for a thread in chronological order."""
    msgs = load_thread_messages(thread_id)
    return [MessageOut(role=m["role"], content=m["content"]) for m in msgs]


# ── 5. Data Upload ───────────────────────────────────────────────

@app.post("/api/data/upload", tags=["Data Analysis"])
async def upload_dataset(
    file: UploadFile = File(...),
    thread_id: Optional[str] = Form(None),
):
    """
    Upload a CSV dataset. If thread_id is provided, links it to that chat thread
    in Supabase Storage.
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    content = await file.read()

    # Save locally
    temp_dir = Path("temp_data")
    temp_dir.mkdir(exist_ok=True)
    local_path = temp_dir / file.filename
    with open(local_path, "wb") as f:
        f.write(content)
    logger.info(f"Saved CSV locally: {local_path}")

    # Upload to Supabase if thread_id provided
    cloud_synced = False
    if thread_id:
        try:
            cloud_synced = upload_csv_to_supabase(thread_id, content, file.filename)
        except Exception as e:
            logger.warning(f"Cloud upload failed: {e}")

    return {
        "status": "uploaded",
        "filename": file.filename,
        "size_bytes": len(content),
        "thread_id": thread_id,
        "cloud_synced": cloud_synced,
    }


@app.get("/api/data/list", tags=["Data Analysis"])
def list_datasets():
    """List all CSV files currently available for analysis."""
    temp_dir = Path("temp_data")
    if not temp_dir.exists():
        return {"datasets": []}
    files = sorted(temp_dir.glob("*.csv"))
    return {
        "datasets": [
            {"filename": f.name, "size_kb": round(f.stat().st_size / 1024, 1)}
            for f in files
        ]
    }


@app.post("/api/data/restore/{thread_id}", tags=["Data Analysis"])
def restore_thread_dataset(thread_id: str):
    """Restore the dataset linked to a thread from Supabase Storage."""
    try:
        filename = restore_dataset_for_thread(thread_id)
        if filename:
            return {"status": "restored", "filename": filename}
        return {"status": "no_dataset", "filename": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 6. Knowledge Base ────────────────────────────────────────────

@app.post("/api/kb/update", response_model=List[KBStatusOut], tags=["Knowledge Base"])
def update_knowledge_base():
    """Check and update all agent knowledge base indexes."""
    try:
        from src.tools.kb_ops_supabase import check_and_update_kb_index_supabase as check_update
    except ImportError:
        from src.tools.kb_ops import check_and_update_kb_index as check_update

    results = []
    for agent_key in ["notes_agent", "books_agent", "video_agent"]:
        updated = check_update(agent_key)
        results.append(KBStatusOut(agent=agent_key, updated=updated))
    return results


@app.get("/api/kb/status", tags=["Knowledge Base"])
def kb_status():
    """Check if knowledge base indexes exist for each agent."""
    from src.tools.kb_ops import get_retriever

    statuses = {}
    for agent in ["notes_agent", "books_agent", "video_agent"]:
        retriever = get_retriever(agent)
        statuses[agent] = retriever is not None

    return {"agents": statuses}


# ── 7. System Info ───────────────────────────────────────────────

@app.get("/api/info", tags=["System"])
def system_info():
    """Returns system configuration for frontend display."""
    return {
        "app_name": "Saarthi",
        "version": "1.0.0",
        "agents": {
            "notes_agent": {"label": "📝 Notes Agent", "description": "Searches lecture notes & handwritten PDFs"},
            "books_agent": {"label": "📚 Books Agent", "description": "Searches textbooks & reference material"},
            "video_agent": {"label": "🎥 Video Agent", "description": "Searches video lecture transcripts"},
            "calculator_agent": {"label": "🧮 Calculator Agent", "description": "Multi-step math & computation"},
            "saarthi_agent": {"label": "🤖 Saarthi Agent", "description": "General conversational assistant"},
            "data_analysis_agent": {"label": "📊 Data Analysis Agent", "description": "Analyze uploaded CSV datasets"},
            "mind_agent": {"label": "🧠 Mind Agent", "description": "Synthesizes answers from all RAG agents"},
        },
        "modes": {
            "planning": "ReAct mode — agent reasons step-by-step with tool use",
            "fast": "Direct LLM — single-pass answer without tool calling",
        },
        "features": {
            "mind_mode": "Queries all RAG agents and synthesizes a rich, cited answer",
            "data_analysis": "Upload CSV files and ask questions about your data",
            "chat_persistence": "Chat history saved to Supabase",
            "knowledge_base_sync": "FAISS indexes synced to Supabase Storage",
        }
    }
