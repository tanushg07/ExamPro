-- File: exam_platform.sql
-- Description: Database schema and sample data for the Exam Platform application

-- Create database
CREATE DATABASE IF NOT EXISTS exam_platform;
USE exam_platform;

-- Drop tables if they exist to avoid conflicts
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS exam_reviews;
DROP TABLE IF EXISTS answers;
DROP TABLE IF EXISTS question_options;
DROP TABLE IF EXISTS questions;
DROP TABLE IF EXISTS exam_attempts;
DROP TABLE IF EXISTS exams;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS security_events;

-- Create tables with proper indexes
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64) NOT NULL UNIQUE,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    user_type VARCHAR(20) NOT NULL, -- admin/teacher/student
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_user_type (user_type)
);

CREATE TABLE exams (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    time_limit_minutes INT NOT NULL,
    creator_id INT NOT NULL,
    is_published BOOLEAN DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Access Control
    access_code VARCHAR(10),  -- Optional access code
    allowed_ip_range VARCHAR(100),  -- IP range in CIDR format (e.g., 192.168.1.0/24)
    available_from DATETIME,  -- When the exam becomes available
    available_until DATETIME,  -- When the exam expires
    max_attempts INT DEFAULT 1,  -- Maximum number of attempts allowed
    join_before_minutes INT DEFAULT 15,  -- Minutes before start that students can join
    
    -- Security Settings
    require_lockdown BOOLEAN DEFAULT TRUE,  -- Require lockdown browser mode
    allow_calculator BOOLEAN DEFAULT FALSE,  -- Allow calculator during exam
    allow_scratch_pad BOOLEAN DEFAULT TRUE,  -- Allow digital scratch pad
    randomize_questions BOOLEAN DEFAULT TRUE,  -- Randomize question order
    one_question_at_time BOOLEAN DEFAULT FALSE,  -- Show one question at a time
    prevent_copy_paste BOOLEAN DEFAULT TRUE,  -- Disable copy/paste
    require_webcam BOOLEAN DEFAULT FALSE,  -- Require webcam monitoring
    allow_backward_navigation BOOLEAN DEFAULT TRUE,  -- Allow going back to previous questions
    show_remaining_time BOOLEAN DEFAULT TRUE,  -- Show countdown timer
    auto_submit BOOLEAN DEFAULT TRUE,  -- Auto submit when time expires
    require_face_verification BOOLEAN DEFAULT FALSE,  -- Verify student face
    proctor_monitoring BOOLEAN DEFAULT FALSE,  -- Enable live proctor monitoring
    monitor_screen_share BOOLEAN DEFAULT FALSE,  -- Monitor screen sharing
    periodic_checks BOOLEAN DEFAULT TRUE,  -- Enable periodic environment checks
    detect_browser_exit BOOLEAN DEFAULT TRUE,  -- Detect browser/tab exits
    max_warnings INT DEFAULT 3,  -- Maximum warnings before auto-submit
    block_virtual_machines BOOLEAN DEFAULT TRUE,  -- Block access from VMs
    browser_fullscreen BOOLEAN DEFAULT TRUE,  -- Require fullscreen mode
    restrict_keyboard BOOLEAN DEFAULT FALSE,  -- Restrict keyboard shortcuts
    block_external_displays BOOLEAN DEFAULT TRUE,  -- Block external displays
    
    -- Proctoring Settings
    proctor_instructions TEXT,  -- Instructions for proctors
    proctor_notes TEXT,  -- Notes for proctors
    max_students_per_proctor INT DEFAULT 20,  -- Maximum students per proctor
    proctor_join_before INT DEFAULT 30,  -- Minutes before exam proctors can join
    
    FOREIGN KEY (creator_id) REFERENCES users(id),
    INDEX idx_creator_published (creator_id, is_published),
    INDEX idx_access_time (available_from, available_until),
    INDEX idx_created_at (created_at)
);

