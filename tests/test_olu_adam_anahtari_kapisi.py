"""
BUG #342 KAPISI — ÖLÜ ADAM ANAHTARININ SÖZLEŞMESİ: SUSMAK ALARMDIR.

ÖLÇÜLEN OLAY (BUG #326/#328)
----------------------------
Kapalı beta 24,5 saat kapalı kaldı ve kimse fark etmedi. Makinenin üzerindeki sağlık
görevi arızayı GÖRÜYORDU ama yalnız `logs/servis.log`'a yazıyordu — ölçen sistem, haber
veren sistem değildir (L61).

NEDEN YOKLAMA DEĞİL, ÖLÜ ADAM ANAHTARI
---------------------------------------
Yoklayan (polling) bir izleyici **sessizce ölebilir**, ve öldüğünde sessizlik "her şey
yolunda" gibi görünür — yani izlemenin kendisi, kapatmak için var olduğu körlüğü üretir.
Ölü adam anahtarı yönü tersine çevirir: makine dışarı ping atar; ping kesilirse alarm
çalar. Kesilme sebeplerinin HEPSİ kesintidir (servis öldü · makine kapandı · ağ gitti ·
görev bozuldu). **Sessizlik, her şeyin yolunda olduğunun değil, alarmın kendisidir.**

KİLİTLENEN SÖZLEŞME (ve neden her maddesi gerekli)
---------------------------------------------------
1. **Ping YALNIZ sağlık tamken atılır.** Koşulsuz ping, "süreç ayakta" ile "servis
   çalışıyor"u karıştırırdı — Y1'in kök nedeni tam buydu (eski süreç de 200 veriyordu).
   Koşulsuz ping atan bir ölü adam anahtarı, alarmı KALICI OLARAK susturur: en tehlikeli
   arıza biçimi, çünkü sistem "izleniyorum" der ve izlenmez.
2. **Ping hatası sağlık görevini DÜŞÜRMEZ.** Bekçi, beklediği şeyi bozmamalı: izleme
   servisi düştüğünde uygulamanın sağlık/onarım döngüsü çalışmaya devam etmeli.
3. **Ping adresi depoya GİRMEZ.** O URL bir kimlik taşır; commit edilirse herkes sahte
   "sağlıklıyım" sinyali gönderip alarmı susturabilir.

Ölçüm PowerShell'in KENDİ ayrıştırıcısıyla yapılır (metin arama değil): çağrının hangi
`if` bloğunun içinde olduğu ancak sözdizimi ağacından bilinir.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

KOK_ = Path(__file__).resolve().parent.parent
if str(KOK_) not in sys.path:
    sys.path.insert(0, str(KOK_))
from scripts.kabuk import git as _git, powershell as _ps, ps_dizge as _psd  # noqa: E402

KOK = Path(__file__).resolve().parent.parent
SAGLIK = KOK / "deploy" / "windows" / "saglik.ps1"
PING_DOSYA = "deploy/windows/izleme-url.txt"

# `-Command` ile fazladan argümanlar `$args`e DÜŞMEZ (aynı tuzağa bu turda ikinci kez
# düşüldü — `test_ps1_bom_kapisi.py` de aynı notu taşıyor). Yol komuta GÖMÜLÜR; içinde
# boşluk ve Türkçe karakter olduğu için tek tırnak + tek tırnak kaçışıyla.
_AST_SORGU = r"""
$ErrorActionPreference='Stop'
$e=$null; $t=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile(__YOL__,[ref]$t,[ref]$e)
if ($e.Count -gt 0) { Write-Output (@{hata=$e[0].Message}|ConvertTo-Json -Compress); exit 0 }

# `PingAt` ÇAĞRILARI (fonksiyon TANIMI degil)
$cagrilar = $ast.FindAll({ param($n)
    $n -is [System.Management.Automation.Language.CommandAst] -and
    $n.GetCommandName() -eq 'PingAt' }, $true)

# Saglik TAM oldugunu soyleyen if blogu
$ifler = $ast.FindAll({ param($n)
    $n -is [System.Management.Automation.Language.IfStatementAst] -and
    $n.Clauses[0].Item1.Extent.Text -match '\$sorun\.Count\s*-eq\s*0' }, $true)

