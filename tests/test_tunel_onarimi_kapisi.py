"""
BUG #478 KAPISI — "FUNNEL ON" YAZAN YAPILANDIRMA, ÖLÜ BİR İNGRESS OTURUMUNU GİZLER.

ÖLÇÜLEN OLAY (14 Eyl 2026, 10:35–11:35)
---------------------------------------
Sağlık görevi altı koşum boyunca "DIS YOL erisilemiyor (son kod: 000)" yazdı. Uygulama
yerelde 200 veriyordu, `tailscale funnel status` "Funnel on" diyordu, DoH üç ingress IP'sini
doğru çözüyordu; üçü de TLS el sıkışmasında 0,12 sn'de düşüyordu. GitHub'daki dış sonda aynı
anda 000 gördü ve kesinti kaydı (#1) açtı. Kök neden: ağ kopup gelince (10:35 DNS kesintisi,
10:46 uyku) funnel'ın ingress OTURUMU yenilenmedi; yapılandırma "açık" kaldı. 2. adımın
sorduğu "funnel açık mı" bunu göremez. Onarım ölçüldü: `serve reset` + funnel'ı yeniden
vermek 30 sn içinde üç ingress'i de 200'e döndürdü.

KİLİTLENEN SÖZLEŞME
-------------------
1. Dış yol düşünce görev yalnız raporlamaz, funnel oturumunu yeniler — ama YALNIZ uygulama
   yerelde sağlamken (sorun tünelde) ve adres çözülüyorken (sorun DNS'te değil).
2. Onarım ölçümü yemez (BUG #344): koşum `onarim=1` olarak kayda geçer.
3. Onarımdan sonra dış yol YENİDEN ölçülür; ölçüm 200 demeden "onarıldı" denmez.
4. Yenileme `serve reset` + `funnel --bg --https=443` ikilisidir (yalnız funnel'ı yeniden
   vermek yetmedi; ölçüldü: reset olmadan ingress'lerden ikisi 000'da kaldı).
"""
from __future__ import annotations

import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
SAGLIK = KOK / "deploy" / "windows" / "saglik.ps1"


def _kaynak() -> str:
    return SAGLIK.read_text(encoding="utf-8")


def _onarim_blogu() -> str:
    """3. adımdaki onarım bloğu: `if (-not $disOk -and ...` ile başlar, ilk `}` seviyesinde biter."""
    s = _kaynak()
    i = s.index("if (-not $disOk -and $uygulamaOk")
    return s[i : s.index("\n    if (-not $disOk) { $disNot", i)]


def test_onarim_yalniz_uygulama_saglam_ve_adres_cozuluyorken():
    blok = _onarim_blogu()
    assert "$uygulamaOk" in blok.splitlines()[0], "uygulama düşükken tünel onarımı yanlış hedefe vurur"
    s = _kaynak()
    # blok, `$ipler.Count -eq 0` dalının ELSE'inde: adres çözülmüyorsa girilmez
    else_baslangic = s.index("} else {", s.index("DIS ADRES HIC COZULMUYOR"))
    assert s.index("if (-not $disOk -and $uygulamaOk") > else_baslangic


def test_onarim_olcumu_yemez():
    blok = _onarim_blogu()
    assert "$onarimGerekti = $true" in blok, "onarım kayda 'onarim=1' olarak geçmeli (BUG #344)"


def test_onarim_sonrasi_yeniden_olculur_ve_ancak_200_ile_onarildi_denir():
    blok = _onarim_blogu()
    assert re.search(r"--resolve \"\$\{Adres\}:443:\$\{ip\}\"", blok), "onarım sonrası dış yol yeniden ölçülmüyor"
    onarildi = blok.index('Yaz "ONARILDI"')
    assert blok.index('$sonKod -eq "200"') < onarildi, '"onarıldı" ölçümden önce söyleniyor'
    assert '$disOk = $true' in blok[blok.index('$sonKod -eq "200"'):]


def test_yenileme_serve_reset_ve_funnel_ikilisi():
    blok = _onarim_blogu()
    assert "& $ts serve reset" in blok, "komut yok (log metnindeki 'serve reset' sayılmaz)"
    assert re.search(r"& \$ts funnel --bg --https=443 \"http://127\.0\.0\.1:\$Port\"", blok)
    assert blok.index("& $ts serve reset") < blok.index("& $ts funnel --bg"), "önce reset, sonra funnel"


def test_baslik_artik_yalniz_raporlanir_demiyor():
    s = _kaynak()
    assert "3. DIŞ YOL (yalnız raporlanır)" not in s
    assert "BUG #478" in s
