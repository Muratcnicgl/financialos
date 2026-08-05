"""
KVKK veri silme (P3.4 / H6, BUG #204) — "unutulma hakkı" DETERMİNİST çalışsın.

Önce yalnızca `db.delete(user)` çağrılıyordu ve ORM cascade'ine güveniliyordu. İki sorun:

1. 6 tablo (Envelope, WishlistItem, Goal, Feedback, DemoDataMarker, ReasoningTrace)
   `user_id` FK'si taşımasına rağmen User'da cascade ilişkisine sahip DEĞİLDİ → verisi
   olan gerçek bir kullanıcı hesabını silmeye çalışınca `FOREIGN KEY constraint failed`
   alıyordu. Rıza metninde taahhüt edilen hak FİİLEN ÇALIŞMIYORDU.
2. İlişki eklemek tek başına yetmedi: ORM'in silme SIRASI koşullara göre değişebiliyor
   (aynı test tek başına geçip toplu koşumda düşüyordu). Veri silme gibi geri alınamaz bir
   işlem "bazen çalışan" olamaz.

Çözüm: silme sırası ŞEMADAN türetilir. `metadata.sorted_tables` FK bağımlılık sırasını
verir; TERSTEN gidildiğinde çocuklar ebeveynlerden önce silinir — dialect'ten ve ORM
yapılandırmasından bağımsız, deterministik.
"""
from __future__ import annotations

import logging

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import Base, User, Workspace

logger = logging.getLogger(__name__)


def purge_user_data(db: Session, user_id: int, delete_user_row: bool = True) -> dict[str, int]:
    """Kullanıcının TÜM verisini siler. Dönüş: tablo→silinen satır sayısı.

    `delete_user_row=False`: kullanıcı SATIRI silinmez — çağıran onu ORM ile siler
    (`db.delete(user)`). Gerekçe: satırı Core-DELETE ile silmek session'daki User
    nesnesini yetim bırakır ve commit sonrası herhangi bir erişim
    `ObjectDeleted/DetachedInstanceError` fırlatır → istek 204 yerine 500 döner.

    Commit ÇAĞIRANA bırakılır: silme + audit aynı transaction'da olsun.
    """
    silinen: dict[str, int] = {}

    # 1) user_id taşıyan her tablo — FK bağımlılığının TERSİ (çocuk → ebeveyn)
    for table in reversed(Base.metadata.sorted_tables):
        if table.name in ("users", "workspaces"):
            continue
        if "user_id" in table.c:
            r = db.execute(delete(table).where(table.c.user_id == user_id))
            if r.rowcount:
                silinen[table.name] = r.rowcount

    # 2) Kullanıcının SAHİBİ olduğu workspace'ler + o workspace'lere bağlı artık satırlar
    ws_ids = [w.id for w in db.query(Workspace)
              .filter(Workspace.owner_user_id == user_id).all()]
    if ws_ids:
        for table in reversed(Base.metadata.sorted_tables):
            if table.name in ("users", "workspaces"):
                continue
            if "workspace_id" in table.c:
                r = db.execute(delete(table).where(table.c.workspace_id.in_(ws_ids)))
                if r.rowcount:
                    silinen[table.name] = silinen.get(table.name, 0) + r.rowcount
        r = db.execute(delete(Workspace.__table__).where(Workspace.id.in_(ws_ids)))
        silinen["workspaces"] = r.rowcount

    # 3) Kullanıcı satırı (varsayılan). ORM yolu için çağıran False geçer.
    if delete_user_row:
        r = db.execute(delete(User.__table__).where(User.id == user_id))
        silinen["users"] = r.rowcount

    logger.info("[kvkk] kullanici verisi silindi user_id=%s tablolar=%s", user_id, silinen)
    return silinen
