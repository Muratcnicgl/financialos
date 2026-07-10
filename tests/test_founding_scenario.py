"""
KURUCU SENARYO golden test — tüm sistem kurucu vizyonu birlikte gerçekliyor mu?

Murat'ın manzarası: nakit 4.276, Ziraat kart 11.976 (%99.8 dolu, son ödeme 12'si),
5 kredi, yatırım, KYK geliri (ayın 8'i). Bu tek test, kurucu mekanikleri ENTEGRE doğrular:
- Gölge Muhasebe: reel_butce kart borcunu düşer (nakit'ten küçük)
- Zikzak: yarin_limit_harcamasiz alanı üretilir
- Kart SON ÖDEME: upcoming_reminders'ta card_payment
- Borç Çığı: koç context'inde BORÇ ÖZGÜRLÜĞÜ
Deterministik: cockpit sabit tarihle çağrılır.
"""
from __future__ import annotations

from datetime import date

from app.models import (
    User, Account, AccountType, RecurringIncome, Transaction, TransactionType,
)
from app.rules_engine import generate_cockpit
from app.coach import _build_context_message
from app.grounding import check_grounding


def _seed_founding(db, user_id):
    db.add(Account(user_id=user_id, name="Enpara", account_type=AccountType.cash, balance=4276.14))
    db.add(Account(user_id=user_id, name="Ziraat Kart", account_type=AccountType.credit_card,
                   balance=11976.0, credit_limit=12000.0, statement_day=2, payment_day=12))
    for i in range(5):
        db.add(Account(user_id=user_id, name=f"Kredi {i+1}", account_type=AccountType.loan,
                       balance=40000.0 - i * 5000, monthly_payment=2000.0,
                       interest_rate=1.5, remaining_installments=24))
    db.add(Account(user_id=user_id, name="TLY Fon", account_type=AccountType.investment,
                   balance=20000.0, lot_count=10.0, cost_per_lot=1800.0, current_price=2000.0))
    db.add(RecurringIncome(user_id=user_id, name="KYK", amount=4000.0, day_of_month=8, is_active=True))
    db.commit()


def test_kurucu_senaryo_golge_muhasebe_ve_zikzak(db_session, test_user):
    _seed_founding(db_session, test_user.id)
    cockpit = generate_cockpit(test_user.id, date(2026, 5, 7), db_session)

    # Gölge Muhasebe: kart borcu (11.976) nakti (4.276) aştığı için reel_butce nakitten KÜÇÜK
    assert cockpit["reel_butce"] < cockpit["nakit_kasa"], "shadow ledger kart borcunu düşmeli"
    # Kart %99.8 dolu → hayatta kalma / likidite baskısı statüsü
    assert cockpit["reel_butce"] < 0 or "baskı" in cockpit["statu"].lower() or "hayatta" in cockpit["statu"].lower()
    # Zikzak projeksiyonu alanı üretildi
    assert "yarin_limit_harcamasiz" in cockpit


def test_kurucu_senaryo_kart_son_odeme_reminder(db_session, test_user):
    _seed_founding(db_session, test_user.id)
    cockpit = generate_cockpit(test_user.id, date(2026, 5, 7), db_session)  # son ödeme 12 → 5 gün
    cp = [r for r in cockpit["upcoming_reminders"] if r["type"] == "card_payment"]
    assert len(cp) == 1
    assert cp[0]["days_until"] == 5
    assert cp[0]["card_risk"] is True


def test_kurucu_senaryo_koc_context_borc_ozgurlugu_ve_zikzak(db_session, test_user):
    _seed_founding(db_session, test_user.id)
    context, _ = _build_context_message(db_session, test_user.id)
    # Borç Çığı koça ulaşıyor
    assert "## BORÇ ÖZGÜRLÜĞÜ" in context
    # Zikzak "biriken güç" satırı koça ulaşıyor
    assert "Bugün harcamazsan" in context
    # Master Checkpoint bloğu (emanet/red-line altyapısı) her zaman var
    assert "MASTER CHECKPOINT" in context


def test_context_grounding_tutarliligi_invariant(db_session, test_user):
    """
    GROUNDING-TUTARLILIK INVARIANT: koça verilen context'teki HER TL tutarı cockpit'te
    doğrulanabilir olmalı. Aksi halde grounding meşru deterministik sayıları "izlenemeyen"
    sanıp analiz raporunda confidence düşürür (BUG #110 sınıfı regresyon). Bu test, ileride
    biri yeni bir context bloğu eklerken sayılarını cockpit'e tanıtmayı unutursa yakalar.
    """
    _seed_founding(db_session, test_user.id)
    context, cockpit = _build_context_message(db_session, test_user.id)
    r = check_grounding(context, cockpit)
    assert r["ok"] is True, f"context'te grounding'siz TL tutar(lar): {r['unverified']}"
