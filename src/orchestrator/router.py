from typing import List, Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from src.prompts.loader import get_prompt
from src.tools.kb_ops import get_expert_description
from src.schemas.models import RouterOutput, ExpertName

def decompose_and_route(query: str, messages: List[Dict[str, Any]] = []) -> RouterOutput:
    """
    Decomposes the query and routes it to experts.
    """
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    # Construct expert descriptions dynamically
    expert_info = []
    # Use Enum values to ensure consistency
    for expert in ExpertName:
        desc = get_expert_description(expert.value)
        expert_info.append(f"- {expert.value}: {desc}")
    
    expert_descriptions_str = "\n".join(expert_info)
    
    system_prompt = get_prompt("orchestrator_system", expert_descriptions=expert_descriptions_str)
    
    # STRICT MODE ENABLED
    structured_llm = llm.with_structured_output(RouterOutput, method="json_schema", strict=True)
    
    # Construct full message list for context
    # System Prompt -> History -> Current Query
    llm_messages = [SystemMessage(content=system_prompt)]
    
    # Add history (skip the last one if it's the current query, to avoid duplication)
    # Streamlit messages are [{"role": "user", "content": "..."}]
    # We need to convert them to LangChain messages or just pass as is if chat model supports it.
    # We'll simple-parse them.
    for msg in messages[:-1]: # process history
        if msg["role"] == "user":
            llm_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            # We treat assistant output as "System/AI" context. 
            # Note: ExpertResponse objects might need stringification if we stored them raw.
            # In app.py we store the stringified response in session_state.messages.
            llm_messages.append(SystemMessage(content=f"Assistant: {msg['content']}"))
            
    # Add current query
    llm_messages.append(HumanMessage(content=query))
    
    try:
        response = structured_llm.invoke(llm_messages)
        return response
    except Exception as e:
        print(f"Routing Error: {e}")
        # Fallback (return empty or default)
        # For strict typing, we can't easily fake it without constructing the object manually.
        # Let's rely on the LLM or raise.
        raise e
