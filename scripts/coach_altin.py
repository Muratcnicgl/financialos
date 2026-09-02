"""
ALTIN SENARYO SETİ — koçun MUHAKEMESİNİN ölçüsü (Wave-K, K-B ölçütü).

NEDEN VAR (K0'ın en büyük kör noktası):
`DEFAULT_SCENARIOS` koçun DAVRANIŞ SÖZLEŞMESİNİ ölçer — "soruya aksiyon önerme", "sahte
tamamlama yazma", "dolgu cümle kurma". Bunlar gereklidir ama koçun İŞİNİ ölçmez. O senaryolar
"Merhaba, nasılsın?" ve "Bugün 500 TL yemek harcadım" gibi cümlelerden oluşur; oradan çıkan
%80'lik oran, koçun bir insanın mali sıkışmasını çözüp çözemediği hakkında HİÇBİR ŞEY
söylemez. Yani ana ölçümümüz yanlış şeyi ölçüyordu ve bunu bilmiyorduk.

Bu modül, 1 Eylül 2026'da bir insanın Murat'ın gerçek verisiyle elle yaptığı analizi ÇITA
olarak sabitler (`docs/kalite-seruveni/masterprompt-koc.md` §4.2, G1-G6). Koç bu çıtaya
yaklaşana kadar "koç iyi" cümlesi kurulamaz.

VARSAYIM YASAK — HER SAYININ KAYNAĞI VAR:
Aşağıdaki manzara uydurulmadı; 1 Eylül canlı oturumunda bankaların kendi ekranlarından
okundu ve `docs/kalite-seruveni/masterprompt-koc.md` §4.2 ile `uygulanan-fixler.md`e
yazıldı. Kaynaklar satır satır `_ALTIN_MANZARA` içinde işaretlidir.

ÖLÇÜTÜN BİLİNEN SINIRLARI (yazılı olmayan sınır, sessiz yalandır):
  1. `grounded` bu sette KULLANILMAZ. İki ayrı nedenle geçersizdir:
     (a) ~~"Erken Kapama" tutarı `notes` içinde METİNDİ~~ → **BUG #318 ile KAPANDI**:
         alan sayısallaştı (`Account.early_payoff_amount`), cockpit'e `erken_kapama` olarak
         giriyor ve artık grounding tarafından doğrulanabiliyor. Bu sınır ortadan kalktı.
     (b) Altın senaryolar TOPLAM/FARK istiyor; türev sayı zaten cockpit'te yoktur.
     Bu bir ölçüt kusuru değil, kapsam dışılıktır — ama ikisi de birer ÜRÜN bulgusudur ve
     deftere yazılmıştır (erken kapama sayısal alan olmalı).
  2. `dogru_sonuc` bir TABANDIR: doğru sayıları ve kavram kelimelerini içeren, gerekçesi
     zayıf bir cevap geçebilir. Muhakemenin NİTELİĞİ desenle ölçülmez; onu `--judge` ölçer
     ve o bir CI kapısı değildir.
  3. G6'nın deterministik imzası setin en zayıfıdır (bkz. senaryo notu).

BAKIM NOTU (2 Eyl 2026): erken kapama tutarı BUG #318 ile sayısal alana taşındı ve bu
fixture güncellendi — tutarlar artık `early_payoff_amount`ta, `notes` yalnız hesap numarası
taşıyor. G1'in tuzağı DEVAM EDİYOR ama artık ADİL: `balance` hâlâ kalan taksit toplamıdır,
kapama bedeli ayrı bir alandır ve koç ikisini AYIRT ETMEK zorundadır. Fark şu: eskiden doğru
cevap için serbest metin ayrıştırmak gerekiyordu, şimdi veri veriliyor. Kredi `balance`i bir
gün anaparaya çevrilirse tuzak tamamen kalkar ve bu fixture yine güncellenmelidir.
"""
# kota-exempt: degerlendirme kosum araci (scripts/eval_runner.py --altin) — urun yuzeyi
#              degil, kullanici tetikleyemez.
#
# NEDEN `app/` DEĞİL, `scripts/`: bu modül Murat'ın GERÇEK mali verisini taşır (isim, banka,
# tutar). `app/` ürün yüzeyidir ve üç ayrı kapı orayı bilerek korur — kişiye özel iz
# (BUG #166), workspace'siz INSERT (BUG #221), gerekçesiz para birimi sabiti. İlk yazımda
# modülü `app/`e koydum ve yedi kapı birden düştü; kapılar HAKLIYDI. Aynı gerekçeyle
# `scripts/eval_runner._canonical_db()` de burada duruyor. Ölçüm aracı ürüne karışmaz.
from __future__ import annotations

