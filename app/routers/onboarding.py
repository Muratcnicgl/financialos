"""
Onboarding — isteğe bağlı DEMO VERİ (P3.5 / H5, BUG #194).

Sorun: yeni kullanıcı bomboş bir ekranla karşılaşıyor. "Örnek veri" ihtiyacı vardı ama
tek çözüm `scripts/setup_data.py`'ydi — o da **başkasının (kullanıcının) kanonik verisini**
yükler ve `drop_all` yapar; bir beta kullanıcısına asla bulaşmamalı.

Karar:
  - Demo veri **isteğe bağlıdır** (kullanıcı ister), kayıtta otomatik yüklenmez.
  - **Tek tuşla, TAM olarak silinebilir** — bunun için yaratılan her satırın kimliği
    `demo_data_markers` tablosunda tutulur. Silme, yalnız o satırları siler; kullanıcının
    kendi girdiği verilere ASLA dokunmaz (işaretsiz satır silinmez).
  - Veriler jeneriktir (kişi adı/banka markası yok — BUG #166/#168 ailesi).

GUNCELLEMELER
-------------
BUG #262 fix (P3.3 — "ilk giriş rehberi"): iki defekt vardı.
  (a) Rehber tek adımlıktı: `bosMu = accounts.length === 0` olduğu için kullanıcı İLK hesabını
      ekler eklemez kart tümüyle kayboluyordu — kalan üç adım (işlem gir → kendi kuralını yaz →
      koça sor) hiç yönlendirilmiyordu. Kart bir cümleydi, rehber değildi.
  (b) Kartın birincil düğmesi ÖLÜYDÜ: `<a href="#accounts">` — uygulama hash-router kullanmıyor
      (`App.jsx` `activeTab` state'i), yani yeni kullanıcının gördüğü ilk düğme hiçbir şey
      yapmıyordu. Sessiz defekt: tarayıcı hata vermez, süit yeşil kalır (L28).
  Çözüm: adım durumu ARTIK BACKEND'DE deterministik türetiliyor (`GET /api/onboarding/rehber`),
  frontend yalnız çiziyor (ADR-001 ruhu: karar veri katmanında, arayüz açıklar). Adımlar
  YALNIZ kullanıcının KENDİ verisini sayar — demo satırları dışlanır; aksi halde "örnek veriyle
  gez" diyen kullanıcı için rehber anında 3/4 tamam görünüp kaybolurdu.
  Ayrıca: `require_write()` router seviyesindeydi → OKUMA uçları da yazma yetkisi istiyordu
  (paylaşılan workspace'te `viewer` üyenin rehberi/demo durumu 403 alıyor, frontend'de sessizce
  yutuluyordu). Guard yalnız POST/DELETE/PATCH'e taşındı.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.user_prefs import user_today  # BUG #237 (D17)
from app.workspace_deps import active_workspace_id, scope_filter, require_write
from app.money_format import format_para  # BUG #256 (H4): para etiketi tek kaynak
from app.models import (
    User, Account, AccountType, Transaction, TransactionType, RecurringIncome,
    MasterCheckpoint, CheckpointType, CoachMemory, Goal, DemoDataMarker,
)

logger = logging.getLogger(__name__)

# BUG #262: require_write ARTIK router seviyesinde DEĞİL — okuma uçlarını da kilitliyordu.
router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

# Silme sırası: çocuk → ebeveyn (FK ihlali olmasın)
_SILME_SIRASI = ("transactions", "recurring_incomes", "goals", "master_checkpoints", "accounts")
_MODEL_HARITASI = {
    "accounts": Account,
    "transactions": Transaction,
    "recurring_incomes": RecurringIncome,
    "master_checkpoints": MasterCheckpoint,
    "goals": Goal,
}


class DemoDurumu(BaseModel):
    yuklu: bool
    satir_sayisi: int


def _isaretle(db: Session, user_id: int, tablo: str, satir_id: int) -> None:
    db.add(DemoDataMarker(user_id=user_id, table_name=tablo, row_id=satir_id))


@router.get("/demo", response_model=DemoDurumu)
def demo_durumu(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.query(DemoDataMarker).filter(DemoDataMarker.user_id == user.id).count()
    return DemoDurumu(yuklu=n > 0, satir_sayisi=n)


@router.post("/demo", response_model=DemoDurumu, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_write())])
def demo_yukle(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),
):
    """Jenerik örnek veri yükler (kullanıcının kendi verisine dokunmaz, izlenebilir)."""
    if db.query(DemoDataMarker).filter(DemoDataMarker.user_id == user.id).count() > 0:
        raise HTTPException(409, "Demo veri zaten yüklü. Önce kaldırabilirsin.")

    bugun = user_today(user)  # BUG #237 (D17): demo veri kullanıcının gününe göre kurulur

    kasa = Account(user_id=user.id, workspace_id=ws_id, name="Örnek Vadesiz Hesap",
                   account_type=AccountType.cash, balance=15000.0,
                   notes="Demo veri — istediğin an kaldırabilirsin.")
    kart = Account(user_id=user.id, workspace_id=ws_id, name="Örnek Kredi Kartı",
                   account_type=AccountType.credit_card, balance=-3200.0,
                   credit_limit=20000.0, statement_day=5, payment_day=20,
                   notes="Demo veri")
    db.add_all([kasa, kart])
    db.flush()
    _isaretle(db, user.id, "accounts", kasa.id)
    _isaretle(db, user.id, "accounts", kart.id)

    maas = RecurringIncome(user_id=user.id, workspace_id=ws_id, name="Örnek Maaş",
                           amount=42000.0, day_of_month=15, is_active=True,
                           notes="Demo veri")
    db.add(maas)
    db.flush()
    _isaretle(db, user.id, "recurring_incomes", maas.id)

    for gun_once, tutar, kategori, aciklama in (
        (2, 480.0, "market", "Örnek market alışverişi"),
        (5, 1250.0, "fatura", "Örnek elektrik/su faturası"),
        (9, 300.0, "ulasim", "Örnek ulaşım harcaması"),
    ):
        tx = Transaction(user_id=user.id, workspace_id=ws_id, account_id=kasa.id,
                         transaction_type=TransactionType.expense, amount=tutar,
                         category=kategori, description=aciklama,
                         transaction_date=bugun - timedelta(days=gun_once))
        db.add(tx)
        db.flush()
        _isaretle(db, user.id, "transactions", tx.id)

    hedef = Goal(user_id=user.id, workspace_id=ws_id, goal_type="cash_target",
                 title="Örnek Hedef: 3 aylık acil fon", target_amount=Decimal("50000"),
                 status="active")
    db.add(hedef)
    db.flush()
    _isaretle(db, user.id, "goals", hedef.id)

    kural = MasterCheckpoint(
        user_id=user.id, workspace_id=ws_id, title="Örnek kural: nakit tabanı",
        description=f"Nakdim {format_para(5000, ondalik=0)}'nin altına inmesin (bu bir demo "
                    "kuralıdır — kendi kuralını yazınca bunu silebilirsin).",
        checkpoint_type=CheckpointType.red_line, priority=2, is_active=True,
        rule_type="min_cash_floor", rule_params='{"amount": 5000}')
    db.add(kural)
    db.flush()
    _isaretle(db, user.id, "master_checkpoints", kural.id)

    db.commit()
    n = db.query(DemoDataMarker).filter(DemoDataMarker.user_id == user.id).count()
    logger.info("[onboarding] demo veri yuklendi user_id=%s satir=%s", user.id, n)
    return DemoDurumu(yuklu=True, satir_sayisi=n)


@router.delete("/demo", response_model=DemoDurumu,
               dependencies=[Depends(require_write())])
def demo_kaldir(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),
):
    """YALNIZ demo olarak işaretlenmiş satırları siler — kullanıcının verisi korunur."""
    isaretler = (db.query(DemoDataMarker)
                 .filter(DemoDataMarker.user_id == user.id).all())
    if not isaretler:
        return DemoDurumu(yuklu=False, satir_sayisi=0)

    by_table: dict[str, list[int]] = {}
    for m in isaretler:
        by_table.setdefault(m.table_name, []).append(m.row_id)

    for tablo in _SILME_SIRASI:
        idler = by_table.get(tablo)
        if not idler:
            continue
        model = _MODEL_HARITASI[tablo]
        (db.query(model)
           .filter(model.id.in_(idler), scope_filter(model, user.id, ws_id))
           .delete(synchronize_session=False))

    (db.query(DemoDataMarker)
       .filter(DemoDataMarker.user_id == user.id)
       .delete(synchronize_session=False))
    db.commit()
    logger.info("[onboarding] demo veri kaldirildi user_id=%s", user.id)
    return DemoDurumu(yuklu=False, satir_sayisi=0)


# =============================================================================
# İLK KURULUM REHBERİ (P3.3 / BUG #262)
# =============================================================================
#
# Neden backend: adımın "tamam" olup olmadığı bir VERİ sorusudur, arayüz sorusu değil.
# Frontend'e bırakılsaydı her panel kendi ölçütünü uydururdu (BUG #161/SBN-001 sınıfı:
# aynı kural birden çok yerde ayrı kodlanır). Burada tek kaynak, tek test.


class RehberAdimi(BaseModel):
    anahtar: str        # kararlı kimlik (test/telemetri) — metin değişse de sabit
    baslik: str
    aciklama: str
    sekme: str          # frontend tab id'si (App.jsx activeTab) — ölü link üretmemek için
    tamam: bool


class RehberDurumu(BaseModel):
    adimlar: list[RehberAdimi]
    tamamlanan: int
    toplam: int
    tamamlandi: bool
    gizli: bool
    gorunur: bool       # arayüzün tek bakacağı alan: çiz / çizme


class RehberGizleIstegi(BaseModel):
    gizli: bool


# (anahtar, başlık, açıklama, sekme) — metinler jeneriktir (kişi adı / banka markası yok).
_ADIM_TANIMLARI = (
    ("hesap", "Kendi hesabını ekle",
     "Vadesiz hesap, kredi kartı ya da yatırım hesabı — bakiyeni sen girersin, "
     "banka bağlantısı yoktur.", "accounts"),
    ("islem", "İlk işlemini gir",
     "Bir gelir ya da gider yaz; bütçe ve nakit akışı bu kayıtlardan hesaplanır.",
     "transactions"),
    ("kural", "Kendi kuralını yaz",
     "Kırmızı çizgini tanımla (örnek: nakit tabanı). Kural tavsiye değildir — "
     "aksiyon öncesi kod seviyesinde uygulanır.", "redlines"),
    ("koc", "Koça ilk sorunu sor",
     "Koç yalnız senin verinden konuşur; hesabı kendisi yapmaz, panel neyse onu anlatır.",
     "coach"),
)


def _demo_satir_idleri(db: Session, tablo: str) -> set[int]:
    """O tabloda demo olarak işaretlenmiş satır id'leri.

    Kullanıcıya göre DEĞİL tabloya göre okunur: bir satır kim yüklediyse yüklesin demodur.
    Sızıntı riski yok — küme YALNIZ zaten kapsam-filtreli bir sorgudan DIŞLAMAK için kullanılır,
    hiçbir id yanıta çıkmaz.
    """
    return {r[0] for r in db.query(DemoDataMarker.row_id)
            .filter(DemoDataMarker.table_name == tablo).all()}


def _kendi_satiri_var_mi(db: Session, model, tablo: str, user_id: int,
                         ws_id: Optional[int]) -> bool:
    """Kapsam içinde, DEMO OLMAYAN en az bir satır var mı.

    Demo dışlaması şart: "örnek veriyle gez" diyen kullanıcı için rehber aksi halde anında
    3/4 tamam görünür ve kaybolur — oysa kullanıcı henüz kendi kurulumuna hiç başlamamıştır.
    """
    q = db.query(model.id).filter(scope_filter(model, user_id, ws_id))
    demo = _demo_satir_idleri(db, tablo)
    if demo:
        q = q.filter(~model.id.in_(demo))
    return db.query(q.exists()).scalar() is True


def _rehber_durumu(db: Session, user: User, ws_id: Optional[int]) -> RehberDurumu:
    tamamlar = {
        "hesap": _kendi_satiri_var_mi(db, Account, "accounts", user.id, ws_id),
        "islem": _kendi_satiri_var_mi(db, Transaction, "transactions", user.id, ws_id),
        "kural": _kendi_satiri_var_mi(db, MasterCheckpoint, "master_checkpoints",
                                      user.id, ws_id),
        # Koç geçmişi workspace'e değil kişiye bağlıdır (CoachMemory'de workspace_id yok).
        "koc": db.query(
            db.query(CoachMemory.id)
              .filter(CoachMemory.user_id == user.id, CoachMemory.role == "user")
              .exists()
        ).scalar() is True,
    }
    adimlar = [
        RehberAdimi(anahtar=a, baslik=b, aciklama=c, sekme=s, tamam=tamamlar[a])
        for a, b, c, s in _ADIM_TANIMLARI
    ]
    tamamlanan = sum(1 for x in adimlar if x.tamam)
    tamamlandi = tamamlanan == len(adimlar)
    gizli = getattr(user, "onboarding_dismissed_at", None) is not None
    return RehberDurumu(
        adimlar=adimlar,
        tamamlanan=tamamlanan,
        toplam=len(adimlar),
        tamamlandi=tamamlandi,
        gizli=gizli,
        gorunur=not tamamlandi and not gizli,
    )


@router.get("/rehber", response_model=RehberDurumu)
def rehber(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),
):
    """İlk kurulum rehberi: hangi adım tamam, sırada ne var, kart çizilmeli mi."""
    return _rehber_durumu(db, user, ws_id)


# require_write YOK: gizleme workspace verisi değil KİŞİSEL tercihtir (users tablosu).
# Paylaşılan bir workspace'te `viewer` üye de kendi rehberini kapatabilmeli.
@router.patch("/rehber", response_model=RehberDurumu)
def rehber_gizle(
    istek: RehberGizleIstegi,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),
):
    """Rehberi gizle / yeniden göster.

    Gizleme GERİ ALINABİLİR olmalı (Hesap panelinden) — geri dönüşü olmayan bir "kapat"
    düğmesi kullanıcıyı kilitler.
    """
    user.onboarding_dismissed_at = datetime.utcnow() if istek.gizli else None
    db.commit()
    db.refresh(user)
    logger.info("[onboarding] rehber gizli=%s user_id=%s", istek.gizli, user.id)
    return _rehber_durumu(db, user, ws_id)
