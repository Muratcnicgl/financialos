"""
M41 (ADR-036) — Workspace izin bağımlılıkları (FastAPI Depends).

Aktif workspace `X-Workspace-Id` header'ından çözülür; yoksa kullanıcının personal
workspace'i (backfill'de yaratıldı). İzin kontrolü membership rolü üzerinden:
owner(3) > editor(2) > viewer(1). Enforcement kod seviyesinde (ADR-001 ruhu — istemciye
güvenilmez); yazma endpoint'leri `require_workspace(WorkspaceRole.editor)` ile korunur.
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
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


def active_workspace_id(
    x_workspace_id: Optional[int] = Header(default=None, alias="X-Workspace-Id"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Optional[int]:
    """M43: aktif workspace_id'yi çözer (okuma/yazma scoping için). Optional[int] döner.

    Köprü-desen: header verilirse üyelik doğrulanıp o workspace_id döner; header yoksa
    personal workspace'e düşer. Personal workspace YOKSA None döner → çağıran legacy
    `user_id` filtresine düşer (backfill öncesi/test ortamı; production'da her user'ın
    personal workspace'i vardır). Header verildi ama üye değilse 403.
    """
    if x_workspace_id is not None:
        membership = (db.query(WorkspaceMembership)
                      .filter(WorkspaceMembership.workspace_id == x_workspace_id,
                              WorkspaceMembership.user_id == user.id)
                      .first())
        if membership is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu workspace'e erişiminiz yok.")
        return x_workspace_id
    ws = _personal_workspace(db, user)
    if ws is not None:
        return ws.id
    # M62 (ADR-037): personal workspace YOK. Production'da bu sessiz veri-sızma riskidir
    # (scope_filter legacy user_id'ye düşer) → fail-fast. Dev'de warning + None (legacy yol).
    from app.settings import is_production
    if is_production():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Kullanıcı {user.id} için personal workspace yok — veri izolasyonu "
                   "garanti edilemez. scripts/create_personal_workspaces.py çalıştırın.",
        )
    import logging
    logging.getLogger(__name__).warning(
        "[workspace] user %s personal workspace YOK → legacy user_id yolu (dev)", user.id)
    return None


def scope_filter(model, user_id: int, workspace_id: Optional[int]):
    """M43 köprü filtresi: workspace_id varsa ona göre, yoksa legacy user_id'ye göre.

    Kullanım: `db.query(Account).filter(scope_filter(Account, user.id, ws_id))`.
    Yeni kayıt insert'inde workspace_id de set edilmeli (workspace_id parametresiyle).
    """
    if workspace_id is not None:
        return model.workspace_id == workspace_id
    return model.user_id == user_id


def require_workspace(min_role: WorkspaceRole):
    """Dependency factory: aktif workspace'te en az `min_role` gerektir (üyelik ZORUNLU).

    Kullanım: `membership = Depends(require_workspace(WorkspaceRole.editor))`.
    Yetersiz rolde/üye değilse 403. Döner: WorkspaceMembership. Yalnız workspace-CRUD
    endpoint'lerinde (invite/remove) — genel yazma için `require_write` kullan (köprü-farkında).
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


def require_write(min_role: WorkspaceRole = WorkspaceRole.editor):
    """M63 (BUG #160): yazma endpoint'leri için KÖPRÜ-FARKINDA izin guard'ı.

    ADR-036 izin matrisi: viewer YALNIZ OKUMA. Bu guard yazma (POST/PUT/PATCH/DELETE)
    endpoint'lerinde `Depends(require_write())` olarak kullanılır.

    Köprü-desen (M43/ADR-037 ile tutarlı): aktif workspace ÇÖZÜLEMEZSE (personal ws yok =
    legacy/test yolu) izin kontrolü ATLANIR → mevcut ~900 test kırılmaz. Workspace VARSA
    üyelik + rol dayatılır: viewer → 403, editor/owner → geçer.
    """
    def _dep(
        request: Request,
        x_workspace_id: Optional[int] = Header(default=None, alias="X-Workspace-Id"),
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> None:
        # Method-farkında: okuma (GET/HEAD/OPTIONS) her role açık → router-level eklenebilir.
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return None
        if x_workspace_id is not None:
            workspace_id = x_workspace_id
        else:
            ws = _personal_workspace(db, user)
            if ws is None:
                return None  # legacy/test: workspace bağlamı yok → izin kontrolü yok (köprü)
            workspace_id = ws.id
        membership = (db.query(WorkspaceMembership)
                      .filter(WorkspaceMembership.workspace_id == workspace_id,
                              WorkspaceMembership.user_id == user.id)
                      .first())
        if membership is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu workspace'e erişiminiz yok.")
        if _ROLE_RANK[membership.role] < _ROLE_RANK[min_role]:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Bu işlem en az '{min_role.value}' rolü gerektirir (mevcut: '{membership.role.value}'). "
                "Görüntüleyici (viewer) yalnız okuyabilir.",
            )
        return None
    return _dep
