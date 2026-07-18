# Tam Süit + Performans Smoke (M90, Wave-6 — 18 Tem 2026)

## 1. Flaky kontrolü — 3× tam süit
| Koşum | Sonuç | Süre |
|---|---|---|
| 1/3 (--durations) | 1235 passed, 1 skipped | 43.4s |
| 2/3 | 1235 passed, 1 skipped | 44.0s |
| 3/3 | 1235 passed, 1 skipped | 45.1s |

**FLAKY YOK** — 3 koşumda da aynı 1235 passed / 1 skipped. Deterministik (in-memory DB + FakeProvider +
sabit `today` enjeksiyonu). 1 skipped bilinçli (tek atlanan test).

## 2. En yavaş 10 test
Hepsi **property-based (hypothesis)** testler — çok sayıda örnek ürettikleri için 1-2s; makul, optimizasyon gerekmez:
| Süre | Test |
|---|---|
| 1.99s | test_metric_properties::test_generate_cockpit_daima_finite |
| 1.59s | test_coach_providers_wave3::test_fallback_zinciri |
| 1.56s | test_card_utilization::test_utilization_invariantlari |
| 1.32s | test_debt_metric_properties::test_opportunity_cost |
| 1.25s | auth/test_auth::test_rate_limit_login (rate-limit bekleme) |
| 1.17s | test_next_action::test_recommend_next_action_asla_cokmez |
| 0.90s | test_actions_lifecycle::test_approve_uygular_ve_history_yazar |

Toplam süit ~44s (1235 test) — CI için hızlı. Property testleri paralelleştirme gerektirmiyor.

## 3. API p95 yanıt smoke
TestClient + in-memory SQLite + gerçekçi veri (6 hesap, 50 işlem, gelir). 40 iterasyon/endpoint:
| Endpoint | p50 (ms) | p95 (ms) | Bütçe (<200) |
|---|---|---|---|
| /api/health | 2.2 | 3.1 | ✓ |
| **/api/cockpit** | **14.4** | **19.3** | ✓ (en ağır — tam rules_engine snapshot) |
| /api/accounts | 4.8 | 7.1 | ✓ |
| /api/transactions | 7.3 | 9.4 | ✓ |
| /api/reports/upcoming-cashflow | 5.0 | 7.5 | ✓ |

**Tümü bütçe içinde (p95 < 20ms).** Cockpit diğerlerinin ~6 katı (tam snapshot: nakit/kart/kredi/yatırım/emanet +
uyarı motoru + upcoming). Gerçek dağıtımda ağ + disk gecikmesi eklenir ama uygulama-katmanı hesabı hızlı.

## Sınır (dürüstlük)
- Bu smoke **in-memory + TestClient** (ağsız, disksiz) — mutlak ms değil, uygulama-katmanı compute göstergesi.
- Cockpit p95'i ileride darboğaz olursa PERF-001 (cockpit memoize, backlog'da AÇIK) devreye alınabilir; şu an gereksiz.
- Yük testi (concurrency, N-kullanıcı) yapılmadı — tek-kullanıcı MVP'de gereksiz; multi-user/deploy'da (kapsam-dışı) değerlendirilir.
