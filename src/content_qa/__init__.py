"""Automated Content Quality Assessment (Phase 1).

Scores individual OCR pages / transcript segments (never a whole PDF/video
at once — see docs/KB_PIPELINE_SETUP.md) and assigns qa_status
(approved/pending/rejected) + explainable qa metadata, without touching
OCR/transcription code. Runs between ingestion and normalization:

    OCR/transcription -> [this package, via scripts/run_content_qa.py] -> normalize_content_kb

Manual QA dashboard/correction UI is out of scope — see the module docstring
in scripts/run_content_qa.py.
"""
