"""
BUG #271 — "KAYDETTİM" GÜVENCESİ ÜÇ AYRI YERDEN DELİKTİ (LLM-020).

`_postprocess_report`'un işi tek cümlede: **aksiyon oluşmadıysa koç "kaydettim" izlenimi
vermemeli** (BUG #041/#085'in kapatmak istediği finansal güven ihlali).

ÖLÇÜM (8 Ağu 2026, düzeltme ÖNCESİ):

| Eksen | Sonuç | Neden |
|---|---|---|
| Sahte tamamlama fiilleri | **6/12 kaçıyordu** | Liste kapalı: "işleme aldım", "kayda geçirdim", "not olarak girdim", "sisteme yazdım", "hallettim", "düştüm" hiçbir filtreye takılmıyordu |
| Çok satırlı yanıt | **hiç korunmuyordu** | `is_structured_report` dalı çok satırlı / `##` / `[` içeren yanıtta taramayı KOMPLE atlıyordu → `"## Durum\\n\\nHarcamanı kaydettim."` dokunulmadan, **hiçbir uyarı olmadan** kullanıcıya gidiyordu |
| EMANET KASA (cockpit'te 0) | **3/6 kaçıyordu** | Silici bölümün NUMARALANMIŞ olmasını şart koşuyordu; `## EMANET KASA`, `**EMANET KASA**`, `### Emanet Kasa` uydurma tutarla birlikte geçiyordu |

Yanlış-pozitif 0/5 idi — yani filtre hassastı ama **kapsamı varsayımdı.**

TASARIM KARARI: listeyi büyütmek tek başına çözüm değil — liste #041 → #085 → #094 boyunca
büyüdü ve hâlâ 6 kaçırıyordu. Güvence artık **ifadeye değil DURUMA** bağlı: kullanıcı
gerçekleşmiş bir eylem bildirdiyse (BUG #267'nin `intent_rules` sözleşmesi) ve o turda
hiçbir aksiyon doğmadıysa, cevabın sonuna dürüst not eklenir — **fiilden ve yanıtın
biçiminden bağımsız.** Fiil listesi ikinci savunma olarak kaldı ve ölçülen korpusla birlikte
BU KAPIYA yazıldı: bir sonraki eş anlamlı sessiz delik değil, kırmızı testtir.
"""
from __future__ import annotations

import pytest

from app.coach import _KAYIT_YOK_NOTU, _postprocess_report

COCKPIT = {"emanet_kasa": 0, "nakit_kasa": 5000.0}
BILDIRIM = "320 TL market harcadım nakitten"      # gerçekleşmiş eylem bildirimi
SORU = "bu ay ne kadar harcadım?"                  # analiz isteği

# Ölçülen korpus — koçun aksiyon oluşmadan kurabildiği tamamlama cümleleri
SAHTE_CUMLELER = [
    "Harcamanı kaydettim.",
    "İşlemi kaydettim, bakiyen güncellendi.",
    "500 TL gideri ekledim.",
    "Bunu işledim.",
    "Kaydı güncelledim.",
    "Hesabına geçirdim.",
    "İşleme aldım, tamamdır.",
    "Not olarak girdim.",
    "Kayda geçirdim.",
    "Sisteme yazdım.",
    "Tamamdır, hallettim.",
    "Bu harcamayı düştüm.",
]


def _yaniltmiyor(cikti: str, cumle: str) -> bool:
    """İddia ya SİLİNMİŞ ya da kullanıcı UYARILMIŞ olmalı."""
    silindi = cumle.rstrip(".").lower() not in cikti.lower()
    uyarildi = ("kayıt oluşturmadım" in cikti) or ("Hangi hesaptan" in cikti)
    return silindi or uyarildi


# ============================================================
# 1) TEK SATIRLIK YANIT — ölçülen 12 cümlenin hepsi
# ============================================================

@pytest.mark.parametrize("cumle", SAHTE_CUMLELER)
def test_tek_satir_sahte_tamamlama_yaniltmaz(cumle):
    cikti = _postprocess_report(cumle, COCKPIT, user_message=BILDIRIM, proposed_actions=[])
    assert _yaniltmiyor(cikti, cumle), cikti


# ============================================================
# 2) ÇOK SATIRLI RAPOR — koruma çalışır VE rapor iskeleti bozulmaz
# ============================================================

@pytest.mark.parametrize("cumle", SAHTE_CUMLELER)
def test_cok_satirli_raporda_da_yaniltmaz(cumle):
    """Düzeltme öncesi bu eksende koruma HİÇ çalışmıyordu."""
    metin = f"## Durum\n\n{cumle}\n\nKart borcun 12.500 TL."
    cikti = _postprocess_report(metin, COCKPIT, user_message=BILDIRIM, proposed_actions=[])
    assert _yaniltmiyor(cikti, cumle), cikti
    # Rapor iskeleti korunur — BUG #085 iter2'nin haklı kaygısı
    assert "## Durum" in cikti and "Kart borcun 12.500 TL." in cikti, cikti


# KARIŞIK mesaj: durum-tabanlı not devreye GİRMEZ (soru var) → çok satırlı yanıtta tek
# koruma SATIR TARAMASIDIR. Bu ayrım kapının kendi kör noktasıydı: not, taramayı
# gölgelediği için tarama bozulsa bile testler yeşil kalıyordu (mutasyon M5 ile ölçüldü).
KARISIK = "320 TL harcadım, bütçem ne durumda?"


