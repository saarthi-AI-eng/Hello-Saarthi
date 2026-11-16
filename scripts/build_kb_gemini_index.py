"""One-time step: embed the fixed Qdrant knowledge-base chunks with Gemini.

Reads Qdrant settings from saarthi_backend/.env.kb and the Gemini key from
saarthi_backend/.env, then writes knowledge_base/gemini_kb/index.json, which
POST /api/kb/ask searches. Re-run only when the knowledge base changes.

Usage (from the project root):
    py -3.13 -m scripts.build_kb_gemini_index
"""
from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    load_dotenv(ROOT / "saarthi_backend" / ".env")
    load_dotenv(ROOT / "saarthi_backend" / ".env.kb")

    from src.knowledge_base.gemini_rag import build_index

    result = build_index()
    print(f"Indexed {result['chunks']} chunks with {result['embedding_model']} -> {result['path']}")


if __name__ == "__main__":
    main()
