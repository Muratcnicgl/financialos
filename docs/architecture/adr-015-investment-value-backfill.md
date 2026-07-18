# ADR-015 — Yatırım değeri tarihsel backfill (Wave-2 stratejisi)

**Tarih:** 9 Mayıs 2026 · **Durum:** Kabul edildi · **İlgili:** ADR-012, ADR-014, ADR-019

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`.

## Bağlam
Geçmiş net değer snapshot'ları için yatırım hesaplarının o tarihteki değeri gerekli, ama `Transaction` tablosu yatırım alım/satımını tutmuyor (tipler: income/expense/transfer) ve `Account.purchased_date` yok.

## Karar
`backfill_net_worth.py` `snapshot_for()` fonksiyonunda yatırım değeri `PriceHistory` forward-fill ile hesaplanır. Dört yardımcı:
1. `_get_price_at(fund_code, target_date)` — en yakın `price_date ≤ target_date`, kaynak önceliği manual > tefas > yfinance > isyatirim.
2. `_account_inception_at(account)` — `account.created_at` proxy (purchased_date yok).
3. `_investment_value_at(account, target_date)` — inception kontrolü + forward-fill fiyat + cost_per_lot fallback.
4. Lot count sabit: `account.lot_count` her tarih için (Wave-2 varsayımı).

## Alternatifler (reddedildi)
- Gerçek lot reverse pattern (alım/satım geçmişi) — Wave-3'e ertelendi (InvestmentTransaction tablosu gerekli).

## Gerekçe
YAGNI / Rule of Three: tek yatırım hesabı (TLY), tek alım. Sektör (Sharesight/Portfolio Performance/pandas) forward-fill konsensüsü.

## Kapsam sınırı
TLY `created_at=2026-05-06` — 1-5 May snapshot'ları `current_price` ile dolduruldu (yaklaşık). `cost_per_lot=4125.2333` manuel giriş (gerçek alım fiyatı proxy'si).

## Revize tetikleyicisi
Wave-3: `InvestmentTransaction` tablosu (lot history), `purchased_date` inception, multi-asset (ADR-019).

## Kaynak
MCP `adr_log` [9 Mayıs 2026] + Research Log.
