"""
D18 (BUG #236) — KURUCUNUN VE ÜÇÜNCÜ BİR KİŞİNİN GERÇEK FİNANSAL VERİSİ PROD İMAJINA GİRİYORDU.

`Dockerfile:33` bütün `scripts/` dizinini kopyalıyor, `.dockerignore` ise `scripts` için
hiçbir istisna içermiyordu. İmaja giren `scripts/setup_data.py` gerçek verilerdir: banka
markaları, gerçek kredi tutarları, **adı geçen üçüncü bir kişinin** 13 aylık borç takvimi ve
aile içi para düzenlemeleri. O kişi uygulamanın kullanıcısı bile değildir ve verisinin bir
registry'ye push edilen imajda taşınmasına rıza vermemiştir.

İkinci zarar: aynı dosya `drop_all` yapar. Guard'ı elle onay ister ama `SETUP_DATA_FORCE=1`
ile atlanır — yani prod konteynerinde tek komut TÜM beta kullanıcılarının verisini siler ve
yerine bu kişisel veriyi kurar.

Mevcut kişiye-özel-iz kapısı (BUG #166, `test_urunlesme_kisisellestirme.py`) bu boşluğu
göremiyordu: kapsamı `app/` + `frontend/src`; imaja giren `scripts/` hiç taranmıyordu.

Bu dosya kapsamı **imajın gerçek içeriğine** bağlar: Dockerfile'ın kopyaladığı yollar
`.dockerignore` uygulandıktan sonra taranır. Yeni bir `COPY` eklenip kişisel veri sızarsa
ya da bir eleme kaldırılırsa kapı kırılır.
"""
from __future__ import annotations

import fnmatch
import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent

# BUG #166 kapısıyla aynı iz listesi — ürün yüzeyinde olduğu gibi imajda da yasak.
YASAK_IZLER = [
    r"\bMurat\b", r"\bEfe\b", r"\bRezan\b", r"\bİçgil\b", r"\bIcgil\b",
    r"\bEnpara\b", r"\bZiraat\b", r"\bGaranti\s+(Kredi|Kart|Hesab|kredi|kart|hesab)",
    r"[\w\.\-]+@(gmail|hotmail|outlook|yahoo|yandex)\.[a-z]+",
]

# İmaja giren dosyalarda bulunmaması gereken YIKICI çağrılar: prod konteynerinde elle
# çalıştırılabilecek her `drop_all` tüm beta verisini siler (telafisi yalnız yedektir).
YIKICI_DESENLER = [r"\bdrop_all\s*\(", r"\bDROP\s+DATABASE\b"]

_METIN_UZANTILARI = {".py", ".sh", ".md", ".txt", ".ini", ".yml", ".yaml", ".json", ".cfg"}


# ------------------------------------------------------------
# Docker bağlamı simülasyonu
# ------------------------------------------------------------

def _dockerignore_kurallari() -> list[tuple[str, bool]]:
    """(desen, istisna_mi) listesi — dosya sırası korunur (son eşleşen kazanır)."""
    kurallar: list[tuple[str, bool]] = []
    for satir in (KOK / ".dockerignore").read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if not satir or satir.startswith("#"):
            continue
        if satir.startswith("!"):
            kurallar.append((satir[1:].rstrip("/"), True))
        else:
            kurallar.append((satir.rstrip("/"), False))
    return kurallar


def _elenmis_mi(goreli: str, kurallar: list[tuple[str, bool]]) -> bool:
    """Docker'ın kuralı: sırayla eşleştir, SON eşleşen belirler (`!` istisnadır)."""
    sonuc = False
    for desen, istisna in kurallar:
        if fnmatch.fnmatch(goreli, desen) or fnmatch.fnmatch(goreli, f"{desen}/*") \
                or any(fnmatch.fnmatch(parca, desen) for parca in goreli.split("/")):
            sonuc = not istisna
    return sonuc


def _copy_kaynaklari() -> list[str]:
    """Runtime aşamasının `COPY` kaynakları (builder'dan gelenler hariç — imaj içi yol)."""
    kaynaklar: list[str] = []
    for satir in (KOK / "Dockerfile").read_text(encoding="utf-8").splitlines():
        s = satir.strip()
        if not s.startswith("COPY ") or "--from=" in s:
            continue
        parcalar = s.split()[1:]
        kaynaklar.extend(parcalar[:-1])      # son parça hedeftir
    return kaynaklar


def imaja_giren_dosyalar() -> list[Path]:
    """Dockerfile'ın kopyaladığı, `.dockerignore` sonrası imajda KALAN metin dosyaları."""
    kurallar = _dockerignore_kurallari()
    bulunan: list[Path] = []
    for kaynak in _copy_kaynaklari():
        yol = KOK / kaynak
        adaylar = [yol] if yol.is_file() else sorted(yol.rglob("*")) if yol.is_dir() else []
        for aday in adaylar:
            if not aday.is_file() or aday.suffix not in _METIN_UZANTILARI:
                continue
            goreli = aday.relative_to(KOK).as_posix()
            if _elenmis_mi(goreli, kurallar):
                continue
            bulunan.append(aday)
    return bulunan


