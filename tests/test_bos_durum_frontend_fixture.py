"""
P3.2 (Wave-9) — BOŞ-DURUM FRONTEND FIXTURE'I + SÖZLEŞME KAYMASI KAPISI.

Sorun: `test_sifirdan_kullanici_e2e.py` boş kullanıcının BACKEND uçlarının çökmediğini
kanıtlıyor. Ama kullanıcının gördüğü şey React panelleri — panel, boş gövdeyi (0/None/
boş liste) render ederken çökerse kullanıcı beyaz ekran görür ve backend testi yeşil kalır.

Bu dosya iki iş yapar:
 1. Gerçek kayıt akışıyla BOŞ bir kullanıcı yaratır, parametresiz her GET ucunu çağırır ve
    cevapları `frontend/src/__fixtures__/bos-kullanici.json` dosyasına döker. Vitest'teki
    boş-durum testi bu dosyayı kullanır → frontend testi TAHMİN EDİLMİŞ mock ile değil,
    backend'in GERÇEK boş-durum sözleşmesiyle koşar.
 2. Sözleşme kayması kapısı: diskteki fixture'ın YAPISI (anahtar + tip iskeleti) canlı
    cevapla karşılaştırılır. Backend boş-durum gövdesini değiştirirse (alan ekler/siler/
    tipini değiştirir) bu test kırılır → frontend testi sessizce bayatlayamaz.

Değerler değil YAPI karşılaştırılır: tarih/saat gibi oynak değerler günlük kırmızıya
sebep olmamalı, ama alan/tip değişikliği gerçek sözleşme kaymasıdır ve yakalanmalıdır.

Fixture'ı güncelleme (sözleşme bilinçli değiştiyse):
    FOS_FIXTURE_UPDATE=1 .\\venv\\Scripts\\python.exe -m pytest tests/test_bos_durum_frontend_fixture.py -q
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db
from app.models import Base
from tests.endpoint_envanteri import parametresiz_get_uclari  # BUG #217

FIXTURE = Path(__file__).resolve().parents[1] / "frontend" / "src" / "__fixtures__" / "bos-kullanici.json"

# Dökümden hariç tutulanlar — GEREKÇELİ (dış servis / kimlik dışı / query zorunlu).
# `test_sifirdan_kullanici_e2e.BOS_DURUM_HARIC` ile aynı gerekçeler; burada frontend'in
# hiç çağırmadığı uçlar da elenir.
DOKUM_HARIC = {
    "/api/workspaces/join": "davet token'ı zorunlu (query param)",
}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-bos-durum-fixture-0123456789abcdef")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    from app import rate_limit
    rate_limit.reset()


@pytest.fixture
def client():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    app.dependency_overrides[get_db] = lambda: s
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()
    s.close()


@pytest.fixture
def bos_kullanici(client):
    r = client.post("/api/auth/register", json={
        "email": "bos.durum@example.com",
        "password": "Guclu-Parola-2026!",
        "name": "Boş Durum",
        "kvkk_consent": True,
    })
    assert r.status_code == 201, f"Kayıt başarısız: {r.status_code} {r.text[:300]}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _parametresiz_get_uclari() -> list[str]:
    # BUG #217: envanter OpenAPI'den (kapsam tabanı assert'li) — `app.routes` körleşmişti.
    return parametresiz_get_uclari(app, DOKUM_HARIC)


def _canli_dokum(client, headers) -> dict:
    """Boş kullanıcının her GET ucundaki gerçek gövdesi (yalnız 200 + JSON olanlar)."""
    dokum = {}
    for yol in _parametresiz_get_uclari():
        r = client.get(yol, headers=headers)
        if r.status_code != 200:
            continue
        if "application/json" not in r.headers.get("content-type", ""):
            continue
        dokum[yol] = r.json()

    # Yol-parametreli tek istisna: kullanıcının KENDİ personal workspace'i. Yeni kullanıcıda
    # bile vardır (kayıt akışı yaratır) ve Aile paneli ilk açılışta onu okur. Fixture'da
    # olmazsa frontend testi boş-durumu değil HATA yolunu ölçer (yanıltıcı yeşil).
    ws_listesi = dokum.get("/api/workspaces") or []
    if ws_listesi:
        ws_id = ws_listesi[0]["id"]
        r = client.get(f"/api/workspaces/{ws_id}", headers=headers)
        if r.status_code == 200:
            dokum[f"/api/workspaces/{ws_id}"] = r.json()
    return dokum


def _iskelet(deger):
    """Değerin YAPI imzası: dict→anahtar/iskelet, list→eleman iskeletlerinin birleşimi,
    skaler→tip adı. Oynak değerler (tarih, id, tutar) imzaya girmez."""
    if isinstance(deger, dict):
        return {k: _iskelet(v) for k, v in sorted(deger.items())}
    if isinstance(deger, list):
        if not deger:
            return ["<bos>"]
        # Boş kullanıcıda dolu liste beklenmez; yine de ilk elemanın iskeletini al.
        return [_iskelet(deger[0])]
    if deger is None:
        return "null"
    return type(deger).__name__


def test_bos_durum_fixture_guncel(client, bos_kullanici):
    """Diskteki frontend fixture'ı backend'in boş-durum sözleşmesiyle aynı YAPIDA olmalı."""
    canli = _canli_dokum(client, bos_kullanici)
    assert canli, "Boş kullanıcı için hiçbir 200 JSON ucu toplanamadı — döküm mantığı bozuk"

    if os.getenv("FOS_FIXTURE_UPDATE") == "1":
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(canli, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
        pytest.skip(f"Fixture güncellendi: {FIXTURE} ({len(canli)} uç)")

    assert FIXTURE.exists(), (
        f"Boş-durum fixture'ı yok: {FIXTURE}\n"
        "Üret: FOS_FIXTURE_UPDATE=1 python -m pytest tests/test_bos_durum_frontend_fixture.py -q"
    )
    diskteki = json.loads(FIXTURE.read_text(encoding="utf-8"))

    eksik = sorted(set(canli) - set(diskteki))
    fazla = sorted(set(diskteki) - set(canli))
    assert not eksik and not fazla, (
        "Boş-durum uç listesi değişmiş (frontend fixture bayat).\n"
        f"  Fixture'da OLMAYAN yeni uçlar: {eksik}\n"
        f"  Backend'de ARTIK OLMAYAN uçlar: {fazla}\n"
        "Güncelle: FOS_FIXTURE_UPDATE=1 python -m pytest tests/test_bos_durum_frontend_fixture.py -q"
    )

    farklar = [
        f"  {yol}: fixture={json.dumps(_iskelet(diskteki[yol]), ensure_ascii=False)[:200]} "
        f"canli={json.dumps(_iskelet(canli[yol]), ensure_ascii=False)[:200]}"
        for yol in sorted(canli)
        if _iskelet(canli[yol]) != _iskelet(diskteki[yol])
    ]
    assert not farklar, (
        "Boş-durum gövde YAPISI değişmiş — frontend paneli bu alanlara göre yazılmıştı:\n"
        + "\n".join(farklar)
        + "\nGüncelle: FOS_FIXTURE_UPDATE=1 python -m pytest tests/test_bos_durum_frontend_fixture.py -q"
    )


def test_fixture_kapsami_daralamaz(client, bos_kullanici):
    """Kapsam kilidi: fixture, panellerin ilk açılışta okuduğu uçları İÇERMELİ.
    Biri düşerse (uç kalkar/kimlik ister) frontend boş-durum testi sessizce körleşir."""
    diskteki = json.loads(FIXTURE.read_text(encoding="utf-8")) if FIXTURE.exists() else {}
    zorunlu = [
        "/api/cockpit", "/api/accounts", "/api/transactions", "/api/incomes",
        "/api/expenses/recurring", "/api/debts", "/api/checkpoints", "/api/goals",
        "/api/envelopes", "/api/wishlist", "/api/subscriptions", "/api/actions/pending",
        "/api/reports/monthly-summary", "/api/reports/category-breakdown",
        "/api/reports/net-worth-trend", "/api/cashflow/forecast",
        "/api/debt-strategy/compare", "/api/coach/usage", "/api/user",
    ]
    eksik = [y for y in zorunlu if y not in diskteki]
    assert not eksik, (
        f"Fixture panellerin okuduğu şu uçları içermiyor: {eksik}\n"
        "Uç kalktıysa listeyi gerekçeyle güncelle; kalkmadıysa fixture'ı yenile."
    )
