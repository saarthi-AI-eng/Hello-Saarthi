"""Code execution schemas."""

from typing import Literal, Optional
from pydantic import BaseModel, Field


SUPPORTED_LANGUAGES = Literal[
    "python", "javascript", "typescript", "cpp", "c", "java",
    "rust", "go", "bash", "r", "matlab_octave"
]

LANGUAGE_VERSIONS = {
    "python": "3.10.0",
    "javascript": "18.15.0",
    "typescript": "5.0.3",
    "cpp": "10.2.0",
    "c": "10.2.0",
    "java": "15.0.2",
    "rust": "1.68.2",
    "go": "1.16.2",
    "bash": "5.2.0",
    "r": "4.1.1",
    "matlab_octave": "8.3.0",
}

# Piston uses these runtime names
PISTON_LANGUAGE_MAP = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "cpp": "c++",
    "c": "c",
    "java": "java",
    "rust": "rust",
    "go": "go",
    "bash": "bash",
    "r": "r",
    "matlab_octave": "octave",
}


class CodeExecuteRequest(BaseModel):
    language: str = Field(..., description="Language key, e.g. 'python'")
    code: str = Field(..., min_length=1, max_length=50_000)
    stdin: Optional[str] = Field(default="", description="Standard input for the program")
    explainOnError: bool = Field(default=True, description="If true and execution fails, call AI to explain the error")
    courseContext: Optional[str] = Field(default=None, description="Course name for better AI error explanation")


class CodeExecuteResult(BaseModel):
    stdout: str
    stderr: str
    exitCode: int
    language: str
    runtime: str               # e.g. "python 3.10.0"
    executionMs: Optional[float] = None


class CodeExplainRequest(BaseModel):
    code: str
    language: str
    stderr: str
    exitCode: int
    courseContext: Optional[str] = None


class CodeExplainResponse(BaseModel):
    explanation: str           # streamed separately via SSE; this is the sync fallback
    suggestions: list[str]


class CodeExecuteResponse(BaseModel):
    result: CodeExecuteResult
    aiExplanation: Optional[str] = None   # populated when explainOnError=True and exitCode != 0
    aiSuggestions: list[str] = []
