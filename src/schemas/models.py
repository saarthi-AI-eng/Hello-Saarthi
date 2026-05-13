from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

class ExpertName(str, Enum):
    NOTES_AGENT = "notes_agent"
    BOOKS_AGENT = "books_agent"
    CALCULATOR_AGENT = "calculator_agent"
    SAARTHI_AGENT = "saarthi_agent"
    VIDEO_AGENT = "video_agent"
    DATA_ANALYSIS_AGENT = "data_analysis_agent"
    WEB_AGENT = "web_agent"

class SubQuery(BaseModel):
    """
    Represents a single decomposed query targeting a specific expert.
    """
    query: str = Field(description="The specific question or task for the expert.")
    expert: ExpertName = Field(description="The unique identifier of the expert best suited to handle this query.")

class RouterOutput(BaseModel):
    """
    The output of the orchestration layer, containing the plan of action.
    """
    sub_queries: List[SubQuery] = Field(description="List of sub-queries and their assigned experts.")

class Citation(BaseModel):
    """
    Reference to a source document.
    """
    source_file: str = Field(description="The name of the source file (e.g., 'meeting_notes.pdf').")
    page_number: int = Field(description="The page number where the information was found.")
    snippet: str = Field(description="A brief snippet of the text to verify the citation.")

class MindCitation(BaseModel):
    """
    A numbered citation reference for the Mind Agent's synthesized answer.
    """
    number: int = Field(description="The citation number (1, 2, 3, ...).")
    source_agent: str = Field(description="Which agent provided this info (e.g. 'Notes Agent', 'Books Agent', 'Video Agent').")
    source_file: str = Field(description="The source file name.")
    snippet: str = Field(description="A brief snippet proving the citation.")

class MindAgentResponse(BaseModel):
    """
    The synthesized response from the Mind Agent.
    Content should use superscript markers like [1], [2] inline.
    """
    content: str = Field(description="The synthesized answer with inline citation markers like [1], [2], etc.")
    references: List[MindCitation] = Field(default_factory=list, description="Numbered list of all citations referenced in the content.")
    confidence_score: float = Field(description="Overall confidence score between 0.0 and 1.0.")

class ExpertResponse(BaseModel):
    """
    The standardized response from an expert agent.
    """
    agent_name: ExpertName = Field(description="The name of the agent providing the response.")
    content: str = Field(description="The natural language answer to the user's query.")
    sources: List[Citation] = Field(default_factory=list, description="List of sources used to generate the answer.")
    confidence_score: float = Field(description="A score between 0.0 and 1.0 indicating confidence in the answer.")
    is_knowledge_present: bool = Field(default=True, description="False if the agent could not find the answer in its knowledge base.")
