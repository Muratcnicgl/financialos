"""
Kategori endpoint'leri — BUG #264 / ADR-046 (P3.5.3, H4 kuyruğu).

- GET    /api/categories            - Defterin kategori seti (varsayılan: gizliler hariç)
- POST   /api/categories            - Yeni kategori
- PATCH  /api/categories/{id}       - Ad / kart varsayılanı / gizli
- DELETE /api/categories/{id}       - Sil (kullanılmışsa `hedef` slug'a TAŞI = birleştir)

Kararın kendisi burada DEĞİL: "bu kategori kart varsayılanı mı", "sistem kategorisi mi"
sorularının tek kaynağı `app/category_rules.py`. Bu router yalnız kaydı yönetir.

`require_write` UÇ BAZINDA uygulanır, router seviyesinde DEĞİL (BUG #262 dersi: router
seviyesindeki yazma kapısı okuma uçlarını da kilitliyordu → `viewer` üye 403 alıyordu).
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.category_rules import normalize
from app.dependencies import get_db, get_current_user
from app.models import Category, Envelope, Transaction, User
from app.serializers import UtcDateTime
from app.workspace_deps import active_workspace_id, require_write, scope_filter

router = APIRouter(prefix="/api/categories", tags=["categories"])


class CategoryCreate(BaseModel):
    ad: str = Field(..., min_length=1, max_length=50)
    kart_varsayilani: bool = False


class CategoryUpdate(BaseModel):
    ad: Optional[str] = Field(None, min_length=1, max_length=50)
    kart_varsayilani: Optional[bool] = None
    gizli: Optional[bool] = None


class CategoryOut(BaseModel):
    id: int
    slug: str
    ad: str
    kart_varsayilani: bool
    sistem: bool
    gizli: bool
    created_at: Optional[UtcDateTime] = None

    model_config = {"from_attributes": True}


def _bul(db: Session, kategori_id: int, user: User, ws_id: Optional[int]) -> Category:
    kayit = db.query(Category).filter(
        Category.id == kategori_id, scope_filter(Category, user.id, ws_id),
    ).first()
    if not kayit:
        raise HTTPException(404, f"Kategori bulunamadi (id={kategori_id})")
    return kayit


def _kullanim_sayisi(db: Session, slug: str, user: User, ws_id: Optional[int]) -> int:
    """Bu kategoriyle kaç işlem var? (silme akışının 'taşı' kararını bu belirler)"""
    return db.query(Transaction).filter(
        scope_filter(Transaction, user.id, ws_id), Transaction.category == slug,
    ).count()


@router.get("", response_model=List[CategoryOut])
def list_categories(
    tumu: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),
) -> List[Category]:
    """Defterin kategorileri. `tumu=true` gizlenenleri de getirir (ayar ekranı için)."""
    q = db.query(Category).filter(scope_filter(Category, user.id, ws_id))
    if not tumu:
        q = q.filter(Category.gizli.is_(False))
    return q.order_by(Category.sistem, Category.ad).all()


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_write())])
def create_category(
    payload: CategoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),
) -> Category:
    """Yeni kategori. Slug addan türetilir; aynı slug varsa 409 (gizliyse geri açılır)."""
    slug = normalize(payload.ad).strip()
    if not slug:
        raise HTTPException(422, "Kategori adı normalize edilince boş kaldı.")
    mevcut = db.query(Category).filter(
        scope_filter(Category, user.id, ws_id), Category.slug == slug,
    ).first()
    if mevcut:
        if mevcut.gizli:
            # Gizlenmiş kategoriyi yeniden eklemek = geri açmak. Geçmiş kayıtlar zaten
            # bu slug'a bağlı olduğundan yeni satır açmak veriyi ikiye bölerdi.
            mevcut.gizli = False
            mevcut.ad = payload.ad.strip()
            mevcut.kart_varsayilani = payload.kart_varsayilani
            db.commit()
            db.refresh(mevcut)
            return mevcut
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail=f"'{slug}' kategorisi zaten var (id={mevcut.id}).")
    kayit = Category(
        user_id=user.id, workspace_id=ws_id, slug=slug, ad=payload.ad.strip(),
        kart_varsayilani=payload.kart_varsayilani, sistem=False,
    )
    db.add(kayit)
    db.commit()
    db.refresh(kayit)
    return kayit


@router.patch("/{kategori_id}", response_model=CategoryOut,
              dependencies=[Depends(require_write())])
def update_category(
    kategori_id: int,
    payload: CategoryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),
) -> Category:
    """Ad / kart varsayılanı / gizlilik. Sistem kategorisi yeniden adlandırılamaz.

    `slug` DEĞİŞMEZ: geçmiş işlemler ona bağlı. Kullanıcı görünen adı değiştirir.
    """
    kayit = _bul(db, kategori_id, user, ws_id)
    alanlar = payload.model_dump(exclude_unset=True)

    if kayit.sistem and ("ad" in alanlar or "kart_varsayilani" in alanlar):
        # Muhasebe kategorisi (transfer/borç ödeme/kredi taksiti): anlamı koda bağlı,
        # kullanıcı adını değiştiremez. Gizleme serbest (listeyi temizleyebilir).
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"'{kayit.slug}' bir sistem kategorisidir; adı ve kart varsayılanı değiştirilemez.",
        )

    for k, v in alanlar.items():
        setattr(kayit, k, v.strip() if k == "ad" else v)
    db.commit()
    db.refresh(kayit)
    return kayit


@router.delete("/{kategori_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_write())])
def delete_category(
    kategori_id: int,
    hedef: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),
):
    """Sil. Kullanılmışsa `hedef` slug ZORUNLU — işlemler oraya taşınır (birleştirme).

    Sektör deseni (Actual Budget): kullanılmış kategori silinirken kullanıcı hedef seçer ve
    kayıtlar taşınır. Hedefsiz silme, geçmiş işlemleri kategorisiz bırakırdı — sessiz veri
    kaybı (L2). Sistem kategorisi hiç silinemez; onun için `gizli` vardır.
    """
    kayit = _bul(db, kategori_id, user, ws_id)
    if kayit.sistem:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"'{kayit.slug}' bir sistem kategorisidir; silinemez (gizleyebilirsiniz).",
        )

    kullanim = _kullanim_sayisi(db, kayit.slug, user, ws_id)
    if kullanim:
        if not hedef:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=(f"'{kayit.slug}' {kullanim} işlemde kullanılıyor. Silmek için "
                        f"işlemlerin taşınacağı kategoriyi `hedef` ile belirtin."),
            )
        hedef_slug = normalize(hedef).strip()
        if hedef_slug == kayit.slug:
            raise HTTPException(422, "Hedef kategori silinenle aynı olamaz.")
        hedef_kayit = db.query(Category).filter(
            scope_filter(Category, user.id, ws_id), Category.slug == hedef_slug,
        ).first()
        if not hedef_kayit:
            raise HTTPException(404, f"Hedef kategori bulunamadi ('{hedef_slug}').")

        db.query(Transaction).filter(
            scope_filter(Transaction, user.id, ws_id), Transaction.category == kayit.slug,
        ).update({Transaction.category: hedef_slug}, synchronize_session=False)
        # Zarf bütçesi de kategoriye bağlıdır (Envelope.category). Hedefte zaten zarf
        # varsa taşınan zarf silinir — (user, category) tekil, iki zarf olamaz.
        hedef_zarf = db.query(Envelope).filter(
            scope_filter(Envelope, user.id, ws_id), Envelope.category == hedef_slug,
        ).first()
        kaynak_zarf = db.query(Envelope).filter(
            scope_filter(Envelope, user.id, ws_id), Envelope.category == kayit.slug,
        ).first()
        if kaynak_zarf:
            if hedef_zarf:
                db.delete(kaynak_zarf)
            else:
                kaynak_zarf.category = hedef_slug

    db.delete(kayit)
    db.commit()
    return None
