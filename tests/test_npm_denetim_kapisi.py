"""
BUG #329 KAPISI — "AÇIK VAR" İLE "ÖLÇEMEDİM" AYNI RENK OLAMAZ.

ÖLÇÜLEN OLAY (4 Eylül 2026): CI arka arkaya iki koşumda kırmızıydı; backend (3435 test)
ve e2e geçiyor, düşen tek adım `npm audit --omit=dev --audit-level=high`. Loga bakınca
sebep bir güvenlik açığı DEĞİLDİ:

    npm warn audit 503 Service Unavailable - POST .../security/audits/quick
    { error: 'Service Unavailable' }
    npm error audit endpoint returned an error

Adım **7 dakika** deneyip düştü. `npm audit` çıkış kodu 1'i iki ayrı durum için kullanıyor:
(a) yüksek/kritik açık bulundu, (b) denetim ucu cevap vermedi. Kapı ikisini ayırmıyordu.

NEDEN BU BİR GÜVENLİK SORUNU: bu proje bir kez **30 koşum boyunca kırmızı kaldı ve kimse
fark etmedi** (BUG #295-#300). Üçüncü tarafın kesintisi her seferinde kırmızı üretirse
kırmızı normalleşir ve GERÇEK bir açık görünmez olur. Yani "her ihtimalde kırmızı" tavrı
güvenliği artırmaz, azaltır. Aynı ilke `pip-audit`/`ci_durum` tarafında da yazılı: L45 —
bilinmeyen, sıfır değildir; ama kötü de değildir, AYRI raporlanır.

Testler ağ KULLANMAZ: sınıflandırıcı saftır ve gerçek `npm` çıktılarıyla beslenir.
"""
from __future__ import annotations

from pathlib import Path

from scripts.npm_denetim import ACIK_VAR, OLCULEMEDI, TEMIZ, dosyadan, siniflandir

# --- gerçek npm çıktıları (kısaltılmış ama YAPISI aynen) ---------------------

TEMIZ_CIKTI = """{"auditReportVersion":2,"vulnerabilities":{},
 "metadata":{"vulnerabilities":{"info":0,"low":0,"moderate":0,"high":0,"critical":0,"total":0}}}"""

ACIK_CIKTI = """{"auditReportVersion":2,"vulnerabilities":{"foo":{"severity":"high"}},
 "metadata":{"vulnerabilities":{"info":0,"low":0,"moderate":0,"high":1,"critical":0,"total":1}}}"""

ORTA_CIKTI = """{"auditReportVersion":2,"vulnerabilities":{"bar":{"severity":"moderate"}},
 "metadata":{"vulnerabilities":{"info":0,"low":2,"moderate":3,"high":0,"critical":0,"total":5}}}"""

# CI'da ölçülen gerçek durum (503):
UC_HATASI = """{"error":{"code":"E503","summary":"Service Unavailable",
 "detail":"POST https://registry.npmjs.org/-/npm/v1/security/audits/quick"}}"""

BOZUK_CIKTI = "npm error audit endpoint returned an error\n"


def test_temiz_cikti_TEMIZ():
    assert siniflandir(TEMIZ_CIKTI)[0] == "temiz"


def test_yuksek_acik_ACIK_sayilir():
    sonuc, aciklama = siniflandir(ACIK_CIKTI)
    assert sonuc == "acik" and "high" in aciklama


def test_ORTA_seviye_acik_kirmizi_YAPMAZ():
    """
    Eşik bilinçli: adı da "yüksek/kritik → kırmızı". Orta/düşük seviyeyi kırmızı yapmak,
    kırmızıyı normalleştiren tam olarak o davranıştır (BUG #298'in dersi).
    """
    assert siniflandir(ORTA_CIKTI)[0] == "temiz"


def test_UC_HATASI_acik_SAYILMAZ_olculemedi_sayilir():
    """Bugünkü CI kırmızısının ta kendisi: 503, bir güvenlik açığı değildir."""
    sonuc, aciklama = siniflandir(UC_HATASI)
    assert sonuc == "olculemedi", aciklama
    assert "Service Unavailable" in aciklama or "hata" in aciklama


def test_JSON_OLMAYAN_cikti_olculemedi_sayilir():
    """npm uç hatasında düz metin de basabiliyor — 'çözemedim' ≠ 'temiz'."""
    assert siniflandir(BOZUK_CIKTI)[0] == "olculemedi"


def test_metadata_YOKSA_temiz_SAYILMAZ():
    """
    Vakumsal yeşil yasağı (L28): 'hiç bulgu bulamadım' bir başarı değildir. Çıktı
    beklenen alanı taşımıyorsa denetim tamamlanmamıştır.
    """
    assert siniflandir('{"auditReportVersion":2}')[0] == "olculemedi"


# --- çıkış kodu sözleşmesi --------------------------------------------------

def test_ACIK_VAR_durdurur_OLCULEMEDI_durdurmaz():
    """
    Sözleşmenin çekirdeği. `OLCULEMEDI == 0` bilinçlidir ve bedeli yazılıdır: üçüncü
    tarafın kesintisi projeyi kilitlemez, ama çıktı bunu büyük harfle söyler.
    """
    assert ACIK_VAR == 1
    assert OLCULEMEDI == 0 and TEMIZ == 0


# --- dosyadan okuma -------------------------------------------------------

def test_dosyadan_gercek_cikti_siniflanir(tmp_path):
    y = tmp_path / "audit.json"
    y.write_text(TEMIZ_CIKTI, encoding="utf-8")
    assert dosyadan(y)[0] == "temiz"


def test_DOSYA_YOKSA_temiz_SAYILMAZ(tmp_path):
    """
    npm hiç koşamamışsa çıktı da yoktur. "Dosya yok" bir başarı değildir (L28) —
    vakumsal yeşile düşmek, denetimi hiç yapmamakla aynı şeydir.
    """
    assert dosyadan(tmp_path / "olmayan.json")[0] == "olculemedi"


def test_UC_HATASI_dosyadan_da_olculemedi(tmp_path):
    y = tmp_path / "audit.json"
    y.write_text(UC_HATASI, encoding="utf-8")
    assert dosyadan(y)[0] == "olculemedi"


# --- CI gerçekten bunu çağırıyor mu ----------------------------------------

def test_CI_ADIMI_bu_araci_CAGIRIYOR():
    """
    Araç var olup çağrılmazsa bugünkü kırmızı aynen tekrarlar — 'ölü kapı'.
    (Aynı ders bugün BUG #326'da da yaşandı: adım kullanılmayan yollardaydı.)
    """
    kok = Path(__file__).resolve().parent.parent
    ci = (kok / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "npm_denetim" in ci, "CI hâlâ çıplak `npm audit` koşuyor — 503 yine kırmızı yapar"
    assert "audit.json" in ci, "CI, denetim çıktısını dosyaya yazmıyor — betik neyi okuyacak?"
