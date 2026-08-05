"""
Kapalı beta davet kodu üretici (P7 / BUG #199) — operatör aracı.

Kullanım:
    python -m scripts.beta_invite --note "Ali (is arkadasi)"
    python -m scripts.beta_invite --email ali@example.com --note "Ali" --gun 14
    python -m scripts.beta_invite --list

Kod tek kullanımlıktır. `--email` verilirse YALNIZ o adres kullanabilir (kod paylaşılsa
bile başkası kayıt olamaz). Kodlar hiçbir log'a yazılmaz; yalnız burada ekrana basılır.

⚠️ GOOGLE/GITHUB ile girecek davetliler için `--email` ZORUNLU (BUG #226 / D05):
OAuth akışında kod girilecek bir alan yoktur, kapı e-posta eşleşmesiyle çalışır.
E-postasız (yalnız-kod) davetler OAuth yolunu AÇMAZ — davetliye sağlayıcı hesabının
adresini sor ve daveti o adrese aç.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal  # noqa: E402
from app.beta_access import davet_olustur, registration_mode  # noqa: E402
from app.models import BetaInvite  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Kapalı beta davet kodu")
    ap.add_argument("--email", default=None, help="Yalnız bu adres kullanabilsin (önerilir)")
    ap.add_argument("--note", default=None, help="Operatör notu (kimin için)")
    ap.add_argument("--gun", type=int, default=30, help="Geçerlilik (gün), 0 = süresiz")
    ap.add_argument("--list", action="store_true", help="Mevcut davetleri listele")
    args = ap.parse_args(argv)

    db = SessionLocal()
    try:
        print(f"Kayit modu: {registration_mode()}")
        if args.list:
            for d in db.query(BetaInvite).order_by(BetaInvite.id.desc()).all():
                durum = "KULLANILDI" if d.used_at else "bekliyor"
                print(f"  #{d.id} [{durum}] {d.code}  {d.email or '(herkes)'}  {d.note or ''}")
            return 0

        d = davet_olustur(db, email=args.email, note=args.note,
                          gecerlilik_gun=args.gun or None)
        print("\nDAVET KODU (tek kullanimlik):")
        print(f"  {d.code}")
        if d.email:
            print(f"  yalniz: {d.email}")
        if d.expires_at:
            print(f"  gecerlilik: {d.expires_at.date()}")
        print("\nKullanicinin kayit ekraninda bu kodu girmesi gerekir.")
        if d.email:
            print("  (Google/GitHub ile girecekse kod gerekmez — davet adresi eslesir.)")
        else:
            print("  UYARI: --email verilmedi -> bu davet GOOGLE/GITHUB girisinde CALISMAZ")
            print("         (OAuth kapisi e-posta eslesmesiyle calisir, BUG #226).")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
