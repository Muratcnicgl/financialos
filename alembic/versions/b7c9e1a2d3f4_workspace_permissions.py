"""workspace + permissions (M40, ADR-036)

Revision ID: b7c9e1a2d3f4
Revises: 697027467ca8
Create Date: 2026-07-14 06:30:00.000000

M40 (ADR-036): Aile hesabı izin sistemi. workspaces + workspace_memberships tabloları
+ 12 finansal-defter tablosuna workspace_id (nullable, native ADD COLUMN — inbound FK'li
tablolar batch recreate'te kırılır, M11 dersi). NOT NULL'a çevirme backfill sonrası
`scripts/create_personal_workspaces.py` ile ayrı yapılır (canlı veri korunur).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7c9e1a2d3f4'
down_revision: Union[str, None] = '697027467ca8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# workspace_id eklenecek finansal-defter tabloları (ADR-036 K10 kapsamı).
# Koç/kişisel tablolar (coach_memories, coach_insights, reasoning_traces, api_call_log,
# action_history) KAPSAM DIŞI — viewer owner'ın özel AI verisini görmemeli.
_SCOPED_TABLES = [
    "accounts",
    "recurring_incomes",
    "recurring_expenses",
    "envelopes",
    "wishlist_items",
    "transactions",
    "personal_debts",
    "master_checkpoints",
    "pending_actions",
    "net_worth_snapshots",
    "goals",
    "decision_journal",
]


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_personal", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workspaces_id", "workspaces", ["id"])  # model: PK index=True
    op.create_index("ix_workspaces_owner_user_id", "workspaces", ["owner_user_id"])

    op.create_table(
        "workspace_memberships",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("workspace_id", sa.Integer(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False, server_default="viewer"),
        sa.Column("invited_by", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("joined_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("workspace_id", "user_id", name="uq_membership_workspace_user"),
    )
    op.create_index("ix_workspace_memberships_id", "workspace_memberships", ["id"])  # model: PK index=True
    op.create_index("ix_membership_user", "workspace_memberships", ["user_id"])

    # Native ADD COLUMN — FK constraint YOK: SQLite ALTER ile FK ekleyemez (batch recreate
    # inbound-FK'li tabloları kırar, M11 dersi). Model-seviyesi FK (ORM relationship) korunur;
    # fiziksel FK Blok D PostgreSQL geçişinde eklenir (ADR-013 divergence notu, asset_type deseni).
    for tbl in _SCOPED_TABLES:
        op.add_column(tbl, sa.Column("workspace_id", sa.Integer(), nullable=True))
        op.create_index(f"ix_{tbl}_workspace_id", tbl, ["workspace_id"])


def downgrade() -> None:
    for tbl in _SCOPED_TABLES:
        op.drop_index(f"ix_{tbl}_workspace_id", table_name=tbl)
        op.drop_column(tbl, "workspace_id")
    op.drop_index("ix_membership_user", table_name="workspace_memberships")
    op.drop_table("workspace_memberships")
    op.drop_index("ix_workspaces_owner_user_id", table_name="workspaces")
    op.drop_table("workspaces")
