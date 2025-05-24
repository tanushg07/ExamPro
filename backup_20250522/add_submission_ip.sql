-- Add submission_ip column to exam_attempts table
ALTER TABLE exam_attempts
ADD COLUMN submission_ip VARCHAR(45) NULL DEFAULT NULL;
