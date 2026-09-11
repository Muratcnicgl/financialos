"""BUG #418 (PERF-010): sik filtrelenen FK sutunlarina indeks

OLCULEN DURUM (12 Eyl 2026): 16 FK sutunu tekil indekssiz. Yedisi her istekte filtre/join
kolonu: bes tablonun `user_id`'si (categories, envelopes, goals, recurring_incomes,
recurring_expenses — her sorgu kullanici filtresiyle baslar), `recurring_expenses.account_id`
(nakit takvimi hesap birlestirmesi) ve `audit_log.workspace_id`. Kalan dokuzu dusuk trafikli
tarihsel baglantilar (parent_step_id, reverted_by_action_id, invited_by...) — bilerek
dokunulmadi; kapi sayiyi ratchet'ler (tests/test_fk_indeks_kapisi.py).

Bugunku olcekte (tek kullanici, yuzlerce satir) hiz farki olculemez; bu bir hijyen ve
cok-kullanicili buyume onlemidir — maliyeti sifira yakin, geri alinabilir.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-09-12
"""
from alembic import op


revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None

INDEKSLER = (
    ("ix_categories_user_id", "categories", "user_id"),
    ("ix_envelopes_user_id", "envelopes", "user_id"),
    ("ix_goals_user_id", "goals", "user_id"),
    ("ix_recurring_incomes_user_id", "recurring_incomes", "user_id"),
    ("ix_recurring_expenses_user_id", "recurring_expenses", "user_id"),
    ("ix_recurring_expenses_account_id", "recurring_expenses", "account_id"),
    ("ix_audit_log_workspace_id", "audit_log", "workspace_id"),
)


def upgrade() -> None:
    for ad, tablo, kolon in INDEKSLER:
        op.create_index(ad, tablo, [kolon])


def downgrade() -> None:
    for ad, tablo, _ in reversed(INDEKSLER):
        op.drop_index(ad, table_name=tablo)
