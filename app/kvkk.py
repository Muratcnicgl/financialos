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

    # 2) Kullanıcının SAHİBİ olduğu workspace'ler.
    #
    # BUG #206 (H18): eskiden SAHİBİ olunan HER workspace siliniyordu — paylaşılan (aile)
    # workspace'i de dahil. Sonuç: aile workspace'inin sahibi hesabını silince EŞİNİN/
    # ÇOCUĞUNUN tüm finansal kayıtları da sessizce yok oluyordu (repro ile doğrulandı).
    # Bir kullanıcının kendi hesabını silmesi, BAŞKASININ verisini yok etme yetkisi vermez.
    #
    # Kural: başka üyesi olan workspace SİLİNMEZ — sahiplik devredilir (en eski üyeye,
    # önce editor sonra viewer). Yalnız kişisel/üyesiz workspace'ler silinir.
    from app.models import WorkspaceMembership, WorkspaceRole
    ws_ids: list[int] = []
    for w in db.query(Workspace).filter(Workspace.owner_user_id == user_id).all():
        diger = (db.query(WorkspaceMembership)
                 .filter(WorkspaceMembership.workspace_id == w.id,
                         WorkspaceMembership.user_id != user_id)
                 .order_by(WorkspaceMembership.id.asc()).all())
        if not diger:
            ws_ids.append(w.id)
            continue
        yeni_sahip = next((m for m in diger if m.role == WorkspaceRole.editor), diger[0])
        w.owner_user_id = yeni_sahip.user_id
        yeni_sahip.role = WorkspaceRole.owner
        silinen["workspace_devredildi"] = silinen.get("workspace_devredildi", 0) + 1
        logger.info("[kvkk] workspace %s sahipligi devredildi: %s -> %s",
                    w.id, user_id, yeni_sahip.user_id)
    db.flush()
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

    # 3) BUG #243 fix (D27): SİLİNMEYEN ama kişisel iz TAŞIYAN kayıtları anonimleştir.
    #
    # Eski hâli yalnız `user_id` kolonu olan tablolara bakıyordu; `beta_invites`'ın kolonu
    # `used_by_user_id` olduğu için kullanıcının E-POSTASI ve operatörün o kişi hakkında
    # yazdığı SERBEST NOT ("tanıdık — iş arkadaşı") silme sonrası veritabanında süresiz
    # kalıyordu → "tüm veriniz kalıcı olarak silinir" taahhüdü fiilen yanlıştı (KVKK m.7).
    # Satırın kendisi silinmez (davet KODU tekrar kullanılamamalı — işletme kaydı); yalnız
    # kişisel alanlar NULL'lanır. Hangi tablo/alan olduğu tek kaynakta: app/data_subject.KAYIT.
    from app.data_subject import anonimlestirilecekler
    from sqlalchemy import update
    for kayit in anonimlestirilecekler():
        tablo = kayit.model.__table__
        atif = "used_by_user_id" if "used_by_user_id" in tablo.c else (
            "last_user_id" if "last_user_id" in tablo.c else "user_id")
        if atif not in tablo.c:
            continue
        r = db.execute(
            update(tablo).where(tablo.c[atif] == user_id)
            .values({alan: None for alan in kayit.anonim_alanlar if alan in tablo.c})
        )
        if r.rowcount:
            silinen[f"{tablo.name}_anonimlestirildi"] = r.rowcount

    # 4) Kullanıcı satırı (varsayılan). ORM yolu için çağıran False geçer.
    if delete_user_row:
        r = db.execute(delete(User.__table__).where(User.id == user_id))
        silinen["users"] = r.rowcount

    logger.info("[kvkk] kullanici verisi silindi user_id=%s tablolar=%s", user_id, silinen)
    return silinen
