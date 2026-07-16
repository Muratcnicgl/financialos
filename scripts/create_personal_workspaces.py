"""
M40 (ADR-036) — Geriye-uyum backfill: her User için bir "personal" workspace yaratır
ve o kullanıcının tüm finansal-defter kayıtlarını (12 tablo) o workspace'e taşır.

Akış:
1. Backup (scripts.backup) — canlı veri güvenliği.
2. Her User için: personal workspace yoksa yarat (is_personal=True, owner=kendisi) +
   owner rolü membership.
3. O user'ın workspace_id'si NULL olan tüm scoped satırlarını personal workspace'e ata.
4. Doğrula: kalan NULL workspace_id (scoped tablolarda) 0 olmalı.

Idempotent: personal workspace zaten varsa yeniden yaratmaz; workspace_id dolu satırlara
dokunmaz. NOT NULL'a çevirme migration'ı bu backfill BAŞARIYLA koştuktan SONRA yapılır
(ayrı migration; canlı DB'de önce bu script). Goal.user_id NULL olabilir (workspace-siz
global hedef) → bu satırlar atlanır, uyarı basılır.
"""
from __future__ import annotations

import sys

from sqlalchemy import update

from app.database import SessionLocal
from app.models import (
    User, Workspace, WorkspaceMembership, WorkspaceRole,
    Account, RecurringIncome, RecurringExpense, Envelope, WishlistItem,
    Transaction, PersonalDebt, MasterCheckpoint, PendingAction,
    NetWorthSnapshot, Goal, DecisionJournal,
)

# workspace_id + user_id taşıyan scoped modeller (ADR-036 kapsamı)
_SCOPED_MODELS = [
    Account, RecurringIncome, RecurringExpense, Envelope, WishlistItem,
    Transaction, PersonalDebt, MasterCheckpoint, PendingAction,
    NetWorthSnapshot, Goal, DecisionJournal,
]


def _get_or_create_personal_workspace(db, user: User) -> Workspace:
    ws = (db.query(Workspace)
          .filter(Workspace.owner_user_id == user.id, Workspace.is_personal.is_(True))
          .first())
    if ws:
        return ws
    name = f"{user.name or user.email or ('user-' + str(user.id))} (Kişisel)"
    ws = Workspace(owner_user_id=user.id, name=name, is_personal=True)
    db.add(ws)
    db.flush()  # ws.id gerekli
    # owner membership (idempotent: UNIQUE(workspace_id,user_id))
    exists = (db.query(WorkspaceMembership)
              .filter_by(workspace_id=ws.id, user_id=user.id).first())
    if not exists:
        db.add(WorkspaceMembership(workspace_id=ws.id, user_id=user.id,
                                   role=WorkspaceRole.owner))
    return ws


def run(db) -> dict:
    """Backfill'i verilen session üzerinde koşar (test edilebilir). İstatistik döner."""
    stats = {"users": 0, "workspaces_created": 0, "rows_assigned": 0, "goals_null_user_skipped": 0}
    users = db.query(User).all()
    stats["users"] = len(users)
    for user in users:
        had = (db.query(Workspace)
               .filter(Workspace.owner_user_id == user.id, Workspace.is_personal.is_(True))
               .first())
        ws = _get_or_create_personal_workspace(db, user)
        if not had:
            stats["workspaces_created"] += 1
        for model in _SCOPED_MODELS:
            res = db.execute(
                update(model)
                .where(model.user_id == user.id, model.workspace_id.is_(None))
                .values(workspace_id=ws.id)
            )
            stats["rows_assigned"] += res.rowcount or 0
    db.commit()
    # Goal.user_id NULL olan global hedefler beklenen istisna (workspace'siz) — atlanır
    stats["goals_null_user_skipped"] = db.query(Goal).filter(
        Goal.workspace_id.is_(None), Goal.user_id.is_(None)).count()
    # Doğrulama: user_id dolu ama workspace_id NULL kalan scoped satır OLMAMALI
    for model in _SCOPED_MODELS:
        remaining = (db.query(model)
                     .filter(model.workspace_id.is_(None), model.user_id.isnot(None))
                     .count())
        if remaining:
            print(f"UYARI: {model.__tablename__} — {remaining} satır hâlâ workspace_id NULL (user_id dolu)")
    return stats


def main() -> int:
    # 1) Backup
    try:
        from scripts.backup import backup
        backup()
        print("Backup alındı.")
    except Exception as e:  # noqa: BLE001
        print(f"UYARI: backup alınamadı ({e}) — devam ediliyor (test/CI olabilir).")

    db = SessionLocal()
    try:
        stats = run(db)
        print(f"OK: {stats['users']} user, {stats['workspaces_created']} personal workspace yaratıldı, "
              f"{stats['rows_assigned']} satır atandı, {stats['goals_null_user_skipped']} global-goal atlandı.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
