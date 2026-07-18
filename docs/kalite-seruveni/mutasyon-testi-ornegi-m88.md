# Mutasyon Testi Örneği (M88, Wave-6)

**Soru:** Coverage %92 — ama testler gerçekten **yakalıyor mu**, yoksa satır mı sayıyor?
Mutasyon testi bunu ölçer: kaynağa küçük bir kusur (mutant) sok, testler KIRILIYORSA test etkili
("mutant öldü"), GEÇİYORSA test boşluğu var ("mutant hayatta kaldı").

## D1 — Sektör referansı (mutasyon testi)
- **mutmut / cosmic-ray** (Python mutation testing araçları): "line coverage tells you code ran, mutation
  testing tells you it was *tested*."
- **PIT (pitest, Java)** dokümantasyonu: "Surviving mutants reveal weak or missing assertions that coverage hides."
- **Google "Mutation Testing at Scale" (2018)**: mutantları geliştiriciye dönüş anında göster, gürültüyü ele.

Bu milestone **örnek** düzeyinde (tam mutmut turu değil) — en kritik 3 modülde elle temsilci mutant.

## 3 kritik modülde mutant (uygula → hedef test koş → geri al)

| # | Modül | Mutant | Hedef test | Sonuç |
|---|---|---|---|---|
| 1 | `rules_engine.apply_shadow_accounting` | `- card_debt` → `+ card_debt` (MC4 gölge muhasebe işaret hatası) | test_founding_scenario + test_metric_coherence | ✅ **ÖLDÜ** (2 failed) |
| 2 | `workspace_deps.scope_filter` | `model.workspace_id == workspace_id` → `model.user_id == user_id` (workspace izolasyonunu kır) | test_workspace_scoping + test_rules_engine_workspace + test_goal_workspace_isolation | ✅ **ÖLDÜ** (12 failed) |
| 3 | `coach.is_question` | `if '?' in m: return True` → `if False` (soru '?' tespitini kaldır) | test_kural_sifir_gating + test_coach_behavior_contract | ❌ **HAYATTA KALDI** |

## Bulgu: mutant #3 HAYATTA KALDI = gerçek test boşluğu
`is_question` satır-coverage'da **%100 kapsanmış** görünüyordu, ama `'?'` dalının DAVRANIŞI test edilmiyordu:
parametrize vakalarının hepsi (`"Bugün ne yapmalıyım?"`) '?' YANINDA bir anahtar kelime (`ne`) de içeriyordu →
'?' dalı kaldırılsa bile `ne` dalı `True` döndürüyor, test geçiyordu. **Satır çalıştı ama davranış assert edilmedi.**

### Düzeltme + yeniden doğrulama
`test_coverage_m88.py::test_is_question`'a **SADECE '?' içeren** (başka anahtar kelime YOK) 2 vaka eklendi:
`"Faturayı ödedim?"`, `"Enparadan çektim?"` → her ikisi de yalnız '?' dalıyla `True`. Mutant tekrar sokuldu →
**bu kez test KIRILDI (2 failed) = mutant öldü.** Boşluk kapandı.

## Sonuç
- **2/3 mutant zaten yakalanıyordu** → ilgili testler (metric coherence, workspace izolasyon) gerçekten etkili.
- **1/3 mutant kaçmıştı** → mutasyon testi, satır-coverage'ın gizlediği bir assert boşluğunu ortaya çıkardı; kapatıldı.
- **Ders:** %92 line-coverage ≠ %92 mutant-kill. Kritik dallar için "satır çalıştı mı" değil "davranış assert edildi mi"
  sorulmalı. Wave-7'de daha geniş bir mutmut turu değerlendirilebilir (özellikle coach.py'nin dallı yardımcıları).
