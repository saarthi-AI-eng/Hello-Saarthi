-- Bring the DB in line with the ORM models: courses.owner_id plus study guides and classroom invites.

ALTER TABLE saarthi_courses ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES saarthi_users(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS ix_saarthi_courses_owner_id ON saarthi_courses (owner_id);

CREATE TABLE IF NOT EXISTS saarthi_study_guides (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    created_by INTEGER REFERENCES saarthi_users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS saarthi_study_guide_prompts (
    id SERIAL PRIMARY KEY,
    guide_id INTEGER NOT NULL REFERENCES saarthi_study_guides(id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL DEFAULT 1,
    title VARCHAR(255) NOT NULL,
    prompt_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_study_guide_prompts_guide_id ON saarthi_study_guide_prompts (guide_id);

CREATE TABLE IF NOT EXISTS saarthi_classroom_invites (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES saarthi_courses(id) ON DELETE CASCADE,
    invited_by INTEGER NOT NULL REFERENCES saarthi_users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    invite_code VARCHAR(64) NOT NULL UNIQUE,
    accepted BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_classroom_invites_course_id ON saarthi_classroom_invites (course_id);
CREATE INDEX IF NOT EXISTS ix_saarthi_classroom_invites_invited_by ON saarthi_classroom_invites (invited_by);
CREATE INDEX IF NOT EXISTS ix_saarthi_classroom_invites_email ON saarthi_classroom_invites (email);
