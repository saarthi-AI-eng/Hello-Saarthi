"""Constants: intent names, expert names, defaults."""

# Intents (orchestrator sends these)
INTENT_THEORY = "THEORY"
INTENT_PROBLEM_SOLVING = "PROBLEM_SOLVING"
INTENT_VIDEO_REFERENCE = "VIDEO_REFERENCE"
INTENT_CODE_REQUEST = "CODE_REQUEST"
INTENT_DIAGRAM_EXPLAIN = "DIAGRAM_EXPLAIN"
INTENT_EXAM_PREP = "EXAM_PREP"
INTENT_FOLLOWUP = "FOLLOWUP"

VALID_INTENTS = {
    INTENT_THEORY,
    INTENT_PROBLEM_SOLVING,
    INTENT_VIDEO_REFERENCE,
    INTENT_CODE_REQUEST,
    INTENT_DIAGRAM_EXPLAIN,
    INTENT_EXAM_PREP,
    INTENT_FOLLOWUP,
}

# Expert names (we return expert_used as lowercase with underscore)
EXPERT_THEORY = "theory"
EXPERT_PROBLEM_SOLVING = "problem_solving"
EXPERT_VIDEO = "video"
EXPERT_CODE = "code"
EXPERT_MULTIMODAL = "multimodal"
EXPERT_EXAM_PREP = "exam_prep"
EXPERT_FOLLOWUP = "followup"

# AI guy agent names -> our expert_used
AGENT_TO_EXPERT = {
    "notes_agent": EXPERT_THEORY,
    "books_agent": EXPERT_THEORY,
    "video_agent": EXPERT_VIDEO,
    "calculator_agent": EXPERT_CODE,
    "saarthi_agent": EXPERT_THEORY,
}

# Retrieval
DEFAULT_TOP_K = 5
DEFAULT_INCLUDE_SCORES = True
CONTENT_TYPES = {"notes", "video", "code", "exercises"}

# Context
SUMMARY_MAX_LENGTH = 2000
METADATA_MAX_KEYS = 50
