# ADR-021 — Cashflow Forecast Engine (Wave-2 H2G1-2)

**Tarih:** 16 Mayıs 2026 (+ REV 1-3, FINAL) · **Durum:** Kabul edildi + KAPALI · **İlgili:** ADR-019, ADR-022, BUG #058

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log` (5 observation: ana karar + 3 revizyon + final).

## Bağlam
Kullanıcıya gelecek nakit akışını (running balance + crunch günleri + Sankey) göstermek. Sektör: PocketSmith (flag system), Monarch (Sankey + scenario), Quicken Simplifi, Buxfer (alert-driven), Cube 2026 raporu.

## Karar (5 alt karar)
- **(a) Horizon:** 30/60/90 gün toggle, default 60.
- **(b) Crunch eşiği:** kullanıcı tanımlı, hesap başına, default 0 (banka < eşik tetikler).
- **(c) Sankey yönü:** yatay (Recharts native, gelir→hesap→kategori 3 sütun).
- **(d) Recurring + one-off:** hepsi varsayılan dahil + filter chip toggles.
- **(e) Yatırım hesap forecast dışında:** cash/credit_card/checking dahil, investment Wave-2'de DAHİL DEĞİL (ADR-019'a ertelendi).

**Veri modeli:** Yeni tablo YOK — forecast runtime'da hesaplanır. **Endpoint:** `GET /api/cashflow/forecast`. **Sankey kütüphanesi:** Recharts `<Sankey>` built-in (0kb ek bağımlılık; ADR-001 ilkesi "explicit > implicit" ile uyumlu). **Running balance:** anchor = bugün actual, events horizon içine expand, günlük opening→inflows-outflows→closing, crunch = closing < threshold.

## Alternatifler (reddedildi)
- 60 sabit horizon (sektörle çelişir); balance<0 hard crunch (geç uyarı); dikey Sankey; sadece recurring; yatırım dahil (mark-to-market volatilitesi forecast'i kirletir).

## Revizyonlar
- **REV 1:** `Transaction.due_date` YOK (PersonalDebt'te) → scheduled_tx event tipi çıkarıldı. Mevcut `/api/reports/upcoming-cashflow` DOKUNULMADI; yeni `/api/cashflow/forecast` ayrı (single-responsibility). UI: yeni tab "Akış".
- **REV 2 (FINAL):** Uygulama tamamlandı — `app/cashflow.py`, `app/routers/cashflow.py`, 12 test PASS. Frontend: Cashflow.jsx + BalanceTrend + CashflowCalendar + CashflowSankey + CashflowSummary. 8. tab oldu (Reports zaten 5.).
- **REV 3 (BUG #058):** Loan taksiti KAPSAMA ALINDI — Account.next_payment_date + monthly_payment + remaining_installments zaten mevcut. Kart taksiti (MC3 Ziraat döngüsü karmaşık) Wave-3'te kalır.

## Revize tetikleyicisi
6 hafta kullanım: horizon 90 üstü (PocketSmith plan-tabanlı); ML crunch threshold; cache (Redis/SQLite TTL).

## Kaynak
MCP `adr_log` [16 Mayıs 2026], commit'ler 2acdae9 + bff14d3 + 38491d7.
