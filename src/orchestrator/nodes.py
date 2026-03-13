from src.utils.state import AgentState
from src.orchestrator.router import decompose_and_route
from src.tools.kb_ops import check_and_update_kb_index
import logging

logger = logging.getLogger(__name__)

def orchestrator_node(state: AgentState):
    query = state["query"]
    logger.info(f"--- Orchestrator Processing: {query} ---")
    for expert in ["notes_agent", "books_agent", "video_agent"]:
        check_and_update_kb_index(expert)
    route_plan = decompose_and_route(query, state.get("messages", []))
    return {
        "sub_queries": route_plan.sub_queries,
        "current_expert": route_plan.sub_queries[0].expert.value if route_plan.sub_queries else None,
        "results": {"execution_plan": [sq.model_dump() for sq in route_plan.sub_queries]}
    }
