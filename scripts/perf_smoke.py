"""
PERFORMANS SMOKE — TEKRARLANABİLİR p50/p95 ÖLÇÜMÜ (BUG #350).

NEDEN VAR
---------
`docs/kalite-seruveni/perf-smoke-m90.md` bir p95 tablosu taşıyor (cockpit p95 19,3 ms,
bütçe < 200 ms) ama **o tablo tekrarlanamıyordu**: depoda onu üreten hiçbir betik yoktu ve
hiçbir test p95 ölçmüyordu. 5 Eylül 2026 denetiminde ölçüldü ve şöyle kaydedildi:
**tekrarlanamayan bir bütçe bütçe değildir** — ihlal edildiğinde kimse öğrenmez (L61'in
performans karşılığı: ölçmek, haber vermek değildir). Bu betik o boşluğu kapatır.

DÜRÜST SINIRLAR (ölçüm neyi söyler, neyi SÖYLEMEZ)
--------------------------------------------------
* `TestClient` + bellek-içi SQLite: **ağ ve disk yok.** Çıkan sayı mutlak bir kullanıcı
  gecikmesi DEĞİL, **uygulama-katmanı hesap maliyetinin** göstergesidir.
* Tek kullanıcı, tek süreç: eşzamanlılık ölçülmez.
* Veri **sentetiktir** ve depoda kişisel veri bırakmaz (gerçek hesap adı/tutarı yok).
* Ölçüm bu makinede yapılır; sayılar makineler arasında kıyaslanamaz. Bu yüzden bütçeler
  gerçek değerin çok üstünde (kat kat) tutulur: kapı **gerçek bir gerilemede** konuşsun,
  makine gürültüsünde değil (L22 — gürültülü kapı okunmaz).

BU YÜZDEN CI'A BAĞLANMADI. Paylaşımlı runner'ların hızı değişkendir; oraya bağlanan bir
p95 kapısı düzenli sahte kırmızı üretir ve okunmaz hâle gelir. Burası bir ÖLÇÜM aracıdır;
bütçe aşımı çıkışı 1'dir, böylece istenirse elle ya da yerel bir kancada kullanılabilir.

KULLANIM
--------
    python scripts/perf_smoke.py                 # ölç ve bütçeye göre karşılaştır
    python scripts/perf_smoke.py --tur 60        # iterasyon sayısı
    python scripts/perf_smoke.py --yaz           # bugünkü ölçümü taban dosyasına yaz
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from datetime import date, timedelta
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))  # `python scripts/perf_smoke.py` ile de koşsun
TABAN_DOSYASI = KOK / "docs" / "kalite-seruveni" / "perf-baseline.json"

# BUG #349 — `app.main` import edildiği an `setup_logging()` koşar ve CANLI betanın
# `logs/financialos.log` dosyasına döner bir handler bağlanır; Windows'ta ikinci bir
# tutucu, canlı uygulamanın rotasyonunu imkânsız kılar ve uygulama sessizce loglamayı
# bırakır. Sunucu OLMAYAN her süreç kendi dizinine yazar.
os.environ.setdefault("LOG_DIR", "logs/arac")
# Ölçüm çıktısı okunabilir kalsın: her istek için INFO satırı basılırsa tablo kaybolur.
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["AUTH_ENABLED"] = "false"
os.environ["SERVE_SPA"] = "0"
os.environ["ENVIRONMENT"] = "development"
os.environ.setdefault("SECRET_KEY", "perf-smoke-icin-kullanilmayan-anahtar-0123456789")
os.environ.pop("SPA_DIST", None)

#: Ölçülen uçlar. `perf-smoke-m90.md`'nin listesiyle aynı — karşılaştırılabilirlik için.
UCLAR = [
    "/api/health",
    "/api/cockpit",
    "/api/accounts",
    "/api/transactions",
    "/api/reports/upcoming-cashflow",
]

#: Bütçe: gerçek değerin kat kat üstü. Amaç gürültüyü değil GERİLEMEYİ yakalamak.
VARSAYILAN_BUTCE_MS = 200.0


def _veri_yukle(session, User, Account, AccountType, Transaction):
    """Sentetik ama gerçekçi bir manzara: 6 hesap + 50 işlem. Kişisel veri YOK.

    Hesap sayısı `perf-smoke-m90.md`'nin manzarasıyla eşleşsin diye 6 tutuldu —
    aksi hâlde 18 Temmuz ölçümüyle kıyaslama elmayla armut olurdu.
    """
    session.add(User(id=1, name="olcum_kullanicisi"))
    session.flush()
    hesaplar = [
        Account(user_id=1, name=f"Olcum Hesabi {n}", account_type=AccountType.cash,
                balance=1_000.0 * (n + 1))
        for n in range(6)
    ]
    for h in hesaplar:
        session.add(h)
    session.flush()
    bugun = date.today()
    for i in range(50):
        session.add(Transaction(
            user_id=1,
            account_id=hesaplar[i % len(hesaplar)].id,
            transaction_type="expense" if i % 3 else "income",
            amount=100.0 + i * 7,
            category="genel",
            description=f"olcum kaydi {i}",
            transaction_date=bugun - timedelta(days=i % 45),
            is_card_expense=False,
        ))
    session.commit()

    # ÖLÇÜM ÜRETİMDEKİ YOLU KOŞMALI. Workspace'i olmayan bir kullanıcı, ürünün
    # ESKİ (legacy user_id) yoluna düşer ve her istekte bir uyarı basar; o hâlde
    # ölçtüğümüz şey gerçek kullanıcının koştuğu yol OLMAZDI (L63/L64'ün performans
    # karşılığı). Backfill KOPYALANMAZ — `scripts/create_personal_workspaces.run()`
    # tek kaynaktır ve workspace'i kurup satırları ona atar.
    from scripts.create_personal_workspaces import run as workspace_backfill
    workspace_backfill(session)
    session.commit()


def olc(tur: int) -> dict[str, dict[str, float]]:
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.dependencies import get_current_user, get_db
    from app.main import app
    from app.models import Account, AccountType, Base, Transaction, User

    motor = create_engine("sqlite:///:memory:",
                          connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(motor)
    session = sessionmaker(bind=motor)()
    _veri_yukle(session, User, Account, AccountType, Transaction)

    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: session.get(User, 1)
    try:
        istemci = TestClient(app)
        sonuc: dict[str, dict[str, float]] = {}
        for uc in UCLAR:
            ilk = istemci.get(uc)
            if ilk.status_code != 200:
                sonuc[uc] = {"durum": float(ilk.status_code)}
                continue
            for _ in range(5):           # ısınma: ilk çağrı import/derleme taşır
                istemci.get(uc)
            olculer = []
            for _ in range(tur):
                t0 = time.perf_counter()
                istemci.get(uc)
                olculer.append((time.perf_counter() - t0) * 1000)
            olculer.sort()
            sonuc[uc] = {
                "p50": round(statistics.median(olculer), 2),
                "p95": round(olculer[min(len(olculer) - 1, int(len(olculer) * 0.95))], 2),
                "n": float(tur),
            }
        return sonuc
    finally:
        app.dependency_overrides.clear()
        session.close()


def _butceler() -> dict[str, float]:
    if TABAN_DOSYASI.exists():
        veri = json.loads(TABAN_DOSYASI.read_text(encoding="utf-8"))
        return {k: float(v) for k, v in veri.get("butce_p95_ms", {}).items()}
    return {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Tekrarlanabilir p50/p95 performans smoke'u.")
    ap.add_argument("--tur", type=int, default=40, help="Uç başına iterasyon (varsayılan 40).")
    ap.add_argument("--yaz", action="store_true", help="Ölçümü taban dosyasına yaz.")
    secenek = ap.parse_args(argv)

    sonuc = olc(secenek.tur)
    butce = _butceler()

    print(f"PERFORMANS SMOKE — {secenek.tur} iterasyon/uç · TestClient + bellek-içi SQLite")
    print("  (ağsız/disksiz: uygulama-katmanı hesap göstergesi, mutlak gecikme DEĞİL)\n")
    print(f"  {'uç':<36} {'p50 ms':>8} {'p95 ms':>8} {'bütçe':>8}")
    asan = []
    for uc, d in sonuc.items():
        if "p95" not in d:
            print(f"  {uc:<36} {'—':>8} {'—':>8}   HTTP {int(d['durum'])} (atlandı)")
            continue
        sinir = butce.get(uc, VARSAYILAN_BUTCE_MS)
        bayrak = "" if d["p95"] <= sinir else "  ← BÜTÇE AŞILDI"
        if bayrak:
            asan.append(uc)
        print(f"  {uc:<36} {d['p50']:>8.2f} {d['p95']:>8.2f} {sinir:>8.0f}{bayrak}")

    if secenek.yaz:
        TABAN_DOSYASI.write_text(json.dumps({
            "olculdu": date.today().isoformat(),
            "not": ("Bu sayılar ÖLÇÜLDÜĞÜ makineye aittir; makineler arası kıyaslanmaz. "
                    "Bütçeler gürültüyü değil gerilemeyi yakalamak için kat kat üstte tutulur."),
            "olcum": sonuc,
            "butce_p95_ms": {uc: (butce.get(uc, VARSAYILAN_BUTCE_MS)) for uc in sonuc},
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\ntaban yazıldı: {TABAN_DOSYASI.relative_to(KOK).as_posix()}")

    if asan:
        print(f"\nBÜTÇE AŞILDI: {', '.join(asan)}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
