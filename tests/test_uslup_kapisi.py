"""
BUG #277 — KOÇUN YAZILI ÜSLUP SÖZLEŞMESİNİ HİÇBİR ŞEY ÖLÇMÜYORDU.

ÖLÇÜM (10 Ağu 2026, kanonik senaryo seti + ScriptedProvider):
  Yapısal olarak KUSURSUZ (aksiyon senaryosunda doğru tool'u çağıran, uydurma sayı
  kullanmayan) ama V3 prompt'unun üslup maddelerini AÇIKÇA ihlal eden 9 persona kuruldu.
  Dokuzu da **%100 pass_rate / 8-8 senaryo** aldı — ihlalsiz referansla birebir aynı.
  Harness koçun DOĞRU İŞ yapıp yapmadığını ölçüyor, DÜZGÜN KONUŞUP konuşmadığını hiç
  ölçmüyordu (L48).

İKİNCİ ÖLÇÜM — sözleşmenin kod tarafı olan tek maddesi (SAHTE NİYET):
  `coach._FAKE_NIYET_RE` gerçekçi 12 cümlenin **8'ini** kaçırıyordu; kaçanların tamamı
  "sen" hitaplı biçimlerdi ("onayını bekliyorum") — oysa AYNI prompt "siz" hitabını
  yasaklar. Bir kuralın koruması, ikinci bir kuralın ihlal edilmesine bağlıydı (L49).
  Uçtan uca (4 mesaj tipi × 2 hitap): sahte niyet cümlesi kullanıcıya 8 hücrenin
  7'sinde ULAŞIYORDU — koruma yalnız retry dalındaydı ve `offer_propose` ile korunuyordu.

KAPI:
  (1) Her üslup maddesi kendi ölçülmüş korpusunu yakalar ve meşru karşı-örneği cezalandırmaz.
  (2) Desen kaynakları KATLANMIŞ yazılır (L32) — diakritikli desen sessizce ölür.
  (3) Ürünün KENDİ ürettiği metinler kendi sözleşmesine uyar.
  (4) Prompt'un yasak-cümle listesi tek kaynaktan üretilir (elle yazılı ikinci liste yok).
  (5) Sahte niyet güvencesi DURUMA bağlıdır: kayıt yoksa iddia düşer, varsa korunur.
  (6) Eval kanonik seti üslup boyutunu ÖLÇER (ihlal eden persona referanstan ayrışır).
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, User, Account, AccountType, PendingAction, ActionStatus
from app.coach import (CoachEngine, LLMResponse, V3_GOD_MODE_PROMPT, _postprocess_report,
                       _ONAY_YOK_NOTU)
from app.coach_eval import DEFAULT_SCENARIOS, run_eval, score_result
from app.tr_text import katlanmis_mi
from app.uslup_kurallari import (KURALLAR, SAHTE_NIYET_IHLAL_ORNEKLERI,
                                 SAHTE_NIYET_MESRU_ORNEKLERI, _SAHTE_NIYET_DESENLERI,
                                 ihlaller, prompt_sahte_niyet_listesi,
                                 sahte_niyet_iddiasi_var)


# ============================================================
# (1) Her maddenin ölçülmüş korpusu — yakalama VE yanlış-pozitif
# ============================================================

@pytest.mark.parametrize("kural", KURALLAR, ids=lambda k: k.kod)
def test_kural_kendi_ihlal_korpusunu_yakalar(kural):
    for ornek in kural.ihlal_ornekleri:
        assert kural.kod in ihlaller(ornek), (
            f"{kural.kod} kendi ölçülmüş ihlal örneğini kaçırdı: {ornek!r}"
        )


@pytest.mark.parametrize("kural", KURALLAR, ids=lambda k: k.kod)
def test_kural_mesru_cumleyi_cezalandirmaz(kural):
    """Yanlış-pozitif, kaçırmak kadar zararlıdır: sağlıklı koç haksız yere düşer (BUG #275)."""
    for ornek in kural.mesru_ornekler:
        assert kural.kod not in ihlaller(ornek), (
            f"{kural.kod} meşru cümleyi ihlal saydı: {ornek!r}"
        )


@pytest.mark.parametrize("kural", KURALLAR, ids=lambda k: k.kod)
def test_kural_ornekleri_bos_degil(kural):
    """Drift kilidi: korpussuz bir madde, ölçülmemiş bir maddedir."""
    assert kural.ihlal_ornekleri and kural.mesru_ornekler, f"{kural.kod} korpussuz"


def test_sahte_niyet_korpusu_tam():
    kacan = [c for c in SAHTE_NIYET_IHLAL_ORNEKLERI if not sahte_niyet_iddiasi_var(c)]
    assert not kacan, f"sahte niyet korpusundan kaçan: {kacan} (ölçülen eski kaçak: 8/12)"
    yanlis = [c for c in SAHTE_NIYET_MESRU_ORNEKLERI if sahte_niyet_iddiasi_var(c)]
    assert not yanlis, f"meşru cümle sahte-niyet sayıldı: {yanlis}"


def test_sen_hitapli_bicimler_de_taniniyor():
    """Ölçülen defektin kalbi: koruma, HİTAP kuralına uyan biçimi görmüyordu."""
    for c in ("Aksiyonu hazırladım, onayını bekliyorum.",
              "Onaylarsan hemen kaydediyorum.",
              "Onayını verirsen kaydedeceğim."):
        assert sahte_niyet_iddiasi_var(c), c


# ============================================================
# (2) Desen hijyeni — katlanmış yazım (L32)
# ============================================================

def test_tum_desenler_katlanmis_yazilmis():
    """Diakritikli desen normalize edilmiş metinle ASLA eşleşmez → sessizce ölür."""
    kaynaklar = [d for k in KURALLAR for d in k.desenler] + list(_SAHTE_NIYET_DESENLERI)
    bozuk = [d for d in kaynaklar if not katlanmis_mi(d)]
    assert not bozuk, f"katlanmamış desen(ler): {bozuk}"


# ============================================================
# (3) Ürünün kendi metinleri kendi sözleşmesine uyar
# ============================================================

_URUN_METINLERI = [
    "Hangi hesaptan harcadın? Yazına 'kartla' veya 'nakitten' eklersen hemen kaydederim.",
    "Aksiyon hazırlanamadı. Mesajını biraz farklı şekilde tekrar gönder, örneğin: '240 TL yemek kart'.",
    "_(Not: bu mesajda hiçbir kayıt oluşturmadım.)_",
    _ONAY_YOK_NOTU,
    ("Koç (yapay zekâ yorumlayıcı) şu an ulaşılamıyor — sağlayıcı kotası dolmuş olabilir. "
     "Ama panelindeki tüm veriler güncel ve doğru: kokpit, günlük limit, bütçe zarfları, "
     "borç planı ve alacakların motor tarafından hesaplanıyor ve koça ihtiyaç duymadan "
     "çalışıyor. Birkaç dakika sonra tekrar yazabilirsin."),
]


@pytest.mark.parametrize("metin", _URUN_METINLERI)
def test_urunun_kendi_metni_sozlesmeye_uyar(metin):
    """'Aksiyon hazırlanAMAdı' ölçümde yakalanmıştı — kapı ürünün dürüst cümlesini vurmamalı."""
    assert not ihlaller(metin), f"ürün metni kendi kuralını ihlal ediyor: {ihlaller(metin)}"
    assert not sahte_niyet_iddiasi_var(metin)


# ============================================================
# (4) Prompt ↔ dedektör tek kaynak (L27)
# ============================================================

def test_prompt_yasak_listesi_tek_kaynaktan_uretilir():
    liste = prompt_sahte_niyet_listesi()
    assert liste.strip(), "yasak cümle listesi boş üretildi"
    for ornek in SAHTE_NIYET_IHLAL_ORNEKLERI:
        assert ornek in liste
    # Prompt'ta yer tutucu KALMAMALI ve üretilmiş liste prompt'a girmiş olmalı
    assert "{SAHTE_NIYET_ORNEKLERI}" not in V3_GOD_MODE_PROMPT
    assert SAHTE_NIYET_IHLAL_ORNEKLERI[0] in V3_GOD_MODE_PROMPT


def test_promptun_yasakladigi_her_cumleyi_dedektor_taniyor():
    """Prompt bir biçimi yasaklayıp kod başkasını arıyorsa, yasak kâğıt üstünde kalır."""
    for ornek in SAHTE_NIYET_IHLAL_ORNEKLERI:
        assert sahte_niyet_iddiasi_var(ornek), ornek


def test_prompt_ornegi_hitap_kuralini_ihlal_etmiyor():
    """Prompt'un 'DOĞRU' örnekleri modele davranış öğretir — kendi kuralını çiğneyemez."""
    ornek_satiri = "için aksiyon hazırladım. Onayını bekliyorum."
    assert ornek_satiri in V3_GOD_MODE_PROMPT
    assert "Onayınızı bekliyorum" not in V3_GOD_MODE_PROMPT


# ============================================================
# (5) Ürün güvencesi — DURUMA bağlı (L39)
# ============================================================

def test_kayit_yokken_sahte_niyet_iddiasi_kullaniciya_gitmez():
    metin = "## Durum\nKart borcun yüksek.\nAksiyonu hazırladım, onayını bekliyorum."
    sonuc = _postprocess_report(metin, None, "Kart borcum ne kadar?", [], False)
    assert not sahte_niyet_iddiasi_var(sonuc), f"sahte niyet kullanıcıya ulaştı: {sonuc!r}"
    assert "Kart borcun yüksek." in sonuc, "iddia dışı içerik de silinmiş"
    assert _ONAY_YOK_NOTU in sonuc


def test_tek_satirlik_yanitta_cumle_bazinda_calisir():
    metin = "Kart borcun 11.976 TL. Aksiyonu hazırladım, onayını bekliyorum."
    sonuc = _postprocess_report(metin, None, "Kart borcum ne?", [], False)
    assert "11.976" in sonuc and not sahte_niyet_iddiasi_var(sonuc)


def test_cevabin_tamami_iddiadan_ibaretse_bos_ekran_kalmaz():
    sonuc = _postprocess_report("Onayını bekliyorum.", None, "Merhaba", [], False)
    assert len(sonuc.strip()) > 20 and not sahte_niyet_iddiasi_var(sonuc)


def test_bekleyen_kayit_VARSA_iddia_korunur():
    """Doğru cümleyi silmek de hasardır: onay ekranında gerçek kayıt varken atıf meşrudur."""
    metin = "Dünkü 500 TL'lik harcaman hâlâ onayını bekliyor."
    sonuc = _postprocess_report(metin, None, "Bekleyen bir şey var mı?", [], True)
    assert sonuc.strip() == metin, f"gerçek kayda yapılan doğru atıf silindi: {sonuc!r}"
    assert _ONAY_YOK_NOTU not in sonuc


def test_aksiyon_olustuysa_iddia_korunur():
    metin = "240 TL market harcamasını hazırladım. Onayını bekliyorum."
    sonuc = _postprocess_report(metin, None, "240 TL market aldım kartla", [{"id": 1}], True)
    assert "Onayını bekliyorum." in sonuc


def test_cift_not_yazilmaz():
    """İki not aynı gerçeği söyler; prompt'un 'aynı şeyi iki kez söyleme' maddesi bize de geçerli."""
    metin = "Kart borcun 11.976 TL. Onayını bekliyorum."
    sonuc = _postprocess_report(metin, None, "500 TL yemek harcadım nakitten", [], False)
    assert sonuc.count("(Not:") == 1, sonuc
    assert _ONAY_YOK_NOTU in sonuc


# ============================================================
# (6) Eval kanonik seti üslup boyutunu ÖLÇER
# ============================================================

class _Persona:
    """Yapısal olarak doğru (gerçekleşmiş eylemde tool çağırır), üslubu bozuk koç."""

    NAME = "Scripted"; model = "scripted-1"; last_used_provider = "scripted"
    _TOOL = [{
        "name": "propose_action",
        "input": {"action_type": "add_transaction",
                  "payload": {"amount": 500, "transaction_type": "expense",
                              "account_id": 1, "category": "yemek"},
                  "summary": "500 TL yemek"},
    }]

    def __init__(self, metin):
        self.metin = metin

    def chat(self, system_prompt, messages, tools):
        son = next((str(m.get("content") or "") for m in reversed(messages)
                    if m.get("role") == "user"), "")
        harcama = ("harcadım" in son) or ("aldım" in son)
        return LLMResponse(text=self.metin, tool_calls=list(self._TOOL) if harcama else [],
                           usage={"input_tokens": 1, "output_tokens": 1},
                           provider_used="scripted", model_name="scripted-1")


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    s.add(User(id=1, name="murat"))
    s.add(Account(id=1, user_id=1, name="Enpara", account_type=AccountType.cash, balance=4276.0))
    s.add(Account(id=2, user_id=1, name="Ziraat", account_type=AccountType.credit_card,
                  balance=11976.0, credit_limit=12000.0, statement_day=2, payment_day=12))
    s.commit()
    yield s
    s.close()


_SAGLIKLI = ("## Durum\nKart borcun nakdinin üzerinde; önce kartı düşürmek mantıklı. "
             "Alternatif olarak nakdi tamponda tutup asgariyi ödersin ama faiz işler — önermem.")

_IHLALLI = {
    "dalkavukluk": "Harika bir soru! ## Durum\nBunu sorman çok güzel, tablo fena değil.",
    "dolgu": "## Durum\nTablo dengede. Umarım yardımcı olmuşumdur, her zaman buradayım.",
    "siz_hitabi": "## Durum\nBorcunuzu bu ay kapatabilirsiniz, harcamalarınızı azaltın.",
    "ic_jargon": "## Durum\nBu hesaplama 'Güvenli Borç Ödemesi' menüsündeki senaryolara dayanıyor.",
    "bos_teselli": "## Durum\nMerak etme, hallederiz! Her şey yoluna girecek, endişelenme.",
    "nutuk": "## Durum\nBenimle profesyonel bir dil kullanmanı tercih ederim. Şimdi tabloya bakalım.",
}


def test_ihlalsiz_koc_tam_puan_alir_kapsam_tabani(db):
    """Kapsam tabanı: kapı her şeyi kırmızıya boyamıyor."""
    rapor = run_eval(CoachEngine(provider=_Persona(_SAGLIKLI)), db, 1, DEFAULT_SCENARIOS)
    assert rapor["pass_rate"] == 100.0, rapor


@pytest.mark.parametrize("ad,metin", sorted(_IHLALLI.items()))
def test_uslup_ihlali_eden_persona_referanstan_ayrisir(db, ad, metin):
    """Ölçülen defekt: dokuz ihlalli persona da referansla BİREBİR aynı %100'ü alıyordu."""
    rapor = run_eval(CoachEngine(provider=_Persona(metin)), db, 1, DEFAULT_SCENARIOS)
    assert rapor["pass_rate"] < 100.0, (
        f"{ad} personası tam puan aldı — üslup boyutu yine ölçülmüyor"
    )
    dusen = [r for r in rapor["scenarios"] if not r["scores"].get("uslup", True)]
    assert dusen, f"{ad}: hiçbir senaryoda uslup kriteri düşmedi"
    assert all(r["uslup_ihlalleri"] for r in dusen), "hangi maddenin düştüğü raporlanmıyor"


def test_her_kanonik_senaryo_uslup_olcer():
    """Drift kilidi: üslup kriteri taşımayan senaryo, o senaryoda sözleşmeyi ölçmez."""
    eksik = [sc.name for sc in DEFAULT_SCENARIOS if "uslup" not in sc.checks]
    assert not eksik, f"üslup ölçmeyen kanonik senaryo(lar): {eksik}"


def test_duvar_metin_basit_soruda_yakalanir():
    uzun = "Finansal dengeni korumak sabır ister. " * 40
    assert score_result({"reply": uzun}, ["oz"])["oz"] is False
    assert score_result({"reply": "Kart borcun 11.976 TL."}, ["oz"])["oz"] is True


def test_eval_kriteri_urunle_AYNI_kaynaktan_okur(db):
    """L46: kapının ölçütü, koruduğu sözleşmeden sapamaz — ikisi de tek kaynağı çağırır."""
    import app.coach_eval as ce
    import app.uslup_kurallari as uk
    assert ce.sahte_niyet_iddiasi_var is uk.sahte_niyet_iddiasi_var
    assert ce.ihlaller is uk.ihlaller


def test_bekleyen_onay_durumu_sozlesmenin_parcasi(db):
    """Yapısal bayrak (ADR-051): metin değil DURUM karar verir; eval de aynı bayrağı okur."""
    res = CoachEngine(provider=_Persona(_SAGLIKLI)).chat(
        db, 1, "Kart borcum ne kadar?", include_cockpit=False)
    assert res["bekleyen_onay_var"] is False

    db.add(PendingAction(user_id=1, action_type="add_transaction", payload="{}",
                         summary="test", status=ActionStatus.pending))
    db.commit()
    res2 = CoachEngine(provider=_Persona("Dünkü kaydın onayını bekliyor.")).chat(
        db, 1, "Bekleyen bir şey var mı?", include_cockpit=False)
    assert res2["bekleyen_onay_var"] is True
    assert "onayını bekliyor" in res2["reply"], "gerçek kayda atıf silindi"
    assert score_result(res2, ["no_fake_niyet"])["no_fake_niyet"] is True
