"""BUG #192 (P3.5/H3): master_checkpoints.rule_type + rule_params — kullanici-tanimli kurallar

Kullanicinin yazdigi kirmizi cizgi eskiden yalnizca koca TAVSIYE olarak gidiyordu.
Bu iki alan doldurulunca kural, aksiyon uygulanmadan ONCE kod seviyesinde dayatilir
(app/user_rules.py) — urunun sabit kurallari (MC1/emanet) kadar sert.

Revision ID: e5f6a7b8c9d0
Revises: c3d4e5f6a7b8
Create Date: 2026-08-05
"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("master_checkpoints", sa.Column("rule_type", sa.String(length=40), nullable=True))
    op.add_column("master_checkpoints", sa.Column("rule_params", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("master_checkpoints", "rule_params")
    op.drop_column("master_checkpoints", "rule_type")
