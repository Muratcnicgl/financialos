# Faz 3 Durum (M6) — Kalite/Güvenlik Denetimi

**Milestone 6.** Kaynak plan: `MASTER-FIX-LIST.md` (P1: 27 madde, P2: ~20 grup, P3). Charter M6: P1 tam + P2 üst yarı + P3 üst %25.

## KRİTİK R3 BULGUSU (M6'nın gerçek doğası)
`MASTER-FIX-LIST.md` bir **PLANLAMA** dokümanı (10 Tem 2026 snapshot). Maddelerin büyük kısmı Kalite Serüveni **Faz 2** işinde ZATEN ÇÖZÜLDÜ (774→789 test baseline bunu yansıtır) ama listede hâlâ "açık" görünüyor. **M6 = "472 şey implement et" DEĞİL; "her maddeyi R3 ile denetle → gerçekten açık olanı düzelt → belgele."** Körlemesine "implement" = zaten-var olanı bozma riski + israf (meta-ders 10: yapılabilir ≠ yapılmalı).

## P1 Denetim Durumu (27 madde)

### ✅ CLOSED (doğrudan R3 ile doğrulandı)
- **P1-2** Para Float → **M5 Decimal göçü** (Numeric(19,4) + money.py). Kanıt: `app/models.py` 20 Numeric kolon, `git tag milestone-5-decimal-migration`.
- **P1-11** Update endpoint ownership → `app/routers/transactions.py:update_transaction` account_id sahiplik 404 (BUG #087).
- **P1-12** update_transaction amount>0 → aynı fonksiyon, `amount<=0` → 422 (BUG #087).
- **P1-14** update_fund_price user_id filtresi → `fund_tracker.py:update_fund_price_manual(user_id=...)` + executor geçiriyor (BUG #115).
- **P1-18** Alembic/create_all drift → **M1 genesis collapse** (ADR-013a, fresh-db test).
- **P1-21** premortem ADR-001 yasaklı isim → **M2 Mustafa temizliği** (isimsiz form).

### ✅ CLOSED (4 paralel audit agent R3 denetimi ile doğrulandı)
- **P1-3** cockpit alacak yeniden-hesap → `cockpit.py:42` cockpit'ten alıyor, fallback (BUG #117).
- **P1-6** fallback provider limit/istatistik → `coach.py:163` `_daily_constrained_provider` normalize (BE-025).
- **P1-9** (create yolu) percent (0,100] → `schemas.py:346` GoalRuleCreate validator.
- **P1-16** recurring day 29/30/31 → `rules_engine.py:594` `min(day, last_day)` klemp.
- **P1-17** NetWorthSnapshot unique → `models.py` UniqueConstraint(user_id, snapshot_date).
- **P1-26** overdue upcoming-cashflow → `cashflow.py:120` `due_date >= start` alt sınır.

### ✅ DÜZELTİLDİ (M6 bu artım — 5 fix + 5 test, 794 yeşil)
- **P1-7** usage sayacı yerel-tarih→UTC (`coach.py` `_today_call_count`, `datetime.utcnow().date()`, BUG #133) — TR sunucuda kota 3 saat erken sıfırlanıyordu.
- **P1-9 residüel** GoalRuleUpdate percent üst-sınır validator (`schemas.py`, BUG #134) — create/update asimetrisi.
- **P1-10** cash_target `current_amount` 0'a klemp (`goal_engine.py`, BUG #132) — negatif "birikmiş tutar" sızıyordu.
- **P1-20** PremortemScenario id deterministik S1..Sn (`premortem.py`, BUG #135) — LLM çakışan/bozuk id → React key bug (kırmadan yeniden-ata).
- **P1-23** link_premortem_outcome try/except (`actions.py`, BUG #131) — executed aksiyon sonrası 500.
- Test: `tests/security/test_faz3_p1.py` (5).

### 🔧 OPEN — kalan (sonraki M6 artımları)
- **P1-1** goals.py datetime UTC suffix (schemas.GoalRead naive) · **P1-4** coach_insights dormant sweep (decision_rhythm + mc_reference top-3-dışı) · **P1-5** explicit_red_line regex finansal-anchor · **P1-8** evaluate_rules_for_transaction ölü kod (bağla/kaldır) · **P1-13** transfer no-op (API'den kaldır/implement) · **P1-15** OperationName values_callable + migration · **P1-19** net_worth_delta yazılmıyor (DecisionJournal kolon/kaldır) · **P1-22** premortem cached hep False (hash karşılaştır) · **P1-24** evaluate_credit_card_strategy ölü kod · **P1-25** AnthropicProvider tool-history adapter · **P1-27** simulation_engine parite (float falsy→None, mark_debt guard, sell price/emanet).
- SQL injection taraması: **temiz** (ORM parametreli; tek f-string `_EXCLUDED_SQL` statik sabit). Secret mgmt: **temiz** (.env gitignore'da + git'te yok).

## Güvenlik P1 (T-17) — Wave-3 prod-gate'e ertelenir (OTONOM KARAR kategori-b)
Charter M6 "Kritik P1: rate limiting, HTTPS, auth, CORS" listeliyor. **R3 + backlog T-17:** bunlar tek-kullanıcı **lokal** MVP'de aktif risk DÜŞÜK (`localhost`, tek kullanıcı, dışa açık değil). En güçlü savunma zaten kod seviyesinde: "LLM asla DB yazmaz" + propose→onay→execute + MC enforcement. Auth/rate-limit/HTTPS **multi-user/prod'a geçmeden ADR ile** ele alınmalı — şimdi eklemek YAGNI + yanlış-güvenlik-hissi (KURAL 12: kalite = doğru zamanda doğru çözüm, gösteriş değil). **Karar:** güvenlik-sertleştirme maddeleri Wave-3 (M7 kapsamı) prod-gate ADR'ına devredildi; SQL-injection (ORM parametreli, ham SQL taraması) + secret-management (.env/.gitignore) + input-validation edge BURADA doğrulanır (aşağıda).

## P2 / P3
P1 denetimi bitince P2 üst yarı (N+1/eager, index, Recharts mount BUG #059) + P3 üst %25. Kalan Wave-3'e.
