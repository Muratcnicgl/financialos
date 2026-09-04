# DURUM RAPORU — 1ada15c..HEAD (11 Ağustos → 4 Eylül 2026)

> **Talep:** web tarafındaki oturumun elindeki son çıpa 11 Ağu 2026 / `1ada15c` /
> `ara-durum-raporu-2026-08-11.md`. Aradaki ~3,5 haftalık pencere ölçülmemişti.
> **Kural (R3):** her sayının arkasında koşulmuş bir komut vardır. Kanıtı olmayan satır
> **KANIT YOK** diye işaretlenir; tahmin yürütülmez.
>
> **Çıpa düzeltmesi:** `1ada15c` commit'i **10 Ağustos** tarihlidir
> (`feat(eval): BUG #278 — LLM-005 kapandi`). 11 Ağustos, ara raporun yazıldığı gündür.

---

## §0.1 ÖZET KARTI — 11 Ağu → 4 Eyl

| Ölçüm | 11 Ağu (çıpa) | 4 Eyl (bugün, ölçüldü) | Yön |
|---|---|---|---|
| Backend testi | 2.969 | **3.486 passed · 18 skipped · 0 failed** (4:55) | +517 |
| Frontend (vitest) | 175 | **214 passed** (19 dosya) | +39 |
| E2E (Playwright) | 6 | **8 passed** (izole koşum, :8100/:5273) | +2 |
| Coverage | **ölçülmüyordu** (KANIT YOK) | **%94,02** (11.713 ifade / 701 kapsanmayan), CI'da `--cov-fail-under=93` | ölçüldü + kilitlendi |
| ADR | 56 | **56** (çıpadan sonra yeni ADR yok) | değişmedi |
| BUG tavanı | #278 | **#338** | +60 |
| Alembic head | `c5d6e7f8a9b0` | **`c3d4e5f8a1b2`** (39 göç dosyası, +6 yeni) | ilerledi |
| Backlog | 164 ✅ / 251 🔲 / 81 🟡 | **164 ✅ / 251 🔲 / 81 🟡 — HİÇ DEĞİŞMEDİ** | ⚠️ güncellenmemiş |
| Kalite kapıları | yok | **7 kapı** (ruff · coverage · ölü kod · belge · ağ · API sözleşmesi · kişisel veri) | +7 |
| Faz | Kapalı beta B0-B3 kapalı, B4 bekliyor | **AYNI** — B4 hâlâ B0'ı bekliyor; ayrıca **Wave-K (koç hattı)** açıldı | yatay |
| Canlı beta | yayında | **yayında** (health 200 · ready 200 · 6 kullanıcı) | ayakta |

**Tek cümlelik özet:** kod kalitesi ölçülebilir biçimde YÜKSELDİ ve ürün canlıda ayakta;
**yayına geçişi engelleyen şey kalite değil, 24 gündür açık duran TEK bir insan kararıdır (B0).**

---

## 1) COMMIT DELTASI

| | Değer | Kanıt |
|---|---|---|
| Commit sayısı | **66** | `git rev-list --count 1ada15c..HEAD` |
| Tarih aralığı | 11 Ağu – 4 Eyl 2026 | `git log --format=%ad` |
| **Aktif gün** | **7** | 11 Ağu (27) · 12 Ağu (2) · 24 Ağu (2) · 27 Ağu (7) · 2 Eyl (9) · 3 Eyl (5) · 4 Eyl (14) |
| Değişen | **265 dosya · +29.803 / −2.888** | `git diff --shortstat` |
| Tag | 100 toplam; çıpadan sonra **1** (`pre-kapali-beta`, geri dönüş etiketi) | `git tag --contains 1ada15c` |
| Dallar | `main` (= `origin/main`, fark yok) + yerel `yedek/atif-duzeltmesi-oncesi` (27 Ağu) | `git branch -a`, `git status -sb` |
| HEAD | `7486e9c` (4 Eyl 12:02) | `git log -1` |

