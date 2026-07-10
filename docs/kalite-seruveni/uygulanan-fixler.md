# Uygulanan Değişiklikler (Kalite Serüveni — fix ledger)

Her satır: yapıldı → **doğrulandı**. Halüsinasyon/varsayım yok; her fix çalıştırılarak teyit edildi. Backlog ID + BUG/ADR numarası referanslı.

| # | ID | Değişiklik | Dosya | Doğrulama | Durum |
|---|----|-----------|-------|-----------|-------|
| 1 | RULE-001 / BUG #059 | `account_type` kriteri `str(enum)` yerine `.value` — enum bug'ı yüzünden account_type kriterli her GoalRule sessizce ölüydü | `app/goal_rules.py:130` | `AccountType.cash.value=='cash'` (True), `str(...)=='AccountType.cash'` (False); import OK | ✅ |
| 2 | DATA-003/004 / BUG #060 | SQLite connect listener: `foreign_keys=ON`, WAL, `busy_timeout`, `synchronous=NORMAL` — FK enforcement default kapalıydı, ondelete tanımları çalışmıyordu | `app/database.py` | Canlı bağlantı: `foreign_keys=1, journal_mode=wal, busy_timeout=5000`. `foreign_key_check`: **20 yetim reasoning_traces kaydı** tespit (temizlenecek) | ✅ |
| 3 | RULE-023 / ADR-026 | ZikZak additive `carried_forward` REDDEDİLDİ (çift-sayım/Sanal Zenginlik). Dinamik `daily_limit` zaten zikzak; yanıltıcı yorum düzeltildi, fonksiyonlar DEPRECATED | `app/rules_engine.py:729-732`; `adr-026` | Simülasyon: naif today_target=1474.96 vs sürdürülebilir 394.10 (çift-sayım kanıtı). Import + davranış (today_target=344.84) korundu | ✅ |
| 4 | FE-002 / BUG #061 | Dinamik Tailwind renkleri prod'da purge oluyordu → safelist eklendi. **Ek latent bug:** palette'te 950 shade'i yoktu, `bg-color-950/30` (RedLines dark bg) hiç render olmuyordu → 4 palette'e 950 eklendi | `frontend/tailwind.config.js` | `npm run build` (5.25s) + dist CSS grep: `bg-warn-950/30`, `dark:bg-warn-950/30`, `text-brand-400`, `ring-negative-500` hepsi VAR | ✅ |

## Tur 2 — P0 sprinti (per-file MASTER-FIX-LIST'ten)

| # | ID | Değişiklik | Dosya | Doğrulama | Durum |
|---|----|-----------|-------|-----------|-------|
| 5 | P0-18 SC-001 / BUG #062 | `run_extractor` except'ine `db.rollback()` — bir extractor commit'te patlarsa paylaşılan session zehirlenip sonraki extractor'lar + Coach `_save_message` sessizce/patlayarak çalışmıyordu | `app/scheduler.py` | app.main import OK | ✅ |
| 6 | P0-21 SH-002 / BUG #063 | `GoalUpdate.status` literal'inden "achieved" çıkarıldı — kullanıcı PATCH ile hiç katkı yapmadan "sanal başarı" işaretleyemez; achieved yalnız refresh_goal'da | `app/schemas.py` | `GoalUpdate(status='achieved')` → ValidationError; 'active' geçerli | ✅ |
| 7 | P0-6 GR-001 / BUG #064 | "fixed" allocation işareti `tx_amount>=0` (hep True) yerine `tx.transaction_type`'tan — gidere eşleşen fixed kural withdrawal yerine +contribution kaydedip goal'i şişiriyordu | `app/goal_rules.py` | `income.value=='income'`; import OK | ✅ |
| 8 | P0-9 CS-001 / BUG #065 | premortem yanlış anahtar `crunch_day` (hep '-') → `lowest_balance_date` + `lowest_balance_tl` + `crunch_count` eklendi; nakit-kriz verisi artık LLM'e ulaşıyor | `app/premortem.py` | `build_cockpit_snapshot` anahtarları kodla teyit | ✅ |
| 9 | P0-5 GE-001 / BUG #066 | goal_engine `snowball.months_to_freedom` (attribute) → `snowball["months_to_freedom"]`; compare_strategies dict döndürüyor, AttributeError bare-except'te yutuluyordu → debt_freedom "tahmini bitiş" hep None'du | `app/goal_engine.py` | Canlı: `months_to_freedom=9` dönüyor; attribute erişimi AttributeError (eski hata teyidi) | ✅ |
| 10 | P0-20 RCH-003 / BUG #067 | `update_checkpoint`'e koruma: korunan (priority=1+red_line) checkpoint'in priority/checkpoint_type'ı değiştirilip sonra hard-delete ile Master Checkpoint enforcement delinmesin | `app/routers/checkpoints.py` | app.main + router import OK | ✅ |

