# data/evaluation/

`golden_questions.jsonl` — hand-written evaluation set for
`scripts/evaluate_retrieval.py`. One JSON object per line:

```json
{"question": "What is the Nyquist sampling theorem?", "expected_source_id": "VID_008", "expected_topic": "Sampling", "expected_content_type": "video_transcript"}
```

`scripts/evaluate_retrieval.py` writes its measured results back into this
directory (not committed — see `.gitignore`).

## ocr_ground_truth.jsonl

Hand-transcribed ground truth for `scripts/evaluate_ocr.py` (CER/WER
comparison across OCR engines). One JSON object per page:

```json
{"source": "data/raw/notes/FFT-Notes-images-3.pdf", "page": 1, "difficulty": "dense_notation", "description": "...", "text": "<reference transcription>"}
```

- `source` is a repo-relative path to the original PDF/image (under
  `data/raw/notes/`, which is git-ignored — the ground-truth JSONL itself
  *is* committed, since it's just text, but it's only usable against a
  checkout that has the matching raw file present).
- `page` is 1-indexed, matching `--page` in `scripts/ingest_notes.py`.
- `text` is a single annotator's best-effort reading of the page, written
  as plain text (not LaTeX) the way a human skimming the page would
  transcribe it — line breaks kept where they appear on the page, math
  approximated in plain ASCII (`pi`, `^`, `<=`, ...) rather than guessed
  LaTeX, since OCR engines don't output LaTeX either. Ambiguous strokes are
  read as the single most plausible character, not flagged inline — this is
  a known limitation of a single-annotator ground truth (see
  `scripts/evaluate_ocr.py`'s normalization rules for what "match" means
  given that uncertainty, and the evaluation report for how it affects
  interpretation of CER on genuinely ambiguous handwriting).

The current set (4 pages, from one real handwritten note scan already in
this repo's demo data) is intentionally small — enough to get a real,
measured comparison between engines rather than none, not a statistically
rigorous benchmark. Extend it by rendering more pages
(`scripts.ingest_notes.render_pdf_page`) and transcribing them by hand;
keep difficulty varied (`clear`, `dense_notation`, `dense_math`, and ideally
genuinely poor/cursive handwriting and different scan qualities, none of
which happened to be present in the one sample PDF used so far).

`scripts/evaluate_ocr.py` writes its measured results to
`ocr_evaluation_results.json` in this directory (not committed).
