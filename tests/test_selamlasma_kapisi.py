"""
LLM-035 (BUG #503): selam/teşekkür/veda turunda araç yok — save_insight de yok.

Ölçüm (14 Eyl 2026): `save_insight` her turda aktifti; canlıda "Kart ile ödeme tavsiyesi
isteği" gibi gerçek olmayan içgörüler yazılmıştı; her selamda araç şeması gidiyordu.
Kilitlenen:
  1. sınıflandırıcı: kısa selam/teşekkür/veda → True (Türkçe karakter ve noktalama duyarsız);
     finansal içerikli ya da uzun mesaj → False (yanlış pozitif = kayıp kayıt, ağır hata),
  2. chat akışı selamda `active_tools = []` verir ve gerekçeyi ize yazar (kaynak),
  3. içgörü sözleşmesi (BUG #268) zaten içeriksiz kaydı reddeder, boş dedup'ı türetir — bu
     maddenin diğer iki eylemi kapalıydı; burada yalnız doğrulanır.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.insight_schema import IcgoruGecersiz, ayikla
from app.intent_rules import selamlasma_mi

KOK = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("m", ["Merhaba!", "selam", "Teşekkürler 🙏", "iyi geceler", "sağ ol", "Tamam.", "Günaydın", "hoşça kal", "naber", "ok"])
def test_selam_tesekkur_veda_yakalanir(m):
    assert selamlasma_mi(m) is True


@pytest.mark.parametrize("m", [
    "merhaba, dün 500 TL market harcadım", "Teşekkürler, kart borcum ne kadar?", "selam bütçem ne durumda",
    "500 harcadım", "kira ödedim", "", "   ", "iyi geceler yarın 2000 TL gelecek",
])
def test_finansal_ya_da_uzun_mesaj_selam_degil(m):
    assert selamlasma_mi(m) is False


def test_chat_akisi_selamda_aracsiz():
    src = (KOK / "app" / "coach.py").read_text(encoding="utf-8")
    assert "_selam = _selamlasma_mi(user_message)" in src
    assert "if _selam:\n                offer_propose = False\n                active_tools = []" in src
    assert "'selamlasma: aracsiz tur' if _selam else _niyet.gerekce" in src


def test_icgoru_sozlesmesi_bos_icerik_reddeder_dedup_turetir():
    with pytest.raises(IcgoruGecersiz):
        ayikla({"content": "   "})
    a = ayikla({"content": "Kira her ayın 5'inde ödenir"})
    assert a.dedup_key and any("dedup_key yoktu" in d for d in a.duzeltmeler)
