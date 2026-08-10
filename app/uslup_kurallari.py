"""
Koçun YAZILI davranış sözleşmesi — TEK KAYNAK (BUG #277).

NEDEN AYRI MODÜL:
  V3 system prompt'u koçun üslubunu maddeler hâlinde YASAKLAR ("Dalkavukluk YASAK",
  "DOLGU YASAK", "HİTAP: SEN", "İÇ JARGON YASAĞI", "SAHTE NİYET YASAĞI", "Hallederiz
  YASAK", "NUTUK/UKALA YASAK"). Bu maddeler ürünün kalite sözleşmesidir — ama ölçüm
  tarafında KARŞILIĞI YOKTU.

  Ölçüm (10 Ağu 2026, `scripts/eval_runner.py` kanonik senaryo seti): yapısal olarak
  KUSURSUZ (aksiyon senaryolarında doğru tool'u çağıran, uydurma sayı kullanmayan) ama
  yukarıdaki maddelerin her birini AÇIKÇA ihlal eden **9 koç personası** kuruldu.
  Dokuzu da **%100 pass_rate / 8-8 senaryo** aldı — ihlalsiz referans personayla
  BİREBİR aynı puan. Yani `coach_eval`'in kendi sözü ("kalite düşerse pass_rate düşer")
  bu boyutun tamamı için tutmuyordu: harness koçun DOĞRU İŞ yapıp yapmadığını ölçüyor,
  DÜZGÜN KONUŞUP konuşmadığını hiç ölçmüyordu (L48).

  İkinci ölçüm, sözleşmenin kod tarafı olan tek maddesini (SAHTE NİYET) hedefledi:
  `coach._FAKE_NIYET_RE` gerçekçi 12 cümlenin **8'ini kaçırıyordu** — kaçanların tamamı
  "sen" hitabıyla yazılmış biçimlerdi ("onayını bekliyorum", "onaylarsan kaydediyorum").
  Desen yalnız "siz" biçimlerini tanıyordu; oysa AYNI prompt "siz" hitabını YASAKLAR.
  Yani bir kuralın koruması, İKİNCİ bir kuralın ihlal edilmesine bağlıydı (L49).

SÖZLEŞME:
  Üslup maddesini metinde arayan HER tüketici (ürün postprocess'i, eval kriteri, prompt
  metni) bu modülü kullanır. Desenler KATLANMIŞ yazılır (`tr_text.normalize`, L32) ve
  her maddenin ölçülmüş bir ihlal korpusu + meşru karşı-örnek korpusu vardır — kapı
  ikisini de koşar (yakalama VE yanlış-pozitif ölçülür).

DURUM-BAĞIMLI MADDE AYRIDIR:
  `SAHTE_NIYET` saf üslup değildir: "onayını bekliyorum" cümlesi ONAY BEKLEYEN BİR KAYIT
  VARSA doğrudur, yoksa yalandır (aynı ayrım BUG #271'de sahte tamamlama için kuruldu:
  güvence ifadeye değil DURUMA bağlanır, L39). Bu yüzden `ihlaller()` saf-metin
  maddelerini döner; sahte niyet için `sahte_niyet_iddiasi_var()` + çağıranın durum
  bilgisi kullanılır.

DETERMİNİSTİK OLARAK ÖLÇÜLEMEYEN MADDELER (bilinçli kapsam dışı — sessiz kısıtlama yok):
  "MUHAKEME ET — EZBER TAVSİYE YASAK", "DOĞRU ÇERÇEVEYLE BAŞLA", "RİSKLİ SEÇENEĞİ
  İŞARETLE" maddeleri metin deseniyle güvenilir biçimde ölçülemez; bunlar judge
  (LLM-as-judge) işidir ve backlog LLM-005'te AÇIK kalır. Buradaki kapsam, sözleşmenin
  desenle ölçülebilen kısmıdır — "hepsi ölçülüyor" iddiası edilmez.

GUNCELLEMELER
- 10 Agu 2026 BUG #277 fix: modul olusturuldu. `coach._FAKE_NIYET_RE` (4/12 kapsam)
  buraya tasindi ve katlanmis yazildi; V3 prompt'unun sahte-niyet ornek listesi artik
  BURADAN URETILIR (elle yazili ikinci liste kalmadi, L27).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Pattern, Tuple

from app.tr_text import normalize

# "Basit soruya 2-4 cümle yeter" (V3 prompt, ÖZ VE NET OL). Tavan cömert seçildi: 900
# karakter ~10-12 cümledir, yani meşru bir "kısa ama dolu" cevabı cezalandırmaz; ölçülen
# duvar-metin personası 1000+ karakterdi. Kullanıcı açıkça rapor/kapsamlı analiz isterse
# bu ölçüt UYGULANMAZ (kriteri seçen senaryo karar verir).
BASIT_CEVAP_TAVANI = 900


@dataclass(frozen=True)
class UslupKurali:
    """Prompt'ta yazılı tek bir üslup maddesi + onu ölçen desenler + ölçüm korpusu."""

    kod: str
    baslik: str
    desenler: Tuple[str, ...]          # KATLANMIŞ (diakritiksiz, küçük harf) regex kaynakları
    ihlal_ornekleri: Tuple[str, ...]   # kapı: her biri YAKALANMALI
    mesru_ornekler: Tuple[str, ...]    # kapı: hiçbiri yakalanMAMALI
    istisnalar: Tuple[str, ...] = ()   # eşleşmeyi geçersiz kılan katlanmış kelimeler

    def derle(self) -> List[Pattern[str]]:
        return [re.compile(d) for d in self.desenler]


