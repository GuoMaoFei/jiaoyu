"""Add key_node fields to KnowledgeNode and create NodeQuiz table

Revision ID: add_quiz_support
Revises: fc1b4f923b9c
Create Date: 2026-03-08 14:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_quiz_support"
down_revision: Union[str, Sequence[str], None] = "fc1b4f923b9c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add key_node fields to knowledge_nodes
    op.add_column(
        "knowledge_nodes",
        sa.Column("is_key_node", sa.Integer(), nullable=True, server_default="0"),
    )
    op.add_column(
        "knowledge_nodes", sa.Column("key_node_reason", sa.Text(), nullable=True)
    )

    # Create node_quizzes table
    op.create_table(
        "node_quizzes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "student_id",
            sa.String(),
            sa.ForeignKey("students.id"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "node_id",
            sa.String(),
            sa.ForeignKey("knowledge_nodes.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("node_title", sa.String(), nullable=False),
        sa.Column("is_key_node", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("time_limit_min", sa.Integer(), nullable=False),
        sa.Column(
            "difficulty_level", sa.String(), nullable=True, server_default="medium"
        ),
        sa.Column("questions_json", sa.Text(), nullable=False),
        sa.Column("time_used_sec", sa.Integer(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("accuracy_pct", sa.Float(), nullable=True),
        sa.Column("answers_json", sa.Text(), nullable=True),
        sa.Column("results_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("node_quizzes")
    op.drop_column("knowledge_nodes", "key_node_reason")
    op.drop_column("knowledge_nodes", "is_key_node")
