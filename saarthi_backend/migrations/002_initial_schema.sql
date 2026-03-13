-- Full schema for Saarthi backend. All tables with IF NOT EXISTS.
-- Order respects foreign keys.

-- Users and auth
CREATE TABLE IF NOT EXISTS saarthi_users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'student',
    institute VARCHAR(255),
    bio TEXT,
    avatar_url VARCHAR(512),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_users_email ON saarthi_users (email);

CREATE TABLE IF NOT EXISTS saarthi_refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_refresh_tokens_user_id ON saarthi_refresh_tokens (user_id);
CREATE INDEX IF NOT EXISTS ix_saarthi_refresh_tokens_token_hash ON saarthi_refresh_tokens (token_hash);

-- Conversation context (chat)
CREATE TABLE IF NOT EXISTS saarthi_conversation_context (
    conversation_id VARCHAR(36) PRIMARY KEY,
    summary TEXT,
    metadata JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Courses
CREATE TABLE IF NOT EXISTS saarthi_courses (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    code VARCHAR(50) NOT NULL,
    instructor VARCHAR(255) NOT NULL,
    description TEXT,
    thumbnail_emoji VARCHAR(16),
    color VARCHAR(32),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_courses_code ON saarthi_courses (code);

CREATE TABLE IF NOT EXISTS saarthi_enrollments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES saarthi_users(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES saarthi_courses(id) ON DELETE CASCADE,
    progress_percent DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    last_accessed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_enrollments_user_id ON saarthi_enrollments (user_id);
CREATE INDEX IF NOT EXISTS ix_saarthi_enrollments_course_id ON saarthi_enrollments (course_id);

CREATE TABLE IF NOT EXISTS saarthi_assignments (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES saarthi_courses(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    due_date VARCHAR(32) NOT NULL,
    points INTEGER NOT NULL DEFAULT 100,
    topic VARCHAR(128),
    attachments TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_assignments_course_id ON saarthi_assignments (course_id);

CREATE TABLE IF NOT EXISTS saarthi_assignment_submissions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES saarthi_users(id) ON DELETE CASCADE,
    assignment_id INTEGER NOT NULL REFERENCES saarthi_assignments(id) ON DELETE CASCADE,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    submitted_at TIMESTAMPTZ,
    grade DOUBLE PRECISION,
    attachment_url VARCHAR(512),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_assignment_submissions_user_id ON saarthi_assignment_submissions (user_id);
CREATE INDEX IF NOT EXISTS ix_saarthi_assignment_submissions_assignment_id ON saarthi_assignment_submissions (assignment_id);

CREATE TABLE IF NOT EXISTS saarthi_materials (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES saarthi_courses(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    type VARCHAR(32) NOT NULL,
    url VARCHAR(512) NOT NULL,
    topic VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_materials_course_id ON saarthi_materials (course_id);

CREATE TABLE IF NOT EXISTS saarthi_stream_items (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES saarthi_courses(id) ON DELETE CASCADE,
    type VARCHAR(32) NOT NULL DEFAULT 'announcement',
    title VARCHAR(255),
    description TEXT NOT NULL,
    author VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_stream_items_course_id ON saarthi_stream_items (course_id);

-- Videos
CREATE TABLE IF NOT EXISTS saarthi_videos (
    id SERIAL PRIMARY KEY,
    course_id INTEGER REFERENCES saarthi_courses(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    thumbnail_url VARCHAR(512),
    url VARCHAR(512) NOT NULL,
    embed_url VARCHAR(512),
    chapters_json TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_videos_course_id ON saarthi_videos (course_id);

CREATE TABLE IF NOT EXISTS saarthi_video_progress (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES saarthi_users(id) ON DELETE CASCADE,
    video_id INTEGER NOT NULL REFERENCES saarthi_videos(id) ON DELETE CASCADE,
    position_seconds INTEGER NOT NULL DEFAULT 0,
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_video_progress_user_id ON saarthi_video_progress (user_id);
CREATE INDEX IF NOT EXISTS ix_saarthi_video_progress_video_id ON saarthi_video_progress (video_id);

CREATE TABLE IF NOT EXISTS saarthi_video_notes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES saarthi_users(id) ON DELETE CASCADE,
    video_id INTEGER NOT NULL REFERENCES saarthi_videos(id) ON DELETE CASCADE,
    time_seconds INTEGER NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_video_notes_user_id ON saarthi_video_notes (user_id);
CREATE INDEX IF NOT EXISTS ix_saarthi_video_notes_video_id ON saarthi_video_notes (video_id);

-- Quizzes
CREATE TABLE IF NOT EXISTS saarthi_quizzes (
    id SERIAL PRIMARY KEY,
    course_id INTEGER REFERENCES saarthi_courses(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    duration_minutes INTEGER NOT NULL DEFAULT 15,
    passing_score DOUBLE PRECISION NOT NULL DEFAULT 60.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_quizzes_course_id ON saarthi_quizzes (course_id);

CREATE TABLE IF NOT EXISTS saarthi_quiz_questions (
    id SERIAL PRIMARY KEY,
    quiz_id INTEGER NOT NULL REFERENCES saarthi_quizzes(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    options_json TEXT NOT NULL,
    correct_index INTEGER NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_quiz_questions_quiz_id ON saarthi_quiz_questions (quiz_id);

CREATE TABLE IF NOT EXISTS saarthi_quiz_attempts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES saarthi_users(id) ON DELETE CASCADE,
    quiz_id INTEGER NOT NULL REFERENCES saarthi_quizzes(id) ON DELETE CASCADE,
    score DOUBLE PRECISION,
    answers_json TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_saarthi_quiz_attempts_user_id ON saarthi_quiz_attempts (user_id);
CREATE INDEX IF NOT EXISTS ix_saarthi_quiz_attempts_quiz_id ON saarthi_quiz_attempts (quiz_id);

-- Notes
CREATE TABLE IF NOT EXISTS saarthi_notes (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES saarthi_users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    course_id INTEGER REFERENCES saarthi_courses(id) ON DELETE SET NULL,
    topic VARCHAR(128),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_notes_user_id ON saarthi_notes (user_id);
CREATE INDEX IF NOT EXISTS ix_saarthi_notes_course_id ON saarthi_notes (course_id);

-- Notifications
CREATE TABLE IF NOT EXISTS saarthi_notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES saarthi_users(id) ON DELETE CASCADE,
    type VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    link VARCHAR(512),
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_notifications_user_id ON saarthi_notifications (user_id);