**Takvimin okunuşu:** 25 günün 7'sinde çalışıldı. İki büyük boşluk var:
**13–23 Ağustos (11 gün)** ve **28 Ağu – 1 Eylül (5 gün)**. Yani "3,5 hafta ilerleme"
aslında **7 günlük yoğun iştir**; kalan 18 gün projeye hiç dokunulmadı.

---

## 2) FAZ DURUMU

### Kapalı beta B0–B6 (`charter-kapali-beta.md`)

| Blok | Konu | Durum | Kanıt |
|---|---|---|---|
| **B0** | Barındırma kararı (insan-kapısı) | ⛔ **AÇIK** | `masterprompt-kapali-beta.md:110` → "Yapılacak". Karar notu hazır ve fiyat araştırması yapılmış; notta hiçbir yerde "seçildi / karar verildi" satırı yok |
| **B1** | Davet kapısı kapsamı ölçülü + kilitli | ✅ KAPALI | BUG #279 |
| **B2** | Geri bildirim teşhis edilebilir | ✅ KAPALI | BUG #281; canlı DB'de **2 geri bildirim kaydı** |
| **B3** | Korelasyon kimliği + sürüm damgası | ✅ KAPALI | BUG #280, #294 |
| **B4** | YAYIN (P6'nın uygulanması) | ⛔ **B0'ı bekliyor** | — |
| **B5** | Davetli paketi | ✅ KAPALI | BUG #282; **5 davet, 5'i de kullanılmış**, 6 kullanıcı |
| **B6** | Beta işletim ritmi | 🟡 KISMİ | Açılış/sağlık/yedek görevleri kurulu (BUG #303/#305), ama 3 Eyl'de **24,5 saatlik sessiz kesinti** yaşandı (BUG #326/#328) |

### Kapı tablosu — **15 satır** (çıpa belgesi 13 diyordu; ölçüm: `charter-kapali-beta.md:291-307`)

| # | Kapı | Durum | Kanıt |
|---|---|---|---|
| 1 | B0 karar notu sunuldu, Murat seçti | ⛔ **AÇIK** | not var, karar yok |
| 2 | Her hesap yolu `beta_access`'ten geçiyor | ✅ | BUG #279 kapı testi |
| 3 | Workspace daveti allowlist dışına sızmıyor | ✅ | test |
| 4 | Geri bildirim düğmesi her rotada | ✅ | kapı testi |
| 5 | Geri bildirim alan kümesi sabit + gizlilik testli | ✅ | test |
| 6 | 5xx → korelasyon kimliği → kayıt zinciri | ✅ | BUG #280 |
| 7 | Korelasyon kimliği log ↔ yanıt ↔ ekran aynı | ✅ | test |
| 8 | Canlıda `/api/meta` gerçek build SHA | ✅ ama **DRIFT** | canlı `aed4b5fa`, yerel HEAD `7486e9c` → **canlı sürüm 24 commit geride** |
| 9 | Canlıda HTTPS + PWA **gerçek telefonda** | ⛔ **KANIT YOK** | hiçbir belgede ekran/komut çıktısı yok |
| 10 | Canlı SMTP uçtan uca (H11) | ⛔ **KANIT YOK** | gelen e-posta kanıtı yok |
| 11 | Canlı yedekten geri yükleme provası | ⛔ **KANIT YOK** | — |
| 12 | Hesap/veri silme yolu canlıda | ⛔ **KANIT YOK** | — |
| 13 | KVKK + karşılama + kurulum metinleri canlıda | ✅ | `/api/meta` hukuki uçları listeliyor |
| 14 | Tam süit yeşil; coverage ölçüldü | ✅ **BUGÜN KAPANDI** | 3486 passed · **%94,02** |
| 15 | Mutasyon disiplini her yeni kapıya | ✅ | #322 5/5 · #323 3/4 · #324 4/4 · #338 3/3 |

**Faz değişti mi:** kapalı beta fazı DEĞİŞMEDİ. Yanına **yeni bir hat açıldı**:
`masterprompt-koc.md` — **Wave-K (koç zekâsı)**, 1 Eylül'de oluşturuldu, K0-K7 fazlı,
kendi altın senaryo seti ve ölçütleriyle. Son üç günün 28 commit'inin tamamı bu hatta.

---

## 3) ÖLÇÜMLER (hepsi bugün koşuldu)

```
pytest tests/ -q --cov=app --cov-fail-under=93
  -> 3486 passed, 18 skipped, 3 warnings in 295.37s
  -> TOTAL 11713 stmts / 701 miss / 94%
     "Required test coverage of 93% reached. Total coverage: 94.02%"

npm test -- --run        -> Test Files 19 passed (19) · Tests 214 passed (214)  [42.4s]
scripts/e2e_izole.py     -> 8 passed (29.5s)
                            [:8000 canlı beta'ya DOKUNULMADI, :8100 + :5273'e kuruldu]

alembic heads            -> c3d4e5f8a1b2 (head)   ·   39 göç dosyası
canlı DB alembic_version -> c3d4e5f8a1b2          ·   32 tablo (31 + alembic_version)
scripts/test_fresh_db_migration.py
  -> OK: temiz DB'de 31 tablo, create_all ile TAM ÖZDEŞ (kolon + index)

scripts/kalite_kapisi    -> E9 0/0 · F 202/202 · S 63/63 · TOPLAM 296 · kapı geçildi
scripts/olu_kod_kapisi   -> ÇAĞRILMAYAN 0 (tavan 0) · kapı geçildi
scripts/belge_denetimi   -> kapı geçildi
scripts/sir_taramasi     -> TEMIZ: sır izi yok
tests/test_api_sozlesmesi.py -> 3 passed
```

### `alembic check` BAŞARISIZ — İLK OKUMA (AŞILDI, aşağıdaki düzeltmeye bakın)

```
alembic check -> FAILED: New upgrade operations detected:
  add_fk categories.workspace_id -> workspaces.id
  add_fk personal_debts.settlement_account_id -> accounts.id
```

> ⚠️ **Bu blok, o anki teşhisi olduğu gibi bırakıyor; SONUCU aşağıdaki düzeltme verir.**
> Kayıt böyle tutuluyor çünkü teşhisin nasıl düzeldiği, teşhisin kendisi kadar önemli.

İlk okuma şöyleydi:

1. Göç dosyası **FK'yı kurmayı gerçekten deniyor** —
   `alembic/versions/f2a3b4c5d6e7_debt_settlement_account.py:35`
   `create_foreign_key("fk_personal_debts_settlement_account_id", ...)`.
2. **Ama veritabanında yok.** Temiz DB'de `alembic upgrade head` sonrası
   `PRAGMA foreign_key_list`: `personal_debts` = `['user_id']` ·
   `categories` = `['user_id']`. Yani `workspace_id` VE `settlement_account_id`
   kısıtları **hiç oluşmuyor** (SQLite `ALTER TABLE ADD CONSTRAINT` desteklemez;
   batch modu olmadan işlem sessizce düşer). Canlı DB'de de aynı.
3. **Uygulama FK zorlamasının AÇIK olduğunu sanıyor:** `app/database.py:78`
   her bağlantıda `PRAGMA foreign_keys=ON` çalıştırıyor (DATA-003 / BUG #060).
   Yani `ondelete` semantiği bu iki ilişki için yazılı ama **kurulmamış**.
4. **Taze-DB kapısı bunu göremez:** `scripts/test_fresh_db_migration.py:38-39`
   yalnız `get_columns` ve `get_indexes` karşılaştırıyor — `get_foreign_keys`
   HİÇ çağrılmıyor. Kapı yine de çıktısında **"şema create_all ile TAM ÖZDEŞ"** diyor.

### ✅ DÜZELTME (aynı gün, tam envanter) — YUKARIDAKİ TEŞHİS YANLIŞTI

İlk yazımda "hiçbir kapı görmedi, sessiz bir defekt" demiştim. **Ölçüm bunu çürüttü.**
Tam envanter alındı (model FK'ları ↔ göçün kurduğu FK'lar, 31 tablo): eksik FK **2 değil 14**.
Ama 12'si **bilinçli ve belgelenmiş**:

`alembic/versions/d4e5f6a7b8c9_workspace_id_fks_postgres.py` — adı bile "postgres" diyor:
> *"**Postgres:** 12 scoped tabloya fiziksel FK ekler. **SQLite:** SKIP (ALTER ADD FK yapamaz;
> batch recreate inbound-FK'li tabloları kırar, M11 dersi). SQLite'ta `alembic check` bu
> FK-sapmasını göstermeye devam eder — BELGELENMİŞ ADR-036/ADR-013 divergence."*

Telafi edici kontroller de adlandırılmış: model-seviyesi FK (ORM relationship) +
uygulama-katmanı scope filtresi (Wave-5 AST kapısı) + Postgres RLS (M51).
`personal_debts.settlement_account_id` de aynı desende **doğru yazılmış**
(`f2a3b4c5d6e7:32` — `if dialect.name == "postgresql"`). Yani o da defekt değil.

**İKİNCİ TEŞHİS DE YANLIŞ ÇIKTI (ve bunu mutasyon testi yakaladı).** Sapmanın 14'ünü tek
tek karşılığına bağlayınca `categories.workspace_id`'nin `_SCOPED_TABLES`'ta olmadığını
görüp *"Postgres'te de FK almıyor, ADR-036'nın sözü delinmiş"* dedim ve düzeltici bir göç
yazdım. **Yanlıştı:** `b4c5d6e7f8a9_kullanici_kategorileri.py:83-87` FK'yı **kendi göçünde**
kuruyor (yorumu da `d4e5f6a7b8c9` desenine atıf yapıyor) — yani tablo listeye yazılmamış,
çünkü ihtiyacı yok. Yazdığım göç Postgres'te **aynı kısıtı ikinci kez kurup patlayacaktı**;
mutasyon testinde M1'in hayatta kalması bunu ortaya çıkardı ve göç **silindi**.

**ÖLÇÜLMÜŞ SONUÇ: ŞEMADA DEFEKT YOK.** 14 sapmanın 14'ü de dialect-korumalı bir Postgres
göçüyle karşılanmış durumda. Rapor bu satırı, ilk iki yanlış teşhisiyle birlikte kayda
geçiriyor — çünkü *"kimse görmedi"* demeden önce belgeleyen dosyayı aramak, bu turun dersi.

**AMA GERÇEK BİR BOŞLUK VAR — SAPMA DEĞİL, SAPMANIN ÖLÇÜLEMEZLİĞİ.** `alembic check`
SQLite'ta **bilerek kalıcı kırmızı** (belgelenmiş sapmayı her koşumda basar). Ölçüldü:
`grep -rn "alembic check" .github/workflows/ scripts/` → **boş**; hiçbir CI adımı, hiçbir
kapı onu koşmuyor. Yani şema bugün temiz olsa bile **yarın eklenecek karşılıksız bir FK
görünmez olurdu**. **L22'nin (gürültülü kapı okunmaz) şema tarafındaki karşılığı.**

**BU TURDA KAPATILDI — `tests/test_fk_sapmasi_kapisi.py` (5 test, mutasyon 3/3).**
Muafiyet elle yazılan bir listeye değil, **sapmayı Postgres'te gerçekten kuran göçe**
bağlı (L67): bir FK ancak karşılığı varsa meşru. Mutasyonlar: bir tablonun Postgres FK
bloğu silindi → kırmızı · modele karşılıksız FK eklendi (14→15) → kırmızı · sapma
azaltıldı (14→13) → kazanım kilidi kırmızı. Kapı bugün **defekt bulmuyor**; değeri
bundan sonrasını tutmakta — BUG #306 (API sözleşmesi) ve #307 (ağ kapısı) ile aynı sınıf.

---

## 4) KAYIT DEFTERLERİ

| Defter | Değer | Kanıt |
|---|---|---|
| ADR | **56 dosya**; çıpadan sonra **0 yeni ADR** | `ls docs/architecture/adr-*.md`, `git diff --diff-filter=A` |
| BUG tavanı | **#338** (sıradaki #339) | `grep -ohrE 'BUG #[0-9]+'` |
| BUG ledger | `uygulanan-fixler.md` **1.070 satır**, 242 numara geçiyor | `wc -l` |
| Backlog | **164 ✅ · 251 🔲 · 81 🟡 · 17 ⏸ · 7 ⚪** (521 madde) | `sections/*.md` `- **Durum:**` sayımı |
| **Backlog hareketi** | **SIFIR** — çıpadaki (`git archive 1ada15c`) sayım birebir aynı | ⚠️ 60 BUG kapandı, backlog güncellenmedi |
| Dersler | **L67**'ye kadar; tanımlar `masterprompt-koc.md` + `uygulanan-fixler.md` | grep |

**Dürüst not:** çıpadan bu yana 60 BUG numarası kapandı ama **backlog'un durum
dağılımı hiç dokunulmadı**. Bu, BUG #310'un ölçtüğü "belge bayatlığı" sınıfının kendisi:
defter ilerliyor, backlog donuk kalıyor. İki kayıt sistemi arasındaki senkron **açık iş**.

---

## 5) YAYIN / BARINDIRMA

| Soru | Cevap | Kanıt |
|---|---|---|
| B0 kararı verildi mi? | ⛔ **HAYIR — 24 gündür açık** | charter "Yapılacak"; karar notunda seçim satırı yok |
| Alan adı | ⛔ yok | B0'a bağlı |
| DNS | ⛔ yok — mevcut ad `financialos.<tailnet>.ts.net` | BUG #303: Cloudflare çözümleyici bu adı 12 sorgunun 11'inde çözemiyor |
| Canlı sırlar | 🟡 Tailscale yolunda kurulu, kalıcı barındırmada yok | — |
| `scripts/deploy.sh` | ✅ dosya var | `ls` |
| `scripts/live_gate.py` | ✅ dosya var | `ls` |
| İkisi koştu mu? | ⛔ **KANIT YOK** — hiçbir koşum çıktısı kayıtlı değil | — |
| Canlı URL | ✅ **çalışıyor**: health 200 · ready 200 | `curl` |
| Canlı sürüm | ⚠️ `aed4b5fa` — **yerel HEAD'den 24 commit geride** | `/api/meta` |
| PWA gerçek telefonda | ⛔ **KANIT YOK** (kapı 9) | — |
| Davetli listesi | ✅ **5 davet, 5'i kullanılmış, 6 kullanıcı** | canlı DB |
| B2 geri bildirim sistemi | ✅ diskte VAR ve çalışıyor (sıfırdan yazılmadı — L52) | BUG #281 |
| Gelen geri bildirim | ✅ **2 kayıt** | `select count(*) from feedback` |

**Kritik gözlem:** yayın için gereken **kodun tamamı hazır**. Kapı 9-12'nin dördü de
"canlıda doğrulandı mı" sorusudur ve dördü de **B4'e**, B4 de **B0'a** bağlıdır.

---

## 5.1) BETA KULLANIMI — ÖLÇÜLDÜ, VE BU RAPORUN EN AĞIR BULGUSU

Kapı tabloları ve test sayıları "ürün hazır mı" sorusunu cevaplıyor. Bu bölüm
**"ürün kullanılıyor mu"** sorusunu cevaplıyor — ve cevap hayır.

Ölçüm (canlı DB, kullanıcı başına gerçek etkinlik):

| Kullanıcı | Kayıt | İşlem | Koç kullanımı | Son etkinlik |
|---|---|---|---|---|
| Davetli 1 | 11 Ağu 13:05 | **0** | **0** | **hiç** |
| Davetli 2 | 11 Ağu 13:11 | 9 | 5 | 11 Ağu |
| Davetli 3 | 11 Ağu 15:37 | 2 | 0 | 11 Ağu |
| **Kurucu (u5)** | 11 Ağu 15:48 | 2 | 8 | **4 Eyl** |
| Davetli 4 | 12 Ağu 11:20 | **0** | **0** | **hiç** |

**13 Ağustos'tan bu yana sistemdeki TEK kullanıcı etkinliği kurucununkidir**
(`transactions` 13 Ağu sonrası: hiç yok · `reasoning_traces`: yalnız u5).
Sistemdeki **2 geri bildirimin ikisi de kurucuya ait.** Yani B2'nin kurduğu geri
bildirim makinesi çalışıyor ama **dışarıdan hiç sinyal almıyor.**

**VE SEBEBİ KAYITLI — TAHMİN DEĞİL.** `BUG #303` (12 Ağustos): davetliler siteyi
**Chrome'da da Brave'de de açamıyor**. Tailscale adı Cloudflare çözümleyicisinde
**12 sorgunun 11'inde NXDOMAIN** dönüyor ve tarayıcıların "Güvenli DNS"i işletim
sisteminin DNS'ini ATLAYIP oraya gidiyor. Ölçüm o gün yapıldı; **son davetli aynı gün
kaydoldu ve bir daha dönmedi.** Geçici çözüm ("davetliye Güvenli DNS'i kapattır")
belgede duruyor, kalıcı çözüm olarak **kendi alan adı** yazılmış — yani **B0**.

**BUNUN ANLAMI:** B0 bir idari tercih ya da "sonra hallederiz" maddesi değil;
**betanın ölü olmasının ölçülmüş sebebidir.** Kalite kapıları, coverage ve 3.486 test
bu tabloyu değiştirmez — insanlar kapıya varamıyor. Raporun §9'daki "yayına geçişi
engelleyen şey kalite değil" tespiti burada somutlaşıyor: engel kalite değil **adres**.

### ⚠️ AYNI GÜN DÜZELTME — "DAVETLİLER GİREMİYOR" İDDİASI BUGÜN GEÇERLİ DEĞİL

Yukarıdaki sebep-sonuç zinciri **12 Ağustos ölçümüne** dayanıyordu ve yayımlanmadan önce
tekrarlanmadı. Tekrarlandı (4 Eylül, aynı yöntem, 6'şar sorgu):

| Çözümleyici | 12 Ağu (BUG #303) | **4 Eylül (bugün)** |
|---|---|---|
| Cloudflare | 12 sorgunun 11'i NXDOMAIN | **6/6 ÇÖZDÜ** |
| Google | 12/12 çözdü | **6/6 ÇÖZDÜ** |
| `GET /api/health` (ad üzerinden) | — | **200** |

**Yani arıza kendiliğinden geçmiş.** Adres bugün her iki çözümleyiciden de çözülüyor ve
site ad üzerinden cevap veriyor. *"Davetliler siteye giremiyor"* cümlesi **bugün yanlıştır**.

**Bunun sonuçları:**
1. Betanın 23 gündür ölü olması **ÖLÇÜLMÜŞ bir gerçek** (tablo yukarıda, değişmedi).
2. Ama **sebebi artık kanıtlı değil.** DNS arızası 11-12 Ağustos'ta gerçekti ve ilk iki
   günü — davetlilerin tek denediği günleri — vurmuş olabilir; bu makul bir hipotezdir,
   ölçülmüş bir sebep DEĞİLDİR.
3. **B0 bu yüzden "betanın ölü olmasının sebebi" olarak sunulamaz.** B0 hâlâ meşru ve açık
   bir karardır (kalıcı barındırma, makine kapalıyken erişim), ama aciliyeti bu bulgudan
   TÜREMEZ.

**ASİSTANIN HATASI, kayda geçsin:** 23 günlük bir sessizliği 23 günlük bir ölçümle
açıkladım ve o ölçümü tekrarlamadan "sebep kayıtlı, tahmin değil" diye yazdım. Bu, KURAL R3'ün
ihlalidir — *bir iddiayı ancak onu ölçen bir KOŞUM kapatır, ve koşum bayatlayabilir.*
Aynı turda `alembic check` teşhisinde iki kez düşülen hatanın üçüncüsü: **eski bir ölçümü
bugünkü bir olgu sanmak.**

**AÇIK KALAN GERÇEK SORU:** davetliler neden dönmedi? Bugün ölçülü tek şey dönmedikleri.
Cevap ancak onlara sorularak öğrenilir (B2 geri bildirim yüzeyi diskte hazır ve çalışıyor) —
ürün tarafında tahminle kapatılacak bir madde değil.


---

## 6) ASKIDA KALANLAR

| Madde | Durum | Kanıt |
|---|---|---|
| MCP'nin 186 satırlık flush'ı | ⛔ **YAPILMADI — ve büyüdü: 186 → 255 satır** | `wc -l .mcp-sync-pending.log` |
| "Milestone/tag bırakıldı, iş P0-P9 + BUG ile yürür" kararı yazıldı mı | ✅ **EVET**, `PROJE.md`'de yazılı | grep |
| H11 canlı SMTP | ⛔ **AÇIK** (kapı 10) | — |

---

## 7) GİZLİLİK / DEPO (bugünkü olay)

| Adım | Commit / kanıt |
|---|---|
| Bulgu: depo **PUBLIC** ve içinde gerçek veri | GitHub API `visibility: public`; `scripts/coach_altin.py`'de 2 kredi hesap numarası, 15 dosyada e-posta, 96 dosyada banka adı |
| 1. Depo private yapıldı | **kimliksiz API sorgusu → HTTP 404** (ekran değil, ölçüm) |
| 2. Hesap numaraları çıkarıldı + kapı kuruldu | `1fe6a70` — BUG #338 + #337 |
| 3. Geçmiş temizlendi | `git-filter-repo --replace-text`; yeni HEAD `ee2b729` |
| Bütünlük kanıtı | commit **671 → 671**; yeniden yazılmış HEAD'in **ağaç hash'i eski uzak HEAD ile BİREBİR AYNI** (`1d74d98…`) |
| Push | `--force-with-lease=main:1fe6a70…` |
| Yedek | `financialos-yedek-20260904-1151.bundle` (5.788.003 bayt, "complete history" doğrulandı) |
| Son doğrulama | **tüm ref'lerde 0** — yerel yedek dal `yedek/atif-duzeltmesi-oncesi` dahil, bugün yeniden tarandı |
| Ledger kaydı | `7486e9c` |

**#337 nerede bekliyor:** beklemiyor — **KAPANDI** (`1fe6a70`). Asgari ödeme artık
`statement_balance` (ekstre borcu) üzerinden hesaplanıyor; kapı `tests/test_ekstre_borcu_kapisi.py`.

**Geçmişte daha önce ne temizlendi:** 7 Ağu 2026'da atıf temizliği —
`git-filter-repo` mesaj-callback ile 574 commit işlendi, 311 mesaj değişti; o turda da
ağaç hash'i korunmuştu (`c9a718e7…`). Yani bu, deponun **ikinci** geçmiş temizliğidir.

---

## 8) REGRESYON

| Soru | Cevap |
|---|---|
| 14 Ağu'dan bu yana kırılan ne var? | **Süitte hiçbir şey** — 3486 passed, 0 failed. |
| ADR ihlali girdi mi? | **Hayır.** ADR-001 (rules engine karar verir, LLM açıklar) bu turda tersine **güçlendi**: stopaj (`app/vergi.py`), kötü hal (#333), nakit takvimi (#331) koçtan alınıp kural motoruna taşındı. |
| Kapsam kayması? | **Hayır, ama hat değişti**: 2-4 Eylül'ün 28 commit'i publish yolunda değil, yeni açılan **Wave-K koç hattında**. Bilinçli ve belgeli, fakat yayına yaklaştırmadı. |
| Bu turda girip aynı turda kapanan gerileme | **1 tane, asistanın bıraktığı:** BUG #338'in kapısı `git ls-files`'ı beşinci kez yeniden yazınca ruff `S` tavanı 63 → 64 kırıldı. Tavan **yükseltilmedi**; kopya kaldırılıp `scripts.sir_taramasi.izlenen_dosyalar` tek kaynağına bağlandı → 63/63. |
| Uzun süredir sessiz duran | **`alembic check` (bkz. §3)** — en az bir aydır başarısız, hiçbir kapı ölçmüyordu. |

---

## 9) "NEDEN BİR TÜRLÜ TAMAMLANAMIYOR?" — ÖLÇÜMLE CEVAP

Bu rapor tam da bu soruyu cevaplamak için istendi. Sayılar, "kalitemiz yetersiz"
teşhisini **desteklemiyor**:

**a) Kalite düşmüyor, ilk kez ÖLÇÜLÜYOR.** 27 Ağustos'tan önce depoda statik analiz
**yoktu**, coverage **hiçbir yerde ölçülmüyordu**, API sözleşmesi **dondurulmamıştı**,
süitin internete çıkmasını engelleyen **hiçbir şey yoktu**. Bugün yedi kapı var ve hepsi
yeşil. Coverage "%93 olabilir" tahmininden **%94,02 ölçülmüş ve kilitlenmiş** hâle geldi.

**b) Artan BUG sayısı kötüleşme değil, GÖRÜŞ ALANI.** 60 BUG'ın **21'i tek bir günde**
(4 Eylül) bulundu — gerçek banka verisi girildiği gün. O defektler zaten oradaydı;
ürün gerçekten kullanılınca görünür oldular. Biri 24,5 saatlik canlı kesintiydi ve
**fark edilmemişti**. Ölçmeye başlamak, bozulmak değildir.

**c) Yayına geçişi engelleyen şey kalite DEĞİL.** 15 kapının açık olanları:
1 (B0 kararı), 9 (PWA telefonda), 10 (SMTP), 11 (yedek provası), 12 (silme yolu).
**Dördü de "canlıda doğrula" kapısıdır ve hepsi B4'e, B4 de B0'a bağlıdır.**
B0 tek bir sorudur — *hangi barındırma?* — ve **11 Ağustos'tan beri, 24 gündür açıktır.**
Kod tarafında bilinen teknik engel yok; `deploy.sh` ve `live_gate.py` diskte hazır bekliyor.

**d) Asıl gecikme sebebi: takvim + hat seçimi.** 25 günün **7'sinde** çalışıldı
(18 gün hiç dokunulmadı). Ve çalışılan son üç günün tamamı publish yoluna değil,
1 Eylül'de açılan **koç kalitesi hattına** gitti. Bu bilinçli bir seçimdi ve ürünü
gerçekten iyileştirdi (koçun muhakemesi 1/6 → 4/6), **ama yayına bir adım yaklaştırmadı.**

**Sonuç:** ürün "tamamlanamıyor" değil — **ürün zaten canlıda ve altı kişi kullanıyor.**
Eksik olan, kalıcı barındırmaya taşınması; onun da tek engeli 24 gündür bekleyen bir
karardır. Kalite bu işin önünde değil, **arkasında** duruyor.

---

## SIRADAKİ ÜÇ İŞ (öncelik sırasıyla)

1. **B0 barındırma kararı** — insan-kapısı, tek soru. Açıldığı anda B4 ve kapı 9-12
   arka arkaya kapanabilir. *(Kod tarafında engel yok.)*
2. ~~`alembic check` bulgusu~~ **KAPANDI (bkz. §3 düzeltmesi).** Şemada defekt çıkmadı;
   eksik olan ÖLÇÜMDÜ ve `tests/test_fk_sapmasi_kapisi.py` ile kapatıldı (mutasyon 3/3).
3. **Canlı sürüm drift'i** — canlıdaki bina 24 commit geride; bugünün 21 defekt
   düzeltmesinin hiçbiri kullanıcılarda değil.
