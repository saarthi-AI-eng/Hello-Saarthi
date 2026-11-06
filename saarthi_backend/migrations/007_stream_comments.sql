-- Comments on classroom stream items.

CREATE TABLE IF NOT EXISTS saarthi_stream_comments (
    id SERIAL PRIMARY KEY,
    stream_item_id INTEGER NOT NULL REFERENCES saarthi_stream_items(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES saarthi_users(id) ON DELETE CASCADE,
    author VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_stream_comments_stream_item_id ON saarthi_stream_comments (stream_item_id);
CREATE INDEX IF NOT EXISTS ix_saarthi_stream_comments_user_id ON saarthi_stream_comments (user_id);
