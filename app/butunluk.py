"""
Veri bütünlüğü kuralları — ORM flush kancası (DATA-025 / DATA-029, BUG #444).

NEDEN DB CHECK DEĞİL: SQLite'ta var olan tabloya CHECK eklemek tabloyu yeniden kurmayı gerektirir
(alembic batch modu: kopyala-sil-yeniden adlandır). Canlı beta SQLite'ta ve bu depo şema
göçlerinde tablo yeniden kurulumundan bilinçli kaçınıyor (FK göçünde de öyle yapıldı). Kural
ORM'de, `before_flush`'ta uygulanır: hangi yazıcıdan gelirse gelsin (router, executor, sim,
betik) tutarsız satır diske inmez. Bedeli: ORM dışı ham SQL bu kapıdan geçmez — depoda
mutasyon yapan ham SQL yok (`test_scope_enforcement` sınıfı kapılar ORM'i zorunlu kılar).

Kurallar (ölçüldü, 13 Eyl 2026 — canlı veride ihlal 0/0):
- `PersonalDebt`: `is_paid` ⇔ `paid_date` dolu. "Ödendi ama tarih yok" ya da "tarih var ama
  ödenmedi" üç-değerli mantık üretir; BUG #106 router'da senkronluyordu, ama tek yazıcı değil.
- `RecurringIncome/Expense.last_triggered_year_month`: `YYYY-MM` biçimi. Dedup anahtarı bu;
  "2026-5" ya da "May-26" yazılırsa aynı ay iki kez tetiklenir (mükerrer propose_action).
- `CoachInsight.status` (DATA-019): sütun `nullable=True` + `default="active"` — NULL üçüncü
  bir durum olurdu ("aktif mi değil mi bilinmiyor"); NOT NULL'a çevirmek SQLite'ta tablo
  yeniden kurulumu ister. Kural burada: yalnız `active | invalidated | dormant | user_invalidated`;
  yeni nesnede None "varsayılan uygulanacak" demektir (sütun default'u INSERT'te yazılır), var
  olan satırda None yasaktır. Canlıda 39/39 dolu (ölçüldü, 13 Eyl 2026).
- `Goal.progress_percent` (DATA-033): [0, 100]. `goal_engine` iki yolda da klempliyor (BUG #132)
  ama tek yazıcı değil; çekim katkıyı aşınca negatif, hedef küçülünce >100 sızabilirdi.
- `Account` kart alanları (DATA-027): `credit_limit / statement_day / payment_day /
  statement_balance` YALNIZ kredi kartında dolu olabilir. Tersi (kartta limit ZORUNLU) bilinçli
  yok: bilinmeyen limit sıfır değildir, arayüz limiti isteğe bağlı tutar, `kart_kullanim` limitsiz
  kartta None döner. Canlı: 13 nakit + 4 kredi + 1 yatırımda hepsi NULL, 6 kartta hepsi dolu.
"""
from __future__ import annotations

import re

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models import Account, AccountType, CoachInsight, Goal, PersonalDebt, RecurringExpense, RecurringIncome

YIL_AY = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


# `user_invalidated` belgeli dorduncu durum (coach_insights.py filtre belgesi); yazicisi bugun yok.
KART_ALANLARI = ("credit_limit", "statement_day", "payment_day", "statement_balance")
ICGORU_DURUMLARI = ("active", "invalidated", "dormant", "user_invalidated")


class ButunlukHatasi(ValueError):
    """Tutarsız satır flush'a giremez; mesaj alan adını ve değeri söyler."""


def _denetle(obj, yeni: bool = False) -> None:
    if isinstance(obj, PersonalDebt):
        if bool(obj.is_paid) != (obj.paid_date is not None):
            raise ButunlukHatasi(
                f"personal_debts id={obj.id}: is_paid={obj.is_paid!r} ile paid_date={obj.paid_date!r} "
                "çelişiyor (ödendiyse tarih zorunlu, ödenmediyse tarih boş)."
            )
    elif isinstance(obj, CoachInsight):
        if obj.status is None and yeni:
            return   # INSERT'te sütun default'u ("active") yazılır
        if obj.status not in ICGORU_DURUMLARI:
            raise ButunlukHatasi(
                f"coach_insights id={obj.id}: status={obj.status!r} geçersiz "
                f"(izinli: {', '.join(ICGORU_DURUMLARI)}; NULL üçüncü durum değildir)."
            )
    elif isinstance(obj, Account):
        if obj.account_type != AccountType.credit_card:
            dolu = [ad for ad in KART_ALANLARI if getattr(obj, ad, None) is not None]
            if dolu:
                raise ButunlukHatasi(
                    f"accounts id={obj.id}: {obj.account_type!r} hesapta kart alanı dolu: {', '.join(dolu)} "
                    "(yalnız kredi kartında anlamlı)."
                )
    elif isinstance(obj, Goal):
        p = obj.progress_percent
        if p is not None and not (0 <= p <= 100):
            raise ButunlukHatasi(f"goals id={obj.id}: progress_percent={p!r} [0, 100] dışında.")
    elif isinstance(obj, (RecurringIncome, RecurringExpense)):
        ym = obj.last_triggered_year_month
        if ym is not None and not YIL_AY.match(ym):
            raise ButunlukHatasi(
                f"{obj.__tablename__} id={obj.id}: last_triggered_year_month={ym!r} 'YYYY-MM' değil "
                "(dedup anahtarı bozulur)."
            )


@event.listens_for(Session, "before_flush")
def _flush_oncesi(session: Session, flush_context, instances) -> None:
    for obj in list(session.new) + list(session.dirty):
        if obj in session.deleted:
            continue
        yeni = obj in session.new
        if yeni or session.is_modified(obj, include_collections=False):
            _denetle(obj, yeni=yeni)
