"""BUG #199 (P7): beta_invites — kapali beta davet kodu

Kayit ucu herkese acikti; domain canliya cikar cikmaz baglantiyi bilen herkes
hesap acabilirdi. Kapali beta bir IDDIA degil, KONTROL olmali.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-08-05
"""
from alembic import op
import sqlalchemy as sa

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "beta_invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("used_by_user_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_beta_invites_id", "beta_invites", ["id"])
    op.create_index("ix_beta_invites_code", "beta_invites", ["code"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_beta_invites_code", table_name="beta_invites")
    op.drop_index("ix_beta_invites_id", table_name="beta_invites")
    op.drop_table("beta_invites")
