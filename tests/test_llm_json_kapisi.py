"""
BUG #270 — "LLM cevabından JSON çıkar" sorusunun İKİ ayrı cevabı vardı, zayıf olanı
kullanıcının bir özelliğini kaybettiriyordu (LLM-009).

ÖLÇÜM (8 Ağu 2026 — premortem yolunda, 9 gerçekçi sarmalama biçimi): **5'i düşüyordu**

| Sarmalama | Önce |
|---|---|
| saf JSON · ```json fence · fence (dil etiketsiz) · kapanışı eksik fence | ✅ |
| `Elbette, işte analiz:` + JSON | ❌ |
| `İşte istediğiniz JSON:` + fence | ❌ |
| fence + `Umarım yardımcı olur.` | ❌ |
| `**Premortem**` + fence + kapanış cümlesi | ❌ |
| JSON + `Not: tutarlar tahminidir.` | ❌ |

Beşinin ortak yanı: JSON'un KENDİSİ kusursuz, kusur ZARFTA. `premortem._parse_and_validate`
fence'i yalnız **metnin tamamı** fence ise soyuyordu. Her düşüş premortem'in iki deneme
hakkından birini yakar; zayıf model aynı alışkanlığı tekrarlarsa (olağan) kullanıcı
premortem'i **hiç göremez**.

Sınıf taraması (L11): aynı sorunun kod tabanında ZATEN daha dayanıklı bir cevabı vardı —
`coach_insights._erl_k2_parse_llm_json` (fence regex + ilk `{` / son `}` yedeği). Yani iki
yol aynı soruya iki farklı cevap veriyordu; tek kaynağa indi (`app/llm_json.py`) ve yedeğin
sessiz zayıflığı da kapandı: "ilk `{` … son `}`" metin İÇİNDEKİ süslü parantezi ayırt
etmiyordu.

Sözleşme: **zarfa toleranslı, içeriğe katı** — zarfı affetmek kullanıcıya özellik kazandırır,
içeriği affetmek ona yanlış veri gösterir (ADR-050 ayrımının bu yoldaki karşılığı).
"""
from __future__ import annotations

import json

import pytest

from app.llm_json import JsonZarfiCozulemedi, cikar
from app.premortem import PremortemValidationError, _parse_and_validate


def _senaryo(no: int, olasilik: str) -> dict:
    return {
        "id": f"S{no}",
        "title": f"Senaryo basligi {no}",
        "probability_label": olasilik,
        "impact_tl": -1000.0 * no,
        "narrative": ("Aksiyon basarisiz oldu. Sebebi su idi: nakit tamponu erken tukendi "
                      "ve odemeler zincirleme gecikti."),
        "mitigation": "Odemeyi ikiye bol ve tamponu bir maas seviyesinde tut.",
    }


GOVDE = json.dumps({"scenarios": [_senaryo(1, "orta"), _senaryo(2, "dusuk"),
                                  _senaryo(3, "yuksek")]}, ensure_ascii=False)

# Zayıf sağlayıcıların (flash-lite / gpt-oss sınıfı) gerçekte ürettiği sarmalamalar
SARMALAMALAR = [
    ("saf JSON", GOVDE),
    ("fence + dil etiketi", f"```json\n{GOVDE}\n```"),
    ("fence, etiketsiz", f"```\n{GOVDE}\n```"),
    ("kapanışı eksik fence", f"```json\n{GOVDE}"),
    ("önünde nezaket cümlesi", f"Elbette, işte analiz:\n\n{GOVDE}"),
    ("önünde cümle + fence", f"İşte istediğiniz JSON:\n```json\n{GOVDE}\n```"),
    ("fence + arkasında cümle", f"```json\n{GOVDE}\n```\nUmarım yardımcı olur."),
    ("başlık + fence + kapanış", f"**Premortem**\n```json\n{GOVDE}\n```\nBaşka bir şey?"),
    ("arkasında not", f"{GOVDE}\n\nNot: tutarlar tahminidir."),
]


# ============================================================
# 1) ZARF TOLERANSI — ölçülen dokuz sarmalamanın hepsi ayrışır
# ============================================================

@pytest.mark.parametrize("ad,metin", SARMALAMALAR)
def test_premortem_tum_sarmalamalari_ayristirir(ad, metin):
    assert len(_parse_and_validate(metin)) == 3, ad


