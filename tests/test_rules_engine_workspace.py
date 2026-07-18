"""
M71 (Wave-5, ADR-037 köprü-desen) — rules_engine FONKSİYON düzeyi workspace-yolu testleri.

Neden: M43'te rules_engine ~50 fonksiyona `_scope()` köprüsü eklendi ama YALNIZ generate_cockpit
uçtan-uca doğrulandı (§B23b RISK #2 — ÖRNEKLEME, KAPSAMA değil). Bu dosya DB-sorgulayan public
fonksiyonları DOĞRUDAN `workspace_scope()` içinde çağırır ve İZOLASYONU kanıtlar: veri YALNIZ
'shared' workspace'te → scope(shared) görür, scope(personal) BOŞ döner. Bir fonksiyon `_scope`'u
atlarsa (global sorgu / user_id sızıntısı) personal-scope BOŞ dönmez → test kırılır.

Kapsam: DB-sorgulayan + user_id alan 7 fonksiyon. Saf-matematik fonksiyonlar (calculate_daily_limit,
evaluate_credit_card_strategy, calculate_health_score, detect_alerts, parse_gg_command vb.) DB'ye
dokunmaz → workspace-yolu yok → kapsam dışı (bilinçli).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base, User, Workspace, WorkspaceMembership, WorkspaceRole, Account, AccountType,
    Transaction, TransactionType, RecurringIncome, PersonalDebt, DebtDirection,
    Envelope, NetWorthSnapshot,
)
from app.rules_engine import (
    workspace_scope,
    generate_cockpit,
    generate_monthly_summary,
    detect_subscriptions,
    calculate_envelopes,
    calculate_receivables_aging,
    calculate_interest_leak,
    calculate_networth_attribution,
)

TODAY = date(2026, 7, 18)


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def ws(db):
    """
    Tek kullanıcı u1: personal ws (BOŞ) + shared ws (TÜM VERİ). İzolasyon testinin çekirdeği:
    her fonksiyon shared'te veri görür, personal'da HİÇBİR ŞEY görmez. Aynı user_id iki ws'de →
    fonksiyon user_id'ye düşerse (scope kaçağı) personal-scope de shared verisini görür = TEST KIRILIR.
    """
    u1 = User(name="murat", email="m@x.com")
    db.add(u1); db.commit()
    personal = Workspace(owner_user_id=u1.id, name="Murat (Kişisel)", is_personal=True)
    shared = Workspace(owner_user_id=u1.id, name="Aile", is_personal=False)
    db.add_all([personal, shared]); db.commit()
    db.add_all([
        WorkspaceMembership(workspace_id=personal.id, user_id=u1.id, role=WorkspaceRole.owner),
        WorkspaceMembership(workspace_id=shared.id, user_id=u1.id, role=WorkspaceRole.owner),
    ])

    pid, sid = personal.id, shared.id

    # --- SHARED ws: dolu finansal manzara (personal BOŞ kalır) ---
    db.add_all([
        Account(user_id=u1.id, workspace_id=sid, name="Aile Nakit",
                account_type=AccountType.cash, balance=5000),
        Account(user_id=u1.id, workspace_id=sid, name="Aile Kredi",
                account_type=AccountType.loan, balance=20000, interest_rate=3.0,
                monthly_payment=2000, remaining_installments=12),
        Account(user_id=u1.id, workspace_id=sid, name="Aile Kart",
                account_type=AccountType.credit_card, balance=4000, interest_rate=4.0,
                credit_limit=12000),
    ])
    # Abonelik paterni: aynı merchant, ~aylık 3 tekrar (detect_subscriptions için)
    for i in range(4):
        d = TODAY - timedelta(days=30 * i + 1)
        db.add(Transaction(user_id=u1.id, workspace_id=sid,
                           transaction_type=TransactionType.expense, amount=150,
                           category="abonelik", description="Netflix",
                           transaction_date=d))
    # Bu ayki gider (envelopes + monthly_summary için)
    db.add(Transaction(user_id=u1.id, workspace_id=sid,
                       transaction_type=TransactionType.expense, amount=800,
                       category="market", description="market",
                       transaction_date=TODAY))
    db.add(RecurringIncome(user_id=u1.id, workspace_id=sid, name="Maaş",
                           amount=30000, day_of_month=1, is_active=True))
    db.add(Envelope(user_id=u1.id, workspace_id=sid, category="market",
                    monthly_amount=1000, is_active=True))
    db.add(PersonalDebt(user_id=u1.id, workspace_id=sid, counterparty="Efe",
                        direction=DebtDirection.receivable, amount=2500,
                        due_date=TODAY - timedelta(days=45), is_paid=False))
    # İki snapshot (attribution için: ay başı ref + güncel)
    db.add_all([
        NetWorthSnapshot(user_id=u1.id, workspace_id=sid, snapshot_date=date(2026, 7, 1),
                         net_worth_seen=10000, net_worth_full=12500, cash=4000,
                         card_debt=5000, loan_debt=22000, investment_value=0, receivables=2500),
        NetWorthSnapshot(user_id=u1.id, workspace_id=sid, snapshot_date=TODAY,
                         net_worth_seen=11000, net_worth_full=13500, cash=5000,
                         card_debt=4000, loan_debt=20000, investment_value=0, receivables=2500),
    ])
    db.commit()
    return {"u1": u1, "pid": pid, "sid": sid}


# ============================================================
# Her fonksiyon: shared'te GÖRÜR, personal'da BOŞ (izolasyon)
# ============================================================

def test_interest_leak_izolasyon(db, ws):
    uid = ws["u1"].id
    with workspace_scope(ws["sid"]):
        shared = calculate_interest_leak(uid, db)
    with workspace_scope(ws["pid"]):
        personal = calculate_interest_leak(uid, db)
    # shared: kredi (20000×3%) + kart (4000×4%) = 600 + 160 = 760
    assert shared["aylik_toplam"] == 760.0
    assert len(shared["kalemler"]) == 2
    # personal: hiç borç hesabı yok → 0
    assert personal["aylik_toplam"] == 0.0
    assert personal["kalemler"] == []


def test_receivables_aging_izolasyon(db, ws):
    uid = ws["u1"].id
    with workspace_scope(ws["sid"]):
        shared = calculate_receivables_aging(uid, TODAY, db)
    with workspace_scope(ws["pid"]):
        personal = calculate_receivables_aging(uid, TODAY, db)
    assert shared is not None
    assert shared["adet"] == 1
    assert shared["toplam"] == 2500.0
    # personal: alacak yok → None
    assert personal is None


def test_envelopes_izolasyon(db, ws):
    uid = ws["u1"].id
    with workspace_scope(ws["sid"]):
        shared = calculate_envelopes(uid, TODAY, db)
    with workspace_scope(ws["pid"]):
        personal = calculate_envelopes(uid, TODAY, db)
    # shared: market zarfı 1000 bütçe, 800 harcanan
    assert len(shared["zarflar"]) == 1
    assert shared["toplam_harcanan"] == 800.0
    # personal: zarf yok → boş
    assert personal["zarflar"] == []
    assert personal["toplam_butce"] == 0.0


def test_monthly_summary_izolasyon(db, ws):
    uid = ws["u1"].id
    with workspace_scope(ws["sid"]):
        shared = generate_monthly_summary(uid, 2026, 7, db)
    with workspace_scope(ws["pid"]):
        personal = generate_monthly_summary(uid, 2026, 7, db)
    # shared: temmuz giderleri var (abonelik 150 + market 800 en az)
    assert shared["current"]["total_expense"] > 0
    # personal: hiç işlem yok → 0
    assert personal["current"]["total_expense"] == 0
    assert personal["current"]["total_income"] == 0


def test_detect_subscriptions_izolasyon(db, ws):
    uid = ws["u1"].id
    with workspace_scope(ws["sid"]):
        shared = detect_subscriptions(uid, TODAY, db)
    with workspace_scope(ws["pid"]):
        personal = detect_subscriptions(uid, TODAY, db)
    # shared: Netflix ~aylık 4 tekrar → abonelik tespit edilir
    assert shared["adet"] >= 1
    # personal: işlem yok → hiç abonelik
    assert personal["adet"] == 0
    assert personal["abonelikler"] == []


def test_networth_attribution_izolasyon(db, ws):
    uid = ws["u1"].id
    with workspace_scope(ws["sid"]):
        shared = calculate_networth_attribution(uid, TODAY, db)
    with workspace_scope(ws["pid"]):
        personal = calculate_networth_attribution(uid, TODAY, db)
    # shared: 2 snapshot → ayrıştırma döner (net 12500→13500 = +1000)
    assert shared is not None
    assert shared["degisim"] == 1000.0
    # personal: snapshot yok → None
    assert personal is None


def test_cockpit_izolasyon(db, ws):
    uid = ws["u1"].id
    with workspace_scope(ws["sid"]):
        shared = generate_cockpit(uid, TODAY, db)
    with workspace_scope(ws["pid"]):
        personal = generate_cockpit(uid, TODAY, db)
    # shared: nakit 5000, kart 4000, kredi 20000
    assert shared["nakit_kasa"] == 5000.0
    assert shared["kart_borcu"] == 4000.0
    assert shared["kredi_borcu"] == 20000.0
    # personal: hiç hesap yok → hepsi 0
    assert personal["nakit_kasa"] == 0.0
    assert personal["kart_borcu"] == 0.0
    assert personal["kredi_borcu"] == 0.0


# ============================================================
# Köprü kontrolü: scope YOKKEN (legacy) user_id'ye düşer → TÜM ws verisi
# ============================================================

def test_legacy_scope_yoksa_user_id_tum_veri(db, ws):
    """workspace_scope KULLANILMAZSA _scope user_id'ye düşer → kullanıcının HER ws'indeki veri
    birleşir (legacy davranış, ~900 mevcut test bu yolla korunur). İzolasyon YALNIZ scope içinde."""
    uid = ws["u1"].id
    # scope yok → kredi+kart shared'te olsa da user_id ile görünür
    leak = calculate_interest_leak(uid, db)
    assert leak["aylik_toplam"] == 760.0  # shared verisi user_id üzerinden görünür (legacy)
