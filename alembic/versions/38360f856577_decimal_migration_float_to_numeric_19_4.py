"""decimal_migration_float_to_numeric_19_4

Para alanları Float -> Numeric(19,4) (ADR-030 / M5). SADECE para kolonları — oran
(interest_rate), miktar (lot_count), skor (confidence_score) Float KALIR (OTONOM KARAR
kategori-c: körlemesine sweep semantik yanlış olurdu). Faz C (batch_alter_table, N2 —
postgresql_using YOK) + Faz D (mevcut REAL değerleri ROUND(4) ile temizle).

Revision ID: 38360f856577
Revises: fec73e5343e5
Create Date: 2026-07-12 17:23:01.351439
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '38360f856577'
down_revision: Union[str, None] = 'fec73e5343e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (tablo, [(kolon, nullable), ...]) — 20 para kolonu, 6 tablo. ADR-030 kararı.
MONEY_COLUMNS = {
    "accounts": [
        ("balance", False), ("credit_limit", True), ("monthly_payment", True),
        ("cost_per_lot", True), ("current_price", True),
    ],
    "recurring_incomes": [("amount", False)],
    "recurring_expenses": [("amount", False)],
    "transactions": [("amount", False)],
    "personal_debts": [("amount", False)],
    "action_history": [
        ("net_worth_before", True), ("net_worth_after", True),
        ("cash_before", True), ("cash_after", True),
    ],
    "net_worth_snapshots": [
        ("net_worth_seen", False), ("net_worth_full", False), ("cash", False),
        ("card_debt", False), ("loan_debt", False), ("investment_value", False),
        ("receivables", False),
    ],
}


def upgrade() -> None:
    # Faz C — tip değişimi (batch_alter_table; SQLite ALTER emülasyonu)
    for table, cols in MONEY_COLUMNS.items():
        with op.batch_alter_table(table) as batch_op:
            for col, nullable in cols:
                batch_op.alter_column(
                    col, existing_type=sa.Float(),
                    type_=sa.Numeric(19, 4), existing_nullable=nullable,
                )
    # Faz D — mevcut REAL binary-float değerleri 4 ondalığa temizle (precision kaybı düzelt)
    for table, cols in MONEY_COLUMNS.items():
        for col, _ in cols:
            op.execute(f"UPDATE {table} SET {col} = ROUND({col}, 4) WHERE {col} IS NOT NULL")


def downgrade() -> None:
    for table, cols in MONEY_COLUMNS.items():
        with op.batch_alter_table(table) as batch_op:
            for col, nullable in cols:
                batch_op.alter_column(
                    col, existing_type=sa.Numeric(19, 4),
                    type_=sa.Float(), existing_nullable=nullable,
                )
