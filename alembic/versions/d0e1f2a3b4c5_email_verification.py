"""BUG #202 (P8): users.email_verified_at — acik kayitta enumerasyonu kapatir

409 "bu e-posta zaten kayitli" yaniti kullanici listesi sizdirir. Gercek cozum:
kayit her durumda AYNI yaniti dondurur, hesap e-postadaki baglanti ile etkinlesir.

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-08-05
"""
from alembic import op
import sqlalchemy as sa

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(), nullable=True))
    # Mevcut kullanicilar dogrulanmis sayilir (geriye uyum: kimse kilitlenmez)
    op.execute("UPDATE users SET email_verified_at = created_at WHERE email IS NOT NULL")


def downgrade() -> None:
    op.drop_column("users", "email_verified_at")
