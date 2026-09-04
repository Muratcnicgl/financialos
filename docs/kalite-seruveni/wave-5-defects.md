# Wave-5 Defect Log (M66-M67 KULLANIM-GATE bulguları)

> ## ✅ 5 Eylül 2026'da DENETLENDİ — iddiaları TUTUYOR, kapsamı ise ARTIK DAHA GENİŞ
>
> `belge_denetimi` bu belgeyi 48 gün dokunulmamış diye işaretledi. Denetlendi ve
> **yanlış bir iddia bulunmadı** — bu belge, düzeltmeleri kaydedilmiş tarihsel bir
> defterdir. Tek bayat nokta, kendi lehine: M70 bölümü tarayıcının kapsamını
> *"app/routers/*.py + rules_engine + goal_engine + debt_strategy"* diye anlatıyor.
>
> **Bugün ölçüldü:** `tests/test_scope_enforcement.py` artık **`app/` ağacının tamamını**
> tarıyor (`rglob("*.py")`, `models.py` hariç) — **104 dosya**, 18 dosyada gerekçeli
> `# scope-exempt` işareti, **17 test yeşil**. Yani M70'in *"ÖRNEKLEME değil KAPSAMA"*
> hedefi yalnız korunmakla kalmamış, dosya listesinden glob'a geçerek **genişlemiş**;
> bugün eklenen yeni bir router hiçbir şey yapılmadan kapsama giriyor.
>
> Belgenin gövdesi 18 Temmuz 2026 kaydı olarak aynen duruyor.

Charter: her defect BUG #161+ numarası + MCP. Kapatma M68'de (kök neden + fix + test + tarayıcı tekrar-kanıt).

---

## BUG #161 [✅ KAPANDI M68] — Koç "kredi kartı ödemesi"ni kart borcunu ARTIRACAK şekilde modelliyor
> **FIX (M68, commit sonra):** `pay_credit_card` first-class aksiyon eklendi (action_executor
> `_execute_pay_credit_card`: kart borcu −amount + kaynak nakit −amount, net-nötr). 3 senkron noktası
> güncellendi (koç tool enum + `propose_action` valid_types + execute dispatcher). V3 prompt: seçim tablosu
> + payload şablonu. 5 birim test. **App-akışı re-proof:** koç `pay_credit_card` önerdi → onayla → kart
> 10.180,01→9.680,01 (AZALDI), nakit 9.747,95→9.247,95, ActionHistory net-nötr (nw değişmedi = doğru).
> **Ders:** action_type 3 yerde ayrı listeleniyor (tek doğruluk kaynağı yok) → miss buradan; Wave-6 adayı.

- **Bulunma:** M66 tam-döngü e2e (18 Tem 2026, Chrome). Login → koça "Ziraat kredi kartıma 500 TL ödeme
  yaptım" → koç PendingAction #41 önerdi → Onayla → execute → **finansal sonuç YANLIŞ.**
- **Beklenen:** Kart ödemesi kart borcunu 500 AZALTIR (10.180,01 → 9.680,01) + nakiti 500 azaltır (9.547,95 → 9.047,95).
- **Gerçekleşen:** Kart borcu 500 **ARTTI** (10.180,01 → 10.680,01); nakit HİÇ değişmedi.
- **Kök neden:** Koç, kart ödemesini `transaction_type=expense, account=Ziraat Kredi Kartı` olarak modelledi
  (Transaction id=2: expense/500/credit_card_payment/account_id=2). `_apply_to_balance` semantiği:
  `credit_card + expense → balance += amount` (kart harcaması borcu artırır). Yani ödeme, kart HARCAMASI
  gibi işlendi → borç arttı; ödemenin nakit ayağı hiç modellenmedi.
- **Doğru model (M68 kararı):** Kart ödemesi = **nakit → kart transfer** VEYA (a) karta `income` (borç azalır:
  `credit_card + income → balance -= amount`) + (b) nakitten `expense`. Tek-bacaklı kart-gider modeli yanlış.
