"""goal_engine_baseline

Revision ID: f3dda4d3996d
Revises: fb38814500bf
Create Date: 2026-05-20 15:03:07.968280

goals tablosuna iki alan ekle:
  - user_id  (FK → users.id, nullable — SQLite ALTER TABLE kısıtı)
  - baseline_amount  (Numeric 14,2, nullable — debt_freedom goal yaratım anı snapshot)

Ayrımlı migration nedeni (ADR-024):
  fb38814500bf = 3 tablo şeması (atomik)
  f3dda4d3996d = servis katmanının gerektirdiği ek alanlar (atomik)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3dda4d3996d'
down_revision: Union[str, None] = 'fb38814500bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('goals', sa.Column('user_id', sa.Integer(), nullable=True))
    op.add_column('goals', sa.Column('baseline_amount', sa.Numeric(14, 2), nullable=True))
    # SQLite ALTER TABLE ADD COLUMN'da FK constraint desteklenmez;
    # user_id değeri uygulama katmanında GoalCreate sırasında set edilir.


def downgrade() -> None:
    op.drop_column('goals', 'baseline_amount')
    op.drop_column('goals', 'user_id')
