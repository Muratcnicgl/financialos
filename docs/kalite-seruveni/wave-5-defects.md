# Wave-5 Defect Log (M66-M67 KULLANIM-GATE bulguları)

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
