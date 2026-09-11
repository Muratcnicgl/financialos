"""BUG #408 (OBS-020 / SEC-024): denetim izi tablosu — finansal kaydin guncelleme/silme izi

OLCULEN DURUM: `ActionHistory` yalniz koc aksiyonlarini tutuyordu; panelden yapilan bir
DELETE ya da PUT (hesap silme, bakiye duzeltme, borc kapama) hicbir yerde kalmiyordu.
KVKK m.12 hesap verebilirligi ve "bu bakiye neden boyle?" sorusu icin kaynak yoktu.

Tablo ekle-yalnizdir; ORM flush kancasi yazar (app/denetim.py), router'lar dokunmaz.
`user_id` tasir: hesap silinince KVKK yoluyla birlikte gider. Saklama 365 gun.

Revision ID: e6f7a8b9c0d1
Revises: c3d4e5f8a1b2
Create Date: 2026-09-12
"""
from alembic import op
import sqlalchemy as sa


revision = "e6f7a8b9c0d1"
down_revision = "c3d4e5f8a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    postgres = op.get_bind().dialect.name == "postgresql"
    # workspace_id FK: yeni tabloda SQLite de CREATE TABLE icinde FK kurabilir (ADR-036'nin
    # kisiti ALTER ADD CONSTRAINT'tir) — sapma ratchet'i buyumesin; Postgres'te ise depo
    # deseni geregi ADLI FK sonradan kurulur (fk_<tablo>_workspace_id, b4c5d6e7f8a9 gibi).
    ws_fk = () if postgres else (sa.ForeignKey("workspaces.id", ondelete="SET NULL"),)
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.Integer(), *ws_fk, nullable=True),
        sa.Column("entity", sa.String(length=40), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=10), nullable=False),
        sa.Column("before_json", sa.Text(), nullable=True),
        sa.Column("after_json", sa.Text(), nullable=True),
        sa.Column("istek_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_log_id", "audit_log", ["id"])
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    # Silinen workspace'in izi kalsin diye ON DELETE SET NULL.
    if postgres:
        op.create_foreign_key(
            "fk_audit_log_workspace_id", "audit_log", "workspaces",
            ["workspace_id"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.drop_constraint("fk_audit_log_workspace_id", "audit_log", type_="foreignkey")
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_index("ix_audit_log_user_id", table_name="audit_log")
    op.drop_index("ix_audit_log_id", table_name="audit_log")
    op.drop_table("audit_log")