from datetime import date
from typing import List

from app.coach_eval import EvalScenario
from app.models import Account, AccountType, Base, User

# ---------------------------------------------------------------------------
# 1 EYLÜL 2026 MANZARASI — kaynak: canlı banka ekranları (oturum kaydı)
# ---------------------------------------------------------------------------
#: Eylül nakit kaynağı 15.663,59 = hesaplardaki 11.663,59 + 08 Eyl KYK 4.000,00.
#: KYK hesap değil GELİR olduğu için fixture'a değil, G3'ün mesajına konur (varsayım yasak:
#: yinelenen gelir kaydını uydurmak yerine kullanıcının söylediği bilgi kullanılır).
KYK_ODEMESI = 4000.00
EYLUL_KAYNAK = 15663.59          # kaynak: §4.2 G3
EYLUL_ZORUNLU_CIKIS = 15078.25   # 4.109,90 + 8.221,13 + 2.747,22 — kaynak: §4.2 G3

#: Kredilerin İKİ AYRI sayısı — G1'in bütün mesele budur.
KREDI1_KALAN_TAKSIT_TOPLAMI = 16439.65   # 4 × 4.109,90 (banka: "Kalan Kredi Borcu")
KREDI1_ERKEN_KAPAMA = 14023.29           # banka: "Erken Kapama Tutarı" (anapara)
KREDI2_KALAN_TAKSIT_TOPLAMI = 63186.20   # 23 × 2.747,22
KREDI2_ERKEN_KAPAMA = 34487.12           # canlı okuma 1 Eyl (financialos'ta 32.604,08 bayattı)
KREDI_TOPLAM_TAKSIT_TOPLAMI = 79625.85   # 16.439,65 + 63.186,20 — G1'İN TUZAĞI
KART_GUNCEL_BORC = 8221.13               # son ekstreden kalan 0,00 iken dönem içi borç


