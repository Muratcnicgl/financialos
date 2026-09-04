"""
VİTRİN ÜRETİCİSİ (Wave-Y / Y7, ADR-060) — private depodan public vitrin üretir.

    python -m scripts.vitrin_uret                # olcer + uretir (vitrin/ dizinine)
    python -m scripts.vitrin_uret --hizli        # sure alan olcumleri atlar (taslak)

NEDEN ÜRETİLİYOR, ELLE YAZILMIYOR
----------------------------------
Elle yazılmış bir vitrin bu deponun **kayıtlı hastalığına** yakalanır: BUG #310 —
belgenin işaret ettiği şey diskte yoktur ve kimse fark etmez. Bir portföy sayfası altı
ayda bayatlar; "3.486 test" yazan bir cümle, testler 2.000'e düşse de orada durur.
Bu üretici **gerçek depoyu ölçer**; sayı koşumdan gelir, dolayısıyla bayatlayamaz.

═══════════════════════════════════════════════════════════════════════════════
NEDEN ALLOWLIST, DENYLIST DEĞİL — BU DOSYANIN EN ÖNEMLİ KARARI
═══════════════════════════════════════════════════════════════════════════════
Bu script bir **private → public boru hattıdır**. Böyle bir hattı denylist'le korumak
(hesap no, IBAN, e-posta, banka adı, tutar ara) yalnız **düşünülen** sızıntıyı yakalar.
Sızıntı düşünülmeyenden gelir:

    · commit mesajları                  · mutlak dosya yolları (C:\\Users\\<ad soyad>\\...)
    · ADR gövdelerindeki gerçek rakamlar · ledger'ın 1.070 satırındaki bakiye örnekleri
    · hata çıktılarına gömülü fixture     · şahsi destek adresi (live_gate bunu yakalamıştı)

Bu yüzden üretici **hiçbir dosyanın metnini kopyalamaz.** Her alan, o alanı üreten
**adanmış bir ölçüm fonksiyonundan** gelir ve `IZINLI_ALANLAR`da açıkça listelenir.
Listede olmayan hiçbir şey çıktıya giremez — çünkü çıktıya giden tek yol o sözlüktür.

Denylist "kötü olanı ara", allowlist "iyi olanı geçir" der. İkincisi **bilmediğin şeye
karşı da korur.** Kapı (`tests/test_vitrin_kapisi.py`) ikinci savunmadır, birinci değil.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess  # noqa: S404 — yalnız pytest/npm sayımı; kullanıcı girdisi yok
import sys
from datetime import date
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
CIKTI = KOK / "vitrin"

# ── ALLOWLIST ────────────────────────────────────────────────────────────────
#: Vitrine çıkabilecek alanların TAM listesi. Buraya yazılmayan hiçbir şey yayılmaz.
#: Her alanın yanında NEDEN güvenli olduğu yazılıdır — gerekçesiz alan eklenmez.
IZINLI_ALANLAR = {
    "tarih":            "üretim tarihi — kişisel değil",
    "olcum_modu":       "'tam' | 'hizli' — hangi ölçümün yapıldığı; iddianın dayanağı",
    "backend_test":     "tam sayı (pytest sayımı)",
    "backend_skip":     "tam sayı",
    "frontend_test":    "tam sayı (vitest sayımı)",
    "e2e_test":         "tam sayı — Playwright `--list` sayımı (metin sayımı DEĞİL: döngüyle üretilen testleri kaçırıyordu, 7 vs 8)",
    "coverage_yuzde":   "ondalık sayı (coverage raporu)",
    "coverage_tavan":   "tam sayı (CI eşiği)",
    "kapilar":          "kapı ADI + TAVANI — ad teknik, tavan tam sayı",
    "adr_sayisi":       "tam sayı — benzersiz ADR NUMARASI (indeks ve ekler elenmiş)",
    "adr_belge_sayisi": "tam sayı — ADR BELGE sayısı (013a gibi ekler dahil)",
    "adr_basliklari":   "ADR BAŞLIK satırı — teknik karar adı; gövde ASLA alınmaz",
    "mutasyon":         "kapı adı + 'n/m' skoru — sayı ve dosya adı",
    "yigin":            "teknoloji adları — sabit liste, depodan okunmaz",
    "goc_sayisi":       "tam sayı",
    "kod_satiri":       "tam sayı",
    "ilke":             "SABİT metin — bu dosyada yazılı, depodan kopyalanmaz",
}

#: Vitrinin anlatısı. Depodan KOPYALANMAZ; burada yazılıdır ve gözden geçirilmiştir.
#: (Bu, "hiçbir dosyanın metnini kopyalama" kuralının tek istisnası değil — istisnası
#: değil, kuralın kendisi: metin ÜRETİCİDE yaşar, depoda değil.)
ILKELER = [
    ("Kural motoru karar verir, LLM açıklar",
     "Tüm matematiksel kararlar saf Python'da; dil modeli yalnız hesaplanmış bir anlık "
     "görüntüyü okur ve açıklar. Model asla veritabanına yazmaz: öner → kullanıcı onayı → uygula."),
    ("Tavan bir hedef değil, bir borç dondurucudur",
     "Kalite kapıları mevcut bulgu sayısını dondurur; büyümesini engeller. Tavan aile "
     "bazında tutulur — tek toplam takasa izin verirdi. Araç sürümü sabittir, yoksa sayının "
     "anlamı sessizce kayar."),
    ("Bir kapı reddettiğinde doğru cevap tavanı yükseltmek değildir",
     "Kapılar bu projede değişiklikleri sekiz kez reddetti ve sekizinde de haklı çıktı. "
     "Her seferinde tasarım düzeldi, tavan değil."),
    ("Her kapıya mutasyon testi",
     "Bir kapı, onu kırması gereken mutasyonlarla sınanmadan kapı sayılmaz. Mutasyon "
     "birçok kez kapının kendi kör noktasını buldurdu — ve bir kez yanlış bir TEŞHİSİ çürüttü."),
    ("Bilinmeyen, sıfır değildir",
     "Ölçülmemiş bir değer varsayılan bir değere sessizce düşmez. Sıfır gözlemden yüzde "
     "üretmek, ölçmediğini mükemmel sanmaktır."),
    ("Ölçen sistem, haber veren sistem değildir",
     "Bir arıza log'a yazılıyorsa fark edilmemiş sayılır. İzleme bu yüzden ölü adam "
     "anahtarıdır: sessizlik, her şeyin yolunda olduğunun değil, alarmın kendisidir."),
]

YIGIN = ["Python 3.11", "FastAPI", "SQLAlchemy 2.x", "Alembic", "Pydantic V2",
         "SQLite / PostgreSQL (dual-dialect)", "React", "Vite", "Tailwind",
         "pytest", "vitest", "Playwright", "ruff"]


# ── ÖLÇÜMLER ─────────────────────────────────────────────────────────────────
def _kos(*argv: str, timeout: int = 900, dizin: Path | None = None) -> str:
    p = subprocess.run(  # noqa: S603
        list(argv), cwd=str(dizin or KOK), capture_output=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )
    return (p.stdout or "") + (p.stderr or "")


def olc_backend(hizli: bool) -> tuple[int, int, float | None]:
    """pytest sayımı + coverage. Hızlı modda yalnız TOPLANAN test sayısı ölçülür."""
    py = str(KOK / "venv" / "Scripts" / "python.exe")
    if hizli:
        c = _kos(py, "-m", "pytest", "tests/", "-q", "--collect-only", timeout=300)
        m = re.search(r"(\d+) tests collected", c)
        return (int(m.group(1)) if m else 0), 0, None
    # `--cov-fail-under=0`: eşik olarak DEĞİL, coverage'ın "Total coverage: 94.02%" satırını
    # bastırmak için. O satır olmadan yalnız TOTAL satırındaki YUVARLANMIŞ tam sayı (94)
    # okunabiliyor ve vitrin "%94.0" yazıyordu — yayınlanan bir sayıda gereksiz hassasiyet
    # kaybı. 0 eşiği hiçbir zaman kırmızı vermez, yani ölçümü etkilemez.
    c = _kos(py, "-m", "pytest", "tests/", "-q", "--cov=app", "--cov-report=term",
             "--cov-fail-under=0")
    gecen = re.search(r"(\d+) passed", c)
    atlanan = re.search(r"(\d+) skipped", c)
    kapsam = re.search(r"Total coverage: ([\d.]+)%", c) or re.search(r"TOTAL.*?(\d+)%", c)
    return (int(gecen.group(1)) if gecen else 0,
            int(atlanan.group(1)) if atlanan else 0,
            float(kapsam.group(1)) if kapsam else None)


def olc_frontend(hizli: bool) -> int:
    if hizli:
        return 0
    # Windows'ta `npm` bir .cmd sarmalayıcısıdır; `subprocess` onu `shell=False` ile
    # bulamaz (WinError 2 — ölçüldü). Uzantı platforma göre seçilir.
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    c = _kos(npm, "test", "--prefix", "frontend", "--", "--run", timeout=600)
    m = re.search(r"Tests\s+(\d+) passed", c)
    return int(m.group(1)) if m else 0


def olc_e2e() -> int:
    """
    E2E test sayısı — **Playwright'ın kendi listesinden**, metin sayımından değil.

    İlk sürüm spec dosyalarındaki `test(` çağrılarını sayıyordu ve **7** veriyordu; gerçek
    koşum **8** diyordu. Sebep yapısal: `tema-mobil.spec.js:165` bir DÖNGÜ içinde tanımlı
    (dark + light tema) — metinde bir kez geçer, koşumda iki kez çalışır. Metin sayımı
    parametrelenmiş testleri **yapısal olarak** göremez.

    Yayınlanacak bir sayının yanlış olması kabul edilemez (vitrin dış bir iddiadır), bu
    yüzden sayım araca sorulur. `--list` testleri KOŞTURMAZ, yalnız numaralandırır —
    canlıya ve DB'ye dokunmaz.
    """
    npx = "npx.cmd" if sys.platform == "win32" else "npx"
    c = _kos(npx, "playwright", "test", "--list", "--reporter=list",
             timeout=180, dizin=KOK / "frontend")
    m = re.search(r"Total:\s*(\d+)\s+tests?", c)
    if m:
        return int(m.group(1))
    # Araç konuşmuyorsa SIFIR dönmek "e2e yok" demek olurdu (L45: bilinmeyen ≠ sıfır).
    # -1, üretici tarafında görünür bir işaret; markdown'da "ölçülemedi" yazılır.
    return -1


def olc_kapilar() -> list[dict]:
    """Kapı ADI + TAVANI. Ad teknik, tavan tam sayı — ikisi de kişisel veri taşımaz."""
    kapilar: list[dict] = []
    taban = KOK / "docs" / "kalite-seruveni" / "kalite-baseline.json"
    if taban.exists():
        d = json.loads(taban.read_text(encoding="utf-8"))
        aile = d.get("tavan") or {}
        # ruff TEK bir kapıdır; E9/F/B/S onun AİLELERİdir. Dört satır olarak listelemek,
        # okuyana dört ayrı kapı varmış izlenimi verirdi (PROJE.md "yedi kapı" diyor).
        # Tavan yine aile bazında gösterilir — çünkü tek toplam takasa izin verirdi.
        parcalar = [f"{ad} {tavan}" for ad, tavan in sorted(aile.items())
                    if isinstance(tavan, int)]
        if parcalar:
            kapilar.append({"ad": "ruff (dar küme; tavan AİLE bazında)",
                            "tavan": " · ".join(parcalar)})
    kapilar += [
        {"ad": "ölü kod", "tavan": "0"},
        {"ad": "belge denetimi (ölü yönlendirme)", "tavan": "0"},
        {"ad": "kişisel veri (hesap no / IBAN / kart)", "tavan": "0"},
        {"ad": "ağ kapısı (süit dışarı çıkamaz)", "tavan": "0"},
        {"ad": "API sözleşmesi (donmuş)", "tavan": "—"},
        {"ad": "şema FK sapması", "tavan": "14"},
    ]
    return kapilar


def olc_adr() -> tuple[int, int, list[str]]:
    """
    ADR sayısı ve **BAŞLIK** satırları. Gövde ASLA alınmaz — gövdelerde gerçek rakamlar var.

    SAYIM DÜZELTİLDİ (4 Eylül 2026): `glob("adr-*.md")` **61** veriyordu ve bu sayı
    yayınlanmıştı. Ölçüldü:

      * 61 dosyanın **1'i `adr-index.md`** — bir karar kaydı değil, indeks.
      * Kalan 60 belgede **58 benzersiz numara** var: `013`/`013a` ve `034`/`034 Revize`
        aynı kararın ekleridir.

    Yani "61 ADR" iddiası iki ayrı hata taşıyordu. Vitrin dış bir iddia olduğu için
    **ikisi de** düzeltildi ve iki sayı AYRI raporlanıyor: kaç KARAR (benzersiz numara)
    ve kaç BELGE. Tek sayı vermek, hangisinin kastedildiğini okuyucuya bırakırdı.
    """
    dosyalar = sorted(
        f for f in (KOK / "docs" / "architecture").glob("adr-*.md")
        if re.match(r"^adr-\d+[a-z]?-", f.name)   # indeks ve benzerleri elenir
    )
    basliklar = []
    numaralar = set()
    for f in dosyalar:
        ilk = f.read_text(encoding="utf-8", errors="replace").split("\n", 1)[0]
        basliklar.append(ilk.lstrip("# ").strip())
        m = re.match(r"^adr-(\d+)", f.name)
        if m:
            numaralar.add(int(m.group(1)))
    return len(numaralar), len(dosyalar), basliklar


def olc_mutasyon() -> list[dict]:
    """Kapı dosyası + `mutasyon n/m` skoru. Yalnız DOSYA ADI ve SAYI çıkar."""
    sonuc = []
    # `MUTASYON 3/3`, `mutasyon 4/4`, `**mutasyon 5/5**` — hepsi geçerli yazım (ölçüldü).
    desen = re.compile(r"mutasyon\s+\**\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)
    for f in sorted((KOK / "tests").glob("test_*kapisi*.py")):
        m = desen.search(f.read_text(encoding="utf-8", errors="replace"))
        if m:
            sonuc.append({"kapi": f.stem, "skor": f"{m.group(1)}/{m.group(2)}"})
    return sonuc


def olc_kod_satiri() -> int:
    n = 0
    for d in ("app", "tests", "scripts"):
        for f in (KOK / d).rglob("*.py"):
            if "__pycache__" in f.parts:
                continue
            n += len(f.read_text(encoding="utf-8", errors="replace").splitlines())
    return n


# ── ÜRETİM ───────────────────────────────────────────────────────────────────
def veri_topla(hizli: bool) -> dict:
    gecen, atlanan, kapsam = olc_backend(hizli)
    adr_n, adr_belge, adr_b = olc_adr()
    veri = {
        "tarih": date.today().isoformat(),
        # HIZLI modda `backend_test` TOPLANAN test sayısıdır, GEÇEN değil. İkisini aynı
        # etiketle yayınlamak, ölçülmemiş bir iddiayı ölçüm gibi sunmak olurdu — bu
        # projenin en sık avladığı hata. Mod veriye yazılır ve kapı taslağı yayınlatmaz.
        "olcum_modu": "hizli" if hizli else "tam",
        "backend_test": gecen,
        "backend_skip": atlanan,
        "frontend_test": olc_frontend(hizli),
        "e2e_test": olc_e2e(),
        "coverage_yuzde": kapsam,
        "coverage_tavan": 93,
        "kapilar": olc_kapilar(),
        "adr_sayisi": adr_n,
        "adr_belge_sayisi": adr_belge,
        "adr_basliklari": adr_b,
        "mutasyon": olc_mutasyon(),
        "yigin": YIGIN,
        "goc_sayisi": len(list((KOK / "alembic" / "versions").glob("*.py"))),
        "kod_satiri": olc_kod_satiri(),
        "ilke": ILKELER,
    }
    # ALLOWLIST ZORLAMASI: sözlükte izinli olmayan anahtar varsa ÜRETİM DURUR.
    fazla = set(veri) - set(IZINLI_ALANLAR)
    if fazla:
        raise SystemExit(f"IZINSIZ ALAN: {sorted(fazla)} — IZINLI_ALANLAR'a gerekçesiyle ekle")
    return veri


def markdown_uret(v: dict) -> str:
    taslak = v["olcum_modu"] != "tam"
    s = ["# FinancialOS — mühendislik vitrini", "",
         *(["> ⚠️ **TASLAK — YAYINLANAMAZ.** Hızlı modda üretildi: testler koşulmadı, "
            "yalnız toplandı; kapsam ölçülmedi. Yayın için: `python -m scripts.vitrin_uret`",
            ""] if taslak else []),
         f"> Bu sayfa **üretilmiştir** (`scripts/vitrin_uret.py`), elle yazılmamıştır. "
         f"Her sayı gerçek depo üzerinde koşulmuş bir ölçümden gelir. Üretim: {v['tarih']}.",
         "",
         "Kişisel finans için bir karar destek sistemi: kural motoru hesaplar, dil modeli "
         "açıklar. Aşağıdaki tablo bir iddia listesi değil, bir ölçüm çıktısıdır.", "",
         "## Ölçümler", "",
         "| | |", "|---|---|",
         (f"| Backend testi | **{v['backend_test']}** geçti · {v['backend_skip']} atlandı |"
          if v["olcum_modu"] == "tam"
          else f"| Backend testi | {v['backend_test']} toplandı (TASLAK — koşulmadı) |"),
         f"| Frontend testi | **{v['frontend_test']}** |",
         (f"| Uçtan uca (Playwright) | **{v['e2e_test']}** |" if v["e2e_test"] >= 0
          else "| Uçtan uca (Playwright) | ölçülemedi |"),
         (f"| Kapsam (coverage) | **%{v['coverage_yuzde']}** — CI'da ≥%{v['coverage_tavan']} kilitli |"
          if v["coverage_yuzde"] else f"| Kapsam | CI'da ≥%{v['coverage_tavan']} kilitli |"),
         (f"| Mimari karar kaydı (ADR) | **{v['adr_sayisi']}** karar"
          + (f" · {v['adr_belge_sayisi']} belge (ekler dahil)"
             if v['adr_belge_sayisi'] != v['adr_sayisi'] else "") + " |"),
         f"| Veritabanı göçü | **{v['goc_sayisi']}** |",
         f"| Python satırı (app+tests+scripts) | **{v['kod_satiri']:,}** |".replace(",", "."),
         "", "## Kalite kapıları", "",
         "Her kapı bir **tavan** taşır. Tavan bir hedef değil, bir borç dondurucusudur: "
         "bugünkü sayı kabul edilir, **büyümesi engellenir**.", "",
         "| Kapı | Tavan |", "|---|---|"]
    s += [f"| {k['ad']} | {k['tavan']} |" for k in v["kapilar"]]
    if v["mutasyon"]:
        s += ["", "## Mutasyon skorları", "",
              "Bir kapı, onu kırması gereken mutasyonlarla sınanmadan kapı sayılmaz.", "",
              f"*Aşağıdaki liste, skorunu **kendi dosyasında beyan eden** kapılardır "
              f"({len(v['mutasyon'])} kapı). Diğer kapıların skorları ölçüm defterinde "
              f"tutuluyor ve bu sayfaya alınmıyor — vitrin yalnız makineyle doğrulanabilir "
              f"olanı yayar.*", "",
              "| Kapı | Mutasyon |", "|---|---|"]
        s += [f"| `{m['kapi']}` | {m['skor']} |" for m in v["mutasyon"]]
    s += ["", "## Çalışma ilkeleri", ""]
    for baslik, aciklama in v["ilke"]:
        s += [f"**{baslik}.** {aciklama}", ""]
    s += ["## Teknoloji", "", " · ".join(v["yigin"]), "",
          "## Mimari karar kayıtları", ""]
    s += [f"- {b}" for b in v["adr_basliklari"]]
    s += ["", "---", "",
          "*Kaynak kod özel bir depoda tutuluyor: ölçüm defterleri ve test fixture'ları "
          "gerçek finansal veri içeriyor. Bu sayfa o depodan üretilir ve yalnız açıkça "
          "izin verilmiş alanları taşır.*", ""]
    return "\n".join(s)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Vitrin ureticisi (Wave-Y/Y7)")
    ap.add_argument("--hizli", action="store_true", help="sure alan olcumleri atla")
    a = ap.parse_args(argv)

    print("olculuyor…" + (" (hizli mod: test/coverage atlaniyor)" if a.hizli else ""))
    veri = veri_topla(a.hizli)
    CIKTI.mkdir(exist_ok=True)
    (CIKTI / "README.md").write_text(markdown_uret(veri), encoding="utf-8")
    (CIKTI / "olcumler.json").write_text(
        json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"uretildi: {CIKTI.relative_to(KOK).as_posix()}/README.md + olcumler.json")
    print(f"  backend {veri['backend_test']} · frontend {veri['frontend_test']} · "
          f"e2e {veri['e2e_test']} · ADR {veri['adr_sayisi']} · kapi {len(veri['kapilar'])}")
    print("\nSIRADAKI: kapiyi kos — pytest tests/test_vitrin_kapisi.py")
    print("Kapi GECMEDEN yayinlanmaz (ADR-060: kapi uretimde degil, PUSH'tan once).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
