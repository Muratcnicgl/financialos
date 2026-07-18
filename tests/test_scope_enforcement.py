"""
M70 (Wave-5, IMPROVEMENT #029) — Scope-filtre zorunluluğu (regresyon kilidi).

Gerekçe (tam-proje-durum-raporu RISK #2 / §B23a-b): workspace izolasyonunun TEK koruması
uygulama katmanı `scope_filter`/`_scope`. Yeni bir endpoint scoped-model'i düz `user_id` ile
filtrelerse workspace verisi **sessizce sızar** (derleme/test hatası YOK). Bu test o boşluğu
kapatır: scoped-model'in her `user_id ==` karşılaştırması ya `scope_filter`/`_scope` içinden
geçmeli ya da açık `# scope-exempt: <sebep>` ile işaretlenmeli. Aksi halde TEST KIRILIR.

Kapsam: app/routers/*.py + app/rules_engine.py + app/goal_engine.py + app/debt_strategy.py.
(M72: goal_engine/debt_strategy eklendi — debt_freedom goal'lerindeki Account.user_id kaçağı
bu iki dosya taranmadığı için M70'te görülmemişti; kör nokta kapandı.) Koç/kişisel modeller
(workspace_id'siz) kapsam dışı — yalnız ADR-036 workspace-scoped 12 model denetlenir.
"""
from __future__ import annotations

import re
from pathlib import Path

# ADR-036 workspace-scoped modeller (workspace_id taşıyan) — bunların user_id filtresi scope'lanmalı
SCOPED_MODELS = {
    "Account", "Transaction", "PersonalDebt", "RecurringIncome", "RecurringExpense",
    "MasterCheckpoint", "PendingAction", "NetWorthSnapshot", "Envelope", "WishlistItem",
    "Goal", "DecisionJournal",
}

_ROOT = Path(__file__).resolve().parent.parent
_TARGETS = list((_ROOT / "app" / "routers").glob("*.py")) + [
    _ROOT / "app" / "rules_engine.py",
    _ROOT / "app" / "goal_engine.py",     # M72: debt_freedom Account kaçağı buradaydı
    _ROOT / "app" / "debt_strategy.py",   # M72: collect_debts kaçağı buradaydı
    _ROOT / "app" / "coach_insights.py",  # M73: nightly batch extractor'ları scoped model okur
]

# `<Model>.user_id ==` (models. öneki opsiyonel)
_PATTERN = re.compile(r"\b(?:models\.)?([A-Z][A-Za-z_]+)\.user_id\s*==")


def _violations() -> list[str]:
    out = []
    for f in _TARGETS:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for m in _PATTERN.finditer(line):
                model = m.group(1)
                if model not in SCOPED_MODELS:
                    continue
                # İzin: scope_filter/_scope içinden VEYA açık exempt yorumu
                if "scope_filter" in line or "_scope(" in line:
                    continue
                if "# scope-exempt" in line:
                    continue
                out.append(f"{f.relative_to(_ROOT).as_posix()}:{i}: {model}.user_id (scope'suz) → {line.strip()}")
    return out


def test_scoped_modeller_scope_filtresiz_user_id_kullanmaz():
    """Scoped-model'in her user_id filtresi scope_filter/_scope veya # scope-exempt olmalı."""
    v = _violations()
    assert not v, (
        "Scope'suz user_id filtresi (workspace sızma riski) — scope_filter/_scope kullan "
        "veya '# scope-exempt: <sebep>' ekle:\n" + "\n".join(v)
    )


def test_scope_helper_var():
    """Köprü helper'ları mevcut (regresyon)."""
    from app.workspace_deps import scope_filter, require_write  # noqa: F401
    from app.rules_engine import _scope, workspace_scope  # noqa: F401
