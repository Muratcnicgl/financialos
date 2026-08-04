"""
P4 (Wave-9) — BUG #191: hukuki metinler CANLIDA ERİŞİLEMEZDİ + envanter kod ile bağlanmadı.

Login ekranı KVKK metnine `/docs/legal/...md` ile bağlanıyordu; prod imajında `docs/`
klasörü YOK (Dockerfile kopyalamıyordu, .dockerignore hariç tutuyordu) ve nginx SPA
fallback'i bu yolu index.html'e düşürüyordu → kullanıcı **rıza verdiği metni okuyamıyordu**.
KVKK aydınlatma yükümlülüğü fiilen karşılanmıyordu.

Bu dosya üç şeyi kilitler:
  1. Zorunlu belgeler var ve API'den kimlik gerekmeden okunabiliyor.
  2. Belgeler prod imajına giriyor (Dockerfile + .dockerignore istisnası).
  3. Veri-işleyen envanteri KODLA tutarlı: kodda tanımlı LLM sağlayıcıları envanterde yazılı.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def client():
    return TestClient(app)


ZORUNLU_BELGELER = ["kvkk", "gizlilik", "kullanim-sartlari", "veri-isleyenler"]


@pytest.mark.parametrize("slug", ZORUNLU_BELGELER)
def test_belge_kimliksiz_okunabilir(client, slug):
    """Rıza METNİ, rıza VERİLMEDEN önce okunabilmeli → kimlik doğrulama istenmez."""
    r = client.get(f"/api/legal/{slug}")
    assert r.status_code == 200, f"{slug} okunamadı: {r.status_code}"
    body = r.json()
    assert len(body["content"]) > 500, f"{slug} içeriği şüpheli derecede kısa"


def test_belge_listesi_doner(client):
    r = client.get("/api/legal")
    assert r.status_code == 200
    slugs = [d["slug"] for d in r.json()["documents"]]
    for zorunlu in ZORUNLU_BELGELER:
        assert zorunlu in slugs


def test_bilinmeyen_slug_404(client):
    assert client.get("/api/legal/olmayan-belge").status_code == 404


def test_slug_ile_dosya_yolu_kurulamaz(client):
    """Path traversal yüzeyi: slug listesi SABİT olmalı, dosya adı kullanıcıdan gelmemeli."""
    for kotucul in ("../../requirements.txt", "..%2f..%2frequirements.txt"):
        r = client.get(f"/api/legal/{kotucul}")
        assert r.status_code in (404, 400), f"Şüpheli yanıt: {r.status_code}"


def test_belgeler_prod_imajina_giriyor():
    """BUG #191 kök nedeni: imajda olmayan belge = erişilemeyen belge."""
    dockerfile = (_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "docs/legal" in dockerfile, "Dockerfile hukuki metinleri imaja kopyalamıyor"
    di = (_ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "!docs/legal" in di, ".dockerignore docs/legal istisnası yok → COPY boş kalır"


def test_kullanim_sartlari_tavsiye_degildir_uyarisi_icerir(client):
    """Finansal ürün için zorunlu: 'yatırım tavsiyesi değildir' açıkça yazmalı."""
    icerik = client.get("/api/legal/kullanim-sartlari").json()["content"].lower()
    assert "tavsiye" in icerik and "değildir" in icerik
    assert "spk" in icerik, "Lisans durumu (SPK) açıkça belirtilmemiş"


def test_envanter_koddaki_llm_saglayicilarini_listeler():
    """Veri-işleyen envanteri KODLA tutarlı olmalı (yeni sağlayıcı eklenip yazılmazsa kırılır)."""
    envanter = (_ROOT / "docs" / "legal" / "veri-isleyen-envanteri.md").read_text(encoding="utf-8").lower()
    for saglayici in ("gemini", "groq", "anthropic", "ollama"):
        assert saglayici in envanter, f"Envanterde {saglayici} yok — KVKK aydınlatması eksik"


def test_riza_surumu_yayinlanan_metinle_ayni():
    """`kvkk_consent_version` DB'ye yazılır; yayınlanan metinle aynı sürüm olmalı."""
    from app.routers.auth import KVKK_CONSENT_VERSION
    from app.routers.legal import BELGELER
    dosya = BELGELER["kvkk"][0]
    assert KVKK_CONSENT_VERSION in dosya, (
        f"Rıza sürümü ({KVKK_CONSENT_VERSION}) yayınlanan metinle ({dosya}) uyuşmuyor"
    )
