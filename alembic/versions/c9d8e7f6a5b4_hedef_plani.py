"""UX-024 (BUG #479): goals.plan — benimsenen borç planı

OLCULEN DURUM (14 Eyl 2026): Borç Stratejisi paneli iki planı karşılaştırıyor ama hiçbirini
"benimsetmiyordu"; debt_freedom hedefinin tahmini bitişi ise her zaman Snowball/ekstra 0 ile
hesaplanıyordu — kullanıcı Avalanche + 1.500 TL ekstra planlasa bile hedef kartı başka bir
tarih gösteriyordu. `plan` sütunu seçimi hedefe bağlar; projeksiyon onu okur.

Revision ID: c9d8e7f6a5b4
Revises: f7a8b9c0d1e2
Create Date: 2026-09-14
"""
from alembic import op
import sqlalchemy as sa


revision = "c9d8e7f6a5b4"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("goals") as batch_op:
        batch_op.add_column(sa.Column("plan", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("goals") as batch_op:
        batch_op.drop_column("plan")
