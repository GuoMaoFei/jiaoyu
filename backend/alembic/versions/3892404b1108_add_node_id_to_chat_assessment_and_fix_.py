"""add_node_id_to_chat_assessment_and_fix_relations

Revision ID: 3892404b1108
Revises: 06f8c7e0e6ce
Create Date: 2026-02-27 21:09:51.640092

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3892404b1108'
down_revision: Union[str, Sequence[str], None] = '06f8c7e0e6ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # SQLite doesn't support ALTER COLUMN, so we use batch mode for the nullable change
    # and standard ops for add_column and create_index.
    with op.batch_alter_table('chat_assessments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('node_id', sa.String(), nullable=True))
        batch_op.alter_column('message_id',
                   existing_type=sa.VARCHAR(),
                   nullable=True)
        batch_op.create_index(batch_op.f('ix_chat_assessments_node_id'), ['node_id'], unique=False)
        batch_op.create_foreign_key('fk_chat_assessments_node_id', 'knowledge_nodes', ['node_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('chat_assessments', schema=None) as batch_op:
        batch_op.drop_constraint('fk_chat_assessments_node_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_chat_assessments_node_id'))
        batch_op.alter_column('message_id',
                   existing_type=sa.VARCHAR(),
                   nullable=False)
        batch_op.drop_column('node_id')
