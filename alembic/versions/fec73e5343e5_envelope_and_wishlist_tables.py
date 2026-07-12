"""envelope_and_wishlist_tables

Revision ID: fec73e5343e5
Revises: f3dda4d3996d
Create Date: 2026-07-12 13:39:27.436764

ADR-013 uzlaşması (M1): Envelope (FEAT-001) ve WishlistItem (FEAT-032) tabloları
kalite-seruveni sprintinde `Base.metadata.create_all` ile eklendi, migration yazılmadı.
Bu migration o borcu kapatır — tablolar artık Alembic ile yönetiliyor.

İdempotent: canlı DB'de tablolar YOK (upgrade yaratır); create_all ile yaratılmış bir
DB'de tablolar VAR (inspector guard atlar). Böylece hem "tablosuz" hem "tablolu" DB'de
tek `alembic upgrade head` güvenli çalışır (charter M1.4 karar tablosu).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fec73e5343e5'
down_revision: Union[str, None] = 'f3dda4d3996d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if 'envelopes' not in existing:
        op.create_table(
            'envelopes',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('category', sa.String(length=50), nullable=False),
            sa.Column('monthly_amount', sa.Numeric(precision=14, scale=2), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('user_id', 'category', name='uq_envelope_user_category'),
        )
        op.create_index('ix_envelopes_id', 'envelopes', ['id'], unique=False)

    if 'wishlist_items' not in existing:
        op.create_table(
            'wishlist_items',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('item', sa.String(length=200), nullable=False),
            sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
            sa.Column('note', sa.Text(), nullable=True),
            sa.Column('status', sa.String(length=20), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('resolved_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_wishlist_items_id', 'wishlist_items', ['id'], unique=False)
        op.create_index('ix_wishlist_user_status', 'wishlist_items', ['user_id', 'status'], unique=False)


def downgrade() -> None:
    existing = set(sa.inspect(op.get_bind()).get_table_names())

    if 'wishlist_items' in existing:
        op.drop_index('ix_wishlist_user_status', table_name='wishlist_items')
        op.drop_index('ix_wishlist_items_id', table_name='wishlist_items')
        op.drop_table('wishlist_items')

    if 'envelopes' in existing:
        op.drop_index('ix_envelopes_id', table_name='envelopes')
        op.drop_table('envelopes')