@pytest.mark.parametrize("ad,metin", SARMALAMALAR)
def test_cikar_govdeyi_bulur(ad, metin):
    assert cikar(metin)["scenarios"][0]["id"] == "S1", ad


# ============================================================
# 2) İÇERİĞE KATI — zarf affedilir, içerik AFFEDİLMEZ
# ============================================================

def test_eksik_alan_hala_reddedilir():
    """Zarfı affetmek, bozuk içeriği kabul etmek DEĞİLDİR."""
    bozuk = json.dumps({"scenarios": [{"id": "S1", "title": "kisa"}]})
    with pytest.raises(Exception):
        _parse_and_validate(f"İşte:\n```json\n{bozuk}\n```")


def test_senaryo_sayisi_hala_denetlenir():
    tek = json.dumps({"scenarios": [_senaryo(1, "orta")]})
    with pytest.raises(PremortemValidationError):
        _parse_and_validate(f"Buyurun:\n{tek}")


def test_scenarios_list_degilse_reddedilir():
    with pytest.raises(PremortemValidationError):
        _parse_and_validate('Sonuc: {"scenarios": "yok"}')


# ============================================================
# 3) DİZGE-DUYARLI TARAMA — metindeki süslü parantez dengeyi bozmaz
# ============================================================

def test_dizge_icindeki_susluyu_ayirt_eder():
    """Eski yedek ('ilk { … son }') bunu ayırt etmiyordu."""
    metin = 'Not: sablon "{ad}" olacak.\n{"a": "su{slu", "b": 2}\nBitti.'
    assert cikar(metin) == {"a": "su{slu", "b": 2}


def test_kacisli_tirnak_dengeyi_bozmaz():
    assert cikar(r'Bak: {"a": "de\"ger"}') == {"a": 'de"ger'}


def test_bos_blok_gercek_govdeyi_golgelemez():
    """Metindeki anlamsız `{}` gerçek gövdenin önüne geçemez."""
    assert cikar('Ornek: {} ve asil cevap: {"a": 1}') == {"a": 1}


# ============================================================
# 4) BAŞARISIZLIK — adlandırılmış hata, sessiz None DEĞİL
# ============================================================

@pytest.mark.parametrize("metin", ["", "   ", None, "hicbir json yok", "```json\nsadece metin\n```"])
def test_json_yoksa_adlandirilmis_hata(metin):
    with pytest.raises(JsonZarfiCozulemedi):
        cikar(metin)


def test_premortem_zarf_hatasi_retry_yoluna_duser():
    """`generate_premortem` bu hatayı yakalayıp ikinci denemeyi yapabilmeli."""
    import inspect

    from app import premortem as pm
    kaynak = inspect.getsource(pm.generate_premortem)
    assert "JsonZarfiCozulemedi" in kaynak, "zarf hatasi retry yolunda yakalanmiyor"


# ============================================================
# 5) TEK KAYNAK — iki yol da aynı çıkarmayı kullanır (drift kilidi)
# ============================================================

def test_iki_tuketici_de_tek_kaynagi_kullanir():
    """Aynı soruya ikinci bir cevap yazılırsa bu kapı kırmızı olur (L26)."""
    import inspect

    from app import coach_insights, premortem
    for modul, fonksiyon in ((premortem, "_parse_and_validate"),
                             (coach_insights, "_erl_k2_parse_llm_json")):
        kaynak = inspect.getsource(getattr(modul, fonksiyon))
        assert "_json_cikar" in kaynak, f"{modul.__name__}.{fonksiyon} tek kaynagi kullanmiyor"
        assert "json.loads" not in kaynak, f"{modul.__name__}.{fonksiyon} kendi parse'ini yapiyor"


def test_k2_parse_sarmalamayi_kaldirir():
    from app.coach_insights import _erl_k2_parse_llm_json
    govde = '{"patterns": [], "reasoning": "yetersiz veri"}'
    assert _erl_k2_parse_llm_json(f"İşte:\n```json\n{govde}\n```\nUmarım olur.") == {
        "patterns": [], "reasoning": "yetersiz veri"}
    assert _erl_k2_parse_llm_json("hicbir json yok") is None
    assert _erl_k2_parse_llm_json("") is None
