"""VTT/SRT parsing and timestamp preservation (Phase 16 items 2, 4)."""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ingest_videos import (
    TranscriptSegment,
    _derive_lecture_label,
    _derive_video_id,
    _resolve_ffmpeg_cmd,
    _timestamp_to_seconds,
    parse_srt,
    parse_vtt,
    resolve_metadata,
    segments_to_records,
)

VTT_SAMPLE = """WEBVTT

00:00:00.000 --> 00:00:04.500
Welcome to lecture five on the Fourier Transform.

00:12:32.100 --> 00:13:21.400
<v Speaker>This is the sampling theorem.</v>

00:13:21.400 --> 00:13:25.000

"""

SRT_SAMPLE = """1
00:00:00,000 --> 00:00:04,500
Welcome to lecture five.

2
00:12:32,100 --> 00:13:21,400
This is the sampling theorem.
"""


def test_timestamp_to_seconds_hhmmss():
    assert _timestamp_to_seconds("00:12:32.100") == pytest.approx(752.1)


def test_timestamp_to_seconds_mmss():
    assert _timestamp_to_seconds("02:04.500") == pytest.approx(124.5)


def test_timestamp_to_seconds_srt_comma():
    assert _timestamp_to_seconds("00:13:21,400") == pytest.approx(801.4)


def test_parse_vtt_preserves_timestamps_and_strips_tags(tmp_path):
    vtt_path = tmp_path / "lecture_05.vtt"
    vtt_path.write_text(VTT_SAMPLE, encoding="utf-8")

    segments = parse_vtt(vtt_path)

    assert len(segments) == 2  # empty cue is skipped
    assert segments[0] == TranscriptSegment(start=0.0, end=4.5, text="Welcome to lecture five on the Fourier Transform.")
    assert segments[1].start == pytest.approx(752.1)
    assert segments[1].end == pytest.approx(801.4)
    assert "<v" not in segments[1].text
    assert segments[1].text == "This is the sampling theorem."


def test_parse_srt_preserves_timestamps(tmp_path):
    srt_path = tmp_path / "lecture_05.srt"
    srt_path.write_text(SRT_SAMPLE, encoding="utf-8")

    segments = parse_srt(srt_path)

    assert len(segments) == 2
    assert segments[0].text == "Welcome to lecture five."
    assert segments[1].start == pytest.approx(752.1)
    assert segments[1].end == pytest.approx(801.4)


def test_derive_video_id_from_filename():
    assert _derive_video_id("lecture 05!!") == "LECTURE_05"


def test_derive_lecture_label_from_filename():
    assert _derive_lecture_label("lecture_05") == "Lecture 05"
    assert _derive_lecture_label("random_file") is None


def test_resolve_metadata_never_invents_topic(tmp_path):
    video_path = tmp_path / "lecture_05.mp4"
    video_path.write_text("", encoding="utf-8")

    meta = resolve_metadata(video_path, cli_course=None, cli_lecture=None, cli_topic=None, cli_video_id=None)

    assert meta["topic"] is None  # never guessed from filename
    assert meta["course"] is None
    assert meta["lecture"] == "Lecture 05"  # filename reformatting is explicitly allowed
    assert meta["video_id"] == "LECTURE_05"


def test_resolve_metadata_reads_manifest_sidecar(tmp_path):
    video_path = tmp_path / "lecture_05.mp4"
    video_path.write_text("", encoding="utf-8")
    (tmp_path / "lecture_05.json").write_text(
        '{"course": "Signals and Systems", "topic": "Sampling", "video_id": "VID_042"}', encoding="utf-8"
    )

    meta = resolve_metadata(video_path, cli_course=None, cli_lecture=None, cli_topic=None, cli_video_id=None)

    assert meta["course"] == "Signals and Systems"
    assert meta["topic"] == "Sampling"
    assert meta["video_id"] == "VID_042"


def test_cli_args_override_manifest(tmp_path):
    video_path = tmp_path / "lecture_05.mp4"
    video_path.write_text("", encoding="utf-8")
    (tmp_path / "lecture_05.json").write_text('{"course": "Manifest Course"}', encoding="utf-8")

    meta = resolve_metadata(video_path, cli_course="CLI Course", cli_lecture=None, cli_topic=None, cli_video_id=None)

    assert meta["course"] == "CLI Course"


def test_segments_to_records_preserves_timestamps_and_ids(tmp_path):
    video_path = tmp_path / "lecture_05.mp4"
    segments = [
        TranscriptSegment(start=0.0, end=4.5, text="  hello   world  "),
        TranscriptSegment(start=752.4, end=801.8, text="the sampling theorem"),
    ]
    meta = {"video_id": "VID_001", "course": "Signals and Systems", "lecture": "Lecture 05", "topic": None, "language": "en"}

    records = segments_to_records(segments, video_path, meta, provider_name="vtt_sidecar", duration_seconds=None)

    assert [r.content_id for r in records] == ["VID_001_SEG_001", "VID_001_SEG_002"]
    assert records[0].text == "hello world"  # light whitespace clean only
    assert records[1].start_time == pytest.approx(752.4)
    assert records[1].end_time == pytest.approx(801.8)
    assert records[0].topic is None  # not hallucinated
    assert records[0].metadata["transcription_provider"] == "vtt_sidecar"


