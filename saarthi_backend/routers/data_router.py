"""Data analysis routes: CSV upload, list, and restore for the data_analysis_agent."""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)

TEMP_DIR = Path("temp_data")

router = APIRouter(prefix="/data", tags=["data-analysis"])


class UploadResponse(BaseModel):
    status: str
    filename: str
    size_bytes: int
    thread_id: Optional[str] = None
    cloud_synced: bool = False


class DatasetItem(BaseModel):
    filename: str
    size_kb: float


class DatasetListResponse(BaseModel):
    datasets: list[DatasetItem]


@router.post("/upload", response_model=UploadResponse)
async def upload_dataset(
    file: UploadFile = File(...),
    thread_id: Optional[str] = Form(None),
):
    """Upload a CSV dataset for analysis by data_analysis_agent."""
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported.")

    content = await file.read()
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    local_path = TEMP_DIR / file.filename
    with open(local_path, "wb") as f:
        f.write(content)
    logger.info("Saved CSV locally: %s", local_path)

    cloud_synced = False
    if thread_id:
        try:
            from src.db.data_store import upload_csv_to_supabase
            cloud_synced = upload_csv_to_supabase(thread_id, content, file.filename)
        except Exception as e:
            logger.warning("Cloud CSV upload failed: %s", e)

    return UploadResponse(
        status="uploaded",
        filename=file.filename,
        size_bytes=len(content),
        thread_id=thread_id,
        cloud_synced=cloud_synced,
    )


@router.get("/list", response_model=DatasetListResponse)
def list_datasets():
    """List all CSV files currently available for analysis."""
    if not TEMP_DIR.exists():
        return DatasetListResponse(datasets=[])
    files = sorted(TEMP_DIR.glob("*.csv"))
    return DatasetListResponse(
        datasets=[
            DatasetItem(filename=f.name, size_kb=round(f.stat().st_size / 1024, 1))
            for f in files
        ]
    )


@router.post("/restore/{thread_id}")
def restore_thread_dataset(thread_id: str):
    """Restore the CSV dataset linked to a chat thread from Supabase Storage."""
    try:
        from src.db.data_store import restore_dataset_for_thread
        filename = restore_dataset_for_thread(thread_id)
        if filename:
            return {"status": "restored", "filename": filename}
        return {"status": "no_dataset", "filename": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
