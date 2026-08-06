# PUBLISH DOĞRULAMA DENETİMİ — 8 boyut, salt-okur + çelişme turu

**Koşum:** 5 Ağustos 2026, 13:20-13:54 · 49 ajan · 3.97M token · workflow `wf_ddd8b54e-1c9`
**Yöntem:** her boyut bağımsız bir denetçi tarafından SALT-OKUR tarandı (kod okuma + kendi geçici probları + canlı DB salt-okur sorguları); ardından **her bulgu ayrı bir çelişme (adversarial) ajanına** verildi ve çürütülmeye çalışıldı. Aşağıdakiler çelişme turundan SAĞ ÇIKAN bulgulardır.
**Sonuç:** 40 bulgu onaylandı, 1 çürütüldü.

> ⚠️ Denetim, bu oturumdaki BUG #217/#220 düzeltmelerinden ÖNCEKİ ağaçta koştu. Test-kalitesi boyutundaki 4 bulgu o düzeltmelerin bağımsız doğrulamasıdır; durumu tabloda işaretlendi.

## Özet — şiddete göre

| Şiddet | Adet |
|---|---|
| kritik | 1 |
| yuksek | 12 |
| orta | 17 |
| dusuk | 10 |

## Bulgular (şiddet sırasıyla)

### D01 · [kritik] Koç-onaylı işlem workspace_id=NULL yazılıyor → kullanıcının KENDİ işlem listesinden/raporundan kayboluyor (bakiye değişiyor)

- **Boyut:** izolasyon · **Yer:** `app/action_executor.py:615` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** Kayıt ZORUNLU olarak workspace'e bağlı okunuyor (app/routers/transactions.py:260 scope_filter). Production'da her kullanıcının personal workspace'i var (app/routers/auth.py:180 ensure_personal_workspace + app/workspace_deps.py:88 production fail-fast), yani bu yol HER kullanıcıda AÇIK. Kullanıcı koça 'X TL harcadım' der, onaylar, bakiyesi düşer ama işlem hiçbir listede/raporda/bütçede görünmez → para 'buharlaştı' algısı, yanlış kategori bütçesi, yanlış reel_butce, hatalı harcama analizi. Ürünün amiral özelliği (koç ile kayıt) sessizce kayıt kaybediyor; finansal uygulamada bu doğrudan güven ve kullanıcı kaybıdır.

<details><summary>Kanıt</summary>

