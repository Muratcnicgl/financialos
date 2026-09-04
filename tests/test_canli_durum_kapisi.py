"""
BUG #328 KAPISI — KAPALI BETA 24,5 SAAT SESSİZCE KAPALIYDI.

`logs/servis.log`'tan ölçülen zaman çizelgesi:
    02/09 10:35  son başarılı açılış
    03/09 08:50  ilk BASLATILAMADI (göç uygulanmamış; schema_guard doğru davranıp açmadı)
    ...          sağlık görevi 10 dakikada bir denedi → **45 başarısız deneme**
    04/09 09:21  elle onarıldı

Arıza gürültülüydü ama **görünmezdi**: her başarısızlık bir günlük dosyasına yazıldı ve o
dosyaya kimse bakmadı. BUG #326 bu ÖZEL arızayı (uygulanmamış göç) kendi kendine çözer;
bir sonraki açılış hatası (SECRET_KEY, port, kapasite, bozuk `.env`) yine aynı sessizlikle
sürerdi. **L61: ölçen sistem, telafi eden ya da HABER VEREN sistem değildir.**

ÇÖZÜM YENİ KANAL İCAT ETMEZ: `scripts/ci_durum.py` aynı sorunu uzak CI için çözmüştü
(30+ koşum kırmızıydı, kimse görmüyordu) ve çözümü operatörün ZATEN her gün yaptığı işe —
commit'e — bir satır iliştirmekti. Aynı desen canlı servise uygulandı.

BU KAPI ÜÇ AYRI ŞEYİ ÖLÇER, ÇÜNKÜ ÜÇÜ AYRI YÖNDE BOZULUR:
  1. Kapalıyı KAPALI görüyor mu?           (körlük)
  2. Ayakta iken SUSUYOR mu?                (gürültü → okunmayan uyarı, L22)
  3. Hook onu ÇAĞIRIYOR mu?                 (ölü araç — bugünkü arızanın ta kendisi)
Üçüncüsü olmadan ilk ikisi bir vaattir: bugün `schema_guard` vardı ve doğru çalışıyordu,
eksik olan onu GÖRÜNÜR kılan bağdı.
"""
from __future__ import annotations

from pathlib import Path

from scripts.canli_durum import AYAKTA, KAPALI, saglik, son_hata

KOK = Path(__file__).resolve().parent.parent
HOOK = KOK / ".githooks" / "pre-commit"


def test_cevap_vermeyen_servis_KAPALI_sayilir():
    """Bağlanamamak KAPALI'dır — bilinmeyen 'ayakta' değildir (L45)."""
    ok, aciklama = saglik(port=9, zaman_asimi=1.0)
    assert ok is False
    assert aciklama, "neden kapalı olduğu boş geçilemez"


def test_cikis_kodlari_ayri():
    assert AYAKTA == 0 and KAPALI == 1


def test_HOOK_canli_durumu_CAGIRIYOR():
    """
    Kapının çekirdeği. Araç var olup çağrılmazsa bugünkü arıza aynen tekrarlar —
    'ölçen ama haber vermeyen sistem'.
    """
    metin = HOOK.read_text(encoding="utf-8")
    assert "canli_durum" in metin, "pre-commit canlı durumu hiç sormuyor — araç ölü"


def test_HOOK_COMMITI_ENGELLEMEZ():
    """
    Bilinçli sınır: bu bir KAPI değil UYARIDIR. Servis kapalıyken commit atamamak,
    tam da servisi onaracak commit'i engellerdi. `ci_durum` ile aynı gerekçe.
    """
    metin = HOOK.read_text(encoding="utf-8")
    satir = [s for s in metin.splitlines() if "canli_durum" in s]
    assert satir, "çağrı yok"
    for s in satir:
        assert "|| true" in s, f"çağrı commit'i düşürebilir: {s.strip()}"
        assert "--sessiz" in s, f"ayakta iken de konuşuyor (gürültü): {s.strip()}"


def test_son_hata_okunamayan_dosyada_COKMEZ():
    """Bir görünürlük aracı, bakacağı dosya yokken çökemez — sessiz kalması da çökmesi de kötü."""
    assert son_hata(KOK / "logs" / "olmayan-dosya.log") == []


def test_gercek_servis_logundan_TESHIS_cikariyor():
    """
    'Kapalı' demek yetmez, NEDEN kapalı olduğu da görünmeli — bugünün dersi teşhisin
    zaten dosyada durduğu ve kimsenin açmadığıydı.
    """
    log = KOK / "logs" / "servis.log"
    if not log.exists():
        return  # taze klonda günlük yok; kapı yine de kurulu
    satirlar = son_hata(log)
    assert isinstance(satirlar, list)
    assert len(satirlar) <= 3, "çok satır basmak uyarıyı okunmaz yapar"


def test_TESHIS_GERCEKTEN_CIKARILIYOR(tmp_path):
    """
    Mutasyon bunu yazdırdı: `son_hata`'yı boş liste döndürmeye çevirmek hiçbir testten
    düşmüyordu — yani araç "KAPALI" deyip NEDENİNİ hiç basmasa da kapı yeşil kalıyordu.
    Oysa aracın bütün değeri sebebi göstermesinde; "kapalı" tek başına eyleme geçirilemez
    (bugün üçüncü kez aynı ders: `uslup=-`, `grounded=-`, `PAYLOAD_GECERSIZ`).

    Gerçek `servis.log`'a bağlanmaz — o dosya bir gün temizlenirse test sessizce
    körleşirdi. Kendi günlüğünü kurar.
    """
    log = tmp_path / "servis.log"
    log.write_text(
        "2026-09-03 08:50:48 [baslat] baslatiliyor (port 8000)\n"
        "2026-09-03 08:50:48 [baslat] BASLATILAMADI — son hatalar: logs/uvicorn.err.log\n"
        "2026-09-03 08:50:48 [baslat]   | RuntimeError: sema KOD ILE UYUSMUYOR\n",
        encoding="utf-8")
    satirlar = son_hata(log)
    assert satirlar, "günlükte açık bir hata var ama teşhis çıkarılmadı"
    assert any("BASLATILAMADI" in s or "RuntimeError" in s for s in satirlar), satirlar