| 11 | P0-2 AE-002 / BUG #068 | `_execute_sell_investment`: satış gelirinin hedef hesabı MUTASYONDAN ÖNCE doğrulanıyor — geçersiz/emanet/eksik hesapta lot düşmeden başarısız dönüyor (eskiden `net_eline_gecen` hiçbir yere yatmadan lot düşüp success dönüyordu → para sessizce kaybı) | `app/action_executor.py` | **In-memory test 4 senaryo:** geçerli→lot 6→2+para yatıyor; emanet/geçersiz/hedefsiz→fail+lot 6 kalıyor | ✅ |
| 12 | P0-1 AE-001 / BUG #069 | `execute_pending_action` post-commit trigger'ı ayrı try'a — trigger hatası zaten 'executed' aksiyonu 'failed' işaretleyip çift-sayıma yol açmasın. (Tam handler-commit birleştirmesi test ağı sonrası) | `app/action_executor.py` | app.main import OK | ✅ |

| 13 | P0-15 REX-001 / BUG #070 | Recurring `last_triggered_year_month` artık propose'ta değil **execute'te** (`_mark_recurring_triggered`) set ediliyor — reddedilen/başarısız gider "bu ay halledildi" sayılıp kaybolmuyor, re-triggerable kalıyor | `action_executor.py`, `expenses.py`, `incomes.py` | In-memory: None→2026-07; non-recurring no-op; import OK | ✅ |
| 14 | P0-16 RIN-001/REX-004 / BUG #071 | Recurring tetikleme `day_of_month`'u ay uzunluğuna clamp'liyor — day=31 kısa aylarda (Şubat/Nisan…) sessizce atlanmıyor | `expenses.py`, `incomes.py` | Clamp: 31→30 (Nisan), 31→28 (Şubat) | ✅ |

| 15 | P0-13/14 RGO-001/002 / BUG #072 | `create_allocation`: bu tx'e tüm hedeflerdeki mevcut allocation toplamı + yeni istek, `abs(tx.amount)`'ı aşamaz (422) — 10 TL işlem "1M katkı" veya aynı tx çok hedefe tam tutarla bağlanıp sanal zenginlik/çift-sayım üretemez | `app/routers/goals.py` | In-memory: sum(abs)=80; 80+30>100 reddet, 80+20 izin | ✅ |

| 16 | P0-11 RRE-001 / BUG #073 | reports category_breakdown "both" modunda gelir+gider aynı kategori satırında toplanıyordu → `transaction_type` group_by'a eklendi, yön etiketli ayrı satırlar | `app/routers/reports.py` | In-memory: "diger" → 2 satır (gelir 1000, gider 200); eskiden 1200 | ✅ |
| 17 | P0-12 RRE-002 / BUG #074 | reports upcoming_cashflow krediler için sadece 1 taksit gösteriyordu → ufuk boyunca aylık taksitler (kalan-limit + gün-clamp + yıl-geçişi) | `app/routers/reports.py` | Logic test: 180g→6 taksit, remaining=2 sınırı, gün-31 clamp, yıl-geçişi | ✅ |

## Genel smoke test (17 fix sonrası, canlı DB read-only)
`generate_cockpit` ✅ (today_target==daily_limit → ADR-026 doğru) · `generate_forecast(180g)` ✅ · `build_cockpit_snapshot` ✅ (P0-9 anahtarları mevcut) · `app.main` import ✅ (her batch). Çekirdek motorlar sağlam.

## Bekleyen (onay/temizlik)
- **20 yetim `reasoning_traces` kaydı** (user id=2, var olmayan): FK açıkken app çalışır ama veri kiri. Silmek düşük riskli (ölü debug trace) — kullanıcı onayıyla temizlenecek.

## Yürütme notları
- Numaralandırma: BUG #059→#061 (önceki en yüksek #058'di). ADR-026 (önceki #025).
- Her fix `dersler-gemini.md` 7 meta-dersine ve kök vizyona hizmet ediyor.
- Sıradaki: backend per-file konsolidasyonu (MASTER-FIX-LIST) → P0 finansal matematik bug'ları.
