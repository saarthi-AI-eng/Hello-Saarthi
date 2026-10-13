from langchain_core.tools import tool, create_retriever_tool
from src.utils.llm import chat_llm
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from typing import List, Dict, Any, Tuple
import logging

from src.prompts.loader import get_prompt
from src.tools.utilities import calculator
from src.tools.kb_ops import get_retriever
from src.tools.retrieve import retrieve, chunks_as_prompt
from src.schemas.models import ExpertResponse, ExpertName, Citation

logger = logging.getLogger(__name__)

MAX_REACT_STEPS = 5

def get_expert_tools(expert_name: str):
    """
    Returns the tools available to the expert.
    """
    tools = [calculator]
    retriever = get_retriever(expert_name)
    if retriever:
        retriever_tool = create_retriever_tool(
            retriever,
            f"search_{expert_name}_knowledge_base",
            f"Searches the knowledge base for {expert_name}. Use this when you need info from the stored documents."
        )
        tools.append(retriever_tool)
    else:
        @tool
        def search_knowledge_base(query: str) -> str:
            """Searches the expert's knowledge base."""
            return f"[No Index Found for {expert_name}. Please add PDFs to knowledge_base/{expert_name} and restart.]"
        tools.append(search_knowledge_base)

    return tools

def _build_history_messages(messages: List[Dict[str, Any]]) -> List:
    """Converts session message dicts to LangChain message objects (excludes last message)."""
    lc_messages = []
    for msg in messages[:-1]:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            lc_messages.append(SystemMessage(content=f"Assistant: {msg['content']}"))
    return lc_messages

def run_expert(
    expert_name: str,
    query: str,
    mode: str = "fast",
    messages: List[Dict[str, Any]] = [],
    boost_terms: List[str] | None = None,
    return_chunks: bool = False,
):
    """
    Runs the expert agent and returns (ExpertResponse, react_trace).

    In planning (ReAct) mode, the agent loops: Think -> Act -> Observe
    up to MAX_REACT_STEPS times, collecting a visible trace of each step.

    react_trace format: [{"step": int, "thought": str, "tools_called": [...], "observations": [...]}]
    In fast mode, react_trace is an empty list.

    With return_chunks=True returns (ExpertResponse, react_trace, chunks) where chunks are
    the retrieve() results (as dicts) used to ground the answer — empty outside RAG mode.
    """
    res, trace, chunks = _run_expert(expert_name, query, mode, messages, boost_terms)
    return (res, trace, chunks) if return_chunks else (res, trace)