```
KOD (app/action_executor.py:615-624) — diğer tüm yazıcılar workspace_id set ederken bu INSERT etmiyor:
    txn = Transaction(
        user_id=user_id,
        account_id=account_id,
        transaction_type=TransactionType(txn_type),
        amount=amount,
        ...
    )   # workspace_id YOK

ÇALIŞMA-ANI KANIT (kendi yazdığım geçici test, in-memory DB; kullanıcı + personal workspace + kasa 10.000 TL, propose_action→POST /api/actions/{id}/approve):
  pending.workspace_id = 1  (personal ws id = 1)
  YAZILAN Transaction.workspace_id = None
  hesap bakiyesi = 9500.0000        <-- bakiye DÜŞTÜ
  GET /api/transactions -> 200 []   <-- işlem GÖRÜNMÜYOR
  cockpit nakit_kasa = 9500.0
  kategori dagilimi = {"items":[],"grand_total":0.0,...}   <-- harcama raporda YOK

CANLI DB KANIT (data/financialos.db, salt-okur sqlite3):
  select workspace_id,count(*) from transactions group by workspace_id -> [(None, 1)]
  select id,user_id,workspace_id,account_id,amount,category,transaction_date from transactions
     -> [(1, 1, None, 1, 2310, 'sigara', '2026-08-04')]
  select workspace_id,count(*) from accounts group by workspace_id -> [(1, 4)]
  select id,name,is_personal,owner_user_id from workspaces -> [(1,'Murat Kişisel',1,1)]
Yani canlı kurulumda tek işlem satırı ws=NULL, tüm hesaplar ws=1 → scope_filter(Transaction,1,1) bu satırı ELEMEKTE.

OTOMATİK KAPI YOK: tüm süit yeşil (1608 passed, 6 skipped) — hiçbir test bunu yakalamıyor.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

BULGU AYAKTA — curutulemedi. Curutmeye calistigim her katman acik cikti.

1) KOD (okundu). `app/action_executor.py:615-624` — `Transaction(user_id=..., account_id=..., transaction_type=..., amount=..., category=..., description=..., transaction_date=..., is_card_expense=...)`; `workspace_id` YOK. Karsilastirma: `app/routers/transactions.py:353` -> `Transaction(user_id=user.id, workspace_id=ws_id, **data)` ve `app/routers/onboarding.py:100` -> `Transaction(user_id=..., workspace_id=ws_id, ...)`. `grep -rn "Transaction(" app/` sonucu: uygulamada TOPLAM 3 Transaction insert'i var, workspace_id'yi atlayan TEK yer action_executor:615. Dispatcher da workspace tasimiyor: `execute_pending_action` handler'i `handler(db, user_id, payload)` imzasiyla cagiriyor (satir 454); `pending.workspace_id` yalnizca `enforce_user_rules`'a veriliyor (satir 447), yazmaya gecmiyor.

2) BASKA KATMAN KAPATIYOR MU? Hayir.
- ORM hook yok: `grep -rn "before_insert|listens_for" app/*.py` -> yalnizca `database.py:66` (sqlite connect) ve `database.py:87` (after_begin GUC). workspace_id damgalayan mapper event'i YOK.
- Model default yok: `app/models.py:367` `workspace_id = Column(Integer, ForeignKey("workspaces.id"), nullable=True, index=True)` — nullable, default yok, DB constraint yok.
- Okuma tarafi NULL'u eliyor: `app/workspace_deps.py:99-107` `scope_filter` -> `workspace_id is not None` ise `model.workspace_id == workspace_id` (NULL satir eslesmez). `active_workspace_id` (satir 81-92) header yoksa personal workspace'e duser ve production'da personal ws yoksa 500 fail-fast eder -> prod'da ws_id HER ZAMAN dolu -> bu yol her kullanicida ACIK.
- Postgres RLS durumu DAHA KOTU: `alembic/versions/f5a6b7c8d9e0_enable_rls_scoped_tables.py` policy'si USING-only (WITH CHECK yok) -> NULL ws INSERT'i REDDETMEZ; USING ifadesi `workspace_id = current_setting(...)::int` oldugundan GUC set edilmisken NULL satir SELECT'te de gorunmez. Yani prod'da hem yazilir hem gizlenir.
- Runtime backfill yok: NULL->personal ws duzeltmesi yalnizca ELLE calisan `scripts/create_personal_workspaces.py`'de (satir 73-74). `app/main.py` lifespan'indaki "catch-up backfill" net-worth backfill'i; scheduler'da workspace backfill job'u yok.
- Statik kapi kapsam disi: `tests/test_scope_enforcement.py` AST tarayicisi yalnizca SORGULARI (db.query/select) denetliyor, INSERT'te eksik workspace_id'yi denetlemiyor.

3) KENDI CALISTIRDIGIM REPRO (scratchpad'de gecici pytest, proje dosyasina dokunulmadi; in-memory SQLite, user + personal ws(id=1) + Nakit Kasa 10.000 TL, propose_action(workspace_id=1) -> POST /api/actions/1/approve):
  pending.workspace_id = 1
  approve status: 200
  txn id=1 ws=None amount=500.0000 cat=market      <-- workspace_id NULL yazildi
  hesap bakiyesi: 9500.0000                         <-- bakiye DUSTU
  GET /api/transactions -> 200 []                   <-- islem listede YOK
  cockpit nakit_kasa: 9500.0
  GET /api/reports/category-breakdown -> {"items":[],"grand_total":0.0,...}   <-- raporda YOK

4) CANLI DB (salt-okur, `data/financialos.db`, mode=ro):
  transactions ws dagilimi -> [(None, 1)]; satir -> (id=1, user_id=1, workspace_id=None, account_id=1, amount=2310, 'sigara')
  accounts ws dagilimi -> [(1, 4)];  workspaces -> [(1,'Murat Kisisel',1,1)]
  pending_actions'ta 3 'executed' kayit var (17 add_transaction, 18 pay_credit_card, 19 add_transaction 2026-08-04 19:50) — tek transaction satiri koc onayindan gelmis ve ws=NULL. Yani hata canli kurulumda ZATEN gerceklesmis.

5) OTOMATIK KAPI YOK: `grep -rn "workspace" tests/test_execute_pending_action.py tests/test_actions_lifecycle.py tests/test_sifirdan_kullanici_e2e.py` -> hicbir assertion yok. Suit yesil oldugu halde hata yasiyor.

6) BELGELENMIS KABUL-EDILEN RISK DEGIL: `docs/kalite-seruveni/guvenlik-review-publish.md` §4 (kabul edilen riskler: e-posta enumerasyonu, prompt injection, localStorage token) ve §1 kapatilan buglar listesinde bu madde YOK.

ZARAR / YAYIN ENGELI: Urunun amiral akisi (koca "X TL harcadim" de -> onayla)
</details>

### D02 · [yuksek] Koç-onaylı Master Checkpoint (kırmızı çizgi) workspace_id=NULL → panelde de koç bağlamında da yok

- **Boyut:** izolasyon · **Yer:** `app/action_executor.py:936` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** Kullanıcı koça 'nakit tabanım 5000 TL' gibi bir kırmızı çizgi söyler, koç kaydeder, kullanıcı 'kaydedildi' geri bildirimi alır — ama çizgi ne Kırmızı Çizgiler panelinde görünür, ne koçun sistem bağlamına girer, ne de kural motorunun okuduğu kümededir. Ürünün en temel güvenlik vaadi (Master Checkpoint enforcement) koç üzerinden yaratılan çizgiler için fiilen çalışmaz; kullanıcı korunduğunu sanırken korunmaz. Bu para kaybına yol açan sessiz bir yanlış-güven durumudur.

<details><summary>Kanıt</summary>

```
KOD (app/action_executor.py:936-943):
    cp = MasterCheckpoint(
        user_id=user_id,
        title=title,
        description=desc,
        checkpoint_type=cp_type_enum,
        priority=int(priority),
        is_active=True,
    )   # workspace_id YOK

ÇALIŞMA-ANI KANIT (geçici test, personal workspace'li kullanıcı; propose_action('add_master_checkpoint') → approve):
  YAZILAN MasterCheckpoint.workspace_id = None
  GET /api/checkpoints -> 200 []
  AssertionError: Koc-onayli kirmizi cizgi panelde YOK (workspace_id=None)

OKUYUCU TARAFI:
  app/routers/checkpoints.py:120  db.query(MasterCheckpoint).filter(scope_filter(MasterCheckpoint, user.id, ws_id))
  app/coach.py:862-871            MasterCheckpoint.user_id == user_id ... if workspace_id is not None: .filter(MasterCheckpoint.workspace_id == workspace_id)
  app/user_rules.py:151-156       scope_filter(MasterCheckpoint, user_id, workspace_id)
Üçü de ws_id doluyken NULL satırı eler.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

Bulgu DISKTEN DOGRULANDI, curutulemedi. (1) Kod aynen iddia edildigi gibi: app/action_executor.py:936-943 MasterCheckpoint'i workspace_id olmadan yaratiyor; karsilastirma noktasi app/routers/checkpoints.py:137 (panel yolu) workspace_id=ws_id GECIYOR. (2) Telafi katmani YOK: app/models.py:390 kolonda default/server_default yok; app/database.py'deki tek workspace listener'i after_begin (Postgres GUC, okuma-tarafi RLS, SQLite no-op) — insert'i doldurmuyor; grep before_insert/before_flush/listens_for app/*.py baska hook gostermiyor. workspace_scope (app/rules_engine.py:134-147) sadece sorgu-tarafi contextvar; execute_pending_action handler'i handler(db,user_id,payload) ile cagiriyor (satir 454), workspace handler'a hic ulasmiyor. (3) Okuyucu taraf gercekten NULL'u eliyor: app/workspace_deps.py:99-107 scope_filter kati esitlik (is_(None) OR dali yok), app/coach.py:869-871 ayni. (4) CALISMA-ANI KANIT (scratchpad script, repo dosyasi degistirilmedi, gercek FastAPI TestClient): personal workspace'li kullanicida POST /api/actions/{id}/approve -> 200 ve mesaj "Yeni kural eklendi: 'Nakit tabani 5000 TL'."; DB satiri (1,'Nakit tabani 5000 TL', None); GET /api/checkpoints -> 200 []. Ayrica uc okuyucu (panel filtresi, coach._build_context_message filtresi, user_rules kumesi) hepsi 0 dondu, ayni anda panelden yaratilan kontrol satiri 1 dondu. (5) Prod'da erisilebilir: canli data/financialos.db'de workspaces=[(1,'Murat Kisisel',1,1)] -> active_workspace_id her zaman non-None doner (app/workspace_deps.py:81-83), mevcut 8 checkpoint'in hepsi workspace_id=1; yani yeni koc-uretimi NULL satir gorunmez olur. Koc bu action'i sunuyor (app/coach.py:413 ve :435 payload sablonu). (6) Otomatik onarim yok: scripts/create_personal_workspaces.py elle tek-sefer script (__main__), app/ icinden cagrilmiyor. (7) docs/kalite-seruveni/guvenlik-review-publish.md'de belgelenmis kabul-edilen-risk DEGIL. DUZELTME (siddet ayari): _execute_add_master_checkpoint rule_type/rule_params yazmiyor, dolayisiyla koc-uretimi cizgiler zaten serbest-metin; app/user_rules.py:153-155 rule_type.isnot(None) sartiyla filtreledigi icin bunlar workspace hatasi olmasa da kod-seviyesi dayatmaya hic girmiyordu. Yani bulgudaki "Master Checkpoint enforcement fiilen calismaz / para kaybi" ifadesi abartili; gercek zarar sessiz veri kaybi + yanlis "kaydedildi" onayi + cizginin kocun kendi baglamindan da dusmesi (kullanici bir daha hatirlatilmaz). Bu yayin engeli sayilir ama kritik degil: capraz-kullanici sizinti yok, yanlis para hareketi yok. Ek not: tests/test_add_master_checkpoint.py bu hatayi kaciriyor cunku workspace yaratmiyor, legacy user_id yoluna dusuyor.
</details>

### D03 · [yuksek] /api/cashflow/forecast ve /api/debt-strategy/* workspace bağlamını hiç kurmuyor — BUG #165 fix'i uç seviyesinde bağlanmamış

- **Boyut:** izolasyon · **Yer:** `app/routers/cashflow.py:84` · **Durum:** ✅ **KAPANDI — BUG #223** (5 Ağu).
  4 uç (`cashflow/forecast`, `debt-strategy/compare|consolidation|opportunity-cost`)
  `Depends(active_workspace_id)` + `with workspace_scope(ws_id):` deseniyle cockpit'e
  hizalandı; üyelik doğrulaması da bu dependency'den geldi (üye olunmayan ws → 403).
  Kapı: `tests/test_cashflow_debt_endpoint_workspace_scope.py` (12 test, HTTP seviyesinde;
  düzeltme öncesi 12'si de kırmızıydı). **Sınıf taraması:** aynı kör nokta `routers/premortem.py`
  ve `routers/simulation.py` içinde de ölçüldü → ayrı bulgu olarak açıldı (aşağıda D03b).
- **Neden yayın engeli / etki:** ADR-036 paylaşımlı (aile) workspace özelliği canlı (POST /api/workspaces/{id}/invite mevcut). Aile görünümündeyken kullanıcının KİŞİSEL borçları ve kişisel nakdi bu ekranlarda görünüyor — kullanıcı 'burada yalnız ortak veriler var' varsayımıyla ekranı aile üyesine gösterirse özel finansal bilgisi istem dışı ifşa olur. Ayrıca aynı bağlamda cockpit 0 TL borç derken debt-strategy iki borç listeliyor (60.000 vs 50.000) → çelişen rakamlar üzerinden yanlış borç kapatma/harcama kararı.

<details><summary>Kanıt</summary>

```
KOD: app/routers/cashflow.py:84-116 — imzada `active_workspace_id` YOK, gövdede `workspace_scope(...)` YOK; generate_forecast ham çağrılıyor. app/cashflow.py:292 `_scope(Account, user_id)` contextvar boş olduğu için HER ZAMAN user_id'ye düşer.
app/routers/debt_strategy.py:81/114/136 — aynı şekilde `collect_debts(db, current_user.id)`, workspace_scope yok.

ÇALIŞMA-ANI KANIT (tek kullanıcı, iki workspace: kisisel + aile; X-Workspace-Id = aile):
  AILE workspace baglaminda debt-strategy borclari: ['KISISEL-KART', 'KISISEL-KREDI']
  AILE workspace cockpit kredi_borcu = 0.0  kart_borcu = 0.0
  AILE baglami: cashflow opening_balance = 60000.0  / cockpit nakit_kasa = 50000.0
     (kisisel kasa 10.000 + aile kasa 50.000 toplanmış; cockpit doğru şekilde yalnız 50.000 diyor)

MEVCUT TESTİN KÖR NOKTASI: tests/test_cashflow_workspace_scope.py yalnız `generate_forecast`'i `with workspace_scope(aile.id):` bloğu içinde çağırıyor (satır 70/83/93/95) — HTTP ucunu hiç çağırmıyor, bu yüzden ucun bağlamı hiç kurmadığı görülmüyor.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

ÇÜRÜTÜLEMEDİ — diskten ve çalışma-anından doğrulandı.

1) KOD: app/routers/cashflow.py:84-116 imzasında `active_workspace_id` bağımlılığı YOK, gövdesinde `workspace_scope(...)` YOK; `generate_forecast(db=db, user_id=current_user.id, ...)` ham çağrılıyor. app/routers/debt_strategy.py:81 (`compare_strategies(db, current_user.id, ...)`), :114 ve :136 (`collect_debts(db, current_user.id)`) aynı durumda. Doğru desen aynı repoda mevcut: app/routers/cockpit.py:72 `ws_id: Optional[int] = Depends(active_workspace_id)` + :89 `with workspace_scope(ws_id):`.

2) BAŞKA KATMAN KAPATMIYOR: app/main.py'de yalnız CORSMiddleware + request_limits.GovdeBoyutuMiddleware kayıtlı; workspace contextvar'ını kuran global middleware/dependency yok (`grep -i middleware app/` ile doğrulandı). app/rules_engine.py:128-146 — contextvar set edilmemişse `_scope` `model.user_id == user_id`'ye düşer. frontend/src/api.js:124 `X-Workspace-Id` başlığını HER isteğe ekler (cashflowApi/debtStrategyApi dahil, api.js:423-450) → UI aile workspace'indeyken bu iki panel başlığı sessizce yok sayar.

3) ÇALIŞMA-ANI KANIT (FastAPI TestClient ile gerçek HTTP uçları, in-memory SQLite, tek kullanıcı + kisisel/aile workspace, X-Workspace-Id=aile):
   [debt-strategy/compare] 200 — AILE bağlamında listelenen borçlar: ['KISISEL-KART', 'KISISEL-KREDI']
   [debt-strategy/consolidation] 200, [opportunity-cost] 200 (aynı kişisel borç kümesiyle)
   [cashflow/forecast] 200 — opening_balance: 60000.0 (10.000 kişisel + 50.000 aile toplanmış), total_receivable: 45000.0 (kişisel maaş)
   [cockpit] 200 — nakit_kasa: 50000.0, kart_borcu: 0.0, kredi_borcu: 0.0
   Yani aynı ekranda cockpit "0 TL borç / 50.000 nakit" derken debt-strategy iki kişisel borç, cashflow 60.000 açılış diyor.
   Ek: üye olunmayan ws=9999 başlığıyla cashflow 200 ve debt-strategy 200 döndü (cockpit doğru şekilde 403) — bu uçlar üyelik doğrulaması da yapmıyor.

4) İKİNCİ KULLANICI SENARYOSU (eş, aile workspace'inde editor): debt-strategy yalnız ['ESI-KART'] (kendi kişisel kartı) döndü, AILE-KREDI'yi hiç göstermedi; aynı bağlamda cockpit kredi_borcu=40000.0 dedi. Yani paylaşımlı workspace'te snowball/avalanche, konsolidasyon ve fırsat-maliyeti simülasyonları tamamen YANLIŞ borç kümesi üzerinde koşuyor (gerçek ortak borcu atlıyor, kişisel borcu katıyor).

5) MEVCUT TEST KÖR NOKTASI DOĞRU: tests/test_cashflow_workspace_scope.py:70/83/93/95 `generate_forecast`'i doğrudan `with workspace_scope(...)` içinde çağırıyor; HTTP ucunu hiç çağırmadığı için ucun bağlamı kurmadığı görülmüyor.

6) KABUL EDİLEN RİSK DEĞİL: docs/kalite-seruveni/guvenlik-review-publish.md §4'teki üç kabul-edilen risk (e-posta enumerasyonu, depolanmış-metin prompt injection, localStorage token) bunu kapsamıyor; §1/§3'te de geçmiyor.

BULGUNUN DÜZELTİLMESİ GEREKEN KISMI (şiddeti kritik'ten yüksek'e indiren): bu bir ÇAPRAZ-KULLANICI ifşası DEĞİL. Eş kullanıcı testinde Murat'ın MURAT-GIZLI-KREDI hesabı eşin yanıtında ÇIKMADI (fallback `user_id`'ye düştüğü için her kullanıcı yalnız kendi verisini görüyor). Dolayısıyla API üzerinden başka hesabın verisi sızmıyor; ifşa yalnız "kullanıcı aile ekranını üyeye gösterirse" dolaylılığında. Asıl kesin zarar para tarafında: paylaşımlı workspace canlı (POST /api/workspaces/{id}/invite mevcut, app/routers/workspaces.py:210) ve aynı ekranda çelişen borç/nakit rakamları + yanlış veri kümesiyle üretilen borç kapatma/konsolidasyon tavsiyeleri kullanıcıyı hatalı finansal karara götürür. Yayın engeli olacak kadar ciddi, ancak hesap-ele-geçirme/çapraz-kiracı sızıntı sınıfı olmadığı için "kritik" değil, "yüksek".
</details>

### D03b · [yuksek] D03'ün AYNI SINIFI: premortem ve simülasyon uçları da workspace bağlamı kurmuyor (D03 düzeltilirken ölçüldü)

- **Boyut:** izolasyon · **Yer:** `app/routers/premortem.py:93`, `app/routers/simulation.py:81` · **Durum:** ✅ **KAPANDI — BUG #224** (5 Ağu).
  İki uç `Depends(active_workspace_id)` + `with workspace_scope(ws_id):` deseniyle bağlandı
  (üyelik doğrulaması da geldi: üye olunmayan ws → 403). Motor katmanı için köprü
  `app/rules_engine.py`'den **yaprak modül `app/scope.py`'ye taşındı** — `simulation_engine`
  tasarım gereği rules_engine'i import etmiyor, bu yüzden köprüye erişemiyordu; artık
  katman ihlali olmadan aynı contextvar'ı paylaşıyorlar (rules_engine geriye-uyum re-export'u
  yapar, mevcut ~20 import yeri değişmedi). `_load_world`'ün 3 sorgusu `scope_expr`'e geçti.
  Kapı: `tests/test_premortem_simulation_workspace_scope.py` (7 test; **mutasyon kontrolü
  yapıldı** — köprü ham `user_id`'ye çevrilince 3 test kırmızıya döndü).
- **Nasıl bulundu:** D03 kapatılırken sınıf taraması yapıldı (L11 — "bir örnek bulunduysa sınıf taranmadan kapatılmaz"). `app/routers/*.py` üzerinde "kapsam-duyarlı motor çağırıyor mu / workspace bağlamı kuruyor mu" ölçümü: engine>0 ve ws=0 olan iki router kaldı.
- **Neden yayın engeli / etki:** ADR-036 paylaşımlı workspace canlı. Aile bağlamındayken bir aksiyonun ön-ölüm (premortem) analizi ve 3-ufuklu simülasyonu **kişisel** finansal manzara üzerinde koşar → kullanıcı ekranda gördüğü aile rakamlarıyla çelişen bir risk/etki analizi okur ve ona göre karar verir. `simulation_engine` hiç workspace-farkında değil (3 sorgu da ham `Model.user_id == user_id`), yani bu bir uç-bağlama düzeltmesinden fazlası: motor katmanı da köprüye geçirilmeli.

<details><summary>Kanıt (statik, disk)</summary>

```
app/routers/premortem.py — dosyada `workspace_scope` / `active_workspace_id` / `scope_filter` YOK (0 eşleşme);
  :93 `snapshot = build_cockpit_snapshot(db, current_user.id)` → app/cockpit_snapshot.py:50 `generate_cockpit(user_id, today, db)`
  (generate_cockpit kapsam-duyarlı ama contextvar boş → legacy user_id dalı).
app/routers/simulation.py — aynı şekilde 0 eşleşme; :121 `simulate_action(..., user_id=current_user.id, ...)`.
app/simulation_engine.py:134/162/178 — `Account.user_id == user_id`, `RecurringIncome.user_id == user_id`,
  `PersonalDebt.user_id == user_id` — `_scope` köprüsü hiç kullanılmıyor (workspace_id'ye hiç bakmıyor).
```
</details>

### D04 · [yuksek] Sifre sifirlama token'i, kullanici sifresini degistirdikten sonra HALA gecerli — hesap geri alinamiyor (BUG #172 ailesinin acik kalan kolu)

- **Boyut:** kimlik-oturum · **Yer:** `app/routers/auth.py:465` · **Durum:** ✅ **KAPANDI — BUG #225** (5 Ağu).
  `create_password_reset_token` artık `token_version`'ı payload'a yazar (eskiden `tv` daima 0'dı,
  yani sürüm kontrolü eklense bile etkisiz kalırdı) + `password_reset_confirm` `token_version_ok(...)`
  doğrular. Sayacı artıran her olay (şifre değişimi, başka bir sıfırlamanın kullanılması) bekleyen
  bağlantıları öldürür. Kapı: `tests/auth/test_pwreset_token_gecerliligi.py` (5 test — denetimin
  PoC'si + iki-canlı-bağlantı senaryosu + meşru akışın bozulmadığı + tek-kullanımlık regresyonu
  + `tv` claim'inin gerçekten taşındığı). Düzeltme öncesi 3'ü kırmızıydı.
  **Sınıf taraması (L11):** diğer token tipleri de bakıldı — `email_verify` (tek-kullanımlık,
  yalnız `email_verified_at` yazar), `oauth_exchange` (60 sn, tek-kullanımlık), `email_change`
  (2 saat + eski-adres bağı). Hiçbiri hesap-ele-geçirme sınıfında değil; sıfırlama tek koldu.
- **Neden yayın engeli / etki:** Posta kutusuna gecici erisim saglayan saldirgan (paylasilan bilgisayar, ele gecirilmis e-posta, iletilmis bir sifirlama postasi) bir sifirlama baglantisini alip BEKLETEBILIR. Kullanicinin dogru refleksi olan 'hemen sifremi degistireyim' saldirganin elindeki baglantiyi OLDURMEZ; saldirgan 30 dakika icinde sifreyi tekrar degistirip hesabi kalici olarak ele gecirir ve gercek sahibini disarida birakir. Hesap icinde tum banka hesap bakiyeleri, borclar, islem gecmisi ve KVKK export'u (GET /api/users/me/export) bulunur; ayrica DELETE /api/users/me ile tum veri geri alinamaz sekilde silinebilir. Uygulama kullaniciya 'Güvenlik için tüm oturumlar kapatıldı' diyerek yanlis guvenlik hissi de verir.

<details><summary>Kanıt</summary>

```
KOD: password_reset_confirm() yalnizca KENDI jti'sini kara listeye alir (satir 473-484); ne `token_version_ok(payload, user)` cagrilir ne de kullanicinin DIGER acik pwreset token'lari gecersizlestirilir. app/auth.py:153 `create_password_reset_token()` token_version parametresi GECMEZ -> payload'daki tv daima 0 (yani tv kontrolu eklense bile su haliyle calismazdi).

CALISTIRILAN KANIT (scratchpad/proof_pwreset.py, TestClient + in-memory SQLite):
0) kayit: 201
1) saldirganin ele gecirdigi sifirlama token'i alindi (user_id=1)
2) kurban sifresini degistirdi -> 200        # POST /api/auth/change-password (BUG #190 yolu, token_version++ )
3) saldirgan ESKI sifirlama token'i ile -> 200 {'message': 'Şifre güncellendi. Güvenlik için tüm oturumlar kapatıldı.'}
4) saldirgan girisi -> 200                   # saldirganin belirledigi sifreyle giris BASARILI
5) kurban girisi (kendi yeni sifresiyle) -> 401   # kurban DISARIDA

Ayni kok neden ikinci senaryoda da gecerli: kullanici arka arkaya iki kez 'sifremi unuttum' derse iki token da 30 dk boyunca ayni anda canli kalir; birinin kullanilmasi digerini oldurmez.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

CURUTULEMEDI — bulgu diskten dogrulandi, hem kod okumasi hem bagimsiz calistirilan PoC ile.

KOD KANITI (salt-okur):
1. `app/routers/auth.py:465-486` `password_reset_confirm()`: `decode_token(..., expected_type="pwreset")` -> `token_revoked(jti)` -> yeni hash -> `user.token_version += 1` -> `revoke_jti(kendi jti)`. `token_version_ok(payload, user)` CAGRILMIYOR ve kullanicinin DIGER acik pwreset jti'leri kara listeye alinmiyor. Bulgunun tarifi birebir dogru.
2. `app/auth.py:153-155` `create_password_reset_token(user_id, ttl_minutes=30)` -> `_create_token(user_id, "pwreset", ...)`; `token_version` parametresi GECMIYOR, `_create_token` default'u 0 (`app/auth.py:96-105`, `"tv": int(token_version or 0)`). Yani payload'daki tv daima 0 — tv kontrolu eklense bile bu haliyle etkisiz olurdu. PoC ciktisi bunu dogruladi: `token payload tv/type: 0 pwreset`.
3. `app/routers/auth.py:297-321` `change_password()` (BUG #190) yalnizca `token_version`'i artirir; bekleyen pwreset jti'lerini iptal etmez.
4. BASKA KATMAN YOK: `grep -rn "revoke_jti|RevokedToken|token_version_ok" app/` -> `token_version_ok` sadece `app/dependencies.py:83` (access token) ve `app/routers/auth.py:263` (refresh rotasyonu) icinde. Kullanici-bazli toplu iptal (per-user revocation) hicbir yerde yok. Middleware/dependency/model constraint/migration/nginx katmaninda risk kapali degil.

CALISTIRILAN KANIT (kendi yazdigim bagimsiz PoC, TestClient + in-memory SQLite, proje venv'i; scratchpad/test_denetim_pwreset.py — proje dosyalarina DOKUNULMADI):
  0) register: 201
  1) reset-request: 200, token alindi, payload tv=0 type=pwreset
  2) change-password (kurban, dogru refleks): 200
  3) reset-confirm ESKI token ile: 200 {"message":"Sifre guncellendi. Guvenlik icin tum oturumlar kapatildi."}
  4) saldirgan login: 200   <- saldirgan iceride
  5) kurban login (kendi yeni sifresiyle): 401   <- kurban disarida
  SONUC: saldirgan_icerde = True | kurban_disarida = True
Ikinci senaryo da dogrulandi: ayni kullanici icin iki ayri pwreset token alindi; birincisi kullanildiktan (200) SONRA ikincisi hala 200 dondu — es-zamanli sifirlama token'lari birbirini oldurmuyor.
(Token'i elde etmek icin dev-modun `_dev_token` yanitini kullandim; bu yalnizca token'i ele gecirme adiminin ikamesidir — prod'da ayni token `password_reset_request` icinde e-posta linkine gomuluyor, `app/routers/auth.py:443-448`. Aciklik dev-token'dan bagimsizdir, kok neden confirm akisindaki eksik kontroldur.)

ZARAR DOGRULAMASI: Ele gecirilen hesapla `GET /api/users/me/export` (KVKK tam veri disa aktarimi, `app/routers/auth.py:628`) ve `DELETE /api/users/me` (`app/routers/auth.py:612`, `purge_user_data` — "Geri alinamaz") erisilebilir. Yani banka bakiyeleri/borclar/islem gecmisi sizar ve veri kalici silinebilir.

BELGELENMIS KABUL-EDILEN RISK DEGIL: `docs/kalite-seruveni/guvenlik-review-publish.md` satir 19 yalnizca TERS yonu belgeliyor ("sifirlama oturumlari dusurmuyordu", BUG #172 — duzeltildi). Sifre degisiminin bekleyen sifirlama token'ini oldurmemesi dokumanda hic gecmiyor; gerekceli kabul-edilen-risk kaydi yok.

SIDDET GEREKCESI (kritik degil, yuksek): Uzaktan kimlik-dogrulamasiz saldirgan tek basina somuremiyor; on-kosul saldirganin bir sifirlama baglantisini ele gecirmesi (paylasilan bilgisayar, ele gecirilmis/iletilmis posta) ve 30 dakikalik pencere. Ancak bu on-kosul saglandiginda kurbanin dogru refleksi (hemen sifre degistirme) saldiriyi DURDURMUYOR — kalici hesap ele gecirme + kurbanin disarida kalmasi + uygulamanin "tum oturumlar kapatildi" diyerek yanlis guvenlik hissi vermesi. OWASP'in standart gereksinimi (sifre degisiminde bekleyen sifirlama token'lari gecersizlestirilir) ihlal edilmis durumda; kapali beta oncesi kapatilmasi gereken gercek bir yayin engeli.
</details>

### D05 · [yuksek] OAuth callback, kapali-beta davet kapisini tamamen atliyor — REGISTRATION_MODE=invite_only iken sinirsiz hesap acilabiliyor

- **Boyut:** kimlik-oturum · **Yer:** `app/routers/auth.py:556` · **Durum:** ✅ **KAPANDI — BUG #226** (5 Ağu).
  OAuth akışında davet kodu girilecek alan yok (kullanıcı sağlayıcıya gidip geliyor) → kapı
  **e-posta eşleşmeli davet** üzerinden kuruldu: davetli-only modda YENİ OAuth kullanıcısı ancak
  kendi adresine açılmış, kullanılmamış, süresi geçmemiş bir davet varsa yaratılır ve davet aynı
  transaction'da TÜKETİLİR (`BetaInvite` artık gerçeği yansıtır). Süre/kullanım/adres kuralları
  tek kaynaktan (`davet_dogrula`) uygulanır — ikinci kural kopyası yok. E-postasız (yalnız-kod)
  davetler bu yolda fail-closed kalır; operatör aracı (`scripts/beta_invite.py`) ve runbook bunu
  açıkça uyarır. MEVCUT kullanıcının girişi etkilenmez (davet kayıt kapısıdır, giriş kapısı değil).
  Kapı: `tests/auth/test_oauth_davet_kapisi.py` (11 test — PoC, `/register` ile aynı davranış,
  meşru davetli akışı + davet tüketimi, büyük/küçük harf, mevcut kullanıcı girişi, `open` modda
  davranış değişmedi, tükenmiş/süresi geçmiş/başka adrese açılmış/e-postasız davet, `/api/meta`
  beyanının kodda karşılığı). Düzeltme öncesi 8'i kırmızıydı.
- **Neden yayın engeli / etki:** BUG #199'un tum gerekcesi 'kapali beta bir iddia degil kontrol olsun' idi; bu yol o kontrolu fail-open birakiyor. OAuth yapilandirilmis bir canliya cikista, alan adini bilen herkes Google/GitHub hesabiyla tek tikla FinancialOS hesabi acar: (a) davetsiz, izlenemeyen kullanicilar KVKK'da veri sorumlusu yukumlulugu dogurur ve envanterde gorunmez; (b) her yeni kullanici COACH_DAILY_USER_LIMIT tavanina ragmen paylasilan LLM saglayici kotasini tuketir (davetli gercek kullanicilar kocu kullanamaz hale gelir); (c) operatorun 'kimler betada' dedigi liste (BetaInvite) gercekle uyusmaz. Ayrica /api/meta kimliksiz olarak `davet_kodu_gerekli: true` beyan eder — urun, uygulamadigi bir kontrolu ilan etmis olur.

<details><summary>Kanıt</summary>

```
KOD: `invite_required()` / `davet_dogrula()` YALNIZCA register()'da cagriliyor. Grep ile dogrulandi:
  app/routers/auth.py:146: from app.beta_access import invite_required, davet_dogrula, davet_kullan
  app/routers/auth.py:148:     if invite_required():
  (app/ altinda BASKA cagri yeri YOK)
oauth_callback() satir 556-570 hicbir davet/kayit-modu kontrolu yapmadan `db.add(User(...))` ile yeni kullanici yaratip oturum aciyor.

CALISTIRILAN KANIT (scratchpad/proof_oauth_invite.py; REGISTRATION_MODE=invite_only, AUTH_ENABLED=true, saglayici cagrisi taklit edildi):
A) POST /api/auth/register (davet kodu YOK) -> 403 {'detail': 'Kayıt şu anda davetlilere açık. Geçerli bir davet kodu gerekli.'}
B) GET /api/auth/callback/google       -> 307 Location: .../auth/oauth-success?code=<oauth_exchange JWT>
C) DB'deki kullanicilar: [(1, 'yabanci@ornek.com', 'google')]
D) BetaInvite kayit sayisi: 0
Kosul: OAUTH_GOOGLE_/GITHUB_CLIENT_ID+SECRET tanimliysa gecerli (aksi halde 501 doner).
```
</details>

<details><summary>Çelişme turu hükmü</summary>

BULGU AYAKTA KALDI — diskten ve calistirilan kanittan dogrulandi.

1) KOD GERCEKTEN OYLE. app/routers/auth.py:520-585 `oauth_callback()`: provider kontrolu -> state/CSRF -> PKCE -> `exchange_code` -> `db.query(User)`; kullanici yoksa satir 556-569 dogrudan `db.add(User(..., is_active=True))` + `db.commit()`. Bu yolda `invite_required()` / `davet_dogrula()` / `registration_mode()` CAGRISI YOK.

2) BASKA KATMAN KAPATMIYOR (hepsi kontrol edildi):
- Grep (tum repo): `invite_required|davet_dogrula|davet_kullan` app/ altinda YALNIZ auth.py:146-149 ve 182'de (register icinde). Baska cagri yeri yok.
- Middleware: `app/main.py` yalnizca CORSMiddleware + `_GovdeBoyutuMiddleware` (govde boyutu) ekliyor — kayit kapisi yok.
- Dependency/constraint: OAuth callback'te hicbir guard dependency yok; User modelinde davet zorunlulugu yok.
- Allowlist/kota: repo genelinde OAUTH_ALLOWED_EMAILS / whitelist / MAX_USERS / global kayit tavani YOK (grep bos).
- app/beta_access.py tam okundu: OAuth icin hicbir kanca sunmuyor.
- Testler: tests/test_beta_invite_access.py YALNIZ /api/auth/register'i deniyor. Dahasi tests/auth/test_oauth.py::test_callback_yeni_kullanici_olusturur davetsiz yeni kullanici yaratilmasini ACIKCA DOGRULUYOR (suit bu fail-open davranisi kilitliyor, yakalamiyor).

3) CALISTIRILAN KANIT (scratchpad'de gecici test; hicbir proje dosyasi degistirilmedi. REGISTRATION_MODE=invite_only, AUTH_ENABLED=true, exchange_code stub):
A) POST /api/auth/register (kodsuz) -> 403 "Kayit su anda davetlilere acik..."
B) GET /api/auth/callback/google -> 307 .../auth/oauth-success?code=<JWT>
C) DB users: [(1, 'yabanci@ornek.com', 'google')]
D) BetaInvite sayisi: 0
Ozgun bulgunun otesine gecip zincirin sonunu da denedim:
E) POST /api/auth/oauth/exchange -> 200 ['access_token','refresh_token','token_type']
F) GET /api/auth/me -> 200 {'id':1,'email':'yabanci@ornek.com','is_active':True}
Yani sadece kullanici yaratilmiyor, TAM KULLANILABILIR OTURUM veriliyor — ayni e-posta /register'da 403 yerken.

4) BELGELENMIS KABUL-EDILEN RISK DEGIL. docs/kalite-seruveni/guvenlik-review-publish.md §4 uc riski sayiyor (kayit ucunda e-posta enumerasyonu, depolanmis metinle prompt injection, localStorage token'lari). OAuth'un davet kapisini atlamasi bu listede YOK.

SIDDET NEDEN "kritik" DEGIL "yuksek" (bulgunun cerceve duzeltmesi):
- Kosullu: .env.prod.example:39-45 OAuth'u OPSIYONEL isaretliyor ("kullaniliyorsa"). OAUTH_*_CLIENT_ID/SECRET tanimli degilse `exchange_code` patlar -> 400, aciklik gerceklesmez. Yine de frontend'de Google/GitHub giris butonu bagli (authApi.oauthLogin), yani urun bu yolu sunuyor.
- Capraz-kullanici veri sizintisi YOK: `ensure_personal_workspace` her yeni user'a kendi workspace'ini veriyor, scope_filter + Postgres RLS duruyor. Yeni kullanici mevcut verilere erisemiyor.
GERCEK ZARAR: (a) kontrolsuz/izlenemeyen kayit — BetaInvite listesi gercekle uyusmaz, KVKK'da veri sorumlusu yukumlulugu envanterde gorunmeyen kisiler icin dogar; (b) toplam LLM maliyeti sinirsiz olcekler (kullanici BASINA COACH_DAILY_USER_LIMIT var, GLOBAL tavan yok — grep ile dogrulandi); (c) /api/meta kimliksiz olarak `davet_kodu_gerekli: true` beyan ediyor (app/routers/meta.py:58-65) — urun uygulamadigi bir kontrolu ilan ediyor. BUG #199'un tum gerekcesi ("kapali beta bir iddia degil kontrol olsun") bu yolda fail-open.
</details>

### D06 · [yuksek] Kimliksiz canli sunucu uretebilen dagitim yolu: docs/deployment/README.md 'Yol 2' + .env.example -> ENVIRONMENT=development, AUTH_ENABLED bos; fail-fast tetiklenmez

- **Boyut:** kimlik-oturum · **Yer:** `docs/deployment/README.md:78` · **Durum:** ✅ **KAPANDI — BUG #227** (5 Ağu).
  Düzeltme dokümanla sınırlı tutulmadı (L8: belgelenen ≠ uygulanan) — **kök neden güvenlik
  varsayılanının fail-OPEN olmasıydı**: `auth_enabled()` tanımsız/boş değeri "kapalı" sayıyor,
  tek koruma da unutulması en kolay değişkene (`ENVIRONMENT=production`) bağlanıyordu.
  Yeni kural: tanımsız/boş/anlamsız değer → kimlik doğrulama **AÇIK**; kapatmak için açıkça
  `AUTH_ENABLED=false` (production'da o da fail-fast ile reddedilir). Ek katmanlar:
  `deploy/financialos.service` kendini `ENVIRONMENT=production` ilan eder (EnvironmentFile'dan
  SONRA — eskimiş bir `.env` ezemesin), deployment README her iki yolda `.env.prod.example`
  gösterir, `.env.example` yeni varsayılanı yazar, ADR-033 §5 "varsayılan kapalı" kararı
  DEĞİŞTİRİLDİ notuyla güncellendi. Kapı: `tests/security/test_kimliksiz_deploy_kapisi.py`
  (20 test — varsayılan/anlamsız değer/açık kapatma, prod fail-fast, **README'nin gösterdiği
  HER şablon gerçekten kimlikli sunucu üretiyor mu** [kapsam tabanı assert'li], systemd unit'i).
  Düzeltme öncesi 9'u kırmızıydı. Tam süit 1677 passed — davranış çevrilmesine rağmen kırmızı yok
  (test altyapısı artık gerçek bir yerel kurulumla aynı hareketi yapıyor: açıkça `AUTH_ENABLED=false`).
- **Neden yayın engeli / etki:** Repo bir self-host urunu olarak yayinlaniyor ve iki dagitim yolunu da resmi olarak belgeliyor (ADR-035 'systemd (alternatif)'). Yol-2'yi harfiyen izleyen biri (Murat dahil, Docker'siz VM tercih ederse) internete acik, kimlik dogrulamasi TAMAMEN KAPALI bir instance calistirir: /api/cockpit, /api/accounts, /api/transactions, GET /api/users/me/export (tum finansal veri JSON) ve DELETE /api/users/me baglantiyi bilen herkese acik olur. BUG #171 tam olarak bu senaryo icin acilmis ve guvenlik review'unda 'kapatildi' denmisti; koruma ise unutulmasi en kolay degiskene (ENVIRONMENT) bagli oldugu icin bu yolda hic devreye girmiyor.

<details><summary>Kanıt</summary>

```
docs/deployment/README.md:79 `sudo -u financialos cp .env.example .env    # düzenle (yukarıdaki gibi)` — 'yukaridaki' minimum liste (satir 39-46) SADECE DOMAIN/LLM_PROVIDER/GEMINI_API_KEY/SECRET_KEY/CORS_ORIGINS icerir; ENVIRONMENT veya AUTH_ENABLED YOK.
.env.example: satir 2 `ENVIRONMENT=development`, AUTH bolumu `AUTH_ENABLED=` (BOS).
deploy/financialos.service: `EnvironmentFile=/opt/financialos/.env` (compose'un `${ENVIRONMENT:-production}` varsayilani BU YOLDA YOK).
app/auth.py:29 `auth_enabled()` bos deger icin False; app/settings.py:69 `auth_problems()` yalniz `is_production()` iken uyarir; app/settings.py:100 `validate_security_config()` prod degilse sadece warning.

CALISTIRILAN KANIT (scratchpad/proof_misc.py):
3) fail-fast OK -> [FAIL-FAST] Güvenlik config sorunları: AUTH_ENABLED production'da açık olmalı ...      # ENVIRONMENT=production iken calisiyor
4) ENVIRONMENT bos + AUTH_ENABLED yok -> istisna YOK (is_production()=False, auth_enabled=False)          # tek degisken unutulunca koruma tamamen sessiz
Bu durumda app/dependencies.py:96 `_fallback_user(db)` devreye girer: token'siz her istek DB'deki ILK kullanici olarak servis edilir.
Not: aktif yayin yolu (docs/deployment/runbook.md + docker-compose.prod.yml:36 `ENVIRONMENT: production`) GUVENLI; risk bu eskimis ama SUPERSEDED isaretlenmemis dokumandan kaynaklaniyor.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

Bulgu diskten doğrulandı; çürütme denemesi başarısız oldu.

DOĞRULANAN ZİNCİR (dosya:satır, hepsi okundu):
1. C:\Users\18155\PycharmProjects\financialos\docs\deployment\README.md:64-87 "Yol 2 — Bare-metal (systemd)": satır 74 `sudo -u financialos cp .env.example .env  # düzenle (yukarıdaki gibi)`. "Yukarıdaki" minimum liste satır 38-44'te: DOMAIN / LLM_PROVIDER / GEMINI_API_KEY / SECRET_KEY / CORS_ORIGINS. ENVIRONMENT ve AUTH_ENABLED bu listede YOK (satır 137-138'deki tabloda "opsiyonel" ve "Compose default" olarak geçiyor — systemd yolunda compose yok).
2. C:\Users\18155\PycharmProjects\financialos\.env.example:2 `ENVIRONMENT=development`, satır 39 `AUTH_ENABLED=` (boş).
3. C:\Users\18155\PycharmProjects\financialos\deploy\financialos.service:12-13 yalnız `Environment=DATABASE_URL=...` + `EnvironmentFile=/opt/financialos/.env`. ENVIRONMENT/AUTH_ENABLED set edilmiyor (compose'daki `${ENVIRONMENT:-production}` / `${AUTH_ENABLED:-true}` bu yolda devrede değil).
4. app/settings.py:69 `auth_problems()` yalnız `is_production()` iken uyarı üretir; :100 `validate_security_config()` prod değilse sadece `logger.warning`. app/auth.py:29 `auth_enabled()` boş değeri False sayar. app/dependencies.py:93-96 auth kapalıyken token'sız istek `_fallback_user(db)` → DB'deki ilk kullanıcı.
5. Başka koruma katmanı YOK: app/main.py:81-121 lifespan yalnız `validate_security_config()` çağırıyor (ek auth/host guard yok), CORS dışında auth middleware yok, deploy/financialos.service reverse-proxy'de basic-auth önermiyor (README:85-86 yalnız Caddy/nginx proxy tarif ediyor).

ÇALIŞTIRILAN KANIT (salt-okur; scratchpad\proof_yol2b.py, in-memory SQLite, gerçek FastAPI app + TestClient):
ENVIRONMENT=development + AUTH_ENABLED="" (yani `cp .env.example .env` + README minimum listesi) ile:
- `environment() = development | is_production() = False`, `auth_enabled() = False`
- `validate_security_config() -> ISTISNA YOK` (log: "[security] config doğrulaması geçti (environment=development)") → uygulama açılır
- `GET /api/cockpit -> 200` (nakit_kasa 123456.78), `GET /api/accounts -> 200`, `GET /api/users/me/export -> 200` (password_hash dahil tam KVKK export'u), `DELETE /api/users/me -> 204` — hepsi Authorization header OLMADAN.
(İlk denemede 401 aldım; nedeni app/database.py:23 `load_dotenv()`'in yerel dev .env'indeki AUTH_ENABLED=true'yu yüklemesiydi — sunucudaki .env.example kopyası simüle edilince yukarıdaki sonuç çıktı. Yani 401, dev makinesinin .env'inden geliyordu, kodun korumasından değil.)

ÇÜRÜTME DENEMELERİ VE SONUÇLARI:
- "Doküman bayat/SUPERSEDED olabilir": README'de böyle bir işaret yok; docs/faq.md:32 hâlâ production yolu olarak bu dosyayı ve systemd'yi gösteriyor; ADR-035 Karar #1 systemd'yi resmi alternatif sayıyor.
- "Yol 1 (Docker) de aynı riski taşır mı / risk zaten kapalı mı": docker-compose.yml:16-17 `${ENVIRONMENT:-production}` / `${AUTH_ENABLED:-true}` ve docker-compose.prod.yml:36,43 `ENVIRONMENT: production` + `AUTH_ENABLED: "true"` → aktif/canlı yol GÜVENLİ. Risk yalnız Yol 2'de.
- "Belgelenmiş kabul-edilen risk mi": docs/kalite-seruveni/guvenlik-review-publish.md:18 BUG #171'i KAPATILDI olarak listeliyor ("Compose dışı bir deploy (systemd/manuel/PaaS) tüm API'yi kimliksiz açardı"); kabul-edilen-risk kaydı yok. Yani review'un kapandı iddiası, korumanın hiç set edilmeyen bir değişkene (ENVIRONMENT) bağlı olması nedeniyle systemd yolu için geçerli değil.
- "Başka katman kapatıyor mu (middleware/nginx/test/migration)": grep + main.py incelemesi ile hayır. Ek olarak aynı senaryoda `is_production()=False` olduğu için main.py:131 gereği /docs, /redoc, /openapi.json de açık kalır (SEC-015 sertleştirmesi de devre dışı).

ZARAR: Repo self-host ürünü olarak yayımlanıyor ve iki yolu da resmî belgeliyor. Yol 2'yi harfiyen izleyen operatör (Murat Docker'sız VM seçerse dahil) internete açık, kimlik doğrulaması tamamen kapalı bir instance koşar: tüm finansal veri (cockpit/hesaplar/işlemler), KVKK export'u ve `DELETE /api/users/me` bağlantıyı bilen herkese 
</details>

### D07 · [yuksek] Premortem ucu (POST /api/premortem/{id}) LLM kotasini tamamen atliyor — kota dolu kullanici sinirsiz LLM cagirtabiliyor

- **Boyut:** kota-maliyet · **Yer:** `app/routers/premortem.py:111` · **Durum:** ✅ **KAPANDI — BUG #228** (5 Ağu).
  Kota muhasebesi router'dan sökülüp `app/llm_quota.py`'ye alındı (uca değil **LLM kullanımına**
  bağlı). Premortem ucu önbellek dalından SONRA rezerve eder (cache LLM harcamaz → kullanıcı
  yapılmamış çağrı için cezalanmaz), çöken çağrı sayılır, tavan doluysa 429. Kapı:
  `tests/test_llm_kota_kapisi.py` (9 test; **statik kapı** dahil: `provider.chat`/`build_provider`
  çağıran her `app/` dosyası ya `llm_quota`'dan geçer ya gerekçeli `# kota-exempt` taşır —
  kapsam tabanı + bayat-muafiyet kontrolüyle, L11). Mutasyon kontrolü: rezervasyonlar
  kaldırılınca 4 test kırmızıya döndü.
- **Neden yayın engeli / etki:** PARA KAYBI + KULLANICI KAYBI. BUG #188/ADR-041'in tum amaci 'bir kullanici paylasilan API anahtarini/faturayi tek basina tuketemesin' idi; premortem ucu bu tavani sifirliyor. Kotasi dolmus (429 almis) bir kullanici bile /api/premortem'i dongude cagirarak sinirsiz LLM uretimi yaptirabiliyor (dogrulandi: 6/6 istek 200, hicbiri sayaca yazilmadi). Ucretsiz kademede paylasilan Gemini anahtari tukenir -> TUM beta kullanicilarinin kocu jenerik 'Koc cevap veremedi' hatasina duser; ucretli kademede dogrudan fatura riski. Ayrica ApiCallLog'a hic yazilmadigi icin scripts/beta_metrics.py maliyet/hata metrikleri bu trafigi HIC gormez — operator patlamayi olctuktan sonra bile nedenini bulamaz. docs/kalite-seruveni/guvenlik-review-publish.md 'Kabul edilen riskler' bolumunde bu YOK; ADR-041 dayatma noktasini yalnizca POST /api/coach/chat olarak tanimliyor ve bu ucu hic anmiyor.

<details><summary>Kanıt</summary>

```
KOMUT: venv/Scripts/python.exe -m pytest <scratchpad>/probe_quota_bypass.py -q -s
CIKTI:
  COACH-1: 200  COACH-2: 429            <- COACH_DAILY_USER_LIMIT=1, tavan dayatiliyor
  KOTA DOLU. ApiCallLog satir sayisi: 1
  PREMORTEM kodlari: [200, 200, 200, 200, 200]
  PREMORTEM LLM uretim cagrisi sayisi: 5
  PREMORTEM SONRASI ApiCallLog satir sayisi: 1
  >>> SONUC: kota DOLU iken 5 adet LLM uretimi yapildi; ApiCallLog degisimi: 0

KOMUT: venv/Scripts/python.exe -m pytest <scratchpad>/probe2.py -q -s   (TEK pending aksiyon, cache asiliyor mu)
CIKTI:
  TEK AKSIYON premortem kodlari: [200, 200, 200, 200, 200, 200]
  snapshot hash'leri: ['42ab9445','227e1290','ec74fcac','d1ce9dc2','ab731599','ff6c745a']
  >>> TEK aksiyon icin uretilen LLM premortem sayisi: 6
  >>> ApiCallLog satiri: 0
(BUG #137 cache'i cockpit_snapshot_hash'e bagli; kullanici kotasiz bir endpoint'le bakiyeyi
degistirince hash degisiyor -> ayni aksiyon icin sinirsiz yeni LLM uretimi)

KOD (app/routers/premortem.py:110-115) — hicbir kota/rezervasyon kontrolu yok:
    try:
        result = generate_premortem(
            action_id=action.id,
            action_context=action_context,
            cockpit_snapshot=snapshot,
        )

KOMUT: grep -c "ApiCallLog|coach_user_daily_limit|_kota_rezerve_et" app/routers/premortem.py app/premortem.py
CIKTI: her ikisi de 0

app/premortem.py:236-241 — her cagri IKI denemeye kadar provider.chat yapar:
    for attempt in range(2):
        response = provider.chat(system_prompt=_SYSTEM_PROMPT, messages=messages, tools=[])

Uc gercek kullanici yuzeyinde: frontend/src/api.js:412 premortemApi.run + PremortemModal.jsx:51 (buton).
Global rate-limit de yok: app/rate_limit.py:37-43 _DEFAULTS sadece login/register/pwreset/oauth/invite.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

CURUTULEMEDI — bulgu diskten ve calisma-aninda dogrulandi.

1) KOD (statik): app/routers/premortem.py tam okundu (138 satir). 110-115. satirda generate_premortem dogrudan cagriliyor; dosyada hicbir kota/rezervasyon/ApiCallLog/rate_limit izi yok. Dayatma tek noktada: _kota_rezerve_et app/routers/coach.py:267'de tanimli ve YALNIZCA app/routers/coach.py:457'de cagriliyor.

2) BASKA KATMAN YOK: app/main.py sadece CORSMiddleware (178) + _GovdeBoyutuMiddleware (197) ekliyor; premortem router'i 274. satirda dependencies= olmadan kaydediliyor. app/rate_limit.py _DEFAULTS yalnizca login/register/pwreset/oauth/invite; rate_limit() cagrilari sadece app/routers/auth.py icinde (7 yer). Proxy katmani da kapatmiyor: deploy/nginx.conf.template:51'deki limit_req YALNIZ "location /api/auth/" altinda; /api/premortem/'i servis eden genel "location /api/" blogunda (satir 60) limit_req YOK.

3) CALISTIRILAN KANIT — probe 1 (COACH_DAILY_USER_LIMIT=1, kota elle doldurulmus):
  COACH/CHAT (kota dolu iken) -> 429
  PREMORTEM HTTP kodlari      : [200, 200, 200, 200, 200]
  PREMORTEM provider.chat sayisi: 5
  ApiCallLog satir sayisi SONRA : 1  (degisim: 0)

4) CACHE SAVUNMASI COKTU — probe 2, hash MONKEYPATCH'SIZ, yalnizca gercek uclarla (PUT /api/accounts ile bakiye +1 TL, sonra POST /api/premortem), TEK bir pending aksiyon:
  PUT /api/accounts kodlari (kotasiz): [200, 200, 200, 200, 200, 200]
  PREMORTEM kodlari                  : [200, 200, 200, 200, 200, 200]
  (hash, cached): [('42ab9445454a32b1', False), ('900ce4f9a36deaf8', False), ('7edfeb9625cbf787', False), ('3819987612d8f891', False), ('29cf8544f82c2e41', False), ('1cbc6dc9c295c41f', False)]
  >>> GERCEK LLM cagrisi sayisi: 6   >>> ApiCallLog toplam: 1
Sebep: app/cockpit_snapshot.py:104 compute_snapshot_hash yalnizca snapshot_at'i disliyor; cash_tl/net_worth_tl hash'e dahil. Kotasiz CRUD ucu (app/routers/accounts.py:154 PUT) hash'i degistiriyor -> load_cached_premortem None donuyor -> her seferinde yeni LLM uretimi. Carpan: app/premortem.py:239 her istekte 2 denemeye kadar provider.chat yapiyor.

5) KABUL-EDILEN-RISK DEGIL: docs/kalite-seruveni/guvenlik-review-publish.md "4. KABUL EDILEN RISKLER" bolumu okundu — yalnizca e-posta enumerasyonu, depolanmis-metin prompt injection, localStorage token. Premortem/kota YOK. docs/architecture/adr-041-per-user-llm-quota.md:24 dayatma noktasini acikca "POST /api/coach/chat" olarak tanimliyor, bu ucu hic anmiyor. tests/ icinde COACH_DAILY_USER_LIMIT yalnizca test_coach_user_quota.py ve test_coach_eszamanlilik.py'de geciyor — premortem icin kota testi yok.

6) KULLANICI YUZEYI GERCEK: frontend/src/api.js:412 premortemApi.run -> frontend/src/components/PremortemModal.jsx:51 (buton). app/main.py:274 router kayitli.

NEDEN YAYIN ENGELI: ADR-041'in tek amaci "paylasilan API anahtarini/faturayi tek kullanici tuketemesin" idi; bu uc tavani sifirliyor. Kotasi dolmus (429 almis) kimliklenmis bir beta kullanicisi dongude sinirsiz LLM uretimi yaptirabiliyor. Ucretsiz kademede paylasilan anahtar tukenince TUM beta kullanicilarinin kocu duser (kullanici kaybi); ucretli kademede dogrudan fatura (para kaybi). Ayrica scripts/beta_metrics.py:72,123-129 tum maliyet/hata/gecikme metriklerini SADECE ApiCallLog'dan hesapliyor — bu trafik sayaca hic yazilmadigi icin operator patlamayi olctukten sonra bile nedenini goremez.

SIDDET NOTU: kritik degil cunku veri sizintisi/yetkisiz erisim yok ve saldirgan davetli-kimlikli bir kullanici olmali; ancak tek maliyet guard'ini tamamen etkisiz kildigi, tum beta kullanicilarini etkiledigi ve gozlemlenemez oldugu icin YUKSEK.
</details>

### D08 · [yuksek] Otomatik fiyat cron'u Account.balance'i guncellemiyor — Hesaplar paneli ile Cockpit ayni hesap icin FARKLI para gosteriyor

- **Boyut:** dayaniklilik · **Yer:** `app/price_providers/router.py:119` · **Durum:** ✅ **KAPANDI — BUG #229** (5 Ağu).
  `record_investment_price` artık `balance == lot_count × current_price` DEĞİŞMEZİNİ korur —
  diğer tüm yazma yolları (fund_tracker, accounts create/update, action_executor,
  simulation_engine) zaten koruyordu, tek ihlal eden cron yoluydu. `lot_count` None ise bakiyeye
  DOKUNULMAZ (hesaplanamaz; 0'a düşürmek veri kaybı olurdu), lot=0 ise bakiye 0 olur.
  Kapı: `tests/test_fiyat_cron_bakiye_senkron.py` (6 test — değişmez, **iki panelin aynı hesapta
  aynı TL'yi göstermesi** [kullanıcı-görünür sözleşme], lot bilinmiyor/0 uç durumları,
  PriceHistory+damga regresyonu, yatırım-dışı hesaba dokunmama). Ayrıca sapmayı yeşil teste gömen
  `test_stock_price_isyatirim_m_hisse.py` bakiye assert'iyle güçlendirildi.
- **Neden yayın engeli / etki:** Kullanici ayni uygulamada ayni yatirim hesabi icin iki farkli TL rakami gorur (Cockpit 36.000, Hesaplar 30.000) ve hangisinin dogru oldugunu bilemez. Bir finansal urunde birbiriyle celisen bakiye = para kaybi (yanlis rakama gore satis/harcama karari) + urune guvenin bir defada bitmesi. Fark her fiyat hareketiyle buyur; kullanici manuel fiyat girmedigi surece Hesaplar paneli kalici olarak donmus kalir.

<details><summary>Kanıt</summary>

```
Kod (router.py:119-121): `account.current_price = price` + `account.last_price_update = ...` yazilir, `account.balance` YAZILMAZ. Diger tum yazma yollari balance'i senkron tutar: fund_tracker.py:142 `account.balance = new_value` (manuel), routers/accounts.py:127 (create) ve routers/accounts.py:193 (update) `acc.balance = lot*current_price`. Ama cockpit lot*current_price kullanir (rules_engine.py:1983-1986), /api/accounts ise ham `acc.balance` doner (routers/accounts.py:108) ve Accounts.jsx:216+243 onu ekrana basar.

CALISTIRDIGIM KANIT (in-memory SQLite, gercek fonksiyonlar):
  a = Account(balance=30000, lot_count=6, current_price=5000)
  record_investment_price(db, a, Decimal('6000'), 'tefas')   # cron'un yaptigi cagri
  ->  cron sonrasi Account.balance (Hesaplar paneli bunu gosterir): 30000.0000
      cron sonrasi current_price: 6000.0000
      Cockpit yatirim_deger (lot*fiyat): 36000.0
      Cockpit hesap bakiyesi: [36000.0]
      FARK: 6000.0

Hicbir test bu senkronu dogrulamiyor: `grep -rn record_investment_price tests/` -> tests/test_price_providers.py yalniz PriceHistory + current_price'i kontrol ediyor (satir 35-59).
```
</details>

<details><summary>Çelişme turu hükmü</summary>

Diskten dogrulandi, curutulemedi. (1) Kod: app/price_providers/router.py:119-121 yalniz current_price + last_price_update yazip commit eder; account.balance'a hic dokunmaz. Cagiran cron: app/scheduler.py:301, is app/scheduler.py:348-353'te kosulsuz kayitli, SCHEDULER_ENABLED default 'true' (app/main.py:102). (2) Asimetri gercek: diger TUM yazma yollari balance == lot_count*current_price degismezini korur — fund_tracker.py:141, routers/accounts.py:125 ve :193, action_executor.py:865-870 (oradaki BUG #102 yorumu bu degismezi ACIKCA adlandirir), simulation_engine.py:240 ve :342. Tek ihlal eden cron yolu. (3) Okuma yollari: rules_engine.py:1982-1983 cockpit bakiyesini lot*fiyat hesaplar, routers/accounts.py:105-108 ham ORM balance doner, frontend/src/panels/Accounts.jsx:216+243 onu oldugu gibi basar. (4) Baska katmanda kapali DEGIL: models.py:209 duz Numeric(19,4) kolon; Account uzerinde event.listens_for / @validates / hybrid_property yok (app/ icindeki tek listens_for database.py PRAGMA/GUC icin). Migration/middleware/constraint karsiligi yok. (5) KOSTUM: in-memory SQLite + gercek record_investment_price + generate_cockpit -> ONCE balance=30000/price=5000, cron cagrisi sonrasi balance=30000/price=6000, cockpit accounts detay 36000.0, /api/accounts ham balance 30000.0 (fark 6000). (6) Bulgunun soylemedigi agirlastirici: Accounts.jsx:385 duzenleme formu balance'i HER ZAMAN gonderdigi icin routers/accounts.py:181 user_specified_balance=True olur ve :188-193 akilli yeniden-hesap DEVRE DISI kalir — yani duzenleme bayat degeri geri yazar; yalniz manuel fiyat akisi (/api/fund-price/update -> fund_tracker.py:141) iyilestirir. (7) Test kapsami yok: tests/test_price_providers.py:34-59 sadece PriceHistory + current_price dogrular; tests/test_stock_price_isyatirim_m_hisse.py:66-77 balance=0 iken cockpit 3295 iddia ederek sapmayi yesil teste gomer. guvenlik-review-publish.md'de kabul-edilen-risk olarak yazili degil. SIDDET 'yuksek', 'kritik' degil: para-etkili yollar dogru — NetWorthSnapshot cockpit'ten uretilir (routers/cockpit.py:52-64), goal_engine.py:50/90 ve debt_strategy.py:95 yalniz loan/card, cashflow.py:298 yalniz cash, satis executor'u lot*fiyattan hesaplayip balance'i kendi onarir. Yani veri sizintisi/sessiz para hareketi/hukuki risk yok; zarar ayni hesap icin iki celisen TL rakami (Cockpit 36.000 / Hesaplar 30.000 — ustelik ayni kartta 6 lot x 6.000 TL de yaziyor, Accounts.jsx:309-318) + kalici bayat DB kolonu = kullanici guveni ve yanlis rakama gore karar riski. Finansal urunde yayin engeli.
</details>

### D09 · [yuksek] Production yiginda OTOMATIK YEDEK YOK; depodaki tek yedek otomasyonu Postgres'te hata verip cikiyor

- **Boyut:** dayaniklilik · **Yer:** `docker-compose.prod.yml:7` · **Durum:** ✅ **KAPANDI — BUG #230** (5 Ağu, D13 ile aynı commit).
  Otomatik yedek servisi eklendi (yukarıda D13). Ayrıca **yanıltıcı systemd unit'i** düzeltildi:
  `deploy/financialos-backup.service` artık başlığında YALNIZ SQLite kurulumu için olduğunu ve
  Docker/Postgres yığınında kullanılmaması gerektiğini söylüyor — operatör "timer kurdum" sanıp
  her gece sessizce başarısız olmasın (teste bağlandı).
- **Neden yayın engeli / etki:** Kapali betada gercek kullanicilarin tum finansal verisi tek bir Docker volume'unde (pg-data) ve hicbir otomatik kopyasi yok. VM/volume kaybi, hatali migration veya yanlis `DROP DATABASE` (runbook geri-yukleme adimi bunu iceriyor) durumunda veri GERI DONULMEZ sekilde kaybolur — operator 'systemd timer'i kurdum' zannederken script her gece cikis kodu 1 ile oluyor, kimse gormuyor. Ayrica KVKK metni kullaniciya var olmayan bir yedek saklama/rotasyon politikasi taahhut ediyor: silme talebinden sonra 'yedeklerdeki kopyalar 30 gun icinde silinir' beyani uygulanmayan bir surece dayaniyor (hukuki risk).

<details><summary>Kanıt</summary>

```
1) Prod compose'da yedek servisi/cron yok: `grep -n "backup|pg_dump|cron" docker-compose.prod.yml` -> yalniz 2 YORUM satiri (6, 73), servis yok. Scheduler'da da yok: `grep -c backup app/scheduler.py` -> 0.
2) Depodaki tek yedek otomasyonu (docs/deployment/README.md:99'un kurmayi soyledigi systemd unit) SQLite-only script cagirir: deploy/financialos-backup.service:7 `ExecStart=.../python -m scripts.backup --keep-days 30`. Prod DATABASE_URL Postgres (docker-compose.prod.yml:46).
   CALISTIRDIM: `DATABASE_URL=postgresql://... python -m scripts.backup --keep-days 30`
   -> "backup.py yalnizca SQLite icindir; DATABASE_URL='postgresql://...'"  cikis kodu: 1
   (kaynak: scripts/backup.py:33-34)
3) Runbook yedeklemeyi yalniz ELLE komut olarak veriyor: docs/deployment/runbook.md:50-52 "# Postgres dump (cron ile gunluk ONERILIR)" — onerilir, kurulmaz.
4) scripts/deploy.sh migration'i yedeksiz calistirir: satir 27-28 `$COMPOSE up -d --build` -> docker-entrypoint.sh:21 `python -m alembic upgrade head`. deploy.sh'da tek bir pg_dump/backup adimi yok; rollback (satir 12-18) yalniz `git reset --hard` yapar, semayi/veriyi geri almaz.
5) Kullaniciya verilen hukuki metin yedegin VAR ve 30 gun donusumlu oldugunu soyluyor: docs/legal/kvkk-consent-v2.md:46-47 "yedeklerde kalan kopyalar, yedek saklama suresi (30 gun) doldugunda kendiliginden ortadan kalkar" ve :53 "yedeklerdeki kopyalar en gec 30 gun icinde silinir".
6) docs/kalite-seruveni/guvenlik-review-publish.md icinde yedek/backup gecmiyor (`grep -ni "yedek|backup"` -> 0 eslesme) -> belgelenmis kabul-edilen-risk DEGIL.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

Bulgu diskten dogrulandi, curutulemedi. (1) docker-compose.prod.yml tamami okundu: db/backend/scheduler/web/certbot - hicbiri yedek almiyor; backup|pg_dump|cron aramasi yalniz 2 YORUM satiri (6, 73) donduruyor. (2) app/scheduler.py:348-382'de 5 cron job var (fiyat 02:45, nightly_batch 03:00, k2 03:30, trace_cleanup 04:00, weekly_smoke pzt 05:00) - yedek job'i YOK (grep -c backup -> 0). (3) Depodaki tek yedek otomasyonu birimi deploy/financialos-backup.service:7, SQLite-only scripts/backup.py'yi cagiriyor; KOMUTU CALISTIRDIM: DATABASE_URL=postgresql://... venv/Scripts/python.exe -m scripts.backup --keep-days 30 -> "backup.py yalnizca SQLite icindir" EXIT=1 (kaynak scripts/backup.py:33-34). Prod DATABASE_URL Postgres (docker-compose.prod.yml:46,77). (4) scripts/deploy.sh:27-28 yedeksiz build+up (entrypoint alembic upgrade head); rollback() 12-18 yalniz git reset --hard - semayi/veriyi geri almiyor. Tum depoda pg_dump YALNIZ dokuman (runbook.md:52,73,176) ve 1 testte geciyor; hicbir .yml/.sh/.service/.timer/Dockerfile/nginx dosyasinda yok (genis grep ile dogrulandi). (5) runbook.md:51 "cron ile gunluk ONERILIR" - kuran adim yok; geri-yukleme akisi gercekten runbook.md:77 DROP DATABASE financialos WITH (FORCE) iceriyor. (6) KVKK metni kullaniciya CANLI servis ediliyor (app/routers/legal.py:26-27 -> kvkk-consent-v2.md) ve :46-47 + :53 var olmayan 30-gunluk yedek saklama/rotasyon politikasi taahhut ediyor -> uygulanmayan hukuki beyan. (7) docs/kalite-seruveni/guvenlik-review-publish.md icinde yedek/backup -> 0 eslesme; belgelenmis kabul-edilen-risk DEGIL. Baska katmanda kapali degil: tests/test_postgres_restore_drill.py geri-yuklemenin CALISTIGINI kanitliyor ama yalnizca bir dump VARSA; dump'i uretecek otomasyon yok. scripts/live_gate.py'de "yedek" yalniz docstring'de gecen masterprompt alintisi, gate implementasyonu degil (kosla() icinde yedek kapisi yok). DUZELTME (bulgunun zayif noktasi, curutmeye yetmiyor): docs/deployment/README.md:98-100'deki systemd timer, o dosyanin "Yol 2 - Bare-metal (systemd, Docker'siz) / SQLite" bolumunun altinda; prod-Postgres runbook'u bu birimi kurmayi hic soylemiyor. Yani "operator timer kurdum sanir, her gece exit 1" senaryosu garanti degil, yanlis-uygulama senaryosu. Asil iddia (prod yiginda otomatik yedek YOK + depodaki tek yedek birimi Postgres'te calismaz + KVKK'da karsiligi olmayan taahhut) aynen ayakta. SIDDET=yuksek (kritik degil): surekli bir sizinti/para kaybi yok, zarar bir tetikleyici olay gerektiriyor (volume kaybi, hatali migration, runbook'un kendi DROP DATABASE adimi) - ama gerceklestiginde tum beta kullanicilarinin finansal verisi GERI DONULMEZ sekilde kaybolur ve kullaniciya servis edilen KVKK metni var olmayan bir yedek politikasi beyan eder (hukuki risk). Kapali beta acilmadan kapatilmasi gereken bir yayin engeli.
</details>

### D10 · [yuksek] Yayınlanan KVKK/veri-işleyen beyanı yalan: ham işlem listesi + açıklama metinleri + üçüncü kişi adları yurt dışındaki LLM'e gidiyor

- **Boyut:** hukuki-gizlilik · **Yer:** `docs/legal/veri-isleyen-envanteri.md:17` · **Durum:** ✅ **KAPANDI — BUG #231** (5 Ağu).
  Beyan gerçeğe uyduruldu: envanterde "koça her mesajda GÖNDERİLEN veri (tam liste)" bölümü
  (hesap adları, **ham işlem listesi + serbest metin açıklamalar**, **üçüncü kişi adları**,
  kategori kırılımları, kırmızı çizgiler, sohbet geçmişi) + **özel nitelikli veri uyarısı**
  (KVKK m.6) + üçüncü kişi uyarısı + gerçekten gönderilmeyenler. Kapsam maddi olarak
  değiştiği için **rıza sürümü v3'e çıkarıldı** (`kvkk-consent-v3.md`) ve
  `/api/legal/kvkk` artık dosyayı **tek kaynaktan türetiyor** (router'da sabit
  "kvkk-consent-v2.md" yazılıydı → sürüm yükselse bile kullanıcı ESKİ metni okuyacaktı).
  "Sürümü yükseltip susmak" L8 tuzağı olacağı için **rıza tazeleme yolu** eklendi
  (`GET/POST /api/users/me/kvkk-consent`) ve Koç panelinde bant olarak gösteriliyor; ayrıca
  aktarımın kapsamı **aktarımın yapıldığı yerde** (mesaj kutusunun altında) yazıyor.
  Kapı: `tests/test_kvkk_beyan_gercek_akis.py` (14 test) — işaretli bir kullanıcıyla gerçek
  bağlam üretilip **giden her veri sınıfının beyanda yazılı olduğu** doğrulanıyor; koç
  bağlamına yeni alan eklenip beyan güncellenmezse kapı KIRILIR. Ters yön de korunuyor
  (şifre hash'i / e-posta gerçekten gitmiyor).
- **Neden yayın engeli / etki:** İşlem açıklaması kullanıcının serbest metnidir ve pratikte özel nitelikli kişisel veri taşır (sağlık: 'psikiyatri kontrol', inanç: 'cemaat bağışı', sendika/siyasi aidat). KVKK m.6 özel nitelikli veri ve m.9 yurt dışına aktarım için AYRI ve BİLGİLENDİRİLMİŞ açık rıza şart; kullanıcıya 'ham işlem listesi gönderilmez' denerek alınan rıza geçersiz, beyan yanlış olduğu için idari para cezası ve tazminat riski doğar. Ayrıca alacak/borç kaydındaki üçüncü kişinin adı-tutarı, o kişinin hiçbir rızası olmadan ABD'deki sağlayıcıya aktarılıyor — veri sahibi uygulamanın kullanıcısı bile değil.

<details><summary>Kanıt</summary>

```
BEYAN (docs/legal/veri-isleyen-envanteri.md:17-18, /api/legal/veri-isleyenler ile kullanıcıya SUNULUYOR):
  "**Gönderilmeyenler:** şifre/hash, oturum token'ı, e-posta adresi, ham işlem listesi
   (yalnız türetilmiş toplamlar ve kullanıcının kendi yazdığı metin gider)."
KVKK metni v2 §4 de aktarımı "cockpit özeti: bakiyeler, borç/gelir toplamları, kırmızı çizgi metinleriniz ve yazdığınız mesaj" ile sınırlı beyan ediyor.

GERÇEK — KOMUT: app.coach._build_context_message() bir kullanıcı için canlı çağrıldı (in-memory DB), LLM'e giden metnin sonu:
```
## Hesaplar
  - id=1 [cash] Garanti Vadesiz 1234: 15.000,00 TL

## Yaklaşan Tahsilatlar
  - 8 Ağustos 2026 Cumartesi: Ahmet Yilmaz → 5.000,00 TL (dugun borcu) ← 3 gün sonra

## YAKLAŞAN VADELER (0-7 gün)
  - 3 gün sonra: Ahmet Yilmaz alacağı +5.000,00 TL (receivable)

## SON İŞLEMLER (en yeni ilk)
  - 2026-08-05: -2.500,00 TL (saglik) — Psikiyatri kontrol - Dr. Ayse Kaya
```
Kod: app/coach.py:1105-1115 (`## SON İŞLEMLER` bloğu, `t['aciklama']` doğrudan basılıyor), :880-891 (hesap adları), :911-914 (`receivables_text` — `r['kim']` = üçüncü kişinin adı), :1044-1046 (`## Davranış Kalıpları` kategori kırılımı). Bu metin `system_prompt = f"{V3_GOD_MODE_PROMPT}\n\n{context_text}"` (app/coach.py:2464) ile sağlayıcıya gönderiliyor.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

CURUTULEMEDI — diskten ve canli calistirma ile dogrulandi.

1) BEYAN (yayinlanan, riza-kapisi): docs/legal/veri-isleyen-envanteri.md:17-18 "Gonderilmeyenler: ... ham islem listesi (yalniz turetilmis toplamlar ve kullanicinin kendi yazdigi metin gider)". docs/legal/kvkk-consent-v2.md:34-37 aktarimi "cockpit ozeti: bakiyeler, borc/gelir toplamlari, kirmizi cizgi metinleriniz ve yazdiginiz mesaj" ile sinirliyor — islemler, karsi-taraf adlari, hesap adlari bu listede YOK. Her iki belge kullaniciya SUNULUYOR: app/routers/legal.py:25-30 (slug->dosya) + frontend/src/panels/Login.jsx:58,153 (KVKK onayi kayit icin ZORUNLU, link /api/legal/kvkk).

2) KOD: app/rules_engine.py:1061-1082 _collect_recent_transactions -> {"aciklama": t.description}; :2270 cockpit["son_islemler"]. app/rules_engine.py:561-588 _collect_upcoming_receivables -> {"kim": d.counterparty}. app/coach.py:1104-1115 t['aciklama'] dogrudan basiliyor ("## SON ISLEMLER"), :911-914 r['kim'], :880-891 hesap adlari. app/coach.py:2463-2464 system_prompt = V3_GOD_MODE_PROMPT + context_text -> saglayiciya gidiyor. Varsayilan saglayici yurt disi: app/coach.py:2065 os.getenv("LLM_PROVIDER","gemini").

3) CANLI KOMUT (in-memory SQLite, hicbir repo dosyasi degistirilmedi; scratchpad/leak_check.py): _build_context_message ciktisinda birebir "## SON ISLEMLER ... - 2026-08-05: -2.500,00 TL (saglik) — Psikiyatri kontrol - Dr. Ayse Kaya", "## Yaklasan Tahsilatlar - ... Ahmet Yilmaz -> 5.000,00 TL (dugun borcu)", "## Hesaplar - id=1 [cash] Garanti Vadesiz 1234". Assertion sonuclari: aciklama=True, 3.kisi adi=True, hesap adi=True.

4) BASKA KATMAN KAPATMIYOR: grep -rniE "anonim|maskele|redact|scrub|pii|sanitize" app/ yalniz app/error_tracking.py (hata-log maskeleme) ve alakasiz string'lere dusuyor; koc baglaminda redaksiyon/middleware/settings kapisi YOK.

5) KABUL-EDILEN-RISK DEGIL: docs/kalite-seruveni/guvenlik-review-publish.md icinde islem aciklamasi / LLM baglam kapsami hakkinda kayit yok (yalniz #180 log-PII, #181 rate-limit ve workspace izolasyon satiri).

6) BELGENIN KENDI "dogrulama" iddiasi da bos cikti: tests/test_legal_docs.py yalniz okunabilirlik, path-traversal, saglayici listesi ve riza-surumu esitligini test ediyor (test_envanter_koddaki_llm_saglayicilarini_listeler, test_riza_surumu_yayinlanan_metinle_ayni) — "Gonderilmeyenler" cumlesini kilitleyen test YOK.

EN GUCLU KARSI-ARGUMAN VE NEDEN YETMEDI: "kullanicinin kendi yazdigi metin gider" ifadesi islem aciklamasini kapsiyor sayilabilir; ancak (a) karsi-taraf adi (counterparty) ve hesap adi ne turetilmis toplam ne de kullanicinin yazdigi mesajdir, (b) son-8 satir literal olarak "## SON ISLEMLER" basligi altinda ham islem listesidir ve bu "ham islem listesi gonderilmez" cumlesiyle dogrudan celisir, (c) KVKK v2 §4'un sayimi islemleri hic icermez.

SIDDET NEDEN "yuksek", "kritik" DEGIL: yurt disi aktarimin KENDISI beyan edilmis (saglayici tablosu, kocu kullanmama hakki, yerel Ollama secenegi) — gizli sizdirma degil, riza-kapisinda kapsami eksik/yanlis beyan. Yine de barindirilan betada veri sorumlusu operatordur ve yanlis kapsamla alinan riza KVKK m.9 (yurt disi aktarim) ve serbest-metin aciklamalarin tasidigi ozel nitelikli veri icin m.6 acisindan sakattir; ayrica alacak kaydindaki ucuncu kisinin adi-tutari, o kisi kullanici bile degilken yurt disi saglayiciya gidiyor. Idari para cezasi + tazminat riski dogurdugu icin yayin engeli.
</details>

### D11 · [yuksek] docker-compose.prod.yml'de env_file YOK — .env.prod'daki zorunlu degiskenler konteynere hic ulasmiyor, prod backend fail-fast ile hic acilmiyor

- **Boyut:** operasyon-deploy · **Yer:** `docker-compose.prod.yml:34` · **Durum:** ✅ **KAPANDI — BUG #230** (5 Ağu).
  `backend` ve `scheduler` servislerine `env_file: [.env.prod]` eklendi — `--env-file` yalnız
  `${...}` interpolasyonunu besliyordu, konteyner ortamına değişken yazmıyordu. `environment`
  bloğu env_file'ı ezdiği için hesaplanmış/sabit değerler otoriter kalır. Böylece `SUPPORT_EMAIL`,
  `SMTP_*`, `OAUTH_*`, `REGISTRATION_MODE`, `MAX_REQUEST_BODY_BYTES` gerçekten uygulamaya ulaşır.
- **Neden yayın engeli / etki:** Belgelenen tek deploy komutu ile beta HIC ayaga kalkmaz: backend konteyneri startup'ta RuntimeError verip restart dongusune girer, deploy.sh'in 60 saniyelik healthcheck'i gecmez ve otomatik rollback bir onceki (ayni sekilde bozuk) surume doner. Operatorun elinde 'neden acilmiyor' sorusunun cevabi yok, cunku .env.prod'a dogru degeri yazmis olmasina ragmen uygulama o degeri hic gormuyor. Ayrica ayni kok neden yuzunden REGISTRATION_MODE (kapali beta anahtari) ve MAX_REQUEST_BODY_BYTES operator tarafindan fiilen ayarlanamaz — operator .env.prod'da 'invite_only' yazdigini sanip aslinda yalnizca kod varsayilanina guveniyor.

<details><summary>Kanıt</summary>

```
KOMUT: venv/Scripts/python.exe -c "yaml.safe_load(open('docker-compose.prod.yml'))" ile servis basina env_file + environment anahtarlari listelendi.
CIKTI:
  db       | env_file: None | environment: ['POSTGRES_DB','POSTGRES_PASSWORD','POSTGRES_USER']
  backend  | env_file: None | environment: ['AUTH_ENABLED','BUILD_COMMIT','CORS_ORIGINS','DATABASE_URL','DB_MAX_OVERFLOW','DB_POOL_SIZE','ENVIRONMENT','GEMINI_API_KEY','GROQ_API_KEY','LLM_PROVIDER','OPENROUTER_API_KEY','SECRET_KEY','SERVICE_MODE','TRUST_PROXY_HEADERS','TZ','WEB_CONCURRENCY']
  scheduler| env_file: None | environment: ['DATABASE_URL','ENVIRONMENT','GEMINI_API_KEY','LLM_PROVIDER','SECRET_KEY','SERVICE_MODE','TZ']
  ORNEKTE VAR, HICBIR SERVISIN environment BLOGUNDA YOK: COACH_DAILY_USER_LIMIT, REGISTRATION_MODE, SUPPORT_EMAIL, MAX_REQUEST_BODY_BYTES

docs/deployment/runbook.md:31 tek deploy yolunu tarif ediyor: `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build`. `--env-file` YALNIZ compose dosyasindaki ${...} interpolasyonunu besler; env_file: olmadigi icin bu degiskenler konteyner ortamina yazilmaz.

KOMUT (ayni davranisi kod tarafinda dogruladim): ENVIRONMENT=production, SECRET_KEY=50 karakter, AUTH_ENABLED=true, SUPPORT_EMAIL YOK iken app.settings.validate_security_config()
CIKTI: RuntimeError: [FAIL-FAST] Guvenlik config sorunlari: SUPPORT_EMAIL tanimli olmali (giris yapamayan kullanicinin tek kanali). Production'da uygulama baslatilamaz.

app/main.py:81-85 lifespan ilk isi olarak validate_security_config() cagiriyor -> uvicorn/gunicorn startup'ta duser.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

Bulgu diskten dogrulandi, curutulemedi. (1) docker-compose.prod.yml YAML parse edildi: 5 servisin hicbirinde env_file: yok (db/backend/scheduler/web/certbot -> env_file=None); repo genelinde tek bir env_file: anahtari yok, yalniz --env-file kullanimi var (compose:3, docs/deployment/runbook.md:31 ve :187, scripts/deploy.sh:9) ve --env-file sadece ${...} interpolasyonunu besler. (2) .env.prod.example:64 SUPPORT_EMAIL'i "ZORUNLU (BUG #210): tanimsizsa uygulama BASLAMAZ" diye tarif ediyor, ama backend environment blogunda (docker-compose.prod.yml:34-58) bu anahtar yok. (3) app/settings.py:82-89 support_problems() production'da bos SUPPORT_EMAIL icin sorun uretir, validate_security_config() (satir 100-105) production'da RuntimeError firlatir; app/main.py lifespan'inin ILK isi bu cagridir. (4) Konteynerin gercek env'ini birebir kurup (yalniz compose'daki 16 anahtar) calistirdim: RuntimeError: [FAIL-FAST] Guvenlik config sorunlari: SUPPORT_EMAIL tanimli olmali... Production'da uygulama baslatilamaz. (5) Alternatif besleme yolu YOK: load_dotenv() yalniz app/database.py:23'te ve cwd /app; Dockerfile hicbir .env dosyasi kopyalamiyor (COPY: app, alembic, alembic.ini, scripts, docs/legal, docker-entrypoint.sh), .dockerignore .env'i haric tutuyor; docker-entrypoint.sh hicbir dosya source etmiyor (yalniz SCHEDULER_ENABLED export); scripts/deploy.sh shell'e export yapmiyor. (6) docs/kalite-seruveni/guvenlik-review-publish.md icinde SUPPORT_EMAIL/env_file/REGISTRATION_MODE gecmiyor -> belgelenmis kabul-edilen-risk degil. DUZELTME (bulgunun abartili kismi): REGISTRATION_MODE, MAX_REQUEST_BODY_BYTES ve COACH_DAILY_USER_LIMIT icin kod varsayilanlari ornekle ayni ve guvenli tarafta (app/beta_access.py:26-31 production varsayilani invite_only fail-closed; app/request_limits.py:53 varsayilan 1 MiB; app/routers/coach.py:231 varsayilan 80) -> "operator invite_only sandi ama acik kaldi" zarari GERCEK DEGIL; tek gercek sapma operatorun bilincli REGISTRATION_MODE=open yazmasinin sessizce yok sayilmasi. EKLENTI (bulgunun kacirdigi, zarari buyuten kisim): .env.prod.example:37-45'te tarif edilen SMTP_* ve OAUTH_* degiskenleri de hicbir servisin environment blogunda yok; app/services/email.py:26-31 ve app/services/oauth.py:64 bunlari os.getenv ile okuyor -> operator SUPPORT_EMAIL'i elle ekleyip uygulamayi acsa bile davet/sifre-sifirlama e-postasi ve OAuth SESSIZCE yapilandirilmamis kalir (kapali betada davet gonderilemez, sifre sifirlama olu). Zarar: belgelenen tek deploy komutu ile backend startup'ta RuntimeError verir, deploy.sh:12-18 otomatik rollback'i ayni derecede bozuk onceki commit'e doner (30x2s healthcheck asilir).
</details>

### D12 · [yuksek] scheduler servisinde AUTH_ENABLED tanimli degil — production fail-fast'i tetikler, cron servisi hic calismaz (fiyatlar bayat kalir)

- **Boyut:** operasyon-deploy · **Yer:** `docker-compose.prod.yml:70` · **Durum:** ✅ **KAPANDI — BUG #230** (5 Ağu).
  `scheduler`'a `AUTH_ENABLED: "true"` eklendi + backend↔scheduler kritik ortam paritesi teste
  bağlandı. Ayrıca **sessiz arıza kapatıldı:** `scripts/deploy.sh` scheduler ayakta değilse
  artık UYARI basıp geçmiyor, **rollback** ediyor; `restarting` (crash-loop) durumu da yakalanıyor
  (eski `Up|running` grep'i onu kaçırıyordu).
- **Neden yayın engeli / etki:** Scheduler servisi hic ayaga kalkmaz: 02:45 fiyat cron'u ve 03:00 gece batch'i calismaz. Kullanici panelde BAYAT fon/hisse/kur fiyatlariyla hesaplanmis net deger gorur ve buna gore borc odeme/yatirim karari verir — yanlis sayiya dayali para karari. Ustelik hata sessizdir: web servisi calisiyor gorunur, deploy.sh sadece 'UYARI: scheduler servisi calismiyor' basip cikis kodu 0 ile TAMAM der (scripts/deploy.sh son adim).

<details><summary>Kanıt</summary>

```
docker-compose.prod.yml:70-79 scheduler environment blogu: SERVICE_MODE, ENVIRONMENT: production, TZ, SECRET_KEY, DATABASE_URL, LLM_PROVIDER, GEMINI_API_KEY. AUTH_ENABLED YOK (backend'de satir 43'te var, scheduler'da unutulmus).

app/auth.py:27-29:
    def auth_enabled() -> bool:
        return os.getenv("AUTH_ENABLED", "").strip().lower() in ("1", "true", "yes")   # varsayilan False

KOMUT: ENVIRONMENT=production, SECRET_KEY dolu, SUPPORT_EMAIL dolu, AUTH_ENABLED YOK iken validate_security_config()
CIKTI: RuntimeError: [FAIL-FAST] Guvenlik config sorunlari: AUTH_ENABLED production'da acik olmali (aksi halde API kimliksiz erisime acilir).

docker-entrypoint.sh scheduler modunda `uvicorn app.main:app` calistiriyor -> ayni lifespan -> ayni RuntimeError. restart: unless-stopped ile sonsuz crash-loop.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

Diskten tam doğrulandı, çürütülemedi. (1) docker-compose.prod.yml:70-79 scheduler environment bloğu = [DATABASE_URL, ENVIRONMENT, GEMINI_API_KEY, LLM_PROVIDER, SECRET_KEY, SERVICE_MODE, TZ] — AUTH_ENABLED YOK, ama ENVIRONMENT: production VAR (backend satır 43'te AUTH_ENABLED: "true" açıkça listeli). Testin kendi parser'ıyla (tests/test_deploy_timezone.py:_servis_bloklari) çıkardım. (2) Hiçbir compose dosyasında env_file: yok, Dockerfile'da ENV AUTH_ENABLED yok → .env.prod'daki AUTH_ENABLED=true yalnız YAML interpolasyonu; konteynere geçmez (backend'in değişkeni açıkça listelemesi de bunu kanıtlıyor). (3) app/settings.py:60-71 auth_problems() + 92-105 validate_security_config() production'da RuntimeError atar. (4) app/main.py:81-85 lifespan bunu SERVICE_MODE'dan bağımsız KOŞULSUZ çağırır. (5) docker-entrypoint.sh:11-16 scheduler modu 'exec uvicorn app.main:app' → aynı lifespan; restart: unless-stopped → crash-loop. (6) ÇALIŞTIRDIĞIM KOMUT (ENVIRONMENT=production, geçerli SECRET_KEY, SUPPORT_EMAIL dolu, AUTH_ENABLED silinmiş) → 'RuntimeError: [FAIL-FAST] Güvenlik config sorunları: AUTH_ENABLED production'da açık olmalı...'. (7) scripts/deploy.sh:38-39 sadece 'UYARI: scheduler servisi çalışmıyor' basıp devam eder, satır 41 '✅ TAMAM' + çıkış 0 ('restarting' durumu 'Up|running' grep'iyle eşleşmez). (8) Kapatan başka katman yok: test_deploy_timezone.py yalnız TZ parity'sine bakıyor, env parity testi yok; guvenlik-review-publish.md'de kabul-edilen-risk olarak yazılı değil (oradaki #171 farklı konu). Etkilenen cron'lar app/scheduler.py:348-378 — 02:45 fiyat, 03:00 gece batch, 03:30 K2, 04:00, Pzt 05:00 smoke: hiçbiri koşmaz. AŞIRI-İDDİA DÜZELTMELERİ (severity'yi kritikten düşürüyor, bulguyu geçersiz kılmıyor): (a) bayatlık kullanıcıya TAMAMEN görünmez değil — app/routers/cockpit.py:92-107 price_freshness/stale_count rozetleri + app/fund_tracker.py:37 is_price_stale + SchedulerRun tablosu (app/models.py:976) var; (b) aynı compose SUPPORT_EMAIL'i hiçbir servise geçirmiyor ve settings.support_problems() onu da production'da zorunlu kılıyor → ilk deploy'da backend de patlar ve deploy.sh healthcheck'inde GÜRÜLTÜLÜ rollback olur; 'sessiz exit 0' senaryosu ancak operatör SUPPORT_EMAIL'i düzelttikten sonra gerçekleşir, o noktada scheduler sessizce ölü kalır. Zarar: canlı deploy'da fiyat/kur tazeleme ve gece batch'i hiç çalışmaz, kullanıcı eski fiyatlarla hesaplanmış net değere göre para kararı verir. Veri sızıntısı/auth bypass'ı YOK (fail-closed yön) — bu yüzden kritik değil, yüksek.
</details>

### D13 · [yuksek] Production'da OTOMATIK YEDEK yok: compose'ta yedek servisi, scheduler'da yedek isi yok; mevcut systemd unit'i SQLite-only script cagiriyor

- **Boyut:** operasyon-deploy · **Yer:** `docker-compose.prod.yml:109` · **Durum:** ✅ **KAPANDI — BUG #230** (5 Ağu).
  Compose'a `backup` servisi eklendi: 24 saatte bir `deploy/pg_backup.sh` → `pg_dump | gzip` →
  **doğrulama** (asgari boyut + `gzip -t` bütünlüğü; geçmeyen dump SİLİNİR — yarım dosya
  "yedeğim var" yanılsaması üretmesin) → adlandırılmış `pg-backups` hacmi (konteyner katmanı
  DEĞİL, `down` ile yok olmaz) → `BACKUP_KEEP_DAYS` rotasyonu. Geçici dosyaya yazıp doğrulandıktan
  SONRA adlandırma (yarım dosya asla geçerli görünmez). Runbook'a listeleme/elle koşma/**dışarı
  kopyalama** adımları eklendi (tek VM = tek nokta; otomatik yedek volume kaybına karşı korumaz).
- **Neden yayın engeli / etki:** Beta kullanicilarinin butun finansal gecmisi (hesaplar, islemler, borclar, hedefler, kocluk hafizasi) tek bir Docker volume'unde ve tek bir Free-Tier VM'de duruyor; hicbir otomatik kopya yok. VM'in silinmesi, volume bozulmasi veya hatali bir `docker compose down -v` tum kullanici verisini kalici olarak yok eder. Operator elle pg_dump almayi bir gun unutursa kayip kaciniIMAZ hale gelir; KVKK acisindan da veri sorumlusunun butunluk/erisilebilirlik yukumlulugunu karsilamaz.

<details><summary>Kanıt</summary>

```
1) docker-compose.prod.yml servisleri: db, backend, scheduler, web, certbot. Yedek servisi/cron YOK (yaml parse ciktisi yukaridaki bulguda).
2) KOMUT: grep -rn 'backup|yedek' app/scheduler.py -> CIKTI: hicbir eslesme (add_job satirlari 348/355/362/369/376, hicbiri yedek degil).
3) deploy/financialos-backup.service: `ExecStart=/opt/financialos/venv/bin/python -m scripts.backup --keep-days 30` — ama scripts/backup.py:33-35:
     if not url.startswith("sqlite:///"):
         raise SystemExit(f"backup.py yalnizca SQLite icindir; DATABASE_URL={url!r}")
   Prod DATABASE_URL postgresql:// oldugu icin bu unit her calistiginda hata verip cikar.
4) docs/deployment/runbook.md:50-52 tek yedek yolu ELLE bir komut: `... exec -T db pg_dump ... > backup-$(date +%F).sql` ve yaninda yalnizca '(cron ile gunluk onerilir)' yaziyor — onerilen cron hicbir yerde kurulmuyor.
5) docs/kalite-seruveni/guvenlik-review-publish.md 'KABUL EDILEN RISKLER' bolumunde yedekleme YOK (yani belgelenmis kabul-edilen-risk degil).
```
</details>

<details><summary>Çelişme turu hükmü</summary>

Bulgu diskten TAM dogrulandi; curutulemedi.

1) docker-compose.prod.yml (113 satir, tamami okundu): servisler yalnizca db, backend, scheduler, web, certbot. Yedek servisi/ops sidecar/cron konteyneri YOK. Veri tek bir `pg-data` named volume'unda.

2) app/scheduler.py:348-382 -> 5 add_job: fetch_investment_prices (02:45), nightly_batch (03:00), k2_batch (03:30), nightly_trace_cleanup (04:00), weekly_smoke_test (pzt 05:00). Yedek isi yok. app/ genelinde backup|yedek|pg_dump grep'i yalnizca json.dumps, logging backupCount ve alakasiz Turkce "yedek" metinleri donuyor.

3) deploy/financialos-backup.service:7 -> `python -m scripts.backup`; scripts/backup.py:33-34 SQLite disi URL'yi reddediyor. KOMUT CALISTIRILDI: DATABASE_URL=postgresql://... ile `python -m scripts.backup --keep-days 30` -> "backup.py yalnizca SQLite icindir" + EXITCODE=1. Dahasi: bu unit bare-metal SQLite yoluna ait (docs/deployment/README.md:99-100); Docker/Postgres prod runbook'unda (docs/deployment/runbook.md) hic systemctl/crontab satiri YOK — yani prod yolunda timer kurulmuyor bile.

4) Repo geneli (venv haric) crontab|systemctl enable|OnCalendar|pg_dump aramasi: sadece SQLite timer'i, iki deployment dokumani, milestone-log ve tests/test_postgres_restore_drill.py. Otomatik Postgres dump'i HICBIR YERDE yok. runbook.md:49-52 tek yol elle pg_dump, yaninda sadece "(cron ile gunluk onerilir)" yaziyor.

5) docs/kalite-seruveni/guvenlik-review-publish.md §4 KABUL EDILEN RISKLER: 3 madde (e-posta enumerasyonu, depolanmis metinle prompt injection, localStorage token). Yedekleme YOK -> belgelenmis kabul-edilen-risk degil.

AGIRLASTIRICI (bulguda yoktu, ben buldum):
- scripts/deploy.sh: entrypoint `alembic upgrade head` kosuyor, basarisizlikta `git reset --hard $PREV_COMMIT` + rebuild yapiyor — yani SADECE KOD rollback'i, oncesinde DB dump'i ALINMIYOR. Yikici/hatali bir migration semayi ileri tasir, geri donulecek kopya yoktur. Her rutin deploy bir veri-kaybi vektoru.
- scripts/live_gate.py:4 docstring'i P6 kapilarini "saglik, login, cockpit, koc, cron 24s, YEDEK" diye sayiyor; ama gate satirlarinda (s.ekle(...), 78-194) yedek kapisi YOK. Canli-dogrulama kapisi bu eksigi yakalamiyor.

KAPATMAYAN AZALTICI: scripts/restore.py + tests/test_backup_restore_drill.py + tests/test_postgres_restore_drill.py geri-yukleme yolunu provali kanitliyor. Ancak geri yuklenecek bir yedek uretilmediginden bu dayaniklilik saglamiyor — runbook'un kendi kurali "geri yuklenebildigi kanitlanmamis yedek yedek degildir"in tersi burada gecerli: var olmayan yedegin restore proseduru degersizdir.

SIDDET: kritik degil yuksek — kayip aktif bir sizinti degil, tetikleyici olay gerektiriyor (Free-Tier VM geri alinmasi, volume bozulmasi, `docker compose down -v`, hatali migration). Ama tetiklendiginde butun beta kullanicilarinin tum finansal gecmisi (hesaplar, islemler, borclar, hedefler, koc hafizasi) geri donulemez sekilde kayboluyor ve KVKK butunluk/erisilebilirlik yukumlulugu karsilanmiyor.
</details>

### D14 · [orta] "Paylasilan saglayici gunluk kotasi" fiilen KULLANICI-BASINA sayiliyor — 1500/gun korumasi olu, block dali matematiksel olarak erisilemez

- **Boyut:** kota-maliyet · **Yer:** `app/routers/coach.py:213` · **Durum:** ✅ **KAPANDI — BUG #234**
  (6 Ağu, D15 ile aynı commit — aynı kök: sayacın neyi saydığı). Paylaşılan sayaç artık
  kullanıcı filtresizdir (`llm_quota.paylasilan_cagri_sayisi`) → %80 uyarısı ve %100 dalı
  gerçekten erişilebilir, ölü UI canlandı. `block` alanının anlamı **"istek reddedilecek"**
  olarak netleşti: yedekli zincirde tavan dolsa bile ürün kilitlenmez (L6), yalnız `warn`
  ateşler; alternatifsiz kurulumda 429 döner. `GET /api/coach/usage` de artık kararlı
  etiket kullanıyor (eskiden "Fallback(Gemini)" etiketiyle rozet sessizce ölüyordu).
- **Neden yayın engeli / etki:** KULLANICI KAYBI + PARA KAYBI. Kapali betada tek API anahtari paylasiliyor. 20 kullanici x 80 mesaj = 1600 mesaj (asagidaki 3. bulguyla birlikte ~3200 gercek Gemini istegi) — ucretsiz kademe 1500/gun tavani sessizce asilir. Uygulamanin kendi korumasi (warn %80 rozeti + block) hicbir zaman ates etmedigi icin ne kullanici ne operator uyarilmaz; kullanicilar ard arda 'Koc su an cevap veremedi (saglayicilar mesgul olabilir)' (coach.py:482) jenerik mesajini alir. Beta kullanicisi icin bu 'urun bozuk' demektir ve sessiz terk sebebidir — P7/P8 metriklerinin cozmeye calistigi tam sorun. Guvenlik-review-publish.md'de kabul-edilen-risk olarak YAZILI DEGIL; aksine UsageInfo docstring'i ve ADR-041 bu korumanin CALISTIGINI iddia ediyor (KURAL R3: disk aksini gosteriyor).

<details><summary>Kanıt</summary>

```
KOD (app/routers/coach.py:207-220) — saglayici kotasi sorgusu user_id ile filtreli:
    def _today_call_count(db: Session, user_id: int, provider: str) -> int:
        today_start = datetime.combine(datetime.utcnow().date(), datetime.min.time())
        return (db.query(func.count(ApiCallLog.id))
                .filter(ApiCallLog.user_id == user_id,          # <-- KULLANICI-BASINA
                        ApiCallLog.provider == provider,
                        ApiCallLog.called_at >= today_start).scalar() or 0)

Oysa sozlesme (app/routers/coach.py:84-85) bunun PAYLASILAN oldugunu soyluyor:
    # BUG #188 (P3): KULLANICI-BASINA tavan. Yukaridakiler saglayicinin PAYLASILAN gunluk
    # kotasidir; tek kullanici onu tuketirse herkes kilitlenir.

KOMUT: venv/Scripts/python.exe -m pytest <scratchpad>/probe3.py -q -s
  (B kullanicisi bugun 2000 gemini cagrisi yapmis; ilan edilen limit 1500)
CIKTI:
  A kullanicisinin gordugu usage: {'today_count': 0, 'daily_limit': 1500, 'percentage': 0.0,
                                   'warn': False, 'block': False, 'user_today_count': 0,
                                   'user_daily_limit': 80}
  B 2000 cagri yapmisken A'nin chat sonucu: 200
  >>> DB'deki TOPLAM bugunku gemini cagrisi: 2001 | ilan edilen gunluk limit: 1500
  >>> A icin block: False  today_count: 0

Ayrica olculebilir olu-kod: coach_user_daily_limit() varsayilani 80 (.env.prod.example:52
COACH_DAILY_USER_LIMIT=80), GEMINI_DAILY_LIMIT=1500 (coach.py:173). Sayac kullanici-basina
oldugu icin tek bir kullanici 1500'e ULASAMADAN 80'de 429 yiyor -> coach.py:447 'if pre_usage.block'
dali (ve %80 'warn' rozeti) hicbir zaman tetiklenemez.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

DISKTEN DOGRULANDI (curutulemedi). (1) app/routers/coach.py:207-220 `_today_call_count` gercekten `ApiCallLog.user_id == user_id` ile filtreli; ayni dosyanin 84-85. satirindaki sozlesme ("Yukaridakiler saglayicinin PAYLASILAN gunluk kotasidir") YANLIS. (2) Kendi bagimsiz probumu kosturdum (scratchpad/probe_kota_b.py, 2 passed, COACH_DAILY_USER_LIMIT env'i SILINEREK varsayilan 80 ile): B kullanicisi bugun 2000 gemini cagrisi yapmisken A'nin gordugu usage = {'today_count': 0, 'daily_limit': 1500, 'block': False} ve A'nin /api/coach/chat cagrisi 200 dondu. (3) Olu-dal matematiksel olarak dogrulandi: A kendi tavanini (80) doldurunca usage 'percentage': 5.3, warn=False, block=False; istek coach.py:441 kisisel-tavan dalindan 429 aliyor -> coach.py:447 `if pre_usage.block` ve %80 warn hicbir zaman tetiklenemez. Frontend'de de olu UI: Coach.jsx:367-368 + 397-412 (block bandi "Gunluk Gemini limiti doldu" + input disable) asla gorunmez. (4) Baska katman kapatmiyor: PROVIDER_DAILY_LIMITS yalniz _build_usage_info'da kullaniliyor; middleware/dependency/global sayac yok; guvenlik-review-publish.md §4 KABUL EDILEN RISKLER icinde YAZILI DEGIL. ANCAK iddia edilen zarar buyuklugu abartili (bu yuzden kritik/yuksek degil orta): (a) ADR-041'in asil guard'i olan KULLANICI-BASINA tavan CALISIYOR (80'de 429 kaniti var); (b) prod varsayilani LLM_PROVIDER=fallback (.env.prod.example:29) ve app/coach.py:1955-1978 FallbackProvider kota-hatasini yakalayip siradaki saglayiciya geciyor -> ikinci anahtar varsa paylasilan tukenme sogurulur; (c) Gemini ucretsiz kademede 1500 asimi FATURA degil 429 uretir, yani dogrudan "para kaybi" kaniti yok; (d) masterprompt-publish.md:114 kapali betayi "davetli, 3-10 kisi" olarak tanimliyor, 10x80=800 satir < 1500. Yine de gercek bir agirlastirici var: router chat basina TEK ApiCallLog satiri yaziyor (coach.py:281) ama engine.chat 2+ provider.chat yapiyor (coach.py:2513/2535), yani 80 "cagri" ~160+ gercek istek -> ~10 agir kullanicida paylasilan tavan erisilebilir hale geliyor. Sonuc: gercek, olculebilir bir defekt (olu koruma dali + olu UI + yanlis kod sozlesmesi) ama veri sizintisi/guvenlik siniri yok ve urun LLM'siz calismaya devam ediyor (ADR-001) -> kapali beta yayin engeli degil, acik beta (P8) oncesi kapatilmasi gereken bir borc.
</details>

### D15 · [orta] Kota tavani CAGRI degil MESAJ sayiyor — gercek LLM maliyeti ADR-041'in ilan ettiginin 2-3 kati

- **Boyut:** kota-maliyet · **Yer:** `app/routers/coach.py:457` · **Durum:** ✅ **KAPANDI — BUG #234**
  (6 Ağu, D14 ile aynı commit). Sayım noktası ağa çıkan isteğe taşındı: `LLMProvider.__init_subclass__`
  her somut sağlayıcının `_raw_chat`'ini otomatik sarmalar (yeni sağlayıcı eklenince kanca
  unutulamaz), ölçüm `llm_quota.cagri_olcumu()` kapsamında toplanır, istek sonunda
  `ek_cagrilari_uzlastir` farkı sayaca yazar. **Sınıf taraması (L11) iki ek yol buldu:**
  premortem ve aksiyon yansıması da tek satırla birden fazla gerçek isteği örtüyordu — üçü
  de kapatıldı. ADR-041'in "80 çağrı ≈ 40 mesaj" sözleşmesi artık diskte DOĞRU.
- **Neden yayın engeli / etki:** PARA KAYBI (yanlis kalibre edilmis maliyet tavani). Beta butcesi ADR-041'in rakamina gore planlaniyor; gercek harcama kullanici basina 2-3 kat. Ucretli kademeye gecildiginde fatura ongorusu dogrudan yanlis olur. Ayrica 2. bulguyla birlesince paylasilan ucretsiz kademe (1500/gun) ilan edilenden 2-3 kat erken tukenir — yani koc, operator hicbir uyari gormeden gun ortasinda tum kullanicilar icin oluyor. Bu bir stil/tercih meselesi degil: belgelenmis sayisal sozlesme ile calisan kod celisiyor (KURAL R3).

<details><summary>Kanıt</summary>

```
KOMUT: venv/Scripts/python.exe -m pytest <scratchpad>/probe_quota_bypass.py::test_bir_chat_kac_provider_cagrisi_bir_satir -q -s
  (CoachEngine'e sayan gercek LLMProvider verildi, tek /api/coach/chat istegi)
CIKTI:
  HTTP: 200
  >>> provider.chat cagri sayisi: 2  | ApiCallLog satiri: 1

KAYNAK: app/coach.py:2513 (STEP B.5 iki-gecis 'plan') + app/coach.py:2535 (STEP C ana cagri)
+ app/coach.py:2661 ve :2728 (iki ayri retry dali) => bir istek 1-4 provider.chat edebilir.
Buna karsilik app/routers/coach.py:457 istek basina TEK satir rezerve eder:
    rezervasyon = _kota_rezerve_et(db, user.id, provider_name, model, kisisel_tavan)

CELISEN BELGE — docs/architecture/adr-041-per-user-llm-quota.md:22
    - Env: `COACH_DAILY_USER_LIMIT` (varsayilan **80 cagri ~ 40 mesaj/gun**; `0` = kapali).
ve ayni ADR satir 16: '**Carpan:** Iki-gecis mimarisi nedeniyle her koc mesaji **2 cagri** eder.'
Gercek: 80 satir = 80 MESAJ = ~160 (retry ile 240'a kadar) saglayici cagrisi, ilan edilenin 2-3 kati.
app/routers/coach.py:226-228 docstring'i de ayni yanlisi tekrarliyor.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

DISKTEN DOGRULANDI, curutulemedi. (1) Kod: app/routers/coach.py:457 -> _kota_rezerve_et istek basina TEK ApiCallLog satiri yazar (:281-287 insert, :492 ayni satiri gunceller). app/ genelinde ApiCallLog grep'i baska hicbir artirma noktasi gostermiyor (yalniz coach router + user.py:193 KVKK export). app/main.py'de sadece CORS + _GovdeBoyutuMiddleware var; coach chat'te rate-limiter yok; model constraint / dependency / migration katmaninda telafi yok. (2) Coklu cagri gercek: app/coach.py:2513 (STEP B.5 iki-gecis plan; kosul include_cockpit ve not has_realized_action, include_cockpit varsayilan True -> app/schemas.py:177) + :2535 (STEP C ana cagri) + :2661/:2728 iki retry dali; ayrica app/coach.py:1944 FallbackProvider'in ic dongusu tek self.provider.chat'i birden fazla ust-saglayici cagrisina cevirebilir. (3) KENDI PROBUM (scratchpad/probe_kota.py, gercek CoachEngine + sayan LLMProvider, tek POST /api/coach/chat): "HTTP: 200 / provider.chat cagri sayisi: 2 | ApiCallLog satiri: 1" (1 passed). (4) Sozlesme celiskisi: adr-041 satir 16 "her koc mesaji 2 cagri eder" + satir 22 "varsayilan 80 cagri ~ 40 mesaj/gun"; kod 80 satir = 80 MESAJ ~ 160 saglayici cagrisi. Ayni yanlis app/routers/coach.py:226-228 docstring'inde tekrarlaniyor. Ayni undercount paylasilan tavanda da var: GEMINI_DAILY_LIMIT=1500 (coach.py:171) satir sayisiyla kiyaslandigi icin gercek 1500 cagri tuketildiginde sayac ~750 gosterir; warn (%80) ve block (%100) saglayici kendisi 429 vermeden ONCE hic tetiklenmez -> operator korumasi fiilen 2 kat gec calisir. (5) Mevcut test curutmuyor: tests/test_coach_user_quota.py SahteMotor kullaniyor (chat dict doner, provider'a hic dokunmaz), carpani olcemez. (6) Kabul-edilen-risk degil: docs/kalite-seruveni/guvenlik-review-publish.md:66-78 listesinde yok (satir 75'teki tek kota atfi prompt-injection ertelemesi). SIDDET "orta": kontrol VAR ve dayatiliyor, veri sizintisi/hukuki risk yok, Rules Engine LLM'siz calismaya devam eder (graceful degradation) -- ama ilan edilen sayisal maliyet tavani 2 kat (retry ile ~3 kat) yanlis kalibre; ucretli kademede fatura ongorusu dogrudan yanlis ve ucretsiz kademede uyari esigi kor kaliyor.
</details>

### D16 · [orta] Aksiyon onayi (POST /api/actions/{id}/approve) arka planda kotasiz + kayitsiz Groq LLM cagrisi yapiyor

- **Boyut:** kota-maliyet · **Yer:** `app/routers/actions.py:127` · **Durum:** ✅ **KAPANDI — BUG #228** (5 Ağu, D07 ile aynı commit — aynı kök).
  Arka plan yansıması artık `app/llm_quota` üzerinden rezerve eder; tavan doluysa **atlar**
  (arka plan görevi kullanıcıya 429 gösteremez — doğru davranış işi atlamak, sessizce kotasız
  çağırmak değil). Koşarsa `ApiCallLog`'a düşer → maliyet metrikleri artık bu trafiği görüyor.
  Beklenmedik hatada rezervasyon iptal edilir (asılı kalan sayaç satırı yok).
- **Neden yayın engeli / etki:** PARA KAYBI + KOR IZLEME. 100 TL ustu her harcama/satis/borc-odeme onayi 1-2 ek LLM cagrisi uretiyor; hicbiri kotaya sayilmiyor, hicbiri ApiCallLog'a yazilmiyor. Kullanici koc kotasi dolduktan SONRA da (dogrulandi) bu yolu tetikleyebiliyor. Beta'da islem girisi mesaj sayisindan cok daha ucuz ve siniri olmayan bir eylem oldugu icin gercek LLM harcamasinin onemli bir kismi olcum disi kaliyor: scripts/beta_metrics.py'nin raporladigi cagri/hata/gecikme rakamlari gercegin altinda kalir, operator maliyet ve saglayici-hata artisini goremez. ADR-041 dayatma noktasini yalnizca /api/coach/chat sayiyor; bu yol ne ADR'de ne guvenlik-review-publish.md kabul-edilen-riskler bolumunde geciyor.

<details><summary>Kanıt</summary>

```
KOMUT: venv/Scripts/python.exe -m pytest <scratchpad>/probe4.py -q -s
  (kullanicinin kotasi DOLU: 5 cagri / tavan 1; approve'un ekledigi background task dogrudan 3 kez calistirildi)
CIKTI:
  >>> kota DOLU (5/1). reflection LLM cagri sayisi: 6 | ApiCallLog once/sonra: 5 / 5
  >>> _should_reflect(add_transaction, 500 TL) = True
(6 cagri = 3 onay x 2 model fallback; ApiCallLog hic degismedi)

KOD app/routers/actions.py:312-318 — onay ucu task'i ekliyor:
            background_tasks.add_task(
                _run_reflection,
                user_id=current_user.id,
                action_type=pending.action_type, ...
KOD app/routers/actions.py:124-131 — task icinde kotasiz LLM, iki model denenir:
        for model in _REFLECTION_MODELS:      # 'llama-3.1-8b-instant,llama-3.3-70b-versatile'
                provider = GroqProvider(api_key=groq_key, model=model.strip())
                response = provider.chat(system_prompt=system_prompt, ...)

KOMUT: grep -c "ApiCallLog|coach_user_daily_limit|_kota_rezerve_et" app/routers/actions.py
CIKTI: 0
```
</details>

<details><summary>Çelişme turu hükmü</summary>

CURUTULEMEDI — diskten ve calisan koddan dogrulandi.

1) KOD (okundu, iddia birebir dogru):
- app/routers/actions.py:49-53 `_REFLECTION_MODELS = os.getenv("REFLECTION_MODELS","llama-3.1-8b-instant,llama-3.3-70b-versatile").split(",")`, esik 100 TL, tipler {add_transaction, sell_investment, mark_debt_paid}.
- app/routers/actions.py:118-151 `_run_reflection` icinde `GroqProvider(api_key=groq_key, model=...)` + `provider.chat(...)` iki model icin sirayla; hicbir kota kontrolu, hicbir ApiCallLog yazimi yok.
- app/routers/actions.py:309-318 approve ucu bu task'i `background_tasks.add_task(_run_reflection, ...)` ile ekliyor.
- grep: actions.py icinde "ApiCallLog|kota|quota|rate_limit" -> yalnizca 1 yorum satiri (satir 77), dayatma kodu YOK.

2) BASKA KATMAN KAPATMIYOR:
- Kota + loglama YALNIZCA app/routers/coach.py'de (`_kota_rezerve_et`/`_rezervasyonu_tamamla`/`coach_user_daily_limit`, satir 208-352). GroqProvider.chat (app/coach.py:1681) sadece `_call_with_retry(self._raw_chat,...)`; ApiCallLog import'u coach.py'de hic yok.
- approve ucunda rate limit yok: `rate_limit(` yalnizca app/routers/auth.py'de (7 yer).
- ADR-041 (docs/architecture/adr-041-per-user-llm-quota.md:24) dayatma noktasini acikca "POST /api/coach/chat" olarak tanimliyor — bu yol kapsam disi.
- docs/kalite-seruveni/guvenlik-review-publish.md §4 KABUL EDILEN RISKLER (satir 65-77): reflection/actions/arka-plan LLM gecmiyor (grep 0 eslesme) — belgelenmis kabul-edilen-risk DEGIL.

3) CALISTIRILAN KANIT (kendi probum, TestClient ile GERCEK approve ucu; scratchpad/probe_refl.py):
KOMUT: venv/Scripts/python.exe -m pytest <scratchpad>/probe_refl.py -q -s
CIKTI:
  >>> approve status: 200
  >>> LLM cagri sayisi (reflection): 2 ['llama-3.1-8b-instant', 'llama-3.3-70b-versatile']
  >>> ApiCallLog once/sonra: 5 / 5
  >>> user_daily_limit: 1
Kullanicinin gunluk tavani DOLUYKEN (5 cagri / tavan 1) tek bir 500 TL gider onayi 2 ek Groq cagrisi uretti, ApiCallLog hic degismedi. GROQ_API_KEY canli .env:17'de DOLU ve docker-compose.prod.yml:56 ile prod'a geciyor — yol olu degil.

4) IDDIADAN DAHA GENIS: pending action uretimi koca bagli degil. app/routers/expenses.py:205 (`/api/expenses/recurring/trigger-due`) hicbir LLM cagrisi yapmadan add_transaction/expense pending'leri uretiyor; duzenli-gider sayisi sinirsiz. Sifir koc mesaji harcamis kullanici bile N adet >=100 TL onay ile 2N kotasiz+kayitsiz LLM cagrisi tetikleyebilir.

ZARAR: (a) ADR-041'in "maliyet tavani + adalet" invaryanti bu yolda gecersiz — paylasilan Groq anahtarini tek kullanici tuketip digerlerinin fallback zincirini bozabilir; (b) scripts/beta_metrics.py yalnizca ApiCallLog'u okuyor (satir 72-129) → operatorun gordugu cagri/hata/gecikme rakamlari bu trafik icin sistematik olarak eksik (kor izleme).

SIDDET GEREKCESI: orta — veri sizintisi/hesap ele gecirme yok, hata sessiz yutuluyor (kullaniciya yansimiyor), modeller ucuz/kucuk; ancak belgelenmis bir kota invaryantinin gercek bypass'i + beta maliyet-olcumunde sistematik kor nokta.
</details>

### D17 · [orta] Saat dilimi kişiselleştirmesi YARIM: kullanıcı-bağlamlı tarih yollarının çoğu hâlâ sunucu tarihini kullanıyor (ADR-042'nin kendi iddiası diskte yanlış)

- **Boyut:** urunlesme · **Yer:** `app/action_executor.py:600` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** Kapalı beta hedefi "yabancı bir kullanıcı kendi hayatını kurabilmeli". Sunucu TR'de (UTC+3); farklı saat dilimindeki bir beta kullanıcısı için: (1) koça "bugün 300 TL market harcadım" dediğinde işlem YANLIŞ GÜNE kalıcı yazılır — kullanıcının kendi girdiği veri sessizce bozulur ve geri alması için elle düzeltmesi gerekir; (2) ay sınırında gider bir önceki/sonraki aya düşer, bu da aylık özet, kategori bütçesi ve günlük harcama limitini yanlış hesaplar — kullanıcı yanlış sayıya bakarak PARA KARARI verir; (3) monthly-summary parametresiz çağrıldığında yanlış ayı açar; (4) net-değer snapshot'ı sunucu günüyle damgalandığı için trend grafiği kullanıcının gördüğü günle hizasız kalır. ADR-042 bu zararı KENDİSİ tarif edip "uygulandı" demiş; belge doğru, kod yarım. Bu kabul edilmiş bir risk DEĞİL — tam tersine kapatıldığı iddia edilmiş bir doğruluk hatası, dolayısıyla kimse tekrar bakmayacak.

<details><summary>Kanıt</summary>

```
ADR-042 (docs/architecture/adr-042-user-personalization.md) DİYOR Kİ: "Şimdi (bu ADR ile uygulandı): User.timezone — tarih üreten TÜM kullanıcı-bağlamlı yollar app/user_prefs.user_today(user) kullanır." DİSK BUNU ÇÜRÜTÜYOR.

KOMUT: grep -rn "user_today" app/ --include=*.py | grep -v user_prefs.py
ÇIKTI: yalnız 7 router (actions, cockpit, debts, envelopes, expenses, incomes) benimsemiş.

KOMUT: grep -rn "date.today()" app/routers/*.py
ÇIKTI (kullanıcı-bağlamlı, current_user KAPSAMDA olduğu halde sunucu tarihi):
  app/routers/reports.py:60   since = date.today() - timedelta(days=days)
  app/routers/reports.py:134  since = date.today() - timedelta(days=days)
  app/routers/reports.py:167  calculate_networth_attribution(current_user.id, date.today(), db)
  app/routers/reports.py:184  calculate_real_networth(current_user.id, date.today(), db)
  app/routers/reports.py:218  today = date.today()   (upcoming-cashflow)
  app/routers/reports.py:326  today = date.today()   (monthly-summary: y = year or today.year)
  app/routers/subscriptions.py:52  detect_subscriptions(user.id, date.today(), db, ...)
  app/routers/cockpit.py:41   today = date.today()   (_ensure_today_snapshot) — AYNI İSTEKTE satır 88 user_today(user) kullanıyor (kendi içinde tutarsız)

EN AĞIRI — KALICI YANLIŞ VERİ YAZIMI (app/action_executor.py:596-600):
    txn_date = payload.get("transaction_date")
    if txn_date:
        txn_date = date.fromisoformat(txn_date) if isinstance(txn_date, str) else txn_date
    else:
        txn_date = date.today()          # <-- SUNUCU tarihi, user_today(user) DEĞİL
(aynı desen app/action_executor.py:685 paid_date için)

ÇALIŞTIRDIĞIM KANIT (in-memory DB, salt-okur prob):
  KOMUT: PYTHONPATH=. venv/Scripts/python.exe scratchpad/probe_tz.py
  ÇIKTI:
    SUNUCU date.today() = 2026-08-05
    tz=Pacific/Kiritimati
      user_today(user)        = 2026-08-06
      DB'ye YAZILAN tx tarihi = 2026-08-05
      ESLESIYOR MU            = False
    tz=Pacific/Midway
      user_today(user)        = 2026-08-04
      DB'ye YAZILAN tx tarihi = 2026-08-05
      ESLESIYOR MU            = False
(Prob koçun kaydettiği yolu doğrudan çağırıyor: _execute_add_transaction(db, user.id, {...}) — transaction_date verilmediğinde.)

MEVCUT TEST KAPSAMI BU BOŞLUĞU GÖRMÜYOR:
  KOMUT: grep -n "def test_" tests/test_user_preferences.py
  ÇIKTI: 7 test — yalnız user_prefs yardımcıları + PUT /api/user + cockpit ucu.
  action_executor yazma yolu, reports, subscriptions, net-değer snapshot'ı HİÇ sınanmamış.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

Bulgu diskten dogrulandi, curutulemedi. (1) app/action_executor.py:596-600 gercekten `txn_date = date.today()` kullaniyor; ayni desen 685'te paid_date icin. (2) Yapisal: execute_pending_action (satir 399) handler'i `handler(db, user_id, payload)` ile cagiriyor — User nesnesi hic gecmiyor, dolayisiyla hicbir handler user_today'e ULASAMAZ; bu atlanmis bir cagri degil, tasarim bosluğu. (3) app/coach.py:281-283 prompt'u LLM'e "payload'a transaction_date EKLEME — tarih belirtilmemisse default bugun olur" diyor, yani sik kullanilan yol bilerek date.today() dalina giriyor. (4) Kendi calistirdigim salt-okur prob (_execute_add_transaction dogrudan cagrildi): sunucu 2026-08-05 iken Pacific/Kiritimati kullanicisi icin user_today=2026-08-06, DB'ye yazilan 2026-08-05; Pacific/Midway icin user_today=2026-08-04, yazilan 2026-08-05 — ikisinde de ESLESMIYOR. (5) grep -rn "user_today" app/ yalniz 6 router'da adaptasyon gosteriyor; action_executor/reports/subscriptions yok. cockpit.py:41 (_ensure_today_snapshot) date.today(), ayni istekte satir 88 user_today(user) — kendi icinde tutarsiz, ikisini de okudum. reports.py:60,134,167,184,218,326 ve subscriptions.py:52'de current_user imzada KAPSAMDA oldugu halde date.today() kullaniliyor (imzalari okudum). (6) Baska katman kapatmiyor: app/ icinde TZ middleware / tzset / istek-kapsamli tz contextvar yok (yalniz workspace contextvar'lari); app/main.py middleware'leri CORS + govde-boyutu. transactions router'inda date.today() fallback'i yok, yani hata koc yazma yoluna ozgu. (7) Kabul-edilen-risk DEGIL: guvenlik-review-publish.md yalniz #169'u (konteyner TZ tanimsiz) aniyor; masterprompt-publish.md:86/:460 "H4 saat dilimi TAMAM" ve ADR-042 "tarih ureten TUM kullanici-baglamli yollar user_today kullanir" diyor — bu iddia diskte YANLIS. (8) tests/test_user_preferences.py 7 test: yalniz user_prefs yardimcilari + PUT /api/user + cockpit ucu; executor yazma yolu sinanmamis. SIDDET DUSURULDU (kritik/yuksek degil, orta): veri sizintisi/para hareketi/hukuki risk yok; hata yalniz User.timezone SET EDILMIS ve sunucudan farkli gune dusen kullanicilarda tetikleniyor — canli tek TR kullanicisinda timezone nullable (app/models.py:154) ve user_today TZ yoksa date.today()'e dusuyor, yani mevcut davranis degismiyor. Rapor tarafi kalemleri (reports/monthly-summary) yalnizca gun-siniri goruntu kaymasi. Asil agirlik executor'in kalici yanlis-gun yazimi + ayni istekteki cockpit/snapshot tutarsizligi; TR-onceligli kapali beta icin sert yayin kapisi degil, ama TR disi ilk kullanicidan once kapatilmasi gereken gercek dogruluk borcu.
</details>

### D18 · [orta] Kurucunun ve adı geçen üçüncü bir kişinin gerçek finansal verisi (tutarlar, borç takvimi, banka markaları) production Docker imajına giriyor

- **Boyut:** urunlesme · **Yer:** `scripts/setup_data.py:1` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** KVKK/hukuki: "Efe" gerçek bir üçüncü kişidir ve borç tutarları + 13 aylık ödeme takvimi onun finansal verisidir; bu veri, o kişinin rızası olmadan dağıtılan bir yapıya (Docker imajı) gömülü halde taşınıyor. İmaj bir registry'ye push edilir, bir sunucu ele geçirilir veya destek amacıyla paylaşılırsa kurucunun VE adı geçen kişinin gerçek bakiyeleri, kredileri, banka ilişkileri ve aile içi para düzenlemeleri ifşa olur — bunlar KVKK m.6 anlamında olmasa da açıkça özel nitelikli-benzeri hassasiyette finansal kişisel veridir. Buna ek olarak drop_all yolu prod konteynerinde erişilebilir kalıyor: tek yanlış komut tüm beta kullanıcılarının verisini kalıcı siler (yedekten dönüş dışında telafisi yok). Çözüm ucuz ve yan etkisiz: .dockerignore'a scripts/setup_data.py eklemek (veya scripts/ altında yalnız gerekli olanları COPY etmek) — kod değişikliği gerekmiyor.

<details><summary>Kanıt</summary>

```
İMAJA GİRİYOR — Dockerfile:33
  COPY scripts ./scripts
.dockerignore tests/ ve docs/ dizinlerini eliyor ama scripts/ İÇİN İSTİSNA YOK:
  KOMUT: cat .dockerignore
  ÇIKTI (ilgili): .git / venv/ / frontend/node_modules/ / data/ / docs/ / tests/ / .env  — 'scripts' GEÇMİYOR.

DOSYA İÇERİĞİ (scripts/setup_data.py):
  satır 2:   "setup_data.py — Murat'in GERCEK Mayis 2026 finansal manzarasi."
  satır 10:  "- Murat'in 1 Mayis 2026 itibariyle gercek verilerini yukler"
  satır 77:  name="Enpara Nakit"   · satır 87: name="Ziraat Kredi Karti"
  satır 100/113/126/139/152: "Garanti Kredi 1 (30K)" ... "Garanti Kredi 5 (6K - Efe)"
  satır 230: (date(2026,5,5), 10215.00, "Ortak krediler son pay ...")
  satır 250-266: 13 satırlık ALACAK TAKVİMİ — counterparty="Efe", gerçek tutar+vade
  satır 322-329 (MC7 checkpoint metni): "Efe Garanti kredilerinin BAZILARINI paylasti. 30K iki kredi
     (Kredi 1+2) Mayis'a kadar paylasimli, Mayis sonrasi tamamen Murat'a. 9K (Kredi 3), 7.5K (Kredi 4),
     6K (Kredi 5) tamamen Efe'ye ait, Efe nakit gonderir Murat oder. Toplam Efe alacagi 29.635 TL,
     13 ay yayilmis. 5 May'da 11.065 TL ilk buyuk giris ..."
  satır 275: "# MC1 SILINDI - Anne 1 Mayis'ta TLY emanetini Murat'a hediye etti."

AYRICA DESTRUCTIVE (satır 48-50): drop_all + create_all. Guard var (satır 40-46: interaktif onay VEYA --force / SETUP_DATA_FORCE=1) ama imajın içinde durduğu için prod konteynerinde `SETUP_DATA_FORCE=1 python -m scripts.setup_data` tek komutla tüm beta kullanıcılarının DB'sini siler ve yerine bu kişisel veriyi kurar. docker-entrypoint.sh onu ÇAĞIRMIYOR (doğrulandı: yalnız `alembic upgrade head` + gunicorn) — yani otomatik tetiklenme yok, risk elle-komut yüzeyi.

KARŞILAŞTIRMA (ürünleşmiş doğru desen mevcut): app/routers/onboarding.py demo verisi tamamen jenerik — "Örnek Vadesiz Hesap", "Örnek Kredi Kartı", "Örnek Maaş" — ve dosya başında bunu açıkça yazıyor: "Sorun: ... tek çözüm scripts/setup_data.py'ydi — o da BAŞKASININ (kullanıcının) kanonik verisini yükler ve drop_all yapar; bir beta kullanıcısına asla bulaşmamalı." Yani ekip riski TANIMLAMIŞ ama dosyayı imajdan çıkarmamış.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

Kod iddialari diskten birebir dogrulandi: Dockerfile:33 `COPY scripts ./scripts`, .dockerignore'da (21 satirin tamami okundu) `scripts` icin hicbir desen/istisna yok, docker-compose.prod.yml backend+scheduler servisleri bu kok Dockerfile'i build ediyor. scripts/setup_data.py gercekten gercek kisisel + ucuncu-kisi finansal verisi tasiyor (s.77 "Enpara Nakit", s.87 "Ziraat Kredi Karti", s.100/126/139 "Garanti Kredi ... (9K - Efe)", s.228-251 efe_takvim -- kodda 15 kayit, docstring'in dedigi 13 degil; s.257 counterparty="Efe"; s.320-329 MC7 metni alintilandigi gibi) ve s.40-51 drop_all + --force/SETUP_DATA_FORCE=1 bypass'i var. docker-entrypoint.sh onu cagirmiyor (dogru). onboarding.py:1-14 karsilastirmasi da birebir dogru. guvenlik-review-publish.md'de "setup_data" hic gecmiyor -> belgelenmis kabul-edilen-risk degil.

ANCAK zarar modeli ve onerilen cozum curutuldu: (1) `git remote -v` = https://github.com/Muratcnicgl/financialos.git ve GitHub API `"private": false`; anonim curl ile raw.githubusercontent.com/.../main/scripts/setup_data.py HTTP 200 dondu ve Efe/Enpara/Garanti satirlari icerikte goruldu -> veri ZATEN herkese acik, Docker imaji birincil ifsa kanali degil, cok daha dar bir alt kume. (2) scripts/deploy.sh:24-28 sunucuda `git pull --ff-only origin main` yapip build ediyor; yani dosya .dockerignore'a eklense bile prod host'un disk'ine repo ile birlikte iniyor -- onerilen "ucuz, yan etkisiz" fix gercek maruziyeti kaldirmiyor. (3) "scripts/ altindan yalniz gerekliyi COPY et" onerisi dikkatsiz uygulanirsa kirici: app/startup.py:32 runtime'da `from scripts.backfill_net_worth import run_backfill` yapiyor. (4) drop_all "tek komutla tum beta DB'si silinir" iddiasi ek risk degil: bu yol konteyner icinde shell gerektirir; shell'i olan zaten DATABASE_URL'i okuyup DROP SCHEMA calistirabilir. deploy.sh/prod_rehearsal.py/live_gate.py'de setup_data cagrisi ve registry push yok (grep bos).

Sonuc: bulgu ayakta ama kritik degil. Gercek yayin-engeli olan sorun daha genis ve farkli: adi gecen ucuncu kisinin (Efe) tutar+vade takvimi ile kurucunun banka/bakiye verisi PUBLIC bir GitHub deposunda duruyor; dogru duzeltme .dockerignore satiri degil, verinin depodan (ve gecmisten) cikarilip setup_data.py'nin jenerik hale getirilmesi ya da tamamen kaldirilip onboarding demo-veri yoluna birakilmasidir. Bulgunun tarif ettigi imaj-yuzeyi bu sorunun yalnizca kucuk bir tezahuru oldugu icin siddet "orta".
</details>

### D19 · [orta] Capraz-kullanici izolasyon matrisinin 'kapsam kilidi' testi commit'li halde SIFIR uc tariyor — kirilmasi imkansiz bos kapi

- **Boyut:** test-kalitesi · **Yer:** `tests/test_cross_user_isolation.py:285` · **Durum:** BUG #217 ile KAPANDI (5 Ağu, commit 442aabf)
- **Neden yayın engeli / etki:** Bu, kapali betanin capraz-kullanici (IDOR) sizinti kapisi. Kapi 'yesil' oldugu icin, P4/P5'te eklenen her yeni `/{id}` ucu izolasyon testi yazilmadan repoya girebildi ve kimse uyarilmadi. Coklu-kullanici workspace'e acilan bir finansal uygulamada B kullanicisinin A'nin hesap/borc/hedef kaydini ID tahmin ederek okumasi = dogrudan finansal veri sizintisi + KVKK ihlali. Kapinin varligi guvenlik denetimlerinde 'kapsam kilitli' diye sayildi; gercekte hicbir sey korumuyordu.

<details><summary>Kanıt</summary>

```
HEAD (d62f6dd) surumundeki kod:
```python
    eksik = []
    for r in app.routes:
        path = getattr(r, "path", "")
        if not path.startswith("/api") or "{" not in path:
            continue
```
Kendi calistirdigim dogrulama (varsayim degil):
```
$ ./venv/Scripts/python.exe -c "from app.main import app; n=[getattr(r,'path','') for r in app.routes if getattr(r,'path','').startswith('/api') and '{' in getattr(r,'path','')]; print(len(n))"
HEAD yontemi (app.routes) ID-li uc sayisi: 0

$ ./venv/Scripts/python.exe -c "from app.main import app; p=app.openapi()['paths']; print(len([y for y in p if y.startswith('/api') and '{' in y]))"
OPENAPI ID-li uc sayisi: 29
```
fastapi 0.141.1'de `include_router` alt yollari artik duzlestirmiyor; `app.routes` ID'li uc DONDURMUYOR. Dolayisiyla dongu hic donmuyor, `eksik` daima bos, `assert not eksik` daima gecer. Dosyanin kendi docstring'i (satir 11-13) bunun tersini iddia ediyor: 'Yeni bir `/{id}` endpoint'i eklenip matrise yazilmazsa test KIRILIR. Boylece bu dosya zamanla bayatlamaz.' Kanit ki bayatladi: calisma agacindaki duzeltme, kapi acilinca P4'te eklenmis `/api/legal/{slug}` ucunun kilit korken fark edilmeden gectigini itiraf ediyor (satir 258-259).
```
</details>

<details><summary>Çelişme turu hükmü</summary>

Bulgunun OLGUSAL cekirdegi diskten dogrulandi, curutulemedi. (1) `git show HEAD:tests/test_cross_user_isolation.py` HEAD'de (d62f6dd) tam olarak alintilanan `for r in app.routes:` dongusunu iceriyor. (2) Calistirdigim kontrol: fastapi 0.141.1'de `app.routes` = Counter({'_IncludedRouter': 29, 'Route': 4, 'APIRoute': 2}); 29 `_IncludedRouter` nesnesinin hepsinin `path` degeri bos string, `/api` ile baslayan tek yol `/api/health` ve onda `{` yok. Yani `/api` + `{` filtresini gecen uc sayisi 0, OpenAPI'de ayni filtre 29 uc veriyor. Dongu govdesi hic calismiyor, `eksik` daima bos, `assert not eksik` daima gecer — kapi fiilen olu. (3) Bayatlama somut: HEAD'in kendi RESOURCES + MATRIS_DISI (18 madde) setini OpenAPI envanterine uygulayinca tek kapsanmayan uc `/api/legal/{slug}` cikiyor; yani P4'te eklenen bir uc kor kapidan gercekten gecmis. `git diff` calisma agacindaki duzeltmenin (OpenAPI tabanli `tests/endpoint_envanteri.yol_parametreli_uclar` + legal maddesi) HENUZ COMMIT EDILMEDIGINI gosteriyor, dolayisiyla main'de kusur canli. (4) Dosyanin 11-13. satirdaki docstring garantisi ("yeni /{id} eklenirse test KIRILIR") HEAD'de yanlis. SIDDET DUSURULDU (kritik degil, orta): iddia edilen "dogrudan finansal veri sizintisi/IDOR kapisi acildi" zarari diskte DOGRULANMADI. Ayni dosyadaki 17 gercek IDOR testi kosuyor ve geciyor (7 kaynak ailesi, gercek HTTP probe'lari). Bagimsiz ve KORLESMEMIS ikinci bir kapi var: tests/test_scope_enforcement.py — regex kapisi (routers + rules_engine + goal_engine + debt_strategy + coach_insights) ARTI AST kapisi tum `app/` agacini tarayip 20 sahipli model uzerindeki kapsamsiz `db.query(M)`/`select(M)` sorgularini yakaliyor; ustelik tarayicinin kendisinin hep-yesil olmadigini ispatlayan meta-testleri var (BUG #162 deseni sentetik olarak besleniyor). Calistirdim: 6 passed. Yeni bir ucun baskasinin satirlarini sahiplik filtresiz okumasi bu kapiyi kirar. Kor donemde gercekten sizan tek uc olan `/api/legal/{slug}` ise kullanici kaynagi degil: app/routers/legal.py:44 sabit `BELGELER` sozlugunden slug cozuyor (path traversal yuzeyi yok, kimliksiz okunmasi KVKK geregi bilincli). Sonuc: gercek ve yayin oncesi kapatilmasi gereken OLU BIR GUVENLIK AGI (kapsam kilidi), ancak su anda acikta duran capraz-kullanici veri sizintisi degil.
</details>

### D20 · [orta] Bos-durum e2e kapisi 40 ucun 39'unu sessizce atliyordu (yalniz /api/health)

- **Boyut:** test-kalitesi · **Yer:** `tests/test_sifirdan_kullanici_e2e.py:86` · **Durum:** BUG #217 ile KAPANDI (5 Ağu, commit 442aabf)
- **Neden yayın engeli / etki:** Betaya davet edilen her yeni kullanici tam olarak bu durumdadir: sifir veri. Panellerin okudugu 39 ucun bos-durumda cokmedigi hic dogrulanmadi. Yeni kullanicinin ilk oturumunda 500 alip beyaz ekran gormesi = ilk izlenimde kullanici kaybi; kapali betada geri donusu olmayan bir kayip cunku davetli sayisi sinirli.

<details><summary>Kanıt</summary>

```
HEAD surumundeki `_parametresiz_get_uclari()` de `app.routes` uzerinden turetiyordu (bkz. `git diff tests/test_sifirdan_kullanici_e2e.py`, silinen bloklar). Kendi olcumum:
```
ESKI YONTEM (app.routes) parametresiz GET sayisi: 1
['/api/health']
OPENAPI parametresiz GET sayisi: 40
fastapi 0.141.1
```
Dosya docstring'i (HEAD, satir 11-12) sunu iddia ediyordu: 'Kapsam otomatik turetilir: parametresiz her GET ucu bos-durumda cagrilir. Yeni bir uc eklenip bos-durumda cokerse bu test kirilir (kapsam kendiliginden daralamaz).' Gerceklik: kapsam 40 -> 1'e dusmustu ve hicbir alarm uretmedi.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

DISKTEN DOGRULANDI, ama iddia edilen zarar abartili.

1) Kod gercekten oyle: `git show HEAD:tests/test_sifirdan_kullanici_e2e.py` icinde `_parametresiz_get_uclari()` envanteri `for r in app.routes` uzerinden turetiyor (HEAD satir ~86-96). Docstring satir 11-12 gercekten "Kapsam otomatik turetilir... kapsam kendiliginden daralamaz" iddiasini tasiyor.

2) Kendi olcumum (dokumana degil, calistirdigim koda dayali; venv, fastapi==0.141.1 — requirements.txt:2'de PINLI, yani ortam artefakti degil):
   - `app.routes` toplam 35 eleman, tipler: ['APIRoute', 'Route', '_IncludedRouter'] → router'lar duzlestirilmiyor.
   - ESKI yontem (app.routes): eleme ONCESI 1 yol (/api/health), BOS_DURUM_HARIC elemesinden SONRA 0 yol. Yani dongu govdesi HIC calismiyordu, `assert not hatalar` bos-listeyle gecti. Bulgunun "39'unu atliyordu" tespiti dogru, hatta gercek daha kotu (39/40 degil, fiilen 32/32).
   - OPENAPI yontemi: 32 parametresiz GET (bulgunun "40" sayisi yanlis — zorunlu query param'li uclari elemiyor; sayisal hata, esasi degistirmiyor).

3) Ayni kok neden BASKA bir kapiyi da korlestirmis: `git show HEAD:tests/test_cross_user_isolation.py:285` de ayni `for r in app.routes` dongusuyle ID'li uc izolasyon-kapsam kilidini turetiyor. Bu, bulguyu curutmuyor, guclendiriyor.

4) CURUTULEN KISIM — iddia edilen zarar: yeni kayit olmus bos kullaniciyla 32 ucun HEPSINI taradim; 32/32 → 200. Tek 200-disi yanitlar zorunlu query param eksikligi (422): /api/auth/verify-email, /api/debt-strategy/consolidation, /api/debt-strategy/opportunity-cost — dogru davranis. Duzeltilmis test dosyasi 8/8 gecti (`pytest tests/test_sifirdan_kullanici_e2e.py -q`). Yani "yeni kullanici 500 alip beyaz ekran gorur" zarari BUGUN DISKTE YOK; gercek zarar sahte-guvence + gelecekteki regresyonlarin yakalanmamasi.

5) Duzeltme durumu: working tree'de zaten uygulanmis ama COMMIT EDILMEMIS (`tests/endpoint_envanteri.py` untracked, MIN_PARAMETRESIZ_GET=25 taban assert'i ile). Commit'li HEAD'de kapi hala kor.

Baska katmanda kapali degil: middleware/dependency/migration/nginx hicbiri test kapsam-cokusunu yakalamaz; kapsam tabani assert'i (endpoint_envanteri.py) HEAD'de yok.
</details>

### D21 · [orta] Bir test global FastAPI `app` nesnesine kalici cokme ucu ekliyor — suit su an 2 testte kirmizi (test kirliligi)

- **Boyut:** test-kalitesi · **Yer:** `tests/test_error_tracking.py:42` · **Durum:** BUG #217 envanter filtresiyle KAPANDI (kök neden — testin global app'i kirletmesi — açık)
- **Neden yayın engeli / etki:** Kapsam kilitleri (BUG #217) OpenAPI'ye tasinip gorusunu kazanir kazanmaz, bir test dosyasinin global durumu kirletmesi yuzunden ANINDA kalici kirmiziya dustuler. `.githooks/pre-commit` tum suiti `-x` ile kosuyor ve `.github/workflows/ci.yml` da oyle → su an hicbir Python commit'i hook'tan gecemez. Pratik sonuc: gelistirici `--no-verify` aliskanligi edinir ve test kapisi tumden islevsizlesir (BUG #061 dersinin aynen tekrari). Ayrica bu kalip, testlerin uretim `app` nesnesini kalicilastirilmis sekilde degistirebildigini gosteriyor — yarin bir test dosyasi kimlik dogrulamayi devre disi birakan bir override birakirsa hicbir sey uyarmaz.

<details><summary>Kanıt</summary>

```
```python
@_test_router.get("/patla")
def _patla():
    raise RuntimeError("beklenmedik cokme")
...
app.include_router(_test_router)   # satir 42 — import-time, geri alinmiyor
```
`import app.main as main_mod; from app.main import app` (satir 21-22) ile PAYLASILAN global app'e yaziliyor; hicbir fixture bunu sokmuyor. Sonuc, calistirdigim tam suit:
```
$ ./venv/Scripts/python.exe -m pytest tests/ -q -rs
3 failed, 1605 passed, 6 skipped, 4 warnings in 141.22s
```
Iki basarisizligin izi dogrudan bu uca cikiyor:
```
tests\test_sifirdan_kullanici_e2e.py:100: r = client.get(yol, headers=yeni_kullanici)
...
    @_test_router.get("/patla")
    def _patla():
>       raise RuntimeError("beklenmedik cokme")
tests\test_error_tracking.py:34: RuntimeError
```
Ayni iz `test_bos_durum_frontend_fixture.py:129` icin de tekrarlaniyor.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

Diskten dogrulandi ve bagimsiz olarak yeniden uretildi. tests/test_error_tracking.py:42 gercekten modul-yukleme aninda `app.include_router(_test_router)` ile PAYLASILAN app.main.app nesnesine kalici bir /api/_test_hata/patla ucu ekliyor; include_in_schema=False yok, dolayisiyla uc app.openapi()["paths"] icinde gorunuyor ve tests/endpoint_envanteri.py'nin OpenAPI tabanli envanterine giriyor. Kendi kosturdugum tam suit: "2 failed, 1606 passed, 6 skipped in 142.06s" (bulgunun dedigi 3 degil, 2 — bu duzeltilmeli). Nedensellik kanitini bulgu kosmamis, ben kostum: iki dosya TEK BASINA yesil (10 passed), test_error_tracking.py ile birlikte toplanınca 2 failed — yani net cross-module global-state kirliligi, cikarim degil. Traceback tam olarak tests/test_error_tracking.py:34 RuntimeError'da bitiyor. .githooks/pre-commit gercekten `pytest tests/ -q -x` kosuyor, .github/workflows/ci.yml de `pytest tests/ -q` kosuyor → commit kapisi gercekten kirmiziya dusuyordu. DUZELTMELER: (1) Sayi 3 degil 2. (2) "Yarin bir test auth'u kapatan override birakirsa" kismi spekulasyon (KURAL 2 ihlali) — uretimde ETKI YOK: app/ altinda hicbir sey tests/ import etmiyor, grep ile _test_hata sadece tests/ icinde. Veri sizintisi/para kaybi/hukuki risk YOK; zarar yalnizca gelistirici test kapisiyla sinirli. (3) Denetim sirasinda durum degisti: paralel bir surec tests/endpoint_envanteri.py'yi duzenledi (satir 24-37, TEST_ENJEKSIYON_ONEKI="/api/_test" filtresi); duzenleme sonrasi ayni uc dosya "17 passed". Ancak kok neden (test_error_tracking.py:42) diskte AYNEN duruyor — git status onu degismis gostermiyor; duzeltme kaynakta degil tuketicide bir gecici cozum, yani OpenAPI okuyan yeni bir tarama ayni tuzaga tekrar dusebilir.
</details>

### D22 · [orta] Prod dialect'i PostgreSQL'in RLS ve dual-dialect kapilari ne yerelde ne CI'da hic kosuyor (6 skip'in 5'i)

- **Boyut:** test-kalitesi · **Yer:** `tests/pg_gate.py:49` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** ADR-038'e gore prod PostgreSQL. Workspace izolasyonunun ikinci savunma katmani oldugu belgelenen RLS'in gercekten calistigina dair otomatik hicbir kanit yok — Alembic RLS migration'i sessizce bozulsa (policy dusse, FORCE kalksa) hicbir test kirmizi olmaz. Ilk savunma (scope_filter) tek bir endpoint'te unutuldugunda (BUG #162 tam olarak boyle olmustu) ikinci savunmanin varliginin da dogrulanmamis olmasi, aile/workspace paylasimi acildiginda baska bir kullanicinin finansal tablosunun okunmasi demektir. Ayrica Numeric(19,4) bit-butunlugu ve NULL-siralama kapilarinin da hic kosmamasi, SQLite'ta dogru gorunen para hesaplarinin prod'da farkli davranmasi riskini test disi birakiyor.

<details><summary>Kanıt</summary>

```
Suit ciktisi:
```
SKIPPED [4] tests\pg_gate.py:49: PostgreSQL erisilemiyor (PG_TEST_URL veya yerel pgserver:5433 gerekli) - dual-dialect gate atlandi
SKIPPED [1] tests\test_rls_postgres.py:33: PostgreSQL erisilemiyor ...
```
`.github/workflows/ci.yml` icinde `services:` bloku, postgres imaji veya `PG_TEST_URL` env'i YOK — backend-tests job'i sadece `python -m pytest tests/ -q` kosuyor (satir 26-29). Yani bu 5 test hicbir otomatik ortamda calismiyor.
Tek RLS testi `tests/test_rls_postgres.py:33 test_rls_yanlis_workspace_sifir_satir` ve docstring'i sunu iddia ediyor: 'Kanit: RLS aktifken, uygulama filtresi (scope_filter) BYPASS edilse bile ... Postgres yanlis workspace satirini DONDURMEZ.' Bu 'kanit' hicbir zaman uretilmiyor.
PROJE.md ise RLS'i canli bir savunma olarak beyan ediyor: 'Row-Level Security (M51: 12 tabloda ENABLE+FORCE + ws_isolation policy, app-katmani scope_filter birincil + DB-katmani 2. savunma)'.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

Bulgu diskten dogrulandi, curutulemedi. (1) tests/pg_gate.py:45-50 skip mekanizmasi gercek; yerelde kosturdum: 5 skip (4x pg_gate.py:49 + 1x test_rls_postgres.py:33), iddia edilen ciktiyla birebir. (2) .github/workflows/ci.yml'de yalniz iki job var; backend-tests (satir 13-29) sadece SECRET_KEY ile "python -m pytest tests/ -q" kosuyor, services:/postgres imaji/PG_TEST_URL YOK; e2e job'i sqlite:///./data/ci.db kullaniyor. (3) .githooks/pre-commit de ciplak "pytest tests/ -q" kosuyor -> ayni skip. (4) grep -rn PG_TEST_URL yalniz tests/pg_gate.py ve scripts/pg_gate_run.py'yi buluyor; pg_gate_run.py ve scripts/prod_rehearsal.py hicbir workflow/hook tarafindan cagrilmiyor (elle scriptler). (5) SQLite tarafinda ikame kapi yok: "ROW LEVEL SECURITY|ws_isolation" grep'i yalnizca alembic/versions/f5a6b7c8d9e0_enable_rls_scoped_tables.py + docs'a dusuyor; tests/ icinde RLS gecen tek dosya test_rls_postgres.py. Yani policy dusse veya FORCE kalksa hicbir test kirmizi olmaz. (6) docs/kalite-seruveni/guvenlik-review-publish.md §4 (kabul edilen riskler) bu bosluğu YAZMIYOR; §5 kaniti "elle kosulmus pg_gate_run.py -> 13 passed" olarak veriyor, yani kural-6 muafiyeti gecerli degil.

SIDDET NEDEN "kritik/yuksek" DEGIL: scripts/pg_gate_run.py'yi bizzat kosturdum -> 15 passed, cikis kodu 0. RLS/Numeric/NULL-ordering/restore-drill kapilari BUGUN yesil; yani canli bir acik degil, regresyon-tespit boslugu. Ayrica birinci savunma (scope_filter) CI'da kosan otomatik AST kilidiyle korunuyor (tests/test_scope_enforcement.py; app/routers + rules_engine + goal_engine + debt_strategy + coach_insights taraniyor). Zarar iki ayri arizanin ust uste binmesini gerektiriyor.

SIDDET NEDEN "dusuk" DEGIL (ve bulguyu guclendiren ek disk kaniti): docker-compose.prod.yml:12 POSTGRES_USER: financialos, satir 46/77 uygulamayi postgresql://financialos:...@db:5432/financialos ile baglıyor. postgres:16-alpine'da bu kullanici bootstrap SUPERUSER'dir ve superuser FORCE'a ragmen RLS'i bypass eder. tests/test_rls_postgres.py:38-39 ise bilincli olarak non-superuser fos_app rolu yaratip yorumunda bunu "prod'daki financialos app-rolunu temsil eder" diye niteliyor — bu compose dosyasiyla celisiyor. Yani kapi CI'da kossa bile prod'un gercek rolunu test etmiyor olacakti. Coklu-uye workspace paylasimi da canli (app/routers/workspaces.py: /invite, /join). PROJE.md ve guvenlik-review'un RLS'i "canli 2. savunma" diye beyan etmesi ile otomasyondaki durum ortusmuyor.
</details>

### D23 · [orta] Koc, saglayici coktugunde haftalarca eski fiyatlari 'guncel' gibi sunuyor — yatirimda bayat isareti YOK (BUG #211'de doviz icin cozulen sorun fiyat tarafinda acik)

- **Boyut:** dayaniklilik · **Yer:** `app/coach.py:891` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** TEFAS/Is Yatirim/yfinance coktugunde saglayicilar sessizce None doner (router.py:51/71, fund_tracker.py:271-275, yfinance_client.py:34) ve fiyat guncellenmez. Koc bu durumda 30 gun onceki fiyatla hesaplanmis 'yatirim degerin X TL, %Y kardasin' cumlesini KOSULSUZ kurar. Kullanici bu rakama gore satis/alim karari verirse dogrudan para kaybeder. Projenin kendi ilkesi (BUG #211: 'bayat degeri suanki diye sunmak hic sunmamaktan daha kotudur') fiyat yolunda ihlal ediliyor; ayrica ADR-001 grounding vaadi (kocun her TL'si izlenebilir/dogru olmali) kirilir.

<details><summary>Kanıt</summary>

```
Bayatlik verisi (`is_stale`, `age_text`) YALNIZ HTTP cockpit yanitina, generate_cockpit'ten SONRA router'da eklenir (routers/cockpit.py:95 `cockpit['price_freshness'] = freshness`). Koc ise generate_cockpit'i DOGRUDAN cagirir (coach.py:859) -> bu alan koca hic ulasmaz. Hesap satiri fiyat yasini yazmaz: coach.py:891 `line += f" (lot {acc['lot']}, fiyat {acc.get('fiyat')}, ...)"`. Prompt'ta da uyari yok: `grep -n "fiyat" app/coach.py` -> yalniz 412 (tool tablosu) ve 891.

CALISTIRDIGIM KANIT (last_price_update = 30 GUN once olan TLY hesabi ile _build_context_message):
  price_freshness cockpit dict'te var mi?: False
  cockpit anahtarlari: [... 'investment_pnl', 'net_deger', 'yatirim_deger', ...]  (tazelik alani YOK)
  baglam metninde 'bayat': False / 'tazelik': False / 'gun once': False / 'stale': False
  SATIR: - id=1 [investment] TLY Fonu: 31.342,86 TL (lot 6.0, fiyat 5223.81, maliyet/lot 4000.0)

Karsit ornek ayni dosyada: doviz icin coach.py:833-838 bayat degeri 'SON BILINEN KUR (BAYAT: X once)' diye etiketler, taze degeri coach.py:845 'SU ANKI GUNCEL KUR' der. Ayni disiplin fiyat/portfoy tarafinda uygulanmamis.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

DISKTEN DOGRULANDI, curutulemedi. (1) app/coach.py:891 satiri iddia edildigi gibi fiyat yasini yazmiyor. (2) app/coach.py:859 generate_cockpit'i dogrudan cagiriyor; tazelik verisi YALNIZ HTTP katmaninda app/routers/cockpit.py:96'da (`cockpit["price_freshness"] = freshness`) ekleniyor -> koc yolunda hic yok. (3) `grep -rn "freshness|is_price_stale|get_price_age_text|fund_tracker" app/routers/coach.py app/coach.py app/grounding.py app/rules_engine.py` -> SIFIR eslesme; fund_tracker'i yalniz routers/cockpit.py:30 ve routers/fund_price.py:29 import ediyor. (4) rules_engine'de stale/bayat/last_price gecmiyor -> `## Uyarilar` blogu da bu riski tasimiyor. (5) V3_GOD_MODE_PROMPT'ta fiyat bayatligi uyarisi yok (yatirim/fiyat/fon/portfoy/guncel eslesen 11 satirin hicbiri tazelikle ilgili degil). (6) CALISTIRDIM: last_price_update=30 gun once olan TLY hesabiyla _build_context_message ciktisi -> "price_freshness cockpit'te var mi?: False", baglamda 'bayat'/'stale'/'gun once'/'eski fiyat' YOK, satirlar "- id=1 [investment] TLY Fonu: 31.342,86 TL (lot 6.0, fiyat 5223.81, ...)" ve "brut kar +7.342,86, getiri %+30,60" kosulsuz sunuluyor; ayni DB'de get_freshness_summary is_stale=True, age_text='30 gun once' donuyor. Yani veri VAR, koca ULASMIYOR. (7) Karsit-ornek gercek: coach.py:833-844 bayat kuru 'SON BILINEN KUR (BAYAT: X once)' etiketler ve 'su anki/guncel DEME' der; ayni disiplin fiyat yolunda yok. (8) Belgelenmis kabul-edilen-risk DEGIL: docs/kalite-seruveni/guvenlik-review-publish.md'de 'bayat|stale' gecmiyor. (9) Grounding kapatmiyor: bayat sayi da cockpit'e izlenebilir oldugu icin app/grounding.py'den gecer. SIDDET DUSURULDU (yuksek -> orta): bulgunun atladigi kismi telafi katmani var — frontend/src/panels/Cockpit.jsx:758-790 'Fiyat tazeligi' karti age_text + 'N eski' rozetini gosteriyor, yani kullanicida gorunur bir bayatlik sinyali baska yuzeyde mevcut; ayrica is_price_stale esigi 24 saat (fund_tracker.py:37) oldugundan normal hafta sonu/TEFAS yayin yapmayan gunler de 'stale' sayilir ve tarif edilen para kaybi icin haftalarca suren sessiz saglayici cokusu + kullanicinin paneldeki rozeti de kacirmasi gerekir. Gercek bir tavsiye-yolu defekti ve duzeltmesi ucuz (veri zaten hesaplaniyor), ancak veri sizintisi/hukuki risk seviyesinde sert yayin engeli degil.
</details>

### D24 · [orta] 5 cron isinden 3'u hicbir kayit tutmuyor — KVKK 90-gun saklama isi dahil sessizce olebilir

- **Boyut:** dayaniklilik · **Yer:** `app/scheduler.py:231` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** trace_cleanup patlarsa ReasoningTrace satirlari (kullanicinin finansal akil-yurutme icerigi) 90 gunu asarak birikmeye devam eder ve bunu KIMSE goremez — kullaniciya verilen KVKK saklama taahhudu sessizce ihlal edilir (hukuki risk). k2_batch olurse koc hafizasi bayatlar, kullanici bunu bilmez. 'Cron calisti mi?' sorusunun cevabi bu 3 is icin, ops ucu ve testler var olmasina ragmen, hala konteyner log'unu elle okumaktan ibaret.

<details><summary>Kanıt</summary>

```
`grep -n "_kayit_basla|_kayit_bitir" app/scheduler.py` ciktisi: yalnizca satir 217 (nightly_batch) ve 288 (fetch_investment_prices). Kayit TUTMAYAN isler: k2_batch_job (satir 231-242), nightly_trace_cleanup_job (satir 245-276), weekly_smoke_test_job (satir 317-337). Hepsi start_scheduler'da kayitli (satir 362-382).
Sonuc: /api/ops/scheduler bu 3 isi HIC listeleyemez — endpoint job adlarini SchedulerRun tablosundan turetiyor (app/routers/ops.py:46 `db.query(SchedulerRun.job_name).distinct()`).
nightly_trace_cleanup_job KVKK'da kullaniciya soz verilen saklama suresini uygulayan istir: docs/legal/kvkk-consent-v2.md:53-54 "Koc akil-yurutme kayitlari 90 gun sonra otomatik temizlenir" (kod: scheduler.py:259-264, 90 gun cutoff).
Ayrica bu gorunurluk sozlesmesi test dosyasinin kendi docstring'inde 'her calisma kaydedilir' diye yazili (tests/test_scheduler_visibility.py:9-10) ama hicbir test tum planlanmis islerin kayit tuttugunu dogrulamiyor (dosyanin tamami okundu).
Uc nokta frontend'de de tuketilmiyor: `grep -rn "/api/ops" frontend/src --include=*.jsx` -> 0 eslesme; yalniz scripts/live_gate.py:167-168 ve orada `zorunlu=False`.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

Diskten ve calistirarak dogrulandi. app/scheduler.py'de _kayit_basla/_kayit_bitir yalnizca nightly_batch_job (satir 217/224/227) ve fetch_investment_prices_job (288/308/312) icinde; k2_batch_job (231-242), nightly_trace_cleanup_job (245-276) ve weekly_smoke_test_job (317-337) hicbir SchedulerRun kaydi acmiyor, ama besi de start_scheduler'da planli. Ampirik kanit: in-memory SQLite + SessionLocal patch ile 4 isi calistirdim -> "KAYIT TUTAN ISLER: ['nightly_batch']"; ayri kosumda "PLANLI ISLER: ['fetch_investment_prices','k2_batch','nightly_batch','nightly_trace_cleanup','weekly_smoke_test']". /api/ops/scheduler is adlarini SchedulerRun.job_name distinct'inden turettigi icin (app/routers/ops.py:46) bu 3 isi hic listeleyemez. Baska katmanda kapali degil: APScheduler listener yok (grep add_listener|EVENT_JOB -> 0), is hatasi icin alarm/bildirim yok, docker-compose.prod.yml scheduler servisinde healthcheck yok ve restart:unless-stopped job istisnasinda konteyneri dusurmez, frontend /api/ops tuketmiyor (grep -> 0), scripts/live_gate.py:167-176 uc kontrolu de zorunlu=False ve "son calismalarda hata yok" kontrolu yalnizca tabloda VAR OLAN isleri gezdigi icin kayit tutmayan 3 ise yapisal olarak kor. tests/test_scheduler_visibility.py tamami okundu: helper/budama/ops-ucu/auth test ediliyor, planlanan tum islerin kayit tuttugunu dogrulayan test YOK (dosyanin kendi docstring'i satir 9-10 "her calisma kaydedilir" sozlesmesini yaziyor). KVKK taahhudu gercek: docs/legal/kvkk-consent-v2.md:53-54 "Koc akil-yurutme kayitlari 90 gun sonra otomatik temizlenir" ve bunu uygulayan tek kod yolu nightly_trace_cleanup_job (90 gun cutoff, 259-264); ReasoningTrace icin baska retention yolu yok (yalniz coach.py:2854 kullanici-silme cascade). guvenlik-review-publish.md'de bu risk kabul-edilmis-risk olarak yazili degil. SIDDET DUZELTMESI: bulgunun tarifi dogru ama zarar dolayli — temizlik kodu calisiyor, zarar icin isin ayrica patlamasi gerekiyor; veri sizintisi/para kaybi yok ve hata yine de log'a (logger.exception + APScheduler ERROR) dusuyor. Bu nedenle kritik/yuksek degil, orta: yayin sonrasi KVKK saklama taahhudunun ve koc hafiza tazeliginin dogrulanabilir/izlenebilir kaniti yok, "cron calisti mi?" sorusu bu 3 is icin hala elle log okumaya bagli.
</details>

### D25 · [orta] Fallback zincirinde aktif iki LLM sağlayıcısı (Together AI, DeepInfra) veri-işleyen envanterinde ve KVKK metninde hiç yok

- **Boyut:** hukuki-gizlilik · **Yer:** `app/coach.py:2098` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** KVKK m.10 aydınlatma, kişisel verinin aktarılacağı alıcı gruplarının bildirilmesini zorunlu kılar; m.9 yurt dışı aktarımda alıcının açıkça bilinmesini gerektirir. Kullanıcı, finansal verisinin Together AI ve DeepInfra'ya gittiğini hiçbir belgede göremiyor — rıza kapsam dışı bir aktarım gerçekleşiyor. Operatör bir gün TOGETHER_API_KEY tanımlarsa (env örneği bunu davet ediyor) tüm beta kullanıcılarının bakiyeleri ve işlem açıklamaları beyan edilmemiş bir ABD şirketine akar; test bunu asla yakalamaz.

<details><summary>Kanıt</summary>

```
app/coach.py:2096-2099 (LLM_PROVIDER=fallback zinciri):
```
# M13/ADR-034 revize sırası: Gemini → OpenRouter → Cerebras → Together → DeepInfra → Groq → Ollama
for builder in [_build_gemini, _build_openrouter, _build_cerebras,
                _build_together, _build_deepinfra, _build_groq, _build_ollama]:
```
app/coach.py:1777 `BASE_URL = "https://api.together.xyz/v1"`, :1788 `BASE_URL = "https://api.deepinfra.com/v1/openai"`; anahtarlar desteklenen konfigürasyon: .env.example:64 `TOGETHER_API_KEY=`, :66 `DEEPINFRA_API_KEY=`.

docs/legal/veri-isleyen-envanteri.md:9-15 tablosu YALNIZCA: Google Gemini, Groq/Cerebras, OpenRouter, Anthropic, Ollama. Together/DeepInfra YOK. Aynı dosya satır 4-5: "Kullanıcı verisine dokunabilen **her** üçüncü taraf burada listelenir. Yeni bir sağlayıcı eklendiğinde bu dosya ve KVKK metni **aynı commit'te** güncellenir."

Güvence olduğu iddia edilen test (tests/test_legal_docs.py:79-81) 4 ismi SABİT kodluyor, kod tarafını hiç okumuyor:
```
for saglayici in ("gemini", "groq", "anthropic", "ollama"):
    assert saglayici in envanter
```
Yani "envanter kodla kilitlenir" (dosya docstring'i, satır 12) iddiası yanlış — yeni sağlayıcı eklendiğinde test yeşil kalır.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

Bulgu diskten dogrulandi, ancak siddet abartilmis. DOGRULANANLAR: (1) app/coach.py:2096-2098 fallback zinciri gercekten _build_together ve _build_deepinfra iceriyor; :1774-1793 TogetherProvider (api.together.xyz) ve DeepInfraProvider (api.deepinfra.com) tanimli. (2) Calistirilan kanit (venv python ile coach.LLMProvider.__subclasses__() vs docs/legal/veri-isleyen-envanteri.md): Anthropic/Gemini/Groq/Cerebras/OpenRouter/Ollama -> envanterde True; Together -> False, DeepInfra -> False. (3) tests/test_legal_docs.py:79-81 yalnizca ("gemini","groq","anthropic","ollama") sabitlerini ariyor, app.coach'u hic import etmiyor; `pytest tests/test_legal_docs.py -q` -> 11 passed (iki saglayici envanterde YOKKEN yesil). Yani hem test dosyasinin docstring iddiasi (satir 12) hem envanterin kendi iddiasi (satir 53-54) "kodla kilitlenir" YANLIS — calistirarak kanitlandi. (4) Kronoloji bulguyu guclendiriyor: git log -S TogetherProvider -> a160466 (2026-07-13) saglayicilar eklendi; envanter dosyasi 5583cba (2026-08-05) yani 3 hafta SONRA yazildi -> bayat dokuman degil, taze bir eksiklik. (5) Kabul-edilen-risk degil: docs/kalite-seruveni/guvenlik-review-publish.md §4'te LLM saglayici/envanter maddesi yok (grep llm|provider|saglayic|envanter -> sifir). (6) Baska katmanda kapali degil: app/ icinde coach.py disinda TOGETHER/DEEPINFRA gecmiyor, prod whitelist/fail-fast yok; aktivasyon salt os.getenv anahtar varligina bagli (coach.py:2037-2048). CURUTULEN/YUMUSATILAN KISIMLAR: (a) Bugun fiili bir aktarim YOK — .env icinde TOGETHER_API_KEY/DEEPINFRA_API_KEY yok (LLM_PROVIDER=fallback ama anahtarsiz builder None doner) ve .env.prod.example:28-31 yalnizca GEMINI/GROQ/OPENROUTER listeliyor; "prod ornegi davet ediyor" iddiasi yanlis, davet eden yalnizca dev .env.example:64-67. (b) KVKK v2 §4 (docs/legal/kvkk-consent-v2.md:34-37) yurt disi aktarimi KATEGORI olarak beyan ediyor ve isim listesi icin envantere atif yapiyor — alici GRUBU beyan edilmis, grup icindeki iki isim eksik. Bu yuzden aktif veri sizintisi/hukuki ihlal degil, latent (tek env degiskeni uzakta) bir eksiklik + yanlis guvence veren kirik test kapisi. Siddet: orta.
</details>

### D26 · [orta] KVKK veri export'u kullanıcının bcrypt şifre hash'ini ve OAuth subject id'sini dosyaya döküyor

- **Boyut:** hukuki-gizlilik · **Yer:** `app/routers/user.py:167` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** KVKK taşınabilirlik export'u tasarımı gereği kullanıcının cihazına inen, e-postayla paylaşılan, yedek diske/buluta atılan bir dosyadır. İçindeki bcrypt hash çevrimdışı kırılabilir (zayıf/tekrar kullanılan şifrelerde saatler); hash sızan kullanıcı hem FinancialOS hesabını hem şifresini tekrar kullandığı banka/e-posta hesabını kaybeder. `oauth_sub` ise Google kimliğinin kalıcı tekil id'sidir ve profil eşleştirmeye yarar. Kimlik doğrulama sırrı, veri taşınabilirliği hakkının kapsamında değildir — sektörde (GDPR/DSAR uygulamaları) kimlik bilgisi export'tan çıkarılır.

<details><summary>Kanıt</summary>

```
KOMUT: TestClient ile iki export ucu da çağrıldı (kullanıcı: password_hash='$2b$12$ORNEKHASH...', oauth_sub='1187766554433'):
```
== /api/user/export 200
   user bloğu: {"id": 1, "name": "Ali", "email": "ali@example.com",
     "password_hash": "$2b$12$ORNEKHASHDEGERIABCDEFGHIJKLMNOP",
     "oauth_provider": "google", "oauth_sub": "1187766554433",
     ... "token_version": 0 ...}
== /api/users/me/export 200
   user bloğu: {... "password_hash": "$2b$12$ORNEKHASHDEGERIABCDEFGHIJKLMNOP" ... "oauth_sub": "1187766554433" ...}
```
Kök neden — hiçbir alan kara listesi yok:
app/routers/user.py:46-47 `def _row_to_dict(row): return {c.name: _json_val(getattr(row, c.name)) for c in row.__table__.columns}` → :167 `"user": _row_to_dict(user)`
app/serializers.py:44-60 `_row(obj)` da aynı şekilde `mapper.column_attrs` üzerinden TÜM kolonları basıyor → :64 `"user": _row(user)`
UI bu dosyayı indirtiyor: frontend/src/api.js:538 `exportData: () => request('/api/users/me/export')`.
Bu, kabul-edilen-riskler listesinde (docs/kalite-seruveni/guvenlik-review-publish.md §4) YOK.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

Bulgu diskten ve calisma zamanindan dogrulandi; curutulemedi.

KOD (aynen iddia edildigi gibi):
- app/routers/user.py:46-47 `_row_to_dict(row) -> {c.name: _json_val(getattr(row, c.name)) for c in row.__table__.columns}` — hicbir alan kara listesi yok; :167 `"user": _row_to_dict(user)`.
- app/serializers.py:46-60 `_row(obj)` da `mapper.column_attrs` uzerinden TUM kolonlari basiyor; :64 `"user": _row(user)`; app/routers/auth.py:627-631 `@users_router.get("/me/export")` bunu cagiriyor.
- app/models.py:136/138/146 — `password_hash`, `oauth_sub`, `token_version` gercek User kolonlari.

CALISTIRILAN KANIT (venv python + TestClient, scratchpad probe; her iki uc da 200):
== /api/user/export 200
   password_hash present: True -> '$2b$12$ORNEKHASHDEGERIABCDEFGHIJKLMNOP'
   oauth_sub present: True -> '1187766554433'
   token_version present: True
== /api/users/me/export 200
   password_hash present: True -> '$2b$12$ORNEKHASHDEGERIABCDEFGHIJKLMNOP'
   oauth_sub present: True -> '1187766554433'
Donen user anahtarlari: created_at, currency, email, email_verified_at, id, is_active, kvkk_consent_at, kvkk_consent_version, locale, name, oauth_provider, oauth_sub, password_hash, timezone, token_version.

CURUTME DENEMELERI (hepsi basarisiz):
- app/main.py icinde redact/scrub/sanitize/exclude veya password_hash/oauth_sub filtresi YOK (grep bos dondu) — yanit-filtreleyen middleware yok.
- docs/kalite-seruveni/guvenlik-review-publish.md icinde bu risk kabul-edilen-risk olarak YAZILI DEGIL (yalniz alakasiz bir path-traversal satiri "export" kelimesini geciriyor).
- tests/ icinde export'ta kimlik alanlarinin BULUNMAMASINI dogrulayan tek bir test yok (tests/test_data_export.py yalnizca tamlik/serilesme kontrol ediyor; password_hash/oauth_sub grep'i sadece auth testlerinde, export baglaminda degil).
- UI zinciri de dogrulandi: frontend/src/api.js:538 `exportData: () => request('/api/users/me/export')` → frontend/src/panels/Hesap.jsx:79-82 yaniti Blob'a yazip dosya olarak indirtiyor, yani hash gercekten kullanicinin diskine inen dosyaya giriyor.

IDDIADA DUZELTME (siddeti dusuren tek nokta): export `get_current_user` ile CAGIRANIN KENDI kaydina kapsamli — kullanici baskasinin hash'ini goremiyor, kendi hash'ini aliyor. Yani uzaktan hesap ele gecirme veya capraz-kullanici sizintisi DEGIL. Zarar, kimlik dogrulama sirrinin tasarimca paylasilan/yedeklenen/e-postayla gonderilen bir dosyaya kalici olarak yazilmasi: o dosya sizarsa saldirgan bcrypt hash'i cevrimdisi kirabilir (zayif/tekrar kullanilan sifrede) ve oauth_sub ile Google kimligini eslestirebilir. Bu bir yukselteci/ikincil-sizinti riski, birincil acik degil. Ayrica bcrypt cost 12 kirmayi pahalilastiriyor. Bu yuzden kritik/yuksek degil, ORTA.

Neden yine de yayin engeli: KVKK/GDPR tasinabilirlik hakkinin kapsami kimlik dogrulama sirlarini icermez (DSAR uygulamalarinda kimlik bilgisi export'tan cikarilir); sifir fayda karsiligi kalici kimlik-bilgisi maruziyeti uretiliyor ve duzeltme iki fonksiyona kara liste eklemekten ibaret.
</details>

### D27 · [orta] Hesap silme sonrası kullanıcının e-posta adresi beta_invites tablosunda kalıyor — 'unutulma hakkı' tam değil

- **Boyut:** hukuki-gizlilik · **Yer:** `app/kvkk.py:43` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** Silme talebinden sonra kullanıcının e-posta adresi + operatörün kişi hakkındaki serbest notu ("Ali - iş arkadaşı" gibi ilişki bilgisi) veritabanında süresiz kalıyor; bu, rıza metninde 'tüm veriniz silinir' diye verilen taahhüdün ihlalidir ve KVKK m.7 kapsamında Kurum'a şikâyet edilebilir. Pratik zarar: silinen kullanıcı hâlâ tanımlanabilir durumda, olası bir DB sızıntısında 'hesabını silmiş' kişiler de e-postasıyla ifşa olur.

<details><summary>Kanıt</summary>

```
KOMUT: purge_user_data() canlı probe (in-memory SQLite, PRAGMA foreign_keys=ON). Kullanıcı ali@example.com bir davet kodu kullanmış ve DELETE /api/users/me akışı koşuldu:
```
purge sonucu: {'transactions': 1, 'workspace_memberships': 1, 'goals': 1, 'accounts': 1,
               'coach_memories': 1, 'api_call_log': 1, 'workspaces': 1, 'users': 1}

KALAN SATIRLAR (silme sonrasi):
  beta_invites: before=1 after=1
  error_logs:   before=1 after=1
  revoked_tokens: before=1 after=1

beta_invites icerik: [('ABC', 'ali@example.com', 'Ali - is arkadasi', 1)]
error_logs icerik:   [('...', last_user_id=1)]
```
Kök neden: app/kvkk.py:43-49 yalnızca `"user_id" in table.c` olan tabloları siliyor; `beta_invites` kolonu `used_by_user_id` (app/models.py:1011) olduğu için hiç dokunulmuyor. Aynı şekilde `email` (models.py:1007) ve operatör notu ("Ali - is arkadasi", models.py:1008) kalıyor.
Mevcut test (tests/test_account_deletion_kvkk.py:100-112) yalnız 9 modeli kontrol ettiği için bunu görmüyor.
KVKK metni v2:45-47 taahhüt: "DELETE /api/users/me — hesabınız ve tüm veriniz kalıcı olarak silinir".
```
</details>

<details><summary>Çelişme turu hükmü</summary>

DISKTEN DOGRULANDI, curutulemedi. (1) Kod: app/kvkk.py:46 yalnizca `if "user_id" in table.c` olan tablolari siliyor; beta_invites kolonu `used_by_user_id` (app/models.py:1011), ayrica `email` (1007) ve operator notu `note` (1008) tasiyor — ikinci dongu de yalniz `workspace_id`'ye bakiyor, beta_invites her iki filtreye de takilmiyor. (2) Kendi kosturdugum probe (in-memory SQLite, PRAGMA foreign_keys=ON, DELETE /api/users/me akisinin birebir taklidi: purge_user_data(delete_user_row=False) + db.delete(user) + commit): "users after: 0" iken "AFTER beta_invites: [('lCTS...', 'ali@example.com', 'Ali - is arkadasi', 1)]". Sema taramasi: user_id'siz ama kullanici-referansli tablolar = beta_invites['used_by_user_id','email'], error_logs['last_user_id']. (3) Baska katman kapatmiyor: beta_invites'a dokunan tum kod app/beta_access.py (olustur/dogrula/kullan) ve scripts/beta_invite.py (operator CLI); hicbirinde silme/anonimlestirme yok. Migration/constraint/middleware yolu da yok. (4) Prod'da kacinilmaz: beta_access.registration_mode() production varsayilani invite_only, register akisi davet_kullan(db, davet, user.id) cagiriyor (app/routers/auth.py:182) — her beta kullanicisinin satiri var. (5) Taahhut gercek ve canlida sunuluyor: docs/legal/kvkk-consent-v2.md §5 "hesabiniz ve tum veriniz kalici olarak silinir (cascade, geri alinamaz)"; app/routers/legal.py bu metni /api/legal/kvkk ile yayinliyor. (6) Belgelenmis kabul-edilen-risk DEGIL: docs/kalite-seruveni/guvenlik-review-publish.md §4 sadece e-posta enumerasyonu, prompt injection ve localStorage token'i sayiyor. (7) Mevcut test gercekten kor: tests/test_account_deletion_kvkk.py:100-112 sabit 9 model + Workspace kontrol ediyor, sema-genel tarama yok. ZAYIF YAN IDDIA: revoked_tokens PII tasimiyor (app/models.py:1083-1088 yalniz jti/tarih), error_logs.last_user_id sadece tamsayi — bulgunun bu kismi anlamsiz; ama govdesi (e-posta + operator serbest notu) ayakta. SIDDET "orta": caprak-kullanici sizintisi, para kaybi, kimlik-dogrulamasiz erisim yok; etki kullanici basina tek satir ve operatorun zaten sahip oldugu bir adres. Buna karsilik canlida sunulan yazili KVKK taahhudu fiilen yanlis — silme hakkini kullanan kisi DB'de e-postasi + iliski notuyla tanimlanabilir kaliyor (m.7 uyumsuzlugu, olasi DB sizintisinda "hesabini silmis" kisiler de ifsa olur). Kritik/yuksek degil cunku istismar edilebilir bir guvenlik acigi degil ve duzeltmesi tek noktada (purge_user_data'ya beta_invites anonimlestirme + sema-genel regresyon testi).
</details>

### D28 · [orta] KVKK metninin ve arayüzün kullandığı export ucu iki tabloyu atlıyor; tamlık testi yanlış ucu koruyor

- **Boyut:** hukuki-gizlilik · **Yer:** `app/serializers.py:63` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** KVKK m.11 taşınabilirlik hakkı 'tüm veri' taahhüdüyle ilan edilmiş; kullanıcı indirdiği dosyanın eksik olduğunu bilmiyor. Hesabını silip başka bir araca geçen kullanıcı hedef katkı/çekim geçmişini (goal_allocations) ve otomatik tahsis kurallarını kalıcı olarak kaybeder — geri alınamaz veri kaybı, üstelik 'yedeğini al, sonra sil' diye yönlendirilen beta akışının (kvkk-consent-v2.md:65) tam ortasında. Testin yanlış ucu koruması, ileride eklenecek her yeni tablonun da sessizce dışarıda kalacağı anlamına gelir.

<details><summary>Kanıt</summary>

```
KOMUT: hedefi + hedef kuralı + tahsisi olan kullanıcı için iki uç karşılaştırıldı:
```
UI'nin kullandigi /api/users/me/export anahtarlari: ['accounts','action_history','api_calls',
 'checkpoints','debts','decision_journal_entries','demo_markers','envelopes','expenses',
 'exported_at','feedback_items','goals','incomes','insights','memories','net_worth_snapshots',
 'owned_workspaces','pending_actions','reasoning_traces','transactions','user',
 'wishlist_items','workspace_memberships']
goal_allocations var mi (me): False | goal_rules var mi: False
full export goal_allocations: [{'id':1,'goal_id':1,'transaction_id':1,'amount':5.0,'source':'rule','rule_id':1,...}] | goal_rules adet: 1
```
Kök neden: app/serializers.py:68 export'u `mapper.relationships` üzerinden kuruyor; GoalAllocation/GoalRule'da `user_id` YOK (models.py:857, 962) ve User'da ilişkileri yok → hiç dökülmüyor.
Bu uç hukuki metinde ve arayüzde birincil yol: docs/legal/kvkk-consent-v2.md:43 "GET /api/users/me/export ile **tüm** verinizi tek JSON dosyasında indirin"; frontend/src/api.js:538 `exportData: () => request('/api/users/me/export')`.
Tamlık invariant testi ise DİĞER ucu koruyor: tests/test_data_export.py:80-98 `from app.routers.user import export_data as _fn` — yani yeşil test yanlış fonksiyonu doğruluyor (kapsam yanılsaması).
```
</details>

<details><summary>Çelişme turu hükmü</summary>

CURUTULEMEDI — diskten ve calistirilarak dogrulandi.

1) KOK NEDEN KODDA AYNEN OYLE. app/serializers.py:39-78 `export_user_data` govdesi export'u SADECE `_sa_inspect(user).mapper.relationships` uzerinden kuruyor (satir 67). app/models.py:852-878 (GoalRule) ve 938-966 (GoalAllocation) siniflarinda `user_id` sutunu YOK ve User'da bu iki modele iliski tanimi yok — yalniz `goal = relationship("Goal", ...)` var. Yani tek-seviye iliski yuruyusu bu iki tabloya hic ulasmiyor.

2) CALISTIRILAN KANIT (in-memory SQLite + TestClient, hedef + hedef kurali + tahsis olan kullanici):
   me status: 200 | full status: 200
   /api/users/me/export anahtarlari: ['accounts','action_history','api_calls','checkpoints','debts','decision_journal_entries','demo_markers','envelopes','expenses','exported_at','feedback_items','goals','incomes','insights','memories','net_worth_snapshots','owned_workspaces','pending_actions','reasoning_traces','transactions','user','wishlist_items','workspace_memberships']
   goal_allocations in me: False | goal_rules in me: False
   /api/user/export goal_allocations: [{'id':1,'goal_id':1,'transaction_id':1,'amount':5.0,'source':'rule','rule_id':1,...}] | goal_rules adet: 1
   Iki uc arasindaki diger tum farklar sadece ANAHTAR ADI takma-adi (api_call_log<->api_calls, coach_memory<->memories, personal_debts<->debts, master_checkpoints<->checkpoints, recurring_incomes<->incomes, recurring_expenses<->expenses, coach_insights<->insights, decision_journal<->decision_journal_entries, demo_data_markers<->demo_markers, feedback<->feedback_items, workspaces<->owned_workspaces) — gercekten EKSIK olan tam olarak iki tablo: goal_allocations, goal_rules (+ metadata 'schema' alani).

3) BAGIMSIZ INVARIANT TEKRARI: User iliskilerinin hedef tablolarini cikarip user_id/goal_id tasiyan tum modellerle karsilastirdim:
   "me-export'ta dusmeyen user-data tablolari: [('goal_rules','GoalRule'), ('goal_allocations','GoalAllocation')]" — tam olarak iddia edilen iki tablo.

4) BASKA KATMAN KAPATMIYOR. Bu uc app/routers/auth.py:627-631'de dogrudan `export_user_data(user, db)` donduruyor; araya middleware/dependency zenginlestirmesi yok. Alternatif TAM uc app/routers/user.py:143-198'de var (goal_allocations/goal_rules'i `dump_by_goal` ile goal_id join'i uzerinden dokuyor, satir 156-162, 174-175) ama arayuz onu KULLANMIYOR: frontend/src/api.js:538 `exportData: () => request('/api/users/me/export')` ve frontend/src/panels/Hesap.jsx:79 `const veri = await authApi.exportData();` (indir butonu). Hukuki metin de ayni ucu isaret ediyor: docs/legal/kvkk-consent-v2.md:43 "GET /api/users/me/export ile **tüm** verinizi tek JSON dosyasında indirin" (v1.md:34 de ayni).

5) TESTIN YANLIS UCU KORUDUGU DOGRU. tests/test_data_export.py:80-98 `test_export_tamlik_invariant` icinde satir 87: `from app.routers.user import export_data as _fn` + `inspect.getsource(_fn)` — yani invariant, arayuzun kullanmadigi ucun KAYNAK METNINDE sinif adi ariyor. /me/export ucunu kapsayan tek test tests/auth/test_auth.py:176-182, o da yalnizca status 200 + user.email + 'exported_at' varligini kontrol ediyor; tamlik dogrulamasi yok. Yani yesil suit, KVKK-yuzlu uc icin kapsam yanilsamasi uretiyor.

6) BELGELENMIS KABUL-EDILEN-RISK DEGIL. docs/kalite-seruveni/guvenlik-review-publish.md icinde export'a dair tek satir 58 ("Path traversal: dosya tabanli export/import ozelligi yok; tum export saf JSON") — bu bulguyla ilgisiz, gerekceli bir kabul yok.

SIDDET GEREKCESI (orta): Zarar gercek ve geri alinamaz — hesabini silip tasinan kullanici hedef-tahsis gecmisini (hangi islem hangi hedefe ne kadar katki verdi) ve otomatik tahsis kurallarini kaybeder; ustelik kvkk-consent-v2.md §8 kullaniciyi acikca "kendi yedegini disa aktarma ozelligiyle al" diye yonlendiriyor, DELETE /api/users/me ise cascade ve geri alinamaz. Hukuki metin "tum verinizi" taahhut ederken uc eksik donuyor (KVKK m.11 tasinabilirlik). Yine de kritik/yuksek degil: veri sizintisi, yetkisiz erisim veya para kaybi yok; hesaplar, islemler
</details>

### D29 · [orta] Hata/log maskelemesi TCKN, telefon, bcrypt hash ve opak token'ları kaçırıyor; global hata yakalayıcı ham traceback'i maskesiz log dosyasına yazıyor

- **Boyut:** hukuki-gizlilik · **Yer:** `app/error_tracking.py:30` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** Modülün kendi docstring'i (satır 14-15) 'PII/sır temizliği zorunlu' diyerek bir güvence veriyor; gerçekte TCKN/telefon/IBAN/şifre hash'i bu ağdan geçiyor ve dosya log'una zaten maskesiz düşüyor. Sunucu log'u operatörün, yedek alan sistemlerin ve olası bir log toplama zincirinin görebildiği bir yüzeydir; KVKK m.12 veri minimizasyonu ve güvenlik yükümlülüğü karşılanmıyor. Somut zarar: bir üretim hatası anında kullanıcının adı + şifre hash'i log dosyasına yazılır, log yedeği sızarsa hesap ele geçirme riskine dönüşür.

<details><summary>Kanıt</summary>

```
KOMUT: app.error_tracking.temizle() 12 gerçekçi örnekle koşuldu (girdi → çıktı):
```
"TCKN 12345678901 gecersiz"            → "TCKN 12345678901 gecersiz"           (MASKELENMEDI)
"telefon 05321234567 kayitli"          → "telefon 05321234567 kayitli"         (MASKELENMEDI)
"IBAN TR330006100519786457841326"      → "IBAN TR330006100519786457841326"     (MASKELENMEDI - bosluksuz IBAN)
"Authorization: Bearer abc123XYZopaquetoken-9f8a7b6c5d4e3f2a1b" → aynen kaldi (JWT olmayan opak token)
"PASSWORD 'Sifre123!' gecersiz"        → "PASSWORD 'Sifre123!' gecersiz"       (tirnakli deger, '=' yok)
SQLAlchemy IntegrityError ornegi       → "...[parameters: ('Ali Veli', '<eposta>', '$2b$12$KIXQK0dQ9lJ0Zp1mQzMOne')]"
                                          (e-posta maskelendi; AD ve bcrypt HASH kaldi)
```
Desenler: app/error_tracking.py:30-37 — yalnız e-posta, `eyJ` ile başlayan JWT, 13-24 haneli sayı dizisi, `ad=deger` biçimli sır.
İkinci boşluk: app/main.py:237 `logger.exception("Beklenmedik hata: %s %s", request.method, request.url.path)` — `exc_info` ile ham istisna metni (yukarıdaki `[parameters: (...)]` dahil) `logs/financialos.log` dosyasına MASKELENMEDEN yazılıyor; `temizle()` yalnızca DB kaydına (error_tracking.kaydet:83-87) uygulanıyor. Ayrıca app/coach.py:2592 `logger.info(f"save_insight: [{result.dedup_key}] {result.content[:60]}")` kullanıcının finansal içgörü metnini log'a düşürüyor (BUG #180'in ham finansal metin loglamama ilkesiyle çelişiyor).
```
</details>

<details><summary>Çelişme turu hükmü</summary>

BULGU AYAKTA KALDI — curutulemedi, diskten uctan uca dogrulandi.

KOD OKUMASI (dogrulandi):
- app/error_tracking.py:30-37 — _MASKELER yalniz 4 desen: e-posta, `eyJ` ile baslayan JWT, \b ile sinirli 13-24 haneli sayi dizisi, `ad=deger` bicimli sir. Bulgunun tarifi birebir dogru.
- app/main.py:237 — `logger.exception("Beklenmedik hata: %s %s", request.method, request.url.path)`, exc_info ile. `temizle()` YALNIZ kaydet() icinde DB satirina uygulaniyor (error_tracking.py:84 message, :87 traceback_tail). Log cagrisina hic uygulanmiyor.
- app/logging_config.py — hicbir logging.Filter YOK (grep: Filter/addFilter eslesmesi yok). JsonFormatter.format satir 28-29 `payload["exc"] = self.formatException(record.exc_info)` ile ham traceback'i dosyaya yaziyor. Maskeleme yapan ikinci katman MEVCUT DEGIL.
- app/database.py:58 — create_engine(..., **_engine_kwargs); _engine_kwargs icinde `hide_parameters=True` YOK → SQLAlchemy istisna metinleri bound parameter'lari tasiyor.
- app/main.py:70-71 — setup_logging() modul seviyesinde cagriliyor, RotatingFileHandler logs/financialos.log aktif.

KOMUT 1 — temizle() dogrudan kosuldu (PYTHONPATH=. venv python):
  'TCKN 12345678901 gecersiz'                    -> DEGISMEDI
  'telefon 05321234567 kayitli'                  -> DEGISMEDI
  'IBAN TR330006100519786457841326'              -> DEGISMEDI
  'refresh_token cookie: abc123XYZopaquetoken-9f8a7b6c5d4e3f2a1b' -> DEGISMEDI
  "PASSWORD 'Sifre123!' gecersiz"                -> DEGISMEDI
  IntegrityError ornegi -> e-posta '<eposta>' oldu; 'Ali Veli' ve '$2b$12$KIXQK0dQ9lJ0Zp1mQzMOne' KALDI
Kok neden: 13-24 hane kurali 11 haneli TCKN/telefonu kacirmakta; \b sinir kurali 'TR33...' bosluksuz IBAN'da harf-oncesi rakamda eslesmiyor.

KOMUT 2 — uctan uca log kaniti (scratchpad/logprobe.py, ENVIRONMENT=production, LOG_DIR=temp):
main.py:237 ile AYNI cagri sekli kullanildi; logs/financialos.log icerigi kontrol edildi:
  bcrypt hash MASKESIZ -> True
  ad-soyad    MASKESIZ -> True
  e-posta     MASKESIZ -> True
  TCKN        MASKESIZ -> True
  telefon     MASKESIZ -> True
Bu, bulgunun iddiasindan DAHA GUCLU: temizle()'nin DB icin YAKALADIGI e-posta bile dosya log'una maskesiz dusuyor. Bu, projenin kendi kapattigini soyledigi BUG #180 ("tam e-posta ... log'da (KVKK)", guvenlik-review-publish.md:34) ilkesiyle dogrudan celisiyor.

GERCEKCI TETIKLEME YOLU: app/models.py:135-136 — email unique constraint + password_hash saklaniyor, name ile ayni INSERT'te. Mukerrer e-posta ile kayit IntegrityError uretir; `[parameters: ('Ali Veli', 'ali@example.com', '$2b$12$...')]` aynen log dosyasina yazilir.

KABUL-EDILEN-RISK DEGIL: docs/kalite-seruveni/guvenlik-review-publish.md §4 yalniz 3 madde sayiyor (e-posta enumerasyonu, depolanmis metin prompt injection, localStorage token). Log maskeleme YOK. Mevcut test tests/test_error_tracking.py:112-116 sadece calisan 4 deseni dogruluyor; bosluklari koruyan test yok.

SIDDET NEDEN 'yuksek' DEGIL 'orta' (durustce indirildi):
1. Uygulama semasinda TCKN/telefon kolonu YOK (grep app/models.py: eslesme yok). Bu degerler ancak serbest metin alanlarindan (notes/description/content) gelebilir → bulgunun o kismi kismen varsayimsal.
2. Log dosyasi DB ile ayni host/disk uzerinde; DB zaten ayni e-posta ve bcrypt hash'i tutuyor. Log'a dosya erisimi olan aktorun buyuk olcude DB'ye de erisimi var → marjinal ek ifsa.
3. Uzaktan somurulebilir degil, hesap-ele-gecirme sinifi degil.
Gercek ek risk yuzeyi log'a ozgu kanallar: rotasyon yedekleri, log toplama zinciri, hata ayiklama sirasinda log paylasimi. KVKK m.12 veri minimizasyonu acisindan gercek bir defekt ve modul docstring'inin (satir 14-15) verdigi "PII/sir temizligi zorunlu" guvencesi log yolu icin YANLIS — ancak sert yayin engeli degil, acik betaya once kapatilmasi gereken bir borc.
</details>

### D30 · [orta] SUPPORT_EMAIL placeholder'i ('destek@<alan-adin>') hem fail-fast'i hem live_gate kapisini geciyor — sahte destek adresi kullanicilara yayinlanir

- **Boyut:** operasyon-deploy · **Yer:** `app/settings.py:84` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** BUG #210'un kapatmaya calistigi zarar aynen geri gelir: giris yapamayan (yanlis sifre, dogrulanmamis e-posta, calismayan davet kodu) kullanici uygulama-ici geri bildirim widget'ina da ulasamaz; giris ekraninda ve /api/meta'da gosterilen tek kanal teslim edilemeyen bir adres olur. Kullanici sessizce kaybedilir ve KVKK'nin 'veri sorumlusuna basvuru' hakki fiilen kullanilamaz hale gelir — bunun uzerine iki bagimsiz otomatik kapi da 'gecti' der.

<details><summary>Kanıt</summary>

```
.env.prod.example:64
    SUPPORT_EMAIL=destek@<alan-adin>   # ZORUNLU (BUG #210): tanimsizsa uygulama BASLAMAZ.

app/settings.py:84-89 (support_problems) yalnizca bos mu ve '@' iceriyor mu diye bakiyor; SECRET_KEY icin var olan placeholder denetiminin (app/settings.py:53 `elif "REPLACE" in secret`) karsiligi burada YOK.

KOMUT: ENVIRONMENT=production, SECRET_KEY dolu, AUTH_ENABLED=true, SUPPORT_EMAIL='destek@<alan-adin>' ile support_problems() + validate_security_config()
CIKTI: support_problems() -> []   ve validate_security_config() hicbir hata vermeden GECTI.

Ayni bosluk canli kapida da var — scripts/live_gate.py:124-126:
    destek = str(kunye.get("destek", ""))
    s.ekle("destek adresi tanimli", "@" in destek, ...)
yani placeholder canli kapiyi da yesil gecer.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

Bulgu diskten DOGRULANDI, curutulemedi.

1) KOD BULGUYU DOGRULUYOR. app/settings.py:82-89 `support_problems()` yalnizca (a) bos mu (b) "@" iceriyor mu diye bakar. Ayni dosyada SECRET_KEY icin var olan placeholder reddi (app/settings.py:53 `elif "REPLACE" in secret`) SUPPORT_EMAIL icin YOKTUR.

2) CALISTIRARAK URETTIM (iddia edilen komut dogrulandi):
   ENVIRONMENT=production, SECRET_KEY=52 karakter, AUTH_ENABLED=true, SUPPORT_EMAIL='destek@<alan-adin>' ile
   `support_problems() -> []`
   `validate_security_config() -> GECTI (hata yok)`
   Yani .env.prod.example:64'teki placeholder fail-fast'i gecer.

3) CANLI KAPI DA GECIRIR. scripts/live_gate.py:125 `s.ekle("destek adresi tanimli", "@" in destek, ...)` — 'destek@<alan-adin>' icinde "@" var, kapi YESIL. Satir 127-129'daki ikinci kontrol yalniz gmail/hotmail/outlook/yahoo/yandex sahsi alan adlarini eler, placeholder'i elemez.

4) BASKA KATMAN KAPATMIYOR (hepsi okundu):
   - app/services/email.py:60 `destek_adresi()` env degerini oldugu gibi dondurur (yalniz bos ise uygulama-ici kanal metnine duser).
   - app/routers/meta.py:63 bu degeri KIMLIKSIZ GET /api/meta ucundan yayinlar.
   - scripts/deploy.sh:21-22 yalniz ".env.prod dosyasi var mi" der; icerik/placeholder denetimi yok.
   - docker-compose.prod.yml'de env_file yok; nginx/middleware/model-constraint/migration katmanlarinda ilgili kontrol yok.
   - tests/test_meta_destek.py:96-104 yalniz TANIMSIZ durumu kilitler; placeholder icin test yok (bu yuzden 1581 test yesil oldugu halde bosluk ayakta).
   - docs/kalite-seruveni/guvenlik-review-publish.md icinde "support/destek/placeholder" gecmiyor -> belgelenmis kabul-edilen-risk DEGIL.

5) OPERATOR HATASI OLASI, EGZOTIK DEGIL: docs/deployment/runbook.md:23 doldurulacaklar olarak yalniz "SECRET_KEY, POSTGRES_PASSWORD, DOMAIN, LLM key(ler)" sayar — SUPPORT_EMAIL bu listede yok. Ustelik .env.prod.example:64'teki yorum "tanimsizsa uygulama BASLAMAZ" diyerek operatoru "basladiysa sorun yok" sanisina iter.

SIDDET NEDEN 'YUKSEK' DEGIL 'ORTA': iki gercek hafifletici diskten dogrulandi.
   (a) docker-compose.prod.yml backend servisi (satir 33-57) SUPPORT_EMAIL'i konteynere HIC gecirmiyor (ne environment ne env_file) — belgelenmis Docker yolunda degisken tanimsiz kalir ve fail-fast dogru sekilde patlar; placeholder o yoldan sessizce yayina cikmaz. Placeholder ancak (i) docker'siz/systemd kurulumda (app/database.py:23 `load_dotenv()` .env okur) veya (ii) operator basla(t)mak icin compose'a `SUPPORT_EMAIL: ${SUPPORT_EMAIL}` ekleyince kullaniciya ulasir.
   (b) Zarar sinifi: veri sizintisi, para kaybi veya kimlik-dogrulama atlatma DEGIL; teslim edilemeyen destek kanali + KVKK basvuru yolunun fiilen kapanmasi (kullanici kaybi + hukuki zayiflik). Duzeltmesi tek satir (SECRET_KEY'deki gibi '<'/'>' veya 'alan-adin' placeholder reddi + live_gate'te ayni kontrol).
</details>

### D31 · [dusuk] Statik kapı 4 yaygın sorgu şeklini hiç modellemiyor (db.get / Model.kolon / func(Model.kolon)) ve LLM yazma yolu action_executor.py 1. kapının kapsamı dışında

- **Boyut:** izolasyon · **Yer:** `tests/test_scope_enforcement.py:106` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** BUG #162 (çapraz-kullanıcı hedef sızıntısı, kullanıcının parası başkasının hedef ilerlemesine yazılıyordu) tam olarak 'kapının modellemediği sorgu şekli' sınıfından geçmişti. Aynı sınıf hâlâ açık: kapalı betada eklenecek `db.get(Account, payload_id)` veya `db.query(Transaction.amount)` biçimli tek bir yeni satır, süit YEŞİL kalırken çapraz-kullanıcı okuma/yazma açar. Kapı bu haliyle 'geçti' raporu üretiyor ama korumadığı yüzey belgelenmemiş.

<details><summary>Kanıt</summary>

```
KOMUT:
  .\venv\Scripts\python.exe -c "from tests.test_scope_enforcement import _scan_source; ..."
ÇIKTI:
  'db.get(Account, id)'                    -> yakalandi mi: False
  'db.query(Transaction.amount,...)'       -> yakalandi mi: False
  'db.query(func.sum(Transaction.amount))' -> yakalandi mi: False
  'db.query(Account.name)'                 -> yakalandi mi: False

KÖK NEDEN (tests/test_scope_enforcement.py:106-116, _owned_model_arg): yalnız `f.attr == 'query'` veya `Name 'select'` çağrılarına bakıyor (db.get kapsam dışı) ve args[0]'ı düz Name/Attribute olarak okuyor — `Account.name` için arg.attr='name', `func.sum(...)` için arg bir Call → ikisi de OWNED_MODELS'e düşmüyor, sessizce atlanıyor.

1. KAPININ DOSYA KAPSAMI (satır 35-40, _TARGETS): yalnız app/routers/*.py + rules_engine.py + goal_engine.py + debt_strategy.py + coach_insights.py. `app/action_executor.py` LİSTEDE YOK — oysa orada 11 adet kapsamsız `Account.user_id == user_id` filtresi var (satır 190,201,268,542,605,673,695,743,752,800,854) ve bu dosya LLM aksiyonlarının TEK yazma yolu.

DOĞRULAMA: kendi bağımsız (daha sıkı) tarayıcımla app/ ağacını taradım — bugün bu şekillerden geçen GERÇEK bir kapsamsız sorgu YOK (10 aday da sahipliği çağıranda doğrulanmış). Yani bu aktif sızıntı değil, kapının kör noktasıdır.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

Bulgunun yapisal iddialari diskten BIREBIR dogrulandi, curutulemedi; ancak yayin engeli degil, test-kapisi kapsam borcu.

KANIT 1 (kapi kor noktalari — calistirilan komut, tests/test_scope_enforcement.py:106-116):
  'db.get(Account, id)'                       -> yakalandi: False
  'db.query(Transaction.amount).all()'        -> False
  'db.query(func.sum(Transaction.amount))'    -> False
  'db.query(Account.name).all()'              -> False
  'db.query(Account).all()'                   -> True   (yalniz ciplak-model sekli calisiyor)
  'db.execute(select(Transaction.amount))'    -> False  (bulgunun listelemedigi EK sekil)
Kok neden dogru: _owned_model_arg yalniz f.attr=='query' / Name 'select' bakar, args[0]'i duz Name/Attribute okur. Bu sekil teorik degil: app/action_executor.py:127 zaten `db.query(Account.name)` kullaniyor (orada _scope var, sizinti yok — ama kapi goremiyor).

KANIT 2 (1. kapi dosya kapsami): _TARGETS (satir 35-40) 33 dosya sayiyor (app/routers/*.py + rules_engine + goal_engine + debt_strategy + coach_insights); app/action_executor.py YOK. Kapinin kendi _PATTERN/SCOPED_MODELS mantigini o dosyaya uyguladim: 11 degil 14 kapsamsiz hit (192,202,270,415,500,544,607,675,696,744,753,756,802,856). Bulgu sayiyi eksik saymis.

KANIT 3: pytest tests/test_scope_enforcement.py -q -> 6 passed. Yani kapi bugun yesil, karakterize edilmemis yuzey uzerinde "gecti" raporu uretiyor.

NEDEN YAYIN ENGELI DEGIL (siddet dusuk):
(a) Aktif sizinti yok — bulgu bunu kendisi kabul ediyor, ben de bagimsiz dogruladim: 14 filtrenin hepsi `Model.user_id == user_id` ve user_id istemciden degil get_current_user'dan geliyor. Baska kullanicinin satirina bu yollardan erisilemez. Kalan artik risk = ayni kullanicinin KENDI hesaplari arasinda workspace karismasi (orn. _normalize_transaction_payload :190-204 workspace_scope(:263) icinde cagriliyor ama _scope yerine ham Account.user_id kullaniyor) — veri ifsasi/para kaybi/hukuki olay degil, kendi verisi uzerinde dogruluk purüzü.
(b) Prod'da ikinci calisma-zamani katmani var: app/database.py:84-98 after_begin hook'u set_config('app.current_workspace_id') yaziyor, Postgres RLS ws_isolation ayni satirlari DB katmaninda suzuyor.
(c) Iddia edilen zarar ("ileride eklenecek tek satir capraz-kullanici acar") var olmayan koda bagli kosullu zarar; KURAL 5 gercek kullanici zarari istiyor.
(d) KURAL 6 diskalifiye etmiyor: docs/kalite-seruveni/guvenlik-review-publish.md §4 kabul-edilen-riskler (e-posta enumerasyonu, depolanmis-metin prompt injection, localStorage token) arasinda bu yok; §3 "baskasinin verisi koca gecmiyor" diyor ama kapinin kendi erisim yuzeyini kapsamiyor.

Sonuc: bulgu gercek (savunma-derinligi / regresyon-kilidi borcu), kapali-beta bloklayicisi degil.
</details>

### D32 · [dusuk] /api/prices/* kimliksiz ve rate-limit'siz dis-servis cagri yuzeyi

- **Boyut:** kimlik-oturum · **Yer:** `app/routers/prices.py:32` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** EVDS_API_KEY yapilandirildigi anda kimliksiz bir saldirgan, istek basina 30 saniyeye kadar bloklanan bir dis HTTP cagrisi tetikleyebilir. Uygulamadaki TUM endpoint'ler senkron (`def`) oldugu icin bunlar Starlette threadpool'unu tuketir; birkac yuz eszamanli istekle butun API (cockpit, koc, islem girisi) yanit veremez hale gelir — yani odeme/borc takibi yapan kullanicilar servise erisemez. Ayrica operatorun TCMB EVDS kotasi ucuncu sahislar tarafindan tuketilebilir.

<details><summary>Kanıt</summary>

```
prices.py:9 docstring: 'Endpoint'ler PUBLIC (piyasa verisi, auth yok)'. Router'da ne `Depends(get_current_user)` ne `rate_limit(...)` var. deploy/nginx.conf.template:50 `limit_req` YALNIZ `location /api/auth/` icin tanimli; `location /api/` (satir 60) limitsiz.
Her istek app/price_providers/evds_client.py:80 `requests.get(url, ..., timeout=30)` ile dis cagri yapar; basarisiz sonuclar _CACHE'e YAZILMAZ (satir 122-135) -> her farkli kod/tarih yeniden dis cagri demektir.

CALISTIRILAN KANIT (scratchpad/proof_misc.py, AUTH_ENABLED=true, EVDS_API_KEY tanimli):
2) 60 kimliksiz /api/prices istegi -> HTTP kodlari={502}, dis (EVDS) cagri sayisi=60  (401/429 YOK = kimlik ve limit yok)
Kosul: EVDS_API_KEY tanimsizsa fetch_series erken doner ve dis cagri olmaz (.env.prod.example'da bu degisken YOK) -> siddet bu yuzden dusuk.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

Kod bulgunun tarif ettigi gibi: app/routers/prices.py:32 ve :52'de ne Depends(get_current_user) ne rate_limit var; app/main.py'de global kimlik/limit middleware yok (add_middleware sadece CORS + GovdeBoyutuMiddleware); deploy/nginx.conf.template:50 limit_req YALNIZ location /api/auth/ icinde, /api/ (satir 60) limitsiz ve proxy_cache yok; evds_client.py:80 timeout=30 ile dis cagri, basarisiz sonuc 122-136'da cache'e YAZILMIYOR. Kendi bagimsiz denememde (AUTH_ENABLED=true, EVDS_API_KEY tanimli, requests.get sayacli): 60 kimliksiz istek -> HTTP={502}, dis cagri=60, timeout=30; ayni kodla 10 istek -> 10 ek dis cagri; kontrol grubu /api/cockpit kimliksiz -> 401. Yani 401/429 gercekten yok. guvenlik-review-publish.md'de prices/EVDS gecmiyor, belgelenmis kabul-edilen-risk degil. ANCAK curutmeye en yakin nokta siddeti dusuruyor: docker-compose.prod.yml'de backend (26-58) ve scheduler (62-79) environment bloklarinda EVDS_API_KEY YOK ve env_file kullanilmiyor (--env-file yalnizca compose ikamesi, konteyner ortami degil), .env.prod.example'da da yok -> belgelenen prod kurulumunda fetch_series anahtarsiz erken doner (evds_client.py:71-74), dis cagri SIFIR, endpoint yalnizca 502 uretir. 30s timeout bir tavan, TCMB'nin tipik yaniti degil; threadpool tuketimi/kota yakimi ancak operator anahtari elle kablolarsa canlanir. Sonuc: boskuk gercek ve hicbir katmanda kapali degil (latent), ama mevcut yapilandirmayla bugun kullanici zarari yok -> yayin engeli degil, dusuk siddetli bir borc.
</details>

### D33 · [dusuk] PUT /api/user para birimini doğrulamadan kabul edip saklıyor, ancak tüm arayüz sabit ' TL' gösteriyor — kullanıcı "ayarladım" sanır, tutarları yanlış para biriminde okur

- **Boyut:** urunlesme · **Yer:** `app/routers/user.py:134` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** Sahte olanak (false affordance): API 200 döndüğü ve GET /api/user değeri geri verdiği için kullanıcı/entegrasyon para biriminin ayarlandığına inanır. Kullanıcı currency=USD ayarlar, bakiyelerini dolar diye girer, uygulama her ekranda "15.000 TL" yazar — kullanıcı kendi net değerini, borç kapatma planını ve nakit tamponunu ~40 kat yanlış okur; bu doğrudan yanlış para kararı demektir. Ayrıca '!!!' gibi ISO-4217 olmayan değer KVKK veri dışa aktarımına ve DB'ye kalıcı yazılıyor; ileride para birimi gerçekten devreye alındığında bu bozuk kayıtlar geriye dönük temizlik/migration borcu üretir. Doğru davranış TZ dalındaki desendir: ya 422 döndür ya ucu hiç açma.

<details><summary>Kanıt</summary>

```
KOD (app/routers/user.py:73-74, 126-136) — TZ ile currency arasındaki asimetri:
    timezone: Optional[str] = Field(None, max_length=40)
    currency: Optional[str] = Field(None, min_length=3, max_length=3)
    ...
    if payload.timezone is not None:
        try: ZoneInfo(payload.timezone)
        except Exception: raise HTTPException(422, f"Gecersiz saat dilimi: {payload.timezone}")
        user.timezone = payload.timezone
    if payload.currency is not None:
        user.currency = payload.currency.upper()      # <-- HİÇBİR doğrulama yok
TZ dalının kendi yorumu gerekçeyi yazıyor: "Gecersiz TZ kabul edilirse kullanici 'ayarladim' sanir ama tarihler yanlis kalir." Aynı gerekçe currency için DAHA GÜÇLÜ geçerli ama uygulanmamış.

ÇALIŞTIRDIĞIM KANIT (TestClient, gerçek kayıt akışı):
  PUT currency='USD'  -> 200  saklanan=USD
  PUT currency='XYZ'  -> 200  saklanan=XYZ
  PUT currency='zzz'  -> 200  saklanan=ZZZ
  PUT currency='!!!'  -> 200  saklanan=!!!
  GET /api/user -> {'id': 1, 'name': 'A', 'timezone': None, 'currency': '!!!', 'locale': None, ...}
  PUT timezone='Mars/Olympus' -> 422 {"detail":"Gecersiz saat dilimi: Mars/Olympus"}
(ISO-4217 olmayan '!!!' kalıcı olarak kullanıcı kaydına yazıldı ve API'den geri okunuyor.)

SAKLANAN DEĞER HİÇBİR YERDE TÜKETİLMİYOR — yardımcı ÖLÜ KOD:
  KOMUT: grep -rn "user_currency\|VARSAYILAN_PARA" app/ frontend/src/ --include=*.py --include=*.js --include=*.jsx
  ÇIKTI: yalnız 3 satır, hepsi app/user_prefs.py içinde (tanımın kendisi). SIFIR çağıran.

GÖSTERİM SABİT TL (kullanıcıya görünen):
  frontend/src/api.js:647  new Intl.NumberFormat('tr-TR', {...})
  frontend/src/api.js:667  return formatTL(amount, opts) + ' TL';
  frontend/src/components/MetricCard.jsx:25  suffix = ' TL',
  frontend/src/panels/DebtStrategy.jsx:7  Intl.NumberFormat('tr-TR',{style:'currency',currency:'TRY',...})
  (+ 19 dosyada gömülü ' TL' — Cockpit, Budget, Accounts, Reports, CashflowSummary, Wishlist ...)

ADR-042 KAPSAM NOTU: ADR "görüntüleme para birimi TRY kalıyor, yayın-engeli değil" diyor ve bunu KABUL EDİYORUM. Bu bulgu o ertelemeyi değil, ADR'nin ele ALMADIĞI kısmı raporluyor: yazma ucunun doğrulamasız olması ve ayarın sessizce yok sayılması (ADR yalnız "alan olarak saklanır, ileriye dönük uyumluluk için" diyor).
```
</details>

<details><summary>Çelişme turu hükmü</summary>

KOD IDDIASI DOGRULANDI, ZARAR ZINCIRI CURUTULDU.

Dogrulanan (disk + calistirilan komut): app/routers/user.py:126-137 asimetrisi aynen bulgudaki gibi. TZ dali ZoneInfo ile dogrulayip 422 atiyor, currency dali sadece `user.currency = payload.currency.upper()`. Kendi TestClient kosumumda (gecici test dosyasi yazildi, kosuldu, silindi; repo degismedi): currency='USD'->200 stored USD, 'XYZ'->200 stored XYZ, '!!!'->200 stored '!!!', '   ' (bosluk)->200 stored '   ' (strip bile yok), 'TR'/'ABCD'->422 (yalniz uzunluk), GET /api/user bozuk degeri geri veriyor; timezone='Mars/Olympus'->422. Locale de dogrulanmiyor ('xx-BOGUS'->200). Baska katman kapatmiyor: app/models.py:155 `Column(String(3), nullable=True)` — CHECK constraint yok; tek migration alembic/versions/b8c9d0e1f2a3_user_preferences.py ciplak sutun ekliyor; middleware/dependency dogrulayici yok. Rule 6 uygulanmiyor: docs/kalite-seruveni/guvenlik-review-publish.md'de "currency" hic gecmiyor, ADR-042 yalniz GORUNTULEME para birimini erteliyor, yazma-ucu dogrulamasindan hic bahsetmiyor — yani belgelenmis kabul-edilen-risk DEGIL.

CURUTULEN (siddeti dusuren iki bagimsiz gercek):
1) Kullanici bu ucu HIC set edemiyor. Tek yazici frontend/src/api.js:201 `update: (name) => request('/api/user', {method:'PUT', body:{name}})` — sadece name gonderiyor. frontend/src genelinde (fixtures haric) case-insensitive `currency|locale|timezone` grep'i SIFIR gonderici donuyor; tek hitler hardcoded `currency:'TRY'` bicimlendirme (DebtStrategy.jsx:7) ve toLocaleString cagrilari. Tercih ayarlari icin arayuzde form/panel yok. Bulgunun "kullanici USD ayarlar, dolar girer, her ekran TL yazar, net degerini ~40 kat yanlis okur" senaryosu urun uzerinden ERISILEMEZ — kullanicinin kendi hesabina elle ham API cagrisi yapmasini gerektirir.
2) Saklanan degerin TUKETICISI yok, dolayisiyla hicbir yanlis sayi uretilmiyor. user_currency() production'da sifir cagirana sahip (yalniz tests/test_user_preferences.py:108); app/cashflow.py:381 `"currency": "TRY"` hardcoded. Bozuk deger hicbir hesabi, gosterimi veya okunan export alanini degistirmiyor; `.upper()` her string'de guvenli oldugu icin cokme de yok.

KALAN GERCEK ZARAR: ISO-4217 disi degerler kullanici kaydinda ve KVKK export blob'unda kalici oluyor; coklu para birimi gercekten devreye girdiginde tek nullable sutunda kucuk bir temizlik/migration borcu birakiyor (tek UPDATE ile kapanir). Veri sizintisi, para kaybi, kullanici kaybi veya hukuki risk yok. Gercek bir kod defekti (TZ dalindaki desenle tutarsizlik) ama YAYIN ENGELI DEGIL — dusuk.
</details>

### D34 · [dusuk] Kurucunun özel hayatına ait kişi adı ve senaryolar sistem prompt'una ve tool şemasına gömülü — her beta kullanıcısının LLM çağrısında üçüncü taraf sağlayıcıya gidiyor

- **Boyut:** urunlesme · **Yer:** `app/coach.py:400` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** İki somut zarar: (1) Her beta kullanıcısının her koç mesajında, kurucunun tanıdığı gerçek bir kişinin adı ("efe") ve kurucunun özel seyahat/yatırım senaryosu üçüncü taraf LLM sağlayıcısına (Gemini/Groq/Anthropic) gönderiliyor — sağlayıcı log/eğitim politikalarına bağlı olarak bu, kurucunun ve o kişinin hayatına dair bir parçanın dışarı çıkması demektir; ürünün kendi KVKK duruşuyla çelişir. (2) Ürün kalitesi: LLM'e verilen tek somut dedup_key ve aksiyon örnekleri tek bir fon kodu (TLY) ve tek bir kişi üzerinden kurulu; kullanıcı bir ürünün kendi hayatına ait olmayan isimleri model çıktısında görürse (dedup_key/hafıza başlığı yüzeye çıkarsa) güven kaybı yaşar ve bunun "başkasının verisi bana mı geldi?" sorusunu doğurması beta geri bildirimi olarak maliyetlidir. Düzeltme sıfır riskli: örnekleri jenerikleştir (ör. yakin_kisi_odemeleri_2026q3, fon_satisi_seyahat, haftalik_market).

<details><summary>Kanıt</summary>

```
SİSTEM PROMPT (V3_GOD_MODE_PROMPT, satır 182'de başlıyor; satır 2460/2464'te her sohbette system_prompt olarak kullanılıyor):
  app/coach.py:400  "  Örnek: efe_payments_end_july2026 / tly_sale_georgia_trip / weekly_market_friday"
  app/coach.py:219  "| \"TLY'yi sat mı tutmalı mı\" (soru/öneri talebi) | YOK | Analiz + A/B/C seçenek |"
  app/coach.py:220  "| \"4 lot TLY sattım hesaba 19.700 geçti\" | VAR | propose_action + kısa not |"
  app/coach.py:289  "1-2 cümlelik kısa Türkçe metin de yaz. Örnek: \"4 lot TLY satışını kaydetmek için ...\""

TOOL ŞEMASI (save_insight, sağlayıcıya tools= ile gönderiliyor — app/coach.py:1427 anthropic_tools, :1650 groq_tools, :2538/:2664 active_tools):
  app/coach.py:530  "description": "Kısa snake_case slug: konu+zaman+kategori özetle. Örn: tly_sale_georgia_trip, efe_payments_end_july2026, weekly_market_friday. ..."

"Efe" gerçek bir kişidir — scripts/setup_data.py:257 counterparty="Efe" ile aynı kişi. "georgia_trip" / "Gürcistan seyahati" kurucunun kişisel olayı (app/models.py:92 "örn: 14 Nisan Gürcistan seyahati", app/models.py:526 "kullanıcı 28 Nisan'da Gurcistan seyahatinin TLY satisiyla finanse edilecegini soyledi"). "TLY" tek bir spesifik fon kodudur (app/models.py:228 fund_code örneği).

İLİŞKİLİ DNA KALINTISI (aynı aile):
  app/coach_insights.py:432  MC_REFERENCE_PATTERN = re.compile(r"\bMC([1-8])\b")
  — 1..8 aralığı kurucunun orijinal 8 master checkpoint'inden geliyor (scripts/setup_data.py:17 "7 master checkpoint (MC1 silindi ... MC2-MC8 korundu)"). Kendi kurallarını yazan yeni kullanıcının checkpoint başlıkları "MC" numarası taşımaz (bkz. app/routers/onboarding.py:118 title="Örnek kural: nakit tabanı"), 8'den fazla kural yazarsa MC9+ hiç sayılmaz.
  app/coach.py:347  "Örnek: \"MC8 (Hayatta Kalma > Yatırım) gereği...\" — numarayı cp.title'dan olduğu gibi al."

NOT: bu bir sızıntı DEĞİL, statik prompt metnidir — başka kullanıcının verisi taşınmıyor. Bu yüzden düşük şiddet.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

KOD DURUMU DISKTEN DOGRULANDI, AMA IDDIA EDILEN ZARARIN YARISI CURUTULDU.

Dogrulanan: app/coach.py:400 (V3_GOD_MODE_PROMPT icinde) ve app/coach.py:530 (SAVE_INSIGHT_SCHEMA dedup_key aciklamasi) bulgunun alintiladigi metni birebir iceriyor: "efe_payments_end_july2026 / tly_sale_georgia_trip / weekly_market_friday". app/coach.py:2460-2464'te system_prompt = V3_GOD_MODE_PROMPT (+cockpit) ve app/coach.py:2493-2496'da SAVE_INSIGHT_SCHEMA her cagrida active_tools icinde (soru olsun olmasin) -> metin gercekten her kullanicinin her koc mesajinda ucuncu taraf saglayiciya gidiyor. Ara sanitize/redaction katmani yok (middleware/dependency/settings tarafinda hicbir maskeleme bulamadim). "Efe"nin gercek karsi-taraf oldugu da dogru: scripts/setup_data.py:257 counterparty="Efe", :126/:139/:152 kredi adlari, :320 "MC7 - Efe Kredi Payi Takvimi". app/coach.py:219-220/:289/:347 TLY ve MC8 ornekleri de aynen mevcut. MC_REFERENCE_PATTERN = re.compile(r"\bMC([1-8])\b") app/coach_insights.py:432'de, ve :542'de mc_counts kullanicinin gercek checkpoint'lerinden bagimsiz olarak sabit 1..8 uzerinden normalize ediliyor. docs/kalite-seruveni/guvenlik-review-publish.md'de bu konu kabul-edilen-risk olarak YAZILI DEGIL (grep: efe/georgia/TLY yok).

CURUTULEN kisimlar (siddeti dusuren): (1) Iddia edilen zarar-2 ("kullanici dedup_key/hafiza basligini gorup 'baskasinin verisi mi geldi' der") diskte desteklenmiyor: dedup_key hicbir frontend dosyasinda gecmiyor (grep dedup_key frontend/src/ bos) ve hicbir response semasinda yok; yalnizca app/routers/actions.py:93-113'te prompt'a geri besleniyor, yani sunucu tarafinda kaliyor. (2) Zarar-1 abartili: saglayiciya giden sey her kullanici icin birebir ayni SABIT sablon metni; hicbir kullanici verisi tasimiyor, "Efe" tek bir ad + ay bilgisi, saglayici acisindan kimliklendirilemez. Ustelik urun tasarimi geregi _build_context_message ile zaten gercek hesap adlari, karsi-taraf isimleri ve checkpoint metinleri saglayiciya gidiyor; sabit ornek bunun yaninda marjinal. Dolayisiyla "KVKK durusuyla celisir" iddiasi kurulamiyor. (3) MC1-8 kalintisi da kullaniciya gorunmuyor: dormant insight'lar hicbir router veya prompt tarafindan okunmuyor (grep dormant app/routers/ app/coach.py bos); tek gorunurluk app/routers/user.py:186 KVKK veri-disa-aktariminda ham satir.

SONUC: Bulgu gercek bir kod durumunu dogru tarif ediyor ve duzeltmesi sifir riskli (ornekleri jeneriklestir), fakat somut kullanici zarari (veri sizintisi / para kaybi / hukuki risk) diskten gosterilemedi -> yayin engeli DEGIL, dusuk siddetli urun-DNA hijyen borcu. AYRICA (bu bulgunun kapsami disinda, ayri madde acilmali): app/coach_insights.py:502-620 extract_mc_reference_frequency, >=10 asistan mesaji olan HER kullanici icin "MC1..MC8 hic kullanilmayan kural" baslikli 8 uydurma dormant insight yaratiyor — kullanicinin MC numarali kurali olmasa bile; gorunurlugu sadece veri-disa-aktarimi oldugu icin yine dusuk siddet ama gercek bir veri-kirliligi defekti.
</details>

### D35 · [dusuk] Saat-bagimli flaky test: gunun %4.17'sinde (UTC 10:00-10:59) suit kirmizi — 'Flaky yok (M90)' iddiasi yanlis

- **Boyut:** test-kalitesi · **Yer:** `tests/test_user_preferences.py:63` · **Durum:** BUG #220 ile KAPANDI (5 Ağu, commit 442aabf)
- **Neden yayın engeli / etki:** PROJE.md 'Flaky yok (M90)' diyor; disk aksini soyluyor. Gunde 1 saat boyunca CI ve pre-commit hook'u kirmizi. Flaky bir kapi, gercek regresyonu goren gozu koreltir: 'yine o test' denip `--no-verify` ile gecilir ve o sirada gerçek bir para/izolasyon hatasi da birlikte gecer. Ayrica kirmizi CI, deploy runbook'unun (Wave-8) on-kosulu.

<details><summary>Kanıt</summary>

```
Kod:
```python
    ileri, geri = user_today(Sahte()), user_today(Sahte2())   # UTC+14 vs UTC-11
    assert (ileri - geri).days in (0, 1), f"beklenmedik fark: {ileri} vs {geri}"
```
Suit ciktisi (13:21 TR = 10:21 UTC):
```
E       AssertionError: beklenmedik fark: 2026-08-06 vs 2026-08-04
E       assert 2 in (0, 1)
tests\test_user_preferences.py:63: AssertionError
```
Deterministik dogrulama (24 saat tarandi):
```
$ ./venv/Scripts/python.exe -c "...Kiritimati vs Midway 24 saat..."
UTC saatine gore assert (0,1) IHLALI: [(10, 2)]
gunun yuzdesi: 4.166666666666666 %
```
UTC+14 ile UTC-11 arasi 25 saat; UTC 10:00-10:59 penceresinde takvim farki 2 gun olur. Assert'in kendisi yanlis, uretim kodu dogru.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

CURUTULEMEDI — diskten dogrulandi. (1) HEAD'deki kod bulgunun tarif ettigi gibi: `git show HEAD:tests/test_user_preferences.py` satir 63 = `assert (ileri - geri).days in (0, 1)`. (2) Canli reprodüksiyon: HEAD kopyasi scratchpad'e alinip kosuldu, SU AN (UTC 10:34) FAILED — `2 = (date(2026,8,6) - date(2026,8,4)).days`. (3) Deterministik 24s tarama: Pacific/Kiritimati +14:00 vs Pacific/Midway -11:00 = 25 saat yelpaze; ihlal yalnizca UTC saat 10'da → gunun %4.17'si. (4) Uretim kodu DOGRU: app/user_prefs.py:40-43 `user_today` = `datetime.now(tz).date()`; kusur assert'te, uygulamada degil. (5) guvenlik-review-publish.md'de kabul-edilen-risk olarak BELGELENMEMIS (orada yalnizca #169 konteyner-TZ var). ONEMLI DUZELTME: calisma agacinda fix ZATEN UYGULANMIS ama COMMIT EDILMEMIS — `git status` `M tests/test_user_preferences.py` gosteriyor, assert `(0, 1, 2)`'ye genisletilmis (`BUG #220 fix` yorumu) ve `pytest tests/test_user_preferences.py -q` → 7 passed. Yani bulgu commit'li repo'ya karsi gecerli, diskte giderilmis, commit bekliyor. SIDDET DUSURULDU: iddia edilen zarar (deploy on-kosulu, para/izolasyon hatasinin birlikte gecmesi) dolayli ve spekulatif; uretim davranisi, veri sizintisi veya para yolu ETKILENMIYOR — bu salt bir test assert hatasi. Gercek maliyet: HEAD'de pre-commit/CI kapisinin gunde 1 saat deterministik kirmizi olmasi ve PROJE.md'deki "Flaky yok (M90)" iddiasinin yanlislanmasi.
</details>

### D36 · [dusuk] Kendi basarisizligini `pytest.skip`'e ceviren test — yazildigi gunden beri olu, execute->hook yolu fiilen test edilmiyor

- **Boyut:** test-kalitesi · **Yer:** `tests/test_scheduler.py:171` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** Test bir basarisizligi 'skip' olarak raporluyor; skip'ler ozet satirinda bir kenara yazilir ve kirmizi saymaz. Yarin `execute_pending_action` add_transaction icin gercekten bozulsa, suit yine 'yesil + 1 skip' der. Kullaniciya etkisi: koc onayli aksiyon (harcama/borc kaydi) uygulanamaz halde kalirsa kullanici parasini yanlis takip eder ve bunu suit degil kullanici kesfeder. Ayni dosyada satir 105-108'de `except Exception: pass` ile `CoachEngine.chat` hatasini yutan ikinci bir ornek daha var.

<details><summary>Kanıt</summary>

```
```python
    result = execute_pending_action(db_session, pending.id, test_user.id)

    if result.get("success"):
        assert len(call_log) >= 1, f"hook cagrilmadi. Log: {call_log}"
    else:
        pytest.skip(f"execute_pending_action setup uyumsuz: {result}")
```
Calistirdigim suit ciktisi bunun CANLI oldugunu kanitliyor:
```
SKIPPED [1] tests\test_scheduler.py:174: execute_pending_action setup uyumsuz: {'success': False, 'action_type': 'add_transaction', 'error': 'transaction_type ve amount gerekli.'}
```
Testin kendi payload'i eksik (satir 155: `payload='{"amount": 100, "category": "test"}'` — `transaction_type` yok), yani `if` dali HIC calismadi. `execute_pending_action` -> `trigger_after_action_resolution` baglantisi (app/action_executor.py:476-477) hicbir testle kapsanmiyor.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

DISKTEN DOGRULANDI (olgusal cekirdek ayakta), ANCAK IDDIA EDILEN ZARAR CURUTULDU — bu yuzden siddet "dusuk".

AYAKTA KALAN KISIM (kanit):
1. Kod bulgudaki gibi. C:\Users\18155\PycharmProjects\financialos\tests\test_scheduler.py:146-174 — payload satir 155'te `'{"amount": 100, "category": "test"}'`, `transaction_type` yok; satir 171-174 `if result.get("success"): assert ... else: pytest.skip(...)`.
2. Test FIILEN OLU. Calistirdim: `.\venv\Scripts\python.exe -m pytest tests/test_scheduler.py -q -rs` → "11 passed, 1 skipped" + "SKIPPED [1] tests\test_scheduler.py:174: execute_pending_action setup uyumsuz: {'success': False, 'action_type': 'add_transaction', 'error': 'transaction_type ve amount gerekli.'}". Yani `assert` dali hic calismiyor.
3. YAZILDIGI GUNDEN BERI OLU. `git blame -L 146,174 tests/test_scheduler.py` → 29 satirin tamami tek commit 320194b3 (Murat Icgil, 2026-05-10) — payload ve skip dali ilk halinden beri ayni, hic duzeltilmemis (~3 ay).
4. Skip kirmizi saymiyor: pyproject.toml [tool.pytest.ini_options] icinde skip'i hataya ceviren bir ayar yok (yalniz testpaths + 3 marker), .githooks/pre-commit'te de skip kontrolu yok.
5. Execute yolunda hook'un cagrildigini DOGRULAYAN baska test yok: `trigger_after_action_resolution` grep'i → yalnizca reject yolu icin assert'li test var (test_scheduler.py:115-143) ve tests/test_coverage_m88.py:263 (wrapper'in exception yutmasi). app/action_executor.py:475-479'daki cagri `except Exception: log.warning` ile sarili oldugu icin, biri 476-477'yi silse/bozsa hicbir test kirmizi olmaz.

CURUTULEN KISIM (bulgunun zarar iddiasi yanlis):
- "Yarin execute_pending_action add_transaction icin gercekten bozulsa suit yine yesil der" → YANLIS. `execute_pending_action` 6 test dosyasinda 43 kez cagriliyor; tests/test_execute_pending_action.py:45-49 `test_execute_add_transaction_bakiye_gunceller` gecerli payload ile basari yolunu ve bakiye mutasyonunu dogruluyor. Bozulursa suit KIRMIZI olur. Kullanicinin "parasini yanlis takip etmesi" senaryosu bu olu test tarafindan degil, calisan testler tarafindan korunuyor.
- "execute->hook baglantisi hicbir testle KAPSANMIYOR" → satir-kapsami acisindan da yanlis. Olcum: `pytest tests/test_execute_pending_action.py tests/test_pay_credit_card.py --cov=app.action_executor --cov-report=term-missing` → missing listesi "...448-450, 478-479, 488-491..." yani 476-477 KAPSANIYOR (calisiyor); yalnizca 478-479 except dali kapsanmiyor. Eksik olan sey "kapsam" degil, "hook cagrildi mi" ASSERTION'i.
- Ikinci ornek (satir 105-108 `except Exception: pass`) olu degil: sonrasindaki satir 111 `assert len(user_calls) >= 1` gercekten kosuyor ve geciyor (test PASSED). Yalnizca hata yutma zayifligi, olu test degil.

SONUC: Gercek bir test-kalitesi defekti (dogumundan beri olu test + skip ile maskelenmis, execute->hook assertion'i yok). Ancak yayin engeli seviyesinde kullanici zarari yok: parasal dogruluk yolu baska testlerle kapali; kaybolan tek sey aksiyon-sonrasi davranissal-hafiza extractor tetiklemesinin regresyon korumasi (prod'da zaten except ile yutulan, koc icgoru kalitesini etkileyen ikincil yol). Veri sizintisi/para kaybi/hukuki risk yok → siddet dusuk.
</details>

### D37 · [dusuk] Fiyat cron'u TEK BIR hesabi bile guncelleyemedigi gecelerde kendini BASARILI (ok=True) kaydediyor

- **Boyut:** dayaniklilik · **Yer:** `app/scheduler.py:308` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** Dis saglayici kesintisi operasyonel olarak YESIL gorunur; kesinti fark edilmeden uzar ve bu sure boyunca kullanici bayat portfoy degerine bakar (bkz. 2. bulgu). Izleme sinyalinin yanlis pozitif olmasi, izlemenin var olma amacini ortadan kaldirir.

<details><summary>Kanıt</summary>

```
app/scheduler.py:293-308: her hesap icin `fetch_for_account` hatasi try/except ile yutulur (297-298), `res` None ise yalniz `logger.warning` (305-306). Dongu bittiginde kosulsuz `_kayit_bitir(_kayit, True, f"{updated}/{len(accounts)} hesap guncellendi")` (satir 308) — `updated == 0` olsa bile ok=True.
Ops ucu bu bayragi 'son_basarili' olarak yayinlar: app/routers/ops.py:53-55 `func.max(SchedulerRun.finished_at)` filtresi `SchedulerRun.ok.is_(True)`. Yani TEFAS/Is Yatirim/EVDS haftalarca cokse bile panel 'son basarili: bu sabah' der; gercek yalniz `detay` metnindeki '0/6' ifadesinden anlasilir.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

MEKANIK IDDIA DISKTEN VE CALISTIRARAK DOGRULANDI. app/scheduler.py:293-308 — her hesap icin fetch_for_account hatasi try/except ile yutuluyor (296-298), res None ise yalniz logger.warning (304-306), dongu sonrasi kosulsuz `_kayit_bitir(_kayit, True, f"{updated}/{len(accounts)} hesap guncellendi")` (308). 309-312'deki except yalnizca dongu-disi hatada (DB/query) tetiklenir; tam saglayici kesintisi ASLA ok=False uretmez. app/routers/ops.py:53-55 son_basarili = func.max(SchedulerRun.finished_at) filtre SchedulerRun.ok.is_(True). Scratchpad probu (3 yatirim hesabi, tum saglayicilar RuntimeError) cikti: "JOB: fetch_investment_prices | ok = True | detay = 0/3 hesap guncellendi" ve "ops.son_basarili = 2026-08-05 10:29:07". Yani bayrak "is cokmedi" demek, "is isini yapti" demek DEGIL — gercek yalniz detay metnindeki 0/3'te.

CURUTME DENEMELERI (siddeti DUSURDU, bulguyu gecersiz KILMADI):
1) Bagimsiz ve VERIDEN TURETILEN tazelik sinyali var ve DOGRU calisiyor: app/fund_tracker.py:166-210 get_freshness_summary, is_stale'i cron bayragindan degil her hesabin last_price_update'inden hesaplar. Ayni probda ayni kesinti sirasinda "freshness stale_count = 3" dondu. Uc: app/routers/fund_price.py:125-141; cockpit payload'ina enjekte: app/routers/cockpit.py:96.
2) Kullanici bayat degeri SESSIZCE gormuyor: frontend/src/panels/Cockpit.jsx:759-789 "Fiyat tazeligi" karti + stale_count>0 ise "N eski" uyari cipi + is_stale hesaplarda warn-renkli age_text. Bulgunun "kullanici bayat portfoy degerine bakar" zarar iddiasi buyuk olcude curudu.
3) Canli kapi yalan bayraga DAYANMIYOR: scripts/live_gate.py:177-182 /api/fund-price/freshness uzerinden stale_count == 0 sartini kosuyor; scheduler kontrolu (171-175) zorunlu=False ve yalniz son_sonuc is False'a bakiyor.
4) Naif duzeltme yanlis olurdu: yatirim hesabi olmayan kullanicida updated==0 & len(accounts)==0 mesrudur (0/0); dogru duzeltme hata-sayisi tabanli olmali.

KABUL-EDILEN-RISK DEGIL: docs/kalite-seruveni/guvenlik-review-publish.md icinde scheduler basari semantigi hakkinda kayit yok (yalniz #169 konteyner saat dilimi).

SIDDET GEREKCESI: para kaybi / veri sizintisi / hukuki risk yok; kullaniciya donuk dogru uyari zaten var (Cockpit rozeti) ve operator icin dogru ikinci sinyal (freshness stale_count) hem API'de hem live_gate'te mevcut. Ayrica ayni ops payload'i detay="0/3" ve son_sonuc alanlarini da donduruyor. Kalan gercek defekt: son_basarili alaninin anlamsal olarak yaniltici olmasi — yayin engeli degil, izleme kalitesi borcu.
</details>

### D38 · [dusuk] Migration geri-alinabilirlik kapisi elle yazilmis sabit listeye bagli — sonraki migration'lar denetlenmiyor

- **Boyut:** dayaniklilik · **Yer:** `tests/test_rollback_drill.py:27` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** `pass` downgrade, eksik downgrade'den daha tehlikelidir: `alembic downgrade` BASARIYLA doner ve surum isaretcisini geri alir ama tablo/sutun yerinde kalir; operator 'sema geri alindi' sanir, sonraki `upgrade head` 'already exists' ile patlar ve kesinti panik aninda elle SQL'e doner (veri kaybi riski). Kapi sabit liste oldugu icin bir sonraki yayin migration'i bu tuzagi sessizce geri getirebilir. Bugun canli veriye zarar vermedigi icin dusuk siddet.

<details><summary>Kanıt</summary>

```
tests/test_rollback_drill.py:27-37 `WAVE9_REVIZYONLAR = {...}` 9 revizyonluk SABIT kume; test_yeni_migrationlar_gercek_downgrade_tasir (satir 100-112) yalniz bu kumeyi parametrize eder. Bu kumeden sonra eklenecek her migration `def downgrade(): pass` ile yazilsa bile kapiyi gecer — oysa docstring (satir 10-11) 'ileriye donuk kapi: Wave-9 ve sonrasi her migration GERCEK bir downgrade govdesi tasimali' diyor.
Mevcut durumda `downgrade` govdesi salt `pass` olan 10 migration var (tum alembic/versions taranarak): fa46373f4ca8, 62136ecd252e, 12b80d6485bf, 9558e190f209, 0db7cfbb706f, 53a3257f906c, fb38814500bf, f3dda4d3996d, fec73e5343e5, c1d2e3f4a5b6. `alembic history` ciktisina gore bunlarin en yenisi (c1d2e3f4a5b6) head'den 13 surum geride — yani runbook'un onerdigi `alembic downgrade -1/-2/-3` yolu (docs/deployment/runbook.md:183) BUGUN guvenli; risk gelecege ait.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

CURUTULEMEDI — bulgu diskten dogrulandi, ancak iddia bir noktada FAZLA GENIS; siddet "dusuk" dogru.

DOGRULANAN OLGULAR (hepsi disk/komut kaniti):
1. tests/test_rollback_drill.py:27-37 gercekten elle yazilmis 9 elemanli sabit kume (WAVE9_REVIZYONLAR). Satir 100-101 `@pytest.mark.parametrize("revizyon", sorted(WAVE9_REVIZYONLAR))` — yalniz bu kumeyi gezer, alembic/versions'i taramaz.
   `pytest tests/test_rollback_drill.py --collect-only -q | grep gercek_downgrade | wc -l` -> 9 (dosyada 29 migration var). Tum dosya: 13 passed.
2. `pass`-govdeli 10 migration iddiasi birebir dogru. alembic/versions tam taramasi (calistirildi) ayni 10 dosyayi verdi: fa46373f4ca8, 62136ecd252e, 12b80d6485bf, 9558e190f209, 0db7cfbb706f, 53a3257f906c, fb38814500bf, f3dda4d3996d, fec73e5343e5, c1d2e3f4a5b6.
3. `alembic history`: en yeni pass-only olan c1d2e3f4a5b6 head'den 12 surum geride (bulgu "13" demis — onemsiz sapma). Yani bugun runbook'un -1/-2/-3 yolu gercekten guvenli; risk gelecege ait. Bulgunun kendi bu tespiti dogru.
4. docs/deployment/runbook.md:183 gercekten `alembic downgrade -1  # veya -2 / -3 …` diyor.
5. alembic/script.py.mako: `def downgrade() -> None:\n    ${downgrades if downgrades else "pass"}` — sablon bos downgrade'i VARSAYILAN olarak `pass` uretiyor, yani tuzak kazayla tekrarlanabilir.
6. Baska katmanda kapali degil: `grep -rln downgrade tests/ scripts/ .githooks/` yalniz test_rollback_drill.py ve alakasiz bir dormant-sweep testini dondurdu. guvenlik-review-publish.md'de "downgrade" gecmiyor -> belgelenmis kabul-edilen-risk DEGIL.

BULDUGUM KISMI SAVUNMA (bulguyu tam curutmuyor):
Scratchpad'de alembic'in kopyasina sahte migration ekleyip denedim. test_geri_alma_sonrasi_tekrar_head_e_cikilabilir (satir 75-87, downgrade -1 -> upgrade head) `pass` downgrade'i ASLINDA yakalayabiliyor: OperationalError "table sahte_tablo already exists". Yani bulgunun "bu kumeden sonra eklenecek HER migration pass ile kapiyi gecer" ifadesi fazla genis.

ANCAK bosluk gercek — ikinci deneyle kanitlandi: pass-downgrade'li migration head DEGIL de head'in altindaysa (bir yayinda iki migration ciktiginda tipik durum) drill sessizce yesil kaliyor: "-1: DRILL GECER (yakalanmadi)" ve "-3: DRILL GECER (yakalanmadi)". Ayrica salt-veri ya da idempotent (drop_* / IF NOT EXISTS) upgrade'lerde head'deki pass bile carpismaz. Dolayisiyla docstring'in (satir 10-11) vaat ettigi "Wave-9 ve sonrasi HER migration gercek downgrade tasimali" kapisi fiilen yok — kapi statik listeyle sinirli.

ZARAR MODELI DOGRU: `pass` downgrade basarili doner, alembic_version isaretcisi geri gider ama tablo/sutun kalir; operator "sema geri alindi" sanir, sonraki `upgrade head` "already exists" ile patlar — kesinti aninda elle SQL riski. Bugun canli veriye zarar yok (en yeni pass-only 12 surum geride), tetiklenmesi gelecekteki bir migration'a bagli ve head-vakasi kismen korunuyor: bu yuzden yayin-engeli degil, dusuk siddetli surdurulebilirlik/operasyon borcu. Duzeltme onerisi: parametrize'i alembic/versions taramasina + bilinen-eski-istisna allowlist'ine cevirmek.
</details>

### D39 · [dusuk] /api/health veritabanina hic dokunmuyor — deploy.sh otomatik-rollback kapisi, Docker HEALTHCHECK ve live_gate 1. kapisi DB cokmusken de YESIL

- **Boyut:** operasyon-deploy · **Yer:** `app/main.py:295` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** Deploy zincirindeki tek otomatik guvenlik agi (rollback) en olasi arizayi — Postgres'e baglanamama, yarim kalmis `alembic upgrade head`, tukenmis baglanti havuzu — hic goremez. Bozuk surum canlida kalir, kullanici her ekranda 500 alir, operatorun panelinde her sey yesildir. Finansal veri tasiyan bir betada 'yesil gorunen ama veriye erisemeyen' sistem, kullanicinin urune guvenini tek seferde bitirir ve sessiz terke yol acar.

<details><summary>Kanıt</summary>

```
app/main.py:295-306:
    def _health_payload() -> dict:
        from app.auth import auth_enabled
        return {"status": "ok", "service": "FinancialOS", "version": _APP_VERSION,
                "build": _build_commit(), "timestamp": ..., "auth_enabled": auth_enabled()}
(app/main.py:315-322 api_health bu payload'i oldugu gibi dondurur — hicbir DB sorgusu, hicbir Session bagimliligi yok.)

Bu uca dayanan uc kapi:
1) scripts/deploy.sh:29-35 — `until $COMPOSE exec -T backend curl -fsS http://localhost:8000/api/health` ... basarisizsa rollback. DB kapali/migration bozuk olsa bile 200 doner -> rollback ASLA tetiklenmez.
2) Dockerfile:41-42 — HEALTHCHECK CMD curl -fsS http://localhost:8000/api/health -> konteyner 'healthy' isaretlenir.
3) scripts/live_gate.py:77-78 — s.ekle("saglik ucu 200", kod == 200, ...) ZORUNLU kapi olarak.
```
</details>

<details><summary>Çelişme turu hükmü</summary>

Kod iddiasi diskten DOGRULANDI: app/main.py:295-322 _health_payload() yalnizca statik/config veri doner (auth_enabled() env okur), hicbir DB sorgusu/Session bagimliligi yok; app/ genelinde grep ile ikinci bir readiness ucu YOK. Calistirilan kanit: DATABASE_URL=postgresql://...@127.0.0.1:59999 (kapali port) ile TestClient — lifespan sadece "Catch-up backfill hatasi: OperationalError ... Connection refused" uyarisi basiyor, ardindan GET /api/health -> 200 {"status":"ok"} ve GET / -> 200; ayni anda SessionLocal().execute(SELECT 1) Connection refused firlatiyor. Uc tuketici de tarif edildigi gibi: scripts/deploy.sh:32-36 curl kapisi -> rollback, Dockerfile:41-42 HEALTHCHECK, scripts/live_gate.py:77-78.

ANCAK iddia edilen zararin buyuk kismi baska katmanlarda KAPALI: (1) "Postgres'e baglanamama" — docker-compose.prod.yml:31-33 backend depends_on db condition: service_healthy (db healthcheck pg_isready, satir 17-21); db saglikli degilse backend hic baslamaz, deploy.sh:28 "compose up -d" basarisiz olur ve rollback ORADA tetiklenir, saglik kapisina hic gelinmez. (2) "Yarim kalmis alembic upgrade head" — docker-entrypoint.sh:7 set -e + satir 21 alembic upgrade head; migration duserse process olur, gunicorn (satir 23) :8000'i hic acmaz, curl -fsS 60 sn boyunca duser -> rollback tetiklenir. Yani rollback bu arizayi GORUR (payload uzerinden degil, olu konteyner uzerinden). (3) live_gate kor degil: olu DB ile calistirilan probe'da /api/auth/register -> 500 (zorunlu kapi 403 bekliyor) ve /api/auth/login -> 500; script cikis kodu 1 verir. Yalnizca ILK satiri yanlis yesildir, toplam verdict FAIL'dir.

GERIYE KALAN GERCEK BOSLUK (bu yuzden bulgu ayakta ama kucuk): sureci ayakta kalan + migration'i gecen ama veri katmani calisma-zamaninda bozuk bir surum (sema/kod uyusmazligi, RLS/rol yanlis yapilandirmasi) veya deploy SONRASI DB kesintisi — deploy.sh'in otomatik rollback'i bunu goremez, konteyner "healthy" gorunur. Ayrica docker compose "unhealthy" durumuna otomatik mudahale etmez (deploy.sh --wait/autoheal kullanmiyor), dolayisiyla DB-farkinda bir HEALTHCHECK'in kazanimi otomatik kurtarma degil operator gorunurlugudur. Rutin guncellemede (runbook.md:46 sadece deploy.sh) live_gate calistirilmiyor; live_gate ancak elle kosulunca (runbook.md:100-106) yakaliyor. Bu bosluk guvenlik-review-publish.md'de kabul-edilen-risk olarak YAZILI DEGIL (grep "health": eslesme yok); yalnizca sections/API.md:133 ve goal-charter-wave4.md:563-568'de bilinen-eksik olarak geciyor. Not: bu makinede docker kurulu degil (Get-Command docker bos), compose depends_on davranisi dosya kanitiyla degerlendirildi, calistirilamadi. Zarar dar bir ariza sinifiyla sinirli ve ikinci bir elle kapi mevcut oldugundan yayin engeli degil -> siddet dusuk.
</details>

### D40 · [dusuk] Runbook'taki davet-uretme komutu konteyner disinda calisiyor — davet kodu YANLIS veritabanina (yerel SQLite) yazilir, davetli 403 alir

- **Boyut:** operasyon-deploy · **Yer:** `docs/deployment/runbook.md:129` · **Durum:** ⬜ AÇIK
- **Neden yayın engeli / etki:** Operator davet kodunu uretir, ekranda gorur, davetliye gonderir; kod host uzerindeki bos bir SQLite dosyasina yazildigi icin canli Postgres'te YOKTUR. Davetli kayit ekraninda 'Kayit su anda davetlilere acik. Gecerli bir davet kodu gerekli.' (403, app/routers/auth.py:152) alir. Sebep ayristirilmadigi icin ne davetli ne operator nedenini anlar — betaya davet edilen kullanicilarin tamami kapida kaybedilir, uygulama hic denenmez.

<details><summary>Kanıt</summary>

```
docs/deployment/runbook.md:126-134 'Beta isletimi (P7)' blogu:
    python -m scripts.beta_invite --email <davetli> --note "<kim>"
    python -m scripts.beta_invite --list
    python -m scripts.beta_triage
Ayni runbook'taki diger tum operasyon komutlari `docker compose -f docker-compose.prod.yml exec -T db ...` ile prefikslenmis (satir 121-122, 52, 80) — bu blok DEGIL.

scripts/beta_invite.py:20 `from app.database import SessionLocal`
app/database.py:23,26:
    load_dotenv()
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/financialos.db")
Prod DATABASE_URL yalnizca compose tarafindan backend/scheduler KONTEYNERLERINE veriliyor (docker-compose.prod.yml:46,77); sunucudaki repo kabuğunda tanimli degil ve sunucuda `.env` dosyasi yok (yalniz `.env.prod`, load_dotenv onu okumaz).
```
</details>

<details><summary>Çelişme turu hükmü</summary>

CEKIRDEK DOGRU, IDDIA EDILEN ZARAR CURUTULDU.

Diskten dogrulanan: docs/deployment/runbook.md:126-137 "Beta isletimi (P7)" blogundaki `python -m scripts.beta_invite/beta_triage/beta_metrics` komutlari konteyner-prefiksiz; ayni runbook DB komutlarini (52, 72-89, 122-123) ve satir 91'de `docker compose exec backend python -m alembic ...` seklinde prefiksliyor, docs/deployment/README.md:53,97 de `docker compose exec backend python -m scripts....` formunu kullaniyor -> beta blogu TUTARSIZ. scripts/beta_invite.py:20 -> app/database.py:23,26 `load_dotenv()` + `os.getenv("DATABASE_URL", "sqlite:///./data/financialos.db")`; .env.prod'u load_dotenv okumaz ve docker-compose.prod.yml:46,77 DATABASE_URL'i yalniz backend/scheduler KONTEYNERLERINE verir -> host kabugunda SQLite varsayilani gecerli. Bu kisim dogru. Kabul-edilen-risk olarak da yazili degil (docs/kalite-seruveni/guvenlik-review-publish.md'de yok).

CURUTULEN kisim (komut calistirildi, ciktilar kanit): temiz sunucuda (runbook adim 2 = git clone, host'ta alembic hic kosmamis) komut SESSIZCE YANLIS DB'ye YAZMAZ, GURULTULU COKER: taze SQLite'a karsi `python -m scripts.beta_invite --email test@example.com` -> `sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: beta_invites`, EXIT=1, hicbir davet kodu basilmaz; `--list` de EXIT=1. Yani "operator kodu gorur -> davetliye gonderir -> davetli 403 alir -> kimse nedenini anlamaz" zinciri OLUSMAZ. Ayrica runbook host'a Python bagimliligi kurmuyor (satir 13-14: yalniz git + Docker; venv/pip yok) -> gercek VM'de komut daha da erken ModuleNotFoundError ile olur. Sessiz-basari yalniz host'ta SEMALI bir SQLite varsa mumkun; bunu ayrica test ettim (`alembic upgrade head` kosulmus host DB'sine karsi EXIT=0 + gecerli gorunen kod, `Kayit modu: open` uyarisiyla) ama runbook'un Docker yolu host'ta asla alembic kosturmuyor. O durum sadece deploy/financialos.service (bare-metal/SQLite alternatifi) yolunda olusur ve orada komut ZATEN DOGRUDUR.

Kalan gercek zarar: runbook'u harfiyen izleyen operator davet URETEMEZ (kapali beta invite_only fail-closed oldugu icin bu sirada kimse kayit olamaz) — ama hata gurultulu, kendini ele veren ve guvenli (fail-loud/fail-safe), dogru form iki dosya oteye (README.md:53) yazili. Veri sizintisi, para kaybi veya sessiz kullanici kaybi YOK.
</details>

## Boyut özetleri

### izolasyon

Çapraz-KULLANICI izolasyonu iddiası büyük ölçüde DOĞRULANDI: 29 router'ın tamamını okudum, bağımsız (statik kapıdan daha sıkı) bir AST tarayıcı yazdım ve kendi runtime probumla hem MATRIS_DISI'na alınmış 20 /{id} ucunu hem de A-yaratır/B-okur ampirik süpürgesini koşturdum — bugün B kullanıcısının A'nın verisine eriştiği tek bir yol bulamadım (0 sızıntı). Ancak WORKSPACE kapsamı tarafında üç gerçek defekt var: koç-onaylı Transaction ve MasterCheckpoint satırları workspace_id=NULL yazılıyor ve kullanıcının KENDİ panelinden/raporundan/koç bağlamından siliniyor (canlı DB'de de görülüyor, tüm süit yeşilken), ayrıca /api/cashflow/forecast ile /api/debt-strategy/* workspace bağlamını hiç kurmadığı için aile görünümünde kişisel borç/nakit ifşa oluyor. Buna ek olarak statik kapı db.get/Model.kolon/func(Model.kolon) şekillerini hiç modellemiyor ve LLM yazma yolu action_executor.py 1. kapının dosya kapsamı dışında — yani BUG #162'nin geçtiği sınıf hâlâ açık.

### kimlik-oturum

Token katmani saglam: HS256 tek algoritma listesiyle dogrulaniyor, imza+exp+tip (`expected_type`)+jti kara listesi+`tv` oturum sayaci access ve refresh yollarinda eksiksiz uygulanmis; refresh rotasyonu ve tekrar-kullanim tespiti (RFC 9700) gercek. Kimliksiz uc envanteri temiz — 115 route'un 95'i `get_current_user` ile korunuyor, geri kalan 20'sinin 12'si zorunlu auth akisi, meta.py/legal.py/health hicbir kullanici sayisi, e-posta veya ic yapilandirma sizdirmiyor (calistirilarak dogrulandi). Buna karsilik dort gercek acik var: (1) sifre sifirlama token'i, kullanici sifresini degistirdikten sonra bile canli kaldigi icin hesap geri alinamiyor — kanitli hesap ele gecirme; (2) OAuth callback kapali-beta davet kapisini tamamen atliyor; (3) AUTH_ENABLED prod fail-fast'i yalniz ENVIRONMENT=production iken tetiklendigi icin belgelenmis systemd dagitim yolu kimliksiz canli sunucu uretebiliyor; (4) /api/prices/* kimliksiz + limitsiz dis-cagri yuzeyi.

### kota-maliyet

(a) Rezervasyon deseninin SAYIM mantigi saglam: satir once yazilip `id <= log.id` ile siralaniyor, reddedilen rezervasyon siliniyor; SQLite'ta 3 paralel istekle dogrulandi (tests/test_coach_eszamanlilik.py 15 test gecti) ve silinen satirin araya giren id'yi bozdugu bir senaryo uretilemedi — bu soruda bulgu yok. (c) Tavan dolunca uygulamanin geri kalani calisiyor: kota dolu kullanicida /api/cockpit, /api/accounts, /api/coach/usage, /api/coach/history, /api/actions/pending hepsi 200 dondu (ADR-041'in vaadi tutuyor). Asil kirilma (b)'de: kota dayatmasi YALNIZCA POST /api/coach/chat'te var; kullanicinin tetikleyebildigi en az iki LLM yolu (POST /api/premortem/{id} ve POST /api/actions/{id}/approve arkasindaki Groq reflection) kotayi tamamen atliyor ve ApiCallLog'a hic yazmiyor — kotasi dolmus (429 almis) bir kullanicida bile calistigi calistirilarak kanitlandi. Ustune, "paylasilan saglayici gunluk kotasi" diye sunulan 1500/gun korumasi sorguda user_id ile filtrelendigi icin fiilen kullanici-basinadir ve kullanici tavani (80) < 1500 oldugundan `block` dali hic tetiklenemez; bir kullanici 2000 cagri yapmisken digerinin sayaci 0 goruldu. Son olarak tavan cagri degil mesaj sayiyor (1 istek = 2 provider.chat olculdu), yani gercek maliyet ADR-041'in ilan ettigi rakamin 2-3 kati.

### urunlesme

Tek-kullanıcı DNA'sının en tehlikeli iki sınıfı TEMİZ çıktı: sabit user_id=1 çalışma-zamanı yolunda kalmamış (tek kalıntı app/reasoning_trace.py:10'daki docstring örneği; _fallback_user production'da settings.auth_problems ile fail-fast kapatılmış) ve BOŞ dünya sağlam — kendi bağımsız problarımda 40 GET ucu + query-param uç değerleri ve 4 kısmi-dünya senaryosu × 27 motor fonksiyonu sıfır 5xx/istisna verdi, bölme-sıfıra ile [0] deref'lerin hepsi guard'lı. Banka markaları da gerçekten sökülmüş (BUG #168, action_executor artık eşleşmeyi kullanıcının kendi hesap adlarından türetiyor) ve onboarding demo verisi tamamen jenerik. Kalan dört bulgu kişiselleştirme ekseninde toplanıyor: en ağırı, ADR-042'nin \"uygulandı\" dediği saat dilimi işinin diskte yarım olması — koçun kaydettiği işlem hâlâ SUNUCU tarihiyle DB'ye yazılıyor (probla iki yönde de yanlış olduğunu kanıtladım), reports/subscriptions/net-değer snapshot'ı da öyle; bunu para birimi ucunun doğrulamasız kabul edip tamamen yok sayması, kurucunun ve adı geçen üçüncü bir kişinin gerçek finansal verisini taşıyan scripts/setup_data.py'nin production imajına girmesi ve o kişinin adının sistem prompt'u ile tool şemasında her LLM çağrısında dışarı gitmesi izliyor.

### test-kalitesi

Suit "1581 passed" degil: diskte su an 3 failed, 1605 passed, 6 skipped. Daha agiri: commit'li HEAD'de (d62f6dd) capraz-kullanici izolasyon matrisinin "kapsam kilidi" testi FastAPI 0.141 ile sessizce boslasmis — 29 ID'li ucun 0'ini tariyordu, yani matematiksel olarak KIRILAMAZ bir guvenlik kapisiydi; ayni kok neden bos-durum e2e kapisini 40 uctan 1'ine dusurmustu. Buna ek olarak bir test global FastAPI `app` nesnesine kalici bir cokme ucu ekleyip iki kapiyi kirmiziya cekiyor, bir test gunun %4.17'sinde saat-bagimli patliyor ("Flaky yok" iddiasi yanlis), bir test kendi basarisizligini `pytest.skip`'e ceviriyor ve prod dialect'i PostgreSQL'in RLS/dual-dialect kapilari ne yerelde ne CI'da hic kosmuyor. Testlerin cogunlugu (ozellikle test_scope_enforcement.py'nin meta-testleri) gercekten saglam; sorun kapi-tipi testlere olcusuz duyulan guvende.

### dayaniklilik

Dis saglayici katmani (TEFAS/pytefas, Is Yatirim, yfinance, EVDS, open.er-api) coktugunde her yol duzgun sekilde None dondurup akisi bozmuyor; doviz tarafinda BUG #211 ile getirilen 'son bilinen deger + BAYAT isareti' disiplini ornek nitelikte. Ancak ayni disiplin YATIRIM FIYATI tarafinda uygulanmamis: bayatlik bilgisi yalniz HTTP cockpit yanitina router'da eklendigi icin koc onu hic gormuyor ve 30 gunluk eski fiyatla hesaplanan portfoy degerini/getirisini kosulsuz 'guncel' gibi sunuyor (calistirarak dogrulandi). Daha agiri: otomatik fiyat cron'u Account.balance'i guncellemedigi icin Hesaplar paneli ile Cockpit ayni hesap icin farkli TL gosteriyor (6 lotluk ornekte 6.000 TL fark, calistirarak dogrulandi). Cron gorunurlugunde 5 isten 3'u hic kayit tutmuyor (KVKK 90-gun saklama isi dahil) ve fiyat isi 0/N guncellemede bile ok=True yaziyor. Yedekleme tarafinda backup.py/restore.py'nin kendisi saglam (integrity_check, bozuk yedek reddi, emniyet kopyasi) ama PRODUCTION yiginda otomatik yedek HIC yok ve depodaki tek systemd unit Postgres'te cikis kodu 1 ile oluyor — kullaniciya verilen KVKK yedek-rotasyon taahhudu de bu bosluga dayaniyor. Migration'larda 10 adet `downgrade: pass` var ama hepsi head'den 13+ surum geride; bugunku geri-alma yolu guvenli, risk kapinin sabit listeye bagli olmasindan dolayi gelecege ait.

### hukuki-gizlilik

KVKK/gizlilik boyutunda en ağır sorun kod ile YAYINLANAN hukuki metin arasındaki çelişki: `veri-isleyen-envanteri.md` "ham işlem listesi gönderilmez" diye beyan ederken, koç bağlamı işlem açıklamalarını (sağlık/özel nitelikli veri içerebilir), hesap adlarını ve üçüncü kişilerin adlarını yurt dışındaki LLM sağlayıcılarına gönderiyor; ayrıca zincirde aktif olan iki sağlayıcı (Together, DeepInfra) envanterde hiç yazmıyor ve "kodla kilitlenir" denen test 4 ismi sabit kodladığı için bunu yakalamıyor. Taşınabilirlik/silme tarafında: her iki export ucu da `password_hash` + `oauth_sub` döküyor, UI'nin kullandığı `/api/users/me/export` iki tabloyu (goal_allocations, goal_rules) atlıyor ve tamlık testi yanlış ucu koruyor, hesap silme sonrasında `beta_invites.email` diskte kalıyor. Log tarafı büyük ölçüde temiz (e-posta maskeleme çalışıyor, ham koç mesajı loglanmıyor) ama `error_tracking.temizle` TCKN/telefon/bcrypt hash/opak token'ı kaçırıyor ve global hata yakalayıcı ham traceback'i maskesiz dosya log'una yazıyor.

### operasyon-deploy

Deploy zinciri kagit uzerinde tam (Dockerfile non-root, nginx HSTS/CSP, fail-fast, invite_only), ama CANLI YOLDA calismaz: `docker-compose.prod.yml`'de `env_file` yok ve `.env.prod.example`'daki SUPPORT_EMAIL/REGISTRATION_MODE/COACH_DAILY_USER_LIMIT/MAX_REQUEST_BODY_BYTES hicbir servise gecmiyor — production fail-fast SUPPORT_EMAIL'i zorunlu tuttugu icin backend ve scheduler acilmadan RuntimeError ile duser (kanit: yaml parse + validate_security_config calistirildi). Kapilarin bir kismi hep-yesil: `/api/health` DB'ye hic dokunmadigi icin deploy.sh'in otomatik-rollback kapisi ve Docker HEALTHCHECK veritabani cokmusken de 200 doner; live_gate cron/fiyat kapilari zorunlu=False ve kimlik verilmeden kosuldugunda tum oturum kapilari atlanmasina ragmen "TUM ZORUNLU KAPILAR GECTI" basar. Davet kodu mekanizmasi (secrets.token_urlsafe(18), unique+index, tek kullanimlik, 30 gun varsayilan sure) saglam — bulgu yok; kullanim metrikleri de (scripts/beta_metrics.py + runbook) gercekten var, o bosluk kapali.

## Çürütülen bulgu (kayıt için)

### [izolasyon] Çapraz-kullanıcı matrisinin kapsam kilidi METOT-KÖR: var olan bir /{id} yoluna eklenen yeni HTTP metodu kilidi kırmadan geçer

CURUTULDU. Bulgunun MEKANIK gozlemi dogru ama IDDIA EDILEN ZARAR diskten yanlislandi.

DOGRU olan kisim (teyit ettim):
- tests/test_cross_user_isolation.py:279-282 — normalize() yalniz yol uzerinde calisiyor (re.sub(r"\{[a-z_]+\}","{id}", path.split("?",1)[0])), metot hic islenmiyor.
- tests/endpoint_envanteri.py:62-73 — yol_parametreli_uclar() docstring'inde bile "metottan bagimsiz" yaziyor, cıplak yol listesi donuyor.
- OpenAPI dokumu: "GET,POST /api/goals/{goal_id}/allocations" var; matris (satir 147) yalniz GET probe ediyor. Ornek gercek.

CURUTEN kisim — iddia edilen zarar mekanizmasi BASKA BIR KATMANDA kapali:
Bulgu diyor ki "var olan bir yola eklenecek yeni POST/PUT izolasyon testi yazilmadan gecer ve suit yesil kalir; baskasinin kaynagina yazma acigi sessizce yayina cikar." Bu YANLIS. tests/test_scope_enforcement.py, app/ agacinin TAMAMINI tarayan, YOL ve METOT'tan tamamen BAGIMSIZ ikinci bir kapidir. Bulgunun tarif ettigi senaryoyu birebir calistirdim:

1) Var olan bir yola (/api/goals/{goal_id}/share) sahiplik filtresi UNUTULMUS yeni bir POST ucu:
   _scan_source(...) -> ['goals.py:4: Goal sorgusu KAPSAMSIZ (sahiplik filtresi yok)'] = YAKALADI
2) Daha ince kacis (duz models.Goal.user_id == current_user.id, workspace scope yok):
   AST kapisi yakalamadi ama M70 regex kapisi (_PATTERN + SCOPED_MODELS) -> ['4: Goal'] = YAKALADI

Yani her iki varyantta da suit KIRMIZI olur. "Suit yesil kalir" premisi coktu; kapsam kilidi hicbir zaman yeni yazma-ucu ile sizinti arasindaki TEK savunma degildi.

CANLI DAVRANIS (kendi runtime probum, salt-okur, scratchpad'de):
- B kullanicisi A'nin goal'ine POST /api/goals/{gid}/allocations (matriste probe EDILMEYEN metot) + POST /{gid}/refresh -> ikisi de 403/404. 1 passed.
- app/routers/goals.py:194-217 create_allocation hem Goal'i hem Transaction'i scope_filter ile suzuyor (satir 207 ve 214). Fiili acik YOK.
- Mevcut tests/test_scope_enforcement.py + tests/test_cross_user_isolation.py: 23 passed.

SONUC: Bulgunun kendisi de "bugun fiili zarar yok" diyor. Geriye kalan tek sey bir kapinin granularitesinin yol-duzeyinde olmasi — bu, ikinci kapi (statik AST + regex, metot-korlugu OLMAYAN) tarafindan zaten ortulen bir stil/tasarim tercihi. Kural 5 geregi gercek kullanici zarari (veri sizinti / para kaybi / hukuki risk) yok, yayin engeli degil. Hicbir dosya degistirilmedi.
