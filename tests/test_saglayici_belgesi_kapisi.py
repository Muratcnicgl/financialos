"""
SAĞLAYICI BELGESİ KAPISI (DOCS-005 — 5 Eylül 2026).

ÖLÇÜLEN ÇELİŞKİ
---------------
Kod **sekiz** LLM sağlayıcısı taşıyor (`_SAGLAYICI_KURUCULARI`'nin yedi anahtarı + koşullu
`ollama`). Belgeler ise başka şeyler söylüyordu:

* `docs/architecture.md` → *"üç implementation (`AnthropicProvider`, `GeminiProvider`,
  `GroqProvider`)"*
* `docs/dev-commands.md` → `LLM_PROVIDER=gemini | anthropic | groq | ollama | fallback`
  (**dördü eksik**) — üstelik aynı belgenin birkaç satır altında `CEREBRAS_MODEL`,
  `TOGETHER_MODEL`, `DEEPINFRA_MODEL` sayılıyordu, yani belge **kendi içinde** de çelişiyordu.

Bu, `.env.example` tuzağının (BUG #317) kardeşidir: bir sağlayıcıyı belgede bulamayan
operatör onu YOK sanar; K1 turunda "zincir tek bacaklı" diye kaydedilen gözlemin bir kısmı
tam olarak bu görünmezlikten geliyordu.

NE ZORLAR
---------
Koddaki her sağlayıcı adı, iki belgede de geçmek zorunda. Yeni bir sağlayıcı eklenip
belge unutulursa süit kırmızı verir — belge, koda BAĞLANIR; hatırlamaya değil (L79).

MUTASYON 2/2 — belgeden bir saglayici adi sil -> ilgili belge testi kirmizi ·
kayit sozlugunu bosalt -> kapsam tabani kirmizi (vakumsal yesil yasagi)
"""
from __future__ import annotations

import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

from app.coach import _SAGLAYICI_KURUCULARI  # noqa: E402

#: `ollama` kayıt sözlüğünde DEĞİL — zincire yalnız `OLLAMA_ENABLED=1` ile eklenir
#: (yerel/egemen yol, LLM-005). Belgede geçmesi yine de şart: operatörün göremediği
#: bir seçenek, var olmayan bir seçenektir.
KOSULLU = ("ollama",)

BELGELER = (
    KOK / "docs" / "architecture.md",
    KOK / "docs" / "dev-commands.md",
)

#: Tarayıcı boşa düşerse kapı geçmez, BOZULUR. Bugün 7 kayıtlı sağlayıcı var.
KAPSAM_TABANI = 5


def _adlar() -> tuple[str, ...]:
    return tuple(_SAGLAYICI_KURUCULARI) + KOSULLU


def test_KAPSAM_TABANI_kayit_bosalirsa_kapi_BOZULUR():
    """Boş bir kayıt sözlüğü 'belgeler tutarlı' anlamına gelmez."""
    assert len(_SAGLAYICI_KURUCULARI) >= KAPSAM_TABANI, (
        f"KAPI BOZUK: yalnız {len(_SAGLAYICI_KURUCULARI)} sağlayıcı bulundu "
        f"(taban {KAPSAM_TABANI}). Kayıt sözlüğü ya da import yolu değişmiş."
    )


def test_HER_saglayici_BELGELERDE_geciyor():
    """Kod ile belge arasındaki tek doğruluk kaynağı KODDUR; belge ona uyar."""
    eksik: dict[str, list[str]] = {}
    for belge in BELGELER:
        metin = belge.read_text(encoding="utf-8").lower()
        yok = [ad for ad in _adlar() if ad not in metin]
        if yok:
            eksik[belge.relative_to(KOK).as_posix()] = yok
    assert not eksik, (
        "Kodda olan ama belgede geçmeyen sağlayıcılar var. Operatörün göremediği bir "
        f"seçenek, var olmayan bir seçenektir (BUG #317'nin kardeşi):\n  {eksik}"
    )
