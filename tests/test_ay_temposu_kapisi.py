"""
UX-028 / BUG #466 KAPISI — "BU AY" TEMPOSU.

Ölçülen (13 Eyl 2026): kokpit "ay sonuna N gün" diyordu ama ayın kaçta kaçının geçtiği ve
harcamanın bu gidişle geçen aya göre nerede olduğu görünmüyordu (goal-gradient yok).
`ay_temposu` aylık özetle aynı kaynaktan (`_month_aggregates`) hesaplar.

Kilitlenen: ilerleme = gün/ay günü; projeksiyon = harcanan/gün×ay günü; geçen ay gideri yoksa
"bilinmiyor" (0 referans hedef değildir); ilk 3 gün "erken"; %105 eşiği; kokpit anahtarı taşır.
"""
from __future__ import annotations

from datetime import date

from app.models import Account, AccountType, Transaction, TransactionType
from app.rules_engine import ay_temposu, generate_cockpit


def _gider(db, uid, acc_id, gun, tutar):
    db.add(Transaction(user_id=uid, account_id=acc_id, transaction_type=TransactionType.expense,
                       amount=tutar, transaction_date=gun, category="x"))


def test_tempo_hesabi_ve_durumlar(db_session, test_user):
    acc = Account(user_id=test_user.id, name="N", account_type=AccountType.cash, balance=0); db_session.add(acc); db_session.commit()
    # Eylül 1-13: 1300 harcandı → projeksiyon 1300/13*30 = 3000
    for g in range(1, 14):
        _gider(db_session, test_user.id, acc.id, date(2026, 9, g), 100)
    db_session.commit()
    t = ay_temposu(test_user.id, date(2026, 9, 13), db_session)
    assert (t["gun"], t["ay_gunu"], t["ilerleme_pct"]) == (13, 30, 43.3)
    assert (t["harcanan"], t["projeksiyon"]) == (1300, 3000)
    assert t["durum"] == "bilinmiyor" and t["referans"] is None and t["referans_ay"] == "Ağustos"
    # geçen ay 2000 → 3000 > 2100 → üstünde
    _gider(db_session, test_user.id, acc.id, date(2026, 8, 10), 2000); db_session.commit()
    assert ay_temposu(test_user.id, date(2026, 9, 13), db_session)["durum"] == "ustunde"
    # geçen ay 3100 → hedefte (3000 ≤ 3255)
    _gider(db_session, test_user.id, acc.id, date(2026, 8, 11), 1100); db_session.commit()
    assert ay_temposu(test_user.id, date(2026, 9, 13), db_session)["durum"] == "hedefte"
    # ayın 2. günü → erken
    assert ay_temposu(test_user.id, date(2026, 9, 2), db_session)["durum"] == "erken"


def test_kokpit_anahtari_tasir(db_session, test_user):
    acc = Account(user_id=test_user.id, name="N", account_type=AccountType.cash, balance=0); db_session.add(acc); db_session.commit()
    c = generate_cockpit(test_user.id, date(2026, 9, 13), db_session)
    assert set(c["ay_temposu"]) >= {"gun", "ay_gunu", "ilerleme_pct", "harcanan", "projeksiyon", "referans", "durum"}
