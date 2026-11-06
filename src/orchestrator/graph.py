from langgraph.graph import StateGraph, END
from src.utils.state import AgentState
from src.orchestrator.nodes import orchestrator_node
from src.experts.base import notes_agent_node, books_agent_node
from src.experts.calculator import calculator_agent_node
from src.experts.saarthi import saarthi_agent_node
from src.experts.video import video_agent_node
from src.experts.mind import mind_fan_out_node, mind_agent_node
from src.experts.data_analysis import data_analysis_agent_node
from src.experts.web import web_agent_node
from src.orchestrator.critique import critic_node
from src.schemas.models import ExpertResponse
import logging
import os

logger = logging.getLogger(__name__)


def web_allowed() -> bool:
    """ALLOW_WEB_AGENT=1 re-enables open-web answers (off: answers come from course materials only)."""
    return os.environ.get("ALLOW_WEB_AGENT", "").strip().lower() in ("1", "true", "yes", "on")


def fast_chat() -> bool:
    """FAST_CHAT=1 skips the faithfulness critic (one extra LLM call) for CPU demos."""
    return os.environ.get("FAST_CHAT", "").strip().lower() in ("1", "true", "yes", "on")

def create_graph():
    workflow = StateGraph(AgentState)
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("notes_agent", notes_agent_node)
    workflow.add_node("books_agent", books_agent_node)
    workflow.add_node("calculator_agent", calculator_agent_node)
    workflow.add_node("saarthi_agent", saarthi_agent_node)
    workflow.add_node("video_agent", video_agent_node)
    workflow.add_node("mind_fan_out", mind_fan_out_node)
    workflow.add_node("mind_agent", mind_agent_node)
    workflow.add_node("data_analysis_agent", data_analysis_agent_node)
    workflow.add_node("web_agent", web_agent_node)
    workflow.add_node("critic", critic_node)

    workflow.set_entry_point("orchestrator")

    def route_from_orchestrator(state):
        if state.get("mind_mode", False):
            return "mind_fan_out"

        expert = state.get("current_expert")
        if expert == "multi_agent":
            return END
        elif expert == "notes_agent":
            return "notes_agent"
        elif expert == "books_agent":
            return "books_agent"
        elif expert == "calculator_agent":
            return "calculator_agent"
        elif expert == "saarthi_agent":
            return "saarthi_agent"
        elif expert == "video_agent":
            return "video_agent"
        elif expert == "data_analysis_agent":
            return "data_analysis_agent"
        elif expert == "web_agent":
            return "web_agent"
        else:
            return "saarthi_agent"

    def _knowledge_missing(state: dict, key: str) -> bool:
        res = state.get("results", {}).get(key)
        return res is not None and hasattr(res, "is_knowledge_present") and not res.is_knowledge_present

    def _after_rag():
        # The critic was documented as "wired after RAG" but these routes ended the
        # graph, so it only ever ran after the video agent.
        return END if fast_chat() else "critic"

    def route_from_notes(state):
        if _knowledge_missing(state, "notes_agent"):
            logger.info("--- Notes: no knowledge → Books Agent ---")
            return "books_agent"
        return _after_rag()

    def route_from_books(state):
        if _knowledge_missing(state, "books_agent"):
            # Grounding rule: no open-web retrieval in the student chat (spec 7.1).
            if web_allowed():
                logger.info("--- Books: no knowledge → Web Agent ---")
                return "web_agent"
            return END
        return _after_rag()

    def route_from_video(state):
        return _after_rag()

    workflow.add_conditional_edges(
        "orchestrator",
        route_from_orchestrator,
        {
            "notes_agent": "notes_agent",
            "books_agent": "books_agent",
            "calculator_agent": "calculator_agent",
            "saarthi_agent": "saarthi_agent",
            "video_agent": "video_agent",
            "mind_fan_out": "mind_fan_out",
            "data_analysis_agent": "data_analysis_agent",
            "web_agent": "web_agent",
            END: END,
        }
    )

    workflow.add_conditional_edges(
        "notes_agent",
        route_from_notes,
        {
            "books_agent": "books_agent",
            "critic": "critic",
            END: END,
        }
    )

    workflow.add_conditional_edges(
        "books_agent",
        route_from_books,
        {
            "web_agent": "web_agent",
            "critic": "critic",
            END: END,
        }
    )

    workflow.add_edge("mind_fan_out", "mind_agent")
    workflow.add_edge("mind_agent", END)
    workflow.add_edge("calculator_agent", END)
    workflow.add_edge("saarthi_agent", END)
    workflow.add_conditional_edges("video_agent", route_from_video, {"critic": "critic", END: END})
    workflow.add_edge("critic", END)
    workflow.add_edge("data_analysis_agent", END)
    workflow.add_edge("web_agent", END)

    return workflow.compile()
