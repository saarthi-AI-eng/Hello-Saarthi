"""Video transcript segment QA scoring (Part 1.3). Operates on one
ContentRecord (one transcript segment) at a time — never a whole video.

Real signals used, honestly scoped to what each provider actually gives:
- local_whisper (faster-whisper): avg_logprob + no_speech_prob, captured
  by ingest_videos.py's LocalWhisperProvider (see that file). A genuine
  per-segment confidence/uncertainty signal.
- vtt_sidecar / srt_sidecar / openai: NO confidence signal exists at all.
  recognition_confidence falls back to a documented neutral default
  rather than a fabricated number — see _recognition_confidence().
"""
from __future__ import annotations

from typing import Optional

from src.content_qa.checks import (
    DuplicateTracker,
    control_char_ratio,
    is_near_empty,
    longest_repeated_char_run,
    qa_content_hash,
    status_from_score,
    weighted_score,
    word_count,
)
from src.content_qa.config import QAConfig
from src.content_qa.result import QAResult

QA_METHOD = "video_heuristic_v1"


def _recognition_confidence(metadata: dict, issues: list[str]) -> float:
    provider = metadata.get("transcription_provider")
    avg_logprob = metadata.get("avg_logprob")
    no_speech_prob = metadata.get("no_speech_prob")
    if provider != "local_whisper" or avg_logprob is None:
        issues.append("no_confidence_signal_available")
        return 75.0  # neutral default — documented limitation, not a fabricated score
    # avg_logprob is a mean log-probability, typically in roughly [-1.5, 0];
    # closer to 0 = more confident. no_speech_prob near 1 means the model
    # itself doubts this is real speech (a classic hallucination signal on
    # a segment that still produced text).
    base = max(0.0, min(100.0, (float(avg_logprob) + 1.5) / 1.5 * 100.0))
    if no_speech_prob is not None and no_speech_prob > 0.3:
        issues.append(f"high_no_speech_prob:{no_speech_prob:.2f}")
        base -= float(no_speech_prob) * 50.0
    return max(0.0, base)


def _text_completeness(text: str, start: Optional[float], end: Optional[float], config: QAConfig, issues: list[str]) -> float:
    duration = (end - start) if (start is not None and end is not None) else None
    words = word_count(text)
    if is_near_empty(text, config.min_word_count, config.min_char_count):
        # Short is normal for a brief utterance in a short segment ("Yes.") —
        # only suspicious if the segment is long enough that this little
        # text implies missed speech, not a natural pause (Part 1.3: "Do
        # not treat natural pauses or silence as failures").
        if duration is not None and duration > 5.0:
            issues.append("short_text_for_segment_duration")
            return 30.0
        return 85.0
    if duration and duration > 0 and (words / duration) < 0.3:
        issues.append("low_words_per_second")
        return 60.0
    return 100.0


def _longest_repeated_word_run(text: str) -> int:
    words = [w.lower() for w in text.split()]
    longest = run = 1
    for i in range(1, len(words)):
        run = run + 1 if words[i] == words[i - 1] else 1
        longest = max(longest, run)
    return longest if words else 0


def _character_quality(text: str, config: QAConfig, issues: list[str]) -> float:
    score = 100.0
    ratio = control_char_ratio(text)
    if ratio > config.max_control_char_ratio:
        issues.append(f"control_char_ratio:{ratio:.3f}")
        score -= min(60.0, ratio * 400.0)
    if longest_repeated_char_run(text) > config.max_repeated_char_run:
        issues.append("repeated_char_run")
        score -= 30.0
    word_run = _longest_repeated_word_run(text)
    if word_run >= 4:  # e.g. "the the the the" — a known ASR hallucination pattern
        issues.append(f"repeated_word_run:{word_run}")
        score -= 30.0
    return max(0.0, score)


def _structural_integrity(start: Optional[float], end: Optional[float], config: QAConfig, issues: list[str]) -> float:
    duration = end - start
    if duration > config.max_video_segment_seconds:
        issues.append(f"unusually_long_segment:{duration:.1f}s")
        return 50.0
    return 100.0


def score_video_segment(
    record,  # scripts.schemas.ContentRecord
    config: QAConfig,
    dup_tracker: Optional[DuplicateTracker] = None,
) -> QAResult:
    text = record.text or ""
    metadata = record.metadata or {}
    issues: list[str] = []

    if not text.strip():
        return _critical(config, "empty_extraction", text, metadata)
    if not record.source or not record.content_id:
        return _critical(config, "missing_required_metadata", text, metadata)
    if record.start_time is None or record.end_time is None or record.start_time < 0 or record.end_time < record.start_time:
        return _critical(config, "invalid_timestamps", text, metadata)
    ratio = control_char_ratio(text)
    if ratio >= config.max_control_char_ratio_for_rejection:
        return _critical(config, f"severe_character_corruption:{ratio:.2f}", text, metadata)

    checks = {
        "recognition_confidence": _recognition_confidence(metadata, issues),
        "text_completeness": _text_completeness(text, record.start_time, record.end_time, config, issues),
        "character_quality": _character_quality(text, config, issues),
        "structural_integrity": _structural_integrity(record.start_time, record.end_time, config, issues),
        "content_consistency": 100.0,
        "metadata_validity": 100.0,
    }

    language = metadata.get("language")
    if language and language.lower() in ("en",):
        non_ascii_letters = sum(1 for c in text if c.isalpha() and ord(c) > 127)
        total_letters = sum(1 for c in text if c.isalpha())
        if total_letters and (non_ascii_letters / total_letters) > 0.3:
            issues.append("unexpected_script_for_declared_language")
            checks["metadata_validity"] = 70.0

    if dup_tracker is not None and dup_tracker.is_duplicate(record.source_id or record.source, text):
        issues.append("duplicate_content")
        checks["content_consistency"] = config.duplicate_penalty_score

    score = weighted_score(checks, config.weights)
    status = status_from_score(score, config.approved_min, config.pending_min)
    return QAResult(
        status=status,
        score=score,
        qa_version=config.qa_version,
        qa_method=QA_METHOD,
        checks=checks,
        issues=issues,
        content_hash=_content_hash(text, metadata),
    )


def _content_hash(text: str, metadata: dict) -> str:
    return qa_content_hash(
        text,
        (
            ("avg_logprob", metadata.get("avg_logprob")),
            ("no_speech_prob", metadata.get("no_speech_prob")),
            ("transcription_provider", metadata.get("transcription_provider")),
        ),
    )


def _critical(config: QAConfig, reason: str, text: str, metadata: dict) -> QAResult:
    zero = {k: 0.0 for k in config.weights}
    return QAResult(
        status="rejected",
        score=0.0,
        qa_version=config.qa_version,
        qa_method=QA_METHOD,
        checks=zero,
        issues=[f"critical:{reason}"],
        critical_failure=reason,
        content_hash=_content_hash(text, metadata),
    )
