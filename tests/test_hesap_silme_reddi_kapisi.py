"""
UX-030 / BUG #434 KAPISI — HESAP SİLME: BAĞLI KAYIT VARSA REDDEDİLİR, SAYISIYLA SÖYLENİR.

Ölçülen (12 Eyl 2026): madde "silme uyarısı bağlı işlem sayısı vermiyor; 'bu hesaba bağlı 47
işlem de silinecek' de" diyordu — ama sunucu bağlı işlem/düzenli gider varsa silmeyi zaten
REDDEDİYOR (409) ve sayıları söylüyor; hiçbir işlem kaskad silinmiyor. Yanlış olan arayüz
metniydi ("bağlı işlemler silinecek"). Bu kapı sunucu davranışını kilitler; arayüz metni
`hesap-silme-metni.test.jsx` ile kilitli.
"""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import Account, AccountType, Base, RecurringExpense, Transaction, TransactionType, User


@pytest.fixture
def ortam():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)(); s.add(User(id=1, name="u")); s.commit()
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    try:
        yield s, TestClient(app)
    finally:
        app.dependency_overrides.clear(); s.close()


def test_bagli_islem_varsa_409_ve_sayilar(ortam):
    s, c = ortam
    acc = Account(user_id=1, name="n", account_type=AccountType.cash, balance=0); s.add(acc); s.commit()
    for _ in range(3):
        s.add(Transaction(user_id=1, account_id=acc.id, transaction_type=TransactionType.expense,
                          amount=1, transaction_date=date(2026, 9, 1), category="x"))
    s.add(RecurringExpense(user_id=1, account_id=acc.id, name="kira", amount=10, day_of_month=1))
    s.commit()
    r = c.delete(f"/api/accounts/{acc.id}")
    assert r.status_code == 409
    assert "3 işlem" in r.json()["detail"] and "1 düzenli gider" in r.json()["detail"]
    assert s.get(Account, acc.id) is not None, "reddedilen silme hesabı da işlemleri de bırakır"
    assert s.query(Transaction).count() == 3  # scope-exempt: test


def test_bagli_kayit_yoksa_silinir(ortam):
    s, c = ortam
    acc = Account(user_id=1, name="n", account_type=AccountType.cash, balance=0); s.add(acc); s.commit()
    assert c.delete(f"/api/accounts/{acc.id}").status_code in (200, 204)
    assert s.get(Account, acc.id) is None
