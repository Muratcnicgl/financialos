"""
İZOLE E2E KOŞUMU — Playwright testlerini CANLI veriye dokunmadan çalıştırır.

NEDEN (BUG #289'un üçüncü ayağı): `npm run e2e` frontend'i :5173'te, backend'i :8000'de
varsayıyordu. Bu makinede :8000'de KAPALI BETA SUNUCUSU koşuyor — yani e2e testleri
gerçek kullanıcıların veritabanına kullanıcı, hesap ve işlem yazıyordu. Süit tarafı
conftest ile kapatıldı (testler artık geçici DB'ye bağlanır); e2e ayrı bir süreç
olduğu için kendi izolasyonuna ihtiyaç duyar.

NE YAPAR:
  1. `data/e2e_izole.db` — her koşumda SIFIRDAN kurulur (alembic upgrade head).
  2. Backend'i :8100'de, o DB ile, AUTH_ENABLED=true olarak başlatır.
  3. Frontend'i :5273'te başlatır; `VITE_API_HEDEF` ile proxy'yi :8100'e çevirir.
  4. Playwright'ı bu adreslere yönlendirip koşar, sonra iki süreci de kapatır.

Canlı sunucuya (:8000) ve canlı DB'ye HİÇBİR noktada dokunmaz — portlar ve dosya ayrı.

Kullanım:
    .\\venv\\Scripts\\python.exe -m scripts.e2e_izole
    .\\venv\\Scripts\\python.exe -m scripts.e2e_izole --test tema-mobil
    .\\venv\\Scripts\\python.exe -m scripts.e2e_izole --tut     (koşum sonrası sunucuları açık bırak)
"""
from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
DB_YOLU = KOK / "data" / "e2e_izole.db"
BACKEND_PORT = 8100
FRONTEND_PORT = 5273
CANLI_PORT = 8000          # dokunulmaz — kapalı beta burada koşuyor


def _port_bos_mu(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _bekle(port: int, saniye: int = 60) -> bool:
    son = time.time() + saniye
    while time.time() < son:
        if not _port_bos_mu(port):
            return True
        time.sleep(0.5)
    return False


def _db_kur(env: dict) -> None:
    """Temiz e2e veritabanı: eski dosya silinir, şema alembic ile kurulur (ADR-013)."""
    for ek in ("", "-wal", "-shm"):
        Path(str(DB_YOLU) + ek).unlink(missing_ok=True)
    DB_YOLU.parent.mkdir(parents=True, exist_ok=True)
    print(f"[e2e] temiz DB: {DB_YOLU.name}")
    sonuc = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                           cwd=KOK, env=env, capture_output=True, text=True)
    if sonuc.returncode != 0:
        print(sonuc.stdout[-2000:], sonuc.stderr[-2000:], sep="\n")
        raise SystemExit("[e2e] alembic upgrade basarisiz")


