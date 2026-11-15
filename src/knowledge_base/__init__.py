"""BGE-M3 + Qdrant knowledge-base pipeline.

Separate from the existing OpenAI + FAISS pipeline (scripts/build_knowledge_base.py,
src/tools/kb_ops.py) by deliberate choice — no paid API, self-hosted vector
store. See docs/KB_PIPELINE_SETUP.md for the full architecture.

Consumes scripts.schemas.ContentRecord JSONL (the existing OCR/transcript
output format) — never re-implements OCR/transcription.
"""
