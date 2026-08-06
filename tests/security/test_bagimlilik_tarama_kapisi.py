"""
BAĞIMLILIK TARAMA KAPISI (BUG #260 / SEC-020 + SEC-021).

ÖLÇÜLEN DEFEKT (7 Ağu 2026)
---------------------------
P2 güvenlik turunda `pip-audit` ELLE koşulmuş ve 23 açık 0'a indirilmişti. Ama:

    grep -rl "pip-audit" .github/   →  0 sonuç

Yani tekrarlayan bir tarama YOKTU. Bağımlılık açıkları **kod değişmeden** ortaya çıkar:
o "0", yazıldığı gün doğruydu ve ertesi gün ölçülmüyordu (**L28**: bir kez yeşil olmak
sürekli yeşil olmak değildir; "çökmedim" başarı değildir).

Bu kapı, taramanın CI'da GERÇEKTEN tanımlı olduğunu ve zamanlanmış koşumun kaldırılmadığını
ölçer. (Taramanın kendisi CI'da koşar; burada onun VARLIĞI teste bağlanır — belgeye değil.)
"""
from __future__ import annotations

from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent.parent
CI = KOK / ".github" / "workflows" / "ci.yml"


@pytest.fixture(scope="module")
def ci_metni() -> str:
    assert CI.exists(), "CI tanımı yok — kapı ölçtüğünü bulamıyor"
    return CI.read_text(encoding="utf-8")


def test_pip_audit_ci_de_tanimli(ci_metni):
    assert "pip-audit" in ci_metni, (
        "Python bağımlılık taraması CI'da yok — SEC-020 yeniden açılır"
    )
    assert "--strict" in ci_metni, "pip-audit uyarıları sessizce geçmemeli (--strict)"


def test_npm_audit_ci_de_tanimli(ci_metni):
    assert "npm audit" in ci_metni, "frontend bağımlılık taraması CI'da yok"
    assert "--audit-level=high" in ci_metni, "npm audit eşiği belirtilmeli"


def test_zamanlanmis_kosum_var(ci_metni):
    """
    Push-tetikli tarama YETMEZ: yeni açık, repoya hiç dokunulmadan yayınlanır. Haftalık
    zamanlanmış koşum bu boşluğu kapatır; kaldırılırsa kapı kırılır.
    """
    assert "schedule:" in ci_metni and "cron:" in ci_metni, (
        "zamanlanmış (haftalık) tarama kaldırılmış — bağımlılık açığı kod değişmeden çıkar"
    )


def test_denetim_isi_ayri_job(ci_metni):
    """Tarama test job'una gömülürse testler kırmızıyken tarama hiç koşmaz (kapsam kaybı)."""
    assert "dependency-audit:" in ci_metni


def test_requirements_sabit_surumlu():
    """
    SEC-021: `>=` pin'li paket, ertesi gün bambaşka bir sürüm kurar (supply-chain).
    Tam sabitleme hedeftir; bugün sabit OLMAYANLAR gerekçeli sayılır ve sayısı ARTAMAZ.
    """
    satirlar = [s.strip() for s in (KOK / "requirements.txt").read_text(encoding="utf-8").splitlines()]
    paketler = [s for s in satirlar if s and not s.startswith("#")]
    assert len(paketler) >= 15, "requirements taraması çökmüş olabilir (kapsam tabanı)"

    esnek = [s for s in paketler if ">=" in s and "==" not in s]
    # Bugün ÖLÇÜLEN gerçek: 9 paket aralıklı pin'li — 4'ü LLM SDK'sı (hızlı sürüm döngüsü),
    # 1'i fiyat kütüphanesi, 4'ü P2'de "en az şu sürüm" diye sabitlenmiş güvenlik tabanı
    # (urllib3/cryptography/idna/pyasn1 — bunlarda tavan koymak eski CVE'ye çivilerdi).
    # Sayı AZALABİLİR, ARTAMAZ: yeni esnek pin eklenirse kapı kırılır (ratchet).
    assert len(esnek) <= 9, (
        "yeni aralıklı (>=) bağımlılık eklendi — supply-chain riski artıyor:\n  "
        + "\n  ".join(esnek)
    )
