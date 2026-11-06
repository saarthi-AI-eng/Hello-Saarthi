-- Assignments can refuse work after the due date ("hard deadline"). Existing assignments keep accepting late work.
ALTER TABLE saarthi_assignments ADD COLUMN IF NOT EXISTS hard_deadline BOOLEAN NOT NULL DEFAULT FALSE;
