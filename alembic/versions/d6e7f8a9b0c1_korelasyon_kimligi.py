"""BUG #280 (B3): error_logs'a last_istek_id (korelasyon kimligi)

Kapali betada davetli "bir seyler patladi" der; operatorun elinde o ANI bulacak tutamak
yoktu. Log dosyasinda binlerce satir, `error_logs`'ta parmak-izine gore BIRLESTIRILMIS
kayitlar ve kullanicida yalniz "Beklenmedik bir hata olustu." cumlesi vardi.

Bu goc TEK SUTUN ekler: kullanicinin ekranda gordugu korelasyon kimligi. Kayit parmak
izine gore birlestigi icin saklanan SON istegin kimligidir — `last_user_id` ile ayni
konvansiyon. Daha eski kimlikler DB'de degil LOG'da bulunur (zincirin kalici ucu log,
ozet ucu bu satirdir).

Geriye donuk doldurma YAPILMAZ: eski hatalarin kimligi gercekte hic uretilmedi. NULL
burada "bilinmiyor" demektir ve uydurulmus bir deger, bilinmeyenden zararlidir (L45).

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-08-11
"""
from alembic import op
import sqlalchemy as sa


revision = "d6e7f8a9b0c1"
down_revision = "c5d6e7f8a9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("error_logs") as batch_op:
        batch_op.add_column(sa.Column("last_istek_id", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("error_logs") as batch_op:
        batch_op.drop_column("last_istek_id")
