"""
FRONTEND YOKLAMA KAPISI (PERF-008 — 5 Eylül 2026).

ÖLÇÜLEN DURUM
-------------
`App.jsx`'in `useBackendHealth` kancası koşulsuz `setInterval(check, 5000)` kuruyordu:
arka plana atılmış bir sekme **saatte 720 istek** üretiyor ve o isteklerin hiçbirinin bakan
bir gözü olmuyordu. Mobil/PWA hedefi olan bir üründe bu doğrudan **pil ve veri** demek —
ve kullanıcı bunu hiçbir zaman göremez, çünkü belirtisi yok.

Düzeltme aralığı DEĞİŞTİRMEDİ (görünürken hâlâ 5 sn; tepkiselliği düşürmek ayrı bir karar
olurdu): yalnız sekme gizliyken yoklama duruyor ve sekme geri geldiğinde anında bir ölçüm
yapılıyor, böylece kullanıcı bayat bir "çevrimdışı" rozetiyle karşılaşmıyor.

NEDEN KAYNAK SEVİYESİNDE ÖLÇÜLÜYOR (dürüst sınır)
--------------------------------------------------
`useBackendHealth` dışa aktarılmıyor; davranışsal bir test için ya kancayı dışa aktarmak ya
da tüm `App`'i render etmek gerekirdi. Frontend'de statik analiz de yok (BUG #351). Bu kapı
bu yüzden **kaynak seviyesinde** çalışır: zayıf bir kilittir ama YOKLUKTAN iyidir ve asıl
işi bir sonraki yoklamayı yakalamaktır — bugünkü tek örneği korumak değil.

NE ZORLAR
---------
`frontend/src` altında `setInterval` ile yoklama kuran her dosya, aynı dosyada bir
`visibilitychange` kaydı taşımak zorundadır. Gerçekten koşulsuz koşması gereken bir zamanlayıcı
varsa (ör. bir geri sayım) `// yoklama-muaf: <gerekçe>` yazılır — gerekçesiz muafiyet yok.

MUTASYON 2/2 — visibilitychange kaydini sil -> kapi kirmizi (nedensellik) ·
tarayiciyi korlestir -> kapsam tabani kirmizi (vakumsal yesil yasagi)
"""
from __future__ import annotations

from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
KAYNAK = KOK / "frontend" / "src"

_MUAF = "yoklama-muaf:"

#: Tarayıcı boşa düşerse kapı geçmez, BOZULUR (bugün 60'tan fazla kaynak var).
KAPSAM_TABANI = 30


def _dosyalar() -> list[Path]:
    return [p for p in sorted(KAYNAK.rglob("*"))
            if p.suffix in {".jsx", ".js"} and ".test." not in p.name]


def _ihlaller(dosyalar: list[Path] | None = None) -> list[str]:
    out: list[str] = []
    for yol in (dosyalar if dosyalar is not None else _dosyalar()):
        metin = yol.read_text(encoding="utf-8")
        # Yorum satırlarındaki `setInterval(` geçişleri sayılmaz: bu dosyada düzeltmenin
        # GEREKÇESİ de `setInterval` kelimesini içeriyor ve kapı kendi açıklamasını
        # ihlal sanmamalı (L67 — bir kapı kendi belgesiyle kör/kırmızı olamaz).
        kurulum_var = any(
            "setInterval(" in s and not s.lstrip().startswith(("//", "*", "/*"))
            for s in metin.splitlines()
        )
        if not kurulum_var:
            continue
        if _MUAF in metin or "visibilitychange" in metin:
            continue
        try:
            ad = yol.relative_to(KOK).as_posix()
        except ValueError:
            ad = yol.name
        out.append(ad)
    return out


def test_KAPSAM_TABANI_tarayici_bozuksa_kapi_BOZULUR():
    dosyalar = _dosyalar()
    assert len(dosyalar) >= KAPSAM_TABANI, (
        f"KAPI BOZUK: yalnız {len(dosyalar)} frontend kaynağı tarandı (taban {KAPSAM_TABANI})."
    )


def test_YOKLAMA_sekme_gizliyken_DURMALI():
    """PERF-008 regresyon kilidi."""
    ihlal = _ihlaller()
    assert not ihlal, (
        "Bu dosyalar `setInterval` ile yoklama kuruyor ama görünürlüğe bakmıyor. "
        "Arka plandaki bir sekme, bakan bir göz olmadan istek üretmeye devam eder "
        "(5 sn'lik bir yoklama saatte 720 istek):\n  "
        + "\n  ".join(ihlal)
        + f"\n\nDüzelt: `visibilitychange` ile gizliyken durdur, geri gelince ANINDA bir "
          f"ölçüm yap. Gerçekten koşulsuz gerekiyorsa `// {_MUAF} <gerekçe>` yaz."
    )


def test_KAPI_sentetik_ornekleri_ayirir(tmp_path):
    """MUTASYON: korumasız yoklama yakalanır; korumalı ve gerekçeli olanlar geçer."""
    korumasiz = tmp_path / "Korumasiz.jsx"
    korumasiz.write_text("const t = setInterval(check, 5000);\n", encoding="utf-8")
    assert _ihlaller([korumasiz]), "Kapı korumasız yoklamayı kaçırdı"

    korumali = tmp_path / "Korumali.jsx"
    korumali.write_text("const t = setInterval(check, 5000);\n"
                        "document.addEventListener('visibilitychange', f);\n", encoding="utf-8")
    assert not _ihlaller([korumali]), "Kapı görünürlük korumasını görmedi"

    gerekceli = tmp_path / "Gerekceli.jsx"
    gerekceli.write_text(f"// {_MUAF} geri sayim; kullanici gorse de gormese de akmali\n"
                         "const t = setInterval(tick, 1000);\n", encoding="utf-8")
    assert not _ihlaller([gerekceli]), "Kapı yazılı gerekçeyi görmedi"
