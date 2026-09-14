"""
DEVOPS-003 (BUG #474): frontend lint standardı KAYNAKTAN doğrulanır.

Ölçüm (14 Eyl 2026, kurulum öncesi): `frontend/`de ne eslint ne lint betiği vardı; koddaki 26
`eslint-disable` direktifi hiçbir yapılandırmanın tanımadığı kurallara işaret ediyordu (yani
susturma bile ölçülmüyordu). İlk koşum 112 hata buldu; ikisi GERÇEK defektti (koşullu hook).

Bu kapı ESLint'i koşturmaz (o, `scripts/eslint_kapisi.py`nin ve pre-commit/CI'ın işi); şunları
kaynaktan ölçer:
  1. yapılandırma tek dosyada ve react-hooks önerilenlerini içeriyor,
  2. araç sürümleri package.json'da TAM sabit ve baseline ile aynı,
  3. warn seviyesindeki her kural baseline tavanında (tavansız warn = görünmez gerileme),
  4. kapı pre-commit'e ve CI'a bağlı; CI frontend işi vitest'i de koşuyor,
  5. her `eslint-disable` direktifinin yazılı bir gerekçesi var,
  6. sayacın karar mantığı: hata → kırmızı, tavan aşımı → kırmızı, sürüm ayrışması → kırmızı,
     `--yaz` yalnız düşürür.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts import eslint_kapisi

KOK = Path(__file__).resolve().parent.parent
FRONTEND = KOK / "frontend"
CONFIG = FRONTEND / "eslint.config.js"
PACKAGE = FRONTEND / "package.json"
BASELINE = KOK / "docs" / "kalite-seruveni" / "kalite-baseline.json"
HOOK = KOK / ".githooks" / "pre-commit"
CI = KOK / ".github" / "workflows" / "ci.yml"

SABIT_PAKETLER = ("eslint", "@eslint/js", "eslint-plugin-react", "eslint-plugin-react-hooks", "globals")


def _oku(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _baseline_fe() -> dict:
    return json.loads(_oku(BASELINE))["frontend"]


def test_yapilandirma_tek_dosya_ve_react_hooks_onerilenleri():
    assert CONFIG.exists(), "frontend/eslint.config.js yok"
    eski = [p for p in FRONTEND.iterdir() if p.name.startswith(".eslintrc")]
    assert not eski, f"iki yapılandırma kaynağı: {eski}"
    kaynak = _oku(CONFIG)
    assert "eslint-plugin-react-hooks" in kaynak
    assert "reactHooks.configs['recommended-latest'].rules" in kaynak, "react-hooks önerilenleri yayılmıyor"
    assert "'react-hooks/rules-of-hooks': 'off'" not in kaynak
    assert "'react-hooks/exhaustive-deps': 'off'" not in kaynak, "FE-028'in kuralı kapatılamaz"
    for dizin in ("dist/**", "node_modules/**"):
        assert dizin in kaynak, f"{dizin} ignore listesinde değil"


def test_arac_surumleri_tam_sabit_ve_baseline_ile_ayni():
    paket = json.loads(_oku(PACKAGE))
    dev = paket["devDependencies"]
    for ad in SABIT_PAKETLER:
        assert ad in dev, f"{ad} devDependencies'te yok"
        assert re.fullmatch(r"\d+\.\d+\.\d+", dev[ad]), f"{ad} tam sürümle sabit değil: {dev[ad]}"
    assert paket["scripts"].get("lint") == "node scripts/lint.cjs"
    assert (FRONTEND / "scripts" / "lint.cjs").exists()
    fe = _baseline_fe()
    assert fe["arac"]["surum"] == dev["eslint"], "baseline eslint sürümü package.json ile ayrıştı"


def test_warn_seviyesindeki_her_kural_tavanli():
    kaynak = _oku(CONFIG)
    warn_kurallar = set(re.findall(r"'([\w/-]+)':\s*'warn'", kaynak))
    warn_kurallar |= set(re.findall(r"'([\w/-]+)':\s*\['warn'", kaynak))
    tavan = _baseline_fe()["tavan"]
    # no-console: uyarı ama tavanda yok → sayaç onu da "YENİ KURAL" diye kırar; sıfırda tutulur.
    eksik = {k for k in warn_kurallar if k not in tavan and k != "no-console"}
    assert not eksik, f"warn seviyesinde ama tavansız kural: {eksik}"
    assert all(isinstance(v, int) and v >= 0 for v in tavan.values())


def test_kapi_pre_commit_ve_ci_ya_bagli():
    hook = _oku(HOOK)
    assert "scripts/eslint_kapisi.py" in hook, "pre-commit lint kapısını çağırmıyor"
    assert re.search(r"frontend/\(src\|e2e\|scripts\)", hook), "hook e2e/scripts değişikliğinde lint koşmuyor"
    ci = _oku(CI)
    assert "frontend-kalite:" in ci
    assert "python scripts/eslint_kapisi.py" in ci
    assert "npx vitest run" in ci, "CI frontend işi vitest koşmuyor"


def test_her_eslint_disable_direktifinin_gerekcesi_var():
    """Gerekçe: aynı satırda `-- ...` ya da hemen üstte bir yorum satırı (direktif olmayan)."""
    kusurlu = []
    for dosya in list((FRONTEND / "src").rglob("*.js")) + list((FRONTEND / "src").rglob("*.jsx")):
        satirlar = _oku(dosya).split("\n")
        for i, s in enumerate(satirlar):
            if "eslint-disable" not in s or "test(" in s or "/eslint-disable" in s:
                continue
            inline = re.search(r"eslint-disable[^\n]*?\s--\s\S", s)
            ust = satirlar[i - 1].strip() if i else ""
            ust_yorum = ust.startswith("//") and "eslint-disable" not in ust
        # `x(); // eslint-disable-line` biçiminde: gerekçe üstteki yorum satırında
            if not (inline or ust_yorum):
                kusurlu.append(f"{dosya.relative_to(FRONTEND)}:{i + 1}")
    assert not kusurlu, f"gerekçesiz susturma: {kusurlu}"


# ── Sayacın karar mantığı ─────────────────────────────────────────────────────
def _rapor(hata=0, uyari=0, kural="react-hooks/set-state-in-effect"):
    mesajlar = [{"ruleId": "no-undef", "severity": 2, "line": 1, "message": "x"} for _ in range(hata)]
    mesajlar += [{"ruleId": kural, "severity": 1, "line": 2, "message": "y"} for _ in range(uyari)]
    return [{"filePath": "C:/x/frontend/src/A.jsx", "messages": mesajlar}]


def _baseline(tavan: int, surum="9.39.5"):
    return {"frontend": {"arac": {"surum": surum}, "tavan": {"react-hooks/set-state-in-effect": tavan}}}


def test_karar_hata_kirar(capsys):
    assert eslint_kapisi.karar(_baseline(5), _rapor(hata=1, uyari=0), "9.39.5", yaz=False) == 1
    assert "HATA" in capsys.readouterr().out


def test_karar_tavan_asimi_kirar_esitlik_gecer():
    assert eslint_kapisi.karar(_baseline(5), _rapor(uyari=6), "9.39.5", yaz=False) == 1
    assert eslint_kapisi.karar(_baseline(5), _rapor(uyari=5), "9.39.5", yaz=False) == 0
    assert eslint_kapisi.karar(_baseline(5), _rapor(uyari=3), "9.39.5", yaz=False) == 0


def test_karar_yeni_warn_kurali_tavansizsa_kirar():
    assert eslint_kapisi.karar(_baseline(5), _rapor(uyari=1, kural="no-console"), "9.39.5", yaz=False) == 1


def test_karar_surum_ayrismasi_kirar():
    assert eslint_kapisi.karar(_baseline(5), _rapor(), "10.0.0", yaz=False) == 1


def test_yaz_yalniz_dusurur(tmp_path, monkeypatch):
    yol = tmp_path / "baseline.json"
    monkeypatch.setattr(eslint_kapisi, "BASELINE_YOLU", yol)
    monkeypatch.setattr(eslint_kapisi, "REPO_KOK", tmp_path)
    b = _baseline(5)
    assert eslint_kapisi.karar(b, _rapor(uyari=3), "9.39.5", yaz=True) == 0
    assert json.loads(yol.read_text(encoding="utf-8"))["frontend"]["tavan"]["react-hooks/set-state-in-effect"] == 3
    # yükseltme reddi: dosya yazılmaz
    b = _baseline(2)
    assert eslint_kapisi.karar(b, _rapor(uyari=3), "9.39.5", yaz=True) == 1
    assert json.loads(yol.read_text(encoding="utf-8"))["frontend"]["tavan"]["react-hooks/set-state-in-effect"] == 3


@pytest.mark.parametrize("dosya", ["src/panels/Cockpit.jsx", "src/components/PendingActions.jsx"])
def test_gercek_defektler_kapali(dosya):
    """rules-of-hooks: hook'lar erken dönüşten önce; static-components: Row render dışında."""
    kaynak = _oku(FRONTEND / dosya)
    if dosya.endswith("PendingActions.jsx"):
        gov = kaynak.index("function TransactionTable(")
        assert kaynak.index("useEffect(() => {", gov) < kaynak.index("if (!p) return null;", gov)
        gov2 = kaynak.index("export default function PendingActions(")
        assert kaynak.index("useState(false);   // BUG #472", gov2) < kaynak.index("if (!actions || actions.length === 0) return null;", gov2)
    else:
        assert "function DokumSatiri(" in kaynak
        assert "const Row = (" not in kaynak
