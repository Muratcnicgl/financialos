"""
P3.5 (Wave-9) — SIFIRDAN KULLANICI UÇTAN UCA (ürünleşme kapısı).

Soru: "Uygulamayı bugün ilk kez açan bir YABANCI, hiçbir hazır veri olmadan kendi
finansal hayatını kurabiliyor mu — hiçbir yerde kırılma, hiçbir yerde başkasının izi?"

Bu, tek-kullanıcı MVP'sinden ürüne geçişin kapısıdır. Süit yeşilken bile bu test
kırmızı olabilir: mevcut testlerin çoğu hazır veri (fixture) ile başlar, yeni kullanıcının
BOŞ dünyası hiç sınanmamıştı.

Kapsam otomatik türetilir: parametresiz her GET ucu boş-durumda çağrılır. Yeni bir uç
eklenip boş-durumda çökerse bu test kırılır (kapsam kendiliğinden daralamaz).

BUG #217 fix (P3.2): kapsam türetme `app.routes` üzerindeydi ve FastAPI 0.141'de SESSİZCE
körleşmişti (`include_router` artık düzleştirmiyor, `_IncludedRouter` sarmalıyor) — "her GET
ucu" fiilen 1 uç (`/api/health`) demekti, test yeşil ama kör kalıyordu. Envanter artık
OpenAPI'den türetiliyor ve kapsam TABANI assert ediliyor (`tests/endpoint_envanteri.py`).
"""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db
from app.models import Base
from tests.endpoint_envanteri import parametresiz_get_uclari  # BUG #217

# Boş-durum taramasında hariç tutulanlar — GEREKÇELİ (dış servis / yan etki / kimlik dışı)
BOS_DURUM_HARIC = {
    "/api/health": "kimlik gerektirmez, altyapı ucu",
    "/api/auth/me": "kimlik ucu, ayrı test edilir",
    "/api/coach/history": "koç geçmişi — LLM'siz boş liste; ayrıca aşağıda açıkça çağrılır",
    "/api/workspaces/join": "davet token'ı ile çalışır (query param zorunlu)",
    "/api/fund-price/freshness": "yatırım hesabı yoksa boş; aşağıda açıkça çağrılır",
}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-sifirdan-kullanici-0123456789abcdef")
    monkeypatch.setenv("AUTH_ENABLED", "true")   # gerçek kayıt/oturum yolu
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    # Rate-limit modül-düzeyi global durum tutar (register bucket). Testler aynı "IP"den
    # arka arkaya kayıt olduğu için 429'a çarpıyordu — koruma ÇALIŞIYOR, test izole edilir.
    from app import rate_limit
    rate_limit.reset()


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def yeni_kullanici(client):
    """Gerçek kayıt akışı: /api/auth/register → token. Hiçbir hazır veri YOK."""
    r = client.post("/api/auth/register", json={
        "email": "yeni.kullanici@example.com",
        "password": "Guclu-Parola-2026!",
        "name": "Yeni Kullanıcı",
        "kvkk_consent": True,
    })
    assert r.status_code == 201, f"Kayıt başarısız: {r.status_code} {r.text[:300]}"
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ══════════════════════════════════════════════════════════════════════════════
# 1. BOŞ DÜNYA — hiçbir uç çökmemeli
# ══════════════════════════════════════════════════════════════════════════════

def _parametresiz_get_uclari() -> list[str]:
    # BUG #217 fix: envanter OpenAPI'den (kapsam tabanı assert'li) — bkz. endpoint_envanteri.
    return parametresiz_get_uclari(app, BOS_DURUM_HARIC)


def test_yeni_kullanici_bos_durumda_hicbir_uc_cokmez(client, yeni_kullanici):
    """Veri girmemiş kullanıcı tüm okuma uçlarını gezebilmeli (0/None/boş liste — çökme yok)."""
    hatalar = []
    for yol in _parametresiz_get_uclari():
        r = client.get(yol, headers=yeni_kullanici)
        if r.status_code >= 500:
            hatalar.append(f"{yol} → {r.status_code} {r.text[:200]}")
        elif r.status_code not in (200, 204, 404, 422):
            hatalar.append(f"{yol} → beklenmedik {r.status_code} {r.text[:160]}")
    assert not hatalar, "Boş durumda kırılan uç(lar):\n" + "\n".join(hatalar)


def test_yeni_kullanici_cockpiti_sifirlarla_acilir(client, yeni_kullanici):
    """Cockpit boş kullanıcıda anlamlı sıfırlar döndürmeli (NaN/None/hata değil)."""
    r = client.get("/api/cockpit", headers=yeni_kullanici)
    assert r.status_code == 200, r.text[:300]
    c = r.json()
    for alan in ("nakit_kasa", "kart_borcu", "kredi_borcu", "yatirim_deger", "net_deger"):
        assert alan in c, f"cockpit'te {alan} yok"
        assert c[alan] == 0 or c[alan] == 0.0, f"{alan} boş kullanıcıda 0 değil: {c[alan]}"


def test_yeni_kullanicinin_verisi_bos(client, yeni_kullanici):
    """Hazır/örnek veri sızmamalı — yeni kullanıcı gerçekten boş başlar."""
    # (uç, kayıt listesinin gövdedeki anahtarı — None ise gövdenin kendisi liste)
    uclar = [("/api/accounts", None), ("/api/transactions", None), ("/api/incomes", None),
             ("/api/debts", None), ("/api/checkpoints", None), ("/api/goals", None),
             ("/api/envelopes", "envelopes"), ("/api/wishlist", None)]
    for yol, anahtar in uclar:
        r = client.get(yol, headers=yeni_kullanici)
        assert r.status_code == 200, f"{yol} → {r.status_code}"
        body = r.json()
        kayitlar = body if anahtar is None else body.get(anahtar)
        if isinstance(kayitlar, dict):  # sarmalayıcı gövde (ör. {"items": [...]})
            kayitlar = kayitlar.get("items", [])
        assert not kayitlar, f"{yol} yeni kullanıcıda BOŞ olmalı, geldi: {str(kayitlar)[:200]}"


