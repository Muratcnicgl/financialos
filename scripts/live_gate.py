"""
CANLI DOĞRULAMA KAPISI (P6) — deploy sonrası tek komut.

Masterprompt P6: "canlı doğrulama gate'leri: sağlık, login, cockpit, koç, cron 24s, yedek."
Bu script o kapıları **elle tıklamadan** koşar ve PASS/FAIL tablosu basar. Amaç: sunucu
ayağa kalktığında "çalışıyor gibi görünüyor" demek yerine ÖLÇMEK (masterprompt §6: kanıt =
komut + gerçek çıktı).

Kullanım (Murat, VM hazır olduğunda):
    python scripts/live_gate.py https://<alan-adi>
    python scripts/live_gate.py https://<alan-adi> --email <e-posta> --password <parola>

Kimlik bilgisi verilmezse yalnız kimliksiz kapılar koşar (sır chat'e/DB'ye yazılmaz;
parametre olarak verilir, hiçbir yere kaydedilmez).

Çıkış kodu: 0 = tüm zorunlu kapılar geçti, 1 = en az bir zorunlu kapı düştü.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Optional

TIMEOUT = 15


class Sonuc:
    def __init__(self):
        self.satirlar: list[tuple[str, bool, bool, str]] = []  # (ad, gecti, zorunlu, not)

    def ekle(self, ad: str, gecti: bool, notu: str = "", zorunlu: bool = True):
        self.satirlar.append((ad, gecti, zorunlu, notu))
        isaret = "GECTI " if gecti else ("DUSTU " if zorunlu else "UYARI ")
        print(f"  [{isaret}] {ad}" + (f" — {notu}" if notu else ""))

    def basarili(self) -> bool:
        return all(g for _a, g, z, _n in self.satirlar if z)


def _iste(url: str, *, metod: str = "GET", veri: Optional[dict] = None,
          token: Optional[str] = None) -> tuple[int, dict, dict]:
    """(status, headers, json_body) — hata durumunda da status döner."""
    govde = json.dumps(veri).encode() if veri is not None else None
    req = urllib.request.Request(url, data=govde, method=metod)
    req.add_header("Accept", "application/json")
    if govde:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            ham = r.read().decode("utf-8", "replace")
            try:
                return r.status, dict(r.headers), json.loads(ham)
            except json.JSONDecodeError:
                return r.status, dict(r.headers), {"_raw": ham[:400]}
    except urllib.error.HTTPError as e:
        ham = e.read().decode("utf-8", "replace")
        try:
            return e.code, dict(e.headers), json.loads(ham)
        except json.JSONDecodeError:
            return e.code, dict(e.headers), {"_raw": ham[:400]}
    except Exception as e:  # ağ/DNS/TLS
        return 0, {}, {"_error": f"{type(e).__name__}: {e}"}


def kosla(base: str, email: Optional[str], password: Optional[str],
          tls_katmani: bool = True) -> Sonuc:
    base = base.rstrip("/")
    s = Sonuc()

    print("\n== 1. ERİŞİM + SAĞLIK ==")
    kod, basliklar, govde = _iste(f"{base}/api/health")
    s.ekle("sağlık ucu 200", kod == 200, f"kod={kod} {govde.get('_error','')}")

    # TLS katmanını nginx/Caddy sağlar. Docker'sız YEREL PROVADA (scripts/prod_rehearsal.py)
    # o katman yoktur → kapılar anlamsızca düşer ve prova hiçbir zaman "geçti" diyemez.
    # `--skip-tls` YALNIZ o prova içindir; GERÇEK SUNUCUDA kullanılmaz (en kritik kapı
    # kör kalır: token'lar açık ağda gider).
    if not tls_katmani:
        print("\n== 2. TAŞIMA GÜVENLİĞİ == (ATLANDI — --skip-tls, yalnız yerel prova)")
    else:
        print("\n== 2. TAŞIMA GÜVENLİĞİ ==")
        s.ekle("HTTPS kullanılıyor", base.startswith("https://"),
               "IP/HTTP ile beta açılmaz (token'lar açık ağda gider)")
        hsts = basliklar.get("Strict-Transport-Security", "")
        s.ekle("HSTS başlığı", bool(hsts), hsts[:40])
        csp = basliklar.get("Content-Security-Policy", "")
        s.ekle("CSP başlığı", bool(csp), csp[:50])
        s.ekle("X-Frame-Options DENY", basliklar.get("X-Frame-Options", "").upper() == "DENY")
        s.ekle("sunucu sürümü gizli", "Server" not in basliklar or
               basliklar.get("Server", "").lower() in ("nginx", "caddy"), zorunlu=False)

    print("\n== 3. KİMLİK ZORUNLULUĞU ==")
    kod, _b, _g = _iste(f"{base}/api/cockpit")
    s.ekle("token'sız cockpit 401", kod == 401,
           f"kod={kod} — 200 ise AUTH_ENABLED kapalı, TÜM veri açık!")
    kod, _b, _g = _iste(f"{base}/api/accounts")
    s.ekle("token'sız hesaplar 401", kod == 401, f"kod={kod}")

    print("\n== 4. BİLGİ İFŞASI ==")
    kod, _b, _g = _iste(f"{base}/docs")
    s.ekle("/docs production'da kapalı", kod in (404, 401, 403), f"kod={kod}")
    kod, _b, _g = _iste(f"{base}/openapi.json")
    s.ekle("/openapi.json kapalı", kod in (404, 401, 403), f"kod={kod}")

    print("\n== 5. KAPALI BETA (kayıt kontrolü) ==")
    # P7 (BUG #199): canlıda kayıt herkese açıksa "kapalı beta" bir İDDİADIR, kontrol değil.
    kod, _b, _g = _iste(f"{base}/api/auth/register", metod="POST", veri={
        "email": "kapali-beta-kontrol@example.com", "password": "Rastgele-Parola-2026!",
        "name": "kontrol", "kvkk_consent": True})
    s.ekle("kayıt davetlilere kapalı", kod == 403,
           f"kod={kod} — 201 ise BAĞLANTIYI BİLEN HERKES hesap açabiliyor")

    print("\n== 6. HUKUKİ METİNLER (KVKK) ==")
    for slug in ("kvkk", "kullanim-sartlari", "veri-isleyenler"):
        kod, _b, govde = _iste(f"{base}/api/legal/{slug}")
        s.ekle(f"/api/legal/{slug} okunabilir",
               kod == 200 and len(str(govde.get("content", ""))) > 500, f"kod={kod}")

    print("\n== 6. PWA ==")
    kod, _b, _g = _iste(f"{base}/manifest.webmanifest")
    s.ekle("manifest yayında", kod == 200, f"kod={kod}", zorunlu=False)
    kod, _b, _g = _iste(f"{base}/sw.js")
    s.ekle("service worker yayında", kod == 200, f"kod={kod}", zorunlu=False)

    if email and password:
        print("\n== 7. OTURUM + VERİ (kimlikli) ==")
        kod, _b, govde = _iste(f"{base}/api/auth/login", metod="POST",
                               veri={"email": email, "password": password})
        token = govde.get("access_token") if kod == 200 else None
        s.ekle("giriş çalışıyor", bool(token), f"kod={kod}")
        if token:
            kod, _b, ck = _iste(f"{base}/api/cockpit", token=token)
            s.ekle("cockpit dönüyor", kod == 200 and "net_deger" in ck, f"kod={kod}")
            kod, _b, uc = _iste(f"{base}/api/coach/usage", token=token)
            s.ekle("koç kota ucu", kod == 200, f"kod={kod}")
            if kod == 200:
                s.ekle("kullanıcı-başı tavan tanımlı", (uc.get("user_daily_limit") or 0) > 0,
                       f"limit={uc.get('user_daily_limit')} (ADR-041)")
            # P5.3 (BUG #203): cron GORUNUR mu? 24 saat sonra bu satir "calisti" demeli.
            kod, _b, sc = _iste(f"{base}/api/ops/scheduler", token=token)
            s.ekle("scheduler görünürlük ucu", kod == 200, f"kod={kod}", zorunlu=False)
            if kod == 200:
                isler = sc.get("isler", [])
                s.ekle("cron en az bir kez çalıştı (24s sonra ZORUNLU)",
                       bool(isler), f"is sayisi={len(isler)}", zorunlu=False)
                basarisiz = [i["job_name"] for i in isler if i.get("son_sonuc") is False]
                s.ekle("son çalışmalarda hata yok", not basarisiz,
                       f"basarisiz={basarisiz}", zorunlu=False)

            kod, _b, fr = _iste(f"{base}/api/fund-price/freshness", token=token)
            s.ekle("fiyat tazeliği ucu", kod == 200, f"kod={kod}", zorunlu=False)
            if kod == 200:
                bayat = fr.get("stale_count", 0)
                s.ekle("cron fiyatları güncel tutuyor (24s sonra kontrol et)",
                       bayat == 0, f"bayat={bayat}", zorunlu=False)
    else:
        print("\n== 7. OTURUM + VERİ == (atlandı — --email/--password verilmedi)")

    # SIRA ÖNEMLİ (production provasında yakalandı, BUG #198): brute-force denemesi login
    # kovasını TÜKETİR. Bu blok kimlikli kontrollerden ÖNCE koşarsa gerçek giriş 429 alır ve
    # kapı "giriş çalışmıyor" diye YANLIŞ ALARM verir — operatör var olmayan bir hatayı
    # kovalar. Bu yüzden EN SONDA.
    print("\n== 8. ORAN SINIRLAMA (en sonda — login kovasını tüketir) ==")
    kodlar = [_iste(f"{base}/api/auth/login", metod="POST",
                    veri={"email": "yok@example.com", "password": "YanlisParola-2026!"})[0]
              for _ in range(8)]
    s.ekle("brute-force sınırı devrede", 429 in kodlar,
           f"kodlar={kodlar} — 429 yoksa limiter çalışmıyor")

    return s


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Canlı deploy doğrulama kapısı (P6)")
    ap.add_argument("base_url", help="https://alan-adi")
    ap.add_argument("--email", default=None)
    ap.add_argument("--password", default=None, help="Sır: yalnız parametre; hiçbir yere yazılmaz")
    ap.add_argument("--skip-tls", action="store_true",
                    help="TLS katmanı kapılarını atla — YALNIZ Docker'sız yerel prova için")
    args = ap.parse_args(argv)

    print(f"CANLI KAPI: {args.base_url}")
    if args.skip_tls:
        print("UYARI: --skip-tls verildi — TLS kapilari ATLANDI. Gercek sunucuda KULLANMA.")
    s = kosla(args.base_url, args.email, args.password, tls_katmani=not args.skip_tls)

    zorunlu_dusen = [a for a, g, z, _n in s.satirlar if z and not g]
    print("\n" + "=" * 60)
    if s.basarili():
        print(f"SONUC: TUM ZORUNLU KAPILAR GECTI ({len(s.satirlar)} kontrol)")
        print("Sonraki adim: 24 saat sonra cron/fiyat tazeligini tekrar kontrol et (P6.3).")
        return 0
    print(f"SONUC: {len(zorunlu_dusen)} ZORUNLU KAPI DUSTU:")
    for ad in zorunlu_dusen:
        print(f"  - {ad}")
    print("Kapali beta ACILMAZ. Sorun giderme: docs/deployment/runbook.md")
    return 1


if __name__ == "__main__":
    sys.exit(main())
