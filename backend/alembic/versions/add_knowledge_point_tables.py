"""add knowledge point tables

Revision ID: add_knowledge_point_tables
Revises: add_mistake_review_fields
Create Date: 2026-04-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_knowledge_point_tables'
down_revision: Union[str, Sequence[str], None] = 'add_mistake_review_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create knowledge_points table
    op.create_table(
        'knowledge_points',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('parent_id', sa.String(), nullable=True),
        sa.Column('subject', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('keywords', sa.Text(), nullable=True),
        sa.Column('level', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('parent_title', sa.String(), nullable=True),
        sa.Column('embedding_hash', sa.String(), nullable=True),
        sa.Column('source_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['parent_id'], ['knowledge_points.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_knowledge_points_id'), 'knowledge_points', ['id'], unique=False)
    op.create_index(op.f('ix_knowledge_points_parent_id'), 'knowledge_points', ['parent_id'], unique=False)
    op.create_index(op.f('ix_knowledge_points_subject'), 'knowledge_points', ['subject'], unique=False)
    op.create_index(op.f('ix_knowledge_points_embedding_hash'), 'knowledge_points', ['embedding_hash'], unique=False)

    # 2. Create knowledge_point_mappings table
    op.create_table(
        'knowledge_point_mappings',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('knowledge_point_id', sa.String(), nullable=False),
        sa.Column('knowledge_node_id', sa.String(), nullable=False),
        sa.Column('relevance_score', sa.Integer(), nullable=True),
        sa.Column('context_snippet', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['knowledge_point_id'], ['knowledge_points.id'], ),
        sa.ForeignKeyConstraint(['knowledge_node_id'], ['knowledge_nodes.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('knowledge_point_id', 'knowledge_node_id', name='uq_kp_node')
    )
    op.create_index(op.f('ix_knowledge_point_mappings_id'), 'knowledge_point_mappings', ['id'], unique=False)
    op.create_index(op.f('ix_knowledge_point_mappings_knowledge_point_id'), 'knowledge_point_mappings', ['knowledge_point_id'], unique=False)
    op.create_index(op.f('ix_knowledge_point_mappings_knowledge_node_id'), 'knowledge_point_mappings', ['knowledge_node_id'], unique=False)

    # 3. Add knowledge_point_id to student_mistakes
    with op.batch_alter_table('student_mistakes', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('knowledge_point_id', sa.String(), nullable=True)
        )
    op.create_index(
        op.f('ix_student_mistakes_knowledge_point_id'),
        'student_mistakes', ['knowledge_point_id'], unique=False
    )
    # Add FK constraint separately for SQLite compatibility
    with op.batch_alter_table('student_mistakes', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_student_mistakes_knowledge_point_id',
            'knowledge_points', ['knowledge_point_id'], ['id']
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Reverse order: drop FK + column from student_mistakes, then mappings table, then points table
    op.drop_index(op.f('ix_student_mistakes_knowledge_point_id'), table_name='student_mistakes')
    with op.batch_alter_table('student_mistakes', schema=None) as batch_op:
        batch_op.drop_constraint('fk_student_mistakes_knowledge_point_id', type_='foreignkey')
        batch_op.drop_column('knowledge_point_id')

    op.drop_index(op.f('ix_knowledge_point_mappings_knowledge_node_id'), table_name='knowledge_point_mappings')
    op.drop_index(op.f('ix_knowledge_point_mappings_knowledge_point_id'), table_name='knowledge_point_mappings')
    op.drop_index(op.f('ix_knowledge_point_mappings_id'), table_name='knowledge_point_mappings')
    op.drop_table('knowledge_point_mappings')

    op.drop_index(op.f('ix_knowledge_points_embedding_hash'), table_name='knowledge_points')
    op.drop_index(op.f('ix_knowledge_points_subject'), table_name='knowledge_points')
    op.drop_index(op.f('ix_knowledge_points_parent_id'), table_name='knowledge_points')
    op.drop_index(op.f('ix_knowledge_points_id'), table_name='knowledge_points')
    op.drop_table('knowledge_points')
