"""BUG #318: kredinin ERKEN KAPAMA tutari sayisal alan degildi, serbest metindeydi

OLCULEN DEFEKT (2 Eyl 2026, altin senaryo G1):
Bir kredinin IKI ayri sayisi vardir ve bunlar birbirine karistirilirsa kullanici yanlis
karar verir:
  * `balance`            = KALAN TAKSIT TOPLAMI (gelecek faizi de icerir)
  * "Erken Kapama Tutari" = bugun kapatirsan odeyecegin ANAPARA

Urun bugune kadar yalniz birincisini sayi olarak tutuyordu; ikincisi `notes` icinde
serbest METIN olarak yaziliyordu ("Erken Kapama: 14.023,29 TL."). Iki somut zarar olctuk:

1. KOC YANLIS TAVSIYE VERDI. "Iki kredimi bugun kapatsam ne oderim?" sorusuna koc
   **79.625,85 TL** dedi; dogrusu 48.510,41 TL (14.023,29 + 34.487,12). Yani kullaniciya
   **31.115,44 TL fazla odeme** tavsiye edildi. Model `balance`i kapama bedeli sandi —
   cunku cockpit'te kapama bedeli diye bir SAYI yoktu.

2. URUN, DOGRU CEVABI CEZALANDIRIYORDU. Koc `notes`u okuyup dogru tutari soylese bile
   grounding dogrulamasi o sayiyi cockpit'in sayisal yapraklarinda bulamaz ve
   "izlenemeyen tutar" (halusinasyon suphesi) damgasi basardi. Yani dogru davranan koc
   cezalandiriliyordu. Bu yuzden altin senaryo setinde `grounded` kriteri kullanilamiyordu.

CARE: alan sayisallasir. `notes` serbest metin olarak kalir ama artik KARAR VERDIREN bir
sayiyi tasimaz — serbest metin bir veri modeli degildir.

NULLABLE ve GERIYE DONUK DOLDURULMAZ: mevcut kredilerin gercek kapama tutarini yalniz
banka bilir; `notes`tan ayristirip "hesaplanmis gibi" yazmak, olcmedigimiz bir sayiyi
dogruymus gibi sunmak olurdu (varsayim yasak). Alan bos kalir, kullanici girer; bos
oldugunda urun "bilmiyorum" der — sifir varsaymaz (L45).

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-09-02
"""
from alembic import op
import sqlalchemy as sa


revision = "f8a9b0c1d2e3"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.add_column(sa.Column("early_payoff_amount", sa.Numeric(19, 4), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_column("early_payoff_amount")