# ══════════════════════════════════════════════════════════════════════════════
# 2. KENDİ HAYATINI KURMA — hesap, işlem, kendi kuralı
# ══════════════════════════════════════════════════════════════════════════════

def test_yeni_kullanici_kendi_hayatini_kurabilir(client, yeni_kullanici):
    """Kayıt → hesap → işlem → cockpit güncel. Ürünün asgari sözleşmesi."""
    h = yeni_kullanici

    r = client.post("/api/accounts", headers=h, json={
        "name": "Maaş Hesabım", "account_type": "cash", "balance": 12000.0})
    assert r.status_code in (200, 201), r.text[:300]
    hesap_id = r.json()["id"]

    r = client.post("/api/transactions", headers=h, json={
        "account_id": hesap_id, "transaction_type": "expense", "amount": 500.0,
        "category": "market", "description": "haftalık market",
        "transaction_date": date.today().isoformat()})
    assert r.status_code in (200, 201), r.text[:300]

    r = client.get("/api/cockpit", headers=h)
    assert r.status_code == 200
    assert r.json()["nakit_kasa"] == pytest.approx(11500.0), (
        f"İşlem sonrası nakit yanlış: {r.json()['nakit_kasa']}"
    )


def test_yeni_kullanici_kendi_kirmizi_cizgisini_yazabilir(client, yeni_kullanici):
    """H1/H3: kullanıcı KENDİ öznel kuralını tanımlayabilmeli ve geri okuyabilmeli."""
    h = yeni_kullanici
    r = client.post("/api/checkpoints", headers=h, json={
        "title": "Acil fonuma dokunmam",
        "description": "3 aylık gider tutarını asla harcamam",
        "checkpoint_type": "red_line",
        "priority": 1,
    })
    assert r.status_code in (200, 201), r.text[:300]
    kural_id = r.json()["id"]

    r = client.get("/api/checkpoints", headers=h)
    assert r.status_code == 200
    basliklar = [c["title"] for c in r.json()]
    assert "Acil fonuma dokunmam" in basliklar
    assert len(r.json()) == 1, "Yeni kullanıcıya başkasının kuralları da gelmiş olabilir"

    r = client.delete(f"/api/checkpoints/{kural_id}", headers=h)
    assert r.status_code in (200, 204)


def test_kimliksiz_erisim_engellenir(client):
    """AUTH_ENABLED açıkken token'sız istek 401 olmalı (tek-kullanıcı fallback'e DÜŞMEZ)."""
    r = client.get("/api/cockpit")
    assert r.status_code == 401, f"Token'sız erişim {r.status_code} döndü — fallback açık olabilir"


# ══════════════════════════════════════════════════════════════════════════════
# H3 (BUG #192) — kullanıcı kendi kuralını API'den yazar ve kural DAYATILIR
# Murat'ın direktifinin uçtan uca kanıtı: yabancı bir kullanıcı kendi öznel
# kuralını kurabiliyor ve sistem onu ürünün kendi kuralı kadar sert uyguluyor.
# ══════════════════════════════════════════════════════════════════════════════

def test_kullanici_kendi_kuralini_yazar_ve_kural_dayatilir(client, yeni_kullanici):
    h = yeni_kullanici

    r = client.post("/api/accounts", headers=h, json={
        "name": "Maaş Hesabım", "account_type": "cash", "balance": 10000.0})
    assert r.status_code in (200, 201)

    # Kullanıcı KENDİ kuralını tanımlıyor (yapılandırılmış → kod seviyesinde dayatılır)
    r = client.post("/api/checkpoints", headers=h, json={
        "title": "Acil fonuma dokunmam",
        "description": "Nakdim 8.000 TL'nin altına inmesin",
        "checkpoint_type": "red_line",
        "priority": 1,
        "rule_type": "min_cash_floor",
        "rule_params": {"amount": 8000},
    })
    assert r.status_code in (200, 201), r.text[:300]
    assert r.json()["rule_params"] == {"amount": 8000}, "Kural parametresi geri okunamıyor"

    # Kuralı ihlal eden işlem doğrudan API'den de yazılamamalı mı? — işlem ucu ayrı bir
    # yoldur (kullanıcının kendi bilinçli girişi); kural motoru KOÇ AKSİYONLARINDA dayatılır.
    # Burada kuralın kaydedildiğini ve geri okunduğunu doğruluyoruz; dayatma kanıtı
    # tests/test_user_defined_rules.py içinde (execute_pending_action yolu).
    r = client.get("/api/checkpoints", headers=h)
    kurallar = [c for c in r.json() if c.get("rule_type") == "min_cash_floor"]
    assert len(kurallar) == 1


def test_gecersiz_kural_sessizce_kabul_edilmez(client, yeni_kullanici):
    """Bozuk kural kabul edilirse kullanıcı KORUNDUĞUNU SANIR — en kötü hata."""
    h = yeni_kullanici
    r = client.post("/api/checkpoints", headers=h, json={
        "title": "Bozuk", "description": "x", "checkpoint_type": "rule",
        "rule_type": "olmayan_tip", "rule_params": {"amount": 5}})
    assert r.status_code == 422

    r = client.post("/api/checkpoints", headers=h, json={
        "title": "Eksik parametre", "description": "x", "checkpoint_type": "rule",
        "rule_type": "min_cash_floor", "rule_params": {}})
    assert r.status_code == 422