def _run_expert(expert_name, query, mode, messages, boost_terms):
    logger.info(f"--- Running Expert: {expert_name} (Mode: {mode}) ---")

    tools = get_expert_tools(expert_name)
    prompt_str = get_prompt("expert_system", expert_name=expert_name, mode=mode)

    if expert_name == "notes_agent":
        prompt_str += "\n\nCRITICAL: You must answer ONLY from the provided context (citations). " \
                      "If the answer is NOT in the context, you MUST set 'is_knowledge_present' to False " \
                      "and return a generic 'I do not have this information in my notes' message."

    llm = chat_llm(temperature=0, max_tokens=3000)
    structured_llm = llm.with_structured_output(ExpertResponse, method="json_schema", strict=True)
    history = _build_history_messages(messages)

    if mode == "planning":
        # ─── TRUE ReAct LOOP ───
        react_prompt = (
            f"{prompt_str}\n\n"
            "You are operating in ReAct (Reasoning + Acting) mode.\n"
            "CRITICAL RULE: On your FIRST step, you MUST call the search tool to retrieve "
            "information from your knowledge base. NEVER answer without searching first. "
            "Do NOT rely on your own training knowledge — ALWAYS search the KB.\n\n"
            "Workflow:\n"
            "Step 1 (MANDATORY): Search the knowledge base for the user's query.\n"
            "Step 2+: Review the results. If you need more detail or a different angle, "
            "search again with a DIFFERENT query phrasing.\n"
            "Final: When you have enough KB context, stop calling tools and state your reasoning.\n\n"
            "IMPORTANT: Use DIFFERENT search queries each step to get diverse results. "
            "Do NOT repeat the same search. After 2-3 good searches, you likely have enough info.\n"
        )

        llm_with_tools = llm.bind_tools(tools)
        react_trace = []
        all_tool_outputs = []

        lc_messages = [SystemMessage(content=react_prompt)] + history + [HumanMessage(content=query)]

        for step in range(1, MAX_REACT_STEPS + 1):
            logger.info(f"--- ReAct Step {step}/{MAX_REACT_STEPS} for {expert_name} ---")

            response = llm_with_tools.invoke(lc_messages)
            thought = response.content or ""
            step_record = {"step": step, "thought": thought, "tools_called": [], "observations": []}

            if not response.tool_calls:
                logger.info(f"--- {expert_name} done reasoning at step {step} (no tool calls) ---")
                step_record["thought"] = thought or "I have enough information to answer."
                react_trace.append(step_record)
                break

            lc_messages.append(response)

            for tool_call in response.tool_calls:
                t_name = tool_call["name"]
                t_args = tool_call["args"]
                t_id = tool_call.get("id", t_name)

                result = "Tool Not Found"
                for t in tools:
                    if t.name == t_name:
                        try:
                            result = t.invoke(t_args) if hasattr(t, "invoke") else t(t_args)
                        except Exception as e:
                            result = f"Error: {e}"
                        break

                result_str = str(result)[:1500]
                step_record["tools_called"].append({"name": t_name, "args": t_args})
                step_record["observations"].append(result_str[:300])
                all_tool_outputs.append(f"[Step {step}] Tool `{t_name}`: {result_str}")

                lc_messages.append(ToolMessage(content=result_str, tool_call_id=t_id))

            react_trace.append(step_record)
            logger.info(f"--- ReAct Step {step}: called {len(response.tool_calls)} tool(s) ---")

        # ─── Final Synthesis with ALL collected context ───
        synthesis_context = "\n\n".join(all_tool_outputs)
        final_prompt = (
            f"The user asked: {query}\n\n"
            f"You performed {len(react_trace)} ReAct reasoning steps and gathered:\n\n"
            f"{synthesis_context}\n\n"
            f"Now synthesize a comprehensive, well-structured answer with proper citations.\n"
            f"If tool outputs contain source filenames (e.g. metadata={{'source': '...'}}), use those for citations.\n"
            f"If no relevant information was found, set is_knowledge_present=False."
        )
        final_messages = (
            [SystemMessage(content=f"{prompt_str}\nYou must respond as {expert_name}.")]
            + history
            + [HumanMessage(content=final_prompt)]
        )
        expert_response = structured_llm.invoke(final_messages)
        return expert_response, react_trace, []

    elif mode == "rag":
        _TYPE = {"notes_agent": "notes", "books_agent": "books", "video_agent": "video"}
        from src.orchestrator.policy import top_n
        from src.utils.llm import _TIER
        k = top_n(_TIER.get() or 1)  # spec 4.2: 3 chunks for Tier 1, 8 for Tier 2
        chunks = retrieve(query, content_types=[_TYPE.get(expert_name, "notes")], boost_terms=boost_terms, k=k)[:k]
        if not chunks:
            # Grounding rule: nothing retrieved -> no LLM call; the graph moves on / says "not covered".
            return ExpertResponse(
                agent_name=ExpertName(expert_name), content="", sources=[],
                confidence_score=0.0, is_knowledge_present=False,
            ), [], []
        kb_context = chunks_as_prompt(chunks)
        if kb_context:
            augmented = (
                f"Relevant excerpts from the knowledge base:\n{kb_context}\n\n"
                f"User question: {query}"
            )
        else:
            augmented = query

        lc_messages = (
            [SystemMessage(content=f"{prompt_str}\nYou must respond as {expert_name}.")]
            + history
            + [HumanMessage(content=augmented)]
        )
        expert_response = structured_llm.invoke(lc_messages)
        if chunks and not expert_response.sources:
            expert_response.sources = [
                Citation(
                    source_file=c.source_file or "unknown",
                    page_number=int(c.page or 0),
                    snippet=c.text[:280],
                )
                for c in chunks[:5]
            ]
        from dataclasses import asdict
        return expert_response, [], [asdict(c) for c in chunks]

    else:
        # Fast mode: Direct Structured LLM call (no ReAct, no retrieval)
        lc_messages = (
            [SystemMessage(content=f"{prompt_str}\nYou must respond as {expert_name}.")]
            + history
            + [HumanMessage(content=query)]
        )
        return structured_llm.invoke(lc_messages), [], []

from src.utils.state import AgentState

def rag_agent_node(expert_name: str, state: AgentState) -> dict:
    query = state["sub_queries"][0].query if state["sub_queries"] else state["query"]
    mode = "planning" if state.get("planning", False) else "rag"
    res, trace, chunks = run_expert(
        expert_name, query, mode=mode, messages=state.get("messages", []),
        boost_terms=state.get("boost_terms") or None, return_chunks=True,
    )
    out = {"results": {expert_name: res, f"{expert_name}_trace": trace}}
    if chunks:
        out["retrieved_chunks"] = chunks
    return out


def notes_agent_node(state: AgentState):
    return rag_agent_node("notes_agent", state)


def books_agent_node(state: AgentState):
    return rag_agent_node("books_agent", state)
