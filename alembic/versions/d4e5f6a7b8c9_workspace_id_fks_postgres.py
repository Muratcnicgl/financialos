"""workspace_id foreign key'leri (Postgres) — ADR-036 "Blok D'de eklenir" sözü

M50 (Wave-7) DIALECT-AWARE: ADR-036 (M40) workspace_id kolonlarını `b7c9e1a2d3f4` migration'ında
FİZİKSEL FK'siz ekledi — gerekçe: "SQLite ALTER ile FK ekleyemez (batch recreate inbound-FK'li
tabloları kırar, M11 dersi); fiziksel FK Blok D PostgreSQL geçişinde eklenir". Model-seviyesi FK
(ORM relationship) zaten vardı. Bu wave (Wave-7) o sözü yerine getirir:
- **Postgres:** 12 scoped tabloya `workspace_id → workspaces.id` fiziksel FK ekler → `alembic check` temizlenir.
- **SQLite:** SKIP (ALTER ADD FK yapamaz; model-FK + uygulama-scope (Wave-5 AST) + Postgres RLS (M51) yeterli).
  SQLite'ta `alembic check` bu FK-sapmasını göstermeye devam eder — BELGELENMİŞ ADR-036/ADR-013 divergence.

Revision ID: d4e5f6a7b8c9
Revises: c1d2e3f4a5b6
Create Date: 2026-07-18
"""
from typing import Sequence, Union

from alembic import op


revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# workspace_id'yi b7c9e1a2d3f4'te FK'siz ADD COLUMN ile alan 12 scoped tablo.
# (workspace_memberships kendi create_table'ında FK'li → burada YOK.)
_SCOPED_TABLES = [
    "accounts", "transactions", "goals", "master_checkpoints", "net_worth_snapshots",
    "pending_actions", "personal_debts", "recurring_expenses", "recurring_incomes",
    "wishlist_items", "decision_journal", "envelopes",
]


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return  # SQLite/diğer: no-op (belgelenmiş ADR-036 divergence)
    for tbl in _SCOPED_TABLES:
        op.create_foreign_key(
            f"fk_{tbl}_workspace_id", tbl, "workspaces",
            ["workspace_id"], ["id"],
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for tbl in _SCOPED_TABLES:
        op.drop_constraint(f"fk_{tbl}_workspace_id", tbl, type_="foreignkey")
