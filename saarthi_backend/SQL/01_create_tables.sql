-- PostgreSQL: reference migration (tables created by SQLAlchemy create_all in main.py)

-- Conversation context
CREATE TABLE IF NOT EXISTS saarthi_conversation_context (
    conversation_id VARCHAR(36) PRIMARY KEY,
    summary TEXT,
    metadata JSONB,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Users (auth)
CREATE TABLE IF NOT EXISTS saarthi_users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'student',
    institute VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_saarthi_users_email ON saarthi_users(email);

-- Refresh tokens
CREATE TABLE IF NOT EXISTS saarthi_refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_saarthi_refresh_tokens_user_id ON saarthi_refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS ix_saarthi_refresh_tokens_token_hash ON saarthi_refresh_tokens(token_hash);
