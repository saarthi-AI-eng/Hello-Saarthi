from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.tools import tool
import numexpr

from src.schemas.models import ExpertResponse, ExpertName

@tool
def calculate(expression: str) -> str:
    """
    Evaluates a mathematical expression using numexpr.
    Example: "50 * 20", "2**10", "sin(10)"
    """
    try:
        # numexpr.evaluate returns a numpy array-like, convert to scalar/str
        return str(numexpr.evaluate(expression).item())
    except Exception as e:
        return f"Error: {e}"

def run_calculator_agent(query: str) -> ExpertResponse:
    """
    Executes the calculator agent.
    """
    print(f"--- Running Calculator Agent for: {query} ---")
    
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    
    # Bind the calculator tool
    llm_with_tools = llm.bind_tools([calculate])
    
    try:
        # 1. LLM decides what to calculate
        messages = [
            SystemMessage(content="You are a calculator agent. Use the 'calculate' tool to solve math problems. Return the final answer clearly."),
            HumanMessage(content=query)
        ]
        response = llm_with_tools.invoke(messages)
        
        content = response.content
        
        # 2. Execute tool if called
        if response.tool_calls:
            for tool_call in response.tool_calls:
                if tool_call["name"] == "calculate":
                    args = tool_call["args"]
                    expression = args.get("expression")
                    if expression:
                        result = calculate.invoke(expression)
                        content = f"Calculated {expression} = {result}"
                    else:
                        content = "Could not parse expression."
        
        # If no tool called, maybe it just answered (e.g. "1+1 is 2")
        if not content:
            content = "I could not calculate that."
            
        confidence = 1.0
        
    except Exception as e:
        content = f"Calculation functionality failed. Error: {e}"
        confidence = 0.0
        
    return ExpertResponse(
        agent_name=ExpertName.CALCULATOR_AGENT,
        content=content,
        sources=[],
        confidence_score=confidence,
        is_knowledge_present=True
    )

# Wrapper for Node
from src.utils.state import AgentState

def calculator_agent_node(state: AgentState):
    query = state["sub_queries"][0].query if state["sub_queries"] else state["query"]
    res = run_calculator_agent(query)
    return {"results": {"calculator_agent": res}}
