"""
BUG #338 KAPISI — KİŞİSEL VERİ KAPISI YANLIŞ YÜZEYİ KORUYORDU.

ÖLÇÜLEN OLAY (4 Eylül 2026): depo **PUBLIC**'ti (`visibility: public`, GitHub API ile
kimliksiz doğrulandı) ve izlenen dosyalarda kurucunun gerçek verisi duruyordu:

    scripts/coach_altin.py : iki KREDİ HESAP NUMARASI (`1304-78…`)
    15 dosya               : gerçek e-posta adresi
    166 dosya              : banka adları

`test_imaj_kisisel_veri` bunların HİÇBİRİNİ görmüyordu, çünkü kapsamı **Docker imajı**:
862 izlenen dosyanın yalnız **186'sını** tarıyor. `scripts/coach_altin.py` bile imaj dışı.

Kapı yanlış yüzeyi koruyordu: imaj registry'ye push edilir, ama **depo da yayınlanır** —
ve bu depo fiilen açıktı. Bir koruma, korumak istediği şeyin gerçek dağıtım yüzeyine
bağlanmalıdır. (L63'ün sınıfı: bir şeyin bir yerde doğru olması, KULLANILAN yerde doğru
olduğu anlamına gelmez.)

İKİ KADEMELİ, BİLİNÇLİ:
  * **SERT KAPI (tavan 0)** — hiçbir yerde bulunmaması gerekenler: hesap numarası, IBAN,
    kart numarası. Bunlar tek başına kimliklendirici ve hiçbir test/fixture bunlara
    ihtiyaç duymaz. Bugün 1 ihlal vardı, temizlendi.
  * **RATCHET (mevcut sayı tavan)** — ad/banka adı/e-posta. Bunlar 166 ve 15 dosyada ve
    çoğu aylar öncesinden; hepsini bugün temizlemek bu turun işi değil. Ama SAYI ARTAMAZ.
    Yeni bir sızıntı kapıyı kırar; temizlik yapılırsa tavan düşürülür (kazanım kilidi).
    Bu, `kalite_kapisi`nin ruff tavanıyla aynı desendir: mevcut borcu dondur, büyümesini
    engelle.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

# İzlenen dosya listesi BİLEREK yeniden yazılmadı. `test_kacis_dizisi_kapisi.py` bunu zaten
# yazmıştı: `git ls-files`'ı çağıran her yeni kopya ruff'ta bir `S607` daha üretiyor ve
# tavan bu sebeple üst üste üç kez yükselmişti. İlk yazımda bu kapı BEŞİNCİ kopyayı ekledi
# ve tavanı 63 → 64 kırdı; doğru cevap tavanı yükseltmek değil, kopyayı kaldırmaktı.
from scripts.sir_taramasi import izlenen_dosyalar as _izlenen_yollar  # noqa: E402
TAVAN_DOSYASI = KOK / "docs" / "kalite-seruveni" / "kisisel-veri-baseline.json"

#: Hiçbir yerde bulunamaz — tek başına kimliklendirici.
SERT_DESENLER = {
    "hesap_numarasi": r"\b\d{4}-\d{7}\b",
    "iban": r"\bTR\d{2}[ ]?(?:\d{4}[ ]?){5}\d{2}\b",
    # Kart deseni, DAHA UZUN bir rakam dizisinin ORTASINDAN eşleşmemeli: boşluklu IBAN
    # (`TR33 0006 1005 1978 6457 8413 26`) içinden `0006 1005 1978 6457` çıkıyordu — yanlış
    # pozitif. Çözüm muafiyet listesine o parçayı EKLEMEK DEĞİL (gerçek bir kartı da
    # körleştirirdi); komşuluğu dışlamak. Meşruluk sınaması ayrı testte kilitli.
    "kart_numarasi": r"(?<!\d[ -])\b(?:\d{4}[ -]){3}\d{4}\b(?![ -]\d)",
}

#: Sayısı artamaz (ratchet). Çoğu aylar öncesinden; temizlik ayrı iş.
YUMUSAK_DESENLER = {
    "eposta": r"[\w\.\-]+@(?:gmail|hotmail|outlook|yahoo|yandex)\.[a-z]+",
    "banka_adi": r"\b(?:Enpara|Ziraat)\b|\bGaranti\s+(?:Kredi|Kart|Hesab|Bankası)",
}

#: MUAFİYET DEĞERİN KENDİSİNE BAĞLI, DOSYAYA DEĞİL.
#:
#: Ölçüldü: sert kapı 5 eşleşme buldu ve BEŞİ DE sahte — maskeleme testinin (`log_maskeleme`,
#: `error_tracking`) kendi girdileri ve o testleri anlatan iki belge. Kullanılan IBAN
#: `TR33 0006 1005 1978 6457 8413 26` Türkiye'nin dokümantasyonlarda geçen STANDART örnek
#: IBAN'ı; kart numarası da `1234 5678 9012 3456`.
#:
#: "Şu dosyaları atla" demek kolaydı ama kapıyı KÖRLEŞTİRİRDİ: aynı dosyaya bir gün gerçek
#: bir IBAN girse görülmezdi (L67 — bir kapı, kendi açıklaması ya da kendi girdisi yüzünden
#: kör kalamaz). Muafiyet bu yüzden DEĞERE bağlı: yalnız bu bilinen sahte değerler serbest.
BILINEN_SAHTE = {
    "TR330006100519786457841326",
    "TR33 0006 1005 1978 6457 8413 26",
    "1234 5678 9012 3456",
    "1234-5678-9012-3456",
}

_METIN = {".py", ".md", ".txt", ".json", ".yml", ".yaml", ".ini", ".cfg", ".sh", ".jsx",
          ".js", ".ts", ".tsx", ".html", ".ps1", ".vbs", ".service", ".example"}


def izlenen_dosyalar() -> list[Path]:
    """Git'in izlediği METİN dosyaları — yayın yüzeyi budur."""
    yollar = []
    for satir in _izlenen_yollar():
        p = KOK / satir
        if p.suffix.lower() in _METIN and p.is_file():
            yollar.append(p)
    return yollar


