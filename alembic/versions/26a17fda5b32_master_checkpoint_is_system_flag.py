"""master_checkpoint_is_system_flag

Revision ID: 26a17fda5b32
Revises: 978ad0f00814
Create Date: 2026-07-13 03:13:07.942442

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '26a17fda5b32'
down_revision: Union[str, None] = '978ad0f00814'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # W3-039 (RCH-002): sistem (Master) checkpoint koruması için is_system flag.
    # SQLite batch (render_as_batch=True). Mevcut satırlar server_default=0 alır.
    with op.batch_alter_table("master_checkpoints") as batch_op:
        batch_op.add_column(
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false())  # M50: dialect-aware boolean
        )
    # Çekirdek Master Checkpoint'ler "MC<n> -" konvansiyonuyla seed edilir → is_system=1.
    # M50: dialect-aware boolean literal (Postgres TRUE, SQLite 1)
    _true = "TRUE" if op.get_bind().dialect.name == "postgresql" else "1"
    op.execute(f"UPDATE master_checkpoints SET is_system = {_true} WHERE title LIKE 'MC%'")


def downgrade() -> None:
    with op.batch_alter_table("master_checkpoints") as batch_op:
        batch_op.drop_column("is_system")
