"""BUG #195 (P5): error_logs — kendi kendine yeten hata izleme

Beklenmedik hatalar yalnizca log dosyasina dusuyordu; kapali betada operator log'u
surekli izleyemez -> hata sessizce yasar. Dis servis (Sentry) kullanici finansal
verisini ucuncu tarafa tasiyacagi icin tercih edilmedi.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-05
"""
from alembic import op
import sqlalchemy as sa

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "error_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fingerprint", sa.String(length=32), nullable=False),
        sa.Column("error_type", sa.String(length=80), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("path", sa.String(length=200), nullable=True),
        sa.Column("method", sa.String(length=10), nullable=True),
        sa.Column("traceback_tail", sa.Text(), nullable=True),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("last_user_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_error_logs_id", "error_logs", ["id"])
    op.create_index("ix_error_logs_fingerprint", "error_logs", ["fingerprint"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_error_logs_fingerprint", table_name="error_logs")
    op.drop_index("ix_error_logs_id", table_name="error_logs")
    op.drop_table("error_logs")
