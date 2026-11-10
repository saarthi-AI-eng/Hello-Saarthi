# Content Pipeline Setup and Usage Guide

Covers the OCR/mathematical-OCR ingestion pipeline (`scripts/ingest_notes.py`)
and the video transcription pipeline (`scripts/ingest_videos.py`). Written
for someone who has just cloned this repository and has no other context.

## 1. Prerequisites

**Mandatory:**
- Python 3.12 or 3.13 (the repo's `.python-version` pins 3.12; this
  pipeline was actually developed and tested against 3.13.2 — both are
  expected to work, but if you hit a dependency resolution issue, try
  the other one first).
- Git.
- [FFmpeg](https://ffmpeg.org/) — required for video transcription (audio
  extraction). On Windows: `winget install --id Gyan.FFmpeg.Essentials -e`.
  On Linux: your package manager (`apt install ffmpeg`, etc). On macOS:
  `brew install ffmpeg`.
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) — required
  for the notes/math pipeline (it's the always-on primary OCR pass). On
  Windows: `winget install --id UB-Mannheim.TesseractOCR -e`. On Linux:
  `apt install tesseract-ocr`. On macOS: `brew install tesseract`.

**Optional, feature-dependent:**
- An NVIDIA GPU + driver, if you want GPU acceleration for PaddleOCR
  (§3). Not required — the pipeline runs on CPU with no code changes.
- Disk space: budget **~5-10GB free** if you plan to use PaddleOCR
  (detection+recognition models, a few hundred MB) and/or a GPU wheel
  (the CUDA runtime bundled in `paddlepaddle-gpu` adds a few GB).
  `faster-whisper`'s models range from ~75MB (`tiny`) to ~3GB
  (`large-v3`) depending on which size you choose.
- CPU/RAM: no hard minimum measured; this pipeline was developed and
  benchmarked on a 14-core/16.8GB-RAM laptop. A faster-whisper `tiny` or
  `base` model and Tesseract-only OCR will run comfortably on much less.

## 2. Clone and Setup

```bash
git clone <this-repository-url>
cd Hello-Saarthi-26
```

**Create and activate a virtual environment:**

Windows PowerShell:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Linux/macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Install dependencies:**
```bash
pip install -r requirements.txt
pip install -r requirements-content-pipeline.txt
pip install -r saarthi_backend/requirements.txt   # only if you also run the backend app
```

**PaddleOCR (optional, not in the requirements files above — see
`requirements-content-pipeline.txt`'s own comments for the exact reason
and commands)**: required only if you want to use the higher-accuracy
PaddleOCR fallback (`SAARTHI_HANDWRITING_OCR=paddleocr`, §4) instead of
Tesseract alone.

CPU-only:
```bash
pip install "paddlepaddle>=3.1" "paddleocr>=3.0"
```

GPU-capable machine (also works CPU-only if the GPU isn't used — one
install covers both, see §3):
```bash
pip install "paddleocr>=3.0"
pip install https://paddle-whl.cdn.bcebos.com/stable/cu126/paddlepaddle-gpu/paddlepaddle_gpu-3.3.1-cp313-cp313-win_amd64.whl
```
Pick the `cuXXX`/`cpXXX` path matching your actual CUDA driver and Python
version — browse
`https://www.paddlepaddle.org.cn/packages/stable/<cuXXX>/paddlepaddle-gpu/`
to find the right file (it's a plain directory listing). Do not assume
the `cu126`/`cp313` URL above matches your machine.

**Verify the installation:**
```bash
python -c "import scripts.ingest_notes; print('ingest_notes OK')"
python -c "import scripts.ingest_videos; print('ingest_videos OK')"
pytest tests/content/ -q
```

**Model weights**: nothing is bundled in this repository. Every model
(Tesseract's language data, PaddleOCR's detection+recognition models,
faster-whisper's Whisper checkpoint) is downloaded automatically on
first use by its own library, to its own standard cache location — see
§5's "Model name/source/size/cache" table.

## 3. GPU Verification

**Check NVIDIA GPU + driver is visible at all:**
```bash
nvidia-smi
```
If this fails, no NVIDIA GPU/driver is available on this machine — the
pipeline will use CPU automatically, with no code change needed.

**Verify PaddleOCR can actually see a CUDA-enabled PaddlePaddle + a GPU:**
```bash
python -c "import paddle; print('compiled with CUDA:', paddle.device.is_compiled_with_cuda()); print('GPU count:', paddle.device.cuda.device_count())"
```
`scripts.ingest_notes._detect_paddleocr_device()` runs exactly this check
at runtime and logs which device it picked — look for a line like
`Loading PaddleOCR (lang='en', device='gpu', ...)` (or `device='cpu'`)
in the pipeline's own log output. **This auto-detection is the default —
you do not need to configure anything for it to use a GPU when one is
actually usable, and it never assumes a specific GPU model or amount of
VRAM.**

**Force a specific device** (override auto-detection):
```bash
export SAARTHI_PADDLEOCR_DEVICE=cpu    # or: gpu, gpu:0, gpu:1, ...
```

**Whisper (video transcription) GPU**: unlike PaddleOCR,
`faster-whisper` defaults to **CPU** even when a GPU is present — this
is a deliberate choice (see the comment in
`scripts/ingest_videos.py::LocalWhisperProvider.transcribe`): a common
"NVIDIA driver installed but CUDA Toolkit's cuBLAS runtime missing"
laptop setup makes `device="auto"` pick CUDA and then crash with a
`cublas64_*.dll` error. Opt into GPU explicitly once you've confirmed
your CUDA Toolkit (not just the driver) is actually installed:
```bash
export SAARTHI_WHISPER_DEVICE=cuda
export SAARTHI_WHISPER_COMPUTE_TYPE=float16   # optional; defaults to int8 on CPU, float16 on GPU
```

**Multiple GPUs**: select one via `SAARTHI_PADDLEOCR_DEVICE=gpu:N` for
PaddleOCR; `faster-whisper`'s underlying CTranslate2 runtime honors the
standard `CUDA_VISIBLE_DEVICES` environment variable.

**Force CPU everywhere** (e.g. to reproduce a CPU baseline, or if GPU
inference misbehaves):
```bash
export SAARTHI_PADDLEOCR_DEVICE=cpu
export SAARTHI_WHISPER_DEVICE=cpu
```

## 4. Running Mathematical and General OCR

**Input location** (default): `data/raw/notes/*.pdf` (or `.png`/`.jpg` —
see `SUPPORTED_EXTENSIONS` in `scripts/ingest_notes.py`).
**Output location** (default): `data/processed/ocr/*.jsonl`, one file per
input, one JSON record per page.

**Basic run** (Tesseract only — always available, no extra install):
```bash
python -m scripts.ingest_notes
```

**With the PaddleOCR handwriting fallback** (recommended if PaddleOCR is
installed — measurably more accurate on real handwritten notes, see
`docs/ocr-architecture.md` and `docs/content-management.md`):
```bash
export SAARTHI_HANDWRITING_OCR=paddleocr
python -m scripts.ingest_notes
```

**Enable mathematical-equation processing** (opt-in, additive — extracts
per-equation-block bounding boxes, a second OCR hypothesis, conservative
`10g`→`log`-style normalization, and per-block quality flags; see
`scripts/ingest_notes.py::_analyze_math_equation_blocks` and
`docs/content-management.md` for the full field reference):
```bash
export SAARTHI_HANDWRITING_OCR=paddleocr
export SAARTHI_MATH_ANALYSIS=1
python -m scripts.ingest_notes
```

**Enable the coarser, band-based region analysis too** (older,
complementary mechanism — works even on pages Tesseract wins, where the
line-bbox-based math analysis above cannot run; needs
`scripts/layout_detector.py` + `scripts/recognition_router.py`, both
included in this repository):
```bash
export SAARTHI_REGION_ANALYSIS=1
```

**Process a single file**, or restrict to one page:
```bash
python -m scripts.ingest_notes --file "AnalogFilters.pdf"
python -m scripts.ingest_notes --file "AnalogFilters.pdf" --page 1
```

**Resume an interrupted large batch** (checkpoints each page as it
completes; a crash partway through doesn't require reprocessing already-
done pages):
```bash
python -m scripts.ingest_notes --resume
```

**Select the output directory, render DPI, or course/topic metadata:**
```bash
python -m scripts.ingest_notes --output data/processed/ocr_custom --dpi 350 --course DSP
```

**Inspect the generated JSONL**: each line is a `ContentRecord` (see
`scripts/schemas.py`) — `text` is the final page text, `metadata` holds
everything else (OCR engine/confidence, quality flags, equation blocks,
etc.):
```bash
python -c "import json; [print(json.loads(l)['text'][:200]) for l in open('data/processed/ocr/AnalogFilters.jsonl', encoding='utf-8')]"
```

## 5. Running Video Transcription

**Supported formats**: anything FFmpeg can decode (the pipeline extracts
a 16kHz mono WAV first) — `.mp4`, `.mkv`, `.mov`, `.avi`, etc.

**Input**: `--input <dir>` (default: `data/raw/videos/`) or `--file
<name>` for one video. **Output**: `--output <dir>` (default:
`data/processed/transcripts/`) — one `.jsonl` (structured, timestamped
segments) and one `.txt` (plain human-readable transcript) per video.

**Basic run** (auto-detects an existing `.vtt`/`.srt` subtitle sidecar
first, then falls back to local Whisper transcription):
```bash
python -m scripts.ingest_videos
```

**Force a specific provider:**
```bash
python -m scripts.ingest_videos --provider local_whisper --whisper-model base
# or: --provider vtt | --provider srt | --provider openai (needs OPENAI_API_KEY)
```

**Whisper model size** (`tiny`/`base`/`small`/`medium`/`large-v3` —
larger is slower but more accurate; `tiny`/`base` are reasonable for a
quick check):
```bash
python -m scripts.ingest_videos --whisper-model base
# or: export SAARTHI_WHISPER_MODEL=base
```

**Language**: faster-whisper auto-detects by default; there is currently
no CLI flag to force a language — set it via the `language` parameter if
you call `LocalWhisperProvider.transcribe()` directly from your own code.

**GPU/CPU execution**: see §3's Whisper GPU note — CPU by default,
explicit `SAARTHI_WHISPER_DEVICE=cuda` opt-in.

**Resume behavior**: video transcription does not currently support
page-level resume the way OCR does (a video is one unit of work, not
many pages) — a re-run with the same `--output` simply reprocesses the
file; it does not skip already-completed videos. If you need to resume a
large batch, move already-processed video files out of the input
directory between runs.

**Verified this session**: ran end-to-end against a real 7.5MB lecture
video (`data/raw/notes/videos/` — see your own `data/raw/videos/`
directory) with `--whisper-model tiny`: 29 segments produced, 0
failures, and the transcribed text was manually spot-checked and found
coherent and genuinely useful (clean sentence boundaries, reasonable
timestamps, correct beginning/end-of-lecture framing) — not just "ran
without crashing."

## 6. Troubleshooting

**"CUDA unavailable" / PaddleOCR silently uses CPU**: expected and safe
— `scripts.ingest_notes._detect_paddleocr_device()` falls back to CPU
automatically. Check `nvidia-smi` and the `paddle.device.is_compiled_with_cuda()`
check in §3 to see which part of the chain (driver, PaddlePaddle wheel)
is missing.

**Incompatible PaddlePaddle/PaddleOCR versions**: install both together
(`pip install "paddlepaddle>=3.1" "paddleocr>=3.0"` or the GPU wheel
variant in §2) rather than upgrading one in isolation. If you see an
import error mentioning `oneDNN`/`PIR`, that's a known PaddlePaddle
3.3.1 CPU-backend issue with specific optional models — see
`docs/ocr-architecture.md` for the exact reproduction; it does not
affect the default pipeline configuration.

**Missing FFmpeg**: `scripts/ingest_videos.py::extract_audio` raises a
clear `RuntimeError` naming the exact install command for your OS (or
set `FFMPEG_CMD` to an explicit path).

**Missing Tesseract**: `scripts/ingest_notes.py::ocr_image` raises a
clear `RuntimeError` naming the exact install command, or set
`TESSERACT_CMD` to an explicit path to `tesseract.exe`/`tesseract`.

**Model download failures** (PaddleOCR/Whisper): both use their own
libraries' standard HTTP download + local cache; a failed download
usually means a network/proxy issue reaching Hugging Face (Whisper) or
PaddleOCR's own model host — retry, or set `HF_ENDPOINT`/proxy env vars
as your network requires.

**GPU out-of-memory**: lower the Whisper model size
(`--whisper-model base` instead of `large-v3`), or force CPU
(`SAARTHI_WHISPER_DEVICE=cpu` / `SAARTHI_PADDLEOCR_DEVICE=cpu`) — this
pipeline does not currently implement automatic OOM-triggered fallback,
only explicit, intentional device selection.

**Missing Python packages**: re-run `pip install -r requirements-content-pipeline.txt`
— every optional dependency's exact install command is documented in
that file's own comments next to the feature that needs it.

**Unsupported PDF or video format**: OCR supports PDF, PNG, JPG/JPEG
(`SUPPORTED_EXTENSIONS` in `scripts/ingest_notes.py`); video transcription
supports whatever your installed FFmpeg can decode.

**Interrupted processing**: for OCR, use `--resume` (§4). For video
transcription, see §5's resume note.

## 7. Expected Outputs

```
data/processed/ocr/
  AnalogFilters.jsonl          # one JSON record per page; see scripts/schemas.py ContentRecord
data/processed/transcripts/
  <video-name>.jsonl           # one JSON record per transcript segment, with start/end timestamps
  <video-name>.txt             # plain-text human-readable transcript
```

Each OCR `ContentRecord`'s `metadata` dict includes (not exhaustive —
see `scripts/schemas.py` and `docs/content-management.md` for the full,
current field list): `ocr_engine`, `ocr_confidence`, `page_quality`,
`review_reasons`, `math_equation_blocks` (when `SAARTHI_MATH_ANALYSIS=1`),
`processing_time_seconds`. This repository does not include any actual
generated OCR/transcript output or the raw PDFs/videos that would
produce them — those are private, regenerable, and excluded from Git
(see `.gitignore`).

## 8. Clean-Clone Verification Procedure

To verify this pipeline actually works from a fresh clone (not just in
the original development environment):

```bash
git clone <repo-url> clean-clone-test
cd clean-clone-test
python -m venv .venv
# activate it (see §2)
pip install -r requirements.txt
pip install -r requirements-content-pipeline.txt
pytest tests/content/ -q                                  # should pass with 0 failures
python -c "import scripts.ingest_notes, scripts.ingest_videos"  # should import cleanly
# with at least one real PDF in data/raw/notes/ and one real video in data/raw/videos/:
python -m scripts.ingest_notes --file "<your-test-pdf>"
python -m scripts.ingest_videos --file "<your-test-video>" --whisper-model tiny
```

**What this session actually verified** (not an idealized claim):
- All 213 tests pass from a fully-synced copy of this repository
  (`pytest -q` from the repo root).
- `scripts.ingest_notes` and `scripts.ingest_videos` both import cleanly
  with only the files present in this repository (no missing-module
  errors).
- PaddleOCR GPU auto-detection was verified to correctly report `"gpu"`
  on a machine with a working CUDA-enabled PaddlePaddle install, and the
  code path that falls back to `"cpu"` was reviewed (not separately
  re-verified on a GPU-less machine this session — see §9 of
  `docs/GITHUB_READY_FILE_MANIFEST.md` for what remains unverified).
- Video transcription was run end-to-end on a real video file with the
  `tiny` Whisper model: 29 segments, 0 failures, manually spot-checked
  for coherence.
- **Not verified this session**: installing into a genuinely fresh
  virtual environment with *only* the files in `Hello-Saarthi-26` (as
  opposed to the already-populated development environment's installed
  packages) was not performed — see the manifest for the exact scope of
  what remains to be checked before relying on this as a guarantee.
