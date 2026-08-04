"""
PRODUCTION PROVASI (P6, Docker'sız) — canlı-öncesi son yazılım kapısı.

Neden: P6 gerçek sunucu ister (KURAL-3 insan-kapısı) ama **prod modunun yazılım yolu**
sunucu olmadan da koşulabilir. Bu script, deploy'un yaptığı işin aynısını yerelde yapar:

    PostgreSQL (prod motoru) → `alembic upgrade head` → uygulamayı
    ENVIRONMENT=production + AUTH_ENABLED=true ile başlat → `scripts/live_gate.py` koş.

Böylece "sunucuda ilk kez öğrenilecek" hatalar burada yakalanır: prod fail-fast config,
Postgres üzerinde migration (RLS dahil), kimlik zorunluluğu, /docs kapalılığı, hukuki
metinlerin erişilebilirliği, oran sınırlama, koç kotası.

KAPSAM DIŞI (yalnız gerçek sunucuda doğrulanabilir, statik olarak doğrulanmış):
  - TLS/HTTPS + HSTS/CSP başlıkları (nginx katmanı — `tests/test_deploy_timezone.py`)
  - Let's Encrypt sertifika akışı
  - 7/24 cron davranışı (24 saat gerektirir)

Kullanım:
    .\\venv\\Scripts\\python.exe scripts/prod_rehearsal.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

PORT = int(os.getenv("REHEARSAL_PORT", "8099"))
BASE = f"http://127.0.0.1:{PORT}"
SECRET = "prova-icin-uretilmis-yeterince-uzun-secret-key-0123456789"


def _pg_url() -> str:
    """Yerel PostgreSQL (pgserver) — prod motorunun aynısı."""
    from tests.pg_gate import get_postgres_url, fresh_pg_database
    url = get_postgres_url()
    if not url:
        # pgserver'ı ayağa kaldır (pg_gate_run ile aynı yol)
        from scripts.pg_gate_run import ensure_cluster, _pgdata_dir
        import pgserver
        pgdata = _pgdata_dir()
        ensure_cluster(pgdata)
        srv = pgserver.get_server(str(pgdata), cleanup_mode=None)
        url = srv.get_uri()
    return fresh_pg_database(url, "financialos_prova")


def _bekle_saglik(sn: int = 45) -> bool:
    for _ in range(sn * 2):
        try:
            with urllib.request.urlopen(f"{BASE}/api/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def main() -> int:
    print("=" * 64)
    print("PRODUCTION PROVASI (Docker'siz) — P6 yazilim yolu")
    print("=" * 64)

    print("\n[1/5] PostgreSQL (prod motoru) hazirlaniyor...")
    db_url = _pg_url()
    print(f"      DB: {db_url.split('@')[-1]}")

    env = dict(
        os.environ,
        DATABASE_URL=db_url,
        ENVIRONMENT="production",
        AUTH_ENABLED="true",
        SECRET_KEY=SECRET,
        TZ="Europe/Istanbul",
        SCHEDULER_ENABLED="false",     # prova: cron ayri servis (MA1)
        COACH_DAILY_USER_LIMIT="80",
        TRUST_PROXY_HEADERS="0",       # nginx yok
        RATE_LIMIT_LOGIN_MAX="5",
    )

    print("\n[2/5] alembic upgrade head (PROD semasi, Postgres)...")
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                       cwd=str(_ROOT), env=env, capture_output=True, text=True)
    if r.returncode != 0:
        print("      HATA: migration basarisiz (deploy'da da patlardi)")
        print(r.stderr[-1500:])
        return 1
    print("      OK — sema kuruldu")

    print("\n[3/5] Uygulama production modunda baslatiliyor...")
    app = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
         "--port", str(PORT), "--log-level", "warning"],
        cwd=str(_ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        if not _bekle_saglik():
            print("      HATA: uygulama acilmadi (prod fail-fast veya baslatma hatasi)")
            app.terminate()
            cikti = app.communicate(timeout=10)[0]
            print((cikti or "")[-2000:])
            return 1
        print("      OK — /api/health yanit veriyor")

        print("\n[4/5] Prova kullanicisi olusturuluyor (gercek kayit akisi)...")
        import json
        kayit = {"email": "prova@example.com", "password": "Prova-Parolasi-2026!",
                 "name": "Prova", "kvkk_consent": True}
        req = urllib.request.Request(f"{BASE}/api/auth/register",
                                     data=json.dumps(kayit).encode(), method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=10) as r2:
                print(f"      OK — kayit {r2.status}")
        except urllib.error.HTTPError as e:
            print(f"      kayit yaniti: {e.code} (409 = zaten var, sorun degil)")

        print("\n[5/5] CANLI KAPI kosuluyor...")
        from scripts import live_gate
        rc = live_gate.main([BASE, "--email", kayit["email"], "--password", kayit["password"],
                             "--skip-tls"])  # TLS katmani nginx'te (statik dogrulandi)

        print("\nNOT: HTTPS/HSTS/CSP kapilari bu provada DUSER — TLS katmani nginx'te")
        print("     (statik olarak dogrulandi: tests/test_deploy_timezone.py).")
        print("     Bu provanin kapsami: prod config + Postgres migration + kimlik +")
        print("     bilgi ifsasi + hukuki metinler + oran sinirlama + koc kotasi.")
        return rc
    finally:
        app.terminate()
        try:
            app.wait(timeout=10)
        except Exception:
            app.kill()
        print("\n[temizlik] uygulama durduruldu")


if __name__ == "__main__":
    sys.exit(main())
