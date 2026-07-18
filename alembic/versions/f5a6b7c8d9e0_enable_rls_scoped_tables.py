"""Row-Level Security (Postgres) — workspace_id izolasyonu 2. savunma katmanı

M51 (Wave-7) POSTGRES-ÖZEL. B23e: workspace izolasyonunun TEK koruması uygulama katmanı
(scope_filter/_scope, Wave-5 AST tarayıcı ile kilitli). RLS = **ikinci, DB-katmanı savunma**:
uygulama filtresi bypass edilse (ham SELECT) bile Postgres yanlış workspace satırını döndürmez.

TASARIM (opt-in 2. savunma):
- 12 scoped tabloda ENABLE + FORCE ROW LEVEL SECURITY (FORCE → tablo sahibi de RLS'e tabi;
  yalnız superuser bypass eder).
- Policy `ws_isolation`: workspace context (`app.current_workspace_id` GUC) SET edilmişse
  `workspace_id = <o değer>` satırları görünür; SET edilmemişse (NULL/'') TÜM satırlar (app-katmanı
  filtresi birincil kalır — legacy/admin/migration sorguları kırılmaz).
- Uygulama Postgres'te `SET app.current_workspace_id = <ws>` yaparsa DB bağımsız dayatır (bkz.
  app/database.py Postgres workspace-context hook, M51).

SQLite: no-op (RLS yok; app-katmanı scope tek savunma, hibrit dev).

Revision ID: f5a6b7c8d9e0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-18
"""
from typing import Sequence, Union

from alembic import op


revision: str = "f5a6b7c8d9e0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCOPED_TABLES = [
    "accounts", "transactions", "goals", "master_checkpoints", "net_worth_snapshots",
    "pending_actions", "personal_debts", "recurring_expenses", "recurring_incomes",
    "wishlist_items", "decision_journal", "envelopes",
]

# context SET edilmişse enforce, edilmemişse (NULL/'') tüm satırlar (app-katmanı birincil).
_POLICY_USING = (
    "nullif(current_setting('app.current_workspace_id', true), '') IS NULL "
    "OR workspace_id = nullif(current_setting('app.current_workspace_id', true), '')::int"
)


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return  # SQLite: RLS yok (hibrit dev)
    for tbl in _SCOPED_TABLES:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY ws_isolation ON {tbl} USING ({_POLICY_USING})")


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for tbl in _SCOPED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS ws_isolation ON {tbl}")
        op.execute(f"ALTER TABLE {tbl} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY")
