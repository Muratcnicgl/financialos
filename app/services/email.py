"""
M11 (ADR-033) — SMTP e-posta gönderimi (şifre sıfırlama).

R3 (14 Tem 2026): scaffold → gerçek gönderim. `smtplib` STARTTLS 587 (Brevo standardı,
Python stdlib — yeni bağımlılık yok). Config `.env`'den os.getenv ile (codebase deseni,
settings.py yok). Gönderim FastAPI `BackgroundTasks` içinde çağrılır (istek bloklamaz).

KVKK: e-posta yalnız kullanıcının açık talebiyle (password-reset-request) + veri
yurt-içi/kendi SMTP'sinden. İçerik Türkçe, "sen istemediysen görmezden gel" notu.
"""
from __future__ import annotations

import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

logger = logging.getLogger(__name__)


def _smtp_config() -> dict:
    return {
        "host": os.getenv("SMTP_HOST", "").strip(),
        "port": int((os.getenv("SMTP_PORT", "587") or "587").strip()),
        "user": os.getenv("SMTP_USER", "").strip(),
        "password": os.getenv("SMTP_PASS", "").strip(),
        "from_addr": os.getenv("SMTP_FROM", "").strip(),
        "from_name": os.getenv("SMTP_FROM_NAME", "FinancialOS").strip() or "FinancialOS",
    }


def _mask(email: str) -> str:
    """BUG #180 (P2): log'a tam e-posta yazma (KVKK — log dosyası kullanıcı listesine dönüşür).

    'ornek.kullanici@site.com' → 'or***@site.com'
    """
    if not email or "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    return f"{local[:2]}***@{domain}"


def destek_adresi() -> str:
    """BUG #205 (H10/P8): DESTEK adresi — sablonlara KISISEL gmail gomuluyordu.

    Yabanci bir beta kullanicisinin aldigi ilk resmi e-posta bir sahsin gmail'ine
    yonlendiriyordu: hem guven sorunu hem KVKK "veri sorumlusu iletisim" beyaniyla
    celiski. Adres artik env'den gelir (SUPPORT_EMAIL).

    BUG #210 (P8) düzeltmesi: eski hali SUPPORT_EMAIL yoksa **SMTP gönderen adresine**
    düşüyordu. Bu adres pratikte operatörün kişisel posta kutusudur ve destek adresi
    artık kimliksiz `/api/meta` ucundan YAYINLANIYOR — yani sessiz bir yedek, şahsi
    adresi herkese açık hale getirirdi. Yedek kaldırıldı: adres ya bilinçli olarak
    `SUPPORT_EMAIL` ile tanımlanır ya da uygulama-içi kanal gösterilir. Production'da
    tanımsız bırakmak startup'ta fail-fast'tir (`app/settings.py: support_problems`).
    """
    return os.getenv("SUPPORT_EMAIL", "").strip() or \
        "uygulama içi geri bildirim (Şikâyet/İstek/Öneri)"


def smtp_configured() -> bool:
    """SMTP gönderime hazır mı (host+user+pass+from dolu)."""
    c = _smtp_config()
    return bool(c["host"] and c["user"] and c["password"] and c["from_addr"])


def send_email(to_email: str, subject: str, text_body: str, html_body: str) -> bool:
    """STARTTLS ile e-posta gönder. Başarıda True; hata/konfig-eksik → False (log)."""
    c = _smtp_config()
    if not smtp_configured():
        logger.warning("[email] SMTP yapılandırılmamış — %s gönderilemedi (SMTP_HOST/USER/PASS/FROM gerekli)", _mask(to_email))
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((c["from_name"], c["from_addr"]))
    msg["To"] = to_email
    # Brevo/çoğu istemci: text alternatifi önce, HTML sonra
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(c["host"], c["port"], timeout=20) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(c["user"], c["password"])
            server.sendmail(c["from_addr"], [to_email], msg.as_string())
        logger.info("[email] SMTP email sent to %s (subject=%r) via %s:%s", _mask(to_email), subject, c["host"], c["port"])
        return True
    except Exception as e:  # noqa: BLE001 — gönderim başarısızlığı akışı bozmamalı (BackgroundTask)
        logger.error("[email] SMTP gönderim hatası (%s): %s: %s", _mask(to_email), type(e).__name__, e)
        return False


