r"""
BELGE DENETİMİ — ÖLÜ YÖNLENDİRME KAPISI + BAYATLIK RAPORU (BUG #310 / KAP-05).

İKİ AYRI İŞ, İKİ AYRI SERTLİK. Ayrımı bilerek yapıyoruz:

  1. ÖLÜ YÖNLENDİRME — **KAPI** (çıkış 1). Bir belge okuyucuyu bir dosyaya GÖNDERİYOR
     ("bkz. `X`", "kaynak: `X`", "tek kaynak `X`") ve o dosya git'te YOK. Bu sezgi değil,
     mekanik bir yalan: belgenin verdiği talimat izlenemez.
     ÖLÇÜLEN ÖRNEK (BUG #306): `docs/api-reference/README.md` şema kaynağı olarak
     "repo kökü `openapi.json`" diyordu; o dosya `.gitignore:71` ile yok sayılıyor ve
     diskte hiç yoktu. Bugün bu sınıftan **0** bulgu var (o tek örnek düzeltildi), yani
     kapı da diğer üçü gibi ÖNLEYİCİDİR.

  2. BAYATLIK — **RAPOR** (çıkış 0). "Şu an", "güncel durum" gibi ŞİMDİKİ ZAMAN iddiası
     taşıyıp uzun süredir dokunulmamış belgeler. Bu SEZGİSELDİR ve bilerek kapı DEĞİL:
     bir cümlenin bayat olup olmadığına kod karar veremez. Kapıya çevirmek, insanı
     "sustur" refleksine iter ve gate'in kendisi çöpe gider.

NEDEN ÖLÜ YÖNLENDİRME DAR TUTULDU (ölçüldü): backtick içindeki HER yol-benzeri jetonu
kontrol eden geniş bir tarayıcı denendi → **208 bulgu / 27 belge**, ve incelendiğinde
neredeyse tamamı yanlış alarmdı: yedek dosya adları (`2026-08-24-102013.db`), önerilen
ama hiç yazılmamış dosyalar (`app/config.py`), ve en çok da **yokluk beyanları** —
`PROJE.md`'nin "`mypy.ini` · `ruff.toml` … yedisi de yoktu" cümlesi gibi. Bir kapı 208
gürültüyle doğarsa ilk gün görmezden gelinir. Bu yüzden yalnız YÖNLENDİRME fiili taşıyan
ve yokluk beyanı OLMAYAN satırlar sayılır: bugün 0 yanlış alarm.

Kullanım:
    .\venv\Scripts\python.exe scripts/belge_denetimi.py             # kapı + rapor
    .\venv\Scripts\python.exe scripts/belge_denetimi.py --gun 60    # bayatlık eşiği

GUNCELLEMELER
-------------
BUG #310 fix: dosya oluşturuldu (KAP-05).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_KOK = Path(__file__).resolve().parent.parent

# ── ÖLÜ YÖNLENDİRME ───────────────────────────────────────────────────────────
_JETON = re.compile(r"`([^`\n]+)`")
_YOL_GIBI = re.compile(
    r"^[A-Za-z0-9_\-./]+\.(py|md|json|toml|yml|yaml|ini|txt|js|jsx|sh|ps1|vbs|cfg)$"
)
# Okuyucuyu bir dosyaya GÖNDEREN ifadeler.
_YONLENDIRME = re.compile(
    r"(bkz\.|bakınız|kaynak\s*:|tek kaynak|referans\s*:|ayrıntı\s*:|şurada|dosyasına bak)",
    re.IGNORECASE,
)
# Aynı satır dosyanın YOK olduğunu söylüyorsa bulgu değildir — belge doğru konuşuyor.
_YOKLUK = re.compile(
    r"(yok\b|yoktu|yoktur|bulunmuyor|mevcut değil|kaldırıl|silin|eksik|olmayan|hiç yok)",
    re.IGNORECASE,
)

# ── BAYATLIK ──────────────────────────────────────────────────────────────────
_IDDIA = re.compile(r"(güncel durum|şu an|bugün itibarıyla|halen|hâlâ)", re.IGNORECASE)

# GÜNLÜK/ARŞİV — şimdiki zaman iddiası taşısa bile bayatlaması TASARIM GEREĞİDİR.
# Bir denetim raporu yazıldığı günün fotoğrafıdır; sonradan değişmesi beklenmez, hatta
# değişirse tarihsel kayıt bozulur. Bu liste path deseniyle çalışır ve rapor kaç dosyayı
# muaf tuttuğunu YAZAR — yanlış sınıflama sessiz kalmasın.
_GUNLUK_DESENLERI = (
    re.compile(r"^docs/kalite-seruveni/dosya-denetimi/"),
    re.compile(r"^docs/architecture/adr-"),
    re.compile(r"^docs/kalite-seruveni/(milestone-log|uygulanan-fixler|research-log)\.md$"),
    re.compile(r"^docs/kalite-seruveni/beta-geri-bildirim\.md$"),
    re.compile(r"\d{4}-\d{2}-\d{2}"),                       # ada tarih yazılmış rapor
    re.compile(r"-\d{1,2}(oca|sub|mar|nis|may|haz|tem|agu|eyl|eki|kas|ara)\.md$"),
    re.compile(r"^CHANGELOG\.md$"),
)


def _izlenen_belgeler() -> list[str]:
    cikti = subprocess.run(
        ["git", "ls-files", "*.md"], cwd=str(REPO_KOK), capture_output=True, text=True, check=True
    )
    return sorted(cikti.stdout.split())


def _izlenen_hepsi() -> set[str]:
    cikti = subprocess.run(
        ["git", "ls-files"], cwd=str(REPO_KOK), capture_output=True, text=True, check=True
    )
    return set(cikti.stdout.split())


def _son_degisim() -> dict[str, int]:
    """Dosya → son commit zamanı (unix). TEK `git log` geçişi.

    Dosya başına `git log -1` çağırmak 232 belge için dakikalar sürüyordu; tek geçiş
    saniyenin altında.
    """
    cikti = subprocess.run(
        ["git", "log", "--name-only", "--format=%at", "--no-merges"],
        cwd=str(REPO_KOK),
        capture_output=True,
        text=True,
        check=True,
    )
    zaman: dict[str, int] = {}
    simdiki = 0
    for satir in cikti.stdout.splitlines():
        satir = satir.strip()
        if not satir:
            continue
        if satir.isdigit():
            simdiki = int(satir)
            continue
        zaman.setdefault(satir, simdiki)  # log yeniden-eskiye: ilk görülen en yenisidir
    return zaman


def olu_yonlendirmeler(belgeler: list[str], izlenen: set[str]) -> list[tuple[str, int, str, str]]:
    bulgular = []
    for belge in belgeler:
        try:
            satirlar = (REPO_KOK / belge).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for no, satir in enumerate(satirlar, 1):
            if not _YONLENDIRME.search(satir):
                continue
            # YOKLUK beyanı satırın DÜZ METNİNDE aranır, backtick içindeki yolda değil.
            # Ölçülen kusur (mutasyon 3): `docs/hic-olmayan-belge.md` adlı bir dosyaya
            # yapılan gerçek bir ölü yönlendirme, DOSYA ADININ İÇİNDEKİ "olmayan" yüzünden
            # muaf sayılıyordu — yani bir bulgunun görünürlüğü, işaret ettiği dosyanın adına
            # bağlıydı. Muafiyet cümlenin ne DEDİĞİNE bakmalı, neyi adlandırdığına değil.
            duz_metin = _JETON.sub(" ", satir)
            if _YOKLUK.search(duz_metin):
                continue
            for m in _JETON.finditer(satir):
                jeton = m.group(1).strip().lstrip("./")
                if not _YOL_GIBI.match(jeton):
                    continue
                adaylar = {jeton, str(Path(belge).parent / jeton).replace("\\", "/")}
                if adaylar & izlenen:
                    continue
                # Yalnız dosya adı verilmişse (örn. `main.py`) depoda o adla biten bir yol ara.
                taban = jeton.rsplit("/", 1)[-1]
                if any(p.endswith("/" + taban) or p == taban for p in izlenen):
                    continue
                bulgular.append((belge, no, jeton, satir.strip()[:120]))
    return bulgular


def _gunluk_mu(yol: str) -> bool:
    return any(d.search(yol) for d in _GUNLUK_DESENLERI)


def bayat_belgeler(belgeler: list[str], gun: int) -> tuple[list[tuple[str, int]], int]:
    zaman = _son_degisim()
    simdi = int(time.time())
    bayat = []
    muaf = 0
    for belge in belgeler:
        if _gunluk_mu(belge):
            muaf += 1
            continue
        try:
            metin = (REPO_KOK / belge).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not _IDDIA.search(metin):
            continue
        son = zaman.get(belge)
        if son is None:
            continue
        yas = (simdi - son) // 86400
        if yas > gun:
            bayat.append((belge, yas))
    return sorted(bayat, key=lambda kv: -kv[1]), muaf


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(description="Belge denetimi: ölü yönlendirme + bayatlık.")
    ayristirici.add_argument("--gun", type=int, default=30, help="Bayatlık eşiği (gün, varsayılan 30).")
    secenek = ayristirici.parse_args(argv)

    belgeler = _izlenen_belgeler()
    izlenen = _izlenen_hepsi()

    print(f"BELGE DENETİMİ — {len(belgeler)} izlenen .md\n")

    # 1) KAPI
    olu = olu_yonlendirmeler(belgeler, izlenen)
    print(f"[KAPI] Ölü yönlendirme: {len(olu)}")
    for belge, no, jeton, satir in olu:
        # ASCII ok BİLEREK: `→` (U+2192) Windows Türkçe konsolunun cp1254 kod sayfasında
        # YOK ve `print` UnicodeEncodeError ile çöküyordu — yani kapı, tam da söyleyecek
        # sözü olduğu anda patlıyordu (mutasyon 1 bunu yakaladı). Bir kapının hata yolu,
        # başarı yolundan daha dayanıklı olmalıdır.
        print(f"  {belge}:{no} -> `{jeton}` (git'te yok)")
        print(f"      {satir}")

    # 2) RAPOR
    bayat, muaf = bayat_belgeler(belgeler, secenek.gun)
    print(
        f"\n[RAPOR] Şimdiki-zaman iddiası taşıyıp {secenek.gun}+ gündür dokunulmamış: "
        f"{len(bayat)}  (günlük/arşiv olduğu için muaf tutulan: {muaf})"
    )
    for belge, yas in bayat:
        print(f"  {yas:>4} gün  {belge}")
    print("\n  Bu bölüm KAPI DEĞİL: bir cümlenin bayat olup olmadığına kod karar veremez.")

    if olu:
        print(
            "\nKAPI KIRILDI: bir belge, git'te olmayan bir dosyaya yönlendiriyor.\n"
            "Belgeyi düzelt ya da dosyayı ekle. Dosyanın YOKLUĞUNU anlatan bir cümleyse\n"
            "(örn. \"`mypy.ini` yok\") kapı zaten saymaz — cümleyi yönlendirme gibi kurma.",
            file=sys.stderr,
        )
        return 1

    print("\nkapı geçildi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
