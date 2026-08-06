"""BUG #241: personal_debts.settlement_account_id — kapanisin nakit ayaginin izi

Panelden "Odendi" isaretlenen alacak/borc nakit tarafinda karsilik uretmiyordu (kullanici
bildirimi: "5000 TL tahsil isaretledim, bakiyem artmadi"). Nakit ayagi artik TEK KAYNAKTAN
uygulanir (app/services/debt_settlement.py) ve hangi hesaba islendigi bu kolonda iz birakir.

Kolon ayni zamanda "ayak uygulandi mi" isaretidir: NULL = uygulanmadi. Fix ONCESI panelden
odendi isaretlenmis eski kayitlar NULL kalir; geri alinirlarsa nakitten para DUSMEZ
(uygulanmamis ayak geri sarilamaz — hayalet para yok).

Fiziksel FK yalnizca PostgreSQL'de (SQLite ALTER ile FK ekleyemez; d4e5f6a7b8c9 deseni).

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f2a3b4c5d6e7"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "personal_debts",
        sa.Column("settlement_account_id", sa.Integer(), nullable=True),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.create_foreign_key(
            "fk_personal_debts_settlement_account_id", "personal_debts", "accounts",
            ["settlement_account_id"], ["id"],
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint(
            "fk_personal_debts_settlement_account_id", "personal_debts", type_="foreignkey"
        )
    op.drop_column("personal_debts", "settlement_account_id")
