"""BUG #172 (P2): users.token_version — oturum geçersizleme sayacı

Şifre sıfırlama/değişiminde sayaç artar; token'ların taşıdığı `tv` claim'i eşleşmeyen
TÜM access/refresh token'lar reddedilir. Eskiden çalınmış 30 günlük refresh token, kurban
şifresini değiştirdikten SONRA da çalışıyordu (hesap geri alınamıyordu).

Zaman-çıpası yerine sayaç: JWT `iat` saniye hassasiyetinde olduğundan, sıfırlama ile aynı
saniyede üretilen YENİ token da yanlışlıkla reddediliyordu.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-04
"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # server_default="0": mevcut satırlar 0 alır (eski token'lar tv=0 ile uyumlu kalır).
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False,
                                     server_default="0"))


def downgrade() -> None:
    op.drop_column("users", "token_version")
