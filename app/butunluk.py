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
"""
from __future__ import annotations

import re

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.models import PersonalDebt, RecurringExpense, RecurringIncome

YIL_AY = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class ButunlukHatasi(ValueError):
    """Tutarsız satır flush'a giremez; mesaj alan adını ve değeri söyler."""


def _denetle(obj) -> None:
    if isinstance(obj, PersonalDebt):
        if bool(obj.is_paid) != (obj.paid_date is not None):
            raise ButunlukHatasi(
                f"personal_debts id={obj.id}: is_paid={obj.is_paid!r} ile paid_date={obj.paid_date!r} "
                "çelişiyor (ödendiyse tarih zorunlu, ödenmediyse tarih boş)."
            )
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
        if session.is_modified(obj, include_collections=False) or obj in session.new:
            _denetle(obj)
