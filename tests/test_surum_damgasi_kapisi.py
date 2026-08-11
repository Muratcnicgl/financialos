"""
SÜRÜM DAMGASI KAPISI — BUG #294.

ÖLÇÜLEN DEFEKT (11 Ağu 2026, canlı beta): `GET /api/health` `build: 6d3bf26abd62`
diyordu; o sırada çalışan kod `fc10e0b`di. Damga, var olmasının TEK sebebi olan soruya
— *hangi kod koşuyor?* — yanlış cevap veriyordu.

Kök neden: `build_commit()` yalnız `BUILD_COMMIT` env değişkenini okuyordu ve o değişken
`.env`'de **elle** tutuluyordu. Bu makinedeki kapalı beta "git pull + yeniden başlat" ile
güncelleniyor; kimse `.env`'i düzeltmediği için damga deploy'dan deploy'a donuyordu.

DERS (L57): bir alanın DOLU olması, DOĞRU olduğunu göstermez. Elle güncellenen bir
kimlik alanı, güncellenmediği ilk günden itibaren yanlış cevap üretmeye başlar ve bunu
hiçbir şey haber vermez — çünkü alan doludur, boş değildir. Kimliği, kimliğin sahibinden
(burada `.git`) türet.

Sözleşme:
  1. Git çalışma kopyasından koşuluyorsa damga GERÇEK HEAD'i gösterir (env'i dinlemez).
  2. Git yoksa (konteyner imajı) env doğru kaynaktır — fallback korunur.
  3. Hiçbiri yoksa "bilinmiyor" — sessizce boş/yanıltıcı bir değer değil.
  4. Çalışma kopyası kirliyse `+` ile işaretlenir: commit edilmemiş değişiklikle koşmak,
     o commit'i koşmakla aynı şey değildir.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app import version as surum

KOK = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _onbellegi_temizle():
    """`build_commit` süreç ömrü boyunca önbelleklenir; her test taze hesaplasın."""
    surum.build_commit.cache_clear()
    yield
    surum.build_commit.cache_clear()


def _gercek_head() -> str | None:
    if not (KOK / ".git").exists():
        return None
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=KOK,
                       capture_output=True, text=True)
    return r.stdout.strip()[:12] if r.returncode == 0 else None


def test_damga_git_head_ile_ayni(monkeypatch):
    """KÖK DEFEKT: env ne derse desin, git varsa damga GERÇEK kodu gösterir."""
    head = _gercek_head()
    if head is None:
        pytest.skip("git çalışma kopyası yok (konteyner ortamı)")

    # Bayat bir env değeri — canlıda tam olarak bu vardı
    monkeypatch.setenv("BUILD_COMMIT", "6d3bf26abd62")
    damga = surum.build_commit()

    assert damga.rstrip("+") == head, (
        f"BUG #294: damga '{damga}' ama çalışan kod '{head}' — sürüm damgası, hangi kodun "
        f"koştuğu sorusuna yanlış cevap veriyor."
    )


def test_git_yoksa_env_kullanilir(monkeypatch):
    """Konteyner imajında `.git` yoktur; orada env doğru kaynaktır."""
    monkeypatch.setattr(surum, "_git_commit", lambda: "")
    monkeypatch.setenv("BUILD_COMMIT", "a1b2c3d4e5f6")
    assert surum.build_commit() == "a1b2c3d4e5f6"


def test_hicbiri_yoksa_bilinmiyor(monkeypatch):
    """Damga uydurulmaz: kaynak yoksa bunu AÇIKÇA söyler."""
    monkeypatch.setattr(surum, "_git_commit", lambda: "")
    monkeypatch.delenv("BUILD_COMMIT", raising=False)
    assert surum.build_commit() == "bilinmiyor"


def test_kirli_calisma_kopyasi_isaretlenir(monkeypatch):
    """Commit edilmemiş değişiklikle koşmak, o commit'i koşmak değildir.

    Mutasyon dersi: bu test önce `_git_commit`'i mock'luyordu — yani `+` işaretini KOYAN
    kodu hiç çalıştırmıyor, kendi mock'unun döndürdüğü stringi doğruluyordu. İşaret
    kaldırıldığında test yeşil kalıyordu. Mock artık bir alt katmanda (`subprocess.run`):
    gerçek dallanma koşuyor.
    """
    class _Sonuc:
        def __init__(self, stdout): self.returncode, self.stdout = 0, stdout

    def _sahte_git(komut, **kw):
        if "rev-parse" in komut:
            return _Sonuc("abc123def4567890\n")
        return _Sonuc(" M app/version.py\n")     # kirli çalışma kopyası

    monkeypatch.setattr(surum.subprocess, "run", _sahte_git)
    assert surum._git_commit() == "abc123def456+"


def test_temiz_calisma_kopyasi_isaretlenmez(monkeypatch):
    """Ters yön: temizken `+` KOYULMAMALI — aksi hâlde işaret bilgi taşımaz."""
    class _Sonuc:
        def __init__(self, stdout): self.returncode, self.stdout = 0, stdout

    def _sahte_git(komut, **kw):
        return _Sonuc("abc123def4567890\n" if "rev-parse" in komut else "")

    monkeypatch.setattr(surum.subprocess, "run", _sahte_git)
    assert surum._git_commit() == "abc123def456"


def test_git_bozuksa_cokmez(monkeypatch):
    """Sürüm ucu, git'in çalışmamasından ötürü 500 vermemeli."""
    def _patlat(*a, **kw):
        raise OSError("git yok")
    monkeypatch.setattr(surum.subprocess, "run", _patlat)
    monkeypatch.setenv("BUILD_COMMIT", "f0e1d2c3b4a5")
    assert surum.build_commit() == "f0e1d2c3b4a5"


def test_saglik_ucu_damgayi_yayinlar():
    """Uçtan uca: /api/health'in `build` alanı bu tek kaynaktan gelir."""
    from fastapi.testclient import TestClient
    from app.main import app

    govde = TestClient(app).get("/api/health").json()
    assert govde["build"] == surum.build_commit()
    assert govde["version"] == surum.APP_VERSION


def test_damga_her_cagrida_git_calistirmaz(monkeypatch):
    """Sağlık ucu sıcak yoldur; her istekte alt süreç açmak kabul edilemez."""
    sayac = {"n": 0}

    def _sayan():
        sayac["n"] += 1
        return "abc123def456"

    monkeypatch.setattr(surum, "_git_commit", _sayan)
    surum.build_commit.cache_clear()
    for _ in range(5):
        surum.build_commit()
    assert sayac["n"] == 1, f"git {sayac['n']} kez çalıştırıldı — önbellek çalışmıyor"
