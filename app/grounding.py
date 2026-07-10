"""
Grounding Check — LLM çıktı doğrulama (Kalite serüveni LLM-003).

DEVRİMSEL ADIM / VİZYON: Kök vizyonun "kusursuzluk, sıfır hata, VARSAYIM YASAK" mandatını
kod seviyesinde enforce eder. "Rules Engine karar verir, LLM açıklar" ilkesinin doğrulama
katmanı: koçun cevabında geçen HER TL tutarı, deterministik cockpit dict'indeki bir değere
izlenebilir olmalı. İzlenemeyen tutar = potansiyel "silent hallucination" (2026 agentic-finans
başarısızlık modu) → işaretlenir, güven düşürülür.

Bu bir UYARI sinyalidir, sert blok değil (koç meşru türev sayılar üretebilir); amaç şeffaflık.
Saf/deterministik — LLM/ağ gerektirmez, birim-test edilebilir.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

# "42.100,50 TL" / "268 TL" / "1.234 TL" — TL etiketli tutarları yakalar (TR sayı formatı).
# TL etiketi zorunlu: yalnızca koçun açıkça FİNANSAL tutar olarak öne sürdüğü sayılar denetlenir
# (yıl/gün/yüzde gibi sayılar yanlış-pozitif üretmesin).
_TL_NUM_RE = re.compile(
    r"(?P<num>\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)\s*TL",
    re.IGNORECASE,
)


def _to_float_tr(token: str) -> float:
    """TR formatlı sayı ('31.342,86') -> float. Nokta binlik, virgül ondalık."""
    return float(token.replace(".", "").replace(",", "."))


def _collect_numeric(obj: Any, out: List[float]) -> None:
    """cockpit dict'indeki tüm sayısal yaprakları topla (recursive)."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_numeric(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect_numeric(v, out)


def check_grounding(
    reply: str,
    cockpit: Dict[str, Any],
    *,
    min_magnitude: float = 100.0,
    rel_tol: float = 0.02,
    abs_tol: float = 1.0,
) -> Dict[str, Any]:
    """
    Koç cevabındaki TL tutarlarını cockpit değerleriyle karşılaştır.

    Dönen:
        {
          "ok": bool,               # tüm TL tutarları izlenebilir mi
          "checked": int,           # denetlenen TL tutarı sayısı
          "unverified": [float],    # cockpit'te karşılığı bulunamayan tutarlar
        }

    min_magnitude altındaki tutarlar atlanır (küçük yuvarlamalar/gürültü).
    Eşleşme: mutlak değer, rel_tol veya abs_tol toleransıyla herhangi bir cockpit değerine yakın.
    """
    allowed_raw: List[float] = []
    _collect_numeric(cockpit, allowed_raw)
    allowed = {round(abs(v), 2) for v in allowed_raw}

    unverified: List[float] = []
    checked = 0
    for m in _TL_NUM_RE.finditer(reply):
        try:
            val = abs(_to_float_tr(m.group("num")))
        except ValueError:
            continue
        if val < min_magnitude:
            continue
        checked += 1
        matched = any(abs(val - a) <= max(abs_tol, rel_tol * a) for a in allowed)
        if not matched:
            unverified.append(round(val, 2))

    return {"ok": not unverified, "checked": checked, "unverified": unverified}
