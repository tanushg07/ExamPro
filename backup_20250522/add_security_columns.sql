ALTER TABLE exam_attempts
ADD COLUMN submitted_at TIMESTAMP NULL DEFAULT NULL,
ADD COLUMN submission_location VARCHAR(100) NULL,
ADD COLUMN time_zone VARCHAR(50) NULL,
ADD COLUMN is_fullscreen BOOLEAN DEFAULT FALSE,
ADD COLUMN secure_browser_active BOOLEAN DEFAULT FALSE,
ADD COLUMN webcam_active BOOLEAN DEFAULT FALSE,
ADD COLUMN screen_share_active BOOLEAN DEFAULT FALSE,
ADD COLUMN security_events JSON NULL,
ADD COLUMN browser_events JSON NULL,
ADD COLUMN warning_events JSON NULL,
ADD COLUMN verification_status ENUM('pending', 'approved', 'flagged', 'auto_flagged') DEFAULT 'pending',
ADD COLUMN server_side_checks JSON NULL,
ADD COLUMN answer_version INT NOT NULL DEFAULT 1,
ADD COLUMN last_sync_time TIMESTAMP NULL DEFAULT NULL,
ADD COLUMN client_timestamp TIMESTAMP NULL DEFAULT NULL;

-- Add indexes for performance
CREATE INDEX idx_exam_time ON exam_attempts(exam_id, started_at);
CREATE INDEX idx_student_grading ON exam_attempts(student_id, is_graded);
CREATE INDEX idx_verification ON exam_attempts(verification_status);
CREATE INDEX idx_security ON exam_attempts(warning_count);

-- Add unique constraint for version control
ALTER TABLE exam_attempts
ADD CONSTRAINT uq_attempt_version UNIQUE (exam_id, student_id, answer_version);
