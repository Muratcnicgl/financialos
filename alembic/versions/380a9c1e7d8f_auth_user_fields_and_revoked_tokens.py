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
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("email", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("password_hash", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("oauth_provider", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("oauth_sub", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("kvkk_consent_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("kvkk_consent_version", sa.String(length=20), nullable=True))
        batch_op.add_column(
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1"))
        )
        # name artık nullable (OAuth kullanıcı) — SQLite batch ile yeniden oluşturur
        batch_op.alter_column("name", existing_type=sa.String(length=100), nullable=True)
        batch_op.create_index("ix_users_email", ["email"], unique=True)

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
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_index("ix_users_email")
        batch_op.drop_column("is_active")
        batch_op.drop_column("kvkk_consent_version")
        batch_op.drop_column("kvkk_consent_at")
        batch_op.drop_column("oauth_sub")
        batch_op.drop_column("oauth_provider")
        batch_op.drop_column("password_hash")
        batch_op.drop_column("email")