@pytest.mark.parametrize("cumle", SAHTE_CUMLELER[:6])
def test_karisik_mesajda_cok_satirli_iddia_satiri_atilir(cumle):
    metin = f"## Durum\n\n{cumle}\n\nKart borcun 12.500 TL."
    cikti = _postprocess_report(metin, COCKPIT, user_message=KARISIK, proposed_actions=[])
    assert _KAYIT_YOK_NOTU not in cikti, "karisik mesajda not eklenmemeli (gurultu)"
    assert cumle.rstrip(".").lower() not in cikti.lower(), f"iddia satiri atilmadi: {cikti}"
    assert "## Durum" in cikti and "Kart borcun 12.500 TL." in cikti, cikti


# ============================================================
# 3) DURUM-TABANLI NOT — fiilden ve biçimden BAĞIMSIZ güvence
# ============================================================

def test_bildirimde_aksiyon_yoksa_kullanici_bilgilendirilir():
    """Koç hiçbir tamamlama iddiası kurmasa BİLE, kayıt oluşmadıysa bu söylenir."""
    cikti = _postprocess_report("Anladım, nakit bakiyen 5.000 TL.", COCKPIT,
                                user_message=BILDIRIM, proposed_actions=[])
    assert _KAYIT_YOK_NOTU in cikti


def test_bilinmeyen_es_anlamli_da_kapsanir():
    """Fiil listesinde OLMAYAN bir tamamlama ifadesi — not yine de kullanıcıyı uyarır."""
    cikti = _postprocess_report("Tamam, senin için hallolmuş durumda.", COCKPIT,
                                user_message=BILDIRIM, proposed_actions=[])
    assert _KAYIT_YOK_NOTU in cikti


def test_aksiyon_varsa_not_eklenmez():
    cikti = _postprocess_report("Harcamanı hazırladım, onayına sunuyorum.", COCKPIT,
                                user_message=BILDIRIM, proposed_actions=[{"id": 1}])
    assert _KAYIT_YOK_NOTU not in cikti


def test_soru_mesajinda_not_eklenmez():
    """Kullanıcı bir şey bildirmediyse 'kayıt oluşturmadım' gürültüdür."""
    cikti = _postprocess_report("Bu ay 3.200 TL harcamışsın.", COCKPIT,
                                user_message=SORU, proposed_actions=[])
    assert _KAYIT_YOK_NOTU not in cikti


def test_not_ile_netlestirme_mesaji_cakismaz():
    """İddia silindiyse zaten netleştirme mesajı gider; iki not üst üste binmez."""
    cikti = _postprocess_report("Harcamanı kaydettim.", COCKPIT,
                                user_message=BILDIRIM, proposed_actions=[])
    assert _KAYIT_YOK_NOTU not in cikti
    assert "Hangi hesaptan" in cikti


# ============================================================
# 4) MEŞRU METİN — yanlış-pozitif yok
# ============================================================

MESRU = [
    "Geçen ay 3 fatura işlendi.",
    "Maaşın hesabına geçirildi.",
    "Bu harcamayı sen kaydettin.",
    "Kaydettiğin işlemler arasında market var.",
    "Kart borcun 12.500 TL.",
]


@pytest.mark.parametrize("cumle", MESRU)
def test_mesru_metne_dokunulmaz(cumle):
    cikti = _postprocess_report(cumle, COCKPIT, user_message=SORU,
                                proposed_actions=[{"id": 1}])
    assert cikti.strip() == cumle.strip()


# ============================================================
# 5) EMANET KASA — koruma modelin BİÇİMİNE bağlı olamaz
# ============================================================

EMANET_BASLIKLARI = [
    "[5. EMANET KASA]", "## 5. EMANET KASA", "5) EMANET KASA",
    "## EMANET KASA", "**EMANET KASA**", "### Emanet Kasa",
    "## EMANET KASA:", "5. Emanet Kasa",
]


@pytest.mark.parametrize("baslik", EMANET_BASLIKLARI)
def test_emanet_bolumu_numaradan_bagimsiz_silinir(baslik):
    """Düzeltme öncesi numarasız başlıklar uydurma tutarla birlikte geçiyordu."""
    metin = f"{baslik}\nEmanet kasanda 12.000 TL var.\n\n## SONRAKI\nDevam."
    cikti = _postprocess_report(metin, COCKPIT, user_message=SORU,
                                proposed_actions=[{"id": 1}])
    assert "12.000" not in cikti, cikti
    assert "Devam." in cikti, "sonraki bölüm yenmiş"


def test_emanet_doluysa_silinmez():
    """Koruma yalnız cockpit 0 iken çalışır — gerçek emanet bilgisi silinemez."""
    metin = "## EMANET KASA\nEmanet kasanda 12.000 TL var."
    cikti = _postprocess_report(metin, {"emanet_kasa": 12000.0}, user_message=SORU,
                                proposed_actions=[{"id": 1}])
    assert "12.000" in cikti


# ============================================================
# 6) DRIFT KİLİDİ — desenler katlanmış yazılır (L32)
# ============================================================

def test_sahte_tamamlama_deseni_katlanmis():
    """Diakritikli literal, normalize edilmiş metinle asla eşleşmez → sessizce ölür."""
    from app.coach import _EMANET_HEADER_RE, _FAKE_PASTTENSE_RE
    from app.tr_text import katlanmis_mi

    for desen in (_FAKE_PASTTENSE_RE, _EMANET_HEADER_RE):
        assert katlanmis_mi(desen.pattern), f"katlanmamis desen: {desen.pattern}"
