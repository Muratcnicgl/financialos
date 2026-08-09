"""
BUG #267 — MESAJ NİYETİ: TEK DOĞRULUK KAYNAĞI (KURAL SIFIR kapısı).

`balance_rules` bir işlemin bakiyeye etkisini, `account_rules` "hangi hesaba"yı,
`category_rules` kategoriye bağlı kararları tek yere topladı. Bu modül de koçun
**"kullanıcı ne yaptı?"** kararını tek yere toplar: `propose_action` tool'u LLM'e
sunulacak mı?

------------------------------------------------------------------------------
ÖLÇÜLEN DEFEKT (7 Ağu 2026 — 25 mesajlık korpus + FakeProvider ile uçtan uca koşum)
------------------------------------------------------------------------------
1) KARIŞIK MESAJ — GERÇEKLEŞMİŞ EYLEM SESSİZCE KAYBOLUYORDU (7/7 yanlış).

   Eski kapı `if is_question(msg): return False` diyordu; yani bir mesaj SORU ise
   içindeki gerçekleşmiş eylem YOK SAYILIYORDU. Oysa insanlar tam olarak böyle yazar:

       "Bugün markette nakitten 320 TL harcadım, bütçem ne durumda?"

   Uçtan uca ölçüm (aynı payload'ı öneren sadık bir sağlayıcıyla):
       "Bugün markette nakitten 320 TL harcadım"            → PendingAction: 1  ✅
       "Bugün markette nakitten 320 TL harcadım, ... ne durumda?" → PendingAction: 0  ❌

   Sonuç iki katmanlı ve ikisi de sessiz: (a) harcama HİÇ kaydedilmez, (b) koç
   kullanıcının sorusunu HARCAMA ÖNCESİ rakamlarla yanıtlar — yani cevap da yanlıştır
   ama doğru görünür. Kullanıcının hatasını fark etmesi için, söylediği şeyin
   kaydedilmediğini kendi başına keşfetmesi gerekir.

   Kök neden bir KAVRAM KARIŞMASI: tek bir bayrak iki BAĞIMSIZ soruyu cevaplıyordu —
   "bu mesaj bir şey soruyor mu?" ve "bu mesaj gerçekleşmiş bir olay bildiriyor mu?".
   Bir mesaj ikisi birden olabilir. KURAL SIFIR'ın ölçütü ise yalnız İKİNCİSİDİR:
   *"propose_action SADECE kullanıcı gerçekleşmiş bir eylemi bildirdiğinde çağrılır."*

2) DİAKRİTİKSİZ YAZIM — KAPI YAZIMA GÖRE DEĞİŞİYORDU (20 token).

   Telefon klavyesinde çok yaygın olan "odedim / dusunuyorum / degerlendir" yazımı
   desenlerin hiçbirinde yoktu. Ayrıntı ve neden yarım göründüğü: `app/tr_text.py`.

------------------------------------------------------------------------------
SÖZLEŞME
------------------------------------------------------------------------------
    propose_sunulsun = gerceklesmis OR (NOT soru AND NOT gelecek)

  · Gerçekleşmiş eylem varsa sorunun VETOSU YOKTUR (defekt 1).
  · Gerçekleşmiş eylem yoksa soru da niyet de baskılar (eski davranış korunur).
  · Hiçbiri yoksa (nötr "Merhaba") sunulur; KURAL SIFIR'ın ikinci katmanı prompt'tur
    (ADR-008 iki katmanlı savunma).

Bu sözleşmenin YAN FAYDASI: soru tespitini genişletmek artık GÜVENLİDİR. Eskiden
`is_question`a yeni bir kelime eklemek, o kelimeyi içeren gerçek bir bildirimi
yutabilirdi — bu yüzden liste dar tutulmuştu ("Borçlarımı sıralar mısın" soru
sayılmıyordu). Veto koşullu olduğu için genişletmenin bedeli kalmadı.

NEDEN LLM SINIFLANDIRICI DEĞİL: backlog LLM-010'un ikinci önerisi "belirsizler için
küçük LLM intent classifier"dı. Uygulanmadı — bu kapı bir GÜVENLİK kapısıdır; ağ
çağrısına ve modelin gününe bağlanırsa hem gecikme/kota maliyeti alır hem de
deterministik olmayan bir katman KURAL SIFIR'ın önüne geçer. Deterministik kapı
zemindir, LLM prompt'u ikinci katmandır. (KURAL D1: üç tetiğin üçü de HAYIR.)

GUNCELLEMELER
- 8 Agu 2026 BUG #267 fix: modul olusturuldu; govde `coach.py`den tasindi. Soru
  vetosu KOSULLU hale geldi, tum desenler katlanmis (diakritiksiz) yazildi ve
  eslesme oncesi metin `tr_text.normalize` ile katlanir. Karar gerekcesi
  (`MesajNiyeti.gerekce`) reasoning trace'e dusurulur.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.tr_text import normalize

# ============================================================
# DESENLER — HEPSİ KATLANMIŞ YAZILIR (diakritiksiz, küçük harf)
# ============================================================
#
# `tests/test_niyet_kapisi.py` bu üç demeti KAYNAKTAN gezerek her literalin katlanmış
# olduğunu doğrular (L27: kapı listeyi elle taşımaz). Diakritikli bir literal eklenirse
# test kırmızı olur — çünkü o literal normalize edilmiş metinle asla eşleşmez ve
# SESSİZCE ölürdü.

# --- Soru / analiz / talep -----------------------------------------------------
# Türkçe eklemeli bir dildir: gövdeler kasıtlı olarak SON sınırsız (önek eşleşmesi),
# böylece "degerlendirir misin / ozetler misin / planim" da yakalanır.
_SORU_DESENLERI: tuple = (
    # soru eki (ayrı yazılır) + çekimli hâlleri: mi/mu · misin/musun · miyim/muyum ...
    re.compile(r"\bm[iu](sin|siniz|sun|sunuz|yim|yiz|yum|yuz|dir|dur|ydi|ydu)?\b"),
    # soru kelimeleri
    re.compile(r"\b(ne|neden|nicin|niye|nasil|kac|hangi|kim|kime|kimin|kimden"
               r"|nerede|nereden|nereye|nere|ne zaman|ne kadar)\b"),
    # analiz / tavsiye / talep gövdeleri (önek eşleşmesi)
    re.compile(r"\b(oner|tavsiye|analiz|incele|stratej|degerlendir|ozetle|ozetli"
               r"|yorumla|karsilastir|kiyasla|goster|hesapla|listele|sirala"
               r"|acikla|anlat|plan|durum|yoksa|ne yap|tahmin et)"),
)

# --- Gerçekleşmiş eylem (KURAL SIFIR ✅ listesi) -------------------------------
# Yalnız AÇIK, birinci/üçüncü şahıs GEÇMİŞ para hareketi fiilleri. Jenerik "-di/-dı"
# eki BİLİNÇLİ olarak alınmadı: "borcum artti" bir kullanıcı eylemi değildir ve
# `has_realized_action` BUG #127'de retry'ı ZORLAYAN sinyaldir — geniş tutulursa koç
# olmayan bir eylemi uydurmaya itilir.
_GERCEKLESMIS_DESENI = re.compile(
    r"\b(yaptim|yaptik|ettim|ettik|sattim|sattik|aldim|aldik|odedim|odedik"
    r"|kapattim|kapattik|harcadim|harcadik|girdim|girdik|yatirdim|yatirdik"
    r"|cektim|cektik|verdim|verdik|gonderdim|gonderdik|tasidim|tasidik"
    r"|kaydett|tahsil ett|geldi|gecti|yatirdi|yatti|odendi)\b"
)

# --- Gelecek / niyet (gerçekleşmemiş) ------------------------------------------
_GELECEK_DESENI = re.compile(
    r"(acagim|ecegim|acagiz|ecegiz|acaksin|eceksin|acak\b|ecek\b"
    r"|planliyorum|dusunuyorum|niyetinde|planim var|dusunuyoruz"
    r"|yarin|gelecek\s+(hafta|ay|yil|sene)|onumuzdeki|ileride|ilerde)"
)


@dataclass(frozen=True)
class MesajNiyeti:
    """Bir kullanıcı mesajının kapı açısından niteliği + kararın GEREKÇESİ.

    `gerekce` reasoning trace'e düşer: kapının neden öyle karar verdiği, kullanıcı
    "neden kaydetmedin?" diye sorduğunda log okunmadan görülebilsin (BUG #253 ilkesi).
    """

    soru: bool
    gerceklesmis: bool
    gelecek: bool
    propose_sunulsun: bool
    gerekce: str


def _soru_mu(katlanmis: str) -> bool:
    if "?" in katlanmis:
        return True
    return any(d.search(katlanmis) for d in _SORU_DESENLERI)


def niyet_cikar(mesaj: str) -> MesajNiyeti:
    """Mesajın niyetini tek geçişte çıkarır (sözleşme: modül docstring'i)."""
    k = normalize(mesaj)
    soru = _soru_mu(k)
    gerceklesmis = bool(_GERCEKLESMIS_DESENI.search(k))
    gelecek = bool(_GELECEK_DESENI.search(k))

    if gerceklesmis:
        # BUG #267: sorunun vetosu YOK — "harcadım, bütçem ne durumda?" iki şeydir.
        sunulsun, gerekce = True, "gerceklesmis eylem bildirildi"
    elif soru:
        sunulsun, gerekce = False, "soru/analiz istegi, gerceklesmis eylem yok"
    elif gelecek:
        sunulsun, gerekce = False, "gelecek/niyet ifadesi, gerceklesmis eylem yok"
    else:
        sunulsun, gerekce = True, "notr mesaj (KURAL SIFIR ikinci katman: prompt)"

    return MesajNiyeti(
        soru=soru, gerceklesmis=gerceklesmis, gelecek=gelecek,
        propose_sunulsun=sunulsun, gerekce=gerekce,
    )


# ============================================================
# GERİYE UYUMLU YÜZEY (coach.py bu adlarla dışa açar)
# ============================================================

def soru_mu(mesaj: str) -> bool:
    """BUG #023: soru ise provider'a `propose_action` gönderilmez — TEK BAŞINA değil,
    `niyet_cikar` sözleşmesi içinde (gerçekleşmiş eylem vetoyu kaldırır)."""
    return niyet_cikar(mesaj).soru


def gerceklesmis_eylem_var_mi(mesaj: str) -> bool:
    return niyet_cikar(mesaj).gerceklesmis


def gelecek_niyet_mi(mesaj: str) -> bool:
    return niyet_cikar(mesaj).gelecek


def propose_sunulsun_mu(mesaj: str) -> bool:
    return niyet_cikar(mesaj).propose_sunulsun
