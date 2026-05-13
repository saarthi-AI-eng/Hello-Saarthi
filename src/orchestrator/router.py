from typing import List, Dict, Any
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from src.prompts.loader import get_prompt
from src.tools.kb_ops import get_expert_description
from src.schemas.models import RouterOutput, ExpertName
import logging

logger = logging.getLogger(__name__)

def decompose_and_route(query: str, messages: List[Dict[str, Any]] = []) -> RouterOutput:
    """
    Decomposes the query and routes it to experts.
    """
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    expert_info = []
    for expert in ExpertName:
        desc = get_expert_description(expert.value)
        expert_info.append(f"- {expert.value}: {desc}")
    
    expert_descriptions_str = "\n".join(expert_info)
    
    system_prompt = get_prompt("orchestrator_system", expert_descriptions=expert_descriptions_str)
    structured_llm = llm.with_structured_output(RouterOutput, method="json_schema", strict=True)
    llm_messages = [SystemMessage(content=system_prompt)]
    for msg in messages[:-1]:
        if msg["role"] == "user":
            llm_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            llm_messages.append(SystemMessage(content=f"Assistant: {msg['content']}"))
            
    llm_messages.append(HumanMessage(content=query))
    
    try:
        response = structured_llm.invoke(llm_messages)
        return response
    except Exception as e:
        logger.error(f"Routing Error: {e}")
        raise e
