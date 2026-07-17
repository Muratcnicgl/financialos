"""
M41 (ADR-036) — Workspace CRUD + üyelik endpoint'leri.

- GET    /api/workspaces                      — kullanıcının üye olduğu workspace'ler (rol dahil)
- POST   /api/workspaces                      — yeni workspace yarat (yaratan owner olur)
- GET    /api/workspaces/{id}                  — detay + üye listesi (üye olmalı)
- DELETE /api/workspaces/{id}/members/{user_id} — üye çıkar (owner; personal/owner-self korunur)

Davet (POST /invite + join) M42'de. İzin: yazma işlemleri `require_workspace` ile kod
seviyesinde bloklanır (ADR-001 ruhu).
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import jwt

from app.serializers import UtcDateTime
from app.dependencies import get_db, get_current_user
from app.models import User, Workspace, WorkspaceMembership, WorkspaceRole
from app.workspace_deps import require_workspace, get_active_membership

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


# ============================================================
# SCHEMAS
# ============================================================

class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)


class MemberOut(BaseModel):
    user_id: int
    name: str | None = None
    email: str | None = None
    role: WorkspaceRole
    joined_at: UtcDateTime


class WorkspaceOut(BaseModel):
    id: int
    name: str
    is_personal: bool
    owner_user_id: int
    role: WorkspaceRole  # istek yapan kullanıcının bu workspace'teki rolü
    created_at: UtcDateTime


class WorkspaceDetail(WorkspaceOut):
    members: List[MemberOut]


class InviteCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    role: WorkspaceRole = WorkspaceRole.viewer


class InviteOut(BaseModel):
    invite_link: str
    email_sent: bool
    expires_in_minutes: int = 60


class JoinOut(BaseModel):
    workspace_id: int
    role: WorkspaceRole
    joined: bool  # True=yeni katıldı, False=zaten üyeydi


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("", response_model=List[WorkspaceOut])
def list_workspaces(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> List[WorkspaceOut]:
    """Kullanıcının üye olduğu tüm workspace'ler (kendi rolüyle)."""
    rows = (db.query(WorkspaceMembership, Workspace)
            .join(Workspace, Workspace.id == WorkspaceMembership.workspace_id)
            .filter(WorkspaceMembership.user_id == user.id)
            .order_by(Workspace.is_personal.desc(), Workspace.id.asc())
            .all())
    return [
        WorkspaceOut(id=ws.id, name=ws.name, is_personal=ws.is_personal,
                     owner_user_id=ws.owner_user_id, role=m.role, created_at=ws.created_at)
        for m, ws in rows
    ]


