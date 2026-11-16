-- MCQ practice: question topic, difficulty and explanation; quiz topic (Classwork module).
ALTER TABLE saarthi_quizzes ADD COLUMN IF NOT EXISTS topic VARCHAR(128);
ALTER TABLE saarthi_quiz_questions ADD COLUMN IF NOT EXISTS topic VARCHAR(128);
ALTER TABLE saarthi_quiz_questions ADD COLUMN IF NOT EXISTS difficulty VARCHAR(20) NOT NULL DEFAULT 'recall';
ALTER TABLE saarthi_quiz_questions ADD COLUMN IF NOT EXISTS explanation TEXT;

-- Course modules (Classwork topics) and the topic of a video.
CREATE TABLE IF NOT EXISTS saarthi_course_modules (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES saarthi_courses(id) ON DELETE CASCADE,
    title VARCHAR(128) NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_course_modules_course_id ON saarthi_course_modules (course_id);
ALTER TABLE saarthi_videos ADD COLUMN IF NOT EXISTS topic VARCHAR(128);

-- Bookmarks.
CREATE TABLE IF NOT EXISTS saarthi_bookmarks (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES saarthi_users(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES saarthi_courses(id) ON DELETE CASCADE,
    item_type VARCHAR(32) NOT NULL,
    item_id VARCHAR(64) NOT NULL,
    title VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (user_id, item_type, item_id)
);
CREATE INDEX IF NOT EXISTS ix_saarthi_bookmarks_user_id ON saarthi_bookmarks (user_id);

-- Code Lab: test cases and submissions.
ALTER TABLE saarthi_code_problems ADD COLUMN IF NOT EXISTS test_cases_json TEXT;
CREATE TABLE IF NOT EXISTS saarthi_code_submissions (
    id SERIAL PRIMARY KEY,
    problem_id INTEGER NOT NULL REFERENCES saarthi_code_problems(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES saarthi_users(id) ON DELETE CASCADE,
    language VARCHAR(32) NOT NULL,
    code TEXT NOT NULL,
    passed INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_code_submissions_problem_id ON saarthi_code_submissions (problem_id);
