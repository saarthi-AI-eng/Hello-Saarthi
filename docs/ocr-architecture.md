# OCR/HTR Architecture

Audience: engineers extending or operating the content-ingestion pipeline's
handwriting/OCR recognition. Companion to `docs/content-management.md`
(the operational guide); this document is the architecture/design record —
what was tried, what works, what doesn't, and why.

## 1. Two pipelines, not one

There are **two** OCR paths in this repo, and only one is the default:

| | Page-level pipeline (default) | Hybrid region pipeline (opt-in) |
|---|---|---|
| Entry point | `scripts.ingest_notes.ocr_image()` / `process_pdf()` | `scripts.hybrid_pipeline.process_page_hybrid()` |
| Unit of work | whole page, multiple preprocessing/PSM attempts | layout-detected region |
| Status | production, measured, used by `ingest_notes.py`'s CLI | evaluated, **not** wired into the CLI's default path |
| Why | proven: CER 0.341 (PaddleOCR) vs 0.769 (Tesseract) on real data | heuristic layout detection; UniMERNet now a real, integrated, opt-in engine (§4) but not a routing default; HTR-VT runs on CPU but has no usable checkpoint |

**The hybrid pipeline is not the default** and nothing in `ingest_notes.py`
calls it automatically. This is a deliberate decision, not an oversight —
see §6 "Known limitations" and the final recommendation in
`data/evaluation/hybrid_ocr_comparison_report.md`.

