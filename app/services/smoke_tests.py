"""
M37 (Wave-4) — Dış API canlı smoke test framework.

Ders 11 (dersler-gemini.md): "pytest yeşil ≠ canlı çalışıyor". M19 EVDS regression'ı
mock test yeşilken endpoint ölüydü (EVDS v2→v3 taşınmış, kod fark etmedi). Bu modül her
dış API için GERÇEK (mock-suz) bir smoke kontrolü yapar; haftalık scheduler job (pazartesi
05:00) çalıştırır ve başarısızlıkları `.mcp-sync-pending.log` ledger'ına `SMOKE_FAIL:<api>`
satırı olarak YAKALAR (M24 capture→flush deseni — scheduler MCP'ye doğrudan yazamaz, Claude
Code oturum başında flush eder).

Her smoke fonksiyonu {"api","ok","detail"} döner. Ağ/yapılandırma hatası ok=False + detail;
akışı asla exception ile bozmaz (dış bağımlılık kontrolsüz).

canli-dogrulama-gate manuel tetik: python -m app.services.smoke_tests
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# capture→flush ledger'ı (M24 post-commit ile aynı dosya, gitignore'da)
_LEDGER = Path(".mcp-sync-pending.log")


def smoke_evds() -> dict:
    """TCMB EVDS v3 döviz — gerçek USD kuru çekilebiliyor mu (buy/sell dolu)."""
    api = "EVDS"
    try:
        from app.price_providers.evds_client import fetch_currency_rate
        rate = fetch_currency_rate("USD")
        if not rate or (rate.get("buy") is None and rate.get("sell") is None):
            return {"api": api, "ok": False,
                    "detail": "USD kuru boş döndü (EVDS_API_KEY eksik veya endpoint erişilemedi)"}
        return {"api": api, "ok": True,
                "detail": f"USD buy={rate.get('buy')} sell={rate.get('sell')} date={rate.get('date')}"}
    except Exception as e:  # noqa: BLE001
        return {"api": api, "ok": False, "detail": f"exception: {str(e)[:150]}"}


def smoke_smtp() -> dict:
    """Brevo SMTP — bağlantı + STARTTLS + login (mesaj GÖNDERMEZ, sadece auth doğrular)."""
    api = "SMTP"
    try:
        from app.services.email import _smtp_config, smtp_configured
        if not smtp_configured():
            return {"api": api, "ok": False, "detail": "SMTP yapılandırılmamış (SMTP_HOST/USER/PASS/FROM)"}
        import smtplib
        cfg = _smtp_config()
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as s:
            s.starttls()
            s.login(cfg["user"], cfg["password"])
        return {"api": api, "ok": True, "detail": f"login OK {cfg['host']}:{cfg['port']}"}
    except Exception as e:  # noqa: BLE001
        return {"api": api, "ok": False, "detail": f"exception: {str(e)[:150]}"}


def smoke_oauth(provider: str) -> dict:
    """OAuth (google/github) — credential yapılandırılmış + auth URL doğru provider host'una gidiyor mu.

    Ağ çağrısı yapmaz (login akışı redirect'tir); yapılandırma + URL üretimini doğrular.
    """
    api = f"OAuth-{provider}"
    try:
        from app.services import oauth as oauth_mod
        if not oauth_mod.provider_configured(provider):
            return {"api": api, "ok": False, "detail": f"{provider} credential eksik (CLIENT_ID/SECRET)"}
        url = oauth_mod.get_auth_url(provider, oauth_mod.new_state())
        expected = {"google": "accounts.google.com", "github": "github.com"}.get(provider, provider)
        if expected not in url:
            return {"api": api, "ok": False, "detail": f"auth URL beklenen host içermiyor: {url[:80]}"}
        return {"api": api, "ok": True, "detail": f"auth URL -> {expected}"}
    except Exception as e:  # noqa: BLE001
        return {"api": api, "ok": False, "detail": f"exception: {str(e)[:150]}"}


def run_all_smoke_tests() -> list[dict]:
    """Tüm dış API smoke testlerini çalıştır, sonuç listesi döner."""
    return [
        smoke_evds(),
        smoke_smtp(),
        smoke_oauth("google"),
        smoke_oauth("github"),
    ]


def capture_smoke_failures(results: list[dict], ledger: Path = _LEDGER) -> int:
    """Başarısız smoke'ları ledger'a SMOKE_FAIL satırı olarak yakala (M24 capture→flush).

    Döner: yakalanan başarısızlık sayısı. Ledger yazımı hata verirse akış bozulmaz.
    """
    fails = [r for r in results if not r.get("ok")]
    if not fails:
        return 0
    try:
        with ledger.open("a", encoding="utf-8") as f:
            for r in fails:
                # M24 formatı: <marker>|<iso-yok>|<mesaj> — flush raporu 3-parça bekler
                f.write(f"SMOKE_FAIL|smoke|{r['api']}: {r['detail']}\n")
    except Exception:  # noqa: BLE001
        logger.exception("[smoke] ledger yazımı başarısız")
    return len(fails)


def main() -> int:
    """CLI canli-dogrulama-gate tetik: her API için ok/fail yazdırır."""
    results = run_all_smoke_tests()
    fails = 0
    for r in results:
        mark = "[OK]  " if r["ok"] else "[FAIL]"  # Windows cp1254 console emoji basamaz
        print(f"{mark} {r['api']}: {r['detail']}")
        if not r["ok"]:
            fails += 1
    print(f"\n{len(results) - fails}/{len(results)} smoke geçti.")
    return 1 if fails else 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