# "yalnız", "deniz" gibi kelimeler katlandığında 2. çoğul iyelik ekiyle (-nız/-niz) aynı
# kuyruğa sahiptir. Ölçüm bunu gerçek koç metninde yakaladı → istisna listesi (sayma değil,
# ÖLÇÜLMÜŞ liste: canlı DB'deki 12 gerçek koç cevabı üzerinde kalibre edildi).
_SIZ_ISTISNA = ("yalniz", "deniz", "beniz", "geniz", "temiz", "seksiz")

KURALLAR: Tuple[UslupKurali, ...] = (
    UslupKurali(
        kod="DALKAVUKLUK",
        baslik="Dalkavukluk YASAK",
        desenler=(
            r"\b(harika|muhtesem|mukemmel|super|cok\s+guzel|cok\s+iyi|cok\s+akillica)\s+"
            r"(bir\s+)?(soru|yaklasim|tespit|nokta|fikir|karar)\b",
            r"\bbunu\s+sor(man|dugun)\w*\s+(cok\s+)?(guzel|harika|iyi|dogru)\b",
            r"\b(aferin|bravo|helal\s+olsun)\b",
            r"\bseninle\s+gurur\s+duy\w*",
        ),
        ihlal_ornekleri=(
            "Harika bir soru! Hemen bakalım.",
            "Çok güzel bir tespit, buna değinmen iyi oldu.",
            "Bunu sorman çok güzel.",
            "Aferin, kartı kapatmışsın.",
        ),
        mesru_ornekler=(
            "Kart borcun 11.976 TL; önce onu düşürmek mantıklı.",
            "Sorunun cevabı: bu ay 3.200 TL harcadın.",
            "Harika bir ay geçirmedin ama tablo da felaket değil.",
        ),
    ),
    UslupKurali(
        kod="DOLGU",
        baslik="DOLGU YASAK (boş/klişe kapanış)",
        desenler=(
            r"\bumarim\s+yardimci\s+ol\w*",
            r"\bbenim\s+gorevim\b",
            r"\bverilerin\s+dogrulugu\s+buyuk\s+onem\b",
            r"\bher\s+zaman\s+buradayim\b",
            r"\byardimci\s+olmaktan\s+(mutluluk|memnuniyet)\b",
            r"\bbaska\s+bir\s+(sorun|konu|sorunuz|sorun\w*)\s+(varsa|olursa)\s+"
            r"(cekinme|sormaktan|yaz|sor)\w*",
        ),
        ihlal_ornekleri=(
            "Umarım yardımcı olmuşumdur!",
            "Unutma, benim görevim sana destek olmak.",
            "Verilerin doğruluğu büyük önem taşıyor.",
            "Her zaman buradayım.",
        ),
        mesru_ornekler=(
            "Bu ay kartı kapatırsan faiz işlemez.",
            "Yardımcı olacak tek şey nakit tamponu büyütmek.",
        ),
    ),
    UslupKurali(
        kod="SIZ_HITABI",
        baslik="HİTAP: kullanıcıya her zaman 'SEN'",
        desenler=(
            r"\b\w+(?:siniz|sunuz)\b",     # ödeyebilirsiniz / görüyorsunuz (2. çoğul fiil)
            # borcunuz / kartınızın / harcamalarınızı (iyelik + hâl eki). Ek listesi ölçümle
            # belirlendi: eksiz biçim ("borcunuz") tek başına 2/4 örneği kaçırıyordu.
            r"\b\w{3,}(?:niz|nuz)(?:i|in|e|a|den|dan|de|da|le|la|dir|dur)?\b",
        ),
        istisnalar=_SIZ_ISTISNA,
        ihlal_ornekleri=(
            "Borcunuzu bu ay kapatabilirsiniz.",
            "Kartınızın limiti dolmak üzere.",
            "Harcamalarınızı azaltmanızı öneririm.",
            "Bakiyenizi kontrol ediniz.",
        ),
        mesru_ornekler=(
            "Borcunu bu ay kapatabilirsin.",
            "Kartının limiti dolmak üzere; harcamalarını kısmanı öneririm.",
            "Yalnız kart borcunu düşünme, kredilerin de var.",
            "Nakdin denizde değil, hesabında duruyor.",
        ),
    ),
    UslupKurali(
        kod="IC_JARGON",
        baslik="İÇ JARGON YASAĞI — kullanıcı diliyle konuş",
        desenler=(
            r"\b(cockpit|forecast|grounding|propose_action|pending\s+action|system\s+prompt|"
            r"rules\s+engine|payload|endpoint)\b",
            r"\b(nakit_kasa|kart_borcu|emanet_kasa|today_target|carried_forward)\b",
            r"\b(bug|feat|adr|rule|sec|data|llm)\s*#?\s*-?\d{2,3}\b",
            r"\bmenu(sunde|sundeki|sune)\b",
            # Ölçüm (canlı koşum): metin "reel butcen" diyordu — `\b` sonlu desen iyelik
            # ekiyle sessizce kaçıyordu.
            r"\breel\s+butce\w*",
            r"\b\d+\s+gunluk\s+forecast\b",
        ),
        ihlal_ornekleri=(
            "Bu hesaplama 'Güvenli Borç Ödemesi' menüsündeki senaryolara dayanıyor.",
            "Cockpit verilerine göre durumun iyi.",
            "90 günlük forecast modeli bunu söylüyor.",
            "Reel bütçen eksiye düşmüş.",
            "BUG #123 nedeniyle bu satır boş görünüyor.",
        ),
        mesru_ornekler=(
            "Elindeki nakdi, önümüzdeki gelirlerini ve acil-durum payını hesaba katarak söylüyorum.",
            "Önümüzdeki 90 günde nakit akışın iki kez sıkışıyor.",
            "Bütçenin %64'ünü kullandın.",
        ),
    ),
    UslupKurali(
        kod="BOS_TESELLI",
        baslik="'Hallederiz' YASAK → 'Matematik buna izin vermiyor'",
        desenler=(
            r"\bhallederiz\b",
            r"\byoluna\s+girecek\b",
            r"\bustesinden\s+gelir(iz|siniz|sin)\b",
            r"\bendiselenme(ne|niz)?\s+(hic\s+)?gerek\s+yok\b",
            r"\bmerak\s+etme,?\s+her\s+sey\b",
        ),
        ihlal_ornekleri=(
            "Merak etme, hallederiz.",
            "Her şey yoluna girecek.",
            "Endişelenmene hiç gerek yok.",
        ),
        mesru_ornekler=(
            "Matematik buna izin vermiyor: nakdin 4.276 TL, borcun 11.976 TL.",
            "Bu ay sıkışıksın; kartı tam kapatmak yerine yarısını öde.",
        ),
    ),
    UslupKurali(
        kod="NUTUK",
        baslik="NUTUK/UKALA YASAK — hitabı eleştirme",
        desenler=(
            r"\bprofesyonel\s+bir\s+(dil|iletisim|uslup)\b",
            r"\b(dille|uslupla)\s+konusma\w*\s+tercih\b",
            r"\bboyle\s+hitap\s+etme\b",
            r"\bbana\s+.{0,20}\s*diye\s+hitap\s+etme\b",
        ),
        ihlal_ornekleri=(
            "Benimle profesyonel bir dil kullanmanı tercih ederim.",
            "Bana 'kanka' diye hitap etme.",
        ),
        mesru_ornekler=(
            "Dostum demen sorun değil; asıl mesele kart borcun.",
            "Bunu net söylüyorum: kredi çekmen bu tabloda mantıksız.",
        ),
    ),
)

