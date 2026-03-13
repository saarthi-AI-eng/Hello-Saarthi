import logging

logger = logging.getLogger(__name__)
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from src.utils.state import AgentState
from src.schemas.models import MindAgentResponse
from src.experts.base import run_expert

MIND_SYSTEM_PROMPT = """You are the **Mind Agent** — the synthesis brain of the Saarthi AI Study Assistant.

You receive answers from multiple expert agents (Notes Agent, Books Agent, Video Agent), each with their own sources and citations. Your job is to:

1. **Merge & Synthesize** all provided answers into ONE comprehensive, clear, well-structured response.
2. **Resolve contradictions** — if agents disagree, present the most accurate view and note the discrepancy.
3. **Add inline citations** — Use numbered markers like [1], [2], [3] at relevant points in your text.
4. **Be thorough** — Combine knowledge from all sources. Don't just pick one agent's answer.
5. **Be educational** — Write in a clear, student-friendly way. Use examples, analogies, and step-by-step explanations.
6. **Use proper math notation** — Write LaTeX equations within \\( ... \\) for inline and \\[ ... \\] for display.

For each citation marker [N], you MUST have a matching numbered entry in the references list with:
- The source agent name (e.g., "Notes Agent", "Books Agent", "Video Agent")
- The source file name
- A brief snippet proving the citation

Example output:
"The Z-transform converts a discrete-time signal x[n] into a complex function X(z) [1]. The Region of Convergence (ROC) determines where this transform converges [2], and for a causal system, the ROC extends outward from the outermost pole [3]."

With references:
[1] Notes Agent — Z-Transform_page_1.txt — "The Z-transform is defined as..."
[2] Books Agent — DSP_Chapter3.pdf — "The ROC is the set of z values..."
[3] Video Agent — Lecture_3_transcript.txt — "For causal systems, we know that..."
"""


def mind_fan_out_node(state: AgentState):
    """
    Fan-out node: Queries all 3 RAG agents and collects their responses.
    """
    query = state["query"]
    logger.info(f"--- Mind Mode: Fan-out to all RAG agents for: {query} ---")

    agent_results = {}
    for agent_name in ["notes_agent", "books_agent", "video_agent"]:
        try:
            logger.info(f"--- Querying {agent_name}... ---")
            res = run_expert(agent_name, query, mode="planning")
            agent_results[agent_name] = res
            logger.info(f"--- {agent_name}: confidence={res.confidence_score}, knowledge_present={res.is_knowledge_present} ---")
        except Exception as e:
            logger.error(f"--- {agent_name} failed: {e} ---")

    return {"results": agent_results}


def mind_agent_node(state: AgentState):
    """
    Mind Agent node: Takes all RAG agent results and synthesizes one rich answer.
    Uses GPT-5.2 for superior synthesis.
    """
    query = state["query"]
    results = state.get("results", {})

    logger.info(f"--- Mind Agent synthesizing... ---")

    # Build context from all agent responses
    agent_sections = []
    for agent_key, label in [("notes_agent", "Notes Agent"), ("books_agent", "Books Agent"), ("video_agent", "Video Agent")]:
        res = results.get(agent_key)
        if res is None:
            continue

        content = res.content if hasattr(res, 'content') else res.get('content', '')
        is_present = res.is_knowledge_present if hasattr(res, 'is_knowledge_present') else res.get('is_knowledge_present', True)
        confidence = res.confidence_score if hasattr(res, 'confidence_score') else res.get('confidence_score', 0.0)
        sources = res.sources if hasattr(res, 'sources') else res.get('sources', [])

        if not is_present or not content.strip():
            agent_sections.append(f"### {label}\n[No relevant information found in this knowledge base.]\n")
            continue

        source_info = ""
        for s in sources:
            s_file = s.source_file if hasattr(s, 'source_file') else s.get('source_file', 'Unknown')
            s_snippet = s.snippet if hasattr(s, 'snippet') else s.get('snippet', '')
            source_info += f"  - File: {s_file} | Snippet: {s_snippet}\n"

        section = f"### {label} (Confidence: {confidence})\n{content}\n"
        if source_info:
            section += f"Sources:\n{source_info}\n"
        agent_sections.append(section)

    combined_context = "\n---\n".join(agent_sections)

    # Synthesize with GPT-5.2
    llm = ChatOpenAI(model="gpt-4.1", temperature=0.2)  # Using gpt-4.1 as gpt-5.2 identifier
    structured_llm = llm.with_structured_output(MindAgentResponse, method="json_schema", strict=True)

    synthesis_prompt = f"""The user asked: "{query}"

Here are the responses from all expert agents:

{combined_context}

Now synthesize these into ONE comprehensive, well-structured answer with inline citation markers [1], [2], etc.
Make sure every fact has a citation. Be thorough, educational, and clear.
Use proper LaTeX for any mathematical expressions."""

    messages = [
        SystemMessage(content=MIND_SYSTEM_PROMPT),
        HumanMessage(content=synthesis_prompt)
    ]

    response = structured_llm.invoke(messages)
    logger.info(f"--- Mind Agent done: {len(response.references)} citations ---")

    return {"results": {"mind_agent": response}}
