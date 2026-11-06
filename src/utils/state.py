from typing import List, Dict, Any, Optional, TypedDict, Union, Annotated
import operator

class AgentState(TypedDict):
    """
    The state of the agent system.
    """
    messages: Annotated[List[Dict[str, Any]], operator.add]
    query: str
    sub_queries: List[Any] # List[SubQuery] objects
    current_expert: Optional[str]
    results: Dict[str, Any] # Values can be ExpertResponse objects
    mind_mode: bool
    planning: bool
    next_step: str
    plan: List[str]
    retrieved_chunks: List[Any]
    critic_ok: bool
    critic_notes: str
    boost_terms: List[str]   # e.g. the student's weak topics; reorders retrieval only
    tier: Optional[int]      # model tier chosen by the chat policy (1 small/local, 2 full/cloud)
