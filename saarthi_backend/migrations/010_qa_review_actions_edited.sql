-- Adds the "edited" column (model: QAReviewAction) — tracks whether the
-- reviewer changed the extracted text as part of their decision.
ALTER TABLE saarthi_qa_review_actions ADD COLUMN IF NOT EXISTS edited BOOLEAN NOT NULL DEFAULT FALSE;
