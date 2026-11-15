-- Manual QA review audit log (model: QAReviewAction). Audit trail only —
-- the actual qa_status the KB pipeline's normalizer reads lives in the
-- ContentRecord JSONL files, applied by src/content_qa/manual_review.py.
CREATE TABLE IF NOT EXISTS saarthi_qa_review_actions (
    id SERIAL PRIMARY KEY,
    content_id VARCHAR(255) NOT NULL,
    source_file VARCHAR(512) NOT NULL,
    reviewer_id INTEGER REFERENCES saarthi_users(id) ON DELETE SET NULL,
    decision VARCHAR(32) NOT NULL,
    previous_status VARCHAR(32) NOT NULL,
    new_status VARCHAR(32) NOT NULL,
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_qa_review_actions_content_id ON saarthi_qa_review_actions (content_id);
CREATE INDEX IF NOT EXISTS ix_saarthi_qa_review_actions_reviewer_id ON saarthi_qa_review_actions (reviewer_id);
