# ADR-032 — Mobil platform (PWA vs React Native+Expo)

**Tarih:** 13 Tem 2026 · **Durum:** 🟡 TASLAK — karar Wave-3 başında (M7 hazırlık, KARAR YOK) · **İlgili:** mobile-roadmap.md

## Bağlam
Web'i (React+Vite+Tailwind) koruyarak mobil-first. Backend REST → herhangi bir istemci tüketebilir. `mobile-roadmap.md`'de 3 yol analiz edildi.

## Açık Sorular (KARAR BEKLİYOR)
1. **PWA** (service worker+manifest, kod %95 korunur, 2-4 hafta, App Store yok) **vs RN+Expo** (native his, ayrı kod tabanı, Expo Router)?
2. **Offline-first** gerekli mi? (SQLite lokal cache + sync).
3. **Push notification** (vade/kesim hatırlatma) — PWA'da iOS kısıtlı, RN native.
4. **Geliştirme akışı:** PWA mevcut akışı (asistan araci+uvicorn) korur; RN yeni toolchain.

## D1 (Wave-3'te yapılacak) → Research Log
iOS Safari PWA capability 2026 (push, install), Expo Router olgunluğu, PWA vs native retention verileri.

## Karar
**(BOŞ — Wave-3 başında D1 sonrası. Charter: "araştır, KARAR VERME".)**

## Kaynak
mobile-roadmap.md, wave-3-master-plan.md §2.