def altin_db():
    """
    1 Eylül 2026 manzarasının İZOLE kopyası (in-memory; gerçek DB'ye DOKUNMAZ).

    `scripts/eval_runner._canonical_db()`ten bilinçli olarak AYRIDIR: oradaki manzara
    KASTEN minimaldir (bkz. oradaki not — zengin bağlam free-tier TPM'ini aşırıp sağlayıcı
    gürültüsü yaratıyor ve DAVRANIŞ ölçümünü bozuyor). Altın set ise zorunlu olarak zengindir;
    ölçtüğü şey tam da karmaşık manzarada muhakemedir. İkisini tek fixture'da birleştirmek,
    iki farklı soruyu tek ölçüme sıkıştırmak olurdu.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="Murat"))
    # --- nakit ---
    s.add(Account(user_id=1, name="Ziraat Vadesiz", account_type=AccountType.cash,
                  balance=1757.01))
    s.add(Account(user_id=1, name="Enpara Vadesiz", account_type=AccountType.cash,
                  balance=906.58))
    s.add(Account(user_id=1, name="Garanti Vadesiz", account_type=AccountType.cash,
                  balance=0.00))
    # --- yatırım (karar bekleyen para) ---
    s.add(Account(user_id=1, name="Midas", account_type=AccountType.investment,
                  balance=9000.00, notes="Nakit, henüz yatırıma dönüşmedi."))
    # --- kredi kartı: son ekstre 0 ama dönem içi borç var (G2) ---
    s.add(Account(user_id=1, name="Ziraat Bankkart Genc", account_type=AccountType.credit_card,
                  balance=KART_GUNCEL_BORC, credit_limit=12000.0,
                  statement_day=2, payment_day=14,
                  # BUG #318'in AYNI SINIFI, KARTTA: `notes` karar verdiren bir SAYI
                  # tasiyordu ("Son ekstreden kalan 0,00 TL") ve `balance` ile CELISIYORDU.
                  # Olculdu — koc G3'te "14 Eylul kart: belirsiz (0 mi 8.221 mi?)" deyip
                  # takvimi ikiye boldu. Serbest metin bir veri modeli degildir: tek
                  # dogruluk kaynagi `balance`tir. Senaryonun "son ekstre 0" baglami
                  # zaten G2'nin SORUSUNDA duruyor.
                  notes="Kesim ayin 2'si, son odeme 14'u."))
    # --- krediler: balance = KALAN TAKSİT TOPLAMI, anapara notes içinde (G1'in tuzağı) ---
    s.add(Account(user_id=1, name="Garanti Kredi 1", account_type=AccountType.loan,
                  balance=KREDI1_KALAN_TAKSIT_TOPLAMI, monthly_payment=4109.90,
                  remaining_installments=4, next_payment_date=date(2026, 9, 11),
                  interest_rate=4.75, early_payoff_amount=KREDI1_ERKEN_KAPAMA,
                  notes="Hesap No: KREDI-HESAP-1."))
    s.add(Account(user_id=1, name="Garanti Kredi 2", account_type=AccountType.loan,
                  balance=KREDI2_KALAN_TAKSIT_TOPLAMI, monthly_payment=2747.22,
                  remaining_installments=23, next_payment_date=date(2026, 9, 15),
                  interest_rate=4.55, early_payoff_amount=KREDI2_ERKEN_KAPAMA,
                  notes="Hesap No: KREDI-HESAP-2."))
    s.commit()
    return s


# ---------------------------------------------------------------------------
# G1-G6 — §4.2'nin ÖLÇÜLEBİLİR hâli
# ---------------------------------------------------------------------------
ALTIN_SENARYOLAR: List[EvalScenario] = [
    # G1 — Kredi bakiyesi "kalan taksit toplamı" mı "anapara" mı?
    # Karıştırılırsa borç motoru ASLA-BİTMEZ üretir: kullanıcı 79.625,85 TL borcu olduğuna
    # inanır, oysa bugün 48.510,41 TL ile çıkabilir. Ölçülen: koç `notes`taki erken kapama
    # tutarlarını kullandı mı, yoksa `balance`i kapama bedeli mi sandı.
    # TOPLAM İSTENMEZ, bileşenler istenir: aksi hâlde "yanlış tabanı seçmek" ile "toplamayı
    # yanlış yapmak" tek kritere sıkışır ve hangisi olduğu ölçümden okunamaz.
    EvalScenario(
        "G1_kredi_anapara_vs_taksit_toplami",
        "Garanti'deki iki kredimi bugün tek seferde kapatsam her biri için ne öderim?",
        ["cevapladi", "dogru_sonuc", "tuzak_yok", "uslup", "no_fake_niyet"],
        include_cockpit=True,
        beklenen_tutarlar=[KREDI1_ERKEN_KAPAMA, KREDI2_ERKEN_KAPAMA],
        # KELİME ŞARTI KALDIRILDI — ve bu bir gevşetme DEĞİL, ölçüt hatasının onarımı.
        # İki koşumda koç doğru tutarları verdi ama "erken kapama" NOUN'unu kullanmadı
        # ("bugün ... ödersin" dedi) ve kriter doğru cevabı düşürdü. Üçüncü kez aynı sınıf.
        # MEŞRULUK SINAMASI: ölçütü gevşetmek, korumaya çalıştığı defekti kaçırıyor mu?
        # Hayır — ölçülen bozuk cevap ("79.625,85 TL ödemen gerekiyor") iki kapama tutarını
        # da içermiyordu, kelimesiz ölçütten de DÜŞERDİ. Sayısal imza tek başına ayırt edici:
        # 14.023,29 ve 34.487,12 ancak DOĞRU taban seçilirse söylenebilir. Kelime şartı,
        # ayırt etmeyen ama doğru cevabı düşüren bir fazlalıktı.
        beklenen_desenler=[],
        tuzak_tutarlar=[KREDI_TOPLAM_TAKSIT_TOPLAMI,
                        KREDI1_KALAN_TAKSIT_TOPLAMI, KREDI2_KALAN_TAKSIT_TOPLAMI],
    ),
    # G2 — "Son ekstreden kalan 0" ile "güncel borç 8.221,13" aynı şey değildir.
    # Gerçekte financialos kartı 0 gösteriyordu; kullanıcı ayın en büyük tek çıkışını
    # görmüyordu. Ölçülen: koç dönem içi borcu bir YÜKÜMLÜLÜK sayıyor mu.
    EvalScenario(
        "G2_kart_guncel_borc_yukumluluktur",
        "Kredi kartimin son ekstresinde kalan borc 0 gorunuyor. Bu ay karta odeme yapacak "
        "miyim, ne kadar?",
        ["cevapladi", "dogru_sonuc", "uslup", "no_fake_niyet"],
        include_cockpit=True,
        beklenen_tutarlar=[KART_GUNCEL_BORC],
        beklenen_desenler=[r"14\s*Eyl|güncel\s*borç|guncel\s*borc|dönem\s*içi|donem\s*ici"],
    ),
    # G3 — Ay içi nakit TAKVİMİ. Aylık toplamlar yeterli değildir: para 8 Eylül'de gelir,
    # çıkışlar 11/14/15 Eylül'dedir. Ölçülen: kaynak ve zorunlu çıkış toplamı + tarih ekseni.
    EvalScenario(
        "G3_ay_ici_nakit_takvimi",
        "8 Eylul'de 4.000 TL KYK odemem gelecek. Eylul boyunca elimdeki parayla zorunlu "
        "odemelerimi karsilayabilir miyim?",
        ["cevapladi", "dogru_sonuc", "uslup", "no_fake_niyet"],
        include_cockpit=True,
        beklenen_tutarlar=[EYLUL_KAYNAK, EYLUL_ZORUNLU_CIKIS],
        beklenen_desenler=[r"11\s*Ey|14\s*Ey|15\s*Ey"],
    ),
    # G4 — Yatırım getirisi ile borç kapatma AYNI BİRİMDE kıyaslanmalı (stopaj sonrası aylık %).
    # Ölçülen: koç mevduat getirisini stopajdan arındırıyor ve kredinin AYLIK faiziyle
    # karşılaştırıyor mu. Yüzdeler `beklenen_tutarlar`a KONULMAZ: küçük sayılarda mutlak
    # tolerans (1,0) %4,55 ile %4,75'i aynı sayar — ölçüt orada körleşirdi.
    EvalScenario(
        "G4_getiri_ile_borc_ayni_birimde",
        "Elimdeki 9.000 TL'yi Enpara birikime koysam yillik %35,5 brut faiz veriyor. Bunun "
        "yerine krediye erken odeme yapsam ne olur, hangisi daha mantikli?",
        ["cevapladi", "dogru_sonuc", "uslup", "no_fake_niyet"],
        include_cockpit=True,
        beklenen_desenler=[r"stopaj|17[.,]5", r"4[.,]55|4[.,]75"],
    ),
    # G5 — Soruyu reddetmek yerine ÇERÇEVEYİ düzeltmek. "Bu parayla ne kazanırım?" sorusunun
    # doğru cevabı bir getiri hesabı değil: o para zaten 14 Eylül'deki kart ödemesine ait.
    EvalScenario(
        "G5_cerceveyi_duzeltmek",
        "Midas'taki 9.000 TL'yi bir haftaligina fona yatirsam ne kazanirim?",
        ["cevapladi", "dogru_sonuc", "uslup", "no_fake_niyet"],
        include_cockpit=True,
        beklenen_tutarlar=[KART_GUNCEL_BORC],
        beklenen_desenler=[r"14\s*Ey"],
    ),
    # G6 — Asıl kaldıraç: aylık 8.221 TL kart harcaması. Yatırım tartışması bu ölçeğin
    # yanında küçüktür ve koç bunu SUÇLAMADAN söylemelidir.
    # ÖLÇÜT ZAYIFLIĞI (yazılı): "kaldıracı gördü mü" sorusunun deterministik imzası yoktur;
    # burada yalnız kart tutarının ve kart kelimesinin geçmesi ölçülür. Suçlayıcı olmama
    # boyutunu `uslup` kısmen tutar (dalkavukluk/nutuk), asıl ölçüsü judge'dır. Bu senaryo
    # setin EN ZAYIF ölçülenidir; %100 alması "G6 çözüldü" demek DEĞİLDİR.
    EvalScenario(
        "G6_asil_kaldirac",
        "Bu ay nasil gidiyorum, neye odaklanmaliyim?",
        ["cevapladi", "dogru_sonuc", "uslup", "no_fake_niyet"],
        include_cockpit=True,
        beklenen_tutarlar=[KART_GUNCEL_BORC],
        beklenen_desenler=[r"kart"],
    ),
]
