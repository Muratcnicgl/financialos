"""
İstek gövdesi boyut sınırı — uygulama katmanı savunması (BUG #213 / P2.9).

NEDEN (ölçülen boşluk): `deploy/nginx.conf.template` içinde `client_max_body_size 1m`
vardı ve tek savunma buydu. Bu üç durumda hiçbir koruma bırakmıyor:

1. Uygulamaya ters vekil ATLANARAK erişilirse (docker ağı içinden, compose portu
   dışarı açılırsa, nginx'siz bir kurulum, yerel geliştirme).
2. nginx yapılandırması değişir/yeniden yazılırsa (tek satırlık sessiz regresyon —
   uygulama tarafında bunu yakalayan hiçbir test yoktu).
3. Chunked transfer-encoding: `Content-Length` başlığı hiç gelmez; boyut ancak
   gövde AKARKEN sayılarak bilinir.

İki katmanlı savunma projenin yerleşik deseni (ADR-008). Sınır burada da uygulanır ve
**testle kilitlenir** — böylece dış yapılandırmaya bağımlı olmaktan çıkar.

DAVRANIŞ: `Content-Length` sınırı aşıyorsa gövde HİÇ okunmadan 413 döner (ucuz yol).
Başlık yoksa gövde parça parça sayılır ve sınır aşıldığı anda kesilir — saldırgan
sınırsız bayt akıtarak belleği/CPU'yu tüketemez.

SINIR: `MAX_REQUEST_BODY_BYTES` (varsayılan 1 MiB — nginx'teki `1m` ile bilinçli olarak
aynı; iki katman aynı sözü verir). Finansal veri girişi için fazlasıyla yeterli:
en büyük gerçek gövde koç mesajıdır (4000 karakter, ChatRequest).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

VARSAYILAN_AZAMI_BAYT = 1 * 1024 * 1024  # 1 MiB


class GovdeCokBuyuk(Exception):
    """Gövde sınırı aşıldı — 413'e çevrilir (500 DEĞİL, beklenen bir durum)."""

    def __init__(self, azami_bayt: int) -> None:
        self.azami_bayt = azami_bayt
        super().__init__(f"istek gövdesi {azami_bayt} baytı aştı")


def azami_govde_bayt() -> int:
    """Sınırı env'den okur. Geçersiz/0/negatif değer varsayılana düşer (fail-safe).

    Sınırı KAPATMA yolu bilinçli olarak yoktur: "0 = sınırsız" gibi bir kaçış,
    yanlış bir env değeriyle korumanın sessizce ölmesi demektir.
    """
    ham = os.getenv("MAX_REQUEST_BODY_BYTES", "").strip()
    if not ham:
        return VARSAYILAN_AZAMI_BAYT
    try:
        deger = int(ham)
    except ValueError:
        logger.warning("[govde-limiti] MAX_REQUEST_BODY_BYTES geçersiz (%r) — varsayılana düşüldü", ham)
        return VARSAYILAN_AZAMI_BAYT
    if deger <= 0:
        logger.warning("[govde-limiti] MAX_REQUEST_BODY_BYTES <= 0 (%s) — varsayılana düşüldü", deger)
        return VARSAYILAN_AZAMI_BAYT
    return deger


def _icerik_uzunlugu(scope: Scope) -> Optional[int]:
    ham = Headers(scope=scope).get("content-length")
    if ham is None:
        return None
    try:
        return int(ham)
    except ValueError:
        return None


class GovdeBoyutuMiddleware:
    """Saf ASGI middleware — gövdeyi akarken sayar (BaseHTTPMiddleware gövdeyi tamponlar)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        azami = azami_govde_bayt()   # her istekte okunur → env testte değiştirilebilir

        uzunluk = _icerik_uzunlugu(scope)
        if uzunluk is not None and uzunluk > azami:
            return await self._reddet(send, azami)

        okunan = 0

        async def _sayan_receive() -> Message:
            nonlocal okunan
            mesaj = await receive()
            if mesaj["type"] == "http.request":
                okunan += len(mesaj.get("body", b"") or b"")
                if okunan > azami:
                    # Chunked / Content-Length'i yalan söyleyen istemci: akış burada kesilir.
                    raise GovdeCokBuyuk(azami)
            return mesaj

        await self.app(scope, _sayan_receive, send)

    @staticmethod
    async def _reddet(send: Send, azami: int) -> None:
        govde = (
            b'{"detail":"Istek govdesi cok buyuk. Azami '
            + str(azami).encode()
            + b' bayt."}'
        )
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(govde)).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": govde})
