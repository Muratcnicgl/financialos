"""P3.3 (BUG #262): users.onboarding_dismissed_at — ilk-kurulum rehberi gizleme

Rehber 4 adim tamamlaninca kendini emekliye ayirir; bu alan "bitirmeden kapat" diyen
kullaniciyi hatirlar (cihazdan bagimsiz). NULL = rehber gorunur (geriye uyum: mevcut
tum kullanicilar rehberi gorur, ki dogru davranis budur).

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-08-07
"""
from alembic import op
import sqlalchemy as sa

revision = "a3b4c5d6e7f8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("onboarding_dismissed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "onboarding_dismissed_at")
