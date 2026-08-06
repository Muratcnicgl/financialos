"""
M24 — `.mcp-sync-pending.log` durumu (capture→flush ledger'ı).

GUNCELLEMELER
- BUG #255 fix (7 Agu 2026): script HER durumda 0 donuyordu — yani "186 commit birikmis"
  ile "hic birikme yok" ayni cikis kodunu veriyordu. Hep-basarili arac, olculmeyen
  aractir (L28: "cokmedim" basari degildir; BUG #248 ile ayni sinif). Artik esik asilinca
  **2** doner ve ne yapilmasi gerektigini yazar.
- 7 Agu 2026 KARAR (master rapor YANILGI-1): MCP knowledge graph **tek gercek kaynak
  DEGIL**, statusu *4 May – 18 Tem 2026 tarihsel arsivi*. Guncel durumun kaynagi repo +
  `docs/kalite-seruveni/master-durum-raporu-2026-08-06.md`. Bu yuzden bu ledger'in isi
  "MCP'yi guncel tutmak" degil, **birikmenin gorunur olmasi**: esik asilirsa ya flush
  yapilir ya da ledger bilincli olarak temizlenir; sessizce buyumesi yasak.

Kullanim:
    python -m scripts.mcp_sync_report            # rapor + esik kontrolu
    python -m scripts.mcp_sync_report --temizle  # ledger'i bosalt (bilincli karar)
"""
from __future__ import annotations

import sys
from pathlib import Path

LEDGER = Path(".mcp-sync-pending.log")

# Esik: bu sayinin ustunde birikme "sessiz cusme" sayilir. 50, bir calisma gununun
# ustu (en yogun gun 103 commit'ti) — gunluk ritmi bogmadan birikmeyi yakalar.
ESIK = 50

KARAR_NOTU = (
    "MCP STATUSU (7 Agu 2026 karari): graph TARIHSEL ARSIV'dir (4 May - 18 Tem 2026).\n"
    "Guncel durum kaynagi: repo + docs/kalite-seruveni/master-durum-raporu-2026-08-06.md\n"
    "Bu ledger'in amaci MCP'yi guncel tutmak DEGIL, birikmeyi GORUNUR kilmaktir."
)


def satirlari_oku() -> list[str]:
    if not LEDGER.exists():
        return []
    return [ln for ln in LEDGER.read_text(encoding="utf-8").splitlines() if ln.strip()]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if "--temizle" in argv:
        LEDGER.write_text("", encoding="utf-8")
        print("ledger temizlendi (bilincli karar).")
        return 0

    lines = satirlari_oku()
    if not lines:
        print("(bekleyen commit yok)")
        return 0

    print(f"{len(lines)} bekleyen commit (esik: {ESIK}):")
    for ln in lines:
        parts = ln.split("|", 2)
        if len(parts) == 3:
            h, iso, subj = parts
            print(f"  {h} [{iso[:16]}] {subj}")
        else:
            print(f"  {ln}")

    print()
    print(KARAR_NOTU)

    if len(lines) > ESIK:
        # BUG #255: sessiz buyume artik cikis koduyla bildirilir.
        print(f"\nKIRMIZI: ledger {len(lines)} satir — esigi ({ESIK}) asti.")
        print("Karar ver: (a) MCP'ye flush et, ya da (b) `--temizle` ile bilincli kapat.")
        return 2

    print(f"\nYESIL: birikme esigin ({ESIK}) altinda.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
