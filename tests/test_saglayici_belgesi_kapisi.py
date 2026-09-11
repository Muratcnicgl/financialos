"""
DEVOPS-015 / BUG #393 KAPISI — SAĞLAYICI LİSTESİ BELGELERDE SÜRÜKLENİYORDU.

Ölçülen (11 Eyl 2026): `.env.example` ↔ kod iki yönde zaten kapılı (`test_env_adi_kapisi`:
her örnek anahtar okunuyor, her okunan anahtar belgeli). Sürüklenen şey ANLATIMDI: README
"four providers" diyordu, `.env.example` yorumu dört ad sayıyordu; kod 8 önek tanıyor ve
zincir 6 halka. PROJE.md artık sağlayıcı listesi taşımıyor (grep: 0).

Kilitlenen: README ve `.env.example`'daki `LLM_PROVIDER` anlatımı, `SAGLAYICI_ONEKLERI`
(tek sağlayıcı adları) ve `_ZINCIR_SIRASI` (zincir sırası) ile aynı — kaynaktan türetilir.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.coach import SAGLAYICI_ONEKLERI, _ZINCIR_SIRASI

KOK = Path(__file__).resolve().parent.parent
BELGELER = ("README.md", ".env.example")


def _llm_provider_paragrafi(metin: str) -> str:
    """`LLM_PROVIDER` geçen satır ve etrafındaki 4'er satır."""
    satirlar = metin.splitlines()
    i = next((k for k, s in enumerate(satirlar) if "LLM_PROVIDER" in s and "fallback" in s), None)
    assert i is not None, "LLM_PROVIDER=fallback anlatımı yok"
    return "\n".join(satirlar[max(0, i - 4): i + 5])


@pytest.mark.parametrize("dosya", BELGELER)
def test_tek_saglayici_adlari_kodla_ayni(dosya):
    p = _llm_provider_paragrafi((KOK / dosya).read_text(encoding="utf-8"))
    m = re.search(r"([a-z]+(?:\s*\|\s*[a-z]+){3,})", p)
    assert m, f"{dosya}: 'a | b | c' biçiminde sağlayıcı listesi yok"
    belgede = [x.strip() for x in m.group(1).split("|")]
    assert belgede == [o.lower() for o in SAGLAYICI_ONEKLERI], (
        f"{dosya}: belge {belgede} ≠ kod {[o.lower() for o in SAGLAYICI_ONEKLERI]}")


@pytest.mark.parametrize("dosya", BELGELER)
def test_zincir_sirasi_kodla_ayni(dosya):
    p = _llm_provider_paragrafi((KOK / dosya).read_text(encoding="utf-8"))
    m = re.search(r"([a-z]+(?:\s*(?:>|→)\s*[a-z]+){3,})", p)
    assert m, f"{dosya}: 'a > b > c' / 'a → b → c' biçiminde zincir yok"
    belgede = [x.strip() for x in re.split(r">|→", m.group(1))]
    assert belgede == list(_ZINCIR_SIRASI), f"{dosya}: zincir {belgede} ≠ kod {list(_ZINCIR_SIRASI)}"


def test_kapsam_tabani():
    assert len(SAGLAYICI_ONEKLERI) >= 6 and len(_ZINCIR_SIRASI) >= 4, "listeler daraldı — kapı anlamını yitirmesin (L45)"
