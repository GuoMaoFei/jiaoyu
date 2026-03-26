"""merge_heads

Revision ID: eac6c38ccb1b
Revises: 3defe00fe431, add_material_id_plan
Create Date: 2026-03-15 20:34:33.249672

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eac6c38ccb1b'
down_revision: Union[str, Sequence[str], None] = ('3defe00fe431', 'add_material_id_plan')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
