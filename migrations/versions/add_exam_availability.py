"""add exam availability columns

Revision ID: add_exam_availability
Revises: create_security_logs
Create Date: 2025-05-21 20:03:14.450

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_exam_availability'
down_revision = 'create_security_logs'
branch_labels = None
depends_on = None


def upgrade():
    # Add available_from and available_until columns to exams table
    op.add_column('exams', sa.Column('available_from', sa.DateTime(), nullable=True))
    op.add_column('exams', sa.Column('available_until', sa.DateTime(), nullable=True))


def downgrade():
    # Remove the columns
    op.drop_column('exams', 'available_until')
    op.drop_column('exams', 'available_from')
