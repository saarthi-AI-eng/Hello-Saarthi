from langchain_core.tools import tool

@tool
def calculator(expression: str) -> str:
    """Calculates the result of a mathematical expression."""
    try:
        return str(eval(expression))
    except Exception as e:
        return f"Error calculating {expression}: {e}"
