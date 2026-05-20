# ADR-025: Goal Engine — Allocation-Based Pattern (Monarch Money Goals 3.0 Referansi)

**Tarih:** 20 Mayıs 2026
**Durum:** Onaylandı, H2G5 (Wave-2) ile uygulandı
**Önerenler:** Murat Can İçgil (kullanıcı), asistan
**İlgili commits:** `258fcd7` (backend), `91546aa`+`89d3710` (fix), `68ad681` (frontend)

---

## Bağlam

FinancialOS Wave-2 H2G5 adımında "Goal Engine" özelliği gerekiyordu. Kullanıcılar iki tip hedef tanımlayabilmeli:

1. **Borç ödeme hedefi (`debt_freedom`)** — tüm aktif borçların kapatılması, baseline = goal yaratıldığı andaki toplam borç bakiyesi.
2. **Tasarruf hedefi (`cash_target`)** — belirli bir tutar biriktirme (acil fon, tatil, ev peşinatı vb.).

Mimari soru: **Hedef ilerlemesi nasıl hesaplansın ve transaction'larla nasıl bağlansın?**

İki ana yaklaşım sektörde gözlemlendi:

| Yaklaşım | Örnek | Mantık |
|---|---|---|
| **Balance-tracking** | YNAB Targets | Hedef = bir kategori veya hesap bakiyesi. Bakiye değişimi otomatik olarak ilerleme. |
| **Allocation-based** | Monarch Money Goals 3.0, Copilot Money | Hedef = ayrı bir kayıt. Transaction'lar manuel veya kurala bağlı olarak hedefe "allocate" edilir. |

---

## Karar

**Allocation-based pattern (Monarch Money Goals 3.0)** seçildi.

### Veri modeli

Üç tablo, üçü de bu sohbette migration `fb38814500bf` + `f3dda4d3996d` ile yaratıldı:

1. **`goals`** — hedef tanımı (title, goal_type, target_amount, status, current_amount cache, progress_percent cache, projected_completion_date cache, baseline_amount, user_id).
2. **`goal_allocations`** — her allocation bir kayıt. `+contribution` veya `-withdrawal`. `transaction_id` opsiyonel (link); olmazsa manuel allocation. `uq_goal_tx` constraint: bir transaction aynı hedefe en fazla bir kez bağlanabilir.
3. **`goal_rules`** — otomatik allocation kuralları. JSON criteria + allocation_type (`full` / `percent` / `fixed`) + allocation_value.

### İlerleme hesaplama

`goal_engine.refresh_goal(goal_id)` — deterministik recompute:

- **debt_freedom**: `current = baseline - toplam_aktif_borç`. Progress = `current / baseline * 100`.
- **cash_target**: `current = SUM(allocations.amount)`. Progress = `current / target * 100`.

`projected_completion_date` son 90 günlük katkı hızından lineer ekstrapolasyon ile cache'lenir.

### Kural motoru

`goal_rules.evaluate_rules_for_transaction(tx)` — yeni transaction yaratıldığında:

- `criteria` JSON eşleşmesi kontrol edilir (kategori, hesap, etiket vb.).
- Eşleşirse `allocation_type` ve `allocation_value`'ya göre tutar hesaplanır.
- Savepoint pattern (`db.begin_nested()`) ile bir kuralın IntegrityError'u diğer kuralları etkilemez.

---

## Alternatifler ve gerekçe

### Alternatif A: Balance-tracking (YNAB tarzı)

- ❌ FinancialOS'ta hedef başına ayrı bir "kategori" veya "hesap" gerektirir → multi-asset yapımıza uyumsuz.
- ❌ Tek bir hesabın bakiyesi birden fazla hedefe bölünemez (örn. Enpara Nakit hem acil fon hem tatil için olamaz).
- ❌ Geçmiş işlemlere bağlama (retro-link) zor.

### Alternatif B: Allocation-based (Monarch tarzı) — **seçildi**

- ✅ Tek hesap birden fazla hedefe bölünebilir (allocation kayıtları sayesinde).
- ✅ Manuel + transaction-linked + kural-tabanlı, üçü birlikte çalışır.
- ✅ Retro-link kolay: var olan bir transaction'a allocation ekle.
- ✅ Withdrawal kavramı (hedeften çekme) doğal şekilde modellenir (`+amount` vs `-amount`).
- ❌ Veri modeli daha karmaşık (3 tablo vs 1).
- ❌ Progress hesabı bakiyeden değil katkılardan; bakiye düşüşü otomatik yansımaz (kural ekle kullanıcıdan beklenir).

### Alternatif C: Hibrit (Fully Allocated Account modu)

Monarch 3.0'da var: bir hesabın **tamamını** tek bir hedefe bağlama. Bakiye değişimi otomatik yansır.

- Şu an scope dışı bırakıldı (gelecek revize: ADR-025 v2 olarak değerlendirilecek).
- Tek kullanıcı + 1-2 hesaplı senaryoda allocation-based zaten yeterli kalitede.

---

## KURAL 10 — Üç Boyut Muhakemesi

| Boyut | Allocation-based değerlendirmesi |
|---|---|
| **MUHAKEME** | Monarch Goals 3.0 (Şubat 2026), Copilot Savings Goals (Mayıs 2025) — iki sektör lideri allocation-based seçti. YNAB target patterni FinancialOS bağlamına uyumsuz (kategori bütçe altyapısı gerektirir, biz multi-asset modelindeyiz). |
| **BENİ DÜŞÜN** | Murat solo dev, multi-account (Enpara Nakit + Enpara Fon + kredi kartı + krediler). Allocation-based bu çeşitliliği bölme yetisi veriyor. Wave-2 zaten kompleks; karmaşıklık maliyeti dengeli. |
| **GENELİ DÜŞÜN** | TR kullanıcı için: birden fazla bankada bakiye + birden fazla hedef yaygın. Self-host topluluk için: pattern endüstri standardı (eğitilebilir, dokümanı zengin). |

---

## KURAL 12 — Kalite Mutlak, Basitlik Gerekçe Değil

İlk taslakta Claude "tek hesaba bağlı, basit MVP yeterli" önerdi. Murat **(c) seçeneği = opsiyonel multi-allocation default tüm cash** ile düzeltti. Mevcut tasarım bu kararı uyguluyor.

---

## Revize tetikleyicileri

Bu ADR şu durumlarda gözden geçirilir:

1. Kullanıcı geri bildirimi: allocation eklemek çok manuel hissediyor → daha akıllı default'lar gerek.
2. Multi-asset envanteri (yatırım fonu + hisse + döviz) hedef bağlamına girdiğinde → balance-tracking ile hibrit gerekebilir.
3. Performance: 10k+ transaction × 50 hedef senaryosunda `refresh_goal` yavaşlarsa → materialized view veya event-driven invalidation.

---

## Referanslar

- Monarch Money Goals 3.0 (Şubat 2026): https://help.monarch.com/hc/en-us/articles/44373110771860-Introducing-Goals-3-0
- Monarch Save Up Goals: https://help.monarch.com/hc/en-us/articles/44373182867476-Using-Save-Up-Goals
- Monarch Fund Allocations: https://help.monarch.com/hc/en-us/articles/46420712538260-Moving-Funds-In-and-Out-of-Goals
- Copilot Money Goals tab: https://help.copilot.money/en/articles/11470324-savings-goal-tab-overview
- Copilot Spending from Goals: https://help.copilot.money/en/articles/11100511-spending-from-savings-goals
- YNAB Targets feature: https://www.ynab.com/features/goal-tracking
