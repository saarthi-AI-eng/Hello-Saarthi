from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
import numexpr
import logging
import math

from src.schemas.models import ExpertResponse, ExpertName

logger = logging.getLogger(__name__)

MAX_CALC_STEPS = 6

@tool
def calculate(expression: str) -> str:
    """
    Evaluates a numeric mathematical expression.
    Supports arithmetic, powers, trig, logs: "50 * 20", "2**10", "sin(3.14159/4)", "log(100)"
    """
    try:
        return str(numexpr.evaluate(expression).item())
    except Exception as e:
        return f"Error with numexpr: {e}"


@tool
def python_math(code: str) -> str:
    """
    Executes multi-step Python math code in a sandboxed environment.
    Has access to: math, cmath, numpy (as np), and basic Python.
    Use this for complex multi-step calculations, matrix operations, solving equations,
    series computations, signal processing math, etc.

    The code MUST assign the final result to a variable named 'result'.

    Example:
        import numpy as np
        A = np.array([[1, 2], [3, 4]])
        eigenvalues = np.linalg.eigvals(A)
        result = f"Eigenvalues: {eigenvalues}"

    Example:
        # Compute partial fraction coefficients
        import numpy as np
        numerator = [1, 0]
        denominator = [1, 3, 2]
        result = f"Num coeffs: {numerator}, Den coeffs: {denominator}, Roots: {np.roots(denominator)}"
    """
    try:
        import numpy as np
        import cmath

        safe_globals = {
            "__builtins__": {
                "range": range, "len": len, "sum": sum, "abs": abs,
                "min": min, "max": max, "round": round, "int": int,
                "float": float, "str": str, "list": list, "tuple": tuple,
                "dict": dict, "enumerate": enumerate, "zip": zip,
                "sorted": sorted, "reversed": reversed, "print": print,
                "isinstance": isinstance, "type": type, "complex": complex,
                "pow": pow, "map": map, "filter": filter, "bool": bool,
                "True": True, "False": False, "None": None,
            },
            "math": math,
            "cmath": cmath,
            "np": np,
            "numpy": np,
            "pi": math.pi,
            "e": math.e,
            "sin": math.sin, "cos": math.cos, "tan": math.tan,
            "asin": math.asin, "acos": math.acos, "atan": math.atan,
            "log": math.log, "log10": math.log10, "log2": math.log2,
            "sqrt": math.sqrt, "exp": math.exp,
            "factorial": math.factorial,
            "inf": float("inf"),
        }
        safe_locals = {}

        exec(code, safe_globals, safe_locals)

        if "result" in safe_locals:
            return str(safe_locals["result"])
        else:
            return "Error: Code must assign final answer to a variable named 'result'."
    except Exception as e:
        return f"Execution error: {type(e).__name__}: {e}"


CALCULATOR_SYSTEM_PROMPT = """You are an advanced Calculator Agent with multi-step reasoning capabilities.

You have TWO tools:
1. `calculate` — For simple numeric expressions (arithmetic, trig, powers, logs).
   Example: calculate("2**10 + 3*sin(1.5)")

2. `python_math` — For complex multi-step computations. This gives you full Python + NumPy.
   Use this for: matrix operations, eigenvalues, polynomial roots, convolutions,
   Z-transform evaluations, Fourier coefficients, solving systems of equations,
   series sums, signal processing, etc.

   The code MUST assign the final answer to a variable named `result`.

WORKFLOW:
- For simple expressions → use `calculate` directly.
- For complex/multi-step problems → use `python_math` with clear Python code.
- You can call tools MULTIPLE times (think → compute → observe → think again).
- Break complex problems into steps. Show your reasoning at each step.
- After gathering all results, provide a clear, well-formatted final answer.

MANDATORY MATH FORMATTING in your final answer:
- Inline math: wrap in $...$  e.g. $x = 5$
- Display equations: wrap in $$...$$ on their own line
- NEVER write bare LaTeX without dollar signs."""


def run_calculator_agent(query: str, messages: list = []) -> tuple:
    """
    Executes the calculator agent with multi-step ReAct reasoning.
    Returns (ExpertResponse, react_trace).
    """
    logger.info(f"--- Running Calculator Agent for: {query} ---")

    llm = ChatOpenAI(model="gpt-4.1", temperature=0)
    tools = [calculate, python_math]
    llm_with_tools = llm.bind_tools(tools)
    tool_map = {t.name: t for t in tools}

    history = []
    for msg in messages[:-1]:
        if msg["role"] == "user":
            history.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            history.append(SystemMessage(content=f"Assistant: {msg['content']}"))

    react_trace = []
    all_results = []

    lc_messages = (
        [SystemMessage(content=CALCULATOR_SYSTEM_PROMPT)]
        + history
        + [HumanMessage(content=query)]
    )

    try:
        for step in range(1, MAX_CALC_STEPS + 1):
            logger.info(f"--- Calculator ReAct Step {step}/{MAX_CALC_STEPS} ---")

            response = llm_with_tools.invoke(lc_messages)
            thought = response.content or ""
            step_record = {"step": step, "thought": thought, "tools_called": [], "observations": []}

            if not response.tool_calls:
                logger.info(f"--- Calculator done at step {step} (no tool calls) ---")
                step_record["thought"] = thought or "Computation complete."
                react_trace.append(step_record)
                break

            lc_messages.append(response)

            for tool_call in response.tool_calls:
                t_name = tool_call["name"]
                t_args = tool_call["args"]
                t_id = tool_call.get("id", t_name)

                if t_name in tool_map:
                    try:
                        result = tool_map[t_name].invoke(t_args)
                    except Exception as e:
                        result = f"Error: {e}"
                else:
                    result = f"Unknown tool: {t_name}"

                result_str = str(result)[:2000]
                step_record["tools_called"].append({"name": t_name, "args": t_args})
                step_record["observations"].append(result_str[:300])
                all_results.append(f"[Step {step}] {t_name}: {result_str}")

                lc_messages.append(ToolMessage(content=result_str, tool_call_id=t_id))

            react_trace.append(step_record)

        # Build final content from the last thought or all results
        final_thought = react_trace[-1]["thought"] if react_trace and react_trace[-1]["thought"] else ""

        if final_thought:
            content = final_thought
        elif all_results:
            content = "\n".join(all_results)
        else:
            content = "I could not calculate that."

        confidence = 1.0

    except Exception as e:
        content = f"Calculation failed: {e}"
        confidence = 0.0
        logger.error(f"Calculator error: {e}")

    expert_response = ExpertResponse(
        agent_name=ExpertName.CALCULATOR_AGENT,
        content=content,
        sources=[],
        confidence_score=confidence,
        is_knowledge_present=True
    )
    return expert_response, react_trace


from src.utils.state import AgentState

def calculator_agent_node(state: AgentState):
    query = state["sub_queries"][0].query if state["sub_queries"] else state["query"]
    res, trace = run_calculator_agent(query, messages=state.get("messages", []))
    return {"results": {"calculator_agent": res, "calculator_agent_trace": trace}}
