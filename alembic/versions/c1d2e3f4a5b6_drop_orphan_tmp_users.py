"""drop orphan _alembic_tmp_users (BUG #159, M65)

Revision ID: c1d2e3f4a5b6
Revises: b7c9e1a2d3f4
Create Date: 2026-07-17 02:10:00.000000

M65 (BUG #159): canlı DB'de `_alembic_tmp_users` yetim tablosu — M11 auth migration'ının
başarısız batch_alter_table denemesinden kalma (0 satır, modelde+migration'da yok). Şema
kirliliği + gelecekteki users batch işlemini bozabilir. `DROP TABLE IF EXISTS` ile temizlenir
(temiz DB'de yok → no-op; fresh-db migration testi bozulmaz).
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'c1d2e3f4a5b6'
down_revision: Union[str, None] = 'b7c9e1a2d3f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF EXISTS: canlı DB'de düşür, temiz DB'de sessizce atla (yetim, geri-yaratılmaz)
    op.execute("DROP TABLE IF EXISTS _alembic_tmp_users")


def downgrade() -> None:
    # Yetim tabloyu geri yaratmıyoruz (zaten hatalı bir artıktı).
    pass
