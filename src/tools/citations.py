"""Citation injection (WBS 3.3.3, spec §4.4): every grounded answer cites ≥ 1 retrieved
chunk, inline, as [Lecture 4, p. 12] or [Video: DSP Week 3, 14:22]."""
from __future__ import annotations

import re


def _title(c) -> str:
    get = c.get if isinstance(c, dict) else (lambda k, d=None: getattr(c, k, d))
    t = get("title") or get("material_title") or get("video_title") or get("source_file") or "Course material"
    return str(t).replace("_", " ").strip()


def _ts(sec) -> str:
    sec = int(sec or 0)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def source_label(c) -> str:
    get = c.get if isinstance(c, dict) else (lambda k, d=None: getattr(c, k, d))
    title = _title(c)
    if get("start_sec") is not None:
        return f"[Video: {title}, {_ts(get('start_sec'))}]"
    page = get("page") if get("page") is not None else get("page_number")
    if page:
        return f"[{title}, p. {page}]"
    return f"[{title}]"


def excerpts_block(chunks, max_chars: int = 900) -> str:
    """Excerpts for the prompt, each headed by the label the model must cite."""
    parts = []
    for c in chunks:
        text = c.get("text") if isinstance(c, dict) else getattr(c, "text", "")
        parts.append(f"{source_label(c)}\n{(text or '').strip()[:max_chars]}")
    return "\n\n---\n\n".join(parts)


def labels(chunks) -> list[str]:
    seen: dict[str, None] = {}
    for c in chunks:
        seen.setdefault(source_label(c), None)
    return list(seen)


def is_cited(answer: str, chunks) -> bool:
    """True if the answer contains one of the chunk labels (or its title in brackets)."""
    text = (answer or "").lower()
    for c in chunks:
        if source_label(c).lower() in text:
            return True
        if re.search(r"\[[^\]]*" + re.escape(_title(c).lower()) + r"[^\]]*\]", text):
            return True
    return False


def sources_suffix(answer: str, chunks, limit: int = 3) -> str:
    """Appended when the model forgot to cite, so 100% of grounded answers carry a source."""
    if not chunks or is_cited(answer, chunks):
        return ""
    return "\n\n**Sources:** " + "; ".join(labels(chunks)[:limit])
