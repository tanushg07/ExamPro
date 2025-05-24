-- File: exam_platform_v2.sql
-- Description: Database schema and sample data for the Exam Platform application
-- Compatible with MySQL 8.0+

-- Create database if it doesn't exist
CREATE DATABASE IF NOT EXISTS exam_platform
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

USE exam_platform;

-- Enable strict mode and other important settings
SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION';

-- Drop tables if they exist (in correct order to handle foreign key constraints)
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS security_events;
DROP TABLE IF EXISTS exam_reviews;
DROP TABLE IF EXISTS answers;
DROP TABLE IF EXISTS question_options;
DROP TABLE IF EXISTS questions;
DROP TABLE IF EXISTS exam_attempts;
DROP TABLE IF EXISTS exams;
DROP TABLE IF EXISTS users;

-- Create tables with proper indexes and constraints
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) NOT NULL,
    email VARCHAR(120) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    user_type ENUM('admin', 'teacher', 'student') NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_username (username),
    UNIQUE KEY uk_email (email),
    INDEX idx_user_type (user_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE exams (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    time_limit_minutes INT NOT NULL,
    creator_id INT NOT NULL,
    is_published BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Access Control
    access_code VARCHAR(10),
    allowed_ip_range VARCHAR(100),
    available_from TIMESTAMP NULL,
    available_until TIMESTAMP NULL,
    max_attempts INT DEFAULT 1,
    join_before_minutes INT DEFAULT 15,
    
    -- Security Settings
    require_lockdown BOOLEAN DEFAULT TRUE,
    allow_calculator BOOLEAN DEFAULT FALSE,
    allow_scratch_pad BOOLEAN DEFAULT TRUE,
    randomize_questions BOOLEAN DEFAULT TRUE,
    one_question_at_time BOOLEAN DEFAULT FALSE,
    prevent_copy_paste BOOLEAN DEFAULT TRUE,
    require_webcam BOOLEAN DEFAULT FALSE,
    allow_backward_navigation BOOLEAN DEFAULT TRUE,
    show_remaining_time BOOLEAN DEFAULT TRUE,
    auto_submit BOOLEAN DEFAULT TRUE,
    require_face_verification BOOLEAN DEFAULT FALSE,
    proctor_monitoring BOOLEAN DEFAULT FALSE,
    monitor_screen_share BOOLEAN DEFAULT FALSE,
    periodic_checks BOOLEAN DEFAULT TRUE,
    detect_browser_exit BOOLEAN DEFAULT TRUE,
    max_warnings INT DEFAULT 3,
    block_virtual_machines BOOLEAN DEFAULT TRUE,
    browser_fullscreen BOOLEAN DEFAULT TRUE,
    restrict_keyboard BOOLEAN DEFAULT FALSE,
    block_external_displays BOOLEAN DEFAULT TRUE,
    
    -- Proctoring Settings
    proctor_instructions TEXT,
    proctor_notes TEXT,
    max_students_per_proctor INT DEFAULT 20,
    proctor_join_before INT DEFAULT 30,
    
    FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE RESTRICT,
    INDEX idx_creator_published (creator_id, is_published),
    INDEX idx_access_time (available_from, available_until),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    exam_id INT NOT NULL,
    question_text TEXT NOT NULL,
    question_type ENUM('mcq', 'code', 'text') NOT NULL,
    points INT NOT NULL DEFAULT 1,
    `order` INT NOT NULL DEFAULT 0,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    INDEX idx_exam_order (exam_id, `order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE question_options (
    id INT AUTO_INCREMENT PRIMARY KEY,
    question_id INT NOT NULL,
    option_text TEXT NOT NULL,
    is_correct BOOLEAN DEFAULT FALSE,
    `order` INT NOT NULL DEFAULT 0,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
    INDEX idx_question_order (question_id, `order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE exam_attempts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    exam_id INT NOT NULL,
    student_id INT NOT NULL,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    is_completed BOOLEAN DEFAULT FALSE,
    is_graded BOOLEAN DEFAULT FALSE,
    score DECIMAL(5,2) NULL,
    
    -- Security Monitoring
    browser_fingerprint VARCHAR(255),
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    screen_resolution VARCHAR(20),
    window_switches INT DEFAULT 0,
    focus_losses INT DEFAULT 0,
    warning_count INT DEFAULT 0,
    last_check_time TIMESTAMP NULL,
    environment_verified BOOLEAN DEFAULT FALSE,
    
    -- Browser State
    is_fullscreen BOOLEAN DEFAULT FALSE,
    secure_browser_active BOOLEAN DEFAULT FALSE,
    webcam_active BOOLEAN DEFAULT FALSE,
    screen_share_active BOOLEAN DEFAULT FALSE,
    
    -- Event Logs (JSON)
    security_events JSON NULL,
    browser_events JSON NULL,
    warning_events JSON NULL,
    verification_status ENUM('pending', 'approved', 'flagged') DEFAULT 'pending',
    
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE RESTRICT,
    INDEX idx_exam_student (exam_id, student_id),
    INDEX idx_student_completed (student_id, is_completed),
    INDEX idx_verification (verification_status),
    INDEX idx_grading_status (is_completed, is_graded)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE answers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    attempt_id INT NOT NULL,
    question_id INT NOT NULL,
    selected_option_id INT NULL,
    text_answer TEXT NULL,
    is_correct BOOLEAN NULL,
    teacher_feedback TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (attempt_id) REFERENCES exam_attempts(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE RESTRICT,
    FOREIGN KEY (selected_option_id) REFERENCES question_options(id) ON DELETE SET NULL,
    INDEX idx_attempt_question (attempt_id, question_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE exam_reviews (
    id INT AUTO_INCREMENT PRIMARY KEY,
    exam_id INT NOT NULL,
    student_id INT NOT NULL,
    rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    feedback TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_exam_student (exam_id, student_id),
    INDEX idx_rating (rating)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    message VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,
    related_id INT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_read (user_id, is_read),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE security_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    attempt_id INT NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    event_data JSON NULL,
    severity ENUM('info', 'warning', 'critical') NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (attempt_id) REFERENCES exam_attempts(id) ON DELETE CASCADE,
    INDEX idx_attempt_time (attempt_id, timestamp),
    INDEX idx_event_type (event_type),
    INDEX idx_severity (severity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert sample data

-- Insert sample users (Admin, Teachers, Students)
INSERT INTO users (username, email, password_hash, user_type, created_at) VALUES
('admin', 'admin@example.com', 'pbkdf2:sha256:260000$zwPVhY1iNSZHvXJ0$b0a19f991fdc8d4193c4454715213f8fc95f10158bef1e292916fd788c3afbf2', 'admin', NOW()),
('teacher1', 'teacher1@example.com', 'pbkdf2:sha256:260000$zwPVhY1iNSZHvXJ0$b0a19f991fdc8d4193c4454715213f8fc95f10158bef1e292916fd788c3afbf2', 'teacher', NOW()),
('teacher2', 'teacher2@example.com', 'pbkdf2:sha256:260000$zwPVhY1iNSZHvXJ0$b0a19f991fdc8d4193c4454715213f8fc95f10158bef1e292916fd788c3afbf2', 'teacher', NOW()),
('student1', 'student1@example.com', 'pbkdf2:sha256:260000$zwPVhY1iNSZHvXJ0$b0a19f991fdc8d4193c4454715213f8fc95f10158bef1e292916fd788c3afbf2', 'student', NOW()),
('student2', 'student2@example.com', 'pbkdf2:sha256:260000$zwPVhY1iNSZHvXJ0$b0a19f991fdc8d4193c4454715213f8fc95f10158bef1e292916fd788c3afbf2', 'student', NOW()),
('student3', 'student3@example.com', 'pbkdf2:sha256:260000$zwPVhY1iNSZHvXJ0$b0a19f991fdc8d4193c4454715213f8fc95f10158bef1e292916fd788c3afbf2', 'student', NOW());

-- Insert sample exams with security settings
INSERT INTO exams (
    title, description, time_limit_minutes, creator_id, is_published, created_at,
    access_code, allowed_ip_range, available_from, available_until, max_attempts,
    require_lockdown, periodic_checks, max_warnings, require_webcam,
    monitor_screen_share, block_virtual_machines, prevent_copy_paste, browser_fullscreen
) VALUES
('Python Basics', 'Test your knowledge of Python fundamentals', 30, 2, TRUE, NOW() - INTERVAL 20 DAY,
 'PY101', '192.168.1.0/24', NOW() - INTERVAL 21 DAY, NOW() + INTERVAL 10 DAY, 2,
 TRUE, 5, 3, TRUE, TRUE, TRUE, TRUE, TRUE),
 
('Data Structures', 'Assessment on various data structures and their applications', 45, 2, TRUE, NOW() - INTERVAL 15 DAY,
 'DS202', NULL, NOW() - INTERVAL 16 DAY, NOW() + INTERVAL 15 DAY, 1,
 TRUE, 10, 2, TRUE, TRUE, TRUE, TRUE, TRUE),
 
('Web Development', 'HTML, CSS, and JavaScript fundamentals', 60, 3, TRUE, NOW() - INTERVAL 10 DAY,
 'WEB303', '10.0.0.0/8', NOW() - INTERVAL 11 DAY, NOW() + INTERVAL 20 DAY, 2,
 TRUE, 5, 3, FALSE, TRUE, TRUE, TRUE, TRUE),
 
('Database Systems', 'SQL and database design principles', 45, 3, TRUE, NOW() - INTERVAL 7 DAY,
 'SQL404', NULL, NOW() - INTERVAL 8 DAY, NOW() + INTERVAL 23 DAY, 1,
 TRUE, 3, 3, TRUE, TRUE, TRUE, TRUE, TRUE),
 
('Advanced Python', 'Advanced Python concepts and libraries', 60, 2, FALSE, NOW() - INTERVAL 2 DAY,
 'PY505', '172.16.0.0/12', NOW() + INTERVAL 1 DAY, NOW() + INTERVAL 30 DAY, 1,
 TRUE, 5, 3, TRUE, TRUE, TRUE, TRUE, TRUE);

-- Insert sample questions for Python Basics exam
INSERT INTO questions (exam_id, question_text, question_type, points, `order`) VALUES
(1, 'What is the output of print(2**3)?', 'mcq', 1, 1),
(1, 'What function is used to get the length of a list in Python?', 'mcq', 1, 2),
(1, 'Write a Python function to check if a number is prime.', 'code', 3, 3),
(1, 'Explain the difference between a list and a tuple in Python.', 'text', 2, 4);

-- Insert options for MCQ questions
INSERT INTO question_options (question_id, option_text, is_correct, `order`) VALUES
(1, '6', FALSE, 1),
(1, '8', TRUE, 2),
(1, '5', FALSE, 3),
(1, '9', FALSE, 4),
(2, 'size()', FALSE, 1),
(2, 'length()', FALSE, 2),
(2, 'len()', TRUE, 3),
(2, 'sizeof()', FALSE, 4);

-- Insert sample questions for Data Structures exam
INSERT INTO questions (exam_id, question_text, question_type, points, `order`) VALUES
(2, 'Which data structure operates on the LIFO principle?', 'mcq', 1, 1),
(2, 'What is the time complexity of searching in a hash table?', 'mcq', 1, 2),
(2, 'Implement a function to reverse a linked list.', 'code', 3, 3),
(2, 'Compare and contrast arrays and linked lists.', 'text', 2, 4);

-- Insert options for Data Structures MCQ questions
INSERT INTO question_options (question_id, option_text, is_correct, `order`) VALUES
(5, 'Queue', FALSE, 1),
(5, 'Stack', TRUE, 2),
(5, 'Tree', FALSE, 3),
(5, 'Heap', FALSE, 4),
(6, 'O(1) average case', TRUE, 1),
(6, 'O(n) always', FALSE, 2),
(6, 'O(log n)', FALSE, 3),
(6, 'O(n²)', FALSE, 4);

-- Insert sample exam attempts
INSERT INTO exam_attempts (
    exam_id, student_id, started_at, completed_at, is_completed, is_graded,
    browser_fingerprint, ip_address, user_agent, screen_resolution,
    window_switches, focus_losses, warning_count, environment_verified,
    is_fullscreen, secure_browser_active, webcam_active, screen_share_active,
    verification_status, security_events, browser_events, warning_events
) VALUES
(1, 4, NOW() - INTERVAL 18 DAY, NOW() - INTERVAL 18 DAY + INTERVAL 25 MINUTE, TRUE, TRUE,
 'f4e8d9c3b2a1', '192.168.1.105', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0',
 '1920x1080', 2, 1, 1, TRUE, TRUE, TRUE, TRUE, TRUE, 'approved',
 '[{"type":"webcam_check","status":"passed","time":"2025-05-02T10:00:00Z"}]',
 '[{"type":"fullscreen","status":"active","time":"2025-05-02T10:00:00Z"}]',
 '[{"type":"tab_switch","count":1,"time":"2025-05-02T10:15:00Z"}]'),

(1, 5, NOW() - INTERVAL 17 DAY, NOW() - INTERVAL 17 DAY + INTERVAL 28 MINUTE, TRUE, TRUE,
 'a1b2c3d4e5f6', '192.168.1.110', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/120.0',
 '1680x1050', 0, 0, 0, TRUE, TRUE, TRUE, TRUE, TRUE, 'approved',
 '[{"type":"webcam_check","status":"passed","time":"2025-05-03T14:00:00Z"}]',
 '[{"type":"fullscreen","status":"active","time":"2025-05-03T14:00:00Z"}]',
 '[]'),

(2, 4, NOW() - INTERVAL 12 DAY, NOW() - INTERVAL 12 DAY + INTERVAL 40 MINUTE, TRUE, TRUE,
 'e5f6g7h8i9j0', '192.168.1.105', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Edge/120.0',
 '1920x1080', 1, 2, 1, TRUE, TRUE, TRUE, TRUE, TRUE, 'flagged',
 '[{"type":"webcam_check","status":"warning","time":"2025-05-08T09:00:00Z"}]',
 '[{"type":"fullscreen","status":"exit","time":"2025-05-08T09:30:00Z"}]',
 '[{"type":"focus_loss","count":2,"time":"2025-05-08T09:35:00Z"}]');

-- Insert sample answers for completed attempts
INSERT INTO answers (attempt_id, question_id, selected_option_id, text_answer, is_correct, teacher_feedback, created_at) VALUES
(1, 1, 2, NULL, TRUE, NULL, NOW() - INTERVAL 18 DAY + INTERVAL 10 MINUTE),
(1, 2, 7, NULL, TRUE, NULL, NOW() - INTERVAL 18 DAY + INTERVAL 15 MINUTE),
(1, 3, NULL, 'def is_prime(n):\n    if n <= 1:\n        return False\n    for i in range(2, int(n**0.5) + 1):\n        if n % i == 0:\n            return False\n    return True', TRUE, 'Good implementation!', NOW() - INTERVAL 18 DAY + INTERVAL 20 MINUTE),
(1, 4, NULL, 'Lists are mutable while tuples are immutable. Lists use square brackets and tuples use parentheses.', TRUE, 'Correct, but you could mention more differences like performance.', NOW() - INTERVAL 18 DAY + INTERVAL 25 MINUTE);

-- Insert sample exam reviews
INSERT INTO exam_reviews (exam_id, student_id, rating, feedback, created_at) VALUES
(1, 4, 5, 'Great exam, really tested my Python knowledge!', NOW() - INTERVAL 17 DAY),
(1, 5, 4, 'Good questions, but could use more code examples.', NOW() - INTERVAL 16 DAY),
(2, 4, 5, 'Challenging but fair assessment.', NOW() - INTERVAL 11 DAY),
(2, 6, 3, 'Some questions were ambiguous.', NOW() - INTERVAL 10 DAY),
(3, 5, 4, 'Loved the practical coding tasks.', NOW() - INTERVAL 7 DAY);

-- Insert sample notifications
INSERT INTO notifications (user_id, message, type, related_id, is_read, created_at) VALUES
(4, 'Your Python Basics exam has been graded.', 'exam_graded', 1, TRUE, NOW() - INTERVAL 17 DAY),
(5, 'Your Python Basics exam has been graded.', 'exam_graded', 2, TRUE, NOW() - INTERVAL 16 DAY),
(4, 'Your Data Structures exam has been graded.', 'exam_graded', 3, TRUE, NOW() - INTERVAL 11 DAY),
(6, 'Your Data Structures exam has been graded.', 'exam_graded', 4, TRUE, NOW() - INTERVAL 10 DAY),
(5, 'Your Web Development exam has been graded.', 'exam_graded', 5, TRUE, NOW() - INTERVAL 7 DAY),
(4, 'A new exam "Advanced Python" has been created.', 'exam_created', 5, FALSE, NOW() - INTERVAL 2 DAY),
(5, 'A new exam "Advanced Python" has been created.', 'exam_created', 5, FALSE, NOW() - INTERVAL 2 DAY),
(6, 'A new exam "Advanced Python" has been created.', 'exam_created', 5, FALSE, NOW() - INTERVAL 2 DAY);

-- Insert sample security events
INSERT INTO security_events (
    attempt_id, event_type, event_data, severity, timestamp
) VALUES
(1, 'browser_exit', 
    '{"reason": "tab_switch", "duration": "5s"}',
    'warning', NOW() - INTERVAL 18 DAY + INTERVAL 10 MINUTE),
(1, 'focus_loss',
    '{"duration": "3s", "reason": "alt_tab"}',
    'warning', NOW() - INTERVAL 18 DAY + INTERVAL 15 MINUTE),
(2, 'verification',
    '{"type": "webcam", "status": "passed", "confidence": 0.95}',
    'info', NOW() - INTERVAL 17 DAY + INTERVAL 1 MINUTE),
(3, 'warning',
    '{"type": "webcam_coverage", "details": "Face not fully visible"}',
    'warning', NOW() - INTERVAL 12 DAY + INTERVAL 20 MINUTE),
(3, 'browser_state',
    '{"type": "fullscreen_exit", "duration": "10s"}',
    'critical', NOW() - INTERVAL 12 DAY + INTERVAL 25 MINUTE);
