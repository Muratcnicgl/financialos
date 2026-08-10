"""BUG #274 (LLM-006/OBS-005): api_call_log'a est_cost_usd + amac

Defterin docstring'i "maliyet analizi icin veri kaynagi" diyor, sema `tokens_in`/`tokens_out`
tasiyor — ama olcum 13 gercek saglayici isteginin 13'unde de token'in NULL oldugunu gosterdi.
Para sutunu hic yoktu; amac ise `model` sutununu isgal ediyordu (`model='premortem'`,
`model='reflection'`) ve calisan modeli eziyordu.

Bu goc IKI SUTUN EKLER, mevcut satirlarin provider/model degerlerini DEGISTIRMEZ:
- `est_cost_usd`: yazma anindaki liste fiyatiyla dondurulmus TAHMINI maliyet (app/llm_cost).
  NULL = "bilinmiyor" (fiyat tablosunda yok / saglayici usage donmedi), 0 DEGIL.
- `amac`: cagriyi hangi urun yolu yapti — 'koc' | 'premortem' | 'yansima'.

Geriye donuk `amac` doldurulur (etiketi `model` sutununda tasiyan eski satirlardan turetilir).
Eski satirlarin bozuk `model`/`provider` degerleri KASTEN duzeltilmez: gercek model geriye
donuk bilinemez, uydurmak defteri kirletir. O satirlar fiyat tablosunda eslesmedigi icin
operator raporunda "fiyati bilinmeyen" olarak gorunur — sessiz sifir degil.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-08-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("api_call_log") as batch_op:
        batch_op.add_column(sa.Column("est_cost_usd", sa.Numeric(12, 6), nullable=True))
        batch_op.add_column(sa.Column("amac", sa.String(20), nullable=True))

    # Geriye donuk amac: etiket eskiden `model` sutununda tasiniyordu (tarihsel deger).
    conn = op.get_bind()
    conn.execute(text("UPDATE api_call_log SET amac = 'premortem' WHERE model = 'premortem'"))
    conn.execute(text("UPDATE api_call_log SET amac = 'yansima' WHERE model = 'reflection'"))
    conn.execute(text("UPDATE api_call_log SET amac = 'koc' WHERE amac IS NULL"))


def downgrade() -> None:
    with op.batch_alter_table("api_call_log") as batch_op:
        batch_op.drop_column("amac")
        batch_op.drop_column("est_cost_usd")
