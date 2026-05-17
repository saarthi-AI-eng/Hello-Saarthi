from pydantic import BaseModel, Field
from datetime import datetime


class PromptItem(BaseModel):
    id: int
    guide_id: int
    step_number: int
    title: str
    prompt_text: str
    created_at: datetime


class GuideItem(BaseModel):
    id: int
    title: str
    description: str | None
    created_by: int | None
    created_at: datetime
    prompts: list[PromptItem] = []


class CreateGuideRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class CreatePromptRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    prompt_text: str = Field(..., min_length=1)
