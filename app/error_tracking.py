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
#
# BUG #244 fix (D29): eski liste dört desendi ve denetimin 12 gerçekçi örneğinin YARISINI
# kaçırıyordu — TCKN/telefon (11 hane, "13-24 hane" kuralının altında kalıyor), boşluksuz
# IBAN (harf öneki `\b` sınırını bozuyor), bcrypt hash, tırnaklı şifre değeri ve JWT olmayan
# opak token. Sıra ÖNEMLİ: özel desenler (IBAN/TCKN) genel sayı deseninden ÖNCE koşar.
_MASKELER = [
    (re.compile(r"[\w\.\-\+]+@[\w\-]+\.[\w\.\-]+"), "<eposta>"),
    (re.compile(r"\beyJ[A-Za-z0-9_\-\.]{10,}"), "<token>"),                    # JWT
    # Opak (JWT olmayan) taşıyıcı token — çalınan oturum log'dan kurtarılamasın.
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_\-\.=]{8,}"), "Bearer <token>"),
    # bcrypt/argon/scrypt hash'i: çevrimdışı kırılabilir → asla log'a düşmemeli.
    (re.compile(r"\$(?:2[aby]|argon2[a-z]*|scrypt)\$[A-Za-z0-9$./+_\-]{10,}"), "<hash>"),
    # IBAN (TR + 24 hane; 4'lü gruplu yazım da yakalanır) — `\b` yerine harf öneki eşleşmesi.
    (re.compile(r"(?i)\bTR\d{2}(?:[ ]?\d{4}){5}[ ]?\d{2}\b"), "<iban>"),
    # TCKN / telefon: 11 hane ve 0/+90 önekli biçimler (eski 13-24 hane kuralı ikisini de kaçırdı).
    (re.compile(r"(?<![\d.])\+?90[ ]?5\d{2}[ ]?\d{3}[ ]?\d{2}[ ]?\d{2}(?![\d.])"), "<telefon>"),
    (re.compile(r"(?<![\d.])0?5\d{2}[ ]?\d{3}[ ]?\d{2}[ ]?\d{2}(?![\d.])"), "<telefon>"),
    (re.compile(r"(?<![\d.])[1-9]\d{10}(?![\d.])"), "<tckn-veya-uzun-sayi>"),
    (re.compile(r"\b(?:\d[ \-]?){13,24}\b"), "<uzun-sayi>"),                   # kart benzeri
    # `[\w-]*` şart: "SECRET_KEY=..." / "api_key_prod: ..." gibi SON EKLİ adlar da yakalanmalı
    # (eski desen yalnız tam kelimeyi görüyordu → SECRET_KEY maskelenmiyordu).
    (re.compile(r"(?i)\b(password|secret|api[_-]?key|token|sifre|parola)[\w-]*\s*[=:]\s*"
                r"(?:'[^']*'|\"[^\"]*\"|\S+)"), r"\1=<gizli>"),
    # Ayırıcısız ama TIRNAKLI değer: `PASSWORD 'Sifre123!' gecersiz`. Ayırıcıyı isteğe bağlı
    # yapmak yanlış olur — o zaman kural "token" gibi ÇIPLAK kelimeyi de yer ve zaten
    # maskelenmiş metni (`<token>`) yeniden bozar (regresyon testiyle ölçüldü).
    (re.compile(r"(?i)\b(password|secret|api[_-]?key|token|sifre|parola)[\w-]*\s+"
                r"('[^']*'|\"[^\"]*\")"), r"\1 <gizli>"),
    # SQLAlchemy istisnası bound parameter'ları metne basar: `[parameters: ('Ali Veli', ...)]`.
    # İçindeki her şey kullanıcı verisidir (ad, adres, açıklama) — teşhis için SQL yeter.
    (re.compile(r"\[parameters:.*?\]", re.S), "[parameters: <gizli>]"),

    # BUG #258 fix: ETİKETE değil DEĞERİN KENDİSİNE bakan desenler. Önceki liste yalnız
    # "api_key=" gibi bir ETİKET görürse maskeliyordu; oysa sağlayıcı istisnaları anahtarı
    # çoğu zaman etiketsiz taşır:
    #   * Gemini/Google:  https://...?key=AIzaSyD...     → "key" kelimesi "api_key" değildir
    #   * OpenAI/OpenRouter: sk-... / sk-or-...   Groq: gsk_...   Cerebras: csk-...
    #   * SMTP: smtp://kullanici:parola@host
    # Anahtarın ŞEKLİ sabittir; etiketi olmasa da tanınır. (Ders L26: yasağın gücü, kaynağı
    # SEÇEN kod sayısı kadardır — burada "kaynak" değerin biçimidir.)
    (re.compile(r"(?i)([?&](?:key|apikey|api_key|access_token|token)=)[^&\s\"']+"), r"\1<gizli>"),
    (re.compile(r"\bAIza[0-9A-Za-z_\-]{20,}"), "<api-anahtari>"),               # Google
    (re.compile(r"\b(?:sk|csk|rk)-[A-Za-z0-9_\-]{16,}"), "<api-anahtari>"),      # OpenAI/OpenRouter/Cerebras
    (re.compile(r"\bgsk_[A-Za-z0-9_\-]{16,}"), "<api-anahtari>"),                # Groq
    (re.compile(r"\bxsmtpsib-[A-Za-z0-9_\-]{16,}"), "<smtp-anahtari>"),          # Brevo
    (re.compile(r"(?i)\b([a-z0-9+.\-]+)://([^:/\s@]+):([^@/\s]+)@"), r"\1://\2:<gizli>@"),  # URL kimliği
]


