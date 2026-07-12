"""
Veri egemenliği — GET /api/user/export tüm kullanıcı verisinin JSON dökümü (KVKK taşınabilirlik).
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import (
    Base, User, Account, AccountType, Transaction, TransactionType, Envelope, Goal,
)


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0))
    s.add(Transaction(user_id=1, transaction_type=TransactionType.expense, amount=250.0,
                      category="market"))
    s.add(Envelope(user_id=1, category="market", monthly_amount=Decimal("2000")))
    s.add(Goal(user_id=1, goal_type="cash_target", title="Acil fon",
               target_amount=Decimal("30000"), current_amount=Decimal("0"),
               status="active", progress_percent=Decimal("0")))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.get(User, 1)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def test_export_tum_veriyi_dondurur(client):
    r = client.get("/api/user/export")
    assert r.status_code == 200
    body = r.json()
    assert body["schema"] == "financialos-export-v1"
    assert body["user"]["name"] == "murat"
    # her koleksiyon mevcut ve doğru serialize
    assert len(body["accounts"]) == 1 and body["accounts"][0]["account_type"] == "cash"
    assert len(body["transactions"]) == 1 and body["transactions"][0]["transaction_type"] == "expense"
    assert len(body["envelopes"]) == 1
    assert body["envelopes"][0]["monthly_amount"] == 2000.0        # Decimal → float
    assert len(body["goals"]) == 1 and body["goals"][0]["title"] == "Acil fon"
    # boş koleksiyonlar da anahtar olarak var
    for key in ("recurring_incomes", "personal_debts", "net_worth_snapshots", "coach_memory"):
        assert key in body and isinstance(body[key], list)


def test_export_json_serialize_edilebilir(client):
    import json
    r = client.get("/api/user/export")
    json.dumps(r.json())   # enum/tarih/Decimal JSON-güvenli → hata fırlatmamalı


def test_export_eylem_karar_hedef_kayitlari_dahil(client):
    """KVKK/egemenlik: kullanıcının eylem/karar/hedef-izleme kayıtları da export'ta olmalı."""
    body = client.get("/api/user/export").json()
    for key in ("pending_actions", "action_history", "decision_journal",
                "goal_allocations", "goal_rules", "reasoning_traces", "api_call_log"):
        assert key in body and isinstance(body[key], list), f"export'ta eksik: {key}"


def test_export_tamlik_invariant():
    """
    TAMLIK INVARIANT: user_id'li (veya goal_id ile kullanıcıya bağlı) HER tablo export'ta
    temsil edilmeli. Biri yeni user-data tablosu ekleyip export'a koymayı unutursa yakalar
    (KVKK/egemenlik regresyon ağı). price_history market verisi (user-data değil) → muaf.
    """
    from app.models import Base
    from app.routers.user import export_data as _fn
    import inspect
    src = inspect.getsource(_fn)
    MARKET_OR_JOIN = {"price_history"}  # user-data değil / özel ele alınır
    for cls in Base.__subclasses__():
        cols = {c.name for c in cls.__table__.columns}
        tn = cls.__tablename__
        if tn == "users" or tn in MARKET_OR_JOIN:
            continue
        if "user_id" in cols or "goal_id" in cols:
            # export fonksiyonunun gövdesinde bu model dump ediliyor mu (isim geçiyor mu)?
            assert cls.__name__ in src, f"{tn} ({cls.__name__}) export'ta yok — KVKK tamlık ihlali"
