from src.utils.state import AgentState
from src.orchestrator.router import decompose_and_route
from src.tools.kb_ops import check_and_update_kb_index
import logging

logger = logging.getLogger(__name__)


def orchestrator_node(state: AgentState):
    query = state["query"]
    logger.info(f"--- Orchestrator Processing: {query} ---")

    # Auto-reindex stale knowledge bases
    for expert in ["notes_agent", "books_agent", "video_agent"]:
        check_and_update_kb_index(expert)

    route_plan = decompose_and_route(query, state.get("messages", []))
    sub_queries = route_plan.sub_queries

    if not sub_queries:
        return {
            "sub_queries": [],
            "current_expert": "saarthi_agent",
            "results": {"execution_plan": []}
        }

    # If there are MULTIPLE sub-queries (multi-agent), run them all here
    # and combine results so the graph doesn't need to handle sequential routing.
    if len(sub_queries) > 1:
        logger.info(f"--- Multi-agent query: {len(sub_queries)} sub-queries ---")
        combined_results = {
            "execution_plan": [sq.model_dump() for sq in sub_queries]
        }

        for sq in sub_queries:
            expert_name = sq.expert.value
            sub_query = sq.query
            logger.info(f"--- Running sub-query [{expert_name}]: {sub_query} ---")

            try:
                if expert_name == "calculator_agent":
                    from src.experts.calculator import run_calculator_agent
                    res, trace = run_calculator_agent(sub_query, state.get("messages", []))
                elif expert_name == "saarthi_agent":
                    from src.experts.saarthi import run_saarthi_agent
                    res = run_saarthi_agent(sub_query, state.get("messages", []))
                    trace = []
                else:
                    from src.experts.base import run_expert
                    res, trace = run_expert(expert_name, sub_query, mode="rag",
                                           messages=state.get("messages", []))

                combined_results[expert_name] = res
                combined_results[f"{expert_name}_trace"] = trace
                logger.info(f"--- [{expert_name}] done ---")
            except Exception as e:
                logger.error(f"--- [{expert_name}] failed: {e} ---")

        # Return all results and mark as "multi_agent" so the UI knows
        return {
            "sub_queries": sub_queries,
            "current_expert": "multi_agent",
            "results": combined_results,
        }

    # Single sub-query: route to the specific agent via the graph
    return {
        "sub_queries": sub_queries,
        "current_expert": sub_queries[0].expert.value,
        "results": {"execution_plan": [sq.model_dump() for sq in sub_queries]}
    }