def temizle(metin: str, max_uzunluk: int = 500) -> str:
    """Hata metninden PII/sır izlerini kaldır ve boyutu sınırla."""
    if not metin:
        return ""
    for kalip, yerine in _MASKELER:
        metin = kalip.sub(yerine, metin)
    return metin[:max_uzunluk]


class LogMaskeleyici(logging.Filter):
    """BUG #244 fix (D29): maskeleme LOG zincirine de bağlanır.

    `temizle()` yalnız DB kaydına uygulanıyordu; global hata yakalayıcı `logger.exception`
    ile HAM traceback'i (SQLAlchemy'nin bound parameter metni dahil) dosyaya yazıyordu —
    yani sinyal vardı ama asıl sızdıran yüzeye hiç ulaşmıyordu (L21). Filtre hem
    biçimlenmiş mesajı hem istisna metnini maskeler; `record.args` temizlenir ki
    formatter yeniden birleştirdiğinde ham değer geri gelmesin.
    """

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003 (logging API)
        try:
            record.msg = temizle(record.getMessage(), max_uzunluk=4000)
            record.args = ()
            if record.exc_info:
                if not record.exc_text:
                    record.exc_text = "".join(
                        traceback.format_exception(*record.exc_info))
                record.exc_text = temizle(record.exc_text, max_uzunluk=8000)
        except Exception:       # log yolu ASLA uygulamayı düşürmez (fail-open görünürlük)
            pass
        return True


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
           user_id: Optional[int] = None, istek_id: Optional[str] = None) -> Optional[int]:
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
            # BUG #280 (B3): kayıt parmak izine göre BİRLEŞTİRİLİR (aynı hata tek satır),
            # bu yüzden burada saklanan SON isteğin kimliğidir — `last_user_id` ile aynı
            # konvansiyon. Daha eski bir kimlik DB'de bulunmaz ama LOG'da bulunur; zincirin
            # kalıcı ucu log, özet ucu bu satırdır.
            if istek_id:
                kayit.last_istek_id = istek_id[:64]
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
                last_istek_id=(istek_id or None) and istek_id[:64],  # BUG #280
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
