"""
GÖÇ DURUMU — canlı şema kodun gerisinde mi? (BUG #326)

NEDEN VAR (ölçülen olay, 4 Eylül 2026): kapalı beta **sabahtan beri kapalıydı**.
`app/schema_guard.py` doğru davrandı ve uygulamayı açmayı REDDETTİ (DB `e7f8a9b0c1d2`,
kod `f8a9b0c1d2e3` — BUG #318'in göçü hiç uygulanmamıştı). Yani bekçi işini yaptı; eksik
olan, göçü UYGULAYAN adımdı:

    deploy/financialos.service   (systemd)  ->  ExecStartPre=... alembic upgrade head   ✅
    scripts/deploy.sh            (Docker)   ->  entrypoint alembic upgrade head          ✅
    deploy/windows/baslat.ps1    (BETANIN GERÇEKTE KOŞTUĞU YOL)                          ❌

Adım, KULLANILMAYAN iki yolda vardı; kullanılan yolda yoktu. Sağlık görevi 10 dakikada bir
yeniden deneyip her seferinde aynı hatayla düştü ve bunu yalnız `logs/servis.log`'a yazdı —
yani arıza gürültülüydü ama GÖRÜNMEZDİ. (L64'ün sınıfı: bir kurulum adımı yalnız bir
yapılandırmada yaşıyorsa, kullanılan yol onu taşımaz.)

BU BETİK KARAR VERMEZ, DURUM BİLDİRİR. Çıkış kodları:
    0  şema güncel — ya da `alembic_version` yok (test/`create_all` yolu, kilitlemeyiz)
    10 GÖÇ BEKLİYOR — çağıran taraf yedek alıp `alembic upgrade head` koşmalı
    1  durum ÖLÇÜLEMEDİ (alembic okunamadı vb.) — bilinmeyen, "güncel" DEĞİLDİR (L45)

Mantık `app/schema_guard.py`ten gelir; İKİNCİ BİR KOPYA YAZILMAZ — iki sürüm okuyucusu
zamanla ayrışır ve hangisinin doğru olduğu ancak canlıda anlaşılır (L21).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schema_guard import _db_surumu, _kod_head  # noqa: E402

GUNCEL = 0
GOC_BEKLIYOR = 10
OLCULEMEDI = 1


def durum(engine=None) -> tuple[int, str]:
    """(çıkış kodu, insan-okur mesaj). Saf: yazmaz, göç çalıştırmaz."""
    if engine is None:
        from app.database import engine as varsayilan
        engine = varsayilan

    beklenen = _kod_head()
    if beklenen is None:
        return OLCULEMEDI, "kod head'i okunamadi (alembic yapilandirmasi?)"

    try:
        mevcut = _db_surumu(engine)
    except Exception as e:  # noqa: BLE001 — sebebi ne olursa olsun BİLİNMİYOR demektir
        return OLCULEMEDI, f"db surumu okunamadi: {type(e).__name__}: {e}"

    if mevcut is None:
        return GUNCEL, "alembic_version yok (test/create_all yolu) — atlandi"
    if mevcut == beklenen:
        return GUNCEL, f"guncel: {mevcut}"
    return GOC_BEKLIYOR, f"GOC BEKLIYOR: db={mevcut} kod={beklenen}"


def main() -> int:
    kod, mesaj = durum()
    print(f"[goc_durumu] {mesaj}")
    return kod


if __name__ == "__main__":
    raise SystemExit(main())