- **Sınıf:** Finansal-doğruluk (kritik) — koç muhakemesi + action_executor semantik boşluğu. LLM "sadece açıklar"
  ama execute literal uyguluyor → yanlış TL. 4 wave boyunca döngü hiç işletilmediği için görülmedi (§B24).
- **Kanıt:** ActionHistory yazıldı (nw_before −12575,29 → nw_after −13075,29 — net değer YANLIŞ yönde düştü);
  cockpit kart 10680,01. Test artefaktı geri alındı (bakiye restore).
- **Fix:** M68.

## NOT (BUG değil, gözlem) — 37 "rejected" Maas pending birikmesi
- M66 sırasında DB'de 40 PendingAction görüldü: 1 pending (#40 Maas, gerçek recurring) + 37 rejected "Maas geldi"
  + 2 rejected diğer. Rejected pending'ler kullanıcı-görünür değil (cockpit yalnız pending gösterir) ama DB
  clutter. BUG #060 (duplicate Maas) alanı; rejected-retention tasarım gereği. M68'de değerlendirilir (öncelik düşük).

---

## M67 — 13 panel console-sweep sonucu (18 Tem 2026)

- **13 panel yüklendi (JS-click ile mount, her biri API çağırdı):** Cockpit, Koç, Hesaplar, İşlemler,
  Gelir&Borç, Kırmızı Çizgiler, Raporlar, Akış, Borç Stratejisi, Hedefler, Bütçe, Aile, Login.