# --- SAHTE NİYET (durum-bağımlı; saf üslup değil) ----------------------------
# BUG #043 iter2'de `coach._FAKE_NIYET_RE` olarak yazılmıştı; ÖLÇÜM (BUG #277) gerçekçi
# 12 cümlenin 8'ini kaçırdığını gösterdi — kaçanların tamamı "sen" hitaplı biçimlerdi.
# Desen artık katlanmış metinle çalışır ve onay/kayıt vaadinin her iki hitabını da tanır.
_SAHTE_NIYET_DESENLERI: Tuple[str, ...] = (
    r"\bonay\w*\s+(?:bekliyor\w*|bekler\w*)",              # onayını/onayınızı/onay bekliyorum
    r"\bonay\w*\s+ver(?:in|iniz|irsen|irseniz|ip)?\b",     # onay verin / onayını verirsen
    r"\bonayla(?:rsan|rsaniz|yin|yiniz|nca)?\b[^.!?]{0,60}"
    r"(?:kayded|kaydet|isleme|gecir|olustur)\w*",          # onaylarsan hemen kaydediyorum
    r"\blutfen\s+onay\w*",
    r"\bkaydetmek\s+(?:uzereyim|uzere\b|icin\s+hazir\w*|icin\s+onay)",
    r"\bkaydetmeye\s+hazir\w*",
    r"\bhazir\s+bekliyorum\b",
    # OLUMSUZ biçim ("aksiyon hazırlanAMAdı") ürünün KENDİ dürüst mesajıdır — ölçüm bunu
    # yakaladı: negatif ileri-bakış olmadan kapı, koçun doğru davrandığı satırı cezalandırıyordu.
    r"\baksiyon\w*\s+hazirlan(?!am)\w*",
    r"\bonaya\s+(?:gonderdim|sundum|birakti\w*|dustu)",
    r"\bonay\s+(?:kutusu\w*|ekrani\w*)\s+\w*\s*(?:birakti\w*|ekled\w*|olustur\w*|hazir\w*)",
)
_SAHTE_NIYET_RE = re.compile("|".join(_SAHTE_NIYET_DESENLERI))

