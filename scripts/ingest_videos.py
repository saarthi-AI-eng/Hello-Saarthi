"""
Ingest lecture videos into canonical, timestamp-preserving transcript
ContentRecords (JSONL).

Pipeline: video -> audio extraction (ffmpeg) -> speech-to-text (pluggable
provider) OR existing .vtt/.srt sidecar -> segment records -> canonical
metadata -> JSONL (+ a human-readable .txt companion).

Usage:
    python -m scripts.ingest_videos --input data/raw/videos --output data/processed/transcripts --provider auto
    python -m scripts.ingest_videos --file lecture_05.mp4 --course "Signals and Systems" --lecture "Lecture 05" --topic "Fourier Transform"

The speech-to-text layer is a small provider interface
(TranscriptionProvider) so the rest of the pipeline never hard-codes one
model. Nothing here is imported by the FastAPI backend — this pipeline is
independent of the live orchestrator/agents (src/orchestrator, src/experts),
so their runtime never depends on faster-whisper/openai being installed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from scripts.content_common import (
    PROCESSED_TRANSCRIPTS_DIR,
    RAW_VIDEOS_DIR,
    get_logger,
    log_operation,
)
from scripts.schemas import ContentRecord, ContentType, ProcessingStatus, QAStatus, write_jsonl

logger = get_logger("ingest_videos")

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".avi", ".webm"}

# faster-whisper model size for LocalWhisperProvider. "base" balances speed
# and accuracy well on a normal laptop CPU; override with --whisper-model or
# this env var (e.g. "small"/"medium" for better accuracy, "tiny" for speed).
DEFAULT_WHISPER_MODEL = os.environ.get("SAARTHI_WHISPER_MODEL", "base")


# ---------------------------------------------------------------------------
# Segment model + VTT/SRT parsing
# ---------------------------------------------------------------------------

@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str


def _timestamp_to_seconds(ts: str) -> float:
    """Parse 'HH:MM:SS.mmm' (VTT) or 'HH:MM:SS,mmm' (SRT) into seconds."""
    ts = ts.strip().replace(",", ".")
    parts = ts.split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
    elif len(parts) == 2:
        hours = "0"
        minutes, seconds = parts
    else:
        raise ValueError(f"Unrecognized timestamp: {ts!r}")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


_VTT_CUE_RE = re.compile(
    r"(\d{1,2}:)?\d{2}:\d{2}[.,]\d{3}\s*-->\s*(\d{1,2}:)?\d{2}:\d{2}[.,]\d{3}"
)


def parse_vtt(path: Path) -> List[TranscriptSegment]:
    """Minimal WebVTT cue parser: enough for timestamps + text, no styling/positioning support."""
    text = path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    segments: List[TranscriptSegment] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" in line and _VTT_CUE_RE.search(line):
            start_str, end_str = [p.strip().split(" ")[0] for p in line.split("-->")]
            start = _timestamp_to_seconds(start_str)
            end = _timestamp_to_seconds(end_str)
            i += 1
            cue_lines = []
            while i < len(lines) and lines[i].strip() != "":
                cue_lines.append(lines[i].strip())
                i += 1
            cue_text = " ".join(_strip_vtt_tags(l) for l in cue_lines).strip()
            if cue_text:
                segments.append(TranscriptSegment(start=start, end=end, text=cue_text))
        else:
            i += 1
    return segments


def _strip_vtt_tags(line: str) -> str:
    return re.sub(r"<[^>]+>", "", line)


def parse_srt(path: Path) -> List[TranscriptSegment]:
    text = path.read_text(encoding="utf-8-sig")
    blocks = re.split(r"\n\s*\n", text.strip())
    segments: List[TranscriptSegment] = []
    for block in blocks:
        lines = [l for l in block.splitlines() if l.strip() != ""]
        if len(lines) < 2:
            continue
        timing_line = next((l for l in lines if "-->" in l), None)
        if timing_line is None:
            continue
        start_str, end_str = [p.strip() for p in timing_line.split("-->")]
        start = _timestamp_to_seconds(start_str)
        end = _timestamp_to_seconds(end_str)
        text_lines = lines[lines.index(timing_line) + 1:]
        cue_text = " ".join(text_lines).strip()
        if cue_text:
            segments.append(TranscriptSegment(start=start, end=end, text=cue_text))
    return segments


# ---------------------------------------------------------------------------
# Transcription provider interface
# ---------------------------------------------------------------------------

class TranscriptionProvider(ABC):
    name: str

    @abstractmethod
    def transcribe(self, audio_path: Path, language: Optional[str] = None) -> List[TranscriptSegment]:
        ...


class LocalWhisperProvider(TranscriptionProvider):
    """Local speech-to-text via faster-whisper. Optional dependency, imported lazily."""

    name = "local_whisper"

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size

    def transcribe(self, audio_path: Path, language: Optional[str] = None) -> List[TranscriptSegment]:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. Install it with `pip install faster-whisper`, "
                "or provide a .vtt/.srt sidecar transcript next to the video instead."
            ) from exc

        # Default to CPU: faster-whisper's device="auto" picks CUDA whenever an
        # NVIDIA driver is merely present, even without the CUDA Toolkit's
        # cuBLAS runtime actually installed — a common "GPU driver but no
        # toolkit" laptop setup that then fails with a cublas64_*.dll error.
        # CPU + int8 is the reliable default; opt into GPU explicitly via env vars.
        device = os.environ.get("SAARTHI_WHISPER_DEVICE", "cpu")
        compute_type = os.environ.get("SAARTHI_WHISPER_COMPUTE_TYPE", "int8" if device == "cpu" else "float16")
        try:
            model = WhisperModel(self.model_size, device=device, compute_type=compute_type)
        except Exception as exc:  # noqa: BLE001 — e.g. a requested GPU device that isn't actually usable
            if device == "cpu":
                raise
            logger.warning(f"faster-whisper failed to load on device={device!r} ({exc}); falling back to CPU.")
            model = WhisperModel(self.model_size, device="cpu", compute_type="int8")

        raw_segments, _info = model.transcribe(str(audio_path), language=language)
        segments = [
            TranscriptSegment(start=float(seg.start), end=float(seg.end), text=seg.text.strip())
            for seg in raw_segments
            if seg.text and seg.text.strip()
        ]
        if not segments:
            raise RuntimeError(
                f"faster-whisper (model={self.model_size!r}) produced no speech segments for "
                f"{audio_path.name} — the audio may be silent, or try a larger --whisper-model."
            )
        return segments


class OpenAITranscriptionProvider(TranscriptionProvider):
    """Speech-to-text via the OpenAI transcription API. Optional, requires OPENAI_API_KEY."""

    name = "openai"

    def __init__(self, model: str = "whisper-1"):
        self.model = model

    def transcribe(self, audio_path: Path, language: Optional[str] = None) -> List[TranscriptSegment]:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("openai package is not installed. Install it with `pip install openai`.") from exc

        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set; required for the 'openai' transcription provider.")

        client = OpenAI()
        with open(audio_path, "rb") as f:
            kwargs = {"model": self.model, "file": f, "response_format": "verbose_json"}
            if language:
                kwargs["language"] = language
            response = client.audio.transcriptions.create(**kwargs)

        segments = getattr(response, "segments", None) or []
        if segments:
            return [
                TranscriptSegment(start=float(seg["start"]), end=float(seg["end"]), text=str(seg["text"]).strip())
                for seg in segments
                if str(seg.get("text", "")).strip()
            ]
        # Fallback: API returned only flat text, no per-segment timestamps.
        text = getattr(response, "text", "") or ""
        if not text.strip():
            return []
        return [TranscriptSegment(start=0.0, end=0.0, text=text.strip())]


def get_provider(name: str, whisper_model: str, openai_model: str) -> TranscriptionProvider:
    if name == "local_whisper":
        return LocalWhisperProvider(model_size=whisper_model)
    if name == "openai":
        return OpenAITranscriptionProvider(model=openai_model)
    raise ValueError(f"Unknown transcription provider: {name!r}")


# ---------------------------------------------------------------------------
# Audio extraction
# ---------------------------------------------------------------------------

def _resolve_ffmpeg_cmd() -> str:
    """Return the ffmpeg command/path to use.

    FFMPEG_CMD env var always wins (a non-default install location).
    Otherwise prefers PATH; a winget-installed Gyan.FFmpeg build registers
    itself in the *persistent* User PATH but that only takes effect in a
    shell started after the install, so we also look for it directly under
    %LOCALAPPDATA%\\Microsoft\\WinGet\\Packages as a fallback.
    """
    env_override = os.environ.get("FFMPEG_CMD")
    if env_override:
        return env_override

    if shutil.which("ffmpeg"):
        return "ffmpeg"

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        packages_dir = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
        try:
            candidates = sorted(packages_dir.glob("Gyan.FFmpeg*/**/bin/ffmpeg.exe"), reverse=True)
        except OSError:
            candidates = []
        if candidates:
            return str(candidates[0])

    return "ffmpeg"  # nothing found — let subprocess raise its own FileNotFoundError below


def extract_audio(video_path: Path, work_dir: Path) -> Path:
    ffmpeg_cmd = _resolve_ffmpeg_cmd()
    audio_path = work_dir / f"{video_path.stem}.wav"
    try:
        result = subprocess.run(
            [ffmpeg_cmd, "-y", "-i", str(video_path), "-vn", "-ar", "16000", "-ac", "1", str(audio_path)],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "ffmpeg not found. Install it with `winget install --id Gyan.FFmpeg.Essentials -e` "
            "(Windows) or your platform's package manager, or provide a .vtt/.srt sidecar "
            "transcript instead. For a non-default install location, set the FFMPEG_CMD "
            "environment variable to the full path of ffmpeg.exe."
        ) from exc
    if result.returncode != 0 or not audio_path.exists():
        raise RuntimeError(f"ffmpeg audio extraction failed for {video_path.name}: {result.stderr[-2000:]}")
    return audio_path


# ---------------------------------------------------------------------------
# Metadata resolution (manifest / filename / CLI — never invented)
# ---------------------------------------------------------------------------

def _load_manifest(video_path: Path) -> dict:
    manifest_path = video_path.with_suffix(".json")
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.warning(f"Ignoring malformed manifest {manifest_path.name}: {exc}")
    return {}


def _derive_video_id(stem: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", stem).strip("_").upper()
    return slug or "VIDEO"


def _derive_lecture_label(stem: str) -> Optional[str]:
    """Turn 'lecture_05' into 'Lecture 05' — reformatting the filename itself, not inventing content."""
    match = re.match(r"^lecture[_\-\s]?(\d+)$", stem, re.IGNORECASE)
    if match:
        return f"Lecture {match.group(1)}"
    return None


def resolve_metadata(
    video_path: Path,
    cli_course: Optional[str],
    cli_lecture: Optional[str],
    cli_topic: Optional[str],
    cli_video_id: Optional[str],
) -> dict:
    manifest = _load_manifest(video_path)
    stem = video_path.stem
    video_id = cli_video_id or manifest.get("video_id") or _derive_video_id(stem)
    course = cli_course or manifest.get("course")
    lecture = cli_lecture or manifest.get("lecture") or _derive_lecture_label(stem)
    topic = cli_topic or manifest.get("topic")  # never guessed from filename
    language = manifest.get("language", "en")
    return {
        "video_id": video_id,
        "course": course,
        "lecture": lecture,
        "topic": topic,
        "language": language,
    }


# ---------------------------------------------------------------------------
# Core per-file pipeline
# ---------------------------------------------------------------------------

def _light_clean(text: str) -> str:
    """Whitespace-only normalization at ingestion time; artifact removal belongs to clean_content.py."""
    return re.sub(r"\s+", " ", text).strip()


def segments_to_records(
    segments: List[TranscriptSegment],
    video_path: Path,
    meta: dict,
    provider_name: str,
    duration_seconds: Optional[float],
    extra_metadata: Optional[dict] = None,
) -> List[ContentRecord]:
    records = []
    for idx, seg in enumerate(segments, start=1):
        text = _light_clean(seg.text)
        if not text:
            continue
        metadata = {
            "duration_seconds": duration_seconds,
            "transcription_provider": provider_name,
            "language": meta["language"],
        }
        if extra_metadata:
            metadata.update(extra_metadata)
        records.append(
            ContentRecord(
                content_id=f"{meta['video_id']}_SEG_{idx:03d}",
                content_type=ContentType.VIDEO_TRANSCRIPT,
                course=meta["course"],
                topic=meta["topic"],
                source=video_path.name,
                source_id=meta["video_id"],
                lecture=meta["lecture"],
                page=None,
                start_time=seg.start,
                end_time=seg.end,
                text=text,
                processing_status=ProcessingStatus.PROCESSED,
                qa_status=QAStatus.PENDING,
                metadata=metadata,
            )
        )
    return records


def write_human_readable_transcript(records: List[ContentRecord], path: Path) -> None:
    lines = []
    for r in records:
        if r.start_time is not None and r.end_time is not None:
            start = time.strftime("%H:%M:%S", time.gmtime(r.start_time))
            end = time.strftime("%H:%M:%S", time.gmtime(r.end_time))
            lines.append(f"[{start} --> {end}] {r.text}")
        else:
            lines.append(r.text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def process_video(
    video_path: Path,
    output_dir: Path,
    provider_choice: str,
    whisper_model: str,
    openai_model: str,
    cli_course: Optional[str],
    cli_lecture: Optional[str],
    cli_topic: Optional[str],
    cli_video_id: Optional[str],
) -> dict:
    start_time = time.perf_counter()
    meta = resolve_metadata(video_path, cli_course, cli_lecture, cli_topic, cli_video_id)

    vtt_path = video_path.with_suffix(".vtt")
    srt_path = video_path.with_suffix(".srt")
    provider_name: str
    segments: List[TranscriptSegment]

    try:
        if provider_choice == "vtt":
            if not vtt_path.exists():
                raise RuntimeError(f"--provider vtt requested but {vtt_path.name} not found")
            segments = parse_vtt(vtt_path)
            provider_name = "vtt_sidecar"
        elif provider_choice == "srt":
            if not srt_path.exists():
                raise RuntimeError(f"--provider srt requested but {srt_path.name} not found")
            segments = parse_srt(srt_path)
            provider_name = "srt_sidecar"
        elif provider_choice == "auto" and vtt_path.exists():
            segments = parse_vtt(vtt_path)
            provider_name = "vtt_sidecar"
        elif provider_choice == "auto" and srt_path.exists():
            segments = parse_srt(srt_path)
            provider_name = "srt_sidecar"
        else:
            provider_name_choice = provider_choice
            if provider_choice == "auto":
                try:
                    import faster_whisper  # noqa: F401
                    provider_name_choice = "local_whisper"
                except ImportError:
                    if os.environ.get("OPENAI_API_KEY"):
                        provider_name_choice = "openai"
                    else:
                        raise RuntimeError(
                            "No .vtt/.srt sidecar found, faster-whisper is not installed, and "
                            "OPENAI_API_KEY is not set. Add a sidecar transcript, `pip install "
                            "faster-whisper`, or set OPENAI_API_KEY."
                        )
            provider = get_provider(provider_name_choice, whisper_model, openai_model)
            with tempfile.TemporaryDirectory(prefix="saarthi_audio_") as tmp:
                audio_path = extract_audio(video_path, Path(tmp))
                segments = provider.transcribe(audio_path, language=meta["language"])
            provider_name = provider.name

        extra_metadata = {"whisper_model": whisper_model} if provider_name == "local_whisper" else None
        records = segments_to_records(segments, video_path, meta, provider_name, duration_seconds=None, extra_metadata=extra_metadata)
        if not records:
            raise RuntimeError("No transcript segments produced (empty sidecar or silent audio)")

        jsonl_path = output_dir / f"{video_path.stem}.jsonl"
        txt_path = output_dir / f"{video_path.stem}.txt"
        write_jsonl(records, jsonl_path)
        write_human_readable_transcript(records, txt_path)

        duration = time.perf_counter() - start_time
        log_operation(
            file=video_path.name,
            type_="video",
            operation="transcription",
            status="success",
            duration_seconds=round(duration, 3),
            output=str(jsonl_path),
            error=None,
            segments=len(records),
            provider=provider_name,
        )
        logger.info(f"{video_path.name}: {len(records)} segments -> {jsonl_path}")
        return {"status": "success", "segments": len(records), "output": str(jsonl_path)}

    except Exception as exc:  # noqa: BLE001 — deliberately broad: one bad file must not abort the batch
        duration = time.perf_counter() - start_time
        log_operation(
            file=video_path.name,
            type_="video",
            operation="transcription",
            status="failed",
            duration_seconds=round(duration, 3),
            output=None,
            error=str(exc),
        )
        logger.error(f"{video_path.name}: FAILED — {exc}")
        return {"status": "failed", "error": str(exc)}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest lecture videos into canonical transcript JSONL.")
    parser.add_argument("--input", type=Path, default=RAW_VIDEOS_DIR, help="Directory of video files to process.")
    parser.add_argument("--output", type=Path, default=PROCESSED_TRANSCRIPTS_DIR, help="Output directory for JSONL/txt.")
    parser.add_argument("--file", type=str, default=None, help="Process a single file (name or path).")
    parser.add_argument(
        "--provider",
        choices=["auto", "vtt", "srt", "local_whisper", "openai"],
        default="auto",
        help="auto = prefer a .vtt/.srt sidecar, then local_whisper, then openai.",
    )
    parser.add_argument(
        "--whisper-model",
        default=DEFAULT_WHISPER_MODEL,
        help="faster-whisper model size (tiny/base/small/medium/large-v3). Also settable via SAARTHI_WHISPER_MODEL.",
    )
    parser.add_argument("--openai-model", default="whisper-1", help="OpenAI transcription model name.")
    parser.add_argument("--course", default=None)
    parser.add_argument("--lecture", default=None)
    parser.add_argument("--topic", default=None)
    parser.add_argument("--video-id", default=None)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)

    if args.file:
        candidate = Path(args.file)
        video_path = candidate if candidate.is_absolute() or candidate.exists() else args.input / candidate
        video_files = [video_path]
    else:
        if not args.input.exists():
            logger.error(f"Input directory not found: {args.input}")
            return 1
        video_files = sorted(p for p in args.input.iterdir() if p.suffix.lower() in VIDEO_EXTENSIONS)

    if not video_files:
        logger.warning(f"No video files found in {args.input}")
        return 0

    succeeded = 0
    failed = 0
    for video_path in video_files:
        if not video_path.exists():
            logger.error(f"File not found: {video_path}")
            failed += 1
            continue
        result = process_video(
            video_path,
            args.output,
            args.provider,
            args.whisper_model,
            args.openai_model,
            args.course,
            args.lecture,
            args.topic,
            args.video_id,
        )
        if result["status"] == "success":
            succeeded += 1
        else:
            failed += 1

    logger.info(f"Done. {succeeded} succeeded, {failed} failed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
