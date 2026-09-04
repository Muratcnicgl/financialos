"""
CANLI ERİŞİLEBİLİRLİK RAPORU (Wave-Y / Y2) — "son 7 günün yüzdesi" şartı.

    python -m scripts.erisilebilirlik_raporu
    python -m scripts.erisilebilirlik_raporu --gun 30

VERİ KAYNAĞI: `logs/erisilebilirlik.csv`
----------------------------------------
`deploy/windows/saglik.ps1` HER koşumda (10 dakikada bir) tek satır yazar:
`zaman_utc,saglikli`. Rapor bu kaydı okur.

**İlk tasarım GitHub Actions koşum geçmişini okuyordu ve Y2'nin tasarımı değişince
veri kaynağı boşta kaldı** (cron kaldırıldı — bkz. `.github/workflows/canli-izleme.yml`).
Bu sürüm üçüncü tarafa hiç bağlı değil.

KAYIP SATIR DA VERİDİR — RAPORUN KALBİ BURASI
----------------------------------------------
Görev 10 dakikada bir koşar. Yani 7 gün için **beklenen slot sayısı 1.008**'dir.
Makine kapalıyken / görev bozukken satır YAZILMAZ. Eğer yalnız yazılmış satırlara
bakılsaydı, makinenin kapalı olduğu gece **hiç gözlem üretmez** ve rapor o günü
"%100 sağlıklı" gösterirdi — ölçmediğini mükemmel sanmak (L45).

Bu yüzden payda **beklenen slot**, pay **sağlıklı kayıt**tır:

    erişilebilirlik = saglikli_kayit / beklenen_slot

Kayıp slotlar kesinti sayılır. Bu, kullanıcının gördüğü gerçekle aynıdır: makine
kapalıyken site de kapalıdır (Wave-Y/Y2 kararı (a) — bkz. `wave-y-ledger.md`).

KABUL EDİLEN SINIR (yazılı, incelenmemiş varsayım değil)
--------------------------------------------------------
Alarm kanalı üçüncü taraf bir ölü-adam-anahtarı servisidir. **O servis kendisi ölürse
kimse haber vermez.** Bu bilinçli olarak kabul edilmiştir: bir SaaS'ın ölme olasılığı,
ev bilgisayarının kapanma olasılığından kat kat düşüktür ve bu raporun kendisi (yerel
kayda dayandığı için) o servisten bağımsız ikinci bir gözdür.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
KAYIT = KOK / "logs" / "erisilebilirlik.csv"
#: `gorevleri_kur.ps1` sağlık görevini 10 dakikada bir koşturur.
PERIYOT_DK = 10


def _oku(gun: int) -> list[tuple[datetime, bool]]:
    if not KAYIT.exists():
        return []
    sinir = datetime.now(timezone.utc) - timedelta(days=gun)
    satirlar: list[tuple[datetime, bool]] = []
    # `utf-8-sig`: PowerShell'in `Add-Content -Encoding UTF8`u dosya başına BOM koyar.
    # Düz `utf-8` ile okunduğunda ilk başlık `﻿zaman_utc` oluyor, `zaman_utc` anahtarı
    # bulunamıyor ve rapor GERÇEK ÖLÇÜMÜ "ölçüm yok" diye raporluyordu — sessizce (ölçüldü).
    with KAYIT.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                t = datetime.strptime(r["zaman_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=timezone.utc)
            except (KeyError, ValueError, TypeError):
                continue
            if t >= sinir:
                satirlar.append((t, str(r.get("saglikli", "")).strip() == "1"))
    return satirlar


def _kesintiler(satirlar: list[tuple[datetime, bool]], bosluk_dk: int) -> list[tuple]:
    """Ardışık kayıtlar arasındaki `bosluk_dk`'dan uzun boşluklar + sağlıksız aralıklar."""
    olaylar: list[tuple] = []
    onceki: datetime | None = None
    for t, ok in satirlar:
        if onceki is not None:
            fark = (t - onceki).total_seconds() / 60
            if fark > bosluk_dk:
                olaylar.append((onceki, t, fark, "kayit yok (makine kapali / gorev olu)"))
        if not ok:
            olaylar.append((t, t, PERIYOT_DK, "saglik BASARISIZ"))
        onceki = t
    return olaylar


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Canli erisilebilirlik raporu (Wave-Y/Y2)")
    ap.add_argument("--gun", type=int, default=7)
    ap.add_argument("--bosluk-dk", type=int, default=PERIYOT_DK * 3,
                    help="bu kadar dakikadan uzun kayit bosluklari kesinti sayilir")
    a = ap.parse_args(argv)

    satirlar = _oku(a.gun)
    print(f"=== CANLI ERISILEBILIRLIK — son {a.gun} gun ===")
    # `relative_to` KOK dışındaki bir yol için ValueError atar (test geçici dizini gibi).
    # Bir raporun BAŞLIK satırı, raporu çökertemez (L66: hata yolu başarı yolundan dayanıklı).
    try:
        kaynak = KAYIT.relative_to(KOK).as_posix()
    except ValueError:
        kaynak = str(KAYIT)
    print(f"  kaynak: {kaynak}")

    beklenen = int(a.gun * 24 * 60 / PERIYOT_DK)

    if not satirlar:
        # L45: sıfır gözlem %100 DEĞİLDİR.
        print(f"  OLCUM YOK — bu donemde hic kayit yok (beklenen ~{beklenen} slot).")
        print("  Bu %100 DEGILDIR: saglik gorevi hic kosmamis ya da kayit yeni acilmis")
        print("  olabilir. Gorev durumu: .\\deploy\\windows\\gorevleri_kur.ps1 -Durum")
        return 2

    saglikli = sum(1 for _, ok in satirlar if ok)
    # İlk kayıttan bu yana geçen süre, istenen pencereden kısa olabilir (kayıt yeni açıldı).
    ilk = min(t for t, _ in satirlar)
    gecen_dk = (datetime.now(timezone.utc) - ilk).total_seconds() / 60
    kapsanan = max(1, int(min(gecen_dk, a.gun * 24 * 60) / PERIYOT_DK))

    print(f"  kayit      : {len(satirlar)}  (saglikli {saglikli} · basarisiz "
          f"{len(satirlar) - saglikli})")
    print(f"  beklenen   : {kapsanan} slot ({PERIYOT_DK} dk'da bir; kayit basi {ilk:%Y-%m-%d %H:%M}Z)")
    print(f"  ERISILEBILIRLIK: %{100.0 * saglikli / kapsanan:.2f}"
          f"   ({saglikli}/{kapsanan} — KAYIP SLOT KESINTI SAYILIR)")

    if len(satirlar) < kapsanan:
        print(f"  kayip slot : {kapsanan - len(satirlar)} "
              "(makine kapali / gorev olu — kullanicinin gordugu de budur)")

    olaylar = _kesintiler(satirlar, a.bosluk_dk)
    if olaylar:
        print("\n  KESINTILER:")
        for bas, _bit, dk, neden in olaylar[:15]:
            print(f"    {bas:%Y-%m-%d %H:%M}Z  ~{dk:.0f} dk  {neden}")
        if len(olaylar) > 15:
            print(f"    … ve {len(olaylar) - 15} tane daha")
    else:
        print("\n  Kesinti yok.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
