"""
Hata izleme (P5 / BUG #195) — dış servise bağımlı OLMAYAN, kendi kendine yeten.

Sorun: beklenmedik bir 500 hatası yalnızca log dosyasına düşüyordu. Kapalı betada
operatör (tek kişi) log dosyasını sürekli izleyemez; kullanıcı "çalışmıyor" der, elde
hiçbir iz olmaz → hata sessizce yaşar. Masterprompt P5: "uygulama hatası sessizce
kaybolmasın".

Karar (K10 / KURAL 12): Sentry gibi bir dış servis **kullanıcının finansal verisini
üçüncü tarafa taşır** ve yeni bir hesap/anahtar (insan-kapısı) gerektirir. Bunun yerine
hata kayıtları KENDİ veritabanımızda tutulur:
  - Aynı hata tekrar ederse yeni satır açılmaz; `parmak_izi` ile sayaç artar
    (log şişmesi yok, "kaç kullanıcıyı kaç kez etkiledi" ölçülebilir).
  - **PII/sır temizliği zorunlu:** mesajdan e-posta, token, uzun sayı dizileri
    (kart/IBAN benzeri) maskelenir; istek gövdesi HİÇ saklanmaz.
  - Kullanıcıya dönen yanıt jeneriktir (BUG #175 ile tutarlı): iç detay sızmaz.
"""
from __future__ import annotations

import hashlib
import logging
import re
import traceback
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# PII/sır desenleri — hata metni log'a ve DB'ye YAZILMADAN önce maskelenir.
_MASKELER = [
    (re.compile(r"[\w\.\-\+]+@[\w\-]+\.[\w\.\-]+"), "<eposta>"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-\.]{10,}"), "<token>"),          # JWT
    (re.compile(r"\b(?:\d[ \-]?){13,24}\b"), "<uzun-sayi>"),          # kart/IBAN benzeri
    # `[\w-]*` şart: "SECRET_KEY=..." / "api_key_prod: ..." gibi SON EKLİ adlar da yakalanmalı
    # (eski desen yalnız tam kelimeyi görüyordu → SECRET_KEY maskelenmiyordu).
    (re.compile(r"(?i)\b(password|secret|api[_-]?key|token)[\w-]*\s*[=:]\s*\S+"), r"\1=<gizli>"),
]


def temizle(metin: str, max_uzunluk: int = 500) -> str:
    """Hata metninden PII/sır izlerini kaldır ve boyutu sınırla."""
    if not metin:
        return ""
    for kalip, yerine in _MASKELER:
        metin = kalip.sub(yerine, metin)
    return metin[:max_uzunluk]


def parmak_izi(hata_tipi: str, yol: str, tb_metni: str) -> str:
    """Aynı hatayı gruplayan kararlı kimlik (satır numaraları dahil, mesaj HARİÇ).

    Mesaj hariç tutulur: içinde değişken değer (id, tutar) olur ve her seferinde
    yeni bir grup açardı.
    """
    cerceveler = re.findall(r'File "([^"]+)", line (\d+)', tb_metni or "")
    imza = "|".join(f"{f.split(chr(92))[-1].split('/')[-1]}:{l}" for f, l in cerceveler[-5:])
    ham = f"{hata_tipi}|{yol}|{imza}"
    return hashlib.sha256(ham.encode("utf-8")).hexdigest()[:32]


def kaydet(db, *, hata: BaseException, yol: str, metod: str,
           user_id: Optional[int] = None) -> Optional[int]:
    """Hatayı DB'ye kaydeder (aynı parmak izi varsa sayacı artırır). Dönüş: kayıt id.

    Hata izleme ASLA isteği düşürmemeli: burada oluşan her sorun yutulur ve loglanır.
    """
    from app.models import ErrorLog
    try:
        tb_metni = "".join(traceback.format_exception(type(hata), hata, hata.__traceback__))
        tip = type(hata).__name__
        fp = parmak_izi(tip, yol, tb_metni)
        simdi = datetime.now(timezone.utc).replace(tzinfo=None)

        kayit = db.query(ErrorLog).filter(ErrorLog.fingerprint == fp).first()
        if kayit:
            kayit.occurrence_count = (kayit.occurrence_count or 1) + 1
            kayit.last_seen_at = simdi
            if user_id and kayit.last_user_id != user_id:
                kayit.last_user_id = user_id
        else:
            kayit = ErrorLog(
                fingerprint=fp,
                error_type=tip,
                message=temizle(str(hata)),
                path=yol[:200],
                method=metod[:10],
                traceback_tail=temizle(tb_metni[-2000:], max_uzunluk=2000),
                first_seen_at=simdi,
                last_seen_at=simdi,
                occurrence_count=1,
                last_user_id=user_id,
            )
            db.add(kayit)
        db.commit()
        return kayit.id
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        logger.exception("[error_tracking] hata kaydedilemedi (istek etkilenmedi)")
        return None
