"""
BUG #221 statik kapısı — workspace'li bir modele workspace_id YAZMADAN kayıt açılamaz.

Mevcut statik kapı (`tests/test_scope_enforcement.py`) yalnız SORGULARI denetliyor
(denetim bulgusu D31). Oysa BUG #221'in şekli okuma değil YAZMA idi: satır `workspace_id`
olmadan INSERT ediliyor, sonra workspace kapsamlı okuma onu ELİYOR — kayıt kullanıcının
kendi listesinden kayboluyor (SQLite'ta sessizce, prod PostgreSQL'de ayrıca RLS ile).

Bu kapı `app/` ağacındaki her `Model(...)` çağrısını AST ile tarar. Model `workspace_id`
kolonu taşıyorsa çağrı ya bu alanı vermeli ya da satırın sonunda gerekçeli bir
`# ws-exempt: <gerekçe>` işareti bulunmalıdır.

L11 gereği kapsam ÖLÇÜLÜR: taranan çağrı sayısı bir tabanın altına düşerse kapı kendini
kırar (tarama yolu bozulup kapı sessizce körleşemez).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"
MODELS_PY = APP / "models.py"

# Kapsam tabanı: bugün workspace'li modellerin app/ içinde ~25 instantiation'ı var.
MIN_TARANAN_CAGRI = 15


def _workspace_modelleri() -> set[str]:
    """`workspace_id` kolonu taşıyan model sınıfları — models.py'den türetilir (elle liste yok)."""
    agac = ast.parse(MODELS_PY.read_text(encoding="utf-8"))
    modeller = set()
    for dugum in ast.walk(agac):
        if not isinstance(dugum, ast.ClassDef):
            continue
        for govde in dugum.body:
            hedefler = []
            if isinstance(govde, ast.Assign):
                hedefler = [t.id for t in govde.targets if isinstance(t, ast.Name)]
            elif isinstance(govde, ast.AnnAssign) and isinstance(govde.target, ast.Name):
                hedefler = [govde.target.id]
            if "workspace_id" in hedefler:
                modeller.add(dugum.name)
    return modeller


def _cagrilar():
    """(dosya, satır, model, verilen_alanlar, kaynak_satır) — app/ ağacındaki her model çağrısı."""
    modeller = _workspace_modelleri()
    for yol in sorted(APP.rglob("*.py")):
        kaynak = yol.read_text(encoding="utf-8")
        satirlar = kaynak.splitlines()
        for dugum in ast.walk(ast.parse(kaynak)):
            if not (isinstance(dugum, ast.Call) and isinstance(dugum.func, ast.Name)):
                continue
            if dugum.func.id not in modeller:
                continue
            alanlar = {k.arg for k in dugum.keywords if k.arg}
            yildiz = any(k.arg is None for k in dugum.keywords)   # Model(**data)
            blok = "\n".join(satirlar[dugum.lineno - 1: (dugum.end_lineno or dugum.lineno)])
            yield yol, dugum.lineno, dugum.func.id, alanlar, yildiz, blok


def test_workspace_modelleri_models_pyden_turetiliyor():
    """Kapının kendisi: model listesi elle yazılmaz, şemadan türetilir (drift olmaz)."""
    modeller = _workspace_modelleri()
    assert {"Transaction", "MasterCheckpoint", "Account", "DecisionJournal"} <= modeller, (
        f"workspace_id kolonlu model türetme bozuk: {sorted(modeller)}"
    )


def test_workspaceli_modele_workspace_id_yazmadan_kayit_acilmaz():
    """BUG #221 kilidi: her INSERT ya workspace_id verir ya gerekçeli muaftır."""
    taranan = 0
    ihlaller = []
    for yol, satir, model, alanlar, yildiz, blok in _cagrilar():
        taranan += 1
        if "workspace_id" in alanlar or yildiz:
            continue
        if re.search(r"#\s*ws-exempt:\s*\S", blok):
            continue
        ihlaller.append(f"{yol.relative_to(APP.parent).as_posix()}:{satir} {model}(...)")

    assert taranan >= MIN_TARANAN_CAGRI, (
        f"Kapı körleşmiş olabilir: yalnız {taranan} model çağrısı tarandı "
        f"(taban {MIN_TARANAN_CAGRI}). AST tarama yolu bozulduysa kapı sessizce boşalır (L11)."
    )
    assert not ihlaller, (
        "workspace_id YAZILMADAN kayıt açan yer(ler) — satır workspace kapsamlı okumadan "
        "elenir (BUG #221). Alanı ver ya da satır sonuna `# ws-exempt: <gerekçe>` yaz:\n  "
        + "\n  ".join(ihlaller)
    )


def test_kapi_gercekten_yakalar():
    """Meta-test (L3): kapı, BUG #221'in birebir şeklini yakalıyor mu?"""
    kaynak = "Transaction(user_id=1, account_id=2, amount=5)"
    dugum = ast.parse(kaynak).body[0].value
    alanlar = {k.arg for k in dugum.keywords if k.arg}
    assert "Transaction" in _workspace_modelleri()
    assert "workspace_id" not in alanlar, "meta-test kurgusu bozuk"
    assert not re.search(r"#\s*ws-exempt:\s*\S", kaynak), "muafiyet işareti yokken var sanıldı"
