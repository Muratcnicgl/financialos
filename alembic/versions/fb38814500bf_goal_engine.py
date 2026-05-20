"""goal_engine

Revision ID: fb38814500bf
Revises: 53a3257f906c
Create Date: 2026-05-20 14:49:53.581865

H2G5 Goal Engine — ADR-024
3 yeni tablo: goals, goal_rules, goal_allocations

Pattern: Monarch Money Goals 3.0 (transaction-linked allocation)
Mevcut tablolara dokunulmaz — tamamen additive migration.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'fb38814500bf'
down_revision: Union[str, None] = '53a3257f906c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # goals
    op.create_table(
        'goals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('goal_type', sa.String(20), nullable=False),
        sa.Column('title', sa.String(200), nullable=False),
        sa.Column('target_amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('target_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('current_amount', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('progress_percent', sa.Numeric(5, 2), nullable=False, server_default='0'),
        sa.Column('projected_completion_date', sa.Date(), nullable=True),
        sa.Column('last_refreshed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('achieved_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_goals_goal_type', 'goals', ['goal_type'])
    op.create_index('ix_goals_status', 'goals', ['status'])

    # goal_rules — goal_allocations'tan ÖNCE (allocations'ın FK'si var)
    op.create_table(
        'goal_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('goal_id', sa.Integer(),
                  sa.ForeignKey('goals.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('criteria', sa.JSON(), nullable=False),
        sa.Column('allocation_type', sa.String(20), nullable=False),
        sa.Column('allocation_value', sa.Numeric(10, 2), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_goal_rules_goal_id', 'goal_rules', ['goal_id'])

    # goal_allocations
    op.create_table(
        'goal_allocations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('goal_id', sa.Integer(),
                  sa.ForeignKey('goals.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('transaction_id', sa.Integer(),
                  sa.ForeignKey('transactions.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('amount', sa.Numeric(14, 2), nullable=False),
        sa.Column('source', sa.String(20), nullable=False, server_default='manual'),
        sa.Column('rule_id', sa.Integer(),
                  sa.ForeignKey('goal_rules.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('goal_id', 'transaction_id', name='uq_goal_tx'),
    )
    op.create_index('ix_goal_allocations_goal_id', 'goal_allocations', ['goal_id'])
    op.create_index('ix_goal_allocations_transaction_id', 'goal_allocations', ['transaction_id'])


def downgrade() -> None:
    op.drop_index('ix_goal_allocations_transaction_id', table_name='goal_allocations')
    op.drop_index('ix_goal_allocations_goal_id', table_name='goal_allocations')
    op.drop_table('goal_allocations')
    op.drop_index('ix_goal_rules_goal_id', table_name='goal_rules')
    op.drop_table('goal_rules')
    op.drop_index('ix_goals_status', table_name='goals')
    op.drop_index('ix_goals_goal_type', table_name='goals')
    op.drop_table('goals')