# ------------------------------------------------------------
# 1. KAPSAM TABANI (L11)
# ------------------------------------------------------------

def test_kapsam_tabani_imaj_icerigi_taraniyor():
    """Simülasyon boşalırsa alttaki kapılar sessizce kör koşar."""
    dosyalar = imaja_giren_dosyalar()
    assert len(dosyalar) >= 60, (
        f"İmaja giren yalnız {len(dosyalar)} dosya bulundu — Dockerfile/`.dockerignore` "
        "ayrıştırması bozulmuş olabilir, kapı kör kalır"
    )


def test_simulasyon_gercekten_eliyor():
    """Meta-test: eleme çalışmıyorsa kapı 'her şey temiz' der. `tests/` elenmiş olmalı."""
    yollar = {p.relative_to(KOK).as_posix() for p in imaja_giren_dosyalar()}
    assert not any(y.startswith("tests/") for y in yollar), \
        "`.dockerignore` simülasyonu `tests/` dizinini elemiyor — eleme mantığı bozuk"
    assert any(y.startswith("app/") for y in yollar), "app/ hiç taranmıyor"


# ------------------------------------------------------------
# 2. KİŞİSEL VERİ (D18 çekirdeği)
# ------------------------------------------------------------

def test_imajda_kisiye_ozel_iz_yok():
    """İmaj dağıtılan bir yapıdır: kurucunun/üçüncü kişilerin gerçek verisi taşınamaz."""
    ihlal = []
    for yol in imaja_giren_dosyalar():
        goreli = yol.relative_to(KOK).as_posix()
        for no, satir in enumerate(yol.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            for kalip in YASAK_IZLER:
                if re.search(kalip, satir):
                    ihlal.append(f"{goreli}:{no}: {satir.strip()[:100]}")
    assert not ihlal, (
        "Production imajına kişiye özel veri giriyor (KVKK: adı geçen üçüncü kişinin rızası "
        "yok; imaj registry'ye push edilir, paylaşılır):\n" + "\n".join(ihlal[:40])
    )


def test_imajda_yikici_sema_araci_yok():
    """Prod konteynerinde `drop_all` bulunması, tek komutluk kalıcı veri kaybı yüzeyidir."""
    ihlal = []
    for yol in imaja_giren_dosyalar():
        metin = yol.read_text(encoding="utf-8", errors="ignore")
        for kalip in YIKICI_DESENLER:
            if re.search(kalip, metin):
                ihlal.append(yol.relative_to(KOK).as_posix())
    assert not ihlal, (
        f"Bu dosyalar imajda YIKICI şema işlemi taşıyor: {sorted(set(ihlal))}. "
        "Prod konteynerinde tek komut tüm beta verisini siler — `.dockerignore` ile ele."
    )


# ------------------------------------------------------------
# 3. ÜRÜN İÇİN GEREKLİ OLANLAR HÂLÂ İMAJDA (L6: kapı ürünü kırmasın)
# ------------------------------------------------------------

def test_calisma_zamani_gerekli_scriptler_imajda_kaliyor():
    """Eleme fazla geniş olursa uygulama prod'da çöker — `app/startup.py` bunu import ediyor."""
    yollar = {p.relative_to(KOK).as_posix() for p in imaja_giren_dosyalar()}
    zorunlu = {"scripts/__init__.py", "scripts/backfill_net_worth.py",
               "app/main.py", "alembic.ini", "docker-entrypoint.sh",
               "docs/legal/kvkk-consent-v3.md"}   # BUG #191: hukuki metin API'den sunulur
    eksik = sorted(z for z in zorunlu if z not in yollar)
    assert not eksik, f"Bu dosyalar imajda OLMALI ama elendi: {eksik}"


def test_operasyon_araclari_imajda_kaliyor():
    """Runbook'un konteyner içinde çalıştırdığı araçlar elenmemeli (yedek/geri yükleme/beta)."""
    yollar = {p.relative_to(KOK).as_posix() for p in imaja_giren_dosyalar()}
    zorunlu = {"scripts/backup.py", "scripts/restore.py", "scripts/beta_invite.py",
               "scripts/beta_metrics.py", "scripts/live_gate.py"}
    eksik = sorted(z for z in zorunlu if z not in yollar)
    assert not eksik, (
        f"Operasyon araçları imajdan çıkarıldı: {eksik}. Runbook bunları konteyner içinde "
        "çalıştırıyor — eleme listesi fazla geniş."
    )
