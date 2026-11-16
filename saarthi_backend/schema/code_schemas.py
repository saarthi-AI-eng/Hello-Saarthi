"""Code execution schemas."""

from typing import Optional
from pydantic import BaseModel, Field


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
    stdout: Optional[str] = None
    courseContext: Optional[str] = None


class CodeExplainResponse(BaseModel):
    explanation: str           # streamed separately via SSE; this is the sync fallback
    suggestions: list[str]


class CodeExecuteResponse(BaseModel):
    result: CodeExecuteResult
    aiExplanation: Optional[str] = None   # populated when explainOnError=True and exitCode != 0
    aiSuggestions: list[str] = []


class TestCase(BaseModel):
    input: str = ""
    expectedOutput: str
    hidden: bool = False


class TestCasePublic(BaseModel):
    """A test case as students see it: hidden cases show neither input nor output."""

    input: Optional[str] = None
    expectedOutput: Optional[str] = None
    hidden: bool = False


class CodeProblemResponse(BaseModel):
    id: int
    title: str
    difficulty: str
    points: int
    description: str
    requirements: list[str]
    expectedOutput: Optional[str]
    hints: list[str]
    starterCode: dict[str, str]
    topics: Optional[str]
    sortOrder: int
    testCases: list[TestCasePublic] = []


class CodeProblemCreate(BaseModel):
    title: str
    difficulty: str = "medium"
    points: int = 50
    description: str
    requirements: list[str] = []
    expectedOutput: Optional[str] = None
    hints: list[str] = []
    starterCode: dict[str, str] = {}
    topics: Optional[str] = None
    sortOrder: int = 0
    testCases: list[TestCase] = []


class CodeProblemUpdate(BaseModel):
    title: Optional[str] = None
    difficulty: Optional[str] = None
    points: Optional[int] = None
    description: Optional[str] = None
    requirements: Optional[list[str]] = None
    expectedOutput: Optional[str] = None
    hints: Optional[list[str]] = None
    starterCode: Optional[dict[str, str]] = None
    topics: Optional[str] = None
    sortOrder: Optional[int] = None
    isActive: Optional[bool] = None
    testCases: Optional[list[TestCase]] = None


class CodeSubmitRequest(BaseModel):
    language: str = Field(..., description="Language key, e.g. 'python'")
    code: str = Field(..., min_length=1, max_length=50_000)


class TestCaseResult(BaseModel):
    index: int
    passed: bool
    hidden: bool
    # Left out for hidden cases.
    input: Optional[str] = None
    expectedOutput: Optional[str] = None
    actualOutput: Optional[str] = None
    stderr: Optional[str] = None


class CodeSubmitResponse(BaseModel):
    id: int
    passed: int
    total: int
    results: list[TestCaseResult]
    createdAt: str


class CodeSubmissionItem(BaseModel):
    id: int
    problemId: int
    userId: int
    studentName: str
    language: str
    code: str
    passed: int
    total: int
    createdAt: str
