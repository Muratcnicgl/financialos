"""
P4 (Wave-9) — BUG #191: hukuki metinler CANLIDA ERİŞİLEMEZ durumdaydı.

Login ekranı KVKK metnine `/docs/legal/kvkk-consent-v1.md` ile bağlanıyordu; ancak
prod imajında `docs/` klasörü YOK (Dockerfile yalnız `app`, `alembic`, `scripts` kopyalar)
ve nginx SPA fallback'i bu yolu `index.html`'e düşürür. Sonuç: kullanıcı rıza verdiği
metni **okuyamıyordu** — KVKK aydınlatma yükümlülüğü fiilen karşılanmıyordu.

Bu router metinleri API üzerinden sunar (kimlik gerektirmez — rıza öncesi okunmalı).
Kaynak, denetlenen `docs/legal/` dosyalarıdır; imaja kopyalanır (Dockerfile).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/legal", tags=["legal"])

_ROOT = Path(__file__).resolve().parent.parent.parent
_LEGAL_DIR = _ROOT / "docs" / "legal"

# Yayınlanan belgeler: slug → (dosya, başlık). Slug listesi SABİT — dosya adı
# kullanıcı girdisinden gelmez (path traversal yüzeyi açılmaz).
# BUG #231 (D10): dosya adı SABİT yazılıydı ("kvkk-consent-v2.md"). Rıza sürümü
# yükseltildiğinde kullanıcıya HÂLÂ eski metin sunuluyordu — yani onay verdiği sürüm ile
# okuduğu metin ayrışıyordu. Sürüm tek kaynaktan (KVKK_CONSENT_VERSION) türetilir.
from app.routers.auth import KVKK_CONSENT_VERSION  # noqa: E402

_KVKK_DOSYA = f"kvkk-consent-{KVKK_CONSENT_VERSION}.md"

BELGELER: dict[str, tuple[str, str]] = {
    "kvkk": (_KVKK_DOSYA, "KVKK Açık Rıza Metni"),
    "gizlilik": (_KVKK_DOSYA, "Gizlilik ve Kişisel Veri Politikası"),
    "kullanim-sartlari": ("kullanim-sartlari.md", "Kullanım Şartları"),
    "veri-isleyenler": ("veri-isleyen-envanteri.md", "Veri İşleyen Envanteri"),
}


@router.get("")
def list_documents() -> dict:
    """Yayınlanan hukuki belgelerin listesi (frontend menüsü buradan beslenir)."""
    return {
        "documents": [
            {"slug": slug, "title": baslik, "url": f"/api/legal/{slug}"}
            for slug, (_, baslik) in BELGELER.items()
        ]
    }


@router.get("/{slug}")
def get_document(slug: str) -> dict:
    """Belgenin markdown içeriğini döner (frontend render eder)."""
    kayit = BELGELER.get(slug)
    if not kayit:
        raise HTTPException(status_code=404, detail="Belge bulunamadı.")
    dosya_adi, baslik = kayit
    yol = _LEGAL_DIR / dosya_adi
    if not yol.exists():
        # Dağıtım hatası (imaja kopyalanmamış) — sessizce boş metin dönmek KVKK açısından
        # daha kötüdür; net hata ver ki deploy doğrulamasında yakalansın.
        raise HTTPException(
            status_code=500,
            detail="Hukuki belge sunucuda bulunamadı (dağıtım eksik).",
        )
    return {
        "slug": slug,
        "title": baslik,
        "content": yol.read_text(encoding="utf-8"),
    }
