"""BUG #281 (B2): feedback'e TESHIS alanlari (surum + korelasyon kimligi + istemci)

FEAT-033 geri bildirimi topluyordu (kim, ne zaman, hangi sekme, ne yazdi) ama
"HANGI KOD KOSUYORDU ve o an NE PATLADI" sorusunu cevaplamiyordu. Kapali betada bir
geri bildirim ancak teshis edilebilirse ise yarar; edilemeyen geri bildirim gurultudur.

Eklenen sabit alan kumesi (fazlasi GIRMEZ — gizlilik siniri B2.3'te yazili):
- `app_version`   : SUNUCUDAN turetilir (app/version.py). Istemcinin beyani degil.
- `istek_id`      : kullanicinin ekranda gordugu korelasyon kimligi (BUG #280).
                    Istemciden gelir ama beta_access/correlation ile AYNI temizleyiciden
                    gecer — dogrudan yazilmaz.
- `viewport_w`    : ekran genisligi (390px sinifi mi, masaustu mu — L29'un veri tarafi).
- `tarayici`      : User-Agent'tan SUNUCUDA turetilen kisa aile adi (ham UA saklanmaz:
                    parmak izi yuzeyi, KVKK).
- `pwa`           : ana ekrana eklenmis uygulamadan mi geldi.

Ayrica `kind` alanina dorduncu deger: 'kafa_karistirdi'. Bu bir sema degisikligi DEGIL
(kind zaten String, dogrulama Pydantic'te) — burada yalniz kayda geciyor. Mevcut uc deger
KORUNUR: canli tabloda 0 satir var, yine de gecmise donuk esleme borcu uretmemek icin
silme YAPILMAZ.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-08-11
"""
from alembic import op
import sqlalchemy as sa


revision = "e7f8a9b0c1d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("feedback") as batch_op:
        batch_op.add_column(sa.Column("app_version", sa.String(40), nullable=True))
        batch_op.add_column(sa.Column("istek_id", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("viewport_w", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("tarayici", sa.String(40), nullable=True))
        batch_op.add_column(sa.Column("pwa", sa.Boolean(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("feedback") as batch_op:
        batch_op.drop_column("pwa")
        batch_op.drop_column("tarayici")
        batch_op.drop_column("viewport_w")
        batch_op.drop_column("istek_id")
        batch_op.drop_column("app_version")