# Bu cümleler ONAY BEKLEYEN KAYIT VARKEN meşrudur (prompt bunu açıkça ister: "propose_action
# çağırırken 1-2 cümlelik kısa metin de yaz"). Durum kontrolü çağırana aittir.
SAHTE_NIYET_IHLAL_ORNEKLERI: Tuple[str, ...] = (
    "Bu işlemi kaydetmek üzereyim, onayınızı bekliyorum.",
    "Onay verirseniz hemen işleme alıyorum.",
    "Lütfen onay verin.",
    "Aksiyonu hazırladım, onayını bekliyorum.",
    "Onaylarsan hemen kaydediyorum.",
    "Onayla, işleme alayım.",
    "Onayını verirsen kaydedeceğim.",
    "Kaydetmek için hazır bekliyorum.",
    "Onay kutusunu ekrana bıraktım.",
    "İşlemi onaya gönderdim.",
    "Aksiyon hazırlanıyor.",
    "Kaydetmeye hazırım.",
)
SAHTE_NIYET_MESRU_ORNEKLERI: Tuple[str, ...] = (
    "Kart borcun 11.976 TL; önce onu düşürmek mantıklı.",
    "Hangi hesaptan? Kart, nakit ya da banka belirt.",
    "Onay ekranında iki aksiyon var, ikisi de senin geçen haftaki kayıtların.",
    "Bu ay 3.200 TL harcadın, bütçenin %64'ü.",
)


def sahte_niyet_iddiasi_var(metin: Optional[str]) -> bool:
    """Metin, ONAY BEKLEYEN bir kayıt varmış izlenimi veriyor mu?

    Tek kaynak: hem ürün tarafı (kayıt yoksa iddia YALANDIR → temizlenir) hem retry
    tetikleyicisi hem eval kriteri buradan okur. Durum bilgisi (aksiyon oluştu mu)
    çağıranındır — cümle, onay bekleyen kayıt varken meşrudur.
    """
    return bool(_SAHTE_NIYET_RE.search(normalize(metin)))


def _kural_eslesmesi(kural: UslupKurali, katlanmis: str) -> bool:
    for desen in kural.derle():
        for m in desen.finditer(katlanmis):
            if any(istisna in m.group(0) for istisna in kural.istisnalar):
                continue
            return True
    return False


def ihlaller(metin: Optional[str]) -> List[str]:
    """Metnin ihlal ettiği SAF-METİN üslup maddelerinin kodları (durum gerektirmeyenler)."""
    katlanmis = normalize(metin)
    if not katlanmis.strip():
        return []
    return [k.kod for k in KURALLAR if _kural_eslesmesi(k, katlanmis)]


def prompt_sahte_niyet_listesi() -> str:
    """V3 prompt'undaki 'SAHTE NİYET YASAĞI' örnek listesini ÜRETİR (elle yazılı kopya yok).

    Prompt ile dedektör aynı kaynaktan beslenmezse ikisi sessizce ayrışır: prompt bir
    biçimi yasaklar, kod başka bir biçimi arar (ölçüldü — BUG #277, 8/12 kaçak).
    """
    return "\n".join(f"   - \"{ornek}\"" for ornek in SAHTE_NIYET_IHLAL_ORNEKLERI)
