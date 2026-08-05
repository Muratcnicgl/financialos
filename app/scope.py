"""
M43 / ADR-036 — Workspace kapsam köprüsünün TEK KAYNAĞI (yaprak modül).

Bu modül yalnız bir contextvar + iki yardımcı taşır; hiçbir uygulama modülünü import
etmez. Router `with workspace_scope(ws_id):` bloğu içinde bir motoru çağırırsa, o motorun
sorguları `scope_expr(...)` üzerinden aktif workspace'e kapsanır; contextvar set
edilmemişse (legacy/test yolu) eski `user_id` davranışı korunur.

NEDEN AYRI MODÜL (BUG #224 / D03b):
Köprü tarihsel olarak `app/rules_engine.py` içinde tanımlıydı. `app/simulation_engine.py`
tasarım gereği rules_engine'i import ETMEZ (bağımsızlık ilkesi: gerçek DB'ye sızıntı riski
yok, mantık bağımsız yazılmıştır) — bu yüzden köprüye erişemiyor, sorgularını ham
`Model.user_id == user_id` ile kuruyordu ve aile workspace'inde KİŞİSEL manzarayı
simüle ediyordu. Köprü yaprak bir modüle taşındı: rules_engine ve simulation_engine
artık AYNI contextvar'ı, katman ihlali olmadan paylaşır. `app/database.py`'nin
circular-import kaçınmak için yaptığı lazy import da bu modülden karşılanabilir.

Geriye uyum: `rules_engine` bu isimleri re-export eder (`workspace_scope`, `_scope`,
`_active_workspace`) — mevcut ~20 import yeri değişmeden çalışır.
"""
from __future__ import annotations

import contextvars
from contextlib import contextmanager
from typing import Optional

_active_workspace: "contextvars.ContextVar[Optional[int]]" = contextvars.ContextVar(
    "rules_active_workspace_id", default=None
)


@contextmanager
def workspace_scope(workspace_id: Optional[int]):
    """Kapsam-duyarlı motor çağrılarını aktif workspace'e kapsar. None → legacy user_id."""
    token = _active_workspace.set(workspace_id)
    try:
        yield
    finally:
        _active_workspace.reset(token)


def scope_expr(model, user_id: int):
    """Aktif workspace varsa `workspace_id`, yoksa legacy `user_id` filtre ifadesi."""
    ws = _active_workspace.get()
    return (model.workspace_id == ws) if ws is not None else (model.user_id == user_id)


# rules_engine'in tarihsel adı — mevcut import'lar (`from app.rules_engine import _scope`)
# bu nesneye çözülür, tek davranış.
_scope = scope_expr