@router.post("", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
def create_workspace(
    body: WorkspaceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WorkspaceOut:
    """Yeni (paylaşımlı) workspace yarat — yaratan owner olur. is_personal=False."""
    ws = Workspace(owner_user_id=user.id, name=body.name.strip(), is_personal=False)
    db.add(ws)
    db.flush()
    db.add(WorkspaceMembership(workspace_id=ws.id, user_id=user.id, role=WorkspaceRole.owner))
    db.commit()
    db.refresh(ws)
    return WorkspaceOut(id=ws.id, name=ws.name, is_personal=ws.is_personal,
                        owner_user_id=ws.owner_user_id, role=WorkspaceRole.owner,
                        created_at=ws.created_at)


@router.get("/join", response_model=JoinOut)
def join_workspace(
    token: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> JoinOut:
    """Davet token'ı ile workspace'e katıl (davet edilen kullanıcının kendi oturumuyla).

    /{workspace_id} int-route'undan ÖNCE tanımlı olmalı (FastAPI str-path 'join'i yakalar).
    KVKK: token'daki email oturum kullanıcısının email'iyle eşleşmeli. Idempotent.
    """
    from app.services.workspace_invite import decode_invite_token
    try:
        data = decode_invite_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Davet süresi dolmuş (1 saat). Yeni davet isteyin.")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Geçersiz davet token'ı.")

    if not user.email or user.email.strip().lower() != data["email"]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Bu davet başka bir e-posta için. Davet edilen hesapla giriş yapın.",
        )
    ws = db.get(Workspace, data["workspace_id"])
    if ws is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace bulunamadı (silinmiş olabilir).")
    existing = (db.query(WorkspaceMembership)
                .filter(WorkspaceMembership.workspace_id == ws.id,
                        WorkspaceMembership.user_id == user.id)
                .first())
    if existing:
        return JoinOut(workspace_id=ws.id, role=existing.role, joined=False)
    db.add(WorkspaceMembership(workspace_id=ws.id, user_id=user.id, role=data["role"]))
    db.commit()
    return JoinOut(workspace_id=ws.id, role=data["role"], joined=True)


@router.get("/{workspace_id}", response_model=WorkspaceDetail)
def get_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WorkspaceDetail:
    """Workspace detayı + üye listesi. Yalnız üyeler görebilir."""
    membership = (db.query(WorkspaceMembership)
                  .filter(WorkspaceMembership.workspace_id == workspace_id,
                          WorkspaceMembership.user_id == user.id)
                  .first())
    if membership is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Bu workspace'e erişiminiz yok.")
    ws = db.get(Workspace, workspace_id)
    member_rows = (db.query(WorkspaceMembership, User)
                   .join(User, User.id == WorkspaceMembership.user_id)
                   .filter(WorkspaceMembership.workspace_id == workspace_id)
                   .order_by(WorkspaceMembership.id.asc())
                   .all())
    members = [MemberOut(user_id=u.id, name=u.name, email=u.email, role=m.role, joined_at=m.joined_at)
               for m, u in member_rows]
    return WorkspaceDetail(id=ws.id, name=ws.name, is_personal=ws.is_personal,
                           owner_user_id=ws.owner_user_id, role=membership.role,
                           created_at=ws.created_at, members=members)


@router.delete("/{workspace_id}/members/{target_user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    workspace_id: int,
    target_user_id: int,
    db: Session = Depends(get_db),
    membership: WorkspaceMembership = Depends(require_workspace(WorkspaceRole.owner)),
):
    """Üye çıkar — yalnız owner. Personal workspace ve owner'ın kendisi çıkarılamaz."""
    # require_workspace aktif workspace'i header'dan çözer; path'teki id ile eşleşmeli
    if membership.workspace_id != workspace_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "X-Workspace-Id header path'teki workspace ile eşleşmiyor.")
    ws = db.get(Workspace, workspace_id)
    if ws is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace bulunamadı.")
    if ws.is_personal:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Personal workspace'ten üye çıkarılamaz.")
    if target_user_id == ws.owner_user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Owner çıkarılamaz (önce sahiplik devri gerekir).")
    target = (db.query(WorkspaceMembership)
              .filter(WorkspaceMembership.workspace_id == workspace_id,
                      WorkspaceMembership.user_id == target_user_id)
              .first())
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Üye bulunamadı.")
    db.delete(target)
    db.commit()


@router.post("/{workspace_id}/invite", response_model=InviteOut, status_code=status.HTTP_201_CREATED)
def invite_member(
    workspace_id: int,
    body: InviteCreate,
    db: Session = Depends(get_db),
    membership: WorkspaceMembership = Depends(require_workspace(WorkspaceRole.owner)),
) -> InviteOut:
    """Workspace'e üye davet et (owner). Davet token'lı e-posta gönderilir; link cevapta da döner.

    Personal workspace'e davet edilemez. Owner rolüyle davet edilemez (owner tek).
    """
    from app.services.workspace_invite import create_invite_token, build_invite_link, send_invite_email

    if membership.workspace_id != workspace_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "X-Workspace-Id header path'teki workspace ile eşleşmiyor.")
    ws = db.get(Workspace, workspace_id)
    if ws is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace bulunamadı.")
    if ws.is_personal:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Personal workspace'e davet edilemez.")
    if body.role == WorkspaceRole.owner:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Owner rolüyle davet edilemez (owner tektir).")

    token = create_invite_token(workspace_id, body.email, body.role)
    link = build_invite_link(token)
    sent = send_invite_email(body.email.strip().lower(), ws.name, body.role, link)
    return InviteOut(invite_link=link, email_sent=sent)
