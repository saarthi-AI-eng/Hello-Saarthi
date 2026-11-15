from __future__ import annotations

from src.content_qa.video_qa import score_video_segment
from tests.content_qa.conftest import video_record


def test_high_quality_segment_is_approved(qa_config):
    record = video_record()
    result = score_video_segment(record, qa_config)
    assert result.status == "approved"
    assert result.critical_failure is None


def test_invalid_timestamps_is_rejected(qa_config):
    record = video_record(start_time=5.0, end_time=2.0)
    result = score_video_segment(record, qa_config)
    assert result.status == "rejected"
    assert result.critical_failure == "invalid_timestamps"


def test_empty_text_is_rejected(qa_config):
    record = video_record(text=" ")
    result = score_video_segment(record, qa_config)
    assert result.status == "rejected"
    assert result.critical_failure == "empty_extraction"


def test_short_natural_utterance_in_short_segment_is_not_penalized(qa_config):
    """Part 1.3: do not treat natural brevity/pauses as a failure."""
    record = video_record(text="Yes.", start_time=0.0, end_time=1.0)
    result = score_video_segment(record, qa_config)
    assert result.checks["text_completeness"] >= 80.0


def test_suspiciously_short_text_over_long_segment_is_flagged(qa_config):
    record = video_record(text="Yes.", start_time=0.0, end_time=12.0)
    result = score_video_segment(record, qa_config)
    assert "short_text_for_segment_duration" in result.issues
    assert result.checks["text_completeness"] < 80.0


def test_repeated_word_hallucination_is_flagged(qa_config):
    record = video_record(text="the the the the the the the")
    result = score_video_segment(record, qa_config)
    assert result.checks["character_quality"] < 100.0


def test_high_no_speech_prob_lowers_confidence(qa_config):
    confident = video_record()
    doubtful = video_record(metadata={
        "transcription_provider": "local_whisper",
        "language": "en",
        "avg_logprob": -0.1,
        "no_speech_prob": 0.9,
    })
    r1 = score_video_segment(confident, qa_config)
    r2 = score_video_segment(doubtful, qa_config)
    assert r2.checks["recognition_confidence"] < r1.checks["recognition_confidence"]


def test_sidecar_provider_has_no_fabricated_confidence(qa_config):
    record = video_record(metadata={"transcription_provider": "vtt_sidecar", "language": "en"})
    result = score_video_segment(record, qa_config)
    assert "no_confidence_signal_available" in result.issues


def test_scoring_is_deterministic(qa_config):
    record = video_record()
    r1 = score_video_segment(record, qa_config)
    r2 = score_video_segment(record, qa_config)
    assert r1.score == r2.score
    assert r1.content_hash == r2.content_hash
