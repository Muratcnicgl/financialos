"""BUG #330: kart asgari odeme orani koda gomuluydu ve yanlisti

OLCULEN DEFEKT (4 Eyl 2026, gercek para karari): koc, kullanicinin 14 Eylul'de karta ne
kadar odeyecegine dair asgariyi `debt_strategy.MIN_CARD_PAYMENT_RATIO = 0.25` SABITINDEN
hesapladi:

    8.221,13 x %25 = 2.055,28   <- kullaniciya SOYLENEN
    8.221,13 x %20 = 1.644,23   <- BANKANIN EKRANINDA YAZAN

411,06 TL fazla. Kullanici bankadan bakip duzeltti ("asgari tutardan kalan borc 1644.23
diyo sen yanlis mi olctun"). Bir KOD VARSAYIMI olcum sanilmisti.

Asgari oran tek bir sabit olamaz: bankaya, kartin limitine ve yasina gore degisir (BDDK
duzenlemesi). `interest_rate` gibi HESABIN ozelligidir.

NULLABLE ve GERIYE DONUK DOLDURULMAZ: her kartin gercek orani yalniz o bankada bellidir;
varsayilan bir oran yazmak, olcmedigimiz bir sayiyi dogruymus gibi sunmak olurdu (varsayim
yasak). Alan bos kalir ve kod bilinen yedege duser — yani davranis DEGISMEZ, yalniz gercek
oran girilebilir hale gelir.

Revision ID: a1b2c3d4e5f7
Revises: f8a9b0c1d2e3
Create Date: 2026-09-04
"""
from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f7"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.add_column(sa.Column("min_payment_ratio", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_column("min_payment_ratio")
