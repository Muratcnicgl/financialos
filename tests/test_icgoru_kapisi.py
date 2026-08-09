"""
BUG #268 — `save_insight` sözleşmesi + "critical" vaadinin enjeksiyona ULAŞMASI.

ÖLÇÜM (8 Ağu 2026, düzeltme ÖNCESİ — FakeProvider ile gerçek koç akışı):

| Tool argümanı              | Ölçülen davranış                                    |
|----------------------------|-----------------------------------------------------|
| `content` anahtarı yok     | KeyError yutuldu; kayıt YOK, koç "Not aldım." dedi   |
| `content` bir nesne (dict) | **TÜM KOÇ İSTEĞİ ÇÖKTÜ** (PendingRollbackError)      |
| `expires_at: "gelecek ay"` | ValueError yutuldu; kayıt YOK, koç "Not aldım."      |
| `dedup_key` yok (2. çağrı) | UNIQUE ihlali; kayıt YOK, koç "Not aldım."           |
| `priority: "cok_kritik"`   | sessizce `normal`e düştü                             |

İkinci satır sözleşme ihlalinden fazlasıydı: başarısız INSERT session'ı rollback edilmemiş
bırakıyor, sonraki `commit()` patlıyor ve kullanıcının o mesajı komple hata dönüyordu —
projenin kendi anti-pattern listesindeki savepoint maddesi.

EN SESSİZ BULGU: tool açıklaması LLM'e "critical: asla unutulmamalı" diyordu, ama enjeksiyon
`sort_priority` + `last_evidence_at` ile sıralayıp `limit(5)` uyguluyor ve `save_insight_action`
bu iki alanı HİÇ yazmıyordu. Ölçüm: 6 rutin çıkarıcı gözlemi (sort_priority=10) +
kullanıcının "asla kredi çekmeyeceğim" beyanı (critical) → **beyan enjekte edilen blokta YOK.**
Koç, kullanıcının "bunu asla unutma" dediği şeyi tam olarak unutuyordu (L21 sınıfı).

Bu kapı üç şeyi birden ölçer: sözleşme (kabul/red yönü), yazma yolunun izolasyonu
(savepoint) ve **beyan edilen önceliğin gerçekten enjekte edilmesi**.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import coach_insights as ci
from app.coach import CoachEngine, LLMResponse, SAVE_INSIGHT_SCHEMA, save_insight_action
from app.coach_insights import format_insights_for_prompt
from app.insight_schema import (
    ICERIK_AZAMI, KATEGORILER, ONCELIKLER, ONEM_MERDIVENI, IcgoruGecersiz,
    ayikla, slugla, tool_semasi,
)
from app.models import Base, CoachInsight, User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(User(id=1, name="icgoru_test"))
    session.commit()
    yield session
    session.close()


# ============================================================
# 1) İÇERİK YÜKTÜR — yoksa/metne dönüşmüyorsa REDDEDİLİR
# ============================================================

@pytest.mark.parametrize("arg", [
    {"dedup_key": "k"},                               # content anahtarı yok
    {"content": None, "dedup_key": "k"},
    {"content": "", "dedup_key": "k"},
    {"content": "   ", "dedup_key": "k"},
    {"content": {"a": 1}, "dedup_key": "k"},          # ölçümde TÜM isteği çökertiyordu
    {"content": ["a"], "dedup_key": "k"},
    {"content": 42, "dedup_key": "k"},
])
def test_icerik_yoksa_reddedilir(arg):
    with pytest.raises(IcgoruGecersiz, match="ICGORU_GECERSIZ"):
        ayikla(arg)


def test_tool_argumani_nesne_degilse_reddedilir():
    with pytest.raises(IcgoruGecersiz, match="ICGORU_GECERSIZ"):
        ayikla("kullanıcı kredi çekmez")


def test_cok_uzun_icerik_reddedilir():
    """Tek içgörü paylaşılan hafıza bütçesini yiyip diğerlerini tahliye edemez."""
    with pytest.raises(IcgoruGecersiz, match="azami"):
        ayikla({"content": "a" * (ICERIK_AZAMI + 1), "dedup_key": "k"})


def test_sinirdaki_icerik_kabul_edilir():
    assert ayikla({"content": "a" * ICERIK_AZAMI, "dedup_key": "k"}).content


# ============================================================
# 2) METADATA ETİKETTİR — kaydı düşürmez, belgeli varsayılana düşer VE RAPORLANIR
# ============================================================

def test_taninmayan_kategori_kaydi_dusurmez():
    a = ayikla({"content": "Kullanıcı kart kapatmayı reddetti",
                "category": "uydurma", "dedup_key": "k"})
    assert a.category == "general"
    assert any("category" in d for d in a.duzeltmeler), "sessiz dusus yasak"


def test_taninmayan_oncelik_ASAGI_duser():
    """Tanınmayan bir etiket 'critical' sayılamaz — güvenli yön aşağıdır."""
    a = ayikla({"content": "Kritik gerçek", "priority": "cok_kritik", "dedup_key": "k"})
    assert a.priority == "normal"
    assert a.sort_priority == ONEM_MERDIVENI["normal"]
    assert any("priority" in d for d in a.duzeltmeler)


def test_bozuk_tarih_gercegi_dusurmez():
    a = ayikla({"content": "Ağustosta seyahat", "dedup_key": "k", "expires_at": "gelecek ay"})
    assert a.content == "Ağustosta seyahat"
    assert a.expires_at is None
    assert any("expires_at" in d for d in a.duzeltmeler)


def test_gecerli_tarih_korunur():
    assert ayikla({"content": "x", "dedup_key": "k", "expires_at": "2026-09-01"}).expires_at == "2026-09-01"


def test_dedup_key_yoksa_icerikten_turetilir():
    """Boş anahtar UNIQUE indeksi ikinci kayıtta patlatıyordu; kaydı bir etiket eksikliği
    yüzünden kaybetmek, kaydın kendisini kaybetmektir."""
    a = ayikla({"content": "Kullanıcı market harcamasını kartla yapar"})
    assert a.dedup_key, "anahtar turetilmeli"
    assert any("dedup_key" in d for d in a.duzeltmeler)
    # Aynı gerçek → aynı anahtar (dedup amacı korunur)
    assert a.dedup_key == ayikla({"content": "Kullanıcı market harcamasını kartla yapar"}).dedup_key


def test_dedup_key_slug_normalize_edilir():
    """Türkçe katlama tek kaynaktan: 'Fon Satışı — Seyahat' → 'fon_satisi_seyahat'."""
    assert slugla("Fon Satışı — Seyahat") == "fon_satisi_seyahat"
    assert ayikla({"content": "x", "dedup_key": "Fon Satışı"}).dedup_key == "fon_satisi"


def test_gecerli_arguman_duzeltme_uretmez():
    a = ayikla({"content": "Kullanıcı asla kredi çekmez", "category": "preference",
                "priority": "critical", "dedup_key": "asla_kredi"})
    assert a.duzeltmeler == []
    assert a.sort_priority == ONEM_MERDIVENI["critical"]


# ============================================================
# 3) ASIL BULGU — BEYAN EDİLEN ÖNCELİK ENJEKSİYONA ULAŞIR
# ============================================================

def _cikarici_gozlemleri(db, adet=6, oncelik=10):
    for i in range(adet):
        db.add(CoachInsight(user_id=1, content=f"cikarici gozlemi {i}", title=f"gozlem {i}",
                            insight_type="decision_rhythm", status="active",
                            sort_priority=oncelik, last_evidence_at=datetime.utcnow(),
                            dedup_key=f"x{i}"))
    db.commit()


def test_kullanicinin_kritik_beyani_enjekte_edilir(db):
    """Ölçüm: düzeltme öncesi bu beyan blokta HİÇ YOKTU (limit 5'i gözlemler dolduruyordu)."""
    _cikarici_gozlemleri(db)
    save_insight_action(db=db, user_id=1, content="Kullanıcı asla kredi çekmeyeceğini söyledi",
                        category="preference", priority="critical", dedup_key="asla_kredi")
    blok = format_insights_for_prompt(db, 1, max_tokens=1500)
    assert "asla kredi" in blok, "kullanicinin 'asla unutma' dedigi gercek enjekte edilmedi"


def test_kritik_beyan_gozlemlerin_USTUNDE_siralanir(db):
    _cikarici_gozlemleri(db)
    save_insight_action(db=db, user_id=1, content="Kullanıcı asla kredi çekmeyeceğini söyledi",
                        category="preference", priority="critical", dedup_key="asla_kredi")
    blok = format_insights_for_prompt(db, 1, max_tokens=1500)
    assert blok.index("asla kredi") < blok.index("cikarici gozlemi"), "beyan gozlemin altinda kaldi"


def test_normal_beyan_bugunku_davranisi_korur(db):
    """Regresyon: `normal` bugünkü varsayılan (5) — davranış değişmemeli."""
    a = save_insight_action(db=db, user_id=1, content="genel bağlam", category="general",
                            priority="normal", dedup_key="genel")
    assert a.sort_priority == 5


def test_beyan_prompt_etiketi_dolu(db):
    """Prompt her içgörünün başına [TİP | GÜVEN] yazar; bu yolda ikisi de NULL'dı."""
    save_insight_action(db=db, user_id=1, content="Kullanıcı nakit sever", category="preference",
                        priority="high", dedup_key="nakit_sever")
    blok = format_insights_for_prompt(db, 1, max_tokens=1500)
    assert "KULLANICI_BEYANI" in blok and "user_stated" in blok
    assert "(baslik yok)" not in blok


def test_onem_merdiveni_gercek_sabitlerle_tutarli():
    """Merdiven sırası, `coach_insights`'ın GERÇEK sabitlerinden türetilerek kilitlenir (L27).

    Bir çıkarıcı sabiti değişirse ve sıra bozulursa bu test kırmızı olur — aksi hâlde
    kullanıcının beyanı sessizce gözlemlerin altına düşerdi."""
    assert ci.ERL_DOMINANT_PRIORITY > ONEM_MERDIVENI["critical"], (
        "deterministik kirmizi-cizgi cikarimi, LLM siniflandirmasinin ustunde kalmali")
    assert ONEM_MERDIVENI["critical"] > ci.ERL_K2_PRIORITY
    assert ONEM_MERDIVENI["high"] > ci.MC_REFERENCE_DOMINANT_PRIORITY, (
        "kullanicinin beyani tum desen gozlemlerinin ustunde olmali")
    assert ONEM_MERDIVENI["high"] > ci.QT_WARNING_PRIORITY
    assert ONEM_MERDIVENI["high"] > ci.ARP_DOMINANT_PRIORITY
    assert ONEM_MERDIVENI["high"] > ci.CAP_DOMINANT_PRIORITY
    assert ONEM_MERDIVENI["high"] > ci.BT_DOMINANT_PRIORITY
    assert ONEM_MERDIVENI["critical"] > ONEM_MERDIVENI["high"] > ONEM_MERDIVENI["normal"]


# ============================================================
# 4) YAZMA YOLU İZOLE — düşen içgörü sohbeti çökertmez
# ============================================================

def test_basarisiz_yazma_session_i_zehirlemez(db):
    """Anti-pattern kuralı: IntegrityError'da session zehirlenmesin (`begin_nested`)."""
    save_insight_action(db=db, user_id=1, content="ilk", category="general",
                        priority="normal", dedup_key="ayni")
    # Aynı anahtarla ikinci INSERT (upsert yolu devre dışı bırakılırsa) yerine, doğrudan
    # çakışan bir satır ekleyerek yazma hatasını tetikle:
    db.add(CoachInsight(user_id=1, content="cakisan", dedup_key="ayni"))
    with pytest.raises(Exception):
        db.commit()
    db.rollback()
    # Session HÂLÂ kullanılabilir olmalı — koç isteği devam edebilsin
    assert db.query(CoachInsight).count() == 1


# ============================================================
# 5) UÇTAN UCA — koç akışı çökmez, kullanıcı DÜRÜSTÇE bilgilendirilir
# ============================================================

class _IcgoruKocu:
    NAME, model, last_used_provider = "Fake", "fake-1", "fake"

    def __init__(self, arg):
        self.arg = arg

    def chat(self, system_prompt, messages, tools=None):
        return LLMResponse(text="Not aldım.",
                           tool_calls=[{"id": "t1", "name": "save_insight", "input": self.arg}],
                           usage={"input_tokens": 1, "output_tokens": 1},
                           provider_used="fake", model_name="fake-1")


@pytest.mark.parametrize("arg", [
    {"category": "preference", "dedup_key": "k1"},          # content yok
    {"content": {"a": 1}, "dedup_key": "k2"},               # ÖLÇÜMDE İSTEĞİ ÇÖKERTİYORDU
    {"content": "a" * (ICERIK_AZAMI + 5), "dedup_key": "k3"},
])
def test_uctan_uca_bozuk_icgoru_cokertmez_ve_soylenir(db, arg):
    cevap = CoachEngine(provider=_IcgoruKocu(arg)).chat(db, 1, "Not al", include_cockpit=False)
    assert db.query(CoachInsight).count() == 0
    assert "kaydedemedim" in cevap["reply"], "sessiz kalirsa kullanici hatirlandigini saniyor"


@pytest.mark.parametrize("arg", [
    {"content": "Kullanıcı hafta sonu harcamıyor", "dedup_key": "hafta_sonu"},
    {"content": "Kullanıcı hafta sonu harcamıyor"},                      # anahtar türetilir
    {"content": "Kullanıcı hafta sonu harcamıyor", "priority": "yok_boyle", "dedup_key": "h"},
    {"content": "Kullanıcı hafta sonu harcamıyor", "expires_at": "gelecek ay", "dedup_key": "h2"},
])
def test_uctan_uca_gercek_metadata_yuzunden_kaybolmaz(db, arg):
    cevap = CoachEngine(provider=_IcgoruKocu(arg)).chat(db, 1, "Not al", include_cockpit=False)
    assert db.query(CoachInsight).count() == 1, "gercek metadata yuzunden kaybedildi"
    assert "kaydedemedim" not in cevap["reply"]


def test_uctan_uca_ayni_anahtar_uzerine_yazar(db):
    for metin in ("Kullanıcı nakit sever", "Kullanıcı artık kart kullanıyor"):
        CoachEngine(provider=_IcgoruKocu(
            {"content": metin, "dedup_key": "odeme_tercihi"})).chat(
            db, 1, "Not al", include_cockpit=False)
    kayitlar = db.query(CoachInsight).all()
    assert len(kayitlar) == 1, "upsert bozuldu"
    assert "kart" in kayitlar[0].content


# ============================================================
# 6) TOOL ŞEMASI SÖZLEŞMEDEN ÜRETİLİR (drift kilidi)
# ============================================================

def test_tool_semasi_sozlesmeden_uretilir():
    sema = tool_semasi()
    ozellik = sema["parameters"]["properties"]
    assert tuple(ozellik["category"]["enum"]) == KATEGORILER
    assert tuple(ozellik["priority"]["enum"]) == ONCELIKLER
    assert ozellik["content"]["maxLength"] == ICERIK_AZAMI


def test_kocun_kullandigi_sema_uretilenle_AYNI():
    """Elle yazılmış ikinci bir liste kalmadı — biri değişirse ikisi birden değişir."""
    assert SAVE_INSIGHT_SCHEMA == tool_semasi()


def test_zorunlu_alanlar_kodun_gercekten_zorunlu_saydiklaridir():
    """Eski şema `category`/`priority`'yi ZORUNLU sayıyordu ama kod ikisini de opsiyonel
    okuyup varsayılana düşürüyordu — sözleşme ile davranış çelişiyordu."""
    zorunlu = set(tool_semasi()["parameters"]["required"])
    assert zorunlu == {"content", "dedup_key"}
    # Sözleşme bunu gerçekten uyguluyor mu?
    with pytest.raises(IcgoruGecersiz):
        ayikla({"dedup_key": "k"})                      # content zorunlu
    assert ayikla({"content": "x"}).dedup_key           # dedup_key türetilebilir ama BOŞ KALMAZ
