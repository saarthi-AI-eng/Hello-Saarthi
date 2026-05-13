import logging
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.schemas.models import ExpertResponse, ExpertName
from src.utils.state import AgentState

logger = logging.getLogger(__name__)

_SYSTEM = (
    "You are Saarthi's web search agent. You have searched the web and gathered results below.\n"
    "Synthesize a clear, accurate answer from those results.\n"
    "MANDATORY MATH FORMATTING:\n"
    "- Inline variables/expressions: $x(t)$, $\\omega$, $H(j\\omega)$\n"
    "- Standalone equations on their own line: $$X(j\\omega) = \\int_{-\\infty}^{\\infty} x(t)\\,e^{-j\\omega t}\\,dt$$\n"
    "- NEVER write bare Unicode math symbols.\n"
    "TONE: Answer directly. Do NOT say 'according to search results' or cite URLs in-text.\n"
    "Respond as agent_name='web_agent'."
)


def _ddg_search(query: str, max_results: int = 5) -> str:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No web results found."
        parts = []
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            parts.append(f"**{title}**\n{body}")
        return "\n\n".join(parts)
    except Exception as e:
        logger.error("DuckDuckGo search failed: %s", e)
        return f"Web search unavailable: {e}"


def run_web_agent(query: str, messages: list = []) -> ExpertResponse:
    logger.info("--- Running Web Agent for: %s ---", query)
    search_results = _ddg_search(query)

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)
    structured_llm = llm.with_structured_output(ExpertResponse, method="json_schema", strict=True)

    user_content = (
        f"User question: {query}\n\n"
        f"Web search results:\n{search_results}\n\n"
        "Now provide a well-structured answer."
    )

    lc_messages = [SystemMessage(content=_SYSTEM)]
    for msg in messages[:-1]:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            lc_messages.append(SystemMessage(content=f"Assistant: {content}"))
    lc_messages.append(HumanMessage(content=user_content))

    return structured_llm.invoke(lc_messages)


def web_agent_node(state: AgentState):
    query = state["sub_queries"][0].query if state["sub_queries"] else state["query"]
    messages = state.get("messages", [])
    res = run_web_agent(query, messages)
    return {"results": {"web_agent": res}}
