"""
Beta geri bildirim TRİYAJI (P7 / H15, BUG #209) — operatör aracı.

Sorun: FEAT-033 widget'ı geri bildirimi topluyordu ama **kimseye ulaşmıyordu**.
`GET /api/feedback` yalnız kullanıcının KENDİ kayıtlarını döndürüyor; operatörün
görebileceği bir yol yoktu. Beta kullanıcısı "koç çöktü" diye yazar, kayıt DB'de kalır,
geliştirici sunucuya elle SQL atmadıkça haberdar olmaz. P7 çıkış kapısındaki
"geri bildirimler triyajlı" ölçütü bu yüzden ölçülemezdi.

Ek olarak hata kayıtları (BUG #195) da burada özetlenir: kullanıcının bildirdiği sorun
ile sistemin gördüğü hata YAN YANA olmalı.

Kullanım (sunucuda):
    python -m scripts.beta_triage                 # açık geri bildirim + son hatalar
    python -m scripts.beta_triage --tumu          # kapatılmışlar dahil
    python -m scripts.beta_triage --kapat 12 --not "duzeltildi: BUG #210"

GİZLİLİK: kullanıcı e-postası MASKELENİR (or***@site.com). Operatörün kimliği bilmesi
gerekiyorsa user_id ile DB'den bakabilir; rutin triyajda tam adres gerekmez.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.models import Feedback, ErrorLog, User  # noqa: E402
from app.services.email import _mask  # noqa: E402

_KIND_ETIKET = {"sikayet": "ŞİKÂYET", "istek": "İSTEK", "oneri": "ÖNERİ"}


def _yazdir_geri_bildirim(db, tumu: bool) -> int:
    q = db.query(Feedback).order_by(Feedback.created_at.desc())
    if not tumu:
        q = q.filter(Feedback.status == "new")
    kayitlar = q.all()
    print(f"\n=== GERİ BİLDİRİM ({'tümü' if tumu else 'açık'}) — {len(kayitlar)} kayıt ===")
    for f in kayitlar:
        u = db.get(User, f.user_id)
        kim = _mask(u.email) if (u and u.email) else f"user#{f.user_id}"
        etiket = _KIND_ETIKET.get(f.kind, f.kind.upper())
        print(f"\n[#{f.id}] {etiket} · {kim} · {f.created_at:%Y-%m-%d %H:%M} · {f.status}")
        print(f"    {f.message.strip()[:400]}")
    if not kayitlar:
        print("  (yeni geri bildirim yok)")
    return len(kayitlar)


def _yazdir_hatalar(db, gun: int = 7) -> int:
    esik = datetime.utcnow() - timedelta(days=gun)
    kayitlar = (db.query(ErrorLog)
                .filter(ErrorLog.last_seen_at >= esik)
                .order_by(ErrorLog.occurrence_count.desc()).all())
    print(f"\n=== SİSTEM HATALARI (son {gun} gün) — {len(kayitlar)} grup ===")
    for e in kayitlar:
        print(f"\n[{e.occurrence_count}x] {e.error_type} · {e.method} {e.path} "
              f"· son: {e.last_seen_at:%Y-%m-%d %H:%M}")
        print(f"    {(e.message or '')[:200]}")
    if not kayitlar:
        print("  (kayıtlı hata yok)")
    return len(kayitlar)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Beta geri bildirim triyajı")
    ap.add_argument("--tumu", action="store_true", help="Kapatılmış kayıtları da göster")
    ap.add_argument("--kapat", type=int, default=None, metavar="ID", help="Kaydı kapat")
    ap.add_argument("--not", dest="notu", default=None, help="Kapatma notu")
    ap.add_argument("--gun", type=int, default=7, help="Hata özeti kaç günlük")
    args = ap.parse_args(argv)

    db = SessionLocal()
    try:
        if args.kapat is not None:
            f = db.get(Feedback, args.kapat)
            if not f:
                print(f"#{args.kapat} bulunamadı")
                return 1
            f.status = "closed"
            if args.notu:
                f.message = f"{f.message}\n\n[operatör notu] {args.notu}"
            db.commit()
            print(f"#{args.kapat} kapatıldı.")
            return 0

        n_fb = _yazdir_geri_bildirim(db, args.tumu)
        n_err = _yazdir_hatalar(db, args.gun)
        print(f"\nÖZET: {n_fb} geri bildirim · {n_err} hata grubu")
        print("Kapatmak için: python -m scripts.beta_triage --kapat <ID> --not \"...\"")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
