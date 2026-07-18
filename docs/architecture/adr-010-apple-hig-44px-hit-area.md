# ADR-010 — Apple HIG 44px hit area (global .btn class)

**Tarih:** 8 Mayıs 2026 · **Durum:** Kabul edildi · **İlgili:** BUG #052, BUG #054

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`.

## Bağlam
Dokunmatik hedef alanları Apple HIG'in önerdiği 44px'in altındaydı (BUG #052, #054) — mobilde tıklanması zor butonlar.

## Karar
Global `.btn` class + `.btn-icon` (44×44px) — Apple HIG 44px hit area standardı CSS seviyesinde global uygulanır.

## Alternatifler (reddedildi)
- Component bazlı tek tek fix — kalıcı değil, yeni butonlar yine küçük çıkar.

## Gerekçe
Global CSS class kalıcı; gelecekteki butonlar otomatik 44px alır.

## Kaynak
MCP `adr_log` [8 Mayıs 2026]. Uygulama: `frontend/src/` global CSS.
