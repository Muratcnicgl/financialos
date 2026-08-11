"""
P9 (Wave-9) — BUG #200: sürüm yönetimi.

Sürüm `app/main.py` içinde `"0.1.0"` olarak SABİT yazılıydı ve hiç güncellenmiyordu.
Canlıda "hangi sürüm koşuyor?" sorusunun cevabı yoktu: kullanıcı hata bildirdiğinde
hangi kodun çalıştığı, deploy'un gerçekten güncellendiği, geri alma sonrası hangi
sürüme dönüldüğü ÖLÇÜLEMİYORDU. Yayın yönetiminin (P9) ön koşuludur.

Kilitlenen sözleşme: tek sürüm kaynağı, CHANGELOG ile senkron, sağlık ucundan görünür,
build commit'i enjekte edilebilir.
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.version import APP_VERSION, build_commit, full_version

_ROOT = Path(__file__).resolve().parent.parent


def test_surum_tek_kaynaktan_gelir():
    """main.py'de sabit sürüm string'i KALMAMALI (drift kaynağı)."""
    src = (_ROOT / "app" / "main.py").read_text(encoding="utf-8")
    assert 'version="0.1.0"' not in src, "main.py'de sabit sürüm hâlâ var"
    assert "_APP_VERSION" in src


def test_saglik_ucu_surum_ve_build_doner():
    c = TestClient(app)
    body = c.get("/api/health").json()
    assert body["version"] == APP_VERSION
    assert "build" in body, "Sağlık ucunda build commit'i yok (deploy doğrulanamaz)"


def test_build_commit_enjekte_edilebilir(monkeypatch):
    """BUG #294: env artık YALNIZ git çalışma kopyası yokken (konteyner imajı) geçerli.

    Eskiden bu test env'i tek kaynak sayıyordu; o sözleşme canlıda damganın donmasına
    yol açtı (`build: 6d3bf26abd62` derken kod `fc10e0b`di). Sözleşme değişti, test de
    onunla birlikte: enjeksiyon hâlâ çalışır ama git'i EZMEZ.
    """
    import app.version as surum
    monkeypatch.setattr(surum, "_git_commit", lambda: "")     # .git yok (konteyner)
    surum.build_commit.cache_clear()
    monkeypatch.setenv("BUILD_COMMIT", "abcdef1234567890")
    assert surum.build_commit() == "abcdef123456"             # 13 karaktere kısalır
    assert APP_VERSION in full_version()
    surum.build_commit.cache_clear()


def test_build_commit_yoksa_bilinmiyor(monkeypatch):
    import app.version as surum
    monkeypatch.setattr(surum, "_git_commit", lambda: "")
    surum.build_commit.cache_clear()
    monkeypatch.delenv("BUILD_COMMIT", raising=False)
    assert surum.build_commit() == "bilinmiyor"
    surum.build_commit.cache_clear()


def test_changelog_surumle_senkron():
    """CHANGELOG'da yayınlanmayan bir sürümü canlıya çıkarmak = izlenemez yayın."""
    ch = (_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"[{APP_VERSION}]" in ch, (
        f"CHANGELOG.md'de [{APP_VERSION}] girdisi yok — sürüm yükseltildi ama not yazılmadı"
    )


def test_surum_semver_formatinda():
    assert re.fullmatch(r"\d+\.\d+\.\d+", APP_VERSION), f"SemVer değil: {APP_VERSION}"


def test_changelog_bilinen_sinirlari_belgeler():
    """Yayın notu yalnız iyi haberi değil, BİLİNEN SINIRLARI da söylemeli."""
    ch = (_ROOT / "CHANGELOG.md").read_text(encoding="utf-8").lower()
    assert "bilinen sınırlar" in ch
