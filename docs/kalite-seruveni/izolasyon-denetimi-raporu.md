# P1 — Çok-Kullanıcı Veri İzolasyonu Denetimi (Wave-9 publish yolu)

**Tarih:** 2026-08-04 · **Kapsam:** kapalı-beta öncesi #1 risk · **Durum:** ✅ KAPI GEÇTİ
**Masterprompt:** `masterprompt-publish.md` §P1

> Gerekçe: tek-kullanıcı kurulumda izolasyon hataları **görünmez**. İkinci gerçek kullanıcı
> girdiği an veri sızar. Bu denetim, "ikinci kullanıcı geldiğinde ne bozulur?" sorusunu
> statik (kod şekli) + runtime (davranış) + DB (RLS) olmak üzere üç katmanda yanıtlar.

---

## 1. BULUNAN AÇIKLAR (4 bug — hepsi kapatıldı)

### BUG #162 — Çapraz-kullanıcı hedef-kuralı sızıntısı (KRİTİK, canlı yol)
`app/goal_rules.evaluate_rules_for_transaction` **tüm kullanıcıların** aktif `GoalRule`
kayıtlarını çekip tek bir kullanıcının işlemine uyguluyordu.

**Somut senaryo:** B kullanıcısının "her gelirin %10'u hedefe" kuralı aktifken A maaşını
girer → A'nın işlemi B'nin hedefine `GoalAllocation` olarak yazılır. B, kendi hedef
ekranında A'nın **tutarını** ve **transaction_id**'sini görür; A'nın hedef ilerlemesi ise
başkasının parasıyla şişer.

**Kök neden:** `GoalRule`'un kendi `user_id`/`workspace_id` sütunu yok — sahiplik **ebeveyn
`Goal`** üzerinden. Wave-5 statik kapısı yalnız "scope'suz `user_id ==`" arıyordu; bu sorguda
`user_id` hiç geçmediği için **kapıdan sessizce geçti**.

**Fix:** `Goal` join + `scope_filter(Goal, tx.user_id, tx.workspace_id)`. ADR-036 korunur —
aynı (aile) workspace'teki başka üyenin kuralı o workspace'in işlemine uygulanmaya devam eder.
**Kanıt:** `tests/test_goal_rules.py::test_15/16` (kırmızı→yeşil) + `test_17` pozitif kontrol.

### BUG #163 — Çok-kullanıcı net-değer geçmişi (doğruluk)
`scripts/backfill_net_worth.run_backfill` + `app/startup.catch_up_snapshots` yalnız **ilk
kullanıcıyı** işliyordu → 2. kullanıcıdan itibaren net-değer geçmişi hiç dolmuyor, trend/atıf
raporları sessizce eksik kalıyordu. Yazılan satırlarda `workspace_id` de NULL kalıyordu →
workspace-kapsamlı okumalar geçmişi göremiyordu.
**Kanıt:** `tests/test_backfill_multiuser.py` (3 test, kırmızı→yeşil).

