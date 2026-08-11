"""
SPA servisi — nginx'siz kurulum için (B4 / BUG #284).

NEDEN VAR:
Üretim yığınında statik dosyaları **nginx** servis eder (`deploy/nginx*.template` →
`root /usr/share/nginx/html; try_files ...`). Ama kapalı betanın ilk adımı Docker'sız
koşuluyor: makinede Docker/WSL yok ve tünel (Tailscale Funnel / Cloudflare Tunnel) TEK bir
yerel porta vekillik eder. nginx yokken o portta hem `/api/*` hem de derlenmiş arayüzün
(`frontend/dist`) bulunması gerekir; aksi hâlde davetli boş bir sayfa görür.

TASARIM KARARLARI:

1. **Varsayılan KAPALI** (`SERVE_SPA` env'i). Docker/nginx yolunda bu kod hiç devreye
   girmez — iki katman aynı işi yapıp çakışmaz ve mevcut dağıtım davranışı DEĞİŞMEZ.
2. **Açıkken FAIL-FAST**: `SERVE_SPA=1` denip `dist/index.html` yoksa uygulama **açılışta
   patlar**. Sessizce 404 servis etmek daha kötüdür: operatör "kurdum" sanır, davetli boş
   sayfa görür ve kimse nedenini bilmez (L5 — fail-closed; L2 — sessiz kabul yasak).
3. **Mount EN SONA** eklenir: `/` altındaki catch-all, kendisinden önce kayıtlı `/api/*`
   yollarını gölgeleyemez (Starlette kayıt sırasına göre eşleştirir).
4. **Kök yol (`/`) ayrıca ele alınır**: `main.py`'de `GET /` sağlık cevabı döndüren bir uç
   var ve mount'tan ÖNCE kayıtlı olduğu için onu gölgelemez. SPA modunda o uç index.html
   döndürür; sağlık kontrolü zaten `/api/health` ve `/api/ready`'dedir (BUG #247 ayrımı).
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def spa_aktif() -> bool:
    """SPA'yı uygulama mı servis edecek? Varsayılan HAYIR (nginx yolu bozulmasın)."""
    return os.getenv("SERVE_SPA", "").strip().lower() in ("1", "true", "yes")


def dist_yolu() -> Path:
    """Derlenmiş arayüzün dizini. `SPA_DIST` ile ezilebilir (repo dışı kurulum için)."""
    ham = os.getenv("SPA_DIST", "").strip()
    if ham:
        return Path(ham)
    return Path(__file__).resolve().parent.parent / "frontend" / "dist"


def index_dosyasi() -> Path:
    return dist_yolu() / "index.html"


def index_yanit() -> FileResponse:
    """Kök yolun SPA modundaki cevabı."""
    return FileResponse(index_dosyasi())


def spa_kur(app) -> bool:
    """SPA mount'unu ekler. Dönüş: eklendi mi.

    Çağrı yeri `app/main.py`'nin EN SONU olmalı — router'lardan sonra.
    """
    if not spa_aktif():
        return False

    dist = dist_yolu()
    if not (dist / "index.html").exists():
        # Fail-fast: "servis ediyorum" diyip boş sayfa döndürmek sessiz bir yalandır.
        raise RuntimeError(
            f"SERVE_SPA açık ama derlenmiş arayüz yok: {dist / 'index.html'} bulunamadı. "
            "Önce `cd frontend; npm run build` koşun ya da SPA_DIST ile doğru dizini verin."
        )

    app.mount("/", StaticFiles(directory=str(dist), html=True), name="spa")
    return True
