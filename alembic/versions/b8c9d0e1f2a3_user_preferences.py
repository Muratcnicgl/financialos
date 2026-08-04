"""H4 (BUG #197): users.timezone / currency / locale — kullanici tercihleri

Uygulama "bugun"u SUNUCU yerel saatinden hesapliyordu; farkli saat diliminde yasayan
kullanici icin islem tarihi / gunluk limit / ay siniri yanlis gune dusuyordu.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-08-05
"""
from alembic import op
import sqlalchemy as sa

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("timezone", sa.String(length=40), nullable=True))
    op.add_column("users", sa.Column("currency", sa.String(length=3), nullable=True))
    op.add_column("users", sa.Column("locale", sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "locale")
    op.drop_column("users", "currency")
    op.drop_column("users", "timezone")
