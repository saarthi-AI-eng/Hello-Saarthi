-- Teacher study guides (missing from 002; ORM already expects these tables)

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
