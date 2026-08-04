"""BUG #194 (P3.5/H5): demo_data_markers — opsiyonel demo verinin tam silinebilirligi

Demo veri kullanicinin KENDI verisiyle karismamali ve tek tusla TAM silinebilmeli.
Is tablolarina is_demo kolonu eklemek yerine ayri isaretleyici tablo.

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-05
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "demo_data_markers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("table_name", sa.String(length=40), nullable=False),
        sa.Column("row_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_demo_data_markers_id", "demo_data_markers", ["id"])
    op.create_index("ix_demo_data_markers_user_id", "demo_data_markers", ["user_id"])
    op.create_index("ix_demo_marker_user_table", "demo_data_markers", ["user_id", "table_name"])


def downgrade() -> None:
    op.drop_index("ix_demo_marker_user_table", table_name="demo_data_markers")
    op.drop_index("ix_demo_data_markers_user_id", table_name="demo_data_markers")
    op.drop_index("ix_demo_data_markers_id", table_name="demo_data_markers")
    op.drop_table("demo_data_markers")
