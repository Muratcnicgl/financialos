# ADR-024 — Goal Engine kapsam daraltma (4 tip → 2 tip)

**Tarih:** 17 Mayıs 2026 · **Durum:** Kabul edildi (Murat onayladı) · **İlgili:** ADR-019, ADR-022, ADR-023, ADR-025

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`.

## Bağlam
Plan v3 4 hedef tipi istiyordu: debt_freedom + cash_target + net_worth + investment.

## Karar
Yalnız **2 tip** uygulanır:
- **debt_freedom** (pay-down arketipi, balance → 0),
- **cash_target** (save-up arketipi, balance → target).

**net_worth** ve **investment** Wave-3'e ertelendi.

## Alternatifler (reddedildi)
- B) 4 tip Plan'a tam sadık — 2 tip placeholder = mimari borç.
- C) 3 tip (net_worth manuel mod) — ADR-022 ihlali riski.

## Gerekçe
- **Teknik:** net_worth projeksiyon gerektirir; ADR-022'nin T+1095 reddetme gerekçesi (TL enflasyon, TLY fiyat sabit varsayılamaz) bu hedef için de geçerli. investment multi-asset balance sheet'e bağlı (ADR-019 Wave-3); tek varlık TLY ile yazıp migration DRY ihlali.
- **D1 BENİ DÜŞÜN:** net değer −22.274 TL, MC8 "Hayatta Kalma > Yatırım", MC1 Emanet TLY kullanıcının parası değil. net_worth/investment hedefi psikolojik ters etki.
- **Sektör (Monarch):** "pay-down goal" + "save-up goal" temel arketip ikilisi MVP standardı.
- ADR-023 ile aynı muhakeme (gerçek veri koşulu Plan'dan sapma gerekçesi). Murat 17 May 2026 onayladı.

## Revize tetikleyicisi
Wave-3 multi-asset (ADR-019) + enflasyon-aware projeksiyon tamamlanınca net_worth + investment eklenir.

## Kaynak
MCP `adr_log` [17 Mayıs 2026], Plan v3 H2G5. Not: ADR-025 (Goal Engine, 20 May) bu kararı allocation-based pattern ile uyguladı.
