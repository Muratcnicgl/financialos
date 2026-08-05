"""
BUG #221 onarım aracı — workspace_id=NULL kalmış kayıtları sahibinin personal
workspace'ine bağlar.

NEDEN: `execute_pending_action` handler'ları workspace bağlamı olmadan çağırıyordu; koç
yolundan yazılan satırlar `workspace_id=NULL` kaldı. Okuma tarafı workspace kapsamlı
olduğu için bu satırlar kullanıcının KENDİ listesinden/raporundan eleniyor (prod
PostgreSQL'de ayrıca RLS ile). Kod düzeltildi; bu araç ZATEN OLUŞMUŞ kayıtları onarır.

GÜVENLİK (BUG #164 dersi — yıkıcı script footgun'ı):
  * Varsayılan SALT-RAPOR. Yazma yalnız açık `--uygula` ile.
  * Sezgi YOK: her satır YALNIZCA kendi `user_id`'sinin personal workspace'ine bağlanır.
    Kullanıcının personal workspace'i yoksa ya da birden fazlaysa o satıra DOKUNULMAZ.
  * Dolu `workspace_id`'ye ASLA dokunulmaz (yalnız NULL satırlar).
  * Yazmadan önce yedek alınır (SQLite; başka dialect'te `--yedek-atla` gerekir).
  * Silme yok — yalnız UPDATE.

Kullanım:
    python -m scripts.repair_null_workspace              # rapor (yazmaz)
    python -m scripts.repair_null_workspace --uygula     # yedek al + onar
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional

from sqlalchemy import inspect, select, update
from sqlalchemy.orm import Session

from app.database import SessionLocal, engine
from app.models import Base, Workspace


def _workspaceli_modeller() -> list:
    """`workspace_id` kolonu taşıyan tüm mapper'lar (elle liste yok — şemadan türer)."""
    return [m.class_ for m in Base.registry.mappers
            if "workspace_id" in m.class_.__table__.c
            and "user_id" in m.class_.__table__.c]


def _personal_workspace_id(db: Session, user_id: int) -> Optional[int]:
    """Kullanıcının TEK personal workspace'i; yoksa ya da birden fazlaysa None (dokunma)."""
    ws = db.execute(
        select(Workspace.id).where(
            Workspace.owner_user_id == user_id,
            Workspace.is_personal.is_(True),
        ).order_by(Workspace.id.asc())
    ).scalars().all()
    return ws[0] if len(ws) == 1 else None


def tara(db: Session) -> dict:
    """{model_adi: [(satir_id, user_id, hedef_ws_id|None), ...]} — yazmaz."""
    bulgular = {}
    for model in _workspaceli_modeller():
        t = model.__table__
        satirlar = db.execute(
            select(t.c.id, t.c.user_id).where(t.c.workspace_id.is_(None))
        ).all()
        if not satirlar:
            continue
        onbellek: dict[int, Optional[int]] = {}
        kayitlar = []
        for satir_id, user_id in satirlar:
            if user_id not in onbellek:
                onbellek[user_id] = _personal_workspace_id(db, user_id) if user_id else None
            kayitlar.append((satir_id, user_id, onbellek[user_id]))
        bulgular[model.__name__] = kayitlar
    return bulgular


def _yedek_al() -> Optional[str]:
    if engine.dialect.name != "sqlite":
        print("[!] SQLite değil — yedek bu araçla alınamaz. Kendi yedeğini alıp "
              "`--yedek-atla` ile tekrar çalıştır.", file=sys.stderr)
        return None
    from scripts.backup import main as backup_main  # mevcut, testli yedek yolu
    backup_main([])
    return "alindi"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="BUG #221: workspace_id=NULL kayıtları onarır.")
    ap.add_argument("--uygula", action="store_true", help="DEĞİŞİKLİĞİ YAZ (varsayılan: yalnız rapor)")
    ap.add_argument("--yedek-atla", action="store_true", help="yedeği atla (yedeği kendin aldıysan)")
    a = ap.parse_args(argv)

    db = SessionLocal()
    try:
        bulgular = tara(db)
        if not bulgular:
            print("Temiz: workspace_id=NULL kayıt yok.")
            return 0

        onarilabilir = 0
        atlanan = 0
        print(f"{'model':<22}{'satır':>7}{'onarılabilir':>14}{'atlanan':>9}")
        for ad, kayitlar in bulgular.items():
            o = sum(1 for _, _, ws in kayitlar if ws is not None)
            s = len(kayitlar) - o
            onarilabilir += o
            atlanan += s
            print(f"{ad:<22}{len(kayitlar):>7}{o:>14}{s:>9}")
            for satir_id, user_id, ws in kayitlar:
                nitelik = f"→ ws={ws}" if ws else "ATLANIR (personal workspace yok/belirsiz)"
                print(f"    id={satir_id} user={user_id} {nitelik}")

        if not a.uygula:
            print(f"\nRAPOR MODU — hiçbir şey yazılmadı. {onarilabilir} satır onarılabilir, "
                  f"{atlanan} satır atlanır.\nUygulamak için: --uygula")
            return 0

        if not a.yedek_atla and _yedek_al() is None:
            return 2

        yazilan = 0
        for model in _workspaceli_modeller():
            kayitlar = bulgular.get(model.__name__)
            if not kayitlar:
                continue
            t = model.__table__
            for satir_id, _user_id, ws in kayitlar:
                if ws is None:
                    continue
                db.execute(
                    update(t)
                    .where(t.c.id == satir_id, t.c.workspace_id.is_(None))  # yarış koruması
                    .values(workspace_id=ws)
                )
                yazilan += 1
        db.commit()
        print(f"\nTAMAM: {yazilan} satır onarıldı, {atlanan} satıra dokunulmadı.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
