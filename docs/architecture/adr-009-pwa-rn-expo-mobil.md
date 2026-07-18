# ADR-009 — PWA → RN+Expo mobil yol haritası

**Tarih:** 8 Mayıs 2026 · **Durum:** Kabul edildi · **İlgili:** ADR-032 (mobil platform, Wave-4)

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`.

## Bağlam
Mobil erişim gerekli ama tek adımda native uygulama maliyetli. Backend FastAPI korunmalı.

## Karar
Aşamalı: **PWA önce** (Wave-2 sonu, 1-2 hafta) → **RN+Expo sonra** (Wave-3, 4-6 ay). Backend FastAPI korunur; yalnız auth + sync için modernize edilir.

## Alternatifler (reddedildi)
- Sadece responsive web (native deneyim yok).
- Sadece RN (PWA'nın hızlı kazanımı kaçırılır).

## Gerekçe
PWA hızlı kazanım verir; RN+Expo native deneyimi sonra ekler. Backend değişmediği için risk düşük.

## Revize tetikleyicisi
Wave-4'te ADR-032 mobil platform kararı bu yol haritasını netleştirir/günceller.

## Kaynak
MCP `adr_log` [8 Mayıs 2026]. Detay: `docs/architecture/mobile-roadmap.md`.
