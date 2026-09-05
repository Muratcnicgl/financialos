"""
ÖLÜ STATE KAPISI (FE-012 / BUG #355 — 5 Eylül 2026).

ÖLÇÜLEN OLAY
------------
`App.jsx`'te şu satır vardı:

    const [usagePct, setUsagePct] = useState(0);

ve `setUsagePct` **depoda hiçbir yerde çağrılmıyordu.** State 0'da doğuyor, 0'da kalıyordu.
Sonuç: başlıkta HER kullanıcıya kalıcı olarak **"0%"** gösteren bir rozet — canlı bir ölçüm
gibi duran, aslında sabit bir sayı. Rengi belirleyen mantık (`>80` kırmızı, `>50` sarı)
hiçbir zaman tetiklenemiyordu.

Daha da can sıkıcısı: rozetin **verisi zaten vardı**. `/api/coach/usage` ucu
`today_count`/`daily_limit`/`percentage` döndürüyor, `api.js`'te `coachApi.usage()`
sarmalayıcısı yazılı, ve ucun kendi docstring'i *"Cockpit panelinin üst köşesindeki
'API kullanım: %42' rozetini bundan çekecek"* diyor. Yani sözleşme yazılmış, **çağıran
hiç eklenmemişti** — ve ürün bunu bir hata olarak değil, bir SAYI olarak gösterdi.

Bu, ölü kod kapısının frontend karşılığıdır (`scripts/olu_kod_kapisi.py` yalnız `app/`
altındaki Python'a bakar) ve depoda frontend statik analizi yoktur (BUG #351).

NE ZORLAR
---------
`frontend/src` altında `const [x, setX] = useState(...)` yazılıp `setX` hiç çağrılmıyorsa
kapı düşer. İki doğru cevabı vardır: (1) setter'ı gerçekten bağla — veri çoğu zaman zaten
vardır; (2) state'i sil ve sabiti doğrudan yaz. Üçüncü bir yol — "dursun, sonra bağlarız" —
kullanıcıya uydurma bir sayı göstermek demektir.

Ölçüm (5 Eyl 2026): **300 `useState` çiftinden ölü setter sayısı 0.**

MUTASYON 3/3 — sentetik olu setter sok · GERCEK dosyada setter cagrisini sil ·
tarayiciyi korlestir. Ucuncusu kapinin KENDI KOR NOKTASINI buldurdu: yorumlar sayiliyordu.
"""
from __future__ import annotations

import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
KAYNAK = KOK / "frontend" / "src"

_CIFT = re.compile(r"const\s*\[\s*(\w+)\s*,\s*(set\w+)\s*\]\s*=\s*useState")

#: Tarayıcı boşa düşerse kapı geçmez, BOZULUR (bugün 300 çift var).
KAPSAM_TABANI = 100


def _dosyalar() -> list[Path]:
    return [p for p in sorted(KAYNAK.rglob("*.jsx")) if ".test." not in p.name]


def _ciftler(dosyalar: list[Path] | None = None) -> int:
    n = 0
    for yol in (dosyalar if dosyalar is not None else _dosyalar()):
        n += len(_CIFT.findall(_kodsuz(yol.read_text(encoding="utf-8"))))
    return n


def _kodsuz(metin: str) -> str:
    """Yorum satırlarını atar.

    KAPININ KENDİ KÖR NOKTASI (ölçülerek bulundu): ilk yazımda yorumlar da sayılıyordu.
    `App.jsx`'in düzeltme notu `setUsagePct` kelimesini geçirdiği için, o setter'ın
    ÇAĞRISI silinse bile sayaç 2'de kalıyor ve kapı ateş etmiyordu. Yani kapı, kendi
    hikâyesini anlatan yorum yüzünden kör kalıyordu — L67'nin birebir tekrarı, bu kez
    kapının kendi içinde. Mutasyon bunu ortaya çıkardı.
    """
    return "\n".join(s for s in metin.splitlines()
                     if not s.lstrip().startswith(("//", "*", "/*")))


def _olu_setterlar(dosyalar: list[Path] | None = None) -> list[str]:
    out: list[str] = []
    for yol in (dosyalar if dosyalar is not None else _dosyalar()):
        metin = yol.read_text(encoding="utf-8")
        kod = _kodsuz(metin)
        for m in _CIFT.finditer(kod):
            setter = m.group(2)
            # Tanım satırındaki geçiş de sayılır; 1 ise BAŞKA hiçbir yerde kullanılmıyor.
            if len(re.findall(r"\b" + re.escape(setter) + r"\b", kod)) <= 1:
                try:
                    ad = yol.relative_to(KOK).as_posix()
                except ValueError:
                    ad = yol.name
                out.append(f"{ad}: {setter}")
    return out


def test_KAPSAM_TABANI_tarayici_bozuksa_kapi_BOZULUR():
    """Hiç `useState` bulamayan bir tarayıcı 'ölü state yok' diyemez."""
    n = _ciftler()
    assert n >= KAPSAM_TABANI, (
        f"KAPI BOZUK: yalnız {n} `useState` çifti tarandı (taban {KAPSAM_TABANI})."
    )


def test_HICBIR_state_SETTERI_olu_kalamaz():
    """FE-012 regresyon kilidi."""
    olu = _olu_setterlar()
    assert not olu, (
        "Bu state'lerin setter'ı hiçbir yerde çağrılmıyor; yani değer BAŞLANGIÇTA "
        "donuyor ve arayüz onu canlı bir ölçüm gibi gösteriyor olabilir:\n  "
        + "\n  ".join(olu)
        + "\n\nİki doğru cevap: setter'ı gerçekten bağla (veri çoğu zaman zaten vardır), "
          "ya da state'i sil. Üçüncüsü — bırakmak — kullanıcıya uydurma bir sayı göstermektir."
    )


def test_KAPI_sentetik_ornekleri_ayirir(tmp_path):
    """MUTASYON: ölü setter yakalanır, kullanılan setter geçer."""
    olu = tmp_path / "Olu.jsx"
    olu.write_text("const [a, setA] = useState(0);\nreturn <span>{a}</span>;\n", encoding="utf-8")
    assert _olu_setterlar([olu]), "Kapı ölü setter'ı kaçırdı"

    canli = tmp_path / "Canli.jsx"
    canli.write_text("const [a, setA] = useState(0);\nuseEffect(() => setA(5), []);\n",
                     encoding="utf-8")
    assert not _olu_setterlar([canli]), "Kapı kullanılan setter'ı ölü sandı"
