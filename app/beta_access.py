"""
Kapalı beta erişim kontrolü (P7 / BUG #199).

Sorun: `POST /api/auth/register` herkese açıktı. Sunucu canlıya çıktığı an bağlantıyı
bilen herkes hesap açabilirdi — "kapalı beta" bir iddia olurdu, kontrol değil. Finansal
veri taşıyan bir üründe davetli-dışı kayıt kabul edilemez.

Karar: kayıt modu env ile yönetilir ve **production'da varsayılan KAPALI**dır.
  REGISTRATION_MODE = invite_only (varsayılan: production) | open (varsayılan: dev)
Yanlış tarafa düşmemek için varsayılan güvenli seçilir: prod'da açık kayıt ancak
operatör AÇIKÇA `open` yazarsa mümkündür (fail-closed).

GUNCELLEMELER
-------------
BUG #279 fix (B1, 11 Ağu 2026): iki ekleme, ikisi de KOPYA KALDIRMAK için.
  (a) `eposta_daveti_bul()` — "bu adrese açılmış geçerli davet var mı?" sorusunun tek
      cevabı. Bu sorgu `routers/auth.py`'nin OAuth dalında elle yazılmıştı; ikinci bir
      kopya olduğu için kural ayrışmasına açıktı (L46: kopya değil içe aktarma).
  (b) `hesap_acabilir_mi()` — "bu adres kapalı betada hesap açabilir mi?". Kayıt
      YOLLARI dışındaki tüketiciler (workspace daveti) için gerekliydi: owner,
      allowlist'te olmayan birine davet gönderebiliyor, davetli hiç kayıt olamıyor ve
      NEDENİNİ bilmiyordu — sessiz ret (ADR-046 ilkesi: sessiz kabulün ikizi sessiz RET).
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session


def registration_mode() -> str:
    """'invite_only' | 'open'. Production varsayılanı KAPALI (fail-closed)."""
    from app.settings import is_production
    ham = os.getenv("REGISTRATION_MODE", "").strip().lower()
    if ham in ("invite_only", "open"):
        return ham
    return "invite_only" if is_production() else "open"


def invite_required() -> bool:
    return registration_mode() == "invite_only"


def yeni_kod() -> str:
    """Tahmin edilemez davet kodu (URL-güvenli)."""
    return secrets.token_urlsafe(18)


def davet_olustur(db: Session, *, email: Optional[str] = None, note: Optional[str] = None,
                  gecerlilik_gun: Optional[int] = 30):
    from datetime import timedelta
    from app.models import BetaInvite
    simdi = datetime.now(timezone.utc).replace(tzinfo=None)
    davet = BetaInvite(
        code=yeni_kod(),
        email=(email or "").lower().strip() or None,
        note=note,
        created_at=simdi,
        expires_at=(simdi + timedelta(days=gecerlilik_gun)) if gecerlilik_gun else None,
    )
    db.add(davet)
    db.commit()
    db.refresh(davet)
    return davet


def davet_dogrula(db: Session, code: Optional[str], email: str):
    """Geçerli daveti döner; geçersizse (kod/e-posta/süre/kullanılmış) None.

    Hata mesajları AYRIŞTIRILMAZ (hangi sebeple reddedildiği sızmasın — kod deneme
    saldırısına bilgi vermez).
    """
    from app.models import BetaInvite
    if not code:
        return None
    davet = db.query(BetaInvite).filter(BetaInvite.code == code.strip()).first()
    if davet is None or davet.used_at is not None:
        return None
    simdi = datetime.now(timezone.utc).replace(tzinfo=None)
    if davet.expires_at is not None and davet.expires_at < simdi:
        return None
    if davet.email and davet.email != (email or "").lower().strip():
        return None
    return davet


def eposta_daveti_bul(db: Session, email: str):
    """Bu ADRESE açılmış, kullanılmamış ve geçerli daveti döner; yoksa None.  # BUG #279

    Kod girilemeyen akışlarda (OAuth: kullanıcı sağlayıcıya gidip geliyor, form yok) kapı
    e-posta eşleşmesiyle kurulur. Süre/kullanım/e-posta kuralları BURADA tekrar YAZILMAZ —
    her aday `davet_dogrula`'dan geçirilir, yani kural tek yerdedir (L46).

    E-postasız (yalnız-kod) davetler bu yolla eşleşmez ve bu BİLİNÇLİDİR: tek genel kod,
    adres bilmeden sınırsız OAuth hesabı açardı (BUG #226 gerekçesi).
    """
    from app.models import BetaInvite
    normal = (email or "").lower().strip()
    if not normal:
        return None
    adaylar = (db.query(BetaInvite)
               .filter(BetaInvite.email == normal, BetaInvite.used_at.is_(None))
               .order_by(BetaInvite.id.asc())
               .all())
    for aday in adaylar:
        if davet_dogrula(db, aday.code, normal) is not None:
            return aday
    return None


def hesap_acabilir_mi(db: Session, email: str) -> bool:
    """Bu adres kapalı betada hesap açabilir mi?  # BUG #279

    Kayıt UÇLARININ kendi kapısı vardır (register/OAuth); bu fonksiyon kayıt DIŞINDAKİ
    tüketiciler içindir — birine "gel kullan" demeden önce sorulacak soru.

    Üç hâlde True:
      - kayıt modu 'open' (kapı yok),
      - adresin ZATEN hesabı var (davet tüketilmiş ya da hiç gerekmemiş),
      - adrese açılmış geçerli bir davet var.
    """
    if not invite_required():
        return True
    normal = (email or "").lower().strip()
    if not normal:
        return False
    from app.models import User
    varsa = db.query(User.id).filter(User.email == normal).first()
    if varsa is not None:
        return True
    return eposta_daveti_bul(db, normal) is not None


def davet_kullan(db: Session, davet, user_id: int) -> None:
    """Daveti tüket (tek kullanımlık). Commit ÇAĞIRANA bırakılır (aynı transaction)."""
    davet.used_at = datetime.now(timezone.utc).replace(tzinfo=None)
    davet.used_by_user_id = user_id


def email_verification_required() -> bool:
    """P8 (BUG #202): e-posta dogrulama zorunlu mu?

    Varsayilan: **PRODUCTION + ACIK KAYIT** ise ZORUNLU; aksi halde degil.

    Gerekce:
      - Davetli-only'de kayit zaten operator kontrolunde (enumerasyon icin gecerli davet
        kodu gerekir) -> akisi agirlastirmaya gerek yok.
      - Acik kayitta "bu e-posta zaten kayitli" yaniti KULLANICI LISTESI SIZDIRIR ve
        sahte hesap spam'i onunde engel kalmaz -> dogrulama sart.
      - **Development'ta ASLA zorunlu degil**: SMTP yok, kayit akisi kilitlenir ve
        yerel gelistirme/test bozulur (bu, ilk denemede 25 testi kirdi).
    Env ile ezilebilir: REQUIRE_EMAIL_VERIFICATION=1|0
    """
    ham = os.getenv("REQUIRE_EMAIL_VERIFICATION", "").strip().lower()
    if ham in ("1", "true", "yes"):
        return True
    if ham in ("0", "false", "no"):
        return False
    from app.settings import is_production
    return is_production() and registration_mode() == "open"
