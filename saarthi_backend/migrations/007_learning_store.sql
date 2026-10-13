CREATE TABLE IF NOT EXISTS saarthi_flashcards (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES saarthi_users(id) ON DELETE CASCADE,
    topic VARCHAR(255) NOT NULL,
    front TEXT NOT NULL,
    back TEXT NOT NULL,
    difficulty VARCHAR(16) NOT NULL DEFAULT 'medium',
    interval INTEGER NOT NULL DEFAULT 1,
    ease_factor DOUBLE PRECISION NOT NULL DEFAULT 2.5,
    next_review_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_flashcards_user_next
    ON saarthi_flashcards (user_id, next_review_at);

CREATE TABLE IF NOT EXISTS saarthi_topic_mastery (
    user_id INTEGER NOT NULL REFERENCES saarthi_users(id) ON DELETE CASCADE,
    topic VARCHAR(255) NOT NULL,
    score DOUBLE PRECISION NOT NULL DEFAULT 0.5,
    source VARCHAR(32) NOT NULL DEFAULT 'quiz',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, topic)
);

CREATE TABLE IF NOT EXISTS saarthi_turn_artifacts (
    message_id INTEGER PRIMARY KEY REFERENCES saarthi_chat_messages(id) ON DELETE CASCADE,
    conversation_id INTEGER NOT NULL REFERENCES saarthi_conversations(id) ON DELETE CASCADE,
    citations JSONB,
    plan JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
