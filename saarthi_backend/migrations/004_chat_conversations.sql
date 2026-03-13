-- Tutor chat: conversations and messages per user
CREATE TABLE IF NOT EXISTS saarthi_conversations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES saarthi_users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL DEFAULT 'New Chat',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_conversations_user_id ON saarthi_conversations (user_id);
CREATE INDEX IF NOT EXISTS ix_saarthi_conversations_updated_at ON saarthi_conversations (updated_at DESC);

CREATE TABLE IF NOT EXISTS saarthi_chat_messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES saarthi_conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_chat_messages_conversation_id ON saarthi_chat_messages (conversation_id);
