"""
Türkiye'ye özgü vergi/getiri dönüşümleri — SAF, deterministik, DB'siz.

NEDEN VAR (Wave-K, K-B / altın senaryo G4):
Ölçüm (2 Eyl 2026): koça "yıllık %35,5 brüt faiz veriyor, krediye ödesem ne olur?" diye
soruldu. Koç **stopajı hiç anmadan** brüt mevduat oranını kredinin aylık faiziyle
karşılaştırdı ve üstüne kredi oranını da yanlış söyledi (%4,25 — doğrusu %4,55). Yani
kullanıcıya iki farklı BİRİMDEKİ iki sayı, aynı sayıymış gibi sunuldu.

Bu bir prompt sorunu değil, MİMARİ sorunudur: `docs/architecture.md`ın ilkesi
*"Rules Engine karar verir, LLM açıklar"*. Vergi ve bileşiklendirme aritmetiğini modelden
beklemek, o ilkeyi tam da en pahalı yerde çiğnemekti — çünkü buradaki hata kullanıcıyı
yanlış finansal karara götürür. Hesap buraya taşındı; koç yalnız okur.

VARSAYIM YASAK — ORANLAR SABİT DEĞİL, ÖLÇÜLMÜŞ VE TARİHLİDİR:
Stopaj oranları Cumhurbaşkanı kararıyla değişir. Bu modül **yalnız kaynağı olan oranı**
taşır ve her oran bir YÜRÜRLÜK TARİHİYLE gelir. Kaynağı olmayan vade dilimleri için sayı
UYDURULMAZ — `None` döner (L45: *bilinmeyen, sıfır değildir*). `None` gören çağıran taraf
"bilmiyorum" demek zorundadır; sessizce %0 varsaymak, vergisiz bir getiri vaat etmek olurdu.

TAZELİK: oran `STOPAJ_TAZELIK_GUN` günden eskiyse `bayat=True` işaretlenir. Kod bu durumda
da hesabı yapar (çalışmayı durdurmak kullanıcıya yardım etmez) ama sonucu BAYAT diye
etiketler; koç bunu kullanıcıya söyleyebilsin diye bayrak çıktıda taşınır.
"""
from __future__ import annotations

import os
from datetime import date
from typing import Dict, Optional

#: Bu oranların OKUNDUĞU tarih. Oran değişirse hem değer hem bu tarih güncellenir.
#: Kaynak: 1 Eylül 2026'da yapılan canlı analiz (mevduat ve TL para piyasası fonu getirisi
#: aynı %17,5 stopajla nete çevrildi). Değiştirmeden önce güncel mevzuata BAKILIR.
STOPAJ_YURURLUK = date(2026, 9, 1)

#: Kaç gün sonra "bayat" sayılır. Stopaj yılda birkaç kez değişebiliyor; 180 gün, oranı
#: körü körüne kullanmakla her koşumda mevzuat okumak arasında ölçülü bir sınır.
STOPAJ_TAZELIK_GUN = int(os.getenv("STOPAJ_TAZELIK_GUN", "180"))

#: YALNIZ KAYNAĞI OLAN DİLİMLER. Diğer vadeler için oran YOK — ve olmadığı için de
#: uydurulmaz. Anahtar: ürün kodu → (vade üst sınırı gün, stopaj %).
#: `.env` ile geçersiz kılınabilir (mevzuat değiştiğinde kod dağıtmadan düzeltilsin).
_VARSAYILAN_ORANLAR: Dict[str, float] = {
    # TL vadeli mevduat, vadesi 6 aya kadar olanlar.
    "try_mevduat_6ay": 17.5,
    # TL para piyasası / kısa vadeli borçlanma araçları fonu.
    "try_para_piyasasi_fonu": 17.5,
}

#: Ürünün geçerli olduğu azami vade (gün). Bunun ÜSTÜNDEKİ vadeler için oranımız YOK.
_VADE_UST_SINIRI: Dict[str, Optional[int]] = {
    "try_mevduat_6ay": 183,
    "try_para_piyasasi_fonu": None,   # fonda vade kavramı yok
}


#: Ürün kodu → ortam değişkeni adı. İsim `f"STOPAJ_{urun.upper()}"` diye TÜRETİLMEZ:
#: türetilen ad kaynakta hiçbir yerde GEÇMEZ, yani operatör `grep` ile bulamaz ve
#: `test_env_adi_kapisi` gibi bir kapı da göremez (BUG #304b'nin sınıfı: davranışı
#: değiştiren ama görünmeyen anahtar). Ad, aranabilir olmak zorundadır.
#: Para birimi kodu `TRY`dir, `TL` değil: `money_format.VARSAYILAN_KOD` tek kaynaktır ve
#: "TL" orada yalnız bir EŞANLAMLIDIR. Bu ayrım ileride önem kazanır — döviz mevduatının
#: stopajı farklıdır ve ürün kodu para birimini net söylemek zorundadır.
_ENV_ADLARI: Dict[str, str] = {
    "try_mevduat_6ay": "STOPAJ_TRY_MEVDUAT_6AY",
    "try_para_piyasasi_fonu": "STOPAJ_TRY_PARA_PIYASASI_FONU",
}


def _env_orani(urun: str) -> Optional[float]:
    ad = _ENV_ADLARI.get(urun)
    if not ad:
        return None
    ham = os.getenv(ad, "").strip()
    if not ham:
        return None
    try:
        oran = float(ham.replace(",", "."))
    except ValueError:
        return None
    # Geçersiz bir override sessizce %0'a düşerse vergisiz getiri vaat ederiz.
    return oran if 0.0 <= oran <= 100.0 else None


