"""File upload: POST /upload (under /api)."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse

from saarthi_backend.deps import get_current_user
from saarthi_backend.model import User

router = APIRouter(prefix="/upload", tags=["upload"])

# Directory relative to project root (parent of saarthi_backend)
UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
MAX_SIZE_MB = 10


def _ensure_upload_dir() -> Path:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOAD_DIR


@router.post("", response_model=dict)
async def upload_file(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Upload a file; returns { url: "/uploads/..." } for use in assignment attachments etc."""
    if not file.filename:
        return JSONResponse(status_code=400, json={"error": {"code": "INVALID", "message": "No filename"}})
    content = await file.read()
    if len(content) > MAX_SIZE_MB * 1024 * 1024:
        return JSONResponse(
            status_code=400,
            json={"error": {"code": "INVALID", "message": f"File too large (max {MAX_SIZE_MB}MB)"}},
        )
    ext = Path(file.filename).suffix or ""
    safe_name = f"{uuid.uuid4().hex}{ext}"
    dest = _ensure_upload_dir() / safe_name
    dest.write_bytes(content)
    return {"url": f"/uploads/{safe_name}"}