**Page-level checkpointing** (`scripts.ingest_notes.process_pdf`'s
`checkpoint_path` param / the CLI's `--resume` flag): each PDF page's
record is appended to the output JSONL as soon as it's done, and a page
already present there (from a prior, interrupted run) is reused instead of
reprocessed. Opt-in — default behavior (`--resume` unset) is unchanged from
before: bulk in-memory collection, one write at the end. For an 800-page
batch job where a crash at page 400 shouldn't mean repeating the first 399:
```bash
python -m scripts.ingest_notes --input data/raw/notes --output data/processed/ocr --resume
```

## 2. Data flow

```
PDF/image
  │
  ├─ native PDF text layer present (after stripping known scanner-app
  │  watermarks — see below)? ──yes──> printed_text, no OCR (both pipelines)
  │
  no
  ▼
render page (pypdfium2, configurable DPI)
  │
  ├── PAGE-LEVEL PIPELINE (default) ─────────────────────────────────
  │     preprocess_image_variants() × Tesseract PSM modes
  │     → region-band re-OCR (_detect_text_bands)
  │     → optional SAARTHI_HANDWRITING_OCR fallback (trocr | paddleocr)
  │     → best-of-N via _attempt_rank()
  │     → ContentRecord (page-level text)
  │
  └── HYBRID PIPELINE (opt-in, scripts.hybrid_pipeline) ─────────────
        layout_detector.detect_regions()        (§3)
          │  band segmentation (reused from ingest_notes) +
          │  heuristic region_type classification
          ▼
        recognition_router.recognize_region()    (§4)
          │  region_type → (primary engine, fallback engine)
          │  primary → fallback only if primary is low-confidence
          ▼
        verification.verify_region_result()      (§5)
          │  empty/completeness/anomaly/disagreement/LaTeX/code checks
          ▼
        PageResult (regions + verification + joined text)
```

### Native-text detection: a real bug, found and fixed against the expanded raw-data set

When 6 new PDFs were added to `data/raw/notes/`, inventorying them (page
counts, native-text-layer presence) found that 3 of them —
`1. DFT.pdf`, `Analog Filters.pdf`, `P3-ROC properties.pdf` (~39 pages
total) — report exactly 24 characters of "native text" on every page:
the literal string `"Scanned with CamScanner\n"`, a watermark the
CamScanner app stamps into a PDF's text layer even when the page is a
pure image scan with no real digital text. 24 ≥ `_MIN_NATIVE_TEXT_CHARS`
(20), so the existing native-text-layer shortcut would have accepted this
watermark as "real native text", stored it as the page's **entire
content**, and never run OCR — silently discarding 100% of the actual
handwritten notes on every page of 3 PDFs. This is the exact failure mode
`scripts.layout_detector`'s docstring and this document's data-flow
diagram already warned about in the abstract ("do not classify an entire
page as printed because some native text exists") — now confirmed as a
real, measured bug in this project's own data, not a hypothetical.

**Fixed**: `ingest_notes._strip_known_watermarks()` strips known
scanner-app watermark substrings (currently just the one pattern found;
easy to extend) before the native-text-length check — and from the
content actually stored, in case a page genuinely has both real text and
the watermark. Verified against the real files: all three PDFs' pages now
correctly route to OCR instead of the watermark-fooled shortcut.

**What was investigated and NOT built**: the task that prompted this
inventory also raised the more general concern of *genuinely* mixed
pages — printed headings or captions alongside handwritten notes on the
same page, needing native-text and OCR'd regions merged. Checked for this
directly: every distinct non-empty native-text string across all 89 pages
in the full corpus was enumerated (not sampled) — exactly two categories
exist, the CamScanner watermark and the 5 pages of `DSP Mod 1
F01-Signals-pages.pdf` (a printed slide deck with no handwriting at all).
**No page in this project's actual raw data mixes real native text with
image-only handwritten content** — so the fuller native+OCR region-merge
architecture was not built; it would be speculative infrastructure for a
scenario that doesn't occur in this corpus (YAGNI). If a future PDF
genuinely mixes the two, `extract_pdf_native_text()`'s all-or-nothing
page-level decision would need revisiting then, with real content to
validate against.

## 3. Layout detection (`scripts/layout_detector.py`)

**Evaluated and rejected**: PaddleX's object-detection-family layout
models — `PicoDet-S_layout_3cls` and `PP-DocLayout-S` were both downloaded
and run. Both hit the identical crash:

```
NotImplementedError: (Unimplemented) ConvertPirAttribute2RuntimeAttribute
not support [pir::ArrayAttribute<pir::DoubleAttribute>]
(at ..\paddle\fluid\framework\new_executor\instruction\onednn\onednn_instruction.cc:118)
```

This is the same class of PaddlePaddle 3.3.1 CPU oneDNN/PIR bug already
documented in `docs/content-management.md` for PaddleOCR's own detection
model — but there, `enable_mkldnn=False` on the `PaddleOCR()` wrapper fixed
it. For these object-detection-family models, `create_model(..., device='cpu',
enable_mkldnn=False)` and the global `FLAGS_use_mkldnn=0` environment
variable were **both** tried and **neither fixed it**. Reproduce:

```bash
python -c "from paddlex import create_model; m = create_model('PicoDet-S_layout_3cls', device='cpu'); list(m.predict('some_page.png'))"
```

Likely GPU execution avoids this code path entirely (it's the CPU
static-graph oneDNN instruction path specifically) — untested here, no GPU
available.

**What's implemented instead**: region *segmentation* reuses
`ingest_notes._detect_text_bands` (row-projection gaps — already
production-proven). Region *type* classification is a heuristic built from
signals the pipeline already computes (math-symbol density, code
keyword/punctuation density, Tesseract's own engine-calibrated confidence
for "is this printed", ink density for diagram detection) — not a vision
model. See the module docstring for exact thresholds and reasoning. This is
explicitly a stopgap: table vs. diagram is not distinguished, and the
heuristic is honestly weak at telling cursive handwritten prose from
handwritten math-adjacent prose from pixels alone (hence `unknown` is the
deliberate safe default rather than a forced guess).

## 4. Recognition routing (`scripts/recognition_router.py`)

| region_type | primary | fallback | notes |
|---|---|---|---|
| `handwritten_text` | paddleocr | trocr | matches the measured best engine |
| `printed_text` | paddleocr | tesseract_light | |
| `mathematical_expression` | paddleocr | trocr | UniMERNet now works and is a selectable engine, but is **not** a ROUTING_TABLE default — see below; always flagged for review |
| `code` | paddleocr | trocr | **not** HTR-VT — see below; always flagged for review |
| `diagram` / `table` | — | — | never auto-recognized, human review only |
| `unknown` | paddleocr | tesseract_light | routes to the measured-best engine, not "confirmed non-text" |

`tesseract_light` (`ingest_notes.run_light_tesseract`) is a single `--psm 6`
attempt, not the full multi-variant sweep (`tesseract` /
`ingest_notes.ocr_image`, ~15-20 Tesseract invocations) — using the full
sweep as a per-region *fallback* was measured to push the hybrid pipeline's
cost to 263.6s/page; the light version brought that to 221.6s/page (16%
faster, same accuracy). `tesseract` (full sweep) stays available for
explicit primary use, where the thorough variant search earns its cost.

### HTR-VT / UniMERNet / PP-FormulaNet — genuinely evaluated, mixed results

All three were installed and actually run, not assumed unsuitable from
documentation alone. Current status: **UniMERNet is a real, working,
integrated engine** (`scripts/unimernet_adapter.py` + `AVAILABLE_ENGINES["unimernet"]`
— opt in via `RouterConfig`, not a `ROUTING_TABLE` default yet). **HTR-VT
runs on CPU but has no usable checkpoint for this content's language** —
a different, more specific blocker than originally reported. PP-FormulaNet-S
was tried and measured to fail outright.

**HTR-VT** — cloning the actual repository
(`github.com/Intellindust-AI-Lab/HTR-VT`) and reading the real source (not
just the README) overturned the original assessment: `apex` is never
imported anywhere in the inference path (`environment.yaml`'s `apex==0.1`
pin is unused dead weight from the authors' training environment), and the
one hard CUDA call — `test.py`'s `model = model.cuda()` — is a one-line
patch (`model.to(device)`). In an isolated Python venv (CPU-only torch,
`timm`, `opencv-python-headless`, `scikit-image`, `torchvision` — kept
completely separate from this project's main Python 3.13 venv), a real
855MB checkpoint (`LAM_10w.pth`, via `gdown --folder` on the README's
Google Drive link) loaded with `strict=True` — every parameter shape
matched exactly — and a forward pass completed on CPU in well under a
second.

The actual remaining blocker is different from what was first reported:
HTR-VT's character vocabulary (`ralph`) is built dynamically from the
training split's label `.txt` files
(`data.dataset.get_alphabet()` — `sorted(set(''.join(all_training_labels)))`),
not published as a fixed constant or embedded in the checkpoint. The only
checkpoint obtained in the first pass was **LAM** (Italian historical
manuscripts) — its 89-character alphabet was reconstructed from LAM's real
label archive (25,823 `.txt` files) and verified to exactly match the
checkpoint's `nb_cls=90` (89 chars + CTC blank). Real end-to-end inference
on a real line crop from this project's own data (`"↳ FFT algorithms*."`,
ground truth) decoded to `' A #t IAgoriermi.'` — wrong, but not random
noise ("IAgoriermi" visually echoes "algorithms"), consistent with a
visually-competent model given the wrong training language.

**Follow-up investigation — does an IAM (English) checkpoint exist at
all?** Three findings, in order:
1. The checkpoints Drive folder's *complete* structure was enumerated
   (recursively, zero downloads, via `gdown`'s internal folder-parsing
   function) — it contains only `lam/LAM_10w.pth` and an **empty** `read/`
   folder. No `iam/` folder exists there at all; this is not a crawl-depth
   artifact.
2. The repository's own GitHub Issues confirm why: maintainer
   `YutingLi0606` stated (closed issue, Feb 2025) that IAM weights are
   hosted on a *former employer's* server and the IAM dataset itself is no
   longer publicly accessible — no IAM checkpoint will be released.
3. A third-party checkpoint does exist:
   `huggingface.co/Mir0da/HTR-VT-english`, from a HAW Hamburg Bachelor
   thesis ("Comparison of language-specific HTR models", Sophie Zach). Its
   `run.log` is a real, readable training log (not just a filename) showing
   genuine training on `./data/iam/lines/`, `nb_cls: 80` (matches IAM's
   documented class count exactly), and validation `CER: 0.0900` /
   `WER: 0.2823` on IAM's own validation set — strong evidence this is a
   legitimately IAM-trained checkpoint.

**Still blocked, for two independent reasons**: (a) no citable, verified
source for IAM's *exact* character-to-index mapping was found despite three
separate searches (SimpleHTR's published char list is a 53-character
*word*-beam-search list, not the full line alphabet; the FKI database's own
page was unreachable; no academic paper text was accessible) — guessing
this mapping would silently produce meaningless decoded text with no way to
validate it, exactly the "fabricated result" this task says not to produce;
and (b) loading this specific third-party checkpoint's raw `.pth` file was
blocked by this environment's own security policy (untrusted pickle
deserialization from an unverified third-party source) — correctly, and not
worked around. Reproduction of what *was* established (LAM, real inference):
```bash
git clone --depth 1 https://github.com/Intellindust-AI-Lab/HTR-VT.git
python -m venv .venv-htrvt  # isolated — do not install into the main pipeline venv
.venv-htrvt/Scripts/pip install torch --extra-index-url https://download.pytorch.org/whl/cpu
.venv-htrvt/Scripts/pip install timm opencv-python-headless scikit-image torchvision
.venv-htrvt/Scripts/pip install gdown
python -m gdown --folder https://drive.google.com/drive/folders/1mGX9Dk7RBY5BKbqHnxwsHtCnX-SuH363
# nb_cls=90, img_size=[64,512] for LAM; state_dict_ema key, strict=True load
```

**UniMERNet** — the original "stalled download" finding was real but
specific to loading it via `paddlex.create_model('UniMERNet', ...)`, which
routes to a different (apparently poorly-reachable) mirror. Downloading
directly (`huggingface_hub.snapshot_download('wanderkid/unimernet_base')`)
worked — one connection reset at 1.06GB/1.3GB, resumed automatically on
retry in 15s. Getting it to actually *run* needed three further fixes, each
a real, distinct problem:
1. The `unimernet` PyPI package won't install on Python 3.13 (`numpy==1.26.4`
   pin, no 3.13 wheel, source build fails — this machine's bundled MinGW
   GCC 6.3.0 is below the 8.4 numpy's build requires). Fixed with an
   isolated **Python 3.11** venv (not 3.13 — a genuinely different
   requirement from HTR-VT's, which only needed isolation, not an older
   interpreter).
2. The package's own transitive dependencies conflict: latest `datasets`
   needs `pyarrow>=21` (→ `numpy>=2`), but the package's pinned
   `transformers==4.42.4` needs `numpy<2`. Fixed: `pip install "datasets<3"
   "pyarrow<15"` — versions contemporaneous with the pinned transformers.
3. The checkpoint's `config.json` claims `architectures:
   ["VisionEncoderDecoderModel"]`, but its weights belong to a *custom*
   encoder (`VariableUnimerNetModel`) that the `unimernet` package
   registers with `transformers.AutoModel` itself — loading via plain
   `transformers.VisionEncoderDecoderModel.from_pretrained` produces a
   100% key mismatch (763/763 unexpected keys). Used the package's own
   `unimernet.models.unimernet.unimernet.UniMERModel.from_config()`
   instead, which does this registration correctly — **with the
   `model_config.model_name`/`tokenizer_config.path` keys its bundled
   `unimernet_base.yaml` is missing (a packaging bug in that PyPI release)
   overridden in-memory via `OmegaConf`**, not by hand-patching the
   installed package's files — portable, no manual per-machine setup step.

**Now a real, working, integrated engine** —
`scripts/unimernet_adapter.py` + `scripts/_unimernet_worker.py`:
- `_unimernet_worker.py` is a small, standalone script that runs *inside*
  the isolated Python 3.11 venv (imports `unimernet`, nothing from this
  repo) — takes a checkpoint directory and an image path as argv, prints
  one JSON line (`{"latex": ..., "model_load_seconds": ..., "inference_seconds": ...}`
  or `{"error": ...}`) to stdout.
- `unimernet_adapter.recognize_formula(image)` runs in the **main venv**,
  never imports `unimernet`, and invokes the worker as a subprocess via
  `SAARTHI_UNIMERNET_PYTHON` (the isolated venv's `python.exe`) and
  `SAARTHI_UNIMERNET_CHECKPOINT` (the checkpoint directory) — both required
  env vars; unset raises `UniMERNetUnavailable` with a clear setup message,
  never a silent no-op.
- Wired into `recognition_router.AVAILABLE_ENGINES["unimernet"]` — real,
  selectable, and verified end-to-end through the actual production call
  path (`recognize_region()` → `verify_region_result()`), not just the
  standalone worker script. **Not** a `ROUTING_TABLE` default: most
  environments won't have the isolated venv configured, and it hasn't been
  measured as more accurate than PaddleOCR on this content yet (only shown
  structurally valid on crops tested so far) — opt in via a `RouterConfig`
  override.
- `recognize_formula()` does not build a dedicated 192×672 resize/pad step
  of its own — `unimernet`'s own `FormulaImageEvalProcessor` (invoked
  inside the worker) already does this from a raw crop, so the adapter
  passes region crops through unmodified; no separate preprocessing module
  was needed.

Real inference on the actual DFT summation formula from this project's
data, run through the full adapter → router → verification path, produced
valid, well-formed LaTeX (structure correct, some symbols wrong),
automatically flagged for mandatory human review (region_type
`mathematical_expression` is always flagged — recognized != verified) with
zero LaTeX-syntax findings from `verify_region_result()` — see
`data/evaluation/hybrid_ocr_comparison_report.md` §D for the full output.

**PP-FormulaNet-S** — downloaded and ran successfully (unlike HTR-VT/
UniMERNet, no environment blocker at all), which makes this the clean
negative-result baseline: on two different real handwritten-formula crops
from this project's own data, it produced degenerate repeated-token output
with zero usable content, e.g.:
```
\ {\begin{array}{r l}}{{{\tt b S C n}}}&{{}\\...\qquad\qquad\qquad\qquad...
```
(the `\qquad` token repeated 40+ times). `scripts.verification.validate_latex_syntax`
correctly flags this as structurally invalid, in contrast with UniMERNet's
output on the same kind of crop, which it flags as clean. This is a
measured domain mismatch, not a bug: PP-FormulaNet is trained on
printed/typeset formula images, not handwriting.

Selecting `htr_vt` or `pp_formulanet` via `RouterConfig` still raises
`RecognitionEngineUnavailable` with the exact reason above — never a silent
no-op, never a fabricated result. `unimernet` is different: it's a real
`AVAILABLE_ENGINES` entry now (see above) — selecting it without
`SAARTHI_UNIMERNET_PYTHON`/`SAARTHI_UNIMERNET_CHECKPOINT` configured raises
the same style of clear, honest error (via `UniMERNetUnavailable`,
re-raised as `RecognitionEngineUnavailable`), but configuring those two
variables makes it genuinely work — not a permanent "not compatible here"
status like HTR-VT/PP-FormulaNet.

### Why math/code still route through general OCR instead of "unknown"

A transcribed-but-unspecialized equation or code block is more useful to a
human reviewer than nothing. Both region types are **always** flagged for
review (`ALWAYS_FLAG_FOR_REVIEW_REGION_TYPES`) regardless of recognition
confidence — "recognized" is never conflated with "verified correct" for
these two types.

## 5. Verification (`scripts/verification.py`)

Real, runnable checks — no model calls:
- empty output / suspiciously-short output (floor-based, not a length guess)
- degenerate repeated-pattern detection (regex backreference; `min_repeats=20`,
  calibrated against **both** real captured outputs this project has —
  PP-FormulaNet's genuine 40+-repeat decoder-loop failure (still caught) and
  UniMERNet's genuine, structurally-valid 11-repeat `~` spacing idiom (no
  longer a false positive — an earlier `min_repeats=8` flagged it
  incorrectly; fixed and locked in with a regression test against both real
  strings, not synthetic approximations)
- primary/fallback disagreement (word-overlap heuristic — flags for
  review, never auto-picks a side)
- **fallback acceptance never compares raw confidence numbers across
  engines** — `recognition_router.recognize_region()` only lets a fallback
  replace the primary result when it strictly improves *rank tier* (real
  text where primary had none, or a confidence score where primary had
  none). A real bug, found and fixed this session: the original logic
  (`if fallback_rank > primary_rank`) fell through to comparing raw
  confidence floats whenever both engines reported their own confidence —
  i.e. "pick whichever engine's number is bigger", even though this
  project's own documentation says those numbers aren't calibrated against
  each other. When both reach tier 2, primary is left standing and
  `check_model_disagreement` flags a real disagreement for human review
  instead of silently picking a side.
- LaTeX structural validation (balanced delimiters, `\begin`/`\end` count —
  stack-based, stdlib only; not a full LaTeX parser)
- Python syntax validation (`ast.parse` — stdlib, real parser)
- C++ validation is **not** a real parser — brace/paren balance only,
  explicitly labeled weaker in its own output. No C++ parsing dependency
  was added for a content category this repo has zero real samples of
  (confirmed by inventorying `data/raw/notes/` — see §7).

VLM-assisted verification is **not implemented** — `flag_for_vlm_review()`
is a documented, unused integration point (returns a plain pending-review
record, calls nothing). No VLM API key/approved service is configured for
this project, and the task is explicit that expensive VLM calls must not
enter the default pipeline.

## 6. Known limitations

- Layout detection is heuristic, not ML-based (§3) — real accuracy numbers
  for region-type classification don't exist because no ground-truth
  region labels exist for this project's one real handwritten document.
- UniMERNet is now a real, integrated, working engine (§4) — but not a
  `ROUTING_TABLE` default, since most environments won't have its isolated
  venv configured and it hasn't been measured more accurate than PaddleOCR
  on this content yet. HTR-VT runs on CPU but has no usable checkpoint:
  the official repo publishes no IAM checkpoint at all (confirmed via the
  maintainer's own GitHub reply), and a real third-party IAM-trained
  checkpoint that was found is blocked by (a) no verifiable source for
  IAM's exact character vocabulary and (b) this environment's security
  policy against deserializing an untrusted third-party `.pth` file — see
  §4 for the full trail. PP-FormulaNet-S runs but was measured to fail
  outright on real handwritten formulas. The default hybrid pipeline's
  handwriting and math recognition still runs through PaddleOCR/TrOCR,
  region-routed — unimernet is available but must be explicitly opted into
  via `RouterConfig`.
- The one real handwritten document in this repo
  (`FFT-Notes-images-3.pdf`, 4 pages) contains dense math/outline notation
  but **no handwritten code, no diagrams, no tables, and no low-quality
  scans** — `code`/`diagram`/`table` routing and math-region review-flagging
  are implemented and unit-tested, but not evaluated against real content
  in this category, because none exists in this repo's raw data.
- No GPU was available. The PaddleX layout-model oneDNN/PIR crash (§3) and
  HTR-VT/UniMERNet's per-call latency are both plausibly GPU-sensitive —
  untested, since none was available in this environment.
- `scripts.verification.check_character_anomalies` false-positives on
  legitimate repeated short tokens in valid output (measured: UniMERNet's
  real, structurally-correct LaTeX uses many consecutive `~` spacing
  tokens, which the regex-backreference check flags as a decoder loop). A
  real, known limitation of that heuristic — not fixed this session.

## 7. Hardware this was evaluated on

Windows 11, Python 3.13.2 (main pipeline), isolated Python 3.11 venv for
UniMERNet (its pinned `numpy==1.26.4` has no 3.13 wheel) and a separate
Python venv for HTR-VT, no CUDA/GPU, 14 physical / 20 logical CPU cores,
16.8GB RAM. See `data/evaluation/hybrid_ocr_comparison_report.md` for full
measured results and the final recommendation.