def stopaj_orani(urun: str, vade_gun: Optional[int] = None) -> Optional[float]:
    """
    Ürün ve vadeye göre stopaj yüzdesi. Kaynağı olmayan durumda **None** (sıfır değil).

    `vade_gun` verilirse ürünün üst sınırıyla karşılaştırılır: 6 aylık dilimin oranını
    2 yıllık bir mevduata uygulamak, bilmediğimiz bir sayıyı biliyormuş gibi kullanmaktır.
    """
    if urun not in _VARSAYILAN_ORANLAR:
        return None
    sinir = _VADE_UST_SINIRI.get(urun)
    if vade_gun is not None and sinir is not None and vade_gun > sinir:
        return None
    ozel = _env_orani(urun)
    return ozel if ozel is not None else _VARSAYILAN_ORANLAR[urun]


def bayat_mi(bugun: date) -> bool:
    """
    Oranlar tazelik penceresini aştı mı? **Gün ZORUNLUDUR, sunucudan okunmaz.**

    `date.today()` yedeği bilerek YOK. Muafiyet isteyip gerekçe yazmak da mümkündü
    (`tz-exempt`), ama muafiyet tavanı kapısının sorduğu soru şuydu: *bu muafiyete gerçekten
    ihtiyaç var mı?* Yanıt hayırdı — gün zaten `generate_cockpit(user_id, today, db)`
    zincirinde taşınıyor. Bir kaçış deliği açmaktansa parametreyi zorunlu kılmak, hem daha
    dürüst hem de kullanıcının günüyle sunucununkini bir daha asla karıştırmayacak.
    """
    return (bugun - STOPAJ_YURURLUK).days > STOPAJ_TAZELIK_GUN


def net_yillik(brut_yillik: float, urun: str = "try_mevduat_6ay",
               vade_gun: Optional[int] = None) -> Optional[float]:
    """Brüt yıllık %'yi stopajdan arındırır. Oran bilinmiyorsa None."""
    oran = stopaj_orani(urun, vade_gun)
    if oran is None:
        return None
    return round(brut_yillik * (1.0 - oran / 100.0), 4)


def aylik_esdeger(net_yillik_yuzde: float, *, bilesik: bool = True,
                  gun: int = 30) -> float:
    """
    Yıllık net oranı, kredi faiziyle KIYASLANABİLİR aylık %'ye çevirir.

    `bilesik=True` (varsayılan) günlük bileşiklendirme varsayar — mevduat/birikim hesapları
    Türkiye'de fiilen böyle işletilir ve 1 Eyl ölçümünde de böyle hesaplandı. `False` basit
    bölmedir (yıllık/12); ikisi arasındaki fark %35,5 brütte yaklaşık 0,1 puandır, yani
    kararı çevirmez ama iki farklı yöntemi tek sayıymış gibi sunmak yanlış olurdu.
    """
    if not bilesik:
        return round(net_yillik_yuzde / 12.0, 4)
    gunluk = net_yillik_yuzde / 100.0 / 365.0
    return round(((1.0 + gunluk) ** gun - 1.0) * 100.0, 4)


def mevduat_karsilastirmasi(brut_yillik: float, bugun: date, *,
                            urun: str = "try_mevduat_6ay",
                            vade_gun: Optional[int] = None) -> Dict:
    """
    Bir mevduat/fon teklifini, borç faiziyle AYNI BİRİME (aylık net %) çevirir.

    Dönüş her zaman `brut_yillik`i taşır; stopaj bilinmiyorsa `net_*` alanları None kalır
    ve `neden` alanı sebebi söyler — çağıran taraf "bilmiyorum"u yazabilsin diye.
    """
    oran = stopaj_orani(urun, vade_gun)
    if oran is None:
        return {
            "brut_yillik": round(brut_yillik, 4),
            "stopaj_yuzde": None,
            "net_yillik": None,
            "net_aylik": None,
            "bayat": bayat_mi(bugun),
            "neden": f"'{urun}' icin kaynakli stopaj orani yok"
                     + (f" (vade {vade_gun} gun sinirin ustunde)" if vade_gun else ""),
        }
    net_y = net_yillik(brut_yillik, urun, vade_gun)
    return {
        "brut_yillik": round(brut_yillik, 4),
        "stopaj_yuzde": oran,
        "net_yillik": net_y,
        "net_aylik": aylik_esdeger(net_y),
        "bayat": bayat_mi(bugun),
        "neden": None,
    }


def esigi_asmak_icin_gereken_brut(esik_aylik_yuzde: float, *,
                                  urun: str = "try_mevduat_6ay",
                                  vade_gun: Optional[int] = None) -> Optional[float]:
    """
    Bir mevduatın borç ödemekten daha iyi olması için gereken **brüt yıllık %**.

    NEDEN BU SAYI: altın senaryo G4'ün asıl sorusu "hangisi daha mantıklı?" — ve buna tek
    bir eşik sayısıyla cevap verilebilir. Kullanıcının eline geçen teklif bu sayının
    altındaysa karar nettir, tartışma bitmiştir; üstündeyse konuşmaya değer. Koçun bunu
    türetmesini beklemek, aynı hatayı (brütü netle kıyaslamak) tekrar davet ederdi.

    Yöntem: aylık eşik → günlük bileşik → yıllık net → stopajdan geri sarılarak brüt.
    Stopaj bilinmiyorsa None (L45: bilinmeyen, sıfır değildir).
    """
    oran = stopaj_orani(urun, vade_gun)
    if oran is None or esik_aylik_yuzde <= 0:
        return None
    gunluk = (1.0 + esik_aylik_yuzde / 100.0) ** (1.0 / 30.0) - 1.0
    net_yillik_yuzde = gunluk * 365.0 * 100.0
    return round(net_yillik_yuzde / (1.0 - oran / 100.0), 2)