CREATE TABLE questions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    exam_id INT NOT NULL,
    question_text TEXT NOT NULL,
    question_type VARCHAR(20) NOT NULL, -- mcq/code/text
    points INT NOT NULL DEFAULT 1,
    `order` INT NOT NULL DEFAULT 0,
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    INDEX idx_exam_order (exam_id, `order`)
);

CREATE TABLE question_options (
    id INT AUTO_INCREMENT PRIMARY KEY,
    question_id INT NOT NULL,
    option_text TEXT NOT NULL,
    is_correct BOOLEAN DEFAULT FALSE,
    `order` INT NOT NULL DEFAULT 0,
    FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE,
    INDEX idx_question_order (question_id, `order`)
);

CREATE TABLE exam_attempts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    exam_id INT NOT NULL,
    student_id INT NOT NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    is_completed BOOLEAN DEFAULT FALSE,
    is_graded BOOLEAN DEFAULT FALSE,
    score DECIMAL(5,2),
    
    -- Security Monitoring
    browser_fingerprint VARCHAR(255),  -- Browser fingerprint for identity verification
    ip_address VARCHAR(45),  -- IP address of student
    user_agent VARCHAR(255),  -- Browser user agent
    screen_resolution VARCHAR(20),  -- Screen resolution
    window_switches INT DEFAULT 0,  -- Number of times window/tab was switched
    focus_losses INT DEFAULT 0,  -- Number of times window lost focus
    warning_count INT DEFAULT 0,  -- Number of warnings issued
    last_check_time DATETIME,  -- Last automated check timestamp
    environment_verified BOOLEAN DEFAULT FALSE,  -- Initial environment check passed
    
    -- Browser State
    is_fullscreen BOOLEAN DEFAULT FALSE,  -- Currently in fullscreen mode
    secure_browser_active BOOLEAN DEFAULT FALSE,  -- Secure browser mode active
    webcam_active BOOLEAN DEFAULT FALSE,  -- Webcam monitoring active
    screen_share_active BOOLEAN DEFAULT FALSE,  -- Screen sharing active
    
    -- Event Logs (JSON)
    security_events JSON,  -- Log of security-related events
    browser_events JSON,  -- Log of browser state changes
    warning_events JSON,  -- Log of warnings issued
    verification_status VARCHAR(20) DEFAULT 'pending',  -- pending/approved/flagged
    
    FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id),
    INDEX idx_exam_student (exam_id, student_id),
    INDEX idx_student_completed (student_id, is_completed),
    INDEX idx_verification (verification_status),
    INDEX idx_grading_status (is_completed, is_graded)
);

CREATE TABLE answers (
    id INT AUTO_INCREMENT PRIMARY KEY,
    attempt_id INT NOT NULL,
    question_id INT NOT NULL,
    selected_option_id INT,
    text_answer TEXT,
    code_answer TEXT,
    is_correct BOOLEAN,
    teacher_feedback TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (attempt_id) REFERENCES exam_attempts(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES questions(id),
    FOREIGN KEY (selected_option_id) REFERENCES question_options(id),
    INDEX idx_attempt_question (attempt_id, question_id),
    INDEX idx_created_at (created_at)
);

CREATE TABLE exam_reviews (
    id INT AUTO_INCREMENT PRIMARY KEY,
    exam_id INT NOT NULL,
    student_id INT NOT NULL,
    rating INT NOT NULL, -- 1-5 stars
    feedback TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (exam_id) REFERENCES exams(id),
    FOREIGN KEY (student_id) REFERENCES users(id),
    INDEX idx_exam_student (exam_id, student_id),
    INDEX idx_rating (rating)
);

CREATE TABLE notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    message VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL, -- 'info', 'exam_graded', 'exam_created', etc.
    related_id INT, -- Optional ID of related entity (exam, attempt)
    is_read BOOLEAN DEFAULT FALSE,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    INDEX idx_user_read (user_id, is_read),
    INDEX idx_created_at (created_at)
);

