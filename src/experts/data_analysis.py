"""
Data Analysis Agent — Answers natural-language questions about uploaded CSV datasets.

Uses a ReAct loop: the LLM decides which data tool to call, reads the output,
then either calls another tool or writes the final answer.

Fully isolated: if this agent errors out, the except block returns a safe
ExpertResponse and no other agent is affected.
"""

import logging
from typing import List, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from src.schemas.models import ExpertResponse, ExpertName
from src.tools.data_tools import DATA_TOOLS

logger = logging.getLogger(__name__)

DATA_ANALYSIS_SYSTEM_PROMPT = """You are the **Data Analysis Agent** of Saarthi — an AI study assistant for engineering students.

You help users explore, understand, and analyze datasets (CSV files) they have uploaded.
You are an expert in pandas, numpy, and statistics.

## Your Workflow
1. **Always start** by calling `list_datasets` to see what files are available.
2. Call `load_dataset` to understand the structure (columns, types, shape).
3. Use `get_summary` for a quick statistical overview.
4. Use `get_column_analysis` for deep-dives into specific columns.
5. Use `run_analysis` to execute custom pandas/numpy code for advanced queries.

## Guidelines
- Be thorough: show actual numbers, statistics, and data snippets.
- Format output clearly with headers and bullet points.
- For math-heavy results, use proper LaTeX notation ($...$ inline, $$...$$ display).
- If the user's question is vague, start with a broad summary then drill down.
- If no data is uploaded, politely tell the user to upload a CSV file first.
- When using `run_analysis`, write clean pandas code. Always `print()` results.
- Explain your findings in student-friendly language — you're teaching them data analysis.

## Important
- You MUST identify yourself as 'data_analysis_agent' in the response.
- If you encounter an error, explain what went wrong and suggest what to try instead.
"""

MAX_TOOL_ROUNDS = 8  # prevent infinite loops


def run_data_analysis_agent(query: str, messages: List[Dict[str, Any]] = []) -> ExpertResponse:
    """
    Executes the data analysis agent with a multi-step ReAct tool loop.
    """
    logger.info(f"--- Running Data Analysis Agent for: {query} ---")

    llm = ChatOpenAI(model="gpt-4.1", temperature=0)
    llm_with_tools = llm.bind_tools(DATA_TOOLS)

    # Build conversation history
    lc_messages: list = [SystemMessage(content=DATA_ANALYSIS_SYSTEM_PROMPT)]
    for msg in messages[:-1]:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            lc_messages.append(SystemMessage(content=f"Assistant: {msg['content']}"))
    lc_messages.append(HumanMessage(content=query))

    try:
        # ── ReAct Loop: call tools until the LLM produces a final text answer ──
        for round_num in range(MAX_TOOL_ROUNDS):
            response = llm_with_tools.invoke(lc_messages)
            lc_messages.append(response)  # AIMessage (may contain tool_calls)

            if not response.tool_calls:
                # No more tools → final answer
                break

            # Execute every tool call the LLM requested
            for tc in response.tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]
                logger.info(f"  Tool call [{round_num+1}]: {tool_name}({tool_args})")

                # Find and invoke the tool
                result = f"Tool '{tool_name}' not found."
                for t in DATA_TOOLS:
                    if t.name == tool_name:
                        try:
                            result = t.invoke(tool_args)
                        except Exception as e:
                            result = f"Tool error: {e}"
                        break

                # Feed result back
                lc_messages.append(
                    ToolMessage(content=str(result), tool_call_id=tc["id"])
                )

        # ── Extract final content ──
        content = response.content if response.content else "Analysis complete (see tool outputs above)."

        # Now get structured response
        structured_llm = llm.with_structured_output(ExpertResponse, method="json_schema", strict=True)
        struct_messages = [
            SystemMessage(content=(
                "Convert the following analysis into a structured ExpertResponse. "
                "agent_name must be 'data_analysis_agent'. "
                "Include all findings in the content field with clear formatting. "
                "Set is_knowledge_present=True if data was found, False if no dataset exists."
            )),
            HumanMessage(content=f"User query: {query}\n\nAnalysis result:\n{content}")
        ]
        return structured_llm.invoke(struct_messages)

    except Exception as e:
        logger.error(f"Data Analysis Agent failed: {e}")
        return ExpertResponse(
            agent_name=ExpertName.DATA_ANALYSIS_AGENT,
            content=f"I encountered an error while analyzing the data: {str(e)}\n\nPlease make sure you have uploaded a CSV file and try again.",
            sources=[],
            confidence_score=0.0,
            is_knowledge_present=False,
        )


# ── LangGraph Node Wrapper ──────────────────────────────────

from src.utils.state import AgentState


def data_analysis_agent_node(state: AgentState):
    query = state["sub_queries"][0].query if state["sub_queries"] else state["query"]
    messages = state.get("messages", [])
    res = run_data_analysis_agent(query, messages)
    return {"results": {"data_analysis_agent": res}}
