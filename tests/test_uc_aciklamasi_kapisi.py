"""
DOCS-008 / BUG #394 KAPISI — HER API UCUNUN BİR AÇIKLAMASI VAR.

Ölçülen (11 Eyl 2026): 125 handler'ın hepsi tag taşıyor, hiçbiri `summary=` taşımıyor
(FastAPI başlığı fonksiyon adından türetir — yeterli), **24'ü docstring'siz**: OpenAPI'de
"ne yapar" boş. Madde "endpoint meta düzensiz" diye 60+ gündür duruyordu; ölçüm sayıyı
verdi, 24 uca tek satırlık açıklama yazıldı.

Kilitlenen: `app.routes` üzerinden türetilen her API handler'ının docstring'i dolu. Liste
elle yazılmaz (L79); yeni bir uç açıklamasız gelirse kırmızı.
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="module")
def rotalar():
    # `app.routes` düz değil: FastAPI 0.141 `include_router` rotaları `_IncludedRouter`
    # altında saklar; düz bakan tarayıcı 1 uç görür (sozlesme_dondur bunu ölçmüştü).
    os.environ.setdefault("SERVE_SPA", "0")
    from scripts.sozlesme_dondur import _rotalar
    from app.main import app
    return [(yol, r) for yol, r in _rotalar(app) if yol.startswith("/api")]


def test_her_api_ucunun_aciklamasi_var(rotalar):
    assert len(rotalar) >= 100, f"yalnız {len(rotalar)} uç görüldü — tarayıcı bozuk olabilir (L45)"
    bos = sorted(f"{','.join(sorted(r.methods))} {yol}" for yol, r in rotalar
                 if not (r.endpoint.__doc__ or "").strip())
    assert bos == [], f"açıklamasız uç: {bos}"


def test_her_api_ucu_etiketli(rotalar):
    etiketsiz = sorted(yol for yol, r in rotalar if not r.tags)
    assert etiketsiz == [], f"tag'siz uç: {etiketsiz}"
