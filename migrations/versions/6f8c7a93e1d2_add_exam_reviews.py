"""Add exam reviews table

Revision ID: 6f8c7a93e1d2
Revises: previous_revision_id
Create Date: 2025-05-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6f8c7a93e1d2'
down_revision = None  # Replace with previous migration ID
branch_labels = None
depends_on = None


def upgrade():
    # Create exam_reviews table
    op.create_table('exam_reviews',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('exam_id', sa.Integer(), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['exam_id'], ['exams.id'], ),
        sa.ForeignKeyConstraint(['student_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add is_graded column to exam_attempts if it doesn't exist
    op.add_column('exam_attempts', sa.Column('is_graded', sa.Boolean(), nullable=True, server_default='0'))


def downgrade():
    # Remove exam_reviews table
    op.drop_table('exam_reviews')
    
    # Remove is_graded column from exam_attempts
    op.drop_column('exam_attempts', 'is_graded')
