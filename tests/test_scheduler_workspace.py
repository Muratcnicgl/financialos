"""
M73 (Wave-5, ADR-037) — Gece batch cron'ları personal-workspace kapsamında koşar.

Bağlam (tam-proje-durum-raporu §B12): 5 cron job workspace_scope contextvar'ı SET ETMİYORDU →
hepsi legacy user_id yolundan koşuyordu. Coach insight'ları USER-SEVİYELİ (CoachInsight/CoachMemory'de
workspace_id YOK) ama snapshot/hesap/işlem okuyan 4 extractor ham `user_id ==` kullanıyordu → paylaşımlı
(aile) workspace eklenince o veri kişisel insight'lara KARIŞIRDI. M73: extractor'lar `_scope`'a çevrildi +
batch job'lar `workspace_scope(personal_ws_id)` ile sarıldı.

Diğer 3 job (fetch_investment_prices=global fon-fiyatı, nightly_trace_cleanup=global retention,
weekly_smoke_test=DB'siz) BİLİNÇLİ workspace-bağımsız — bkz. milestone-log M73.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base, User, Workspace, WorkspaceMembership, WorkspaceRole, Account, AccountType,
    Transaction, TransactionType, CoachInsight,
)
from app.rules_engine import workspace_scope
from app.coach_insights import extract_category_account_preference
from app.scheduler import _personal_workspace_id, run_periodic_batch_for_user


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def two_ws(db):
    """u1: personal ws (KisiselKart + 6 market gideri) + shared ws (AileKart + 6 market gideri)."""
    u1 = User(name="murat", email="m@x.com")
    db.add(u1); db.commit()
    personal = Workspace(owner_user_id=u1.id, name="Kişisel", is_personal=True)
    shared = Workspace(owner_user_id=u1.id, name="Aile", is_personal=False)
    db.add_all([personal, shared]); db.commit()
    db.add_all([
        WorkspaceMembership(workspace_id=personal.id, user_id=u1.id, role=WorkspaceRole.owner),
        WorkspaceMembership(workspace_id=shared.id, user_id=u1.id, role=WorkspaceRole.owner),
    ])
    pk = Account(user_id=u1.id, workspace_id=personal.id, name="KisiselKart",
                 account_type=AccountType.credit_card, balance=0)
    ak = Account(user_id=u1.id, workspace_id=shared.id, name="AileKart",
                 account_type=AccountType.credit_card, balance=0)
    db.add_all([pk, ak]); db.commit()
    base = datetime.utcnow() - timedelta(days=10)
    for i in range(6):
        db.add(Transaction(user_id=u1.id, workspace_id=personal.id, account_id=pk.id,
                           transaction_type=TransactionType.expense, amount=100, category="market",
                           description="market", transaction_date=(base + timedelta(days=i)).date()))
        db.add(Transaction(user_id=u1.id, workspace_id=shared.id, account_id=ak.id,
                           transaction_type=TransactionType.expense, amount=100, category="market",
                           description="market", transaction_date=(base + timedelta(days=i)).date()))
    db.commit()
    return {"u1": u1, "personal": personal, "shared": shared, "pk": pk, "ak": ak}


def test_personal_workspace_id_cozumu(db, two_ws):
    """Helper personal ws id'yi döner; user'ın personal'ı yoksa None (köprü legacy)."""
    assert _personal_workspace_id(db, two_ws["u1"].id) == two_ws["personal"].id
    assert _personal_workspace_id(db, 99999) is None


def test_batch_personal_scope_izole(db, two_ws):
    """
    run_periodic_batch_for_user personal-scope'ta koşar → category_account_preference YALNIZ
    personal (KisiselKart) işlemlerini sayar (6), AileKart'ı (shared) GÖRMEZ. Insight KisiselKart
    referansı içermeli; toplam işlem 6 (12 değil = karışım yok).
    """
    run_periodic_batch_for_user(db, two_ws["u1"].id)
    insight = (db.query(CoachInsight)
               .filter(CoachInsight.user_id == two_ws["u1"].id,
                       CoachInsight.insight_type == "category_account_preference")
               .first())
    assert insight is not None
    assert "KisiselKart" in insight.content
    assert "AileKart" not in insight.content
    assert "6/6" in insight.content or "6 expense" in insight.content  # 12 değil = izole


def test_legacy_scope_yoksa_karisir_kanit(db, two_ws):
    """Köprü kanıtı: scope YOKKEN extractor user_id'ye düşer → personal+shared KARIŞIR (12 işlem).
    Bu, M73 öncesi davranıştı; batch'in neden personal-scope'a alındığını gösterir."""
    # scope yok → _scope user_id → her iki ws'in market gideri toplanır (2 dominant hesap, share 0.5)
    extract_category_account_preference(db, two_ws["u1"].id)
    insight = (db.query(CoachInsight)
               .filter(CoachInsight.insight_type == "category_account_preference").first())
    # 12 işlem 2 hesaba %50/%50 bölününce dominant eşiği (%70) AŞILMAZ → insight YARATILMAZ
    # (yani karışım dominant sinyali BOZAR — izolasyonun neden gerekli olduğunun kanıtı)
    assert insight is None
