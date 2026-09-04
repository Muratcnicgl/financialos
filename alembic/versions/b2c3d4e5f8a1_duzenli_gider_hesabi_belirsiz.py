"""BUG #332: duzenli giderin hesabi BOS birakilabilir ("o an belli olur")

KULLANICI ISTEGI (4 Eyl 2026, birebir): "harcamalar kart mi nakit mi o anlik karar
verilen bir sey; secenek olarak onerirse eger bana sormali, varsayimla karta yada
nakite yazilmammalidir."

OLCULEN DURUM: `recurring_expenses.account_id` NOT NULL idi. Yani "sigara" gibi bazen
kartla bazen nakitle yapilan bir harcamayi sisteme girmek icin bir hesap SECMEK
gerekiyordu — ve o secim bir VARSAYIMDI. Asistan da bunu yapti (uc yasam giderini karta
bagladi); kullanici fark edip duzeltilmesini istedi.

NULL artik gecerli bir cevaptir: "bilmiyorum / o an belli olur". Nakit takviminde ne
cikisa ne karta sayilir, AYRI bir kovada gosterilir ve koc sorar. Saymamak yok saymak
degildir — iki yonde de varsayim yapmamak icin (nakit saymak sahte acik uretir, kart
saymak nakdi bol gosterir).

GERIYE UYUM: mevcut kayitlar dokunulmadan kalir (hepsinin hesabi dolu). Yalnizca
kisitlama gevser.

Revision ID: b2c3d4e5f8a1
Revises: a1b2c3d4e5f7
Create Date: 2026-09-04
"""
from alembic import op
import sqlalchemy as sa


revision = "b2c3d4e5f8a1"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("recurring_expenses") as batch_op:
        batch_op.alter_column("account_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # Geri alis, NULL tasiyan satirlar varsa BASARISIZ olur — bilincli: veriyi sessizce
    # bir hesaba atamaktansa gocun durmasi yeglenir (varsayim yasak).
    with op.batch_alter_table("recurring_expenses") as batch_op:
        batch_op.alter_column("account_id", existing_type=sa.Integer(), nullable=False)