def _tara(desenler: dict[str, str]) -> dict[str, list[str]]:
    bulgular: dict[str, list[str]] = {ad: [] for ad in desenler}
    derli = {ad: re.compile(k) for ad, k in desenler.items()}
    for yol in izlenen_dosyalar():
        goreli = yol.relative_to(KOK).as_posix()
        if goreli.startswith("tests/test_depo_kisisel_veri_kapisi"):
            continue          # kapının KENDİ desenleri bulgu sayılmaz (L67)
        try:
            metin = yol.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for ad, kalip in derli.items():
            for m in kalip.finditer(metin):
                if m.group(0).strip() in BILINEN_SAHTE:
                    continue
                bulgular[ad].append(goreli)
                break
    return bulgular


def test_SERT_desenler_hicbir_izlenen_dosyada_YOK():
    """
    Hesap numarası / IBAN / kart numarası: tavan SIFIR. Hiçbir test ya da fixture bunlara
    ihtiyaç duymaz; bulunmaları daima bir kazadır.
    """
    bulgular = _tara(SERT_DESENLER)
    ihlal = {ad: d for ad, d in bulgular.items() if d}
    assert not ihlal, (
        "Depoda tek başına kimliklendirici veri var (depo yayınlanabilir):\n"
        + json.dumps(ihlal, ensure_ascii=False, indent=2)
    )


def test_YUMUSAK_desenler_ARTMIYOR():
    """
    Ad/banka adı/e-posta: mevcut borç dondurulur, BÜYÜMESİ engellenir. Hepsini bugün
    temizlemek bu turun işi değil (166 dosya, çoğu aylar öncesinden) — ama yeni bir
    sızıntı buradan geçemez. Temizlik yapılırsa tavan DÜŞÜRÜLÜR (kazanım kilidi).
    """
    tavan = json.loads(TAVAN_DOSYASI.read_text(encoding="utf-8"))
    bulgular = _tara(YUMUSAK_DESENLER)
    artan = {ad: {"tavan": tavan[ad], "olculen": len(d), "yeni": sorted(set(d) - set(tavan.get(f"{ad}_dosyalar", [])))[:10]}
             for ad, d in bulgular.items() if len(d) > tavan.get(ad, 0)}
    assert not artan, (
        "Kişisel veri izi ARTMIŞ (depo yayınlanabilir; yeni sızıntı eklenmiş):\n"
        + json.dumps(artan, ensure_ascii=False, indent=2)
        + "\nTemizle, ya da bilinçliyse tavanı GEREKÇESİYLE güncelle."
    )


def test_TAVAN_kazanimi_kilitler():
    """
    Sayı düştüyse tavan da düşmeli — yoksa temizlenen bir sızıntının yeri boş kalır ve
    sessizce yeniden dolar (ruff kapısındaki `--yaz` kazanım kilidiyle aynı ilke).
    """
    tavan = json.loads(TAVAN_DOSYASI.read_text(encoding="utf-8"))
    bulgular = _tara(YUMUSAK_DESENLER)
    gevsek = {ad: {"tavan": tavan[ad], "olculen": len(d)}
              for ad, d in bulgular.items() if len(d) < tavan.get(ad, 0)}
    assert not gevsek, (
        "Kişisel veri izi AZALMIŞ ama tavan güncellenmemiş — kazanım kilitlenmedi:\n"
        + json.dumps(gevsek, ensure_ascii=False, indent=2)
    )


def test_KAPSAM_imajdan_GENIS():
    """
    Kapının varlık sebebi: `test_imaj_kisisel_veri` yalnız imaja giren dosyaları tarıyor
    (ölçüldü: 862 izlenenin 186'sı). Bu kapı YAYIN yüzeyine bakar. Kapsam daralırsa
    aynı kör nokta geri gelir.
    """
    import sys
    sys.path.insert(0, str(KOK / "tests"))
    from tests.test_imaj_kisisel_veri import imaja_giren_dosyalar
    assert len(izlenen_dosyalar()) > len(list(imaja_giren_dosyalar())), \
        "depo taraması imaj taramasından geniş değil — kapı yanlış yüzeyi koruyor"


def test_KART_DESENI_gercek_karti_KACIRMAZ():
    """
    Deseni daralttım (IBAN içinden yanlış pozitif çıkıyordu) — daraltma gerçek bir kartı
    kaçırıyor mu? MEŞRULUK SINAMASI: hayır. Bu test onu kilitler; yoksa bir sonraki
    daraltma kapıyı sessizce körleştirebilir.
    """
    kalip = re.compile(SERT_DESENLER["kart_numarasi"])
    for gercek in ("4321 8765 2109 6543", "5555-4444-3333-2222", "4111111111111111"[:4] +
                   " 1111 1111 1111"):
        assert kalip.search(gercek), f"gerçek kart deseni kaçtı: {gercek}"
    # IBAN içinden eşleşme OLMAMALI
    assert not kalip.search("IBAN TR33 0006 1005 1978 6457 8413 26")
