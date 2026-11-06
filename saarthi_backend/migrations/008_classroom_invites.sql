-- Classroom invites / class codes (model: ClassroomInvite). This table had an ORM
-- model but no migration, so POST /api/courses/join failed with
-- 'relation "saarthi_classroom_invites" does not exist'.
CREATE TABLE IF NOT EXISTS saarthi_classroom_invites (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES saarthi_courses(id) ON DELETE CASCADE,
    invited_by INTEGER NOT NULL REFERENCES saarthi_users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    invite_code VARCHAR(64) NOT NULL UNIQUE,
    accepted BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_saarthi_classroom_invites_course_id ON saarthi_classroom_invites (course_id);
CREATE INDEX IF NOT EXISTS ix_saarthi_classroom_invites_invited_by ON saarthi_classroom_invites (invited_by);
CREATE INDEX IF NOT EXISTS ix_saarthi_classroom_invites_email ON saarthi_classroom_invites (email);
CREATE INDEX IF NOT EXISTS ix_saarthi_classroom_invites_invite_code ON saarthi_classroom_invites (invite_code);