CREATE TABLE security_events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    attempt_id INT NOT NULL,
    event_type VARCHAR(50) NOT NULL,  -- browser_exit, focus_loss, warning, verification, etc.
    event_data JSON,  -- Detailed event information
    severity VARCHAR(20) NOT NULL,  -- info, warning, critical
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (attempt_id) REFERENCES exam_attempts(id) ON DELETE CASCADE,
    INDEX idx_attempt_time (attempt_id, timestamp),
    INDEX idx_event_type (event_type),
    INDEX idx_severity (severity)
);

-- Sample Data

-- Insert sample users (Admin, Teachers, Students)
-- Note: Password hashes are generated with PBKDF2-SHA256 for a secure default password
INSERT INTO users (username, email, password_hash, user_type, created_at) VALUES
('admin', 'admin@example.com', 'pbkdf2:sha256:260000$zwPVhY1iNSZHvXJ0$b0a19f991fdc8d4193c4454715213f8fc95f10158bef1e292916fd788c3afbf2', 'admin', NOW()),
('teacher1', 'teacher1@example.com', 'pbkdf2:sha256:260000$zwPVhY1iNSZHvXJ0$b0a19f991fdc8d4193c4454715213f8fc95f10158bef1e292916fd788c3afbf2', 'teacher', NOW()),
('teacher2', 'teacher2@example.com', 'pbkdf2:sha256:260000$zwPVhY1iNSZHvXJ0$b0a19f991fdc8d4193c4454715213f8fc95f10158bef1e292916fd788c3afbf2', 'teacher', NOW()),
('student1', 'student1@example.com', 'pbkdf2:sha256:260000$zwPVhY1iNSZHvXJ0$b0a19f991fdc8d4193c4454715213f8fc95f10158bef1e292916fd788c3afbf2', 'student', NOW()),
('student2', 'student2@example.com', 'pbkdf2:sha256:260000$zwPVhY1iNSZHvXJ0$b0a19f991fdc8d4193c4454715213f8fc95f10158bef1e292916fd788c3afbf2', 'student', NOW()),
('student3', 'student3@example.com', 'pbkdf2:sha256:260000$zwPVhY1iNSZHvXJ0$b0a19f991fdc8d4193c4454715213f8fc95f10158bef1e292916fd788c3afbf2', 'student', NOW());

select * from users;
-- Update password_hash for all sample users
-- UPDATE users 
-- SET password_hash = 'pbkdf2:sha256:260000$MCCRAZ4Eyiag7HvL$e69fe7329d402f68a46120a241733541f8d768e6f27c789fa375ebb046bc7dd6'
-- WHERE username IN ('admin', 'teacher1', 'teacher2', 'student1', 'student2', 'student3');


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

-- Insert sample questions for Web Development exam
INSERT INTO questions (exam_id, question_text, question_type, points, `order`) VALUES
(3, 'Which HTML tag is used to define a hyperlink?', 'mcq', 1, 1),
(3, 'What CSS property is used to change the text color?', 'mcq', 1, 2),
(3, 'Create a simple form with validation using JavaScript.', 'code', 3, 3),
(3, 'Explain the concept of responsive web design.', 'text', 2, 4);

-- Insert options for Web Development MCQ questions
INSERT INTO question_options (question_id, option_text, is_correct, `order`) VALUES
(9, '<a>', TRUE, 1),
(9, '<link>', FALSE, 2),
(9, '<href>', FALSE, 3),
(9, '<url>', FALSE, 4),
(10, 'text-color', FALSE, 1),
(10, 'font-color', FALSE, 2),
(10, 'color', TRUE, 3),
(10, 'text-style', FALSE, 4);

-- Insert sample questions for Database Systems exam
INSERT INTO questions (exam_id, question_text, question_type, points, `order`) VALUES
(4, 'What SQL statement is used to retrieve data from a database?', 'mcq', 1, 1),
(4, 'Which normalization form eliminates transitive dependencies?', 'mcq', 1, 2),
(4, 'Write a SQL query to find the second highest salary in an employees table.', 'code', 3, 3),
(4, 'Explain the difference between INNER JOIN and LEFT JOIN.', 'text', 2, 4);

