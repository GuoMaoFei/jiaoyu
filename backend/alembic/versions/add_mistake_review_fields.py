"""add_mistake_review_fields

Revision ID: add_mistake_review_fields
Revises: eac6c38ccb1b
Create Date: 2026-04-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'add_mistake_review_fields'
down_revision: Union[str, Sequence[str], None] = 'eac6c38ccb1b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('student_mistakes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('root_cause_summary', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('review_count', sa.Integer(), nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('last_reviewed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('student_mistakes', schema=None) as batch_op:
        batch_op.drop_column('last_reviewed_at')
        batch_op.drop_column('review_count')
        batch_op.drop_column('root_cause_summary')
