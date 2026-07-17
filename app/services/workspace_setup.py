"""
M62 (ADR-036/037) — Personal workspace yaratımı (tek kanonik nokta).

Her User'ın bir `is_personal` workspace'i + owner membership'i olmalı. Bu fonksiyon
register + oauth_callback akışlarında (yeni user yaratılınca) VE backfill script'inde
kullanılır → DRY, tek doğruluk. Idempotent: personal workspace zaten varsa dokunmaz.

Neden kritik (M61 R3 bulgusu + tam-proje-durum-raporu B23a): eskiden personal workspace
YALNIZ elle çalışan `create_personal_workspaces.py` ile yaratılıyordu; register akışına
bağlı değildi → 17 Tem'den sonra kaydolan her user `ws_id=None` legacy yolundan koşuyordu.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import User, Workspace, WorkspaceMembership, WorkspaceRole


def ensure_personal_workspace(db: Session, user: User, commit: bool = True) -> Workspace:
    """User için personal workspace + owner membership garanti eder (idempotent).

    commit=False: çağıran kendi transaction'ında commit eder (register akışı — user ile
    aynı commit). Döner: personal Workspace.
    """
    ws = (db.query(Workspace)
          .filter(Workspace.owner_user_id == user.id, Workspace.is_personal.is_(True))
          .order_by(Workspace.id.asc())
          .first())
    if ws is None:
        name = f"{user.name or user.email or ('user-' + str(user.id))} (Kişisel)"
        ws = Workspace(owner_user_id=user.id, name=name, is_personal=True)
        db.add(ws)
        db.flush()  # ws.id gerekli

    exists = (db.query(WorkspaceMembership)
              .filter_by(workspace_id=ws.id, user_id=user.id).first())
    if not exists:
        db.add(WorkspaceMembership(workspace_id=ws.id, user_id=user.id,
                                   role=WorkspaceRole.owner))
    if commit:
        db.commit()
        db.refresh(ws)
    return ws
