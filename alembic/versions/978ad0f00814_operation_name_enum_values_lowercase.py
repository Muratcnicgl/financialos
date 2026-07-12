"""operation_name_enum_values_lowercase

reasoning_traces.operation_name: üye-ADI ("RULE_CHECK") → DEĞER ("rule_check") veri göçü
(P1-15 / BUG #146). Model'e values_callable eklendi; bu migration mevcut satırları hizalar.
Şema DEĞİŞMEZ (kolon VARCHAR(12), CHECK yok) — yalnızca veri UPDATE. İdempotent (WHERE ile).

Revision ID: 978ad0f00814
Revises: 38360f856577
Create Date: 2026-07-13 01:17:56.533688
"""
from typing import Sequence, Union

from alembic import op


revision: str = '978ad0f00814'
down_revision: Union[str, None] = '38360f856577'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (üye_adı, değer) — OperationName enum. values_callable öncesi DB'ye SOL yazılıyordu.
_PAIRS = [
    ("RULE_CHECK", "rule_check"),
    ("LLM_CALL", "llm_call"),
    ("EXECUTE_TOOL", "execute_tool"),
    ("OBSERVATION", "observation"),
    ("FINAL_ANSWER", "final_answer"),
]


def upgrade() -> None:
    for name, value in _PAIRS:
        op.execute(
            f"UPDATE reasoning_traces SET operation_name = '{value}' "
            f"WHERE operation_name = '{name}'"
        )


def downgrade() -> None:
    for name, value in _PAIRS:
        op.execute(
            f"UPDATE reasoning_traces SET operation_name = '{name}' "
            f"WHERE operation_name = '{value}'"
        )