- **Console HATASI: 0** (read_console_messages onlyErrors, tüm paneller). B18-5 boşluğu (console hiç okunmamıştı) kapandı.
- **BUG #059 DOĞRULANDI (hâlâ açık):** Recharts ResponsiveContainer `width(-1)/height(-1)` warning, 8×
  (chart panelleri). Kozmetik, düşük öncelik (16 May 2026'dan beri açık). UI etkilenmiyor, chart sonra doğru render.
- **UI CREATE browser-kanıtı:** Accounts ("M67 Test Kasa" oluştu, 7 hesap) · Transactions (M66, "200 fatura") ·
  Coach (M66, tam döngü). Hepsi gerçek UI + gerçek veri.
- **OTONOM KARAR M67 (kategori-b, ORTAM KISITI):** Chrome MCP extension bu ortamda kararsız (screenshot
  timeout + mid-op disconnect + kaçan koordinat-tık, M66-M67 boyunca tekrarlı). Exhaustive 13-panel ×
  (create+update+delete) screenshot-tabanlı sweep güvenilir değil + devasa context. **Systematic CRUD sweep
  M69 Playwright harness'ına devredildi** — charter M69 zaten bunu istiyor ve Playwright MCP-extension'dan
  KARARLI (doğru araç). Kalite düşürme değil, araç değişimi.

---

## M70 — Scope AST tarayıcısı 3 GERÇEK leak buldu (RISK #2 / §B23b somut kanıtı)

`tests/test_scope_enforcement.py` (regex/AST tarayıcı): her router + rules_engine'de `<ScopedModel>.user_id ==`
kalıbını arar; `scope_filter`/`_scope`/`workspace_scope` ile sarılı DEĞİLSE ve `# scope-exempt` yoksa TEST KIRILIR.
İlk koşu **12 ihlal** buldu → 3 gerçek leak + 9 kasıtlı (exempt işaretlendi).

**3 GERÇEK LEAK (workspace izolasyonu delik — M43 ÖRNEKLEME idi, KAPSAMA değil):**
- **`goals.py:211`** — hedef ilerlemesi `Transaction.user_id == current_user.id` ile hesaplanıyordu (ws_id
  yok) → başka workspace'in işlemleri hedef progress'e sızardı. Fix: `scope_filter(Transaction, id, ws_id)`.
- **`fund_price.py:85`** — POST /update hesap sahiplik kontrolü `Account.user_id ==` (ws_id yok) → viewer/editor
  workspace'te yatırım fiyatı güncelleme scope-dışı. Fix: `active_workspace_id` param + `scope_filter(Account, ...)`.
- **`subscriptions.py:69,73`** — abonelik→RecurringExpense dönüşümü hem hesap doğrulamada hem dup-kontrolde
  `.user_id ==` (ws_id yok) + yeni RecurringExpense'e `workspace_id` yazılmıyordu. Fix: `workspace_scope` list'te,
  `scope_filter` to-recurring'de, `workspace_id=ws_id` yeni kayıtta.

**Anlamı:** §B23b RISK #2 ("M43 workspace scoping ÖRNEKLEME ile doğrulandı, KAPSAMA değil") **somut kanıtlandı** —
M43'te 3 endpoint atlanmıştı, kimse fark etmemişti çünkü kapsayıcı test yoktu. Artık tarayıcı test var: yeni
endpoint scope'u unutursa CI kırılır. Bu tam olarak charter Blok B M70'in amacı ("Yeni endpoint unutursa TEST KIRILSIN").

**9 KASITLI (exempt):** cockpit snapshot legacy-fallback (ws_id None branch), user KVKK export (per-user tam veri),
actions approve/reject ownership (id+user), expenses/incomes pending-dedup (user-level), premortem/simulation pending
lookup. Her biri `# scope-exempt: <sebep>` ile işaretli — tarayıcı bunları atlar, sebep kod-içi görünür.

**Kanıt:** `pytest tests/test_scope_enforcement.py` 2 passed; tam süit 975 passed, 1 skipped (M69'da 973 idi, +2 tarayıcı).

---

## M72 — debt_freedom goal'lerinde workspace borç-kaçağı (tarayıcı KÖR NOKTASI: goal_engine/debt_strategy)

**Bulgu:** `debt_freedom` tipi goal'lerin ilerleme hesabı, workspace izolasyonunu DELİYORDU. M70
tarayıcısı yalnız `routers/*.py + rules_engine.py` tarıyordu; **goal_engine.py ve debt_strategy.py
taranmıyordu** → oradaki 3 `Account.user_id ==` sızıntısı görülmemişti:
- `goal_engine.calculate_baseline_for_debt_freedom` — goal yaratımında baseline TÜM workspace'lerin
  kredi+kart toplamından alınıyordu (aile ws goal'ü Murat'ın kişisel kredilerini de sayardı).
- `goal_engine._compute_debt_freedom` — güncel borç aynı şekilde `Account.user_id == goal.user_id`.
- `debt_strategy.collect_debts` — snowball/avalanche + debt_freedom projeksiyonu için borçları
  `Account.user_id == user_id` ile topluyordu (workspace-kör).

**Anlamı:** İki workspace aynı user_id'yi paylaştığından (köprü-desen), aile ws'indeki bir "borçsuzluk"
hedefi kişisel workspace'in kredilerini karıştırıp progress'i YANLIŞ gösterirdi. Tek-kullanıcı gerçekte
tek personal ws olduğu için canlıda tetiklenmemişti — ama aile özelliği kullanılınca patlardı (§B23b RISK #2 sınıfı).

**Fix (köprü-uyumlu, ADR-037):**
- goal_engine + debt_strategy: `Account.user_id ==` → `_scope(Account, user_id)` (contextvar yoksa user_id = legacy korunur).
- `refresh_goal`: `compute_progress` çağrısı `with workspace_scope(goal.workspace_id)` ile sarıldı — tek
  noktada hem borç sorgusu hem projeksiyon (compare_strategies→collect_debts) doğru workspace'e kapanır.
- `goals.create_goal`: baseline hesabı `with workspace_scope(ws_id)` içinde.
- **M70 tarayıcısı genişletildi:** `_TARGETS` artık goal_engine.py + debt_strategy.py de kapsar → kör nokta kapandı, regresyon kilidi bu iki dosyayı da koruyor.

**GoalAllocation/GoalRule (rapordaki asıl M72 endişesi):** İNCELENDİ, GÜVENLİ. user_id'leri yok ama her
router erişimi önce parent goal'ü `scope_filter(Goal, …)` ile doğruluyor (list/create `/{goal_id}/…` → 404;
delete/update `{id}` → item çek + goal-scope → 403). goal_id join workspace-bound goal üzerinden izole.

**Kanıt:** `tests/test_goal_workspace_isolation.py` 3 test — baseline shared=20000 / personal=50000 /
legacy=70000; debt_freedom progress %25 (yalnız shared borç azalınca); personal borç değişimi shared
goal'ü ETKİLEMİYOR. Scanner 2 passed (goal_engine/debt_strategy dahil, ihlal yok). Tam süit 986 passed, 1 skipped.

---

## M73 — Gece batch cron'ları workspace-kör + coach insight'larına cross-workspace karışma riski

**Bulgu (rapor §B12, R3-doğrulandı):** 5 cron job `workspace_scope` contextvar'ı SET ETMİYORDU. R3
inceleme her job'u ayrı değerlendirdi (rapor "hepsi eksik" derken 3'ü aslında BİLİNÇLİ global):
- `fetch_investment_prices` (02:45) — `Account.account_type==investment` GLOBAL sorgu (user/ws filtresi
  YOK), tüm hesapları işler → paylaşımlı ws dahil. Fon fiyatı ws'e bağlı değil → workspace-scope GEREKMEZ, olsa YANLIŞ olur. ✓
- `nightly_trace_cleanup` (04:00) — `ReasoningTrace` global retention (workspace-scoped değil). ✓
- `weekly_smoke_test` (Pzt) — DB'siz dış-API smoke. ✓
- `nightly_batch` (03:00) + `k2_batch` (03:30) — **coach insight extractor'ları.** GERÇEK risk buradaydı.

**Kök neden:** Coach insight'ları USER-SEVİYELİ (schema R3: `CoachInsight`/`CoachMemory`'de `workspace_id`
YOK). Ama 4 extractor workspace-scoped modelleri ham `user_id ==` ile okuyordu:
`extract_category_account_preference` (Account+Transaction), `extract_action_rejection_pattern` (PendingAction),
`extract_breakthrough`/`extract_setback` (NetWorthSnapshot). Paylaşımlı (aile) workspace eklenince o veri
kişinin PERSONAL insight'larına karışırdı — örn. aile net-değeri kişisel "breakthrough"a sızardı.

