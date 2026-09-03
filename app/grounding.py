"""
Grounding Check — LLM çıktı doğrulama (Kalite serüveni LLM-003).

DEVRİMSEL ADIM / VİZYON: Kök vizyonun "kusursuzluk, sıfır hata, VARSAYIM YASAK" mandatını
kod seviyesinde enforce eder. "Rules Engine karar verir, LLM açıklar" ilkesinin doğrulama
katmanı: koçun cevabında geçen HER para tutarı, deterministik cockpit dict'indeki bir değere
izlenebilir olmalı. İzlenemeyen tutar = potansiyel "silent hallucination" (2026 agentic-finans
başarısızlık modu) → işaretlenir, güven düşürülür.

Bu bir UYARI sinyalidir, sert blok değil (koç meşru türev sayılar üretebilir); amaç şeffaflık.
Saf/deterministik — LLM/ağ gerektirmez, birim-test edilebilir.

GUNCELLEMELER
- BUG #322 fix (3 Eyl 2026, K3): **izin listesi, modelin GÖRDÜĞÜ veriyle aynı olmalıydı.**
  `CoachEngine` modele son turları veriyor; izin listesi ise yalnız O ANKİ mesajı sayıyordu.
  Kullanıcının bir tur önce söylediği tutarı doğru hatırlayan koç halüsinasyon damgası
  yiyor, üretimde güveni 0,4'e düşüyordu. `gecmis_kullanici_mesajlari` eklendi; koçun
  KENDİ cevapları bilinçli olarak dışarıda (döngüsellik yasağı — bkz. fonksiyon docstring'i).
- **ÖLÇÜLMÜŞ SINIR (3 Eyl 2026, açık iş): bu dedektör YANLIŞ BERAAT de veriyor.**
  Eşleşme %2 oransal toleransla yapılır ve kokpit onlarca sayısal yaprak taşır; ölçüldü:
  100-20.000 aralığından rastgele bir tutar, hiçbir dayanağı olmasa da **%10,7** olasılıkla
  "izlenebilir" sayılıyor (27 yaprakla; canlı kokpit daha zengin). Canlı bir örnekte koçun
  YANLIŞ hesabı (3.536) alakasız bir yaprağa denk geldiği için geçti, DOĞRUSU (3.776)
  düşerdi. Tolerans daraltılmadı — yuvarlanmış doğru cevabı düşürürdü (BUG #316 dersi).
  Doğru yön eşleşmeyi izlenebilir kılmak; `masterprompt-koc.md` §9.4'te açık madde.
- BUG #256 fix (7 Agu 2026, H4): iki sessiz körlük kapatıldı.
  (1) **Etiket koda gömülüydü.** Desen `…\\s*TL` sabitiyle yazılmıştı; para birimi etiketi
      değişirse desen hiçbir tutar bulamaz, `checked=0` olur ve fonksiyon `{"ok": True}`
      döner — yani doğrulama **vakumsal yeşile** düşer. Etiket artık tek kaynaktan gelir
      (`app/money_format.taninan_etiketler`) ve o kaynakla birlikte değişir (ders L21).
  (2) **"Para gibi görünen ama etiketsiz" tutarlar hiç denetlenmiyordu.** Koç
      `"net değerin 31.343"` yazdığında (etiket unutulmuş ya da başka birimde) eski kod
      bunu görmezden geliyordu; halüsinasyon etiketi düşürerek denetimden kaçabiliyordu.
      Artık bu sayılar `etiketsiz` olarak raporlanır ve sonucu KIRMIZI yapar (ders L28:
      "hiç eşleşme bulamadım" başarı değildir).

YANLIŞ-POZİTİF SINIRI (bilinçli): `etiketsiz` yalnız **para biçiminde yazılmış** sayıları
sayar — binlik ayıracı ya da iki haneli ondalık virgülü olan ve eşiğin üstünde olanlar.
Yüzdeler, tarihler, yıl/gün/ay/adet gibi birim taşıyan sayılar ve ayraçsız düz tam sayılar
(2026, 30) kapsam dışıdır; aksi halde kapı gürültü üretir ve kimse ciddiye almaz (L22).
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from app.money_format import taninan_etiketler

# Para biçiminde yazılmış sayı: "42.100,50" / "1.234" / "268,75"
# (binlik ayıracı ya da ondalık virgül taşıyanlar; ayraçsız düz sayı da yakalanır ama
#  etiketsiz taramada ayrıca "biçimli mi" kontrolünden geçer.)
#: BUG #316 — BİNLİK AYIRACI YALNIZ NOKTA DEĞİLDİR. (TEK KAYNAK)
#:
#: Ölçülen defekt (1 Eyl 2026, üretim kaydı): koç tutarları BOŞLUKLU binlik ayıraçla
#: yazıyor — `4 573,52 TL`, `79 625,85 TL`, `15 000 TL`. Türkçede geçerli bir yazımdır ve
#: LLM'lerin doğal çıktısıdır. Desen yalnız noktayı tanıdığı için `4 573,52` metninden
#: sadece `573,52` yakalanıyor, cockpit'te bulunamıyor ve **doğru cevap "silent
#: hallucination" damgası yiyordu**. Üretimde 14 cevabın 6'sı (%43) bu yüzden ihlalli
#: görünüyordu; işaretlenen sayılar gerçek tutarların KUYRUKLARIYDI (4.**573,52** nakit
#: kasa, 79.**625,85** kredi borcu, 4.**109,90** ve 2.**747,22** taksitler).
#: Uçtan uca kanıt: aynı doğru cevap noktalı yazımda `ok=True`, boşluklu yazımda
#: `ok=False, unverified=[573.52, 625.85]`.
#:
#: Zarar sessizdi ve çift yönlüydü: (a) `chat()` doğru cevapta güveni 0.4'e düşürüyordu,
#: (b) eval'in `grounded` kriteri aynı dedektöre bağlı olduğu için **kalite oranı
#: olduğundan kötü** görünüyordu.
#:
#: Ayıraç kümesi: nokta + boşluk ailesi (normal, kırılmaz, dar kırılmaz, ince boşluk).
#: Kaçış dizisiyle yazılır, LİTERAL görünmez karakterle DEĞİL: kırılmaz boşluk (U+00A0),
#: dar kırılmaz boşluk (U+202F) ve ince boşluk (U+2009) kaynakta gözle ayırt edilemez;
#: kopyala-yapıştırda ya da düzenleyici temizliğinde sessizce kaybolur ve desen körleşir.
#: (Aynı sınıf: BUG #312 — görünmeyen/kaçan karakterin kaynakta bıraktığı sessiz hasar.)
_BINLIK = "[.\u0020\u00A0\u202F\u2009]"
_SAYI = rf"\d{{1,3}}(?:{_BINLIK}\d{{3}})+(?:,\d+)?|\d+(?:,\d+)?"

# Etiketsiz taramada yok sayılacak birimler — bunlar para değildir.
_BIRIM_SONRASI = (
    r"gün|gun|ay|yıl|yil|hafta|saat|dakika|adet|kez|lot|kişi|kisi|puan|"
    r"%|yaş|yas|derece|km|kg|tl/gün|tl/gun"
)


@lru_cache(maxsize=8)
def _etiketli_desen(kod: Optional[str]) -> re.Pattern[str]:
    """'<sayı> <etiket>' deseni — etiketler para-birimi tek kaynağından gelir."""
    etiketler = "|".join(re.escape(e) for e in taninan_etiketler(kod))
    # `\b` KULLANMA: etiketlerden biri sembol (₺) ve sembol harf-olmayan karakterdir —
    # `\b` orada eşleşmez, yani "4.276,14 ₺" desenin dışında kalırdı (sessiz körlük).
    return re.compile(
        # BUG #316: boşluk ayıracı gelince eşleşme bir sayının ORTASINDAN
        # başlayabilir ("2026 300 TL" → "026 300" = 26300). Geriye-bakış bunu keser.
        rf"(?<![\d.,])(?P<num>{_SAYI})\s*(?:{etiketler})(?!\w)", re.IGNORECASE)


@lru_cache(maxsize=8)
def _etiketsiz_desen(kod: Optional[str]) -> re.Pattern[str]:
    """
    Para BİÇİMİNDE yazılmış ama para etiketi taşımayan sayı.

    Zorunlu: binlik ayıracı (1.234) ya da iki haneli ondalık virgül (12,50).
    Ardında para etiketi ya da bir birim kelimesi gelmemeli, önünde % olmamalı.
    """
    etiketler = "|".join(re.escape(e) for e in taninan_etiketler(kod))
    # DİKKAT (kendi tuzağım, 7 Agu): lookahead'i `\s*(?!ETIKET)` diye yazmak İŞE YARAMAZ —
    # `\s*` geri izleyip boşluğu bırakır ve lookahead " TL"nin boşluğunda başarılı olur,
    # yani etiketli tutar "etiketsiz" sayılır. Boşluk lookahead'in İÇİNDE olmalı.
    return re.compile(
        r"(?<![%\d,.])"                                       # önünde % ya da sayı parçası olmasın
        rf"(?P<num>\d{{1,3}}(?:{_BINLIK}\d{{3}})+(?:,\d+)?|\d+,\d{{2}})"  # para BİÇİMİ zorunlu (BUG #316: tek kaynak)
        r"(?![\d.,])"                                         # sayının devamı gelmesin
        rf"(?!\s*(?:{etiketler})(?!\w))"                      # para etiketi gelmiyorsa
        rf"(?!\s*(?:{_BIRIM_SONRASI})\b)"                     # ve birim kelimesi de gelmiyorsa
        r"(?!\s*%)",
        re.IGNORECASE,
    )


#: Silinecek ayıraçlar — `_BINLIK` ile AYNI küme, kaçış dizisiyle yazılır.
_AYIRAC_SIL = str.maketrans("", "", ".\u0020\u00A0\u202F\u2009")


def _to_float_tr(token: str) -> float:
    """TR formatlı sayı ('31.342,86') -> float. Nokta binlik, virgül ondalık."""
    # BUG #316: nokta VE boşluk ailesi binlik ayıracıdır; hepsi silinir, sonra
    # ondalık virgül noktaya çevrilir (sıra önemli).
    return float(token.translate(_AYIRAC_SIL).replace(",", "."))


def _collect_numeric(obj: Any, out: List[float]) -> None:
    """cockpit dict'indeki tüm sayısal yaprakları topla (recursive)."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_numeric(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect_numeric(v, out)


