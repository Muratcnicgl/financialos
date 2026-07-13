"""auth_user_fields_and_revoked_tokens

Revision ID: 380a9c1e7d8f
Revises: 26a17fda5b32
Create Date: 2026-07-13 19:35:42.803696

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '380a9c1e7d8f'
down_revision: Union[str, None] = '26a17fda5b32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # M11 (ADR-033): User auth alanları + revoked_tokens (logout blacklist).
    # NATIVE ADD COLUMN (batch DEĞİL): `users` tablosuna çok sayıda inbound FK var
    # (accounts/transactions/... .user_id). batch_alter_table table-recreate yapar →
    # foreign_keys=ON (BUG #060) altında DROP TABLE users FK ihlaliyle kırılır.
    # SQLite native ALTER TABLE ADD COLUMN recreate yapmaz, güvenli.
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("oauth_provider", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("oauth_sub", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("kvkk_consent_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("kvkk_consent_version", sa.String(length=20), nullable=True))
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "revoked_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_revoked_tokens_jti", "revoked_tokens", ["jti"], unique=True)
    op.create_index("ix_revoked_tokens_id", "revoked_tokens", ["id"])


def downgrade() -> None:
    op.drop_table("revoked_tokens")
    op.drop_index("ix_users_email", table_name="users")
    for col in ("is_active", "kvkk_consent_version", "kvkk_consent_at",
                "oauth_sub", "oauth_provider", "password_hash", "email"):
        op.drop_column("users", col)
