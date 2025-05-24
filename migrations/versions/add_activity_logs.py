"""Add activity logs table

Revision ID: add_activity_logs
Create Date: 2025-05-21 22:05:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import JSON

def upgrade():
    # Create activity_logs table
    op.create_table(
        'activity_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('details', JSON, nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add indexes for better query performance
    op.create_index('idx_activity_user', 'activity_logs', ['user_id'])
    op.create_index('idx_activity_category', 'activity_logs', ['category'])
    op.create_index('idx_activity_created', 'activity_logs', ['created_at'])

def downgrade():
    op.drop_table('activity_logs')