# `PingAt` govdesinde try/catch var mi
$fn = $ast.FindAll({ param($n)
    $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
    $n.Name -eq 'PingAt' }, $true)
$tryVar = $false
if ($fn.Count -gt 0) {
    $tryVar = ($fn[0].FindAll({ param($n)
        $n -is [System.Management.Automation.Language.TryStatementAst] }, $true)).Count -gt 0
}

$sonuc = @{
    cagri_sayisi = $cagrilar.Count
    saglikli_if_var = ($ifler.Count -gt 0)
    fonksiyon_var = ($fn.Count -gt 0)
    try_var = $tryVar
    cagrilar_saglikli_blokta = @()
}
foreach ($c in $cagrilar) {
    $icinde = $false
    foreach ($i in $ifler) {
        $g = $i.Clauses[0].Item2.Extent      # yalniz THEN govdesi
        if ($c.Extent.StartOffset -ge $g.StartOffset -and $c.Extent.EndOffset -le $g.EndOffset) {
            $icinde = $true
        }
    }
    $sonuc.cagrilar_saglikli_blokta += $icinde
}
Write-Output ($sonuc | ConvertTo-Json -Compress)
"""


def _ast() -> dict:
    p = _ps(_AST_SORGU.replace("__YOL__", _psd(SAGLIK)))
    if p.returncode != 0 or not p.stdout.strip():
        if "not recognized" in (p.stderr or "") or p.returncode == 127:
            pytest.skip("powershell yok (Windows disi ortam)")
        pytest.fail(f"AST sorgusu basarisiz: {(p.stderr or p.stdout)[:600]}")
    return json.loads(p.stdout.strip().splitlines()[-1])


def test_PING_YALNIZ_SAGLIK_TAMKEN_atilir():
    """
    **Bu kapının asıl maddesi.** Koşulsuz ping atan bir ölü adam anahtarı alarmı KALICI
    olarak susturur — sistem "izleniyorum" der ve izlenmez. En tehlikeli arıza biçimi bu,
    çünkü hiçbir belirti üretmez.
    """
    a = _ast()
    assert not a.get("hata"), a.get("hata")
    assert a["fonksiyon_var"], "PingAt fonksiyonu yok — ölü adam anahtarı kaldırılmış"
    assert a["saglikli_if_var"], "`$sorun.Count -eq 0` bloğu bulunamadı — sözleşme kayması"
    assert a["cagri_sayisi"] >= 1, "PingAt hiç çağrılmıyor — anahtar ölü"
    icinde = a["cagrilar_saglikli_blokta"]
    if isinstance(icinde, bool):
        icinde = [icinde]
    assert all(icinde), (
        "PingAt çağrısı SAĞLIK TAM bloğunun DIŞINDA: ping koşulsuz atılıyor olabilir.\n"
        "Bu, ölü adam anahtarını tersine çevirir — servis ölse bile 'sağlıklıyım' sinyali "
        "gider ve alarm KALICI olarak susar."
    )


def test_PING_HATASI_saglik_gorevini_DUSURMEZ():
    """Bekçi, beklediği şeyi bozmamalı: izleme servisi düşse de onarım döngüsü sürmeli."""
    a = _ast()
    assert a["try_var"], (
        "PingAt gövdesinde try/catch yok — izleme servisi düştüğünde sağlık görevi de "
        "düşer ve uygulama onarımsız kalır."
    )


def test_PING_ADRESI_DEPOYA_GIRMEZ():
    """
    URL bir kimlik taşır: commit edilirse herkes sahte 'sağlıklıyım' gönderip alarmı
    susturabilir. Hem izlenmemesi hem `.gitignore`da olması ölçülür — yalnız "şu an yok"
    demek, yarın eklenmesini engellemez.
    """
    izlenen = _git("ls-files", PING_DOSYA).stdout.strip()
    assert not izlenen, f"{PING_DOSYA} git tarafından İZLENİYOR — ping kimliği depoda"

    yoksay = _git("check-ignore", PING_DOSYA)
    assert yoksay.returncode == 0, (
        f"{PING_DOSYA} .gitignore kapsamında değil — bir gün yanlışlıkla commit edilir."
    )
