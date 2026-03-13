from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool, create_retriever_tool
from langchain_core.messages import SystemMessage, HumanMessage
from typing import List, Dict, Any

from src.prompts.loader import get_prompt
from src.tools.utilities import calculator
from src.tools.kb_ops import get_retriever
from src.schemas.models import ExpertResponse, ExpertName, Citation

def get_expert_tools(expert_name: str):
    """"
    Returns the tools available to the expert.
    """
    tools = [calculator]
    
    # Get Retriever Tool
    retriever = get_retriever(expert_name)
    if retriever:
        retriever_tool = create_retriever_tool(
            retriever,
            f"search_{expert_name}_knowledge_base",
            f"Searches the knowledge base for {expert_name}. Use this when you need info from the stored documents."
        )
        tools.append(retriever_tool)
    else:
        # Fallback if no index exists
        @tool
        def search_knowledge_base(query: str) -> str:
            """Searches the expert's knowledge base."""
            return f"[No Index Found for {expert_name}. Please add PDFs to knowledge_base/{expert_name} and restart.]"
        tools.append(search_knowledge_base)
        
    return tools

def run_expert(expert_name: str, query: str, mode: str = "fast") -> ExpertResponse:
    """
    Runs the expert agent and returns a structured ExpertResponse.
    """
    print(f"--- Running Expert: {expert_name} (Mode: {mode}) ---")
    
    tools = get_expert_tools(expert_name)
    prompt_str = get_prompt("expert_system", expert_name=expert_name, mode=mode)
    
    # Strict Prompting for Knowledge Fallback
    if expert_name == "notes_agent":
        prompt_str += "\n\nCRITICAL: You must answer ONLY from the provided context (citations). " \
                      "If the answer is NOT in the context, you MUST set 'is_knowledge_present' to False " \
                      "and return a generic 'I do not have this information in my notes' message."
    
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    # Define the structured output LLM
    # We use this for the FINAL step to ensure strict adherence
    structured_llm = llm.with_structured_output(ExpertResponse, method="json_schema", strict=True)
    
    if mode == "planning":
        # Planning Mode: Use LLM with tools
        llm_with_tools = llm.bind_tools(tools)
        
        messages = [
            SystemMessage(content=prompt_str),
            HumanMessage(content=query)
        ]
        
        # Simple tool invocation loop (1 turn for demo)
        response = llm_with_tools.invoke(messages)
        
        tool_outputs = []
        
        # Handle Tool Calls
        if response.tool_calls:
            for tool_call in response.tool_calls:
                t_name = tool_call["name"]
                t_args = tool_call["args"]
                
                # Execution
                result = "Tool Not Found"
                for t in tools:
                    if t.name == t_name:
                        try:
                            # LangChain tools might be run differently depending on type
                            if hasattr(t, "invoke"):
                                result = t.invoke(t_args)
                            else:
                                result = t(t_args)
                        except Exception as e:
                            result = f"Error: {e}"
                        break
                
                tool_outputs.append(f"Tool `{t_name}` output: {str(result)[:1000]}...") 
            
            # Synthesize final answer using Structured LLM
            final_prompt = (
                f"The user asked: {query}. You used tools and got these results: {tool_outputs}. "
                f"Please synthesize the answer and provide citations if available in the tool outputs. "
                f"If the tool output contains source filenames (e.g. 'metadata={{'source': '...'}}'), use those for citations."
                f"If the tool output indicates no information found, set is_knowledge_present=False."
            )
            
            final_messages = [
                SystemMessage(content=f"{prompt_str}\nYou must respond as {expert_name}."),
                HumanMessage(content=final_prompt)
            ]
            
            return structured_llm.invoke(final_messages)
            
        else:
             # No tools called, just return structured response
            final_messages = [
                SystemMessage(content=f"{prompt_str}\nYou must respond as {expert_name}."),
                HumanMessage(content=query)
            ]
            return structured_llm.invoke(final_messages)
        
    else:
        # Fast mode: Direct Structured LLM call
        messages = [
            SystemMessage(content=f"{prompt_str}\nYou must respond as {expert_name}."),
            HumanMessage(content=query)
        ]
        return structured_llm.invoke(messages)

# Wrapper for the node
from src.utils.state import AgentState

def notes_agent_node(state: AgentState):
    query = state["sub_queries"][0].query if state["sub_queries"] else state["query"]
    # state["sub_queries"] is now a list of SubQuery objects, not dicts
    # Update logic to handle Pydantic objects from router
    
    res = run_expert("notes_agent", query, mode="planning") 
    return {"results": {"notes_agent": res}}

def books_agent_node(state: AgentState):
    query = state["sub_queries"][0].query if state["sub_queries"] else state["query"]
    res = run_expert("books_agent", query, mode="planning") 
    return {"results": {"books_agent": res}}