def send_password_reset_email(to_email: str, reset_link: str, ilk_kez: bool = False) -> bool:
    """Şifre sıfırlama e-postası (Türkçe, KVKK-uyumlu, HTML + text alternatifli).

    BUG #233: `ilk_kez=True` → hesabın hiç şifresi olmamış (Google/GitHub ile açılmış).
    Ona "şifre SIFIRLAMA" demek şaşırtır ("benim şifrem yoktu ki") ve postayı sahte
    sandırıp göz ardı ettirir; metin "şifre BELİRLEME" olur.
    """
    eylem = "Şifre Belirleme" if ilk_kez else "Şifre Sıfırlama"
    talep = "şifre belirleme" if ilk_kez else "şifre sıfırlama"
    buton = "Şifremi Belirle" if ilk_kez else "Şifremi Sıfırla"
    subject = f"FinancialOS — {eylem}"
    destek = destek_adresi()   # BUG #205: kişisel adres şablona GÖMÜLMEZ
    text_body = (
        "Merhaba,\n\n"
        f"FinancialOS hesabınız için {talep} talebinde bulunuldu.\n"
        "Yeni şifrenizi belirlemek için aşağıdaki bağlantıya tıklayın "
        "(bağlantı 30 dakika geçerlidir):\n\n"
        f"{reset_link}\n\n"
        "Bu talebi siz yapmadıysanız bu e-postayı görmezden gelebilirsiniz; "
        "hesabınız güvende ve hiçbir değişiklik yapılmaz.\n\n"
        f"Sorularınız için: {destek}\n\n"
        "— FinancialOS"
    )
    html_body = f"""\
<!doctype html>
<html lang="tr"><body style="margin:0;background:#f4f4f5;font-family:Arial,Helvetica,sans-serif;color:#18181b">
  <div style="max-width:480px;margin:24px auto;background:#ffffff;border-radius:12px;padding:28px">
    <h1 style="font-size:20px;margin:0 0 8px">FinancialOS</h1>
    <p style="font-size:14px;line-height:1.6;color:#3f3f46">Merhaba,</p>
    <p style="font-size:14px;line-height:1.6;color:#3f3f46">
      Hesabınız için <b>{talep}</b> talebinde bulunuldu. Yeni şifrenizi belirlemek için
      aşağıdaki butona tıklayın. Bağlantı <b>30 dakika</b> geçerlidir.
    </p>
    <p style="text-align:center;margin:24px 0">
      <a href="{reset_link}" style="background:#4f46e5;color:#fff;text-decoration:none;padding:12px 22px;border-radius:8px;font-size:14px;display:inline-block">
        {buton}
      </a>
    </p>
    <p style="font-size:12px;line-height:1.6;color:#71717a">
      Buton çalışmazsa bu bağlantıyı tarayıcınıza kopyalayın:<br>
      <span style="word-break:break-all;color:#4f46e5">{reset_link}</span>
    </p>
    <hr style="border:none;border-top:1px solid #e4e4e7;margin:20px 0">
    <p style="font-size:12px;line-height:1.6;color:#a1a1aa">
      Bu talebi siz yapmadıysanız bu e-postayı görmezden gelebilirsiniz; hesabınız güvende
      ve hiçbir değişiklik yapılmaz. Sorularınız için: {destek}
    </p>
  </div>
</body></html>"""
    return send_email(to_email, subject, text_body, html_body)


