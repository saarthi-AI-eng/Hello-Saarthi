"""Ask the course-notes knowledge base (under /api/kb). See src/knowledge_base/gemini_rag.py."""

from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from saarthi_backend.deps import get_current_user
from saarthi_backend.model import User
from saarthi_backend.utils.exceptions import AIServiceError, RetrievalError
from saarthi_backend.utils.logging import get_logger

router = APIRouter(prefix="/kb", tags=["knowledge-base"])
logger = get_logger(__name__)


class KBAskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)
    topK: int = Field(5, ge=1, le=10)


class KBSource(BaseModel):
    n: int
    sourceFile: Optional[str] = None
    page: Optional[int | str] = None
    topic: Optional[str] = None
    sourceType: Optional[str] = None
    score: float
    text: str


class KBAskResponse(BaseModel):
    answer: str
    sources: list[KBSource]


@router.get("/status")
async def kb_status(user: Annotated[User, Depends(get_current_user)]):
    """Whether the Gemini index of the knowledge base is built, and how many chunks it holds."""
    from src.knowledge_base import gemini_rag

    return await run_in_threadpool(gemini_rag.status)


@router.post("/ask", response_model=KBAskResponse)
async def kb_ask(body: KBAskRequest, user: Annotated[User, Depends(get_current_user)]):
    """Find the closest knowledge-base chunks and answer from them with Gemini, citing each one."""
    from src.knowledge_base import gemini_rag

    try:
        return await run_in_threadpool(lambda: gemini_rag.answer(body.question.strip(), body.topK))
    except FileNotFoundError as e:
        raise RetrievalError(str(e)) from e
    except Exception as e:  # noqa: BLE001 - Gemini errors (quota, overload, bad key)
        logger.warning("KB ask failed: %s", e)
        msg = str(e)
        if "429" in msg or "quota" in msg.lower():
            text = "The Gemini free-tier limit was reached. Wait a minute and try again."
        elif "503" in msg or "overloaded" in msg.lower() or "high demand" in msg.lower():
            text = "Gemini is busy right now. Try again in a few seconds."
        else:
            text = "Could not get an answer from Gemini. Check the API key and model settings."
        raise AIServiceError("KB_ASK_FAILED", text, status_code=502) from e
