"""BUG #182 (P2): rate_limit_hits — paylasilan (cok-worker guvenli) rate limit sayaci

Eskiden sayaclar process-yerel bellekte tutuluyordu: gunicorn --workers 2+ ile ilan
edilen limit worker sayisi kadar katlaniyor, her restart sayaci sifirliyordu.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-05
"""
from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_hits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("bucket_key", sa.String(length=160), nullable=False),
        sa.Column("hit_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_rate_limit_hits_id", "rate_limit_hits", ["id"])
    op.create_index("ix_rate_limit_hits_bucket_key", "rate_limit_hits", ["bucket_key"])
    op.create_index("ix_rate_limit_hits_hit_at", "rate_limit_hits", ["hit_at"])
    op.create_index("ix_rate_limit_key_time", "rate_limit_hits", ["bucket_key", "hit_at"])


def downgrade() -> None:
    op.drop_index("ix_rate_limit_key_time", table_name="rate_limit_hits")
    op.drop_index("ix_rate_limit_hits_hit_at", table_name="rate_limit_hits")
    op.drop_index("ix_rate_limit_hits_bucket_key", table_name="rate_limit_hits")
    op.drop_index("ix_rate_limit_hits_id", table_name="rate_limit_hits")
    op.drop_table("rate_limit_hits")
