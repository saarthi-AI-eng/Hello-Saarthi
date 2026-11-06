"""Planner + faithfulness critic nodes."""
from langchain_core.messages import SystemMessage, HumanMessage
from src.utils.llm import chat_llm
from src.utils.state import AgentState


def planner_node(state: AgentState):
    q = state["query"]
    try:
        llm = chat_llm(fast=True, temperature=0)
        msg = llm.invoke([
            SystemMessage(content=(
                "Write 2-4 short numbered steps for a teaching assistant. "
                "Always include 'search course materials' as step 1. "
                "No extra prose. One step per line."
            )),
            HumanMessage(content=q),
        ])
        plan = [ln.strip(" -0123456789.") for ln in (msg.content or "").splitlines() if ln.strip()]
        return {"plan": [p for p in plan if p][:4]}
    except Exception:
        return {"plan": ["Search course materials", "Answer the student"]}


def critic_node(state: AgentState):
    results = state.get("results") or {}
    answer = ""
    for key, res in results.items():
        if key.endswith("_trace") or key in ("execution_plan", "mind_agent"):
            continue
        if hasattr(res, "content") and res.content:
            answer = res.content
            break
    if not answer:
        mind = results.get("mind_agent")
        if mind is not None and hasattr(mind, "content"):
            answer = mind.content or ""
    chunks = state.get("retrieved_chunks") or []
    evidence = "\n".join(str(c.get("text", "") if isinstance(c, dict) else getattr(c, "text", ""))[:400] for c in chunks[:6])
    if not answer:
        return {"critic_ok": False, "critic_notes": "empty answer"}
    if not evidence:
        return {"critic_ok": True, "critic_notes": "no evidence (non-RAG agent)"}
    try:
        llm = chat_llm(fast=True, temperature=0)
        verdict = llm.invoke([
            SystemMessage(content=(
                "You check tutoring answers against excerpts.\n"
                "Reply with exactly: OK or FAIL: <one sentence>.\n"
                "FAIL if a key claim is not in the excerpts."
            )),
            HumanMessage(content=f"EXCERPTS:\n{evidence}\n\nANSWER:\n{answer[:2500]}"),
        ])
        text = (verdict.content or "").strip()
        ok = text.upper().startswith("OK")
        return {"critic_ok": ok, "critic_notes": text}
    except Exception as e:
        return {"critic_ok": True, "critic_notes": f"critic skipped: {e}"}
