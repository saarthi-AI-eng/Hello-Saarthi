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
    next_step: str
