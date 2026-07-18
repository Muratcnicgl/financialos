"""operation_name_enum_values_lowercase

reasoning_traces.operation_name: üye-ADI ("RULE_CHECK") → DEĞER ("rule_check") veri göçü
(P1-15 / BUG #146). Model'e values_callable eklendi; bu migration mevcut satırları hizalar.

M50 (Wave-7) DIALECT-AWARE: SQLite'ta enum düz VARCHAR → basit UPDATE. Postgres'te `operationname`
GERÇEK ENUM TİPİ → 'rule_check' değeri tipte yok, UPDATE `InvalidTextRepresentation` verir. Postgres'te
`ALTER TYPE ... RENAME VALUE 'RULE_CHECK' TO 'rule_check'` kullanılır (yerinde yeniden-adlandırma, satır
UPDATE'i gerekmez — mevcut satırlar otomatik yeni değeri yansıtır). İdempotent değil-ama-güvenli: RENAME
VALUE zaten-yeniden-adlandırılmışsa hata verir → pg_enum kontrolüyle atlanır.

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


def _pg_enum_has(bind, enum_name: str, label: str) -> bool:
    """Postgres enum tipinde bir label var mı (idempotent RENAME için)."""
    from sqlalchemy import text
    return bind.execute(text(
        "SELECT 1 FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid "
        "WHERE t.typname = :tn AND e.enumlabel = :lb"
    ), {"tn": enum_name, "lb": label}).scalar() is not None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Postgres: enum değerini YERİNDE yeniden adlandır (veri UPDATE'i gereksiz + güvenli).
        for name, value in _PAIRS:
            if _pg_enum_has(bind, "operationname", name) and not _pg_enum_has(bind, "operationname", value):
                op.execute(f"ALTER TYPE operationname RENAME VALUE '{name}' TO '{value}'")
    else:
        # SQLite/diğer: enum düz VARCHAR → satır UPDATE (idempotent, WHERE ile).
        for name, value in _PAIRS:
            op.execute(
                f"UPDATE reasoning_traces SET operation_name = '{value}' "
                f"WHERE operation_name = '{name}'"
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for name, value in _PAIRS:
            if _pg_enum_has(bind, "operationname", value) and not _pg_enum_has(bind, "operationname", name):
                op.execute(f"ALTER TYPE operationname RENAME VALUE '{value}' TO '{name}'")
    else:
        for name, value in _PAIRS:
            op.execute(
                f"UPDATE reasoning_traces SET operation_name = '{name}' "
                f"WHERE operation_name = '{value}'"
            )
