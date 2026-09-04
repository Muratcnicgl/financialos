"""BUG #337: kartin SON EKSTRE borcu sayisal alan degildi

OLCULEN DEFEKT (bir bankanin kart ekrani, 4 Eyl 2026):
    Son Ekstreden Kalan Borc : 8.221,13   <- ASGARI BUNUN yuzdesidir
    Guncel Borc              : 8.338,13   <- `balance` bu (veri modeli kurali, dogru)
Asgari odeme ekstre borcunun %20'sidir: 8.221,13 x %20 = 1.644,23 (bankanin ekraninda
yazan). Urun `balance` kullandigi icin 1.667,63 hesapliyordu — 23,40 TL fark. Bugun
kucuk, ama YON yanlis: ekstre kesildikten sonra yapilan her harcama asgariyi oldugundan
buyuk gosterir.

Bu, BUG #318'in ayni sinifi: bir hesabin karar verdiren IKI sayisi varsa ikisi de
SAYISAL alan olmalidir (kredide balance <-> early_payoff_amount; kartta balance <->
statement_balance).

NULLABLE ve GERIYE DONUK DOLDURULMAZ: ekstre borcunu yalniz banka bilir; `balance`ten
turetmek olcmedigimiz bir sayiyi dogruymus gibi sunmak olurdu (varsayim yasak). Bos
kalirsa kod `balance`e duser — davranis DEGISMEZ.

Revision ID: c3d4e5f8a1b2
Revises: b2c3d4e5f8a1
Create Date: 2026-09-04
"""
from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f8a1b2"
down_revision = "b2c3d4e5f8a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.add_column(sa.Column("statement_balance", sa.Numeric(19, 4), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_column("statement_balance")
