from src.utils.state import AgentState
from src.orchestrator.router import decompose_and_route
from src.tools.kb_ops import check_and_update_kb_index

def orchestrator_node(state: AgentState):
    """
    The main orchestrator node.
    1. Checks KB updates.
    2. Decomposes and routes the query.
    """
    query = state["query"]
    print(f"--- Orchestrator Processing: {query} ---")
    
    # 1. Check/Update Knowledge Bases
    # In a real scenario, we might want to check all experts or just relevant ones.
    # For now, check all known experts.
    for expert in ["notes_agent", "books_agent", "video_agent"]:
        check_and_update_kb_index(expert)
        
    # 2. Decompose and Route
    route_plan = decompose_and_route(query, state.get("messages", []))
    
    # Update State
    # route_plan is now a RouterOutput object
    return {
        "sub_queries": route_plan.sub_queries, # Store list of SubQuery objects
        # We need a way to schedule these. For this simple graph, 
        # we might just store the plan and let the graph edges handle it.
        # But LangGraph works best if we schedule the next node.
        # Let's verify the first expert to call.
        "current_expert": route_plan.sub_queries[0].expert.value if route_plan.sub_queries else None,
        # Store the full plan
        "results": {"execution_plan": [sq.model_dump() for sq in route_plan.sub_queries]}
    }
