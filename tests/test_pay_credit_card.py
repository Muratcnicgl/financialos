"""
M68 (BUG #161) — Kredi kartı ödemesi doğru modeli.

Kök defect: koç kart ödemesini add_transaction expense/kart olarak modelliyordu →
credit_card+expense → borç ARTIYORDU + nakit ayağı hiç işlenmiyordu. Fix: pay_credit_card
first-class aksiyon — kart borcu AZALIR + nakit çıkar.
"""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from app.models import Account, AccountType, PendingAction, ActionStatus
from app.action_executor import execute_pending_action, propose_action


def _setup(db, user):
    cash = Account(user_id=user.id, name="Enpara Nakit", account_type=AccountType.cash,
                   balance=Decimal("10000"))
    card = Account(user_id=user.id, name="Ziraat Kredi Karti", account_type=AccountType.credit_card,
                   balance=Decimal("10180.01"))  # borç
    db.add_all([cash, card])
    db.commit()
    return cash, card


def test_pay_credit_card_borcu_ve_nakiti_azaltir(db_session, test_user):
    """500 ödeme → kart borcu 10180.01→9680.01 (AZALIR), nakit 10000→9500 (çıkar)."""
    cash, card = _setup(db_session, test_user)
    pending = PendingAction(
        user_id=test_user.id, action_type="pay_credit_card",
        payload=json.dumps({"card_account_id": card.id, "amount": 500}),
        summary="Ziraat kartına 500 TL ödeme", status=ActionStatus.pending,
    )
    db_session.add(pending); db_session.commit()

    res = execute_pending_action(db_session, pending.id, test_user.id)
    assert res["success"] is True, res
    db_session.refresh(card); db_session.refresh(cash)
    assert card.balance == Decimal("9680.0100")   # borç AZALDI (BUG #161: eskiden 10680.01 idi)
    assert cash.balance == Decimal("9500.0000")   # nakit çıktı


def test_pay_credit_card_kaynak_hesap_secilebilir(db_session, test_user):
    cash, card = _setup(db_session, test_user)
    ikinci = Account(user_id=test_user.id, name="Ikinci Kasa", account_type=AccountType.cash,
                     balance=Decimal("3000"))
    db_session.add(ikinci); db_session.commit()
    pending = PendingAction(
        user_id=test_user.id, action_type="pay_credit_card",
        payload=json.dumps({"card_account_id": card.id, "amount": 200, "source_account_id": ikinci.id}),
        summary="x", status=ActionStatus.pending)
    db_session.add(pending); db_session.commit()
    execute_pending_action(db_session, pending.id, test_user.id)
    db_session.refresh(ikinci); db_session.refresh(cash); db_session.refresh(card)
    assert ikinci.balance == Decimal("2800.0000")   # seçilen kaynaktan çıktı
    assert cash.balance == Decimal("10000.0000")    # varsayılan nakit dokunulmadı
    assert card.balance == Decimal("9980.0100")


def test_pay_credit_card_kredi_karti_degilse_hata(db_session, test_user):
    cash, card = _setup(db_session, test_user)
    pending = PendingAction(
        user_id=test_user.id, action_type="pay_credit_card",
        payload=json.dumps({"card_account_id": cash.id, "amount": 100}),  # nakit hesap, kart değil
        summary="x", status=ActionStatus.pending)
    db_session.add(pending); db_session.commit()
    res = execute_pending_action(db_session, pending.id, test_user.id)
    assert res["success"] is False and "Kredi kartı" in res.get("error", "")


def test_pay_credit_card_pozitif_tutar(db_session, test_user):
    cash, card = _setup(db_session, test_user)
    pending = PendingAction(
        user_id=test_user.id, action_type="pay_credit_card",
        payload=json.dumps({"card_account_id": card.id, "amount": -50}),
        summary="x", status=ActionStatus.pending)
    db_session.add(pending); db_session.commit()
    res = execute_pending_action(db_session, pending.id, test_user.id)
    assert res["success"] is False


def test_pay_credit_card_fazla_odeme_uyarir(db_session, test_user):
    """Borçtan fazla ödeme → başarılı ama warning (kart alacak bakiyesi)."""
    cash, card = _setup(db_session, test_user)
    pending = PendingAction(
        user_id=test_user.id, action_type="pay_credit_card",
        payload=json.dumps({"card_account_id": card.id, "amount": 11000}),  # borç 10180'den fazla
        summary="x", status=ActionStatus.pending)
    db_session.add(pending); db_session.commit()
    res = execute_pending_action(db_session, pending.id, test_user.id)
    assert res["success"] is True
    db_session.refresh(card)
    assert card.balance == Decimal("-819.9900")  # alacak bakiyesi (negatif borç)
    assert res["result"]["warning"] is not None
