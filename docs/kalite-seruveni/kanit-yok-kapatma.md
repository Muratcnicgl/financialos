# KANIT YOK Kapatma Eki (M78, Wave-5 — 18 Tem 2026)

`tam-proje-durum-raporu.md` R3 disipliniyle yazıldı: kanıt bulunamayan yerde **KANIT YOK** yazıldı.
M78 o boşlukları güncel diskten topladı. Rapor (tarihsel snapshot) DEĞİŞTİRİLMEDİ; kapatmalar burada.

## Yeni R3 kanıtıyla kapatılanlar (M78 turu)

| Rapor satırı | KANIT YOK konusu | M78 KANITI | Durum |
|---|---|---|---|
| 348 | Stopaj nerede implement? | `simulation_engine.py:231` `withholding = max(0,profit)*0.175` (%17.5). `rules_engine.py:366` K/Z brüt (stopajsız). | ✅ KAPANDI |
| 372 | Hangi provider cevaplıyor? | `provider_used` alanı loglanıyor (`coach.py:1214,1279` — `provider_used=self.NAME.lower()`). Artık ölçülebilir. | ✅ KAPANDI (mekanizma var) |
| 378 | V3 prompt bölüm başlıkları | UTF-8 ile çıkarıldı (11.926 kr): KURAL SIFIR / KARAKTER / KURALLAR / RAPOR FORMATI (5 alt-bölüm: Stratejik Analiz, Kokpit, Harekat Planı, Tehdit-Fırsat, Emanet) / Deterministik Veri. | ✅ KAPANDI |
| 383 | Prompt CoachInsight'ları OKUYOR MU? | **EVET** — `coach.py:1149-1152` `format_insights_for_prompt(db, user_id, 1500)` → context'e ekleniyor. **"Dead code" şüphesi ÇÜRÜK** (ADR-020 enjeksiyonu canlı). | ✅ KAPANDI |
| 386 | CoachInsight status kırılımı | Canlı: **14 active + 3 dormant = 17** (invalidated 0). | ✅ KAPANDI |
| 389 | Yetim trace (olmayan user) temizlendi mi? | Canlı: mevcut user_id={1}, **yetim trace = 0** (79 trace hepsi user 1). | ✅ KAPANDI |
| 546-548 | reasoning_traces / coach_insights sayı | ReasoningTrace **79**, CoachInsight **17** (canlı). | ✅ KAPANDI |
| 767/1041 | README içerik doğruluğu | `README.md` gerçek: başlık + rozet + kurulum komutları (alembic/uvicorn/pip/npm — 4 blok). İçerik geçerli. | ✅ KAPANDI |
| 906/907 | requirements-dev / package.json | `requirements-dev.txt` 5 satır VAR. `frontend/package.json`: vitest 4.1.10, @testing-library/react 16.3.2, jest-dom 6.9.1, jsdom 25.0.1. | ✅ KAPANDI |

## Wave-5 önceki milestone'ları (M70-M77) tarafından zaten kapatılanlar

| Rapor satırı | KANIT YOK konusu | Kapatan milestone |
|---|---|---|
| 663 | sections/ gerçek stale oranı (tam sayı) | **M76** — RULE boyutu tam doğrulandı: %42 stale ölçüldü (`sections/DURUM-INDEX.md`). |
| 667 | dosya-denetimi/ güncellik | **M77** — 75 rapor banner'landı + örneklem 2/2 stale (`dosya-denetimi/GUNCELLIK-INDEX.md`). |
| 982 | rules_engine `filter_by(user_id` scope | **M70/M71** — scope AST tarayıcısı rules_engine dahil; fonksiyon-düzeyi izolasyon testleri. |
| 985 | IMPROVEMENT #029 (AST scanner) diskte yok | **M70** — tarayıcı `tests/test_scope_enforcement.py` olarak uygulandı. |
| 516/810 | frontend try/catch + console hatası | **M67** — 13 panel console-sweep, 0 hata (`milestone-67`). |

## Kalan (bilinçli — başka milestone/kapsam)

| Rapor satırı | Konu | Neden açık |
|---|---|---|
| 803/1041 | `docker-compose config` koşturulmadı | **M80** işi (Docker Compose lokalde ayağa). |
| 426/451 | yfinance / BIST canlı test | Dış-API + bu env'de Yahoo blok (ADR-031 R3: graceful None). Kapsam dışı (Wave-5 KAPSAM DIŞI: kripto/multi-asset genişletme). |
| 916 | OAuth Google Console test-mode | Google Console'a erişilemez (dış panel); `odeme-bekleyen-kararlar.md` #3 test-mode teyit ediyor. Elle-görev (KURAL 3 istisnası). |
| 694/697 | disk açık-bug listesi / yeniden-açılan bug | Bug arşivi MCP `Bug Archive`'da (disk değil); yapısal, M79+ değil Wave-6 bug-hijyeni. |

## Özet
Raporun ~25 KANIT YOK maddesinden: **9'u M78'de yeni R3 kanıtıyla**, **5'i M70-M77 milestone'larında** kapatıldı;
**4'ü bilinçli açık** (M80 / dış-panel / kapsam-dışı). En kritik çürütme: **RE-383 "prompt insight'ları okumuyor
(dead code)" şüphesi YANLIŞ** — `format_insights_for_prompt` canlı enjekte ediyor.