def check_grounding(
    reply: str,
    cockpit: Dict[str, Any],
    user_message: str = "",
    *,
    min_magnitude: float = 100.0,
    rel_tol: float = 0.02,
    abs_tol: float = 1.0,
    para_kodu: Optional[str] = None,
    gecmis_kullanici_mesajlari: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Koç cevabındaki para tutarlarını cockpit değerleriyle karşılaştır.

    Dönüş: `{"ok", "checked", "unverified", "etiketsiz"}`.
      * `unverified` — etiketli ama cockpit'te karşılığı olmayan tutarlar (halüsinasyon şüphesi).
      * `etiketsiz`  — para biçiminde yazılmış ama etiketi olmayan tutarlar (denetimden kaçış).
      * `ok`         — ikisi de boşsa True.

    Ders LLM-003a: Kullanıcının az önce söylediği tutar cockpit'e henüz girmediği
    için (pending action) grounding ihlali vermemeli. user_message içindeki
    tutarlar da 'geçici izinli' sayılır.

    BUG #322 — İZİN LİSTESİ, MODELİN GÖRDÜĞÜ VERİYLE AYNI OLMALI.
    Yukarıdaki ders TEK TURLUK bir konuşma için yazılmıştı; oysa `CoachEngine` modele son
    `max_history_turns` turu veriyor. Ölçülen defekt (3 Eyl 2026): kullanıcı bir turda
    *"Bugün 500 TL yemek harcadım"* dedi, koç iki tur sonra bunu doğru hatırlayıp yazdı ve
    **halüsinasyon damgası yedi** (üretimde güven 0.4'e düşer). `gecmis_kullanici_mesajlari`
    bu boşluğu kapatır.

    **KOÇUN KENDİ ÖNCEKİ CEVAPLARI BİLİNÇLİ OLARAK İZİNLİ DEĞİLDİR** — çağıran taraf yalnız
    `role == "user"` mesajlarını geçirir. Aksi halde bir turda uydurulan sayı sonraki turda
    aklanırdı: denetlenen şey modelin çıktısıyken izin listesini yine modelin çıktısından
    beslemek döngüseldir. Kullanıcı mesajı DIŞ bir olgudur, koç cevabı denetlenenin kendisi.
    """
    etiketli = _etiketli_desen(para_kodu)
    etiketsiz_re = _etiketsiz_desen(para_kodu)

    allowed_raw: List[float] = []
    _collect_numeric(cockpit, allowed_raw)

    # Kullanıcı mesajındaki tutarları da izinli listesine ekle. BUG #322: yalnız BU TURUN
    # mesajı değil, modele verilen geçmişteki kullanıcı mesajları da.
    # `metindeki_tutarlar` kullanılır, `etiketli` deseni DEĞİL: kullanıcı "bugün 500
    # harcadım" diye etiketsiz yazar, koç "500 TL" diye etiketleyerek tekrarlar — yazım
    # biçimi bir ayrım yaratmamalı (BUG #316/#321'in aynı dersi).
    for _mesaj in [user_message, *(gecmis_kullanici_mesajlari or [])]:
        if _mesaj:
            allowed_raw.extend(metindeki_tutarlar(_mesaj))

    allowed = {round(abs(v), 2) for v in allowed_raw}

    unverified: List[float] = []
    checked = 0
    etiketli_araliklar: List[tuple[int, int]] = []
    for m in etiketli.finditer(reply):
        etiketli_araliklar.append(m.span("num"))
        try:
            val = abs(_to_float_tr(m.group("num")))
        except ValueError:
            continue
        if val < min_magnitude:
            continue
        checked += 1
        matched = any(abs(val - a) <= max(abs_tol, rel_tol * a) for a in allowed)
        if not matched:
            unverified.append(round(val, 2))

    # BUG #256: etiketi düşürülmüş tutarlar artık görünür. Etiketli eşleşmelerin içindeki
    # sayılar tekrar sayılmaz (aynı tutar iki kez raporlanmasın).
    etiketsiz: List[float] = []
    for m in etiketsiz_re.finditer(reply):
        bas, son = m.span("num")
        if any(b <= bas and son <= s for b, s in etiketli_araliklar):
            continue
        try:
            val = abs(_to_float_tr(m.group("num")))
        except ValueError:
            continue
        if val < min_magnitude:
            continue
        # BUG #321 — ETİKETSİZ OLMAK, İZLENEMEZ OLMAK DEĞİLDİR.
        #
        # Ölçülen defekt (2 Eyl 2026): koç `"limit 12.000 (%99,8 dolu)"` yazdı. `12000`
        # cockpit'te VAR (`credit_limit`), yalnız para etiketi olmadan yazılmıştı — ve
        # kapı onu "denetimden kaçış" sayıp cevabı KIRMIZI yaptı. Davranış setinde
        # `grounded` kriteri 0/6 çıkıyordu; sebebinin bir kısmı buydu.
        #
        # BUG #256'nın amacı korunur: "halüsinasyon etiketi düşürerek denetimden kaçmasın".
        # Uydurma bir sayı cockpit'te de OLMAYACAĞI için hâlâ yakalanır. Değişen tek şey,
        # izlenebilir bir sayının yalnız YAZIM biçimi yüzünden suçlanmaması.
        # (Aynı sınıf: bir ölçüt, kabul ettiği yazım kadar iyidir — BUG #316.)
        if any(abs(val - a) <= max(abs_tol, rel_tol * a) for a in allowed):
            continue
        etiketsiz.append(round(val, 2))

    return {
        "ok": not unverified and not etiketsiz,
        "checked": checked,
        "unverified": unverified,
        "etiketsiz": etiketsiz,
    }


#: ALTIN SENARYO ÖLÇÜMÜ (Wave-K, K-B) — "koç DOĞRU sayıyı söyledi mi?" sorusunun tek kaynağı.
#:
#: NEDEN BURADA: bu soru, `check_grounding`in sorduğu sorunun AYNASIDIR — orada "cevaptaki
#: sayı cockpit'te var mı", burada "beklenen sayı cevapta var mı". İkisi de aynı ayıraç
#: kümesine bağlıdır. Ayrı bir modülde ikinci bir sayı deseni yazmak, BUG #316'nın tam olarak
#: tekrar etmesi demekti: iki desenden biri boşluklu binlik ayıraca kör kalır, hangisinin kör
#: olduğu ancak canlı koşumda anlaşılır. Tek kaynak (ders L21).
_TUTAR_DESENI = re.compile(rf"(?<![\d.,])(?P<num>{_SAYI})(?![\d.,])")


def metindeki_tutarlar(metin: str) -> List[float]:
    """
    Metindeki para biçimli sayıları float listesine çevirir (etiketli/etiketsiz fark etmez).

    Etiket ARANMAZ: altın senaryoda ölçülen şey koçun tutarı doğru SÖYLEYİP söylemediğidir,
    doğru ETİKETLEDİĞİ değil (onu `check_grounding` ölçer). Yüzde/tarih gibi para olmayan
    sayılar da listeye girer — ayıklanmaz, çünkü çağıran taraf BELİRLİ bir değeri arar ve
    fazladan sayı yalnız gürültüdür; ayıklamaya kalkmak (tarih mi, yüzde mi?) ölçütü
    kırılganlaştırır.
    """
    out: List[float] = []
    for m in _TUTAR_DESENI.finditer(metin or ""):
        try:
            out.append(abs(_to_float_tr(m.group("num"))))
        except ValueError:
            continue
    return out


def tutar_gecti(metin: str, deger: float, *,
                tolerans_mutlak: float = 1.0, tolerans_oransal: float = 0.005) -> bool:
    """
    `deger` metinde geçiyor mu? Yazım biçiminden (nokta/boşluk ayıraç) bağımsızdır.

    Tolerans NEDEN var: koç `48.510,41` yerine `48.510` yazabilir — bu bir hata değil,
    yuvarlamadır ve ölçüt bunu hata sayarsa DOĞRU cevabı düşürür (BUG #316'nın dersi:
    bir zorlama ancak ölçütü kadar iyidir). Oransal tolerans dar tutulur (%0,5): altın
    senaryodaki beklenen değerler birbirinden en az %3 uzaktır, yani bu genişlikte iki
    ayrı beklenti birbirine karışamaz.
    """
    esik = max(tolerans_mutlak, tolerans_oransal * abs(deger))
    return any(abs(v - abs(deger)) <= esik for v in metindeki_tutarlar(metin))
