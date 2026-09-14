r"""
GÖREV KOŞUCUSU — komutların TEK KAYNAĞI (BUG #475 / DEVOPS-014).

NEDEN BU, NEDEN Makefile/justfile DEĞİL
---------------------------------------
Komutlar `docs/dev-commands.md`, `docs/contributing.md`, `.githooks/pre-commit` ve
`.github/workflows/ci.yml` arasında dağınıktı; aynı iş dört yerde farklı yazılıyordu
(ör. testler `pytest tests/ -q` / `python -m pytest tests/` / `-x --tb=short`). Bir
Makefile bunu Linux/mac'te çözer ama bu proje Windows'ta geliştiriliyor ve `make`
kurulu değil; `just` ek araç ister; `tasks.ps1` ise CI'da (Linux) koşmaz. İki dosya
(Makefile + tasks.ps1) tutmak = iki kaynak = kaçınılmaz sürüklenme.

Python zaten şart; koşucu Python'da yaşar ve HER yerde aynı çalışır:

    python -m scripts.gorev            # görev listesi
    python -m scripts.gorev test       # pytest (tam süit)
    python -m scripts.gorev kapilar    # commit öncesi tüm kapılar
    python -m scripts.gorev test --kuru   # komutu koşturmadan yazdır

`Makefile` yine var ama TEK satırlık bir vekildir (`make test` → bu betik); komut bilgisi
orada değil, burada durur. `tests/test_gorev_kapisi.py` her görevin işaret ettiği betiğin
gerçekten var olduğunu ve belgelerin bu listeyle uyuştuğunu ölçer.

KURAL: yeni komut önce buraya girer, belgeler buradan `--liste` çıktısıyla beslenir.

GUNCELLEMELER
-------------
BUG #475 fix: dosya oluşturuldu (DEVOPS-014).
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess  # noqa: S404 — sabit argümanlı geliştirme komutları
import sys
from dataclasses import dataclass
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
FRONTEND = KOK / "frontend"
PY = sys.executable  # hangi yorumlayıcı koşturduysa o (venv içindeyse venv)


def _npm() -> str:
    # Windows'ta `npm` bir .cmd; shutil.which uzantıyı çözer, CI'da düz `npm`.
    return shutil.which("npm") or "npm"


def _npx() -> str:
    return shutil.which("npx") or "npx"


@dataclass(frozen=True)
class Gorev:
    ad: str
    aciklama: str
    komutlar: tuple[tuple[str, ...], ...]   # sırayla; ilk hata durdurur
    dizin: Path = KOK


GOREVLER: dict[str, Gorev] = {}


def _kaydet(ad: str, aciklama: str, *komutlar: tuple[str, ...], dizin: Path = KOK) -> None:
    GOREVLER[ad] = Gorev(ad, aciklama, komutlar, dizin)


# ── Kurulum ──────────────────────────────────────────────────────────────────
_kaydet(
    "kur", "Bağımlılıklar: pip (çalışma + geliştirme) ve npm ci; commit kancası.",
    (PY, "-m", "pip", "install", "-r", "requirements.txt", "-r", "requirements-dev.txt"),
    (_npm(), "ci", "--prefix", str(FRONTEND)),
    ("bash", "scripts/install-hooks.sh"),
)
_kaydet("goc", "Veritabanı şemasını en son sürüme taşı (alembic upgrade head).",
        (PY, "-m", "alembic", "upgrade", "head"))

# ── Çalıştırma ───────────────────────────────────────────────────────────────
_kaydet("calistir", "Backend geliştirme sunucusu (:8000, --reload).",
        (PY, "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"))
_kaydet("arayuz", "Frontend geliştirme sunucusu (:5173, /api → :8000).",
        (_npm(), "run", "dev"), dizin=FRONTEND)
_kaydet("derle", "Frontend üretim derlemesi (frontend/dist).",
        (_npm(), "run", "build"), dizin=FRONTEND)

# ── Test ─────────────────────────────────────────────────────────────────────
_kaydet("test", "Backend tam süit (pytest, ilk hatada durur).",
        (PY, "-m", "pytest", "tests/", "-q", "-x", "--tb=short", "-p", "no:cacheprovider"))
# Kapı altkümesi pre-commit ile AYNI seçimdir (tests/*_kapisi.py); liste koşum anında üretilir.
_KAPI_TESTLERI = tuple(sorted(str(t.relative_to(KOK)).replace("\\", "/") for t in (KOK / "tests").glob("*_kapisi.py")))
_kaydet("test-hizli", "Yalnız kaynak-türevli kapı testleri (tests/*_kapisi.py, ~2,5 dk).",
        (PY, "-m", "pytest", *_KAPI_TESTLERI, "-q", "-x", "--tb=short", "-p", "no:cacheprovider"))
_kaydet("test-arayuz", "Frontend birim + kaynak-türevli kapılar (vitest).",
        (_npx(), "vitest", "run"), dizin=FRONTEND)
_kaydet("e2e", "Playwright e2e, izole DB ve portlarla (canlı veriye dokunmaz).",
        (PY, "-m", "scripts.e2e_izole"))

# ── Kalite kapıları ──────────────────────────────────────────────────────────
_kaydet("lint", "Lint gerileme sayaçları: ruff (backend) + eslint (frontend).",
        (PY, "scripts/kalite_kapisi.py"),
        (PY, "scripts/eslint_kapisi.py"))
_kaydet(
    "kapilar", "Commit öncesi TÜM kapılar: lint sayaçları, belge denetimi, ölü kod, sır taraması.",
    (PY, "scripts/kalite_kapisi.py"),
    (PY, "scripts/eslint_kapisi.py"),
    (PY, "scripts/belge_denetimi.py"),
    (PY, "scripts/olu_kod_kapisi.py"),
    (PY, "-m", "scripts.sir_taramasi"),
)

# ── İşletim ──────────────────────────────────────────────────────────────────
_kaydet("yedek", "SQLite çevrimiçi yedeği (data/backups/), 30 günden eskisi silinir.",
        (PY, "-m", "scripts.backup"))
_kaydet("durum", "Canlı servis + CI + backlog özet durumu.",
        (PY, "scripts/durum_ozeti.py"))
_kaydet("koc-eval", "Koç kalite ölçümü — davranış seti (gerçek LLM çağrısı, .env gerekir).",
        (PY, "-m", "scripts.eval_runner"))


def _goster(k: tuple[str, ...]) -> str:
    return " ".join(("python" if p == PY else p) for p in k)


def liste() -> str:
    genis = max(len(g.ad) for g in GOREVLER.values())
    satirlar = ["Kullanım: python -m scripts.gorev <görev> [--kuru]", ""]
    for g in GOREVLER.values():
        satirlar.append(f"  {g.ad:<{genis}}  {g.aciklama}")
    return "\n".join(satirlar)


def kostur(ad: str, kuru: bool = False) -> int:
    g = GOREVLER.get(ad)
    if g is None:
        print(f"bilinmeyen görev: {ad!r}\n\n{liste()}", file=sys.stderr)
        return 2
    ortam = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    for k in g.komutlar:
        print(f"$ {_goster(k)}" + (f"   (dizin: {g.dizin.relative_to(KOK) or '.'})" if g.dizin != KOK else ""))
        if kuru:
            continue
        sonuc = subprocess.run(list(k), cwd=str(g.dizin), env=ortam)  # noqa: S603 — sabit komutlar
        if sonuc.returncode != 0:
            print(f"görev '{ad}' durdu: çıkış {sonuc.returncode}", file=sys.stderr)
            return sonuc.returncode
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="FinancialOS görev koşucusu.", add_help=True)
    p.add_argument("gorev", nargs="?", help="görev adı (boşsa liste)")
    p.add_argument("--kuru", action="store_true", help="komutları koşturmadan yazdır")
    p.add_argument("--liste", action="store_true", help="görevleri listele")
    s = p.parse_args(argv)
    if s.liste or not s.gorev:
        print(liste())
        return 0
    return kostur(s.gorev, kuru=s.kuru)


if __name__ == "__main__":
    raise SystemExit(main())
