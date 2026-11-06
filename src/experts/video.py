from src.schemas.models import ExpertResponse, ExpertName
from src.experts.base import run_expert
from src.utils.state import AgentState

def run_video_agent(query: str, messages: list = []) -> ExpertResponse:
    """
    Executes the video agent using the same RAG pattern as books/notes agents.
    """
    return run_expert("video_agent", query, mode="planning", messages=messages)

def video_agent_node(state: AgentState):
    from src.experts.base import rag_agent_node
    return rag_agent_node("video_agent", state)