### BUG #164 — Yıkıcı bakım script'i footgun'ı (KRİTİK, operasyonel)
`scripts/cleanup_orphan_traces.py` "gerçek kullanıcı = adı `test` ile başlamayan" sezgisiyle
**kalan herkesi** siliyordu (FK'lar `PRAGMA foreign_keys=OFF` ile kapalı, geri dönüşsüz).
Kapalı betada adı "Test…" olan **gerçek** bir kullanıcının tüm finansal verisi + hesabı silinirdi.
**Fix:** isim sezgisi kaldırıldı; `--keep-user-ids` + `--delete-user-ids` zorunlu, keep id'leri
DB'de doğrulanır, kesişim reddedilir, production'da ek onay şartı.
**Kanıt:** `tests/test_cleanup_script_guards.py` (6 test: 5 kilit + 1 pozitif kontrol).

### BUG #165 — Workspace kapsam tutarsızlığı (doğruluk)
`app/cashflow.generate_forecast`, `workspace_scope(...)` bloğu içinden çağrılmasına rağmen ham
`user_id` filtreliyordu → paylaşımlı (aile) workspace görünümünde nakit krizi / güvenli-harcama
rakamları **kişisel** veriden hesaplanıyor, workspace'in kendi kalemleri hiç sayılmıyordu.
**Fix:** 5 sorgu `rules_engine._scope` köprüsüne geçti. **Kanıt:** `tests/test_cashflow_workspace_scope.py`.

---

## 2. KURULAN KALICI KAPILAR

| Kapı | Dosya | Ne yakalar |
|---|---|---|
| Statik (mevcut, M70) | `tests/test_scope_enforcement.py` | scope'suz `Model.user_id ==` |
| **Statik (YENİ, P1)** | aynı dosya | **hiç sahiplik filtresi olmayan sorgu** — BUG #162'nin şekli. AST tabanlı, `app/` ağacının tamamı. İstisna yalnız `# scope-exempt: <gerekçe>` ile |
| **Meta (YENİ)** | aynı dosya | Kapının kendisi: sentetik BUG #162 deseni yakalanıyor mu, kapsamlı sorgu yanlış-pozitif veriyor mu, satır-sonu exempt yorumu görülüyor mu |
| **Runtime (YENİ)** | `tests/test_cross_user_isolation.py` | A yaratır → B id ile okur/yazar/siler → 403/404 (7 kaynak ailesi). Liste sızıntısı, crafted `account_id` ile yazma, `X-Workspace-Id` ile workspace ele geçirme |
| **Kapsam kilidi (YENİ)** | aynı dosya | Yeni `/{id}` endpoint'i matrise veya **gerekçeli** `MATRIS_DISI`'na yazılmazsa süit kırılır — kapsam kendiliğinden daralamaz |
| DB katmanı (mevcut) | `tests/test_rls_postgres.py` | PostgreSQL Row-Level Security (2. savunma) |
| **Koşucu (YENİ)** | `scripts/pg_gate_run.py` | Dual-dialect kapısını tek komutla koşar (docker'sız pgserver, `initdb --locale=C` tuzağı çözülü) |

---

## 3. KANITLAR

```
KOMUT : .\venv\Scripts\python.exe -m pytest tests/ -q
ÇIKTI : 1318 passed, 5 skipped in 63.10s
```
```
KOMUT : .\venv\Scripts\python.exe scripts/pg_gate_run.py
ÇIKTI : 13 passed in 6.36s   (RLS + Numeric + net-worth + NULL-ordering, PostgreSQL)
YORUM : Bu kapı önceden SKIP oluyordu (postgres ayakta değildi) → yani DOĞRULANMAMIŞTI.
```
```
KOMUT : .\venv\Scripts\python.exe -m pytest tests/test_cross_user_isolation.py -q
ÇIKTI : 17 passed
```

---

## 4. TRİYAJ EDİLEN, AÇIK OLMADIĞI DOĞRULANAN NOKTALAR

Bunlar tarama sırasında "kapsamsız" göründü; her biri **tek tek** incelendi ve gerekçesi koda
`# scope-exempt:` olarak yazıldı (sessiz geçiş yok):

- `accounts.py` çocuk sayımları — sahipliği doğrulanmış hesabın alt kayıtları.
- `goals.py` allocation/rule listeleri — ebeveyn `Goal` sahipliği hemen üstte doğrulanıyor.
- `goal_engine.unlink_transaction`, `goal_rules._matches` — sahiplik çağıranda / tx üzerinden.
- `premortem.link_premortem_outcome` — sentinel küresel benzersiz `PendingAction` id'si taşır.
- `reasoning_trace` — yalnız kendi örneğinin yazdığı satır id'leri.
- `scheduler` fiyat cron'u — sistem işi (piyasa verisi), kullanıcı verisi okunmuyor.
- `fund_tracker` (BUG #115) — her iki çağıran `user_id` geçiriyor, doğrulandı.
- `PendingAction` / `CoachMemory` / `ReasoningTrace` / `ApiCallLog` — **kişisel-bağlı** modeller
  (workspace paylaşımı yok), `user_id` ile kapsanıyor. İki yerde savunma derinliği eklendi.

## 5. KABUL EDİLEN (düşük) RİSKLER — belgelenmiş, kapatılmadı

- `premortem` `DecisionJournal` satırlarını `workspace_id=NULL` yazıyor. Bugün
  DecisionJournal'ın **workspace-kapsamlı okuyucusu yok** (tek okuyucu: kullanıcı dışa-aktarımı,
  `user_id` ile kapsalı) → etkisiz. Workspace-kapsamlı bir okuyucu eklenirse **önce bu düzeltilmeli**.
- `goal_engine` fonksiyonları sahipliği kendi içinde doğrulamıyor (çağıran doğruluyor).
  Yeni bir çağıran eklenirse sahiplik kontrolü o çağırana düşer — statik kapı bunu
  `# scope-exempt` yorumuyla görünür kılar.

## 6. SONRAKİ

P1 kapandı. Sıradaki yayın-engeli: **P3.5 ürünleşme** (tek-kullanıcı DNA'sının sökülmesi) ve
**P2 güvenlik review**.
