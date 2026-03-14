"""Request/response schemas for notifications."""

from typing import Optional

from pydantic import BaseModel, Field


class NotificationResponse(BaseModel):
    id: str
    type: str
    title: str
    body: str
    link: Optional[str] = None
    readAt: Optional[str] = None
    createdAt: str

    class Config:
        populate_by_name = True
