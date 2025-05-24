"""add class fields

Revision ID: add_class_fields
Revises: 7f9c8a94e2d3
Create Date: 2025-05-20

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_class_fields'
down_revision = '7f9c8a94e2d3'
depends_on = None

def upgrade():
    # Add new columns to groups table
    op.add_column('groups', sa.Column('subject', sa.String(50), nullable=True))
    op.add_column('groups', sa.Column('section', sa.String(20), nullable=True))
    op.add_column('groups', sa.Column('room', sa.String(20), nullable=True))
    op.add_column('groups', sa.Column('archived', sa.Boolean, nullable=False, server_default='0'))

    # Make group code exactly 6 characters
    op.alter_column('groups', 'code',
                    existing_type=sa.String(20),
                    type_=sa.String(6),
                    existing_nullable=False)


def downgrade():
    # Remove columns added in upgrade
    op.drop_column('groups', 'subject')
    op.drop_column('groups', 'section')
    op.drop_column('groups', 'room')
    op.drop_column('groups', 'archived')
    
    # Revert code column length
    op.alter_column('groups', 'code',
                    existing_type=sa.String(6),
                    type_=sa.String(20),
                    existing_nullable=False)
