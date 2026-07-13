"""M24 — .mcp-sync-pending.log'u okunur formatta göster (asistan araci MCP'ye flush eder, sonra temizler)."""
from __future__ import annotations

import sys
from pathlib import Path

LEDGER = Path(".mcp-sync-pending.log")


def main() -> int:
    if not LEDGER.exists() or not LEDGER.read_text(encoding="utf-8").strip():
        print("(bekleyen commit yok)")
        return 0
    lines = [ln for ln in LEDGER.read_text(encoding="utf-8").splitlines() if ln.strip()]
    print(f"{len(lines)} bekleyen commit (MCP FinancialOS Working State'e flush için):")
    for ln in lines:
        parts = ln.split("|", 2)
        if len(parts) == 3:
            h, iso, subj = parts
            print(f"  {h} [{iso[:16]}] {subj}")
        else:
            print(f"  {ln}")
    print("\nFlush sonrası temizle: > .mcp-sync-pending.log")
    return 0


if __name__ == "__main__":
    sys.exit(main())
