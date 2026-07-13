"""
W3-039 (M20) — Canlı DB master checkpoint'lerine is_system=True uygular.

Bağlam: migration 26a17fda5b32 is_system kolonunu ekledi; veri-adımı `WHERE title LIKE 'MC%'`
kullandığı için canlı DB (MC-öneksiz başlıklar) 0 satır işaretlendi. Bu script eksik
veri-flag'i güvenli uygular: önce backup, sonra çekirdek master checkpoint'leri per-row
(explicit id, narrow) is_system=True yapar, doğrular.

Güvenlik: yalnız BEKLENEN çekirdek master set (tek-kullanıcı, ad-hoc yok) işaretlenir.
Beklenmedik durum (fazla/eksik satır, is_system zaten set) → durur, hiçbir şey değiştirmez.
Idempotent (tekrar → 0 değişiklik). Geri alma: backup restore veya is_system=False.
"""
from __future__ import annotations

import sys

from app.database import SessionLocal
from app.models import MasterCheckpoint

# Canlı DB'deki çekirdek Master Checkpoint başlıkları (MC1-MC8, R3 ile doğrulandı 14 Tem)
_EXPECTED_TITLES = {
    "Emanet TLY Dokunulmaz", "TLY Kaldirac Stratejisi", "Ziraat Kart Dongusu",
    "Golge Muhasebe", "Dalkavukluk Yasak", "Varsayim Yasagi",
    "Efe Kredi Payi Takvimi", "Hayatta Kalma > Yatirim",
}


def main() -> int:
    db = SessionLocal()
    try:
        rows = db.query(MasterCheckpoint).all()
        titles = {r.title for r in rows}
        # Güvenlik: yalnız beklenen çekirdek set varsa uygula (ad-hoc checkpoint yoksa)
        unexpected = titles - _EXPECTED_TITLES
        if unexpected:
            print(f"DURDU: beklenmeyen checkpoint(ler) var, elle incele: {unexpected}")
            return 1
        changed = 0
        for r in rows:
            if not r.is_system:
                r.is_system = True  # per-row ORM (explicit, narrow)
                changed += 1
        db.commit()
        after = db.query(MasterCheckpoint).all()
        flagged = sum(1 for r in after if r.is_system)
        print(f"OK: {changed} checkpoint is_system=True yapildi. Toplam is_system: {flagged}/{len(after)}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
