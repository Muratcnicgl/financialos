# Tam Süit + Performans Smoke (M90, Wave-6 — 18 Tem 2026)

> ## ⚠️ 48 GÜN DOKUNULMADI — 5 Eylül 2026'da DENETLENDİ
>
> **Bu belgedeki hiçbir sayı bugünü anlatmıyor** ve en tehlikelisi de sonuçtur:
> *"Toplam süit ~44s — CI için hızlı."*
>
> | | M90 (18 Tem 2026) | 5 Eyl 2026 (bu gece ölçüldü) |
> |---|---|---|
> | Test sayısı | 1.235 | **3.527** (+18 skipped) |
> | Tam süit süresi | ~44 s | **202,8 s** |
>
> Süit **2,9 kat büyüdü, 4,6 kat yavaşladı** — yani test başına maliyet de arttı.
> "CI için hızlı" cümlesi bugün bir ölçüm değil, bir hatıradır.
>
> **ASIL BULGU — BU BÜTÇE YENİDEN ÖLÇÜLEMİYOR.** §3'teki p95 tablosu (cockpit p95 19,3 ms,
> bütçe <200 ms) tek seferlik, elle kurulmuş bir koşumdan geliyor: depoda onu tekrarlayan
> **hiçbir betik yok** (`scripts/` altında perf/smoke/bench aranır — sonuç sıfır) ve hiçbir
> test p95 ölçmüyor. **Tekrarlanamayan bir bütçe bütçe değildir**; ihlal edildiğinde kimse
> öğrenmez — L61'in performans karşılığı: ölçmek, haber vermek değildir.
> Bu yüzden §3 tablosu bugün *"bütçe içindeyiz"* kanıtı olarak KULLANILAMAZ; yalnız
> 18 Temmuz'da öyle olduğunu söyler.
>
> **Açık iş:** p95 smoke'unu `scripts/` altında tekrarlanabilir bir ölçüme çevirmek
> (o zaman bu tablo bir kapıya bağlanabilir). Süre büyümesi ayrıca kendi başına bir konu:
> 202 s'lik bir pre-commit kancası, atlanmaya davet eden bir kancadır (L22).
>
> ---
>
> ### ✅ AÇIK İŞ AYNI GECE KAPANDI — ölçüm artık TEKRARLANABİLİR (BUG #350)
>
> `scripts/perf_smoke.py` yazıldı: aynı beş ucu, aynı yöntemle, tek komutla ölçer.
> **Yeni ölçüm (5 Eyl 2026, 40 iterasyon/uç) ve 18 Temmuz karşılaştırması:**
>
> | Uç | M90 p95 | 5 Eyl p95 | bütçe |
> |---|---|---|---|
> | /api/health | 3,1 | **3,05** | 200 |
> | /api/cockpit | 19,3 | **22,14** | 200 |
> | /api/accounts | 7,1 | **5,76** | 200 |
> | /api/transactions | 9,4 | **9,03** | 200 |
> | /api/reports/upcoming-cashflow | 7,5 | **7,56** | 200 |
>
> **Sonuç: belgenin SAYILARI bayattı ama YARGISI ayakta.** Süit 2,9 kat büyürken uygulama
> katmanının maliyeti pratikte değişmemiş; hepsi bütçenin bir onda birinde. Bu, 48 gün
> sonra ilk kez **ölçülerek** söylenebiliyor.
>
> **İki tasarım kararı kayda geçsin.** (1) Ölçüm, kullanıcının koştuğu yolu koşmalı:
> workspace'i olmayan sentetik bir kullanıcı ürünün ESKİ `user_id` yoluna düşüyordu ve
> her istekte uyarı basıyordu — `create_personal_workspaces.run()` çağrılarak gerçek yola
> geçildi (backfill kopyalanmadı, tek kaynak kullanıldı). (2) **CI'a bağlanmadı:**
> paylaşımlı runner'ların hızı değişkendir, oraya bağlanan bir p95 kapısı düzenli sahte
> kırmızı üretir ve okunmaz hâle gelir (L22). Bütçeler de gerçek değerin kat kat üstünde —
> amaç gürültüyü değil GERİLEMEYİ yakalamak.
>
> Aşağıdaki gövde 18 Temmuz 2026 kaydı olarak korunuyor.

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
