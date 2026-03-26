"""add material_id to plan_items

Revision ID: add_material_id_plan
Revises: add_quiz_support
Create Date: 2025-03-15

"""

from alembic import op
import sqlalchemy as sa

revision = "add_material_id_plan"
down_revision = "add_quiz_support"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("plan_items", schema=None) as batch_op:
        batch_op.add_column(sa.Column("material_id", sa.String(), nullable=True))

    op.create_index(
        op.f("ix_plan_items_material_id"), "plan_items", ["material_id"], unique=False
    )

    op.execute("""
        UPDATE plan_items
        SET material_id = (
            SELECT kn.material_id
            FROM knowledge_nodes kn
            WHERE kn.id = plan_items.node_id
        )
        WHERE material_id IS NULL
    """)


def downgrade():
    op.drop_index(op.f("ix_plan_items_material_id"), table_name="plan_items")
    with op.batch_alter_table("plan_items", schema=None) as batch_op:
        batch_op.drop_column("material_id")