-- Insert options for Database Systems MCQ questions
INSERT INTO question_options (question_id, option_text, is_correct, `order`) VALUES
(13, 'GET', FALSE, 1),
(13, 'SELECT', TRUE, 2),
(13, 'FETCH', FALSE, 3),
(13, 'QUERY', FALSE, 4),
(14, '1NF', FALSE, 1),
(14, '2NF', FALSE, 2),
(14, '3NF', TRUE, 3),
(14, '4NF', FALSE, 4);

-- Insert sample exam attempts
INSERT INTO exam_attempts (exam_id, student_id, started_at, completed_at, is_completed, is_graded) VALUES
(1, 4, NOW() - INTERVAL 18 DAY, NOW() - INTERVAL 18 DAY + INTERVAL 25 MINUTE, TRUE, TRUE),
(1, 5, NOW() - INTERVAL 17 DAY, NOW() - INTERVAL 17 DAY + INTERVAL 28 MINUTE, TRUE, TRUE),
(2, 4, NOW() - INTERVAL 12 DAY, NOW() - INTERVAL 12 DAY + INTERVAL 40 MINUTE, TRUE, TRUE),
(2, 6, NOW() - INTERVAL 11 DAY, NOW() - INTERVAL 11 DAY + INTERVAL 42 MINUTE, TRUE, TRUE),
(3, 5, NOW() - INTERVAL 8 DAY, NOW() - INTERVAL 8 DAY + INTERVAL 55 MINUTE, TRUE, TRUE),
(4, 6, NOW() - INTERVAL 5 DAY, NOW() - INTERVAL 5 DAY + INTERVAL 43 MINUTE, TRUE, FALSE),
(4, 4, NOW() - INTERVAL 4 DAY, NULL, FALSE, FALSE);

-- Insert sample exam attempts with security monitoring
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
-- Student 1's answers for Python Basics
INSERT INTO answers (attempt_id, question_id, selected_option_id, text_answer, is_correct, teacher_feedback, created_at) VALUES
(1, 1, 2, NULL, TRUE, NULL, NOW() - INTERVAL 18 DAY + INTERVAL 10 MINUTE),
(1, 2, 7, NULL, TRUE, NULL, NOW() - INTERVAL 18 DAY + INTERVAL 15 MINUTE),
(1, 3, NULL, 'def is_prime(n):\n    if n <= 1:\n        return False\n    for i in range(2, int(n**0.5) + 1):\n        if n % i == 0:\n            return False\n    return True', TRUE, 'Good implementation!', NOW() - INTERVAL 18 DAY + INTERVAL 20 MINUTE),
(1, 4, NULL, 'Lists are mutable while tuples are immutable. Lists use square brackets and tuples use parentheses.', TRUE, 'Correct, but you could mention more differences like performance.', NOW() - INTERVAL 18 DAY + INTERVAL 25 MINUTE);

-- Student 2's answers for Python Basics
INSERT INTO answers (attempt_id, question_id, selected_option_id, text_answer, is_correct, teacher_feedback, created_at) VALUES
(2, 1, 1, NULL, FALSE, NULL, NOW() - INTERVAL 17 DAY + INTERVAL 10 MINUTE),
(2, 2, 7, NULL, TRUE, NULL, NOW() - INTERVAL 17 DAY + INTERVAL 18 MINUTE),
(2, 3, NULL, 'def is_prime(n):\n    if n < 2:\n        return False\n    for i in range(2, n):\n        if n % i == 0:\n            return False\n    return True', FALSE, 'Your solution works but is inefficient. You only need to check up to sqrt(n).', NOW() - INTERVAL 17 DAY + INTERVAL 25 MINUTE),
(2, 4, NULL, 'Lists can be changed after creation, tuples cannot.', TRUE, 'Basic answer, but correct.', NOW() - INTERVAL 17 DAY + INTERVAL 28 MINUTE);

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







