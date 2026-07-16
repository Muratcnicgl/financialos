"""
M41 (ADR-036) — Workspace izin bağımlılıkları (FastAPI Depends).

Aktif workspace `X-Workspace-Id` header'ından çözülür; yoksa kullanıcının personal
workspace'i (backfill'de yaratıldı). İzin kontrolü membership rolü üzerinden:
owner(3) > editor(2) > viewer(1). Enforcement kod seviyesinde (ADR-001 ruhu — istemciye
güvenilmez); yazma endpoint'leri `require_workspace(WorkspaceRole.editor)` ile korunur.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models import User, Workspace, WorkspaceMembership, WorkspaceRole

_ROLE_RANK = {WorkspaceRole.viewer: 1, WorkspaceRole.editor: 2, WorkspaceRole.owner: 3}


def _personal_workspace(db: Session, user: User) -> Optional[Workspace]:
    return (db.query(Workspace)
            .filter(Workspace.owner_user_id == user.id, Workspace.is_personal.is_(True))
            .order_by(Workspace.id.asc())
            .first())


def get_active_membership(
    x_workspace_id: Optional[int] = Header(default=None, alias="X-Workspace-Id"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceMembership:
    """Aktif workspace'te kullanıcının üyeliğini döner (yoksa 403/404).

    Header yoksa personal workspace'e düşer. Kullanıcı üye değilse 403.
    """
    if x_workspace_id is not None:
        workspace_id = x_workspace_id
    else:
        ws = _personal_workspace(db, user)
        if ws is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Personal workspace bulunamadı (backfill gerekli).",
            )
        workspace_id = ws.id

    membership = (db.query(WorkspaceMembership)
                  .filter(WorkspaceMembership.workspace_id == workspace_id,
                          WorkspaceMembership.user_id == user.id)
                  .first())
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu workspace'e erişiminiz yok.",
        )
    return membership


def require_workspace(min_role: WorkspaceRole):
    """Dependency factory: aktif workspace'te en az `min_role` gerektir.

    Kullanım: `membership = Depends(require_workspace(WorkspaceRole.editor))`.
    Yetersiz rolde 403. Döner: WorkspaceMembership (workspace_id + role erişimi için).
    """
    def _dep(membership: WorkspaceMembership = Depends(get_active_membership)) -> WorkspaceMembership:
        if _ROLE_RANK[membership.role] < _ROLE_RANK[min_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Bu işlem en az '{min_role.value}' rolü gerektirir "
                       f"(mevcut: '{membership.role.value}').",
            )
        return membership
    return _dep
