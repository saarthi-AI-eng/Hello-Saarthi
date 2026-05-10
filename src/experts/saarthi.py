from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.schemas.models import ExpertResponse, ExpertName
import logging

logger = logging.getLogger(__name__)

def run_saarthi_agent(query: str, messages: list = []) -> ExpertResponse:
    """
    Executes the Saarthi agent: A helpful, humble, and friendly conversational assistant.
    Focused on engineering students in the signals domain.
    """
    logger.info(f"--- Running Saarthi (General Agent) for: {query} ---")
    
    llm = ChatOpenAI(model="gpt-4.1", temperature=0.7)
    
    system_prompt = (
        "You are Saarthi, a friendly and humble AI assistant designed to help engineering students, "
        "specifically in the signals and systems domain.\n"
        "Your Persona:\n"
        "- Friendly, polite, and encouraging.\n"
        "- Humble and patient.\n"
        "- Focused on academic and engineering success.\n"
        "- If the user asks about specific calculations or retrieving notes/books, politely guide them "
        "but do not try to invent specific data if you don't have it (though you are a general agent, "
        "so answer general conceptual questions freely).\n"
        "Guidelines:\n"
        "- Always maintain a helpful tone.\n"
        "- Follow the product's policy: Be safe, respectful, and educational.\n"
        "MANDATORY MATH FORMATTING — follow this exactly:\n"
        "- Inline variables/expressions: wrap in single dollar signs: $H(s)$, $x[n]$, $\\\\omega_0$\n"
        "- Standalone equations: wrap in double dollar signs on their own line:\n"
        "  $$X(z) = \\\\sum_{n=0}^{\\\\infty} x[n] z^{-n}$$\n"
        "- NEVER write bare LaTeX like: H(s) = \\\\frac{N(s)}{D(s)}\n"
        "- ALWAYS use $...$ or $$...$$ around ANY mathematical expression.\n"
        "IMPORTANT: You must identify yourself as 'saarthi_agent' in the structured output."
    )
    
    # We use strict structure to maintain consistency with the rest of the app
    structured_llm = llm.with_structured_output(ExpertResponse, method="json_schema", strict=True)
    
    llm_messages = [SystemMessage(content=system_prompt)]
    
    # Add History
    for msg in messages[:-1]:
        if msg["role"] == "user":
            llm_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            llm_messages.append(SystemMessage(content=f"Assistant: {msg['content']}"))
            
    llm_messages.append(HumanMessage(content=query))
    
    response = structured_llm.invoke(llm_messages)
    return response

# Wrapper for Node
from src.utils.state import AgentState

def saarthi_agent_node(state: AgentState):
    query = state["sub_queries"][0].query if state["sub_queries"] else state["query"]
    # Pass full messages from state
    messages = state.get("messages", [])
    res = run_saarthi_agent(query, messages)
    return {"results": {"saarthi_agent": res}}
