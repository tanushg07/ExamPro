-- Add activity logs table for tracking all user actions
CREATE TABLE activity_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    action VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,  -- e.g., 'exam', 'question', 'auth', etc.
    details JSON NULL,  -- Store additional context as JSON
    ip_address VARCHAR(45) NULL,  -- IPv4/IPv6 address
    user_agent VARCHAR(255) NULL, -- Browser/client info
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Add foreign key constraint
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    
    -- Add indexes for common queries
    INDEX idx_activity_user (user_id),
    INDEX idx_activity_category (category),
    INDEX idx_activity_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Sample activity categories and their meanings:
-- 'auth': Login, logout, password changes
-- 'exam': Create, edit, delete, publish exams
-- 'question': Add, edit, delete questions
-- 'attempt': Start, submit exam attempts
-- 'grade': Grade submissions, provide feedback
-- 'group': Create, join, leave groups
-- 'admin': User management, system settings
-- 'security': Security-related events
