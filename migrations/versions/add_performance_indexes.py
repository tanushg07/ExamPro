"""Add performance indexes to frequently queried fields

Revision ID: add_performance_indexes
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add indexes for exam attempts
    op.create_index('idx_attempt_exam_completion', 'exam_attempts', ['exam_id', 'is_completed'])
    op.create_index('idx_attempt_student_status', 'exam_attempts', ['student_id', 'is_completed', 'is_graded'])
    op.create_index('idx_attempt_times', 'exam_attempts', ['started_at', 'completed_at'])
    
    # Add indexes for answers
    op.create_index('idx_answer_attempt', 'answers', ['attempt_id'])
    op.create_index('idx_answer_question', 'answers', ['question_id', 'is_correct'])
    
    # Add indexes for questions
    op.create_index('idx_question_exam', 'questions', ['exam_id', 'order'])
    op.create_index('idx_question_type', 'questions', ['exam_id', 'question_type'])
    
    # Add indexes for security monitoring
    op.create_index('idx_attempt_security', 'exam_attempts', ['warning_count', 'verification_status'])
    op.create_index('idx_attempt_monitoring', 'exam_attempts', ['exam_id', 'environment_verified', 'secure_browser_active'])


def downgrade():
    # Remove indexes in reverse order
    op.drop_index('idx_attempt_monitoring')
    op.drop_index('idx_attempt_security')
    op.drop_index('idx_question_type')
    op.drop_index('idx_question_exam')
    op.drop_index('idx_answer_question')
    op.drop_index('idx_answer_attempt')
    op.drop_index('idx_attempt_times')
    op.drop_index('idx_attempt_student_status')
    op.drop_index('idx_attempt_exam_completion')
