"""account_asset_type

Revision ID: 697027467ca8
Revises: 380a9c1e7d8f
Create Date: 2026-07-13 20:04:13.289816

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '697027467ca8'
down_revision: Union[str, None] = '380a9c1e7d8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # M12 (ADR-031): Account.asset_type. Native ADD COLUMN — accounts'a inbound FK
    # (transactions.account_id vb.) var, batch recreate FK-ON'da kırılır (M11 dersi).
    op.add_column("accounts", sa.Column("asset_type", sa.String(length=10), nullable=True))
    # Mevcut yatırım hesapları (fund_code'lu) fon → 'fund'
    op.execute(
        "UPDATE accounts SET asset_type = 'fund' "
        "WHERE account_type = 'investment' AND fund_code IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("accounts", "asset_type")
