"""
M42 (ADR-036) — Workspace davet token'ı + davet e-postası.

Davet = imzalı JWT (type=workspace_invite, exp=1 saat) — sunucu-tarafı state gerektirmez
(OAuth state'in aksine; tek kullanımlık değil ama kısa ömürlü + kabul edince membership
UNIQUE constraint çift-katılımı engeller). Kabul, davet edilen kullanıcının kendi
oturumuyla (`/api/workspaces/join?token=`) yapılır — token e-posta sahibini taşır,
gerçek erişim oturum + email eşleşmesiyle doğrulanır (KVKK: opt-in kabul).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import jwt

from app.auth import _secret, _ALGO
from app.models import WorkspaceRole

_INVITE_TYPE = "workspace_invite"
_INVITE_TTL = timedelta(hours=1)


def create_invite_token(workspace_id: int, email: str, role: WorkspaceRole) -> str:
    """İmzalı davet token'ı üretir (workspace_id + email + role, 1 saat geçerli)."""
    now = datetime.now(timezone.utc)
    payload = {
        "type": _INVITE_TYPE,
        "workspace_id": workspace_id,
        "email": email.strip().lower(),
        "role": role.value,
        "iat": int(now.timestamp()),
        "exp": int((now + _INVITE_TTL).timestamp()),
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGO)


def decode_invite_token(token: str) -> dict:
    """Davet token'ını doğrular (imza+süre+tip). {workspace_id, email, role} döner.

    jwt exception'ları (ExpiredSignatureError, InvalidTokenError) fırlatır — çağıran 400'e çevirir.
    """
    payload = jwt.decode(token, _secret(), algorithms=[_ALGO])
    if payload.get("type") != _INVITE_TYPE:
        raise jwt.InvalidTokenError(f"beklenen tip '{_INVITE_TYPE}', gelen '{payload.get('type')}'")
    return {
        "workspace_id": int(payload["workspace_id"]),
        "email": payload["email"],
        "role": WorkspaceRole(payload["role"]),
    }


def build_invite_link(token: str) -> str:
    """Frontend join URL'i (FRONTEND_URL/workspaces/join?token=)."""
    base = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
    return f"{base}/workspaces/join?token={token}"


def send_invite_email(to_email: str, workspace_name: str, role: WorkspaceRole, link: str) -> bool:
    """Davet e-postasını Brevo SMTP ile gönderir (KVKK-uyumlu, açık davet metni).

    SMTP yapılandırılmamışsa False (akış bozulmaz; link yine de API cevabında döner).
    """
    from app.services.email import send_email

    subject = f"FinancialOS — '{workspace_name}' workspace daveti"
    role_tr = {"owner": "sahip", "editor": "düzenleyici", "viewer": "görüntüleyici"}[role.value]
    text = (
        f"Merhaba,\n\n"
        f"'{workspace_name}' adlı FinancialOS workspace'ine '{role_tr}' rolüyle davet edildiniz.\n"
        f"Kabul etmek için (1 saat geçerli):\n{link}\n\n"
        f"Bu daveti siz istemediyseniz görmezden gelin — hiçbir işlem yapılmaz.\n"
        f"FinancialOS"
    )
    html = (
        f"<p>Merhaba,</p>"
        f"<p><b>{workspace_name}</b> adlı FinancialOS workspace'ine "
        f"<b>{role_tr}</b> rolüyle davet edildiniz.</p>"
        f"<p><a href=\"{link}\">Daveti kabul et</a> (1 saat geçerli).</p>"
        f"<p style=\"color:#888;font-size:12px\">Bu daveti siz istemediyseniz görmezden gelin — "
        f"hiçbir işlem yapılmaz.</p>"
    )
    return send_email(to_email, subject, text, html)
