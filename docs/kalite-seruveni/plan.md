# FinancialOS Kalite & Gelişim Master Planı

**Sahip:** Otonom ajan (tam yetki). **İlke:** araştır → teyit et → uygula → doğrula → öz-kontrol. Halüsinasyon/varsayım/tembellik/dalkavukluk YOK. Her adım kök vizyona (`origin-vision.md`) ve 7 meta-derse (`dersler-gemini.md`) hizmet eder.

## Yürütme protokolü (her değişiklikte)
1. **Teyit:** iddiayı gerçek kodla/çalıştırarak doğrula (sim/test), varsayma.
2. **Uygula:** BUG #NNN konvansiyonu (GUNCELLEMELER docstring + inline yorum, sıralı numara). Backlog ID'sini (`[RULE-001]`) referansla.
3. **Doğrula:** import/test/çalıştır — davranışı gözlemle.
4. **Öz-kontrol:** talep karşılandı mı + kalite yeterli mi; değilse tekrar araştır.
5. **Backlog/ADR güncelle:** durum + ders.

## Faz 0 — Analiz (BÜYÜK ORANDA BİTTİ)
- ✅ Dimension audit: 520 madde (`sections/`).
- ⏳ Per-file audit: 36 backend dosyası (çalışıyor) → sonra 33 frontend + 5 script.
- ✅ Kök vizyon (`origin-vision.md`) + dersler (`dersler-gemini.md`) + ADR-026 (zikzak).

## Faz 1 — Konsolidasyon & önceliklendirme
- Dimension + per-file bulgularını birleştir, tekilleştir, P0/P1/P2 ata.
- "Canlı bug" listesi (doğrulanmış) ayrı; P0.

## Faz 2 — P0 doğruluk sprinti ("sıfır hata" vizyonu)
Finansal matematik hataları — kök vizyonun "kusursuzluk" talebinin karşılığı:
- ✅ RULE-001 (BUG #059) · ✅ DATA-003/004 (BUG #060) · ✅ ADR-026 (zikzak)
- RULE-002 (kart min ödeme sabit), RULE-003/004/005 (kart döngüsü tarih), RULE-006/035/040 (float→Decimal para), RULE-016/017/018/019 (cashflow/simülasyon taksit-faiz), RULE-020 (kategori pencere).
- Her biri: yanlış-sonuç senaryosu ile teyit → fix → test.

## Faz 3 — Temel güvenlik ağı (refactor'ları güvenli kılar)
- pytest + in-memory izolasyon + **FakeProvider** (TEST-005/006/012) → MC enforcement + is_question + postprocess için deterministik test.
- `Settings` (pydantic-settings, BE-012) · merkezî exception handler (BE-009/API-004).

## Faz 4 — Vizyon-kritik özellikler (meta-derslere kod-seviyesi enforce)
- **LLM-003 grounding check** — LLM'in söylediği sayı cockpit ile eşleşmeli (meta-ders 1+2: LLM matematiğe güvenme + varsayım yasak). **En yüksek vizyon değeri.**
- **Structured output** (LLM-009/020) — kırılgan regex postprocess'i emekliye ayır (meta-ders 4: kırılgan format).
- **Gölge muhasebe sağlamlaştırma** (RULE-027) + **harcama günü tavanı** (ADR-026 sonraki adım, zikzak lump).
- KURAL SIFIR sağlamlaştırma (is_question LLM-010/BE-027).

## Faz 5 — Devrimsel adımlar (araştırma-güdümlü, kopyalamadan)
Piyasa (YNAB, Actual, Monarch, Copilot, Maybe, Rocket) + akademi incelenip, FinancialOS'in ÖZGÜN vizyonuna (egemenlik + realist strateji + zikzak/gölge muhasebe) katkı sağlayacak, kopya olmayan sıçramalar. Adaylar (araştırmayla doğrulanacak):
- **Egemenlik (V2):** yerel LLM (Ollama/Qwen) seçeneğini fallback zincirine ekle — kök vizyonun "Sovereign OS" ideali; gizlilik + kotasızlık.
- **Agentic proaktif koç:** gün sonu/vade proaktif ritüeli (KURAL SIFIR'ı bozmadan, öneri olarak).
- **Grounding + structured output** ile "sıfır-halüsinasyon finansal rapor" — pazarda AI-koçların zayıf noktası.
- (Faz 5 detayı Faz 1-4 sonrası araştırmayla netleşecek.)

## Durum tablosu
| Faz | Durum |
|-----|-------|
| 0 Analiz | Büyük oranda bitti (per-file sürüyor) |
| 1 Konsolidasyon | Sıradaki (per-file bitince) |
| 2 P0 doğruluk | Başladı (3 fix) |
| 3 Güvenlik ağı | Bekliyor |
| 4 Vizyon özellikleri | Bekliyor |
| 5 Devrimsel | Araştırma başladı |
