-- Add foreign key from saarthi_refresh_tokens.user_id to saarthi_users.id
-- (referential integrity and cascade delete on user removal)

ALTER TABLE saarthi_refresh_tokens
ADD CONSTRAINT fk_saarthi_refresh_tokens_user_id
FOREIGN KEY (user_id) REFERENCES saarthi_users(id) ON DELETE CASCADE;