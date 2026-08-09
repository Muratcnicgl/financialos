"""
BUG #267 — MESAJ NİYETİ KAPISI + TÜRKÇE YAZIM BAĞIMSIZLIĞI.

ÖLÇÜM (7-8 Ağu 2026, düzeltme ÖNCESİ):

  (1) KARIŞIK MESAJ — 25 mesajlık korpusta 7/7 yanlış. Aynı gerçekleşmiş eylem,
      cümleye bir soru eklenince `propose_action` tool'u LLM'e HİÇ sunulmuyordu.
      FakeProvider ile uçtan uca koşum (aynı payload'ı öneren sadık sağlayıcı):

          "Bugün markette nakitten 320 TL harcadım"                → PendingAction 1
          "Bugün markette nakitten 320 TL harcadım, bütçem ne?"    → PendingAction 0

      İki katmanlı sessizlik: harcama kaydedilmez VE soru harcama-öncesi rakamlarla
      cevaplanır. Kök neden: tek bayrak iki bağımsız soruyu cevaplıyordu; KURAL SIFIR'ın
      ölçütü ise yalnız "gerçekleşmiş eylem bildirildi mi?"dir.

  (2) YAZIM — 20 token iki yazımdan birinde eşleşmiyordu (`odedim`, `dusunuyorum`,
      `degerlendir`, `agustosta`, `kaç` ...). Sinsiliği: `re.IGNORECASE` ı↔i eşitliğini
      kendiliğinden kurar, ç/ş/ğ/ö/ü için kurmaz — yani sorun harfe göre değişiyordu ve
      test edilen örnekte tesadüfen çalışabiliyordu.

  Sınıf taraması (L11) aynı defekti iki yerde daha buldu:
    · `action_executor._DATE_KEYWORD_RE` — "subatta/agustosta/eylulde" görülmüyordu →
      TARIH_BELIRSIZ koruması devreye girmiyor, işlem SESSİZCE bugüne yazılıyordu.
    · `coach_insights.QT_OPEN_PATTERN` — `kac` yazılmış, `kaç` unutulmuştu. Bu sayaç
      KOÇUN kendi mesajlarını ölçer ve koç düzgün Türkçe yazar → açık sorular
      sayılmıyor, MI/OARS oranı düşük görünüyor, "direktif tarz" uyarısı haksız
      tetikleniyordu.

Kapı iki yönlüdür: davranış (her iki yazım) + kaynak-türetimli drift kilidi (desen
literalleri katlanmış olmak ZORUNDA — diakritikli bir literal normalize edilmiş metinle
asla eşleşmez ve sessizce ölür).
"""
from __future__ import annotations

import re

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import action_executor, coach_insights, intent_rules
from app.action_executor import _tarih_ifadesi_var_mi, propose_action
from app.coach import (
    CoachEngine, LLMResponse, has_realized_action, is_future_or_intent,
    is_question, should_offer_propose_tool,
)
from app.coach_insights import _classify_sentence
from app.intent_rules import niyet_cikar
from app.models import Account, AccountType, Base, PendingAction, User
from app.tr_text import katlanmis_mi, normalize

TR2ASCII = str.maketrans("şğıöüçŞĞİÖÜÇ", "sgioucSGIOUC")


def _iki_yazim(metin: str):
    """Aynı cümlenin düzgün ve diakritiksiz hâli — kullanıcı ikisini de yazar."""
    return [metin, metin.translate(TR2ASCII)]


# ============================================================
# 1) KARIŞIK MESAJ — SORU, GERÇEKLEŞMİŞ EYLEMİ VETO EDEMEZ
# ============================================================

KARISIK = [
    "Bugün markette 320 TL harcadım, bütçem ne durumda?",
    "Kart borcumu ödedim, şimdi ne kadar borcum kaldı?",
    "3 lot TLY sattım, kâr mı ettim?",
    "Maaşım geldi, nasıl dağıtmalıyım?",
    "Kahveye 50 lira verdim, günlük limitim ne oldu?",
    "Efe'ye 1000 TL ödedim, alacak listem güncel mi?",
    "Krediyi kapattım, stratejim değişti mi?",
]


@pytest.mark.parametrize("msg", [y for m in KARISIK for y in _iki_yazim(m)])
def test_karisik_mesajda_propose_sunulur(msg):
    """Soru + gerçekleşmiş eylem aynı cümlede: eylem KAYBOLMAZ."""
    n = niyet_cikar(msg)
    assert n.gerceklesmis is True, msg
    assert n.propose_sunulsun is True, msg
    assert n.gerekce == "gerceklesmis eylem bildirildi"


@pytest.mark.parametrize("msg", [y for m in KARISIK for y in _iki_yazim(m)])
def test_karisik_mesaj_hala_soru_sayilir(msg):
    """Veto kalktı diye mesaj 'soru değil'e dönüşmedi — iki bayrak BAĞIMSIZ."""
    assert is_question(msg) is True, msg


# ============================================================
# 2) ESKİ DAVRANIŞ KORUNDU (baskılama yönü değişmedi)
# ============================================================

SAF_SORU = [
    "Kart borcum ne kadar?",
    "Bütçemi değerlendir",
    "Bu ayki harcamalarımı özetle",
    "Borç stratejimi karşılaştır",
    "Borçlarımı sıralar mısın",
    "Bana bir tasarruf planı yaz",
    "Hangi borcu önce kapatayım",
]
SAF_GELECEK = [
    "Yarın kredi kartı borcumu kapatacağım",
    "Gelecek hafta 4 lot TLY satacağım",
    "Önümüzdeki ay krediyi kapatmayı planlıyorum",
    "İleride yatırım yapmayı düşünüyorum",
]
SAF_BILDIRIM = [
    "Bugün 500 TL harcadım",
    "Kart borcumu ödedim",
    "Bugün 200 lira benzin aldım",
    "Kiramı gönderdim",
    "Elektrik faturasını yatırdım",
    "Maaş yattı",
]


@pytest.mark.parametrize("msg", [y for m in SAF_SORU for y in _iki_yazim(m)])
def test_saf_soru_baskilanir(msg):
    assert should_offer_propose_tool(msg) is False, msg


@pytest.mark.parametrize("msg", [y for m in SAF_GELECEK for y in _iki_yazim(m)])
def test_saf_gelecek_baskilanir(msg):
    assert is_future_or_intent(msg) is True, msg
    assert should_offer_propose_tool(msg) is False, msg


@pytest.mark.parametrize("msg", [y for m in SAF_BILDIRIM for y in _iki_yazim(m)])
def test_saf_bildirimde_propose_sunulur(msg):
    assert should_offer_propose_tool(msg) is True, msg


def test_fiilsiz_bildirim_sunulur():
    """"Market 320 TL" — fiil yok; nötr yol (KURAL SIFIR 2. katmanı prompt'tur)."""
    n = niyet_cikar("Market 320 TL")
    assert n.gerceklesmis is False and n.propose_sunulsun is True


def test_notr_selam_sunulur():
    assert should_offer_propose_tool("Merhaba") is True


def test_karisik_gecmis_ve_gelecek():
    """BUG #095 vakası korundu: 'aldım ama yarın satacağım' → gerçekleşen kısım kazanır."""
    for msg in _iki_yazim("5 lot TLY aldım ama yarın satacağım"):
        assert has_realized_action(msg) is True, msg
        assert should_offer_propose_tool(msg) is True, msg


def test_gerekce_kararla_tutarli():
    """Gerekçe trace'e düşer; kararla çelişemez (BUG #253: kullanıcı sistemini görebilmeli)."""
    for msg in KARISIK + SAF_SORU + SAF_GELECEK + SAF_BILDIRIM + ["Merhaba"]:
        n = niyet_cikar(msg)
        assert n.gerekce, msg
        if n.propose_sunulsun:
            assert "gerceklesmis" in n.gerekce or "notr" in n.gerekce, msg
        else:
            assert "yok" in n.gerekce, msg


# ============================================================
# 3) UÇTAN UCA — KARIŞIK MESAJ GERÇEKTEN KAYIT ÜRETİR
# ============================================================

class _SadikKoc:
    """propose_action SUNULDUYSA çağıran sağlayıcı — ölçülen şey koç değil KAPI."""

    NAME = "Fake"
    model = "fake-model-1"
    last_used_provider = "fake"

    def chat(self, system_prompt, messages, tools=None):
        adlar = [t.get("name") for t in (tools or [])]
        if "propose_action" in adlar:
            return LLMResponse(
                text="320 TL market harcamanı kaydediyorum.",
                tool_calls=[{
                    "id": "t1", "name": "propose_action",
                    "input": {
                        "action_type": "add_transaction",
                        "payload": {"transaction_type": "expense", "amount": 320.0,
                                    "account_id": 1, "category": "market"},
                        "summary": "320 TL market harcaması kaydedildi",
                    },
                }],
                usage={"input_tokens": 10, "output_tokens": 5},
                provider_used="fake", model_name="fake-model-1",
            )
        return LLMResponse(text="Nakit bakiyen 5.000 TL.", tool_calls=[],
                           usage={"input_tokens": 10, "output_tokens": 5},
                           provider_used="fake", model_name="fake-model-1")


@pytest.fixture
def koc_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(User(id=1, name="niyet_test"))
    db.flush()
    db.add(Account(id=1, user_id=1, name="Kasa", account_type=AccountType.cash, balance=5000))
    db.commit()
    yield db
    db.close()


@pytest.mark.parametrize("msg", [
    "Bugün markette nakitten 320 TL harcadım",
    "Bugün markette nakitten 320 TL harcadım, bütçem ne durumda?",
    "Nakitten 320 TL market alışverişi yaptım, ne kadar param kaldı?",
    "Bugun markette nakitten 320 TL harcadim, butcem ne durumda?",
])
def test_uctan_uca_bildirilen_harcama_kaydedilir(koc_db, msg):
    """Düzeltme öncesi son üç satır 0 kayıt üretiyordu (kullanıcının parası kayboluyordu)."""
    CoachEngine(provider=_SadikKoc()).chat(koc_db, 1, msg, include_cockpit=False)
    koc_db.expire_all()
    assert koc_db.query(PendingAction).count() == 1, f"kayit uretilmedi: {msg}"


def test_uctan_uca_saf_soruda_kayit_olusmaz(koc_db):
    """Ters yön: soru KURAL SIFIR gereği aksiyon üretmez (BUG #023 korundu)."""
    CoachEngine(provider=_SadikKoc()).chat(koc_db, 1, "Kart borcum ne kadar?", include_cockpit=False)
    koc_db.expire_all()
    assert koc_db.query(PendingAction).count() == 0


# ============================================================
# 4) SINIF TARAMASI — TARİH ANAHTAR KELİMESİ (yanlış güne yazma)
# ============================================================

AY_IFADELERI = [
    "ocak", "şubat", "mart", "nisan", "mayıs", "haziran", "temmuz",
    "ağustos", "eylül", "ekim", "kasım", "aralık",
    "ocakta", "şubatta", "martta", "nisanda", "mayısta", "haziranda",
    "temmuzda", "ağustosta", "eylülde", "ekimde", "kasımda", "aralıkta",
    "dün", "bugün", "geçen hafta", "geçen ay", "3 gün önce", "tarihli", "tarihinde",
]


@pytest.mark.parametrize("ifade", [y for m in AY_IFADELERI for y in _iki_yazim(m)])
def test_tarih_ifadesi_iki_yazimda_da_gorulur(ifade):
    assert _tarih_ifadesi_var_mi(f"5.000 TL {ifade} ödendi") is True, ifade


@pytest.mark.parametrize("ozet", [
    "320 TL market harcaması ağustosta kaydedildi",
    "320 TL market harcamasi agustosta kaydedildi",
])
def test_tarihli_ozet_tarihsiz_payloadla_onaya_sunulmaz(koc_db, ozet):
    """BUG #044 koruması yazımdan bağımsız: aksi hâlde işlem sessizce BUGÜNE yazılırdı."""
    with pytest.raises(ValueError, match="TARIH_BELIRSIZ"):
        propose_action(
            db=koc_db, user_id=1, action_type="add_transaction",
            payload={"transaction_type": "expense", "amount": 320.0, "account_id": 1},
            summary=ozet, user_message="nakitten 320 TL market harcadım",
        )


# ============================================================
# 5) SINIF TARAMASI — KOÇUN AÇIK-SORU SAYACI (MI/OARS metriği)
# ============================================================

ACIK_SORULAR = [
    "Kaç lira ayırabilirsin?",
    "Nasıl bir yol izlemek istersin?",
    "Hangi borcu önce kapatmak istersin?",
    "Neden bu ay zorlandın?",
]


@pytest.mark.parametrize("cumle", [y for m in ACIK_SORULAR for y in _iki_yazim(m)])
def test_acik_soru_iki_yazimda_da_acik_sayilir(cumle):
    """`kaç` sayılmayınca oran düşük görünüyor ve 'direktif tarz' uyarısı haksız çıkıyordu."""
    assert _classify_sentence(cumle) == "open_q", cumle


