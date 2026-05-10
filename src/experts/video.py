from src.schemas.models import ExpertResponse, ExpertName
from src.experts.base import run_expert
from src.utils.state import AgentState

def run_video_agent(query: str, messages: list = []) -> ExpertResponse:
    """
    Executes the video agent using the same RAG pattern as books/notes agents.
    """
    return run_expert("video_agent", query, mode="planning", messages=messages)

def video_agent_node(state: AgentState):
    query = state["sub_queries"][0].query if state["sub_queries"] else state["query"]
    res, trace = run_video_agent(query, messages=state.get("messages", []))
    return {"results": {"video_agent": res, "video_agent_trace": trace}}