def main() -> int:
    ap = argparse.ArgumentParser(description="Playwright e2e — izole DB + izole portlar")
    ap.add_argument("--test", default=None, help="playwright argumanlari (orn: tema-mobil, ya da: -g kapsam)")
    ap.add_argument("--tut", action="store_true", help="kosum sonrasi sunuculari kapatma")
    args = ap.parse_args()

    if _port_bos_mu(CANLI_PORT):
        print(f"[e2e] not: :{CANLI_PORT} bos (canli sunucu kosmuyor) — yine de ayri portta kosulur.")
    else:
        print(f"[e2e] :{CANLI_PORT} MESGUL (canli beta) — dokunulmuyor, e2e :{BACKEND_PORT}'e kurulur.")

    for port in (BACKEND_PORT, FRONTEND_PORT):
        if not _port_bos_mu(port):
            print(f"[e2e] HATA: :{port} mesgul. Onceki bir kosum acik kalmis olabilir.")
            return 2

    env = dict(
        os.environ,
        DATABASE_URL=f"sqlite:///{DB_YOLU.as_posix()}",
        AUTH_ENABLED="true",
        ENVIRONMENT="development",
        REGISTRATION_MODE="open",           # e2e kendi kullanicisini kaydeder
        REQUIRE_EMAIL_VERIFICATION="0",
        SCHEDULER_ENABLED="false",          # e2e sirasinda cron tetiklenmesin
        SERVE_SPA="0",
        # Hiz siniri e2e'de YANLIS soruyu cevaplar: uretimde "3 kayit / saat" spam'a
        # karsidir, burada ise UC SPEC DOSYASI kendi kullanicisini kaydeder ve her
        # retry bir deneme daha yakar -> kosum 429 ile duser (olculdu). Sinir
        # kaldirilmiyor, e2e sureci icin tavanlar yukseltiliyor; gercek limit
        # davranisini `tests/security/` pytest tarafinda olcuyoruz.
        RATE_LIMIT_REGISTER_MAX="500",
        RATE_LIMIT_LOGIN_MAX="500",
        RATE_LIMIT_INVITE_MAX="500",
        RATE_LIMIT_PRICES_MAX="500",
    )
    _db_kur(env)

    backend = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(BACKEND_PORT)],
        cwd=KOK, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    frontend = None
    try:
        if not _bekle(BACKEND_PORT):
            print("[e2e] HATA: backend acilmadi")
            return 3
        print(f"[e2e] backend :{BACKEND_PORT} hazir")

        npm = shutil.which("npm") or "npm"
        # VITE_OTOMATIK_AC=0: vite'in `open:true` ayari her kosumda gelistiricinin
        # tarayicisinda yeni sekme aciyordu (arka arkaya kosumlarda onlarca sekme).
        fe_env = dict(env, VITE_API_HEDEF=f"http://localhost:{BACKEND_PORT}",
                      VITE_OTOMATIK_AC="0")
        # `npm run dev` YERİNE doğrudan vite: Windows'ta npm bir sarmalayıcı süreç açar
        # ve `terminate()` yalnız sarmalayıcıyı öldürür — vite hayatta kalır, port
        # meşgul kalır, SONRAKİ koşum "frontend açılmadı" diye düşer (ölçüldü).
        vite_bin = KOK / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"
        fe_log = KOK / "logs" / "e2e_frontend.log"
        fe_log.parent.mkdir(parents=True, exist_ok=True)
        with open(fe_log, "w", encoding="utf-8") as fe_cikti:
            frontend = subprocess.Popen(
                [shutil.which("node") or "node", str(vite_bin),
                 "--port", str(FRONTEND_PORT), "--strictPort",
                 # Windows'ta vite varsayilan olarak ::1 (IPv6) dinler; hazir-olma
                 # yoklamasi 127.0.0.1'e baktigi icin sunucu "acilmadi" saniliyordu.
                 "--host", "127.0.0.1"],
                cwd=KOK / "frontend", env=fe_env,
                stdout=fe_cikti, stderr=subprocess.STDOUT)
        if not _bekle(FRONTEND_PORT):
            print("[e2e] HATA: frontend acilmadi. Son ciktisi:")
            print(fe_log.read_text(encoding="utf-8", errors="replace")[-1500:].encode("ascii", "replace").decode("ascii"))
            return 4
        print(f"[e2e] frontend :{FRONTEND_PORT} hazir (proxy -> :{BACKEND_PORT})")

        komut = [npm, "run", "e2e"]
        if args.test:
            komut += ["--", *args.test.split()]
        pw_env = dict(fe_env, PLAYWRIGHT_BASE_URL=f"http://127.0.0.1:{FRONTEND_PORT}",
                      E2E_API=f"http://127.0.0.1:{BACKEND_PORT}")
        sonuc = subprocess.run(komut, cwd=KOK / "frontend", env=pw_env,
                               shell=(os.name == "nt"))
        return sonuc.returncode
    finally:
        if args.tut:
            print(f"[e2e] sunucular acik birakildi (:{BACKEND_PORT} / :{FRONTEND_PORT}).")
        else:
            for p in (frontend, backend):
                if p and p.poll() is None:
                    p.terminate()
                    try:
                        p.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        p.kill()
            print("[e2e] sunucular kapatildi.")


if __name__ == "__main__":
    raise SystemExit(main())
