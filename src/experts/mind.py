import logging

logger = logging.getLogger(__name__)
from langchain_core.messages import SystemMessage, HumanMessage
from src.utils.llm import chat_llm

from src.utils.state import AgentState
from src.schemas.models import MindAgentResponse
from src.experts.base import run_expert

MIND_SYSTEM_PROMPT = """You are the Mind Agent of Saarthi. Merge the expert answers below into ONE clear answer for a student.
- Use only what the experts found; drop "no information" sections; note real disagreements.
- Put a numbered marker [1], [2] after each fact and give a matching reference (agent, file, short snippet).
- Structure with ## headings; be educational and concise.
- Math: every expression in LaTeX — $H(s)$ inline, $$...$$ on its own line; never bare LaTeX or Unicode math."""


def mind_fan_out_node(state: AgentState):
    """
    Fan-out node: Queries all 3 RAG agents and collects their responses.
    """
    query = state["query"]
    logger.info(f"--- Mind Mode: Fan-out to all RAG agents for: {query} ---")

    agent_results = {}
    from concurrent.futures import ThreadPoolExecutor, as_completed

    import contextvars
    with ThreadPoolExecutor(max_workers=3) as pool:
        # copy_context so the request's model tier / usage collector reach the workers
        futs = {
            pool.submit(contextvars.copy_context().run, run_expert, name, query, "planning"): name
            for name in ("notes_agent", "books_agent", "video_agent")
        }
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                res, trace = fut.result()
                agent_results[name] = res
                agent_results[f"{name}_trace"] = trace
                logger.info(
                    "--- %s: confidence=%s knowledge=%s ---",
                    name, res.confidence_score, res.is_knowledge_present,
                )
            except Exception as e:
                logger.error("--- %s failed: %s ---", name, e)

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
    llm = chat_llm(temperature=0.2)
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
