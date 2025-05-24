"""
Database migration script to update enums and fix schema problems.
Run this after updating to the fixed models.
"""
from sqlalchemy import create_engine, text, MetaData, Table, Column, Enum
from sqlalchemy.ext.declarative import declarative_base
from config import Config
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Run the database migration to fix schema issues"""
    logger.info("Starting database schema migration")
    
    # Create a database connection
    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    connection = engine.connect()
    transaction = connection.begin()
    
    try:
        # 1. Update verification_status_enum if it exists
        logger.info("Updating verification_status_enum")
        connection.execute(text("""
        -- Check if the enum exists and update it
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 
                FROM pg_type 
                WHERE typname = 'verification_status_enum'
            ) THEN
                -- Drop constraints that use the enum
                ALTER TABLE exam_attempts 
                ALTER COLUMN verification_status TYPE VARCHAR(20);
                
                -- Drop the enum type
                DROP TYPE verification_status_enum;
                
                -- Create new enum type
                CREATE TYPE verification_status_enum AS ENUM (
                    'pending', 'approved', 'flagged', 'auto_flagged'
                );
                
                -- Convert column back to enum type
                ALTER TABLE exam_attempts 
                ALTER COLUMN verification_status TYPE verification_status_enum 
                USING verification_status::verification_status_enum;
            END IF;
        END $$;
        """))
        
        # 2. Create other enum types if they don't exist
        logger.info("Creating user_type_enum")
        connection.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 
                FROM pg_type 
                WHERE typname = 'user_type_enum'
            ) THEN
                CREATE TYPE user_type_enum AS ENUM (
                    'admin', 'teacher', 'student'
                );
            END IF;
        END $$;
        """))
        
        logger.info("Creating question_type_enum")
        connection.execute(text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 
                FROM pg_type 
                WHERE typname = 'question_type_enum'
            ) THEN
                CREATE TYPE question_type_enum AS ENUM (
                    'mcq', 'text', 'code'
                );
            END IF;
        END $$;
        """))
        
        # 3. Add missing indexes
        logger.info("Adding missing indexes")
        connection.execute(text("""
        -- Exam indexes
        CREATE INDEX IF NOT EXISTS idx_exam_availability 
        ON exams (is_published, available_from, available_until);
        
        CREATE INDEX IF NOT EXISTS idx_exam_creator 
        ON exams (creator_id);
        
        CREATE INDEX IF NOT EXISTS idx_exam_group 
        ON exams (group_id);
        
        -- Question indexes
        CREATE INDEX IF NOT EXISTS idx_question_exam 
        ON questions (exam_id);
        
        CREATE INDEX IF NOT EXISTS idx_question_type 
        ON questions (question_type);
        
        -- Option indexes
        CREATE INDEX IF NOT EXISTS idx_option_question 
        ON question_options (question_id);
        
        -- Answer indexes
        CREATE INDEX IF NOT EXISTS idx_answer_attempt 
        ON answers (attempt_id);
        
        CREATE INDEX IF NOT EXISTS idx_answer_question 
        ON answers (question_id);
        
        -- ExamAttempt indexes
        CREATE INDEX IF NOT EXISTS idx_attempt_completion 
        ON exam_attempts (is_completed, completed_at);
        
        -- Group indexes
        CREATE INDEX IF NOT EXISTS idx_group_archived 
        ON groups (archived);
        
        -- Notification indexes
        CREATE INDEX IF NOT EXISTS idx_notification_user 
        ON notifications (user_id, is_read);
        
        -- Security log indexes
        CREATE INDEX IF NOT EXISTS idx_security_log_type 
        ON security_logs (event_type, severity);
        
        CREATE INDEX IF NOT EXISTS idx_security_log_ip 
        ON security_logs (ip_address);
        
        CREATE INDEX IF NOT EXISTS idx_security_log_time 
        ON security_logs (timestamp);
        
        -- Activity log indexes
        CREATE INDEX IF NOT EXISTS idx_activity_category 
        ON activity_logs (category);
        
        CREATE INDEX IF NOT EXISTS idx_activity_time 
        ON activity_logs (created_at);
        
        CREATE INDEX IF NOT EXISTS idx_activity_action 
        ON activity_logs (action);
        
        -- Membership indexes
        CREATE INDEX IF NOT EXISTS idx_membership_user 
        ON group_membership (user_id);
        
        CREATE INDEX IF NOT EXISTS idx_membership_group 
        ON group_membership (group_id);
        """))
        
        # 4. Add missing columns for versioning
        logger.info("Adding version columns")
        connection.execute(text("""
        -- Add version column to exams if it doesn't exist
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name='exams' AND column_name='version'
            ) THEN
                ALTER TABLE exams ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
            END IF;
        END $$;
        
        -- Add version column to questions if it doesn't exist
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name='questions' AND column_name='version'
            ) THEN
                ALTER TABLE questions ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
            END IF;
        END $$;
        
        -- Add version column to answers if it doesn't exist
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name='answers' AND column_name='version'
            ) THEN
                ALTER TABLE answers ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
            END IF;
            
            -- Add updated_at column to answers if it doesn't exist
            IF NOT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name='answers' AND column_name='updated_at'
            ) THEN
                ALTER TABLE answers ADD COLUMN updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW();
            END IF;
        END $$;
        """))
        
        # 5. Add check constraints
        logger.info("Adding check constraints")
        connection.execute(text("""
        -- Add check constraint for exam review ratings
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.constraint_column_usage
                WHERE table_name='exam_reviews' AND constraint_name='chk_rating_range'
            ) THEN
                ALTER TABLE exam_reviews 
                ADD CONSTRAINT chk_rating_range 
                CHECK (rating >= 1 AND rating <= 5);
            END IF;
        END $$;
        """))
        
        # 6. Update cascade delete behavior
        logger.info("Updating foreign key constraints")
        connection.execute(text("""
        -- Update exam_reviews cascade behavior
        ALTER TABLE exam_reviews 
        DROP CONSTRAINT IF EXISTS exam_reviews_exam_id_fkey;
        
        ALTER TABLE exam_reviews 
        ADD CONSTRAINT exam_reviews_exam_id_fkey 
        FOREIGN KEY (exam_id) REFERENCES exams(id) ON DELETE CASCADE;
        
        ALTER TABLE exam_reviews 
        DROP CONSTRAINT IF EXISTS exam_reviews_student_id_fkey;
        
        ALTER TABLE exam_reviews 
        ADD CONSTRAINT exam_reviews_student_id_fkey 
        FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE;
        
        -- Update answers cascade behavior
        ALTER TABLE answers 
        DROP CONSTRAINT IF EXISTS answers_attempt_id_fkey;
        
        ALTER TABLE answers 
        ADD CONSTRAINT answers_attempt_id_fkey 
        FOREIGN KEY (attempt_id) REFERENCES exam_attempts(id) ON DELETE CASCADE;
        
        ALTER TABLE answers 
        DROP CONSTRAINT IF EXISTS answers_question_id_fkey;
        
        ALTER TABLE answers 
        ADD CONSTRAINT answers_question_id_fkey 
        FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE;
        
        -- Update group_membership cascade behavior
        ALTER TABLE group_membership 
        DROP CONSTRAINT IF EXISTS group_membership_user_id_fkey;
        
        ALTER TABLE group_membership 
        ADD CONSTRAINT group_membership_user_id_fkey 
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        
        ALTER TABLE group_membership 
        DROP CONSTRAINT IF EXISTS group_membership_group_id_fkey;
        
        ALTER TABLE group_membership 
        ADD CONSTRAINT group_membership_group_id_fkey 
        FOREIGN KEY (group_id) REFERENCES groups(id) ON DELETE CASCADE;
        """))
        
        # Commit the transaction
        transaction.commit()
        logger.info("Database migration completed successfully")
        
    except Exception as e:
        transaction.rollback()
        logger.error(f"Migration failed: {str(e)}")
        raise
    finally:
        connection.close()

if __name__ == "__main__":
    run_migration()
