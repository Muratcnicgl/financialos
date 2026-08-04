"""BUG #203 (P5.3): scheduler_runs — cron calisti mi GORUNUR olsun

Zamanlanmis isler yalnizca log'a yaziyordu; bir is sessizce olurse (servis ayakta ama
job patliyor) haftalarca fark edilmezdi: fiyatlar bayatlar, gece batch'i insight uretmez.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-08-05
"""
from alembic import op
import sqlalchemy as sa

revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduler_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_name", sa.String(length=60), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=True),
        sa.Column("detail", sa.String(length=300), nullable=True),
    )
    op.create_index("ix_scheduler_runs_id", "scheduler_runs", ["id"])
    op.create_index("ix_scheduler_runs_job_name", "scheduler_runs", ["job_name"])


def downgrade() -> None:
    op.drop_index("ix_scheduler_runs_job_name", table_name="scheduler_runs")
    op.drop_index("ix_scheduler_runs_id", table_name="scheduler_runs")
    op.drop_table("scheduler_runs")