def test_segments_to_records_merges_extra_metadata(tmp_path):
    video_path = tmp_path / "lecture_05.mp4"
    segments = [TranscriptSegment(start=0.0, end=4.5, text="hello world")]
    meta = {"video_id": "VID_001", "course": None, "lecture": None, "topic": None, "language": "en"}

    records = segments_to_records(
        segments, video_path, meta, provider_name="local_whisper", duration_seconds=None,
        extra_metadata={"whisper_model": "base"},
    )

    assert records[0].metadata["whisper_model"] == "base"
    assert records[0].metadata["transcription_provider"] == "local_whisper"  # base fields untouched


# --- ffmpeg auto-detection (mirrors the Tesseract fix in ingest_notes.py) ----

def test_resolve_ffmpeg_cmd_env_var_always_wins(monkeypatch):
    monkeypatch.setenv("FFMPEG_CMD", r"D:\custom\ffmpeg.exe")
    assert _resolve_ffmpeg_cmd() == r"D:\custom\ffmpeg.exe"


def test_resolve_ffmpeg_cmd_prefers_working_path(monkeypatch):
    monkeypatch.delenv("FFMPEG_CMD", raising=False)
    monkeypatch.setattr("shutil.which", lambda cmd: r"C:\somewhere\ffmpeg.exe")
    assert _resolve_ffmpeg_cmd() == "ffmpeg"  # PATH already resolves it — use the bare command


def test_resolve_ffmpeg_cmd_falls_back_to_winget_package_dir(monkeypatch, tmp_path):
    monkeypatch.delenv("FFMPEG_CMD", raising=False)
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    winget_bin = tmp_path / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg.Essentials_x" / "ffmpeg-9.0.1" / "bin"
    winget_bin.mkdir(parents=True)
    fake_ffmpeg = winget_bin / "ffmpeg.exe"
    fake_ffmpeg.write_bytes(b"")

    assert _resolve_ffmpeg_cmd() == str(fake_ffmpeg)


def test_resolve_ffmpeg_cmd_falls_back_to_bare_command_when_nothing_found(monkeypatch, tmp_path):
    monkeypatch.delenv("FFMPEG_CMD", raising=False)
    monkeypatch.setattr("shutil.which", lambda cmd: None)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))  # empty dir, no WinGet packages

    assert _resolve_ffmpeg_cmd() == "ffmpeg"


# --- provider priority: no API key, no sidecar -> local faster-whisper ------

def test_process_video_auto_uses_local_whisper_without_openai_key(tmp_path, monkeypatch):
    """No .vtt/.srt sidecar, OPENAI_API_KEY unset — must transcribe locally via
    faster-whisper, never require an API key. faster_whisper itself is mocked
    (no real model download/inference in a unit test); extract_audio is mocked
    too so this doesn't need a real ffmpeg or a real video file."""
    import scripts.ingest_videos as ingest_videos

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    video_path = tmp_path / "DTFT_ Periodicity property.mp4"
    video_path.write_bytes(b"")

    monkeypatch.setattr(ingest_videos, "extract_audio", lambda video_path, work_dir: tmp_path / "audio.wav")
    monkeypatch.setattr(
        ingest_videos.LocalWhisperProvider,
        "transcribe",
        lambda self, audio_path, language=None: [
            TranscriptSegment(start=0.0, end=3.2, text="The DTFT is periodic in omega."),
            TranscriptSegment(start=3.2, end=7.5, text="This follows from the periodicity property."),
        ],
    )

    output_dir = tmp_path / "out"
    result = ingest_videos.process_video(
        video_path, output_dir, provider_choice="auto", whisper_model="base", openai_model="whisper-1",
        cli_course="DSP-V", cli_lecture=None, cli_topic=None, cli_video_id=None,
    )

    assert result["status"] == "success"
    assert result["segments"] == 2

    jsonl_path = output_dir / "DTFT_ Periodicity property.jsonl"
    records = list(jsonl_path.read_text(encoding="utf-8").splitlines())
    assert len(records) == 2
    import json as _json
    first = _json.loads(records[0])
    assert first["course"] == "DSP-V"
    assert first["metadata"]["transcription_provider"] == "local_whisper"
    assert first["metadata"]["whisper_model"] == "base"
    assert first["start_time"] == 0.0
    assert first["end_time"] == 3.2


def test_process_video_clear_error_when_no_sidecar_no_whisper_no_key(tmp_path, monkeypatch):
    """If faster-whisper genuinely can't be imported and no key/sidecar exists,
    the failure must be clear, not silent."""
    import builtins

    import scripts.ingest_videos as ingest_videos

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    real_import = builtins.__import__

    def _blocked_import(name, *args, **kwargs):
        if name == "faster_whisper":
            raise ImportError("simulated: not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)

    video_path = tmp_path / "lecture_05.mp4"
    video_path.write_bytes(b"")
    output_dir = tmp_path / "out"

    result = ingest_videos.process_video(
        video_path, output_dir, provider_choice="auto", whisper_model="base", openai_model="whisper-1",
        cli_course=None, cli_lecture=None, cli_topic=None, cli_video_id=None,
    )

    assert result["status"] == "failed"
    assert "faster-whisper is not installed" in result["error"]
    assert "OPENAI_API_KEY is not set" in result["error"]