@pytest.mark.parametrize("cumle", [y for m in ["Bunu yapar mısın?", "Doğru mu?"] for y in _iki_yazim(m)])
def test_kapali_soru_iki_yazimda_da_kapali_sayilir(cumle):
    assert _classify_sentence(cumle) == "closed_q", cumle


@pytest.mark.parametrize("cumle", [y for m in ["Gibi görünüyor.", "Anlıyorum."] for y in _iki_yazim(m)])
def test_yansitma_iki_yazimda_da_yansitma_sayilir(cumle):
    assert _classify_sentence(cumle) == "reflection", cumle


# ============================================================
# 6) DRIFT KİLİDİ — DESEN LİTERALLERİ KAYNAKTAN TÜRETİLEREK ÖLÇÜLÜR
# ============================================================
#
# L27: kapı listeyi ELLE taşırsa ölçmüyordur. Burada desenler modül namespace'inden
# GEZİLEREK bulunur; yeni eklenen bir desen otomatik kapsama girer.

def _desenleri_topla(modul, adlar=None):
    bulunan = {}
    for ad, deger in vars(modul).items():
        if adlar is not None and ad not in adlar:
            continue
        if isinstance(deger, re.Pattern):
            bulunan[ad] = deger.pattern
        elif isinstance(deger, tuple) and deger and all(isinstance(d, re.Pattern) for d in deger):
            for i, d in enumerate(deger):
                bulunan[f"{ad}[{i}]"] = d.pattern
    return bulunan


def test_niyet_desenlerinin_tamami_katlanmis():
    """`intent_rules`'un TÜM modül-seviyesi desenleri katlanmış olmak zorunda.

    Diakritikli bir literal, normalize edilmiş metinle asla eşleşmez → kural SESSİZCE
    ölür (L28). Kapsam tabanı: modülde en az üç desen bulunmalı (kapı boşa düşmesin)."""
    desenler = _desenleri_topla(intent_rules)
    assert len(desenler) >= 3, f"kapsam tabani coktu: {list(desenler)}"
    kirik = {ad: p for ad, p in desenler.items() if not katlanmis_mi(p)}
    assert not kirik, f"katlanmamis desen (sessizce olur): {kirik}"


@pytest.mark.parametrize("modul,adlar", [
    (action_executor, {"_DATE_KEYWORD_RE", "_ACCOUNT_KEYWORD_RE"}),
    (coach_insights, {"QT_OPEN_PATTERN", "QT_CLOSED_PATTERN", "QT_REFLECTION_PATTERN"}),
])
def test_katlanmis_metinle_eslesen_desenler_katlanmis(modul, adlar):
    """Bu desenler normalize edilmiş metne uygulanır → literalleri de katlanmış olmalı."""
    desenler = _desenleri_topla(modul, adlar)
    assert set(desenler) == adlar, f"sozlesmedeki desen kayboldu/yeniden adlandirildi: {set(desenler) ^ adlar}"
    kirik = {ad: p for ad, p in desenler.items() if not katlanmis_mi(p)}
    assert not kirik, f"katlanmamis desen: {kirik}"


def test_normalize_uzunluk_korur():
    """Eşleşme ofsetleri ham metinde de geçerli olmalı (alıntı çıkaran tüketiciler için)."""
    for metin in ["Ödedim", "İstanbul", "ŞUBAT", "çğıöşü", "ÇĞİÖŞÜ", "normal ascii"]:
        assert len(normalize(metin)) == len(metin), metin


def test_abonelik_grup_anahtari_yazimdan_bagimsiz():
    """Sınıf taraması: "Türk Telekom" ile "Turk Telekom" AYNI aboneliktir.

    Ayrı gruplanırlarsa her biri ≥3 tekrar eşiğinin altında kalır ve abonelik hiç
    görünmez. (Ölçülmüş canlı örnek YOK — aynı sınıfın kapatılması.)"""
    from app.rules_engine import _normalize_merchant
    assert _normalize_merchant("Türk Telekom") == _normalize_merchant("Turk Telekom")
    assert _normalize_merchant("Spotify Türkiye — Mayıs") == _normalize_merchant("spotify turkiye")


def test_normalize_tek_kaynak():
    """`category_rules` kendi kopyasını tutmaz — aynı fonksiyon nesnesi olmalı (BUG #267)."""
    from app import category_rules, tr_text
    assert category_rules.normalize is tr_text.normalize
    assert category_rules.TR_NORM is tr_text.TR_NORM