def send_email_change_verification(to_email: str, dogrulama_link: str) -> bool:
    """P4.4 (BUG #215): YENİ adrese gönderilen doğrulama — adres ancak tıklanınca değişir.

    Neden yeni adrese: kullanıcı adresi yanlış yazarsa (asıl senaryo — hesabı kilitleyen
    şey budur) bağlantı gelmez, DEĞİŞİKLİK OLMAZ ve eski adresiyle girmeye devam eder.
    Adresi anında değiştirseydik tek harflik bir hata hesabı kalıcı olarak öldürürdü.
    """
    destek = destek_adresi()
    subject = "FinancialOS — E-posta Adresi Doğrulama"
    text_body = (
        "Merhaba,\n\n"
        "FinancialOS hesabınızın e-posta adresinin BU adresle değiştirilmesi talep edildi.\n"
        "Onaylamak için aşağıdaki bağlantıya tıklayın (bağlantı 2 saat geçerlidir):\n\n"
        f"{dogrulama_link}\n\n"
        "Bu talebi siz yapmadıysanız hiçbir şey yapmayın — tıklanmadıkça adres DEĞİŞMEZ.\n\n"
        f"Sorularınız için: {destek}\n\n"
        "— FinancialOS"
    )
    html_body = f"""\
<!doctype html>
<html lang="tr"><body style="margin:0;background:#f4f4f5;font-family:Arial,Helvetica,sans-serif;color:#18181b">
  <div style="max-width:480px;margin:24px auto;background:#ffffff;border-radius:12px;padding:28px">
    <h1 style="font-size:20px;margin:0 0 8px">FinancialOS</h1>
    <p style="font-size:14px;line-height:1.6;color:#3f3f46">Merhaba,</p>
    <p style="font-size:14px;line-height:1.6;color:#3f3f46">
      Hesabınızın e-posta adresinin <b>bu adresle</b> değiştirilmesi talep edildi.
      Onaylamak için butona tıklayın. Bağlantı <b>2 saat</b> geçerlidir.
    </p>
    <p style="text-align:center;margin:24px 0">
      <a href="{dogrulama_link}" style="background:#4f46e5;color:#fff;text-decoration:none;padding:12px 22px;border-radius:8px;font-size:14px;display:inline-block">
        Adresi Doğrula
      </a>
    </p>
    <p style="font-size:12px;line-height:1.6;color:#71717a">
      Buton çalışmazsa bu bağlantıyı tarayıcınıza kopyalayın:<br>
      <span style="word-break:break-all;color:#4f46e5">{dogrulama_link}</span>
    </p>
    <hr style="border:none;border-top:1px solid #e4e4e7;margin:20px 0">
    <p style="font-size:12px;line-height:1.6;color:#a1a1aa">
      Bu talebi siz yapmadıysanız hiçbir şey yapmayın — bağlantıya tıklanmadıkça adresiniz
      değişmez. Sorularınız için: {destek}
    </p>
  </div>
</body></html>"""
    return send_email(to_email, subject, text_body, html_body)


def send_email_changed_notice(to_email: str, yeni_adres_maskeli: str) -> bool:
    """ESKİ adrese uyarı — çalınmış bir oturumla yapılan adres değişimi GÖRÜNÜR olsun.

    Bildirim olmasaydı saldırgan adresi sessizce değiştirir, şifre sıfırlamayı kendi
    kutusuna yönlendirir; gerçek sahip hesabını kaybettiğini ancak giriş yapamayınca
    (ve artık sıfırlayamayacak durumdayken) fark ederdi.
    """
    destek = destek_adresi()
    subject = "FinancialOS — Hesabınızın e-posta adresi değişti"
    text_body = (
        "Merhaba,\n\n"
        f"FinancialOS hesabınızın e-posta adresi {yeni_adres_maskeli} olarak değiştirildi "
        "ve güvenlik gereği tüm oturumlar kapatıldı.\n\n"
        "BU İŞLEMİ SİZ YAPMADIYSANIZ hemen aşağıdaki adrese yazın — hesabınıza başkası "
        "erişmiş olabilir:\n"
        f"{destek}\n\n"
        "— FinancialOS"
    )
    html_body = f"""\
<!doctype html>
<html lang="tr"><body style="margin:0;background:#f4f4f5;font-family:Arial,Helvetica,sans-serif;color:#18181b">
  <div style="max-width:480px;margin:24px auto;background:#ffffff;border-radius:12px;padding:28px">
    <h1 style="font-size:20px;margin:0 0 8px">FinancialOS</h1>
    <p style="font-size:14px;line-height:1.6;color:#3f3f46">
      Hesabınızın e-posta adresi <b>{yeni_adres_maskeli}</b> olarak değiştirildi ve güvenlik
      gereği tüm oturumlar kapatıldı.
    </p>
    <p style="font-size:14px;line-height:1.6;color:#b91c1c">
      Bu işlemi siz yapmadıysanız hemen <b>{destek}</b> adresine yazın — hesabınıza başkası
      erişmiş olabilir.
    </p>
  </div>
</body></html>"""
    return send_email(to_email, subject, text_body, html_body)
