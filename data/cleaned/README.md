# data/cleaned/

Output of `scripts/clean_content.py`: same `ContentRecord` JSONL shape as
`data/processed/`, with extraction artifacts removed (whitespace, repeated
ASR words, broken OCR line joins, etc). Timestamps, page numbers, and
mathematical notation are preserved.

This is the input to `scripts/build_catalog.py`, `scripts/validate_content.py`,
and `scripts/build_knowledge_base.py`. Records still carry
`qa_status: pending` until a reviewer approves them — cleaning is not QA.
