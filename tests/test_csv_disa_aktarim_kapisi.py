"""
DVIZ-011 (BUG #495): işlemler CSV olarak dışa aktarılır.

Ölçüm (14 Eyl 2026): hiçbir uç CSV üretmiyordu (KVKK JSON dökümü tablo değil). Kilitlenen:
  1. `GET /api/transactions/export.csv`: text/csv, indirme başlığı, UTF-8 BOM, `;` ayırıcı,
     ondalık virgül, ISO tarih, en yeni önce,
  2. tarih aralığı filtreler (dahil),
  3. formül enjeksiyonu: `=`/`+`/`-`/`@` ile başlayan metin `'` ile etkisizleştirilir,
  4. Türkçe karakter ve `;` içeren metin bozulmadan (tırnaklı) yazılır,
  5. başka kullanıcının işlemi dökümde yoktur (sahiplik).
"""
from __future__ import annotations

import csv
import io
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.dependencies import get_current_user, get_db
from app.main import app
from app.models import Base, Transaction, TransactionType, User


@pytest.fixture
def client():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add_all([User(id=1, name="ben"), User(id=2, name="baskasi")])
    s.add_all([
        Transaction(user_id=1, transaction_type=TransactionType.expense, amount=1234.5, category="market", description="Şarküteri; peynir", transaction_date=date(2026, 9, 1)),
        Transaction(user_id=1, transaction_type=TransactionType.income, amount=30000, category="maaş", description="=HYPERLINK(\"x\")", transaction_date=date(2026, 9, 10)),
        Transaction(user_id=1, transaction_type=TransactionType.expense, amount=10, category="x", description="eski", transaction_date=date(2026, 8, 1)),
        Transaction(user_id=2, transaction_type=TransactionType.expense, amount=999, category="gizli", description="baskasinin", transaction_date=date(2026, 9, 5)),
    ])
    s.commit()
    app.dependency_overrides[get_db] = lambda: s
    app.dependency_overrides[get_current_user] = lambda: s.get(User, 1)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        s.close()


def _satirlar(r):
    metin = r.content.decode("utf-8")
    assert metin.startswith("﻿"), "UTF-8 BOM yok (Excel Türkçe karakteri bozar)"
    return list(csv.reader(io.StringIO(metin.lstrip("﻿")), delimiter=";"))


def test_csv_bicimi_ve_siralama(client):
    r = client.get("/api/transactions/export.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert 'attachment; filename="islemler.csv"' == r.headers["content-disposition"]
    satirlar = _satirlar(r)
    assert satirlar[0] == ["tarih", "tur", "tutar", "kategori", "aciklama", "hesap_id", "kart_harcamasi"]
    assert [s[0] for s in satirlar[1:]] == ["2026-09-10", "2026-09-01", "2026-08-01"]   # en yeni önce
    assert satirlar[2][2] == "1234,50"                      # ondalık virgül
    assert satirlar[2][4] == "Şarküteri; peynir"            # `;` tırnaklı, Türkçe sağlam
    assert "baskasinin" not in r.content.decode("utf-8")   # sahiplik


def test_formul_enjeksiyonu_etkisiz(client):
    satirlar = _satirlar(client.get("/api/transactions/export.csv"))
    assert satirlar[1][4] == "'=HYPERLINK(\"x\")"


def test_tarih_araligi_dahil(client):
    satirlar = _satirlar(client.get("/api/transactions/export.csv", params={"baslangic": "2026-09-01", "bitis": "2026-09-10"}))
    assert [s[0] for s in satirlar[1:]] == ["2026-09-10", "2026-09-01"]
    r = client.get("/api/transactions/export.csv", params={"baslangic": "2026-09-02"})
    assert 'filename="islemler-2026-09-02.csv"' in r.headers["content-disposition"]
    assert [s[0] for s in _satirlar(r)[1:]] == ["2026-09-10"]
