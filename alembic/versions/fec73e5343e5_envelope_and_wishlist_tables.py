"""fec73e5343e5_envelope_and_wishlist_tables (collapsed)

M1 non-destructive collapse (ADR-013 tam gerceklestirme): bu migration'in orijinal
create/alter islemleri artik b70779a2f621_genesis_full_schema (tek baseline) tarafindan
yapiliyor. Zincir surekliligi + canli DB alembic_version gecerliligi icin revizyon KORUNUR,
govde no-op'tur. Orijinal icerik git gecmisinde. Temiz DB: genesis her seyi yaratir; bunlar pass.
Canli DB: bu revizyonlari zaten calistirdi (eski govdeleriyle) -> yeniden CALISMAZ.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'fec73e5343e5'
down_revision: Union[str, None] = 'f3dda4d3996d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
