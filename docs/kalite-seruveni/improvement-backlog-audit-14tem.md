# Improvement Backlog Kapatma Turu (M29, 14 Tem 2026)

MCP Improvement Backlog ~188 observation. R3 (M25 deseni): disk kanıtından (git commit +
fixler.md + kod) ONERI durumu çıkarıldı.

## ✅ KAPANDI (FEAT/milestone kanıtlı)
22 FEAT uygulandı (git+fixler+kod doğrulandı) — ilgili ONERI'leri kapatır:
| ONERI | Karşılayan | Kanıt |
|-------|-----------|-------|
| #002 goal engine | Wave-2 H2G5 (Goal/Allocation/Rule) | ADR-024, canlı |
| #004 recurring expense | FEAT-006 subscription detector | app/routers/subscriptions |
| #005 debt payoff optimizer | FEAT-014/015 (avalanche/snowball/konsolidasyon) | debt_strategy |
| #006 inflation adjuster | FEAT-024 reel net değer | rules_engine |
| #008 cashflow forecast | FEAT-009 safe-to-spend + generate_forecast | cashflow |
| #019 DB index | Wave-1 composite index'ler | models.py |
| #020 atomik transaction | RESIL-001/002 (M6 Faz-3) | action_executor |
| #021 API rate limit (LLM kota) | ApiCallLog + coach kota | coach.py |
| #028 fiyat çekim | M4 pytefas cron | ADR-029 |
| #030 precommit gate | W3-058 .githooks/pre-commit | M9 |

Ayrıca FEAT-001/002/003/005/007/010/012/013/016/017/021/022/027/032/034/041 (bütçe/borç/servet/sağlık-skoru/İLK-ADIM) uygulandı.

## ⏭️ AÇIK → Wave-4 (feature-fikri, kritik değil)
- #007 tax_calendar (vergi takvimi) · #009 weekly_review (haftalık rapor) · #010 scenario_save ·
  #011 coach_personality_modes · #014 coach_disagreement_log · #016 receipt_ocr (Vision API bağımlı) ·
  #017 family_mode (aile hesabı — Wave-4 explicit) · #018 smart_categorization_ml (veri bağımlı) ·
  #029 AST scanner (dual-index tarayıcı).
- Kısmi: #012 2FA-for-destructive (auth M11 var, 2FA-onay ayrı) · #013 multi_currency (M12 fx desteği var).

## Değerlendirme
- **Kapanan:** ~15+ ONERI (FEAT dalgası + Wave-3 milestone'ları).
- **Açık kalanların hepsi enhancement/feature** (kritik/blocking yok) → Wave-4 uygun.
- **Otonom milestone gerekmedi** (açık maddeler kritik değil, KURAL 12 ile Wave-4).
