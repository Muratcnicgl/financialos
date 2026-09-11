"""
SEC-016 / BUG #412 KAPISI — HATA GÖVDESİNE HAM İSTİSNA METNİ SIZMAZ.

Ölçülen (12 Eyl 2026): beklenmedik hata için merkezî 500 işleyicisi genel metin + korelasyon
kodu döner (BUG #280, `test_korelasyon_kapisi` kilitler); açık 500'ler (legal, simulation)
genel metinli; `detail=str(e)` yalnız BİR yerde — `transactions` hızlı-giriş ayrıştırma
hatası (`_parse_quick_text` ValueError: kullanıcının kendi metnine dair mesaj, iç bilgi
değil). Madde "tüm endpoint garanti değil" diyordu; garanti ölçülüp kilitlendi.

Kilitlenen: router'larda `detail=str(<istisna>)` / `detail=f"...{e}..."` deseni yalnız
gerekçeli listede; merkezî işleyici ham `str(exc)` içermez.
"""
from __future__ import annotations

import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent.parent
ROUTERS = KOK / "app" / "routers"
DESEN = re.compile(r"detail=(?:str|repr)\(\s*(\w+)\s*\)|detail=f\"[^\"]*\{(e|exc|err|hata)\b")

# Gerekçeli izin: dosya → (adet, neden). Yalnız kullanıcı-girdisi doğrulama mesajları.
IZINLI = {
    "transactions.py": (1, "hızlı giriş ayrıştırma (ValueError) — kullanıcının kendi metnine dair mesaj, iç bilgi taşımaz"),
}


def _bulgular():
    out = {}
    for p in sorted(ROUTERS.glob("*.py")):
        n = 0
        for s in p.read_text(encoding="utf-8").splitlines():
            if s.strip().startswith("#"):
                continue
            if DESEN.search(s):
                n += 1
        if n:
            out[p.name] = n
    return out


def test_router_hata_detayi_ham_istisna_tasimaz():
    bulgular = _bulgular()
    fazla = {d: n for d, n in bulgular.items() if n > IZINLI.get(d, (0, ""))[0]}
    assert fazla == {}, f"ham istisna metni hata gövdesine sızıyor: {fazla} — genel mesaj + log (BE-009)"
    for d, (adet, _) in IZINLI.items():
        assert bulgular.get(d, 0) == adet, f"{d}: izin {adet}, ölçülen {bulgular.get(d, 0)} — listeyi gerçek sayıya çek"


def test_merkezi_500_isleyicisi_ham_metin_icermez():
    kaynak = (KOK / "app" / "main.py").read_text(encoding="utf-8")
    i = kaynak.index("@app.exception_handler(Exception)")
    govde = kaynak[i:i + 2500]
    assert "Beklenmedik bir hata oluştu" in govde
    assert not re.search(r"\"detail\":\s*f?\"[^\"]*\{(exc|e)\b", govde), "500 gövdesi istisna metnini taşıyor"
    assert "str(exc)" not in govde.split("content=")[1].split("}")[0]


def test_kapi_kendisi_calisiyor():
    assert DESEN.search('raise HTTPException(status_code=400, detail=str(e))')
    assert DESEN.search('detail=f"olmadi: {e}"')
    assert not DESEN.search('detail=f"Kullanici zaten var (id={existing.id})"')
    assert not DESEN.search('detail="Simulasyon su anda yapilamiyor."')
