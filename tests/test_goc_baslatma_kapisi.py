"""
BUG #326 KAPISI — GÖÇÜ UYGULAYAN ADIM, UYGULAMAYI BAŞLATAN YOLDA OLMALI.

ÖLÇÜLEN OLAY (4 Eylül 2026): kapalı beta **sabahtan beri kapalıydı.** `schema_guard`
doğru davrandı ve uygulamayı açmayı REDDETTİ (DB `e7f8a9b0c1d2`, kod `f8a9b0c1d2e3` —
BUG #318'in göçü canlı DB'ye hiç uygulanmamıştı). Sağlık görevi 10 dakikada bir yeniden
denedi, her seferinde aynı hatayla düştü ve bunu yalnız `logs/servis.log`'a yazdı.

KÖK NEDEN — ADIM YANLIŞ YOLLARDAYDI:
    deploy/financialos.service  (systemd, KULLANILMIYOR)  -> ExecStartPre alembic ✅
    scripts/deploy.sh           (Docker,  KULLANILMIYOR)  -> entrypoint alembic   ✅
    deploy/windows/baslat.ps1   (BETANIN GERÇEKTE KOŞTUĞU YOL)                    ❌
Yani göç adımı iki KULLANILMAYAN yolda vardı; kullanılan yolda yoktu. Bu, BUG #305'in
(L64) ve BUG #304'ün (L63) aynı sınıfı: **bir adımın belgede/başka bir yolda olması,
kullanılan yolda olduğu anlamına gelmez.**

BU KAPI İKİ ŞEYİ AYRI AYRI ÖLÇER — çünkü ayrı yönlerde bozulurlar:
  1. `goc_durumu` GERÇEKTEN ölçüyor mu (bekleyen göçü bekliyor, güncel olanı güncel diyor)?
  2. Başlatma yolu göç adımını TAŞIYOR mu?
İkincisi olmadan birincisi ölü bir araçtır (bugün tam olarak bu oldu: bekçi vardı,
uygulayıcı yoktu). Birincisi olmadan ikincisi ölçülemez bir vaattir.
"""
from __future__ import annotations

import re
from pathlib import Path

from sqlalchemy import create_engine, text

from scripts.goc_durumu import GOC_BEKLIYOR, GUNCEL, OLCULEMEDI, durum

KOK = Path(__file__).resolve().parent.parent
BASLAT = KOK / "deploy" / "windows" / "baslat.ps1"


# ---- 1) ölçüm gerçekten ölçüyor mu ----------------------------------------

def _db(revizyon: str | None):
    eng = create_engine("sqlite:///:memory:")
    if revizyon is not None:
        with eng.begin() as c:
            c.execute(text("create table alembic_version (version_num varchar(32) not null)"))
            c.execute(text("insert into alembic_version values (:r)"), {"r": revizyon})
    return eng


def test_BEKLEYEN_goc_yakalanir():
    kod, mesaj = durum(_db("e7f8a9b0c1d2"))
    assert kod == GOC_BEKLIYOR, mesaj
    assert "e7f8a9b0c1d2" in mesaj, "hangi sürümde kaldığı yazılmalı — teşhis edilebilirlik"


def test_GUNCEL_sema_bekleyen_sayilmaz():
    from app.schema_guard import _kod_head
    kod, mesaj = durum(_db(_kod_head()))
    assert kod == GUNCEL, mesaj


def test_alembic_version_YOKSA_kilitlenmez():
    """Test/`create_all` yolu göç görmez — geliştirmeyi kilitlemeyiz (schema_guard ile aynı ilke)."""
    kod, _ = durum(_db(None))
    assert kod == GUNCEL


def test_cikis_kodlari_birbirinden_AYRI():
    """`0 = güncel` ile `1 = ölçülemedi` karışırsa, bilinmeyen sessizce 'güncel' sayılır (L45)."""
    assert GUNCEL != GOC_BEKLIYOR != OLCULEMEDI != GUNCEL


# ---- 2) başlatma yolu adımı taşıyor mu ------------------------------------

def test_WINDOWS_BASLATMA_YOLU_gocu_uygular():
    """
    Bugünkü kesintinin kapısı. `baslat.ps1` uygulamayı başlatmadan ÖNCE göç durumunu
    kontrol etmeli ve gerekiyorsa uygulamalı.
    """
    metin = BASLAT.read_text(encoding="utf-8-sig")
    assert "goc_durumu" in metin, "başlatma yolu göç durumunu HİÇ ölçmüyor"
    assert re.search(r"alembic.+upgrade.+head", metin), \
        "başlatma yolu göçü uygulamıyor — her yeni migration betayı sessizce düşürür"


def test_GOC_ONCESI_YEDEK_ALINIR():
    """
    SQLite'ta `batch_alter_table` tabloyu YENİDEN KURAR. Göçü yedeksiz koşmak, canlı
    beta verisini tek bir bozuk migration'a emanet etmektir.
    """
    metin = BASLAT.read_text(encoding="utf-8-sig")
    assert "scripts.backup" in metin, "göç öncesi yedek adımı yok"


def test_GOC_BASARISIZSA_UYGULAMA_BASLATILMAZ():
    """
    Yarım göçle açılan uygulama, eksik kolonu okuyan her uçta 500 verir — kapalı olmaktan
    DAHA KÖTÜ (baslat.ps1'in kendi başlığındaki gerekçenin aynısı).
    """
    metin = BASLAT.read_text(encoding="utf-8-sig")
    assert re.search(r"GOC BASARISIZ|goc basarisiz", metin, re.IGNORECASE), \
        "göç başarısızlığında durduran bir dal yok"


def test_KULLANILMAYAN_yollar_da_adimi_TASIMAYA_devam_etsin():
    """
    systemd ve Docker yollarında adım ZATEN vardı; kaldırılırsa bu kapı sessizce
    yarım kalır (bir gün o yollara dönülürse aynı kesinti orada tekrarlanır).
    """
    servis = (KOK / "deploy" / "financialos.service").read_text(encoding="utf-8")
    assert "alembic" in servis and "upgrade" in servis