**Fix (KURAL 12 tam çözüm, 4 parça):**
1. **Canlı backfill:** `create_personal_workspaces.run` çalıştırıldı (idempotent, backup-guard'lı) — 1 kalan
   `NetWorthSnapshot` NULL `workspace_id` → personal ws=1. Artık user 1'in TÜM scoped verisi ws=1 (0 NULL kaldı).
   Bu, batch'i personal-scope'a almanın eski (NULL) snapshot'ları düşürmeden yapılabilmesi için önkoşuldu.
2. **Extractor'lar:** 7 ham `user_id ==` filtresi → `_scope(Model, user_id)` (contextvar yoksa user_id = legacy korunur).
3. **Batch job'lar:** `run_periodic_batch_for_user` + `run_k2_batch_for_user` `workspace_scope(_personal_workspace_id(...))`
   ile sarıldı → scoped okumalar kişinin KENDİ verisini görür. `_personal_workspace_id` None fallback → test/legacy korunur.
   (Olay-tetikli extractor'lar request bağlamındaki ambient scope'u kullanır — dokunulmadı, doğru.)
4. **M70 tarayıcısı:** `_TARGETS += coach_insights.py` → extractor'ların scoped okumaları kilitlendi.

**Kanıt:** `tests/test_scheduler_workspace.py` 3 test — `_personal_workspace_id` çözümü; batch personal-scope'ta
category_account_preference YALNIZ KisiselKart'ı sayıyor (6, 12 değil = izole, AileKart görünmez); köprü kanıtı:
scope yokken personal+shared karışıp dominant %70 eşiğini bozuyor (insight yaratılmıyor — karışımın neden zararlı
olduğunun kanıtı). coach_insights+scheduler 67 mevcut test yeşil. Scanner 2 passed. Tam süit 989 passed, 1 skipped.
