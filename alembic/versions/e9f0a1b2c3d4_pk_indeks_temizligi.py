"""PERF-011 (BUG #491): birincil anahtar üstündeki gereksiz ikinci indeksler kaldırıldı

OLCULEN DURUM (14 Eyl 2026): 29 tabloda `id = Column(Integer, primary_key=True, index=True)`
— SQLAlchemy her biri için PK'nın yanına bir de `ix_<tablo>_id` indeksi üretiyordu (canlı
SQLite'ta 29 adet ölçüldü). PK zaten benzersiz indekstir (SQLite rowid / PostgreSQL btree);
ikinci indeks her INSERT/DELETE'te fazladan yazma, hiç okuma kazancı yok. Modelden `index=True`
kaldırıldı; bu göç var olan indeksleri düşürür (yoksa sessiz geçer — eski DB'ler farklı olabilir).

Revision ID: e9f0a1b2c3d4
Revises: c9d8e7f6a5b4
Create Date: 2026-09-14
"""
from alembic import op
from sqlalchemy import inspect


revision = "e9f0a1b2c3d4"
down_revision = "c9d8e7f6a5b4"
branch_labels = None
depends_on = None

TABLOLAR = ['accounts', 'action_history', 'api_call_log', 'audit_log', 'beta_invites', 'categories', 'coach_insights', 'coach_memories', 'decision_journal', 'demo_data_markers', 'envelopes', 'error_logs', 'feedback', 'goal_allocations', 'goal_rules', 'goals', 'master_checkpoints', 'net_worth_snapshots', 'pending_actions', 'personal_debts', 'rate_limit_hits', 'reasoning_traces', 'recurring_expenses', 'recurring_incomes', 'revoked_tokens', 'scheduler_runs', 'transactions', 'users', 'wishlist_items', 'workspace_memberships', 'workspaces']


def _var(tablo: str, ad: str) -> bool:
    insp = inspect(op.get_bind())
    if tablo not in insp.get_table_names():
        return False
    return any(ix["name"] == ad for ix in insp.get_indexes(tablo))


def upgrade() -> None:
    for tablo in TABLOLAR:
        ad = f"ix_{tablo}_id"
        if _var(tablo, ad):
            op.drop_index(ad, table_name=tablo)


def downgrade() -> None:
    insp = inspect(op.get_bind())
    for tablo in TABLOLAR:
        ad = f"ix_{tablo}_id"
        if tablo in insp.get_table_names() and not _var(tablo, ad):
            op.create_index(ad, tablo, ["id"])
