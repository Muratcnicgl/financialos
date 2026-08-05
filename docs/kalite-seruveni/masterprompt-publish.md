# MASTERPROMPT — PUBLISH YOLU (Wave-9)

> **Bu dosya bir plan değil, bir TALİMATTIR.** asistan araci her oturumda bu dosyayı okur ve
> buradaki protokolü uygular. "Kaldığımız yerden devam" = bu dosyanın §11 DURUM TABLOSU'ndaki
> ilk ⬜/🟡 satırdan devam etmek demektir.
>
> **Sürüm:** v2.0 · **Yazıldı:** 2026-08-04 · **Revize:** 2026-08-05 (41 bug sonrası ders-kuralları) · **Sahip:** Murat İçgil · **Yürütücü:** asistan araci
> **Değişiklik günlüğü:** §12 (yalnız İLERİ yönlü — kapsam daraltma/kalite düşürme yasak)

---

## §0. GÖREVİN TANIMI (tek cümle)

FinancialOS'u, **yabancı insanların gerçek finansal verisini** taşıyabilecek kalitede,
**kapalı betaya açılabilir** ve ardından **publish edilebilir** hale getirmek — hiçbir adımı
varsayımla, geçiştirerek veya "sonra bakarız" diyerek atlamadan.

**Bu bir finans uygulamasıdır.** Bar, sıradan bir CRUD uygulamasının barı DEĞİLDİR:
bir izolasyon açığı = birinin maaşının/borcunun yabancıya görünmesi. Bir hesap hatası =
birinin yanlış finansal karar alması. Bu iki cümle, aşağıdaki her kapının gerekçesidir.

---

## §1. DEĞİŞMEZ KURALLAR (her görevde geçerli, istisnasız)

Bunlar `PROJE.md`'den devralınır ve bu goal boyunca **sertleştirilmiş** haliyle uygulanır:

| # | Kural | Bu goal'de anlamı |
|---|---|---|
| K1 | Türkçe, direkt, dalkavukluk yok | Rapor = bulgu + kanıt. "Harika gidiyoruz" cümlesi yok. |
| K3 | asistan araci'un yapabildiğini kullanıcıya delege etme | Yalnız §9'daki İNSAN-KAPISI listesi delege edilir. Başka hiçbir şey. |
| K12 | Kalite MUTLAK, basitlik gerekçe değil | "MVP yeter / pratik / hızlı / şimdilik" → **yasak gerekçe**, reddedilir. |
| R3 | Memory vs disk çelişirse **disk** gerçek | Her iddia `git`/`pytest`/`alembic`/`inspect`/`curl` ile doğrulanır. |
| D1 | Yeni mimari karar öncesi 2-3 sektör referansı | ADR yazılmadan mimari karar uygulanmaz. |
| K10 | "sen seç" → üç boyut muhakemesi | MUHAKEME + BENİ DÜŞÜN + GENELİ DÜŞÜN. |
| ADR-001 | Rules Engine karar verir, LLM açıklar | Hiçbir kapıyı LLM'e sordurarak geçme. |

### §1.1 Bu goal'e özel EK KURALLAR (Murat'ın 4 Ağustos direktifi)

- **VARSAYIM YASAK.** "Muhtemelen çalışıyor / zaten vardır / test ediliyordur" cümlesi kuruluyorsa,
  o cümle bir **görev**e dönüşür ve doğrulanır. Doğrulanamayan her şey `KANIT YOK` olarak kaydedilir.
- **GEÇİŞTİRME YASAK.** Bir kapı kısmen geçildiyse **geçilmemiştir**. Kısmi = ⬜.
- **TEMBELLİK YASAK.** "Bu dosya büyük, örnek birkaçına bakayım" → yasak. Kapsam tamsa tam taranır.
- **ZAMAN İSRAFI ÖNEMSİZ, KALİTE İSRAFI YASAK.** Uzun süren doğru yol > kısa süren yaklaşık yol.
- **DURMAK YOK.** Bir faz bitince rapor + bir sonraki faza geçiş aynı turda başlar. Onay beklenmez
  (Murat tüm işlemleri önceden onayladı) — **tek istisna §9 İNSAN-KAPISI**.
- **GERİLEME YASAK.** Bu masterprompt yalnız ileri yönlü güncellenir (§12).

### §1.3 DERS-KURALLARI L1-L10 (v2.0 — 41 bug'ın ardından, YALNIZ EKLENİR)

> Not: `D1` §1'de **sektör referansı** kuralıdır; karışmasın diye ders-kuralları **L** ile numaralanır.

Bu kurallar teorik değil: her biri bu goal'de **gerçekten yaşanmış** bir hatadan çıkarıldı.
Yeni bir iş yaparken bu listeyi bir kontrol listesi gibi geçir.

| # | Kural | Nereden çıktı |
|---|---|---|
| L1 | **"İkinci kullanıcı geldiğinde ne bozulur?"** — her özellik için sor. Tek kullanıcıda görünmeyen hata, ikinci kullanıcıda VERİ SIZINTISIDIR. | #162 (çapraz-kullanıcı kural sızıntısı), #163 (yalnız ilk kullanıcı), #188 (paylaşılan kota) |
| L2 | **Sessiz kabul, en kötü hatadır.** Geçersiz girdi/ayar kabul edilirse kullanıcı KORUNDUĞUNU SANIR. Yazma anında gürültüyle reddet. | #192 (bozuk kural), #197 (geçersiz saat dilimi), #164 (bozuk yedek) |
| L3 | **Yeşil kapı ≠ çalışan kapı.** Her statik/otomatik kapıya, kapının kendisini sınayan meta-test yaz. | #162'yi kaçıran Wave-5 kapısı |
| L4 | **Provasız güvence yoktur.** "Yedeğimiz var / migration çalışır / deploy hazır" iddiaları ancak TATBİKATLA doğrulanır. | H14 (geri yükleme), #196 (veri-dolu migration), prod provası |
| L5 | **Production varsayılanları FAIL-CLOSED olmalı.** Operatör hiçbir şey yazmazsa sistem güvenli tarafta kalmalı. | #171 (AUTH_ENABLED), #199 (kayıt modu), #170 (sıfırlama token'ı) |
| L6 | **Sertleştirirken geliştirmeyi kilitleme.** Kapsamı prod'a daralt; dev/test akışı bozulursa kapsam yanlıştır. | #202 ilk denemesi 25 testi kırdı → kapsam prod+açık-kayda daraltıldı |
| L7 | **Kapılar birbirini etkileyebilir.** Sıra/yan etki düşün; yoksa kapı YANLIŞ ALARM verir. | #198 (rate-limit testi login kovasını tüketiyordu) |
| L8 | **Belgelenen ≠ ulaşılabilir.** Metin/ayar var diye erişilebilir sanma; canlı yolu ölç. | #191 (KVKK metni prod imajında yoktu) |
| L9 | **Kod ile doküman arasına test koy.** Env adı/sürüm/envanter gibi sözleşmeler elle senkron kalmaz. | #189 (OAuth env adları), #200 (CHANGELOG↔sürüm), veri-işleyen envanteri |
| L10 | **Yalnız yerelde görünmeyeni ara.** Sunucu/konteyner/çok-worker/başka saat dilimi farklı davranır. | #169 (TZ), #182 (proxy/çok-worker), #185 (state process-yerel) |
| L11 | **"Hepsini tarar" diyen kapı, KAÇ TANE taradığını da ölçmeli.** Kapsamı üçüncü-taraf iç yapısından (ör. `app.routes`) türetme; kararlı kamu sözleşmesinden türet ve **taban assert et**. Aksi halde bir kütüphane sürümü kapıyı sessizce körleştirir, kapı yeşil kalır. L3'ün meta-testi bile bunu kaçırır — meta-test kapının MANTIĞINI sınar, KAPSAMINI değil. | #217 (FastAPI 0.141 `_IncludedRouter` → 87 uçtan 1'i taranıyordu; izolasyon kapısı 0 ölçüyordu, ikisi de yeşildi) |
| L13 | **Kurulum adımını denetleyen bir kapı yoksa, o adım eninde sonunda atlanır.** "Runbook'ta yazıyor" bir kapı değildir. Kod ile ÇALIŞAN sistemin durumu (şema sürümü, uygulanmış migration, yapılandırma) arasına startup'ta fail-fast koy — aksi halde sistem yarım çalışır ve sağlık ucu yeşil kalır. | #222 (canlı DB 9 migration geride; koç onayı 500 verirken `/api/health` yeşildi) |
| L12 | **Hata yolu da bir ürün yüzeyidir.** Panel/akış "veri yok" halinde test edilip "istek patladı" halinde test edilmiyorsa yarısı sınanmamıştır — çökme ve **istek döngüsü** oradan çıkar. | #218 (toast kimliği → sonsuz istek), #219 (hata → state null → panel çöktü) |

---

---

## §1.2 KALICI HATIRLATMA LİSTESİ ("Murat unutsa da sistem hatırlar")

Murat'ın direktifi: *"bu ve bunun gibi detayları da masterprompt'u geliştirirsin… ben unutsam da
sen hatırla diye. Ben bir örnek vereceğim ama nicelerini de sen eklersin."*

Kural: **bu liste yalnız büyür.** Akla gelen her "publish öncesi bu da olmalı" maddesi buraya
yazılır, sonra ilgili faza görev olarak bağlanır. Buraya yazılmayan şey unutulmuş sayılır.

| # | Madde | Kaynak | Bağlı faz | Durum |
|---|---|---|---|---|
| H1 | **Yeni kullanıcı kendi verisini + kendi öznel kurallarını kurabilmeli** — sistem tek kişinin OS'u olmaktan çıkıp ürün olmalı | Murat (4 Ağu) | P3.5 | ✅ kayıt→boş dünya→kendi hesabı→kendi kuralı (dayatılan) uçtan uca testli; kalan: kişiselleştirme alanları (H4) |
| H2 | Kodda/prompt'ta gerçek kişi adı, banka markası, kişisel senaryo kalmamalı (statik kapı ile kilitle) | Claude (ölçüldü) | P3.5.1 | ✅ 45 iz temizlendi (yorum/docstring + kullanıcıya görünen placeholder); kapı TÜM app/+frontend/src |
| H3 | Kullanıcının yazdığı kırmızı çizgi, koddaki MC1 kadar sert dayatılmalı | Claude | P3.5.2 | ✅ BUG #192 — rules-as-data, aksiyon öncesi kod-seviyesi dayatma (11 test) |
| H4 | Para birimi / dil / saat dilimi / kategori seti kullanıcı başına | Claude | P3.5.3 | 🟡 **saat dilimi TAMAM** (BUG #197 — davranışsal); para birimi/locale **alan olarak** var, görüntüleme aşaması ADR-042 ile P8 öncesine planlandı |
| H5 | Boş-durum kırılmamalı + **isteğe bağlı** demo veri (tek tuşla sil) | Claude | P3.5.5 | ✅ BUG #194 — `/api/onboarding/demo`; kaldırma KULLANICININ verisine dokunmaz (testli) |
| H6 | Hesabını silen kullanıcının verisi **gerçekten** silinmeli (KVKK "unutulma"), yedeklerdeki durum yazılı olmalı | Claude | P3.4 / P4.4 | ✅ **BUG #204** — KIRIKTI: verisi olan kullanıcı hesabını silemiyordu (FK ihlali). Şema-türetimli determinist silme + 4 test |
| H7 | Veri dışa aktarma **taşınabilir** formatta (JSON/CSV) ve tam olmalı | Claude | P3.4 | ✅ doğrulandı (14 tablo, goal çocukları dahil) |
| H8 | Kullanıcı başına LLM maliyet tavanı — bir kullanıcı bütçeyi tüketip diğerlerini kilitleyememeli | Claude | P3.1 | ✅ ADR-041 / BUG #188 |
| H9 | Koça yazılan metin **prompt injection** taşıyabilir; koç başkasının verisine ulaşamamalı | Claude | P2.8 | 🟡 başkasının verisine ULAŞAMIYOR (doğrulandı); enjeksiyon yüzeyi sınırlandı (#177), tam ayrıştırma açık |
| H10 | E-posta şablonları ürün kimliğiyle konuşmalı, kişisel imza taşımamalı | Claude | P3.5.1 | ✅ **BUG #205** — şifre sıfırlama şablonunda kişisel gmail vardı; `SUPPORT_EMAIL` + kapı genişletildi |
| H11 | Şifre sıfırlama/oturum akışı gerçek e-posta ile uçtan uca denenmeli (SMTP canlı) | Claude | P6.3 | ⬜ |
| H12 | Kayıt sırasında KVKK rızası sürüm/tarih ile saklanmalı (mevcut) + metin **yayında erişilebilir** olmalı | Claude | P4.3 | ✅ BUG #191 (v2) |
| H13 | "Yatırım tavsiyesi değildir" uyarısı koç arayüzünde de görünmeli (yalnız sözleşmede değil) | Claude | P4.2 | ✅ koç paneli + kayıt ekranı |
| H14 | Yedekten **geri yükleme provası** yapılmadan yedek sayılmaz | Claude | P5.1 | ✅ SQLite + **PostgreSQL (prod yolu)** provası otomatik koşuyor |
| H15 | Beta kullanıcısının bildirdiği hata, geliştiriciye **kullanıcı verisi sızmadan** ulaşmalı | Claude | P7 | ✅ **BUG #209** — geri bildirim kimseye ULAŞMIYORDU; `scripts/beta_triage.py` (hata kayıtlarıyla yan yana, e-posta maskeli) |
| H16 | Fiyat sağlayıcıları (TEFAS/BIST/döviz) çöktüğünde uygulama çalışmaya devam etmeli, sayı **bayat** işaretlenmeli | Claude | P5.2 | ✅ **BUG #211** — fon/hisse zaten bayat işaretliydi (`fund_tracker.is_stale` → Cockpit "N eski"); **döviz** kör noktaydı: sağlayıcı düşer düşmez kur TAMAMEN kayboluyordu. Son bilinen değer artık `bayat`/`yas_dakika` ile döner, koç "şu anki" DEMEZ, 12 saatten eskisi hiç sunulmaz (8 test) |
| H17 | Çok kullanıcı aynı anda koç kullanınca sağlayıcı kotası/kilit sorunu olmamalı | Claude | P3.1 / P8 | ✅ **BUG #212** — iki defekt: (a) kota akışı "oku → LLM çağır → yaz" olduğu için hakkı 1 kalan kullanıcı paralel istekle tavanı deliyordu (ölçüldü: `[200,200,200]`); rezervasyon desenine geçildi. (b) muhasebe etiketi `FallbackProvider`'ın **paylaşılan** durumundan okunuyordu → `fallback(gemini)` limit tablosunda yok → günlük kota koruması sessizce ölüydü (5 test) |
| H18 | Kullanıcı silme/çıkarma sonrası workspace sahipliği ortada kalmamalı | Claude | P3.4 | ✅ **BUG #206** — VERİ KAYBI: aile workspace'i sahibiyle siliniyordu (eşin verisi yok oluyordu). Sahiplik devri + 3 test |
| H19 | **`alembic/env.py` config URL'ini yok sayıyor** — test/script içinden migration çağrısı GERÇEK DB'ye gidebilir (BUG #196) | Claude (ölçüldü 5 Ağu) | P5.4 | ✅ düzeltildi + veri-dolu migration provası (4 test) |
| H20 | Onboarding UI: demo veri + ilk-kurulum rehberi arayüze bağlanmalı | Claude | P3.3 | ✅ Cockpit'te boş-durum kartı (sıralı yol + örnek veriyle gez/kaldır) |
| H21 | Kullanıcı-tanımlı kural arayüzü: kural tiplerini UI'dan seçebilmeli | Claude | P3.5.2 | ✅ kırmızı-çizgi formunda "otomatik uygulansın mı?" seçimi (3 tip) |
| H22 | **Hiçbir güvenlik sınırı tek katmanda (ters vekilde) yaşamamalı** — nginx atlanabilir, yapılandırma sessizce değişebilir | Claude (ölçüldü 5 Ağu) | P2.9 | ✅ **BUG #213** — gövde sınırı YALNIZ `client_max_body_size 1m` idi; uygulama katmanına taşındı (chunked dahil), nginx şablonu testle kilitlendi |
| H23 | **Operatör betanın kullanılıp kullanılmadığını görebilmeli** — beta'nın en olası başarısızlığı gürültülü çöküş değil SESSİZ TERK'tir | Claude (ölçüldü 5 Ağu) | P7/P8 | ✅ **BUG #214** — yalnız şikâyet edeni gören `beta_triage` vardı; `scripts/beta_metrics.py` (onboarding hunisi, sessiz terk, tutunma, koç hata oranı — **yalnız sayı, PII testle yasak**) |
| H24 | **Kullanıcının GÖRDÜĞÜ katman da boş/hata durumunda sınanmalı** — backend uçları sağlam diye arayüz sağlam değildir; kullanıcı beyaz ekran görür, süit yeşil kalır | Claude (ölçüldü 5 Ağu) | P3.2 | ✅ **BUG #218/#219** — 13 panel hem boş-veri hem hata yolunda taranıyor (`empty-state` + `error-state`, 54 test); mock'lar tahmin değil **gerçek boş-kullanıcı cevapları** (fixture + sözleşme kayması kapısı) |
| H25 | **Kapsam ölçülmeden kapı sayılmaz** — "hepsini tarar" diyen her kapıya taban (minimum sayı) assert et; kütüphane sürümü kapıyı sessizce körleştirebilir | Claude (ölçüldü 5 Ağu) | P0/P1 | ✅ **BUG #217** — iki kapı (boş-durum taraması + izolasyon matrisi kapsamı) fiilen ölüydü; envanter OpenAPI'ye taşındı + taban assert (L11) |

---

## §2. "PUBLISH EDİLEBİLİR" TANIMI (Definition of Done)

Publish tek bir olay değil, **üç kapılı** bir merdivendir. Her basamak, bir öncekinin kapıları
yeşil olmadan açılmaz.

### Basamak A — KAPALI BETA (davetli, 3-10 kişi, tanıdıklar)
Gereksinim: veri izolasyonu ispatlı, güvenlik taban seviyesi geçilmiş, maliyet kontrolü var,
hukuki taban metinleri var, canlı ortam ayakta ve yedekli.
→ Fazlar: **P0, P1, P2, P3, P4, P5, P6, P7**

### Basamak B — AÇIK BETA (bağlantıyı bilen herkes, kayıt açık)
Gereksinim: A'nın tüm kapıları + gerçek kullanıcı davranışıyla sınanmış operasyon (hata izleme,
kota, kötüye kullanım savunması, destek/geri bildirim döngüsü kanıtlı işliyor).
→ Fazlar: **P8**

### Basamak C — PUBLISH (duyuru / Play Store TWA / dizinlere ekleme)
Gereksinim: B'nin tüm kapıları + sürüm yönetimi, geri alma provası, dokümantasyon, destek kanalı.
→ Fazlar: **P9**

**Bu goal'in hedefi: A ve B'nin TAMAMI + C'nin teknik hazırlığı.**

---

## §3. FAZ HARİTASI

Her faz: **GİRİŞ ŞARTI → GÖREVLER → ÇIKIŞ KAPISI (kanıtlı) → ÇIKTI**.
Kapı kanıtı **komut + gerçek çıktı** demektir; "yaptım" demek kanıt değildir.

---

### P0 — TEMEL DOĞRULAMA (baseline)
**Giriş:** yok (ilk faz).
**Görevler:**
1. Tam test süiti koş, gerçek sayıyı kaydet (pytest + vitest + e2e).
2. `alembic upgrade head` temiz DB'de koş (`scripts/test_fresh_db_migration.py`).
3. `git status` temiz mi; bekleyen yerel değişiklik varsa karara bağla (commit / revert).
4. Mevcut açık borçları listele: `KANIT YOK` kayıtları, açık backlog P0/P1 maddeleri.
**Çıkış kapısı:** ✅ tüm testler yeşil + migration temiz + çalışma ağacı bilinçli durumda.
**Çıktı:** bu dosyada §11 tablosunun ilk satırı + baseline sayıları.

---

### P1 — ÇOK-KULLANICI VERİ İZOLASYONU (#1 RİSK)
**Giriş:** P0 yeşil.
**Neden #1:** Tek-kullanıcı kurulumda izolasyon hataları **görünmezdir**; ikinci gerçek kullanıcı
girdiği an veri sızar. Wave-5'te statik+runtime kilit kuruldu ama kapsamı **eksikti** (bkz. BUG #162).

**Görevler:**
1. **Statik tam tarama:** `app/**/*.py` içindeki HER scoped-model sorgusu (`db.query(M)`, `select(M)`)
   üç kategoriden birine girmeli: (a) scope'lu, (b) sahiplik doğrulanmış id-lookup, (c) açık
   `# scope-exempt: <gerekçe>`. Kategorisiz tek satır kalmayacak.
2. **Statik gate'i kalıcılaştır:** `tests/test_scope_enforcement.py` genişletilir — **filtresiz sorgu**
   ihlali de testi kırar (mevcut gate yalnız scope'suz `user_id ==` yakalıyordu; #162'yi kaçırdı).
3. **Runtime çapraz-kullanıcı matrisi:** iki gerçek kullanıcı (A, B) + **her yazma/okuma endpoint'i**
   için B'nin token'ıyla A'nın kaynağına erişim denemesi → 403/404 beklenir. Endpoint listesi
   `app.main`'in route tablosundan **otomatik türetilir** (yeni endpoint eklenince test kendiliğinden kapsar).
4. **Arka plan katmanları:** scheduler/cron, coach_insights, backfill, action_executor, goal_rules —
   kullanıcı sınırını aşan iş var mı, her biri ayrı doğrulanır.
5. **RLS (PostgreSQL) ikinci savunma:** `tests/pg_gate.py` yeşil; RLS politikası kapsamdaki her tabloda.
6. **Bulunan her açık:** BUG numarası + TDD (önce kırmızı test) + fix + ledger.
**Çıkış kapısı:** ✅ statik gate yeşil + otomatik endpoint matrisi yeşil (atlanan endpoint sayısı 0
veya her atlama gerekçeli) + pg RLS gate yeşil + açık bug 0.
**Çıktı:** `docs/kalite-seruveni/izolasyon-denetimi-raporu.md`.

---

### P2 — GÜVENLİK REVIEW
**Giriş:** P1 yeşil.
**Görevler (her başlık ayrı kanıtlanır):**
1. **Kimlik/oturum:** JWT süre/refresh/iptal (`RevokedToken`), şifre politikası, reset akışı,
   OAuth callback state/PKCE, oturum sabitlemesi.
2. **Yetki:** rol matrisi (owner/editor/viewer) her yazma endpoint'inde dayatılıyor mu (BUG #160 dersi).
3. **Girdi:** Pydantic sınırları, para alanları (`schema_types` sonlu-değer), SQL enjeksiyonu
   (raw `text()` kullanımları), XSS (frontend'de `dangerouslySetInnerHTML` var mı), yol/dosya.
4. **Sırlar:** `.env.prod` fail-fast (BUG #157), repo'da sızmış sır taraması (git geçmişi dahil),
   log'a sır/PII sızması.
5. **Taşıma/başlıklar:** HTTPS zorunluluğu, HSTS/CSP/X-Frame, CORS listesi prod'da dar mı, cookie flag'leri.
6. **Oran sınırlama:** login/register/reset/coach uçlarında bucket'lar; brute-force senaryosu testi.
7. **Bağımlılık:** `pip-audit`/`npm audit` — kritik/yüksek açık 0 veya gerekçeli.
8. **LLM'e özel:** prompt injection (kullanıcı metni koça gidiyor), koçun başkasının verisini
   bağlama alması, `propose_action` ile yetkisiz yazma (KURAL SIFIR + Master Checkpoint).
**Çıkış kapısı:** ✅ 8 başlığın her biri kanıtlı; kritik/yüksek bulgu 0; orta bulgular ya kapatılmış
ya da ADR/backlog'a gerekçeli kaydedilmiş.
**Çıktı:** `docs/kalite-seruveni/guvenlik-review-publish.md`.

---

### P3 — ÇOK-KULLANICI OPERASYONEL GERÇEKLİK
**Giriş:** P2 yeşil.
**Görevler:**
1. **Per-user LLM maliyet/kota guard'ı** — koç mesajı başına 2 LLM çağrısı (iki-geçiş mimarisi).
   Kullanıcı başına günlük/aylık limit + limit aşımında **nazik** davranış (koç kapanmaz, düşer).
   `ApiCallLog` şu an yalnız kayıt tutuyor → **dayatma** eklenecek. ADR yazılacak.
2. **Yeni kullanıcı sıfırdan çalışıyor mu:** kayıt → personal workspace → boş cockpit → ilk hesap →
   ilk işlem → koç anlamlı cevap. **Boş-veri hali** her panelde kırılmadan görünmeli (0/None/NaN).
3. **Onboarding akışı:** ilk giriş rehberi + örnek veri seçeneği + "buradan başla" yönlendirmesi.
4. **Hesap yaşam döngüsü:** şifre değiştir, e-posta doğrula, **hesabı sil (veri dahil)**, **veriyi dışa aktar**.
5. **Kötüye kullanım:** kayıt spam'i, davet suistimali, dev payload, dosya/alan boyut sınırları.
**Çıkış kapısı:** ✅ kota dayatması testli + sıfırdan kullanıcı uçtan uca testli + sil/dışa-aktar çalışıyor.
**Çıktı:** ADR (LLM kota) + testler + onboarding paneli.

---

### P3.5 — ÜRÜNLEŞME: TEK-KULLANICI DNA'SININ SÖKÜLMESİ ⚠️ **YAYIN-ENGELİ**
**Giriş:** P1 yeşil (izolasyon), P3 ile paralel yürür.
**Neden (Murat'ın 4 Ağustos direktifi):** Sistem bugün "giriş yapılabilen Murat'ın OS'u"dur.
Publish edilebilir ürün, **her kullanıcının kendi finansal DNA'sını** (hesapları, kuralları,
kırmızı çizgileri, dili, alışkanlıkları) kurabildiği sistemdir. Bir yabancı kayıt olduğunda
uygulamanın hiçbir yerinde başkasının hayatının izine rastlamamalı — ne örnek veride, ne koç
metninde, ne de kod içindeki sabit kurallarda.

**ÖLÇÜLEN GERÇEKLİK (2026-08-04, R3 taraması — varsayım değil):**
- `app/coach.py` sistem prompt'unda **gerçek kişi adı** örnek olarak gömülü ("Efe 9.000 ödedi").
- `app/action_executor.py:98` niyet regex'inde **banka markaları sabit** (`enpara`, `ziraat`) —
  başka bankayı kullanan kullanıcının cümlesi eşleşmez.
- `MC1`/`MC3` gibi **kural numaraları koda gömülü** (`MC1 = emanet dokunulmaz`); kullanıcının
  kendi yazdığı kırmızı çizgi aynı güçle dayatılmıyor.
- `scripts/setup_data.py` **kanonik Murat verisi** yükler (drop_all'lı) — yeni kullanıcıya asla
  bulaşmamalı, ama "örnek veri" ihtiyacı da karşılanmamış durumda.
- `get_current_user` **AUTH kapalıyken ilk kullanıcıya düşer** — production'da bu yol kesin kapalı olmalı.
- ✅ Kayıt akışı doğru çalışıyor: `register` → personal workspace + owner membership (doğrulandı).

**GÖREVLER:**
1. **Kişiye özel iz taraması + kalıcı kapı:** `app/`, `frontend/src/`, prompt metinleri ve
   e-posta şablonlarında gerçek kişi adı / banka markası / kişisel senaryo aranır; temizlenir.
   Ardından **statik test** eklenir (yasaklı sözcük listesi) — yeniden sızarsa süit kırılır.
2. **Kullanıcı-tanımlı kural motoru:** Kullanıcı kendi kırmızı çizgisini/kuralını UI'dan yazar,
   `rules_engine`/`action_executor` bunu **genel** biçimde dayatır (sabit MC numarası yok).
   Emanet/dokunulmazlık bir **hesap özelliği** (`is_emanet`) olarak kalır — kişiye değil, veriye bağlı.
   ADR yazılır (D1: 2-3 sektör referansı — kullanıcı-tanımlı kural/politika motorları).
3. **Kişiselleştirme katmanı:** hitap adı, para birimi, dil/locale, saat dilimi, maaş günü,
   ekstre/ödeme günleri, kategori seti — hepsi **kullanıcı başına**; hiçbiri kodda sabit değil.
4. **Koç kişiselleştirmesi:** koç metni kullanıcının kendi verisinden konuşur; örnek senaryolar
   jenerik veya kullanıcının kendi geçmişinden üretilir.
5. **Boş-durum + örnek veri:** yeni kullanıcı boş sistemde kırılmadan gezebilir; **isteğe bağlı**
   demo veri seti yükleyebilir ve **tek tuşla silebilir** (kendi verisine karışmadan).
6. **Sıfırdan kullanıcı uçtan uca testi:** temiz DB + yeni kayıt → hesap ekle → işlem gir →
   kendi kuralını yaz → koça sor → kural dayatılıyor mu. Otomatik test olarak kalır.
7. **Çok-kullanıcı eşzamanlılık:** iki kullanıcı aynı anda çalışırken kuralların/koçun
   birbirine karışmadığı doğrulanır (P1 matrisi + koç bağlamı).
**Çıkış kapısı:** ✅ yasaklı-iz taraması temiz (statik test kilitli) + kullanıcı-tanımlı kural
uçtan uca dayatılıyor + kişiselleştirme alanları kullanıcı başına + sıfırdan-kullanıcı testi yeşil.
**Çıktı:** ADR (kullanıcı-tanımlı kurallar) + `docs/kalite-seruveni/urunlesme-denetimi.md`.

---

### P4 — HUKUKİ / UYUM TEMELİ
**Giriş:** P3 devam ederken paralel yürüyebilir.
**Görevler:**
1. Gizlilik Politikası (KVKK uyumlu; hangi veri, neden, nerede, ne kadar süre, kiminle — LLM sağlayıcı
   **açıkça** yazılır).
2. Kullanım Şartları + **"lisanslı yatırım/finans tavsiyesi değildir"** uyarısı (uygulama içinde de görünür).
3. Açık rıza akışı: kayıtta onay kutusu, sürüm/tarih kaydı (`docs/legal/kvkk-consent-v1.md` mevcut — UI'ya bağlanacak).
4. Veri sahibi hakları: erişim (dışa aktar), silme, düzeltme — P3.4 ile aynı uçlar.
5. Veri işleyen envanteri: LLM sağlayıcıları, e-posta (SMTP), fiyat sağlayıcıları, hosting.
**Çıkış kapısı:** ✅ 3 metin yayında + rıza akışı çalışıyor + envanter yazılı.
**Çıktı:** `docs/legal/` + frontend sayfaları.

---

### P5 — DAYANIKLILIK & GÖZLEMLENEBİLİRLİK
**Giriş:** P2 yeşil.
**Görevler:**
1. **Yedek + GERİ YÜKLEME PROVASI** (yedek almak yetmez; geri yükleme denenmeden yedek yoktur).
2. Hata izleme (uygulama hatası sessizce kaybolmasın) + yapılandırılmış log + PII sızmaması.
3. Sağlık/uptime uçları, scheduler canlılığı (cron çalıştı mı görünür olsun).
4. Migration güvenliği: canlı veriyle `alembic upgrade` provası + geri alma yolu.
5. Kapasite/limit: eşzamanlı kullanıcı, DB bağlantı havuzu, LLM eşzamanlılığı.
**Çıkış kapısı:** ✅ geri yükleme provası kanıtlı + hata izleme çalışıyor + migration provası kanıtlı.

---

### P6 — CANLI ORTAM (İNSAN-KAPISI karışık)
**Giriş:** P1-P5 yeşil.
**Görevler:**
1. Sunucu provizyonu (**İNSAN-KAPISI** — §9.1).
2. Deploy runbook koşumu (`docs/deployment/runbook.md`), HTTPS/Let's Encrypt, servisler ayakta.
3. Canlı doğrulama gate'leri: sağlık, login, cockpit, koç, cron 24s, yedek.
4. **PWA canlı gate'leri** (Wave-8'den devir): Lighthouse PWA, "ana ekrana ekle", offline shell,
   gerçek mobil viewport uçtan uca.
**Çıkış kapısı:** ✅ canlı HTTPS'te uçtan uca kullanım + PWA gate'leri + 24 saat cron kanıtı.

---

### P7 — KAPALI BETA (Basamak A tamamlanır)
**Görevler:** davet akışı, 3-10 davetli, geri bildirim döngüsü (FEAT-033 widget'ı canlı),
hata/istek triyajı, ilk hafta düzeltme turu, kullanım metrikleri (gizlilik-dostu).
**Çıkış kapısı:** ✅ en az 3 gerçek kullanıcı en az 1 hafta kullandı + kritik bulgu 0 + geri bildirimler triyajlı.

---

### P8 — AÇIK BETA (Basamak B)
**Görevler:** kayıt açılır, kota/abuse savunmaları gerçek trafikte doğrulanır, destek kanalı,
sürüm notları, durum sayfası, ölçeklenme gözlemi.
**Çıkış kapısı:** ✅ açık kayıtla 2 hafta olaysız + kritik bulgu 0.

---

### P9 — PUBLISH (Basamak C)
**Görevler:** sürümleme + değişiklik günlüğü, geri alma provası, Play Store TWA paketi (opsiyonel,
ADR-040), duyuru metni, dokümantasyon (kullanıcı rehberi güncel), destek/iletişim.
**Çıkış kapısı:** ✅ **GOAL TAMAM — PUBLISH**.

---

## §4. YÜRÜTME PROTOKOLÜ (her görev için)

1. **Oku, varsayma.** İlgili dosyayı/komutu gerçek çalıştır. (R3)
2. **TDD.** Bug/özellik → önce başarısız test, sonra fix, sonra yeşil kanıtı.
3. **Bug konvansiyonu.** Sıradaki numara + dosya docstring'i `GUNCELLEMELER` + inline yorum +
   `docs/kalite-seruveni/uygulanan-fixler.md` satırı.
4. **Regresyon.** Değişen alanın süiti + ardından tam süit. Kırmızıysa faz ilerlemez.
5. **Commit.** Anlamlı mesaj, pre-commit hook'u atlama yok (`--no-verify` yasak).
6. **Kayıt.** §11 durum tablosu + `milestone-log.md` güncellenir; kanıt komutu ve çıktısı yazılır.
7. **Kapı.** Kapı ölçütü **ölçülebilir** olmalı ("çalışıyor gibi" değil, "şu komut şu çıktıyı verdi").

### §4.1 Yasak gerekçeler (görülürse görev reddedilir)
> "MVP için yeterli" · "pratikte olmaz" · "şimdilik böyle kalsın" · "sonra bakarız" ·
> "test yazmaya değmez" · "zaten çalışıyordur" · "büyük dosya, örneklem yeter" ·
> "kullanıcı bunu yapmaz" · "tek kullanıcı var nasılsa"

---

## §5. PARALEL AJAN PROTOKOLÜ

Murat paralel çalışmayı onayladı. Ajanlar **keşif ve tarama** için kullanılır, **karar** için değil.

- **Ne zaman ajan:** geniş tarama (çok dosya/dizin), bağımsız denetim boyutları, çok sayıda
  endpoint/dosyanın aynı ölçütle taranması, birbirine bağımsız iş parçaları.
- **Ne zaman ajan DEĞİL:** mimari karar, bug fix'in doğruluğu, kapı geçme kararı — bunlar bende kalır.
- **Ajan brief şablonu:** (1) tek cümle görev, (2) tam kapsam (dosya/dizin listesi), (3) aranan
  ölçüt, (4) beklenen çıktı formatı, (5) **"bulgunu dosya:satır ile kanıtla"**, (6) yasak: fix yapma.
- **AJAN RAPORU KANIT DEĞİLDİR.** Her ajan bulgusu, kapıya sayılmadan önce **benim tarafımdan**
  dosya/komut ile doğrulanır. Doğrulanamayan bulgu düşer.

---

## §6. KANIT FORMATI

Her kapı kaydı şu üç parçayı içerir:

```
KOMUT   : .\venv\Scripts\python.exe -m pytest tests/ -q
ÇIKTI   : 1254 passed, 1 skipped in 92.4s
YORUM   : P1 statik+runtime izolasyon gate'leri dahil; kırmızı yok.
```

Kanıt üretilemeyen madde `KANIT YOK` etiketiyle §11'e yazılır ve **kapı geçilmez**.

---

## §7. RİSK KAYDI (canlı — yeni risk çıkınca eklenir)

| # | Risk | Etki | Karşılık | Durum |
|---|---|---|---|---|
| R1 | Çok-kullanıcı veri sızıntısı | Kritik (yasal + itibar) | P1 statik gate + runtime matris + RLS | 🟡 P1'de |
| R2 | LLM maliyet patlaması | Yüksek (para) | P3 per-user kota + Ollama yedeği | ⬜ |
| R3 | KVKK ihlali | Yüksek (yasal) | P4 metinler + rıza + silme/dışa-aktarma | ⬜ |
| R4 | Veri kaybı | Kritik | P5 yedek + **geri yükleme provası** | ⬜ |
| R5 | Koçun yanlış finansal yönlendirmesi | Yüksek | ADR-001 + grounding + "tavsiye değildir" | 🟡 |
| R6 | Tek kişilik bakım yükü | Orta | P8 destek kanalı + hata izleme | ⬜ |
| R7 | **Ürün "birinin kişisel sistemi" gibi hissettiriyor** (yabancı kullanıcı kendi hayatını kuramıyor) | Yüksek (ürün ölür) | P3.5 ürünleşme + §1.2 hatırlatma listesi | 🟡 |

---

## §8. KAPSAM DIŞI (bilinçli — kapsam kayması önlemi)

- Native mobil uygulama (ADR-040: PWA kararı; TWA yalnız P9 opsiyonu).
- Ödeme/abonelik altyapısı (ücretsiz kapalı/açık beta).
- Çok-dilli arayüz (Türkçe; alan adları Türkçe korunur).
- Kripto/çoklu-varlık genişlemesi (ADR-031 vizyonu — publish sonrası).

---

## §9. İNSAN-KAPISI (KURAL 3 istisnaları — YALNIZ bunlar delege edilir)

Bunlar asistan araci'un yapamayacağı gerçek elle görevlerdir. Her biri için Murat'a **net talimat**
verilir, beklenen çıktı yazılır, geri dönene kadar **başka fazlar paralel yürür**.

1. **§9.1 Sunucu provizyonu** — Oracle Free Tier hesabı/VM/SSH anahtarı. (P6)
2. **§9.2 Alan adı** — domain kaydı + DNS A kaydı. (P6)
3. **§9.3 Canlı sırlar** — `.env.prod` içeriği **sunucuda** oluşturulur; **chat'e düşmez**. (P6)
4. **§9.4 Canlı DB üzerinde yıkıcı işlem onayı** — silme/geri yükleme provası. (P5/P6)
5. **§9.5 Üçüncü taraf hesapları** — LLM API anahtarı, SMTP, (varsa) hata izleme servisi kaydı. (P3/P5)
6. **§9.6 Beta davetlileri** — gerçek insanlara davet göndermek. (P7)

**Otonom para harcama ve sunucu satın alma YASAK.**

---

## §10. MASTERPROMPT'UN KENDİNİ GELİŞTİRMESİ (Murat'ın 3. adımı)

Her faz kapanışında **10 dakikalık geriye-bakış** yapılır ve bu dosya güncellenir:

- Bu fazda **kaçırdığım** ne vardı? → yeni görev/kapı olarak eklenir.
- Hangi kapı **ölçülemez** çıktı? → ölçülebilir hale getirilir.
- Hangi kural işe yaramadı / eksikti? → §1.1'e eklenir.
- Yeni risk çıktı mı? → §7'ye eklenir.

**Kısıt:** güncelleme **yalnız ileri yönlü**. Bir kapıyı kaldırmak, gevşetmek, kapsamı daraltmak
**yasaktır**. Yalnız şu üç yön serbest: (a) kapı **ekleme**, (b) kapıyı **daha ölçülebilir** yapma,
(c) sırayı **verimlilik** için değiştirme (kapı sayısı azalmadan). Her güncelleme §12'ye satır düşer.

---

## §11. DURUM TABLOSU (canlı — tek doğruluk kaynağı)

### §11.0 KALDIĞIMIZ YER (yeni oturum buradan devam eder — 5 Ağustos 2026, 14:40)

**Repo durumu:** çalışma ağacı TEMİZ, her şey commit'li. Son commit `4b05c64`.
**Test tabanı:** `1616 passed, 6 skipped` (backend) + `125 passed` (vitest, önceki tur 71).
Kırmızı yok. Frontend test sayısındaki sıçrama gerçek kapsam artışıdır (13 panel × boş-durum
+ 13 panel × hata-durumu).

---

#### ⚠️ ÖNCE OKU — bekleyen İKİ şey

**(a) CANLI DB — yapıldı (Murat onayıyla, 5 Ağu). Not olarak kalsın.**
Sıra: yedek → `repair_null_workspace --uygula` (BUG #221'in canlıda oluşmuş 2 satırı:
4 Ağu 2310 TL 'sigara' işlemi + 1 net-değer anlık görüntüsü) → yedek → **`alembic upgrade head`
(9 migration — BUG #222)** → doğrulama: satır kaybı yok, bakiye değişmedi. Ardından kullanıcının
bildirdiği 5 Ağu 300 TL yemek harcaması uygulamanın kendi akışıyla yazıldı (Enpara Nakit,
2.263,52 → 1.963,52 TL) — #221 düzeltmesinin canlı doğrulaması.
Yedekler: `data/backups/2026-08-05-141912.db` (onarım öncesi) ve `-142714.db` (upgrade öncesi).

**(b) TOKEN BÜTÇESİ — workflow maliyeti ölçüldü (5 Ağu).**
Doğrulama denetimi 49 ajanla koştu: **~3.97M token, haftalık limitin ~%50'si, 31 dakika.**
Pahalı kısım 8 denetçi değil **41 çelişme ajanıydı** (her bulguya bir ajan). Kural:
workflow yalnız Murat açıkça isterse; istendiğinde **tavan konur** ("en fazla 5 ajan" ya da
`/config` → Dynamic workflow size = small) ve **çelişme turu yalnız kritik/yüksek bulgulara**
uygulanır (~1/4 maliyet). Solo çalışma bunun yanında ihmal edilebilir — yavaşlama gerekiyorsa
kısılacak şey ajan fan-out'udur, çalışmanın kendisi değil.

**Bu turda kapanan 4 defekt + 1 altyapı** (P3.2 — boş/hata durumu arayüz kapısı):

| Bug | Konu |
|---|---|
| #217 | **İki kapı fiilen ÖLÜYDÜ.** Kapsam `app.routes`'tan türetiliyordu; FastAPI 0.141 router'ları düzleştirmeyi bırakınca boş-durum taraması 87 uçtan **1**'ini tarar oldu, izolasyon matrisi kapsamı **0** ölçtü — ikisi de yeşildi. Envanter OpenAPI'ye taşındı + **kapsam tabanı** assert edildi (`tests/endpoint_envanteri.py`). Kapı açılınca ilk gerçek bulgu: `/api/legal/{slug}` matris dışıydı |
| #218 | **Tek hatalı istek → sonsuz istek döngüsü.** `ToastProvider` context değerini her render'da yeniden yaratıyordu → `[toast]` bağımlı effect'ler tekrar koşuyordu. Ölçüldü: Aile paneli 150 ms'de **54 istek**, durmuyor. `useMemo` ile sabitlendi → 2 istek |
| #219 | **Bütçe paneli backend hata verince çöküyordu** (`data` null iken `data.envelopes`). Artık kalıcı hata kartı + "Tekrar dene"; yükleme başarısızken kullanıcıya "zarfın yok" DENMİYOR |
| #220 | **Zamana bağlı gizli flaky test** — UTC+14/UTC-11 farkı günün ~1/24'ünde 2 gün olur, iddia `(0,1)` idi. Üretim kodu doğruydu, test yanlıştı |
| altyapı | Frontend boş-durum testi **gerçek** boş-kullanıcı cevaplarıyla koşuyor (`frontend/src/__fixtures__/bos-kullanici.json`, 36 uç) + **sözleşme kayması kapısı** (backend gövde yapısını değiştirirse test kırılır, frontend sessizce bayatlayamaz) |

**Yeni ders-kuralları:** L11 (kapsamı ölç, taban assert et) · L12 (hata yolu da ürün yüzeyidir).
**Yeni hatırlatmalar:** H24 (arayüz katmanı boş/hata durumunda sınanmalı) · H25 (kapsam ölçülmeden kapı sayılmaz).

**Sonra kapatılan (aynı gün, denetim bulgusundan — commit `4b05c64`):**

| Bug | Konu |
|---|---|
| #222 | **CANLI ŞEMA KODUN 9 MIGRATION GERİSİNDEYDİ.** `data/financialos.db` `a1b2c3d4e5f6`'da kalmış, kod `e1f2a3b4c5d6` bekliyordu. `master_checkpoints.rule_type` yoktu → `enforce_user_rules` her onayda onu sorguladığı için **koç yolundan yapılan her onay 500 veriyordu**; rate-limit/hata-izleme/davet/e-posta-doğrulama/cron-görünürlüğü de canlıda fiilen yoktu. Uygulama yine de açılıyor, `/api/health` yeşil dönüyordu. Kapı yoktu: ADR-013 "şema yalnız Alembic" doğruydu ama "migration'ı çalıştırmayı unutma" adımı denetlenmiyordu. Fix: `app/schema_guard` startup fail-fast (prod), dev'de uyarı, test/`create_all` yolunda sessiz geçer. **Canlı DB head'e yükseltildi** (yedekli, satır kaybı yok) |
| #221 | **KRİTİK — koç-onaylı kayıt kullanıcının KENDİ listesinden kayboluyordu.** `execute_pending_action` handler'ları `(db, user_id, payload)` imzasıyla çağrılıyordu; workspace bağlamı hiç geçmiyordu → `Transaction` / `MasterCheckpoint` satırları `workspace_id=NULL`. Okuma workspace kapsamlı olduğu için: koça "500 TL harcadım" de → onayla → **bakiye düşüyor ama işlem hiçbir listede/raporda yok**. 3. kol: `premortem.DecisionJournal` de NULL yazıyordu (`decision_journal` RLS listesinde → prod Postgres'te satır yazılır ama görünmez). Fix: handler çağrısı `workspace_scope(pending.workspace_id)` içine alındı + `_yazma_workspace_id()` (aktif kapsam → kaynağın workspace'i → personal → None). **Statik kapı:** `tests/test_workspace_insert_kapisi.py` — workspace'li modele `workspace_id` vermeden kayıt açılamaz (AST, model listesi şemadan türer, kapsam tabanı assert'li, mutasyon kontrolü yapıldı) |

---

#### DOĞRULAMA DENETİMİ SONUCU (5 Ağu, `wf_ddd8b54e-1c9`)

**Rapor: `docs/kalite-seruveni/publish-dogrulama-denetimi.md`** — 8 boyut, salt-okur denetim +
her bulguya ayrı çelişme (adversarial) turu. **40 bulgu onaylandı, 1 çürütüldü.**
Şiddet dağılımı: 1 kritik · 12 yüksek · 17 orta · 10 düşük.

- **Kapandı:** D01/D02 (+3. kol) → BUG #221 · D19/D20/D21 → BUG #217 · D35 → BUG #220.
  (D19/D20/D35 bu turdaki düzeltmelerin **bağımsız doğrulamasıdır** — denetim onlardan
  önceki ağaçta koştu ve aynı defektleri buldu.)
- **Açık yüksek bulgular (sıradaki iş, şiddet sırasıyla):**
  1. **D03** `/api/cashflow/forecast` + `/api/debt-strategy/*` workspace bağlamını hiç kurmuyor (BUG #165 fix'i uç seviyesinde bağlanmamış)
  2. **D04** şifre sıfırlama token'ı, şifre değiştikten sonra HÂLÂ geçerli (BUG #172 ailesinin açık kolu)
  3. **D05** OAuth callback davet kapısını atlıyor → `invite_only` iken sınırsız hesap
  4. **D06** `docs/deployment/README.md` "Yol 2" + `.env.example` kimliksiz canlı sunucu üretebiliyor (fail-fast tetiklenmiyor)
  5. **D07** premortem ucu LLM kotasını tamamen atlıyor
  6. **D08** fiyat cron'u `Account.balance`'ı güncellemiyor → Hesaplar paneli ile Cockpit aynı hesap için FARKLI para gösteriyor
  7. **D11/D12/D13** `docker-compose.prod.yml`: `env_file` yok (prod backend fail-fast ile hiç açılmıyor), scheduler'da `AUTH_ENABLED` yok, otomatik yedek yok
  8. **D10** yayınlanan KVKK/veri-işleyen beyanı yanlış: ham işlem açıklamaları + üçüncü kişi adları yurt dışı LLM'e gidiyor
  9. **D09** production yığınında otomatik yedek yok
- **Not:** denetim "1581 passed" varsayımıyla başladı, diskte o an 3 kırmızı vardı — o üçü de bu turda kapandı.

**SIRADAKİ İŞLER** (öncelik sırasıyla, hepsi asistan araci'un yapabileceği işler):

1. **Denetimin açık YÜKSEK bulguları** — yukarıdaki D03…D13 listesi, şiddet sırasıyla.
   Çalışma ritmi: tek bulgu → TDD ile düzeltme → tam süit → ayrı commit. Her commit kendi
   başına tam olsun (oturum/kota kesilirse yarım iş kalmasın).
2. **Denetimin ORTA bulguları** (17 adet) — rapordaki D14…D30.
3. **P2.1** — session-fixation kararının yazılı gerekçesi (kabul edilen risk mi, değil mi).
4. **Durum sayfası** (kimliksiz "sistem ayakta mı") — `/api/meta/durum` var, sayfa yok.
5. **H4 kalanı** — para birimi/locale GÖRÜNTÜLEME aşaması (ADR-042).
6. **H9 kalanı** — prompt injection tam ayrıştırma.
7. **L11 taraması:** "hepsini tarar" diyen DİĞER kapılar da kapsam tabanı almalı —
   `test_scope_enforcement` (AST taraması), yasaklı-iz kapısı, veri-işleyen envanteri.
   #217 bu sınıfın yalnız ilk örneğiydi; sınıf taranmadı. (Denetim D31 aynı yöne işaret
   ediyor: statik kapı `db.get` / `Model.kolon` / `func(Model.kolon)` şekillerini modellemiyor.)

**Denetim workflow'unun scripti** (yeniden koşulacaksa): `~/.asistan/projects/.../workflows/
scripts/publish-dogrulama-denetimi-wf_87c89bbf-0d8.js`. `resumeFromRunId` yalnız AYNI
oturumda çalışır; yeni oturumda `scriptPath` ile baştan koşar. **Tekrar koşurmadan önce
maliyeti oku (yukarıdaki (b) maddesi) — tavan koymadan çalıştırma.**

**İNSAN-KAPISI (Claude yapamaz, Murat'ta):** §9 — Oracle VM + domain/DNS + canlı sırlar,
gerçek davetliler, gerçek trafik, duyuru. Canlı deploy olmadan P6/P7/P8/P9 kapanmaz.


Durum: ⬜ başlamadı · 🟡 devam · ✅ kapı geçti (kanıtlı) · ⏸️ insan-kapısı bekliyor

| Faz | Konu | Durum | Kanıt / Not |
|---|---|---|---|
| P0 | Temel doğrulama | ✅ | `pytest tests/ -q` → **1608 passed, 6 skipped** (2 dk 12 sn) + vitest **125 passed**; migration/çalışma-ağacı kontrolü yapıldı. **BUG #220:** süitte zamana bağlı gizli bir flaky vardı (UTC+14/UTC-11 farkı günün ~1/24'ünde 2 gün) — kapatıldı |
| P1 | Veri izolasyonu | ✅ | 4 bug kapandı (**#162** çapraz-kullanıcı kural sızıntısı, **#163** çok-kullanıcı backfill, **#164** yıkıcı script footgun'ı, **#165** workspace kapsam tutarsızlığı) + statik kapı (3 meta-testle ispatlı) + runtime matris (17 test) + **PostgreSQL RLS gate 13 passed** (`scripts/pg_gate_run.py`). ⚠️ **Düzeltme (BUG #217, 5 Ağu):** buradaki "kapsam kilitli" iddiası yazıldığı andan itibaren GEÇERSİZDİ — kapsam kilidi `app.routes`'tan besleniyordu ve FastAPI 0.141'de boş dönüyordu, yani hiçbir ucu ölçmüyordu. Kilit OpenAPI'ye taşındı + taban assert edildi; açılır açılmaz `/api/legal/{slug}` matris dışı çıktı (gerekçeli istisnaya yazıldı). Matrisin kendisi (17 test) doğruydu, **kapsamı** ölçülmemişti |
| P2 | Güvenlik review | ✅ | **19 bug kapandı + bağımlılık 23→0.** Rapor: `guvenlik-review-publish.md`. Kabul edilen 3 risk gerekçeli yazılı (kayıt enumerasyonu, dolaylı prompt injection, localStorage token). Eski not: **8 başlıktan 6'sı kapandı.** Kapatılan: #170 sıfırlama-token'ı prod'da yanıtta dönüyordu (hesap ele geçirme), #171 prod'da AUTH_ENABLED doğrulanmıyordu (API kimliksiz açık), #172 şifre sıfırlama oturumları düşürmüyordu + tek-kullanım + logout access iptali, #173 viewer paylaşılan workspace'e yazabiliyordu, #174 kimliksiz kullanıcı yaratma, #175 ham exception gövdede, #176/#177/#181 girdi sınırları, #178 prod CORS localhost, #179 OAuth token'ları URL'de, #180 PII log. **Bağımlılık: pip-audit 23 açık → 0** (PyJWT/authlib/starlette/cryptography dahil), npm audit 0. **Gövde sınırı TAMAM (H22 / #213):** sınır yalnız nginx'teydi (ters vekil atlanırsa koruma yok, chunked gövdede `Content-Length` hiç gelmez) → uygulama katmanına taşındı, akan gövde sayılır, 413 hata-izlemeye düşmez, nginx şablonu testle kilitlendi (14 test). **KALAN:** rate-limit çok-worker/proxy-IP (Redis veya nginx limit_req), OAuth PKCE + state store çok-worker, refresh rotasyonu, şifre politikası (blocklist), register enumerasyonu kararı |
| P3 | Operasyonel gerçeklik | ✅ | **Onboarding UI TAMAM (H20)** — Cockpit boş-durum kartı + demo veri akışı. **Kota TAMAM (ADR-041, BUG #188):** kullanıcı-başına LLM tavanı — paylaşılan sağlayıcı kotasını tek kişi tüketip diğerlerini kilitleyemez; tavan dolunca uygulama kapanmaz (Rules Engine deterministik). **#189** OAuth env adı kod↔doküman uyumsuzluğu, **#190** giriş yapmış kullanıcı şifre değiştiremiyordu. Sıfırdan-kullanıcı e2e ✅ (P3.5). **P3.2 (boş-veri hali her panelde) TAMAM (5 Ağu):** backend tarafı zaten kanıtlıydı ama kapsamı ölçülmemişti (**#217** — 87 uçtan 1'i taranıyordu); arayüz tarafı hiç sınanmamıştı → 13 panel × boş-durum + 13 panel × hata-durumu (54 test, gerçek boş-kullanıcı fixture'ı + sözleşme kayması kapısı). Bulunan gerçek defektler: **#218** (sonsuz istek döngüsü), **#219** (Bütçe paneli hata yolunda çöküyordu). **Kalan:** onboarding rehberi + opsiyonel demo veri |
| P3.5 | **Ürünleşme (tek-kullanıcı DNA söküm)** | ✅ | **H1/H2/H3/H5/H21 ✅ + H4 saat dilimi ✅** (para birimi görüntüleme ADR-042 ile P8 öncesine planlı — yayın-engeli değil). Eski not: **H1/H2/H3/H5 ✅** (kullanıcı-tanımlı kural motoru #192, demo veri #194, iz temizliği). **Kalan: H4** (para birimi/dil/saat dilimi/kategori seti kullanıcı başına) — TRY/TR varsayımı hâlâ kodda; çok-para-birimi büyük bir iş, ayrı ADR ile ele alınacak. Eski not: **1. tur:** BUG #166 (metinlerde kişi adı → jenerik + statik kapı), #167 (TR normalize Kiril 'о' + sıra hatası → sessiz veri bozulması), #168 (banka markası koda gömülü → kullanıcının kendi hesap adları). **Kalan:** kullanıcı-tanımlı kural motoru (MC sabitleri), kişiselleştirme alanları, boş-durum + demo veri, sıfırdan-kullanıcı uçtan uca testi, yorum/docstring temizliği |
| P4 | Hukuki/uyum | ✅ | **BUG #191:** rıza metni canlıda ERİŞİLEMEZDİ (imajda docs/ yok → 404). `/api/legal/<slug>` ucu + Dockerfile/dockerignore. Rıza **v2** (v1 "self-host" varsayıyordu — barındırılan betada yanlış beyan), kullanım şartları (SPK/tavsiye-değildir), veri-işleyen envanteri (kodla test-bağlı). Koç panelinde görünür uyarı (H13) |
| P5 | Dayanıklılık/gözlem | ✅ | **Geri yükleme provası TAMAM (H14):** `scripts/restore.py` (onaysız yazmaz, bozuk yedeği reddeder, emniyet kopyası alır) + SQLite drill (7 test) + **PostgreSQL dump→drop→restore→doğrula** provası + runbook geri-yükleme bölümü. **Hata izleme TAMAM (#195):** kendi DB'mizde (dış servise veri gitmez), tekrarlar gruplanır, PII/sır maskelenir, izleme isteği düşürmez. **Canlı-veri migration provası TAMAM (#196):** `alembic/env.py` config URL'ini yok sayıyordu (test/script içinden migration GERÇEK DB'ye gidiyordu) → düzeltildi; prova artık izole DB'de koşuyor ve *gerçek DB'ye dokunulmadığı* da teste bağlı. **Fiyat sağlayıcı çöküşü TAMAM (H16 / #211):** fon-hisse zaten bayat işaretliydi; **döviz** kesintide TAMAMEN susuyordu → son bilinen kur `bayat`/`yas_dakika` ile sunuluyor, koç "şu anki" demiyor, 12 saatten eski değer hiç dönmüyor. **Kalan:** kapasite sınırları |
| P6 | Canlı ortam | ⏸️ | **İNSAN-KAPISI (§9.1-9.3):** Oracle VM + domain/DNS + canlı sırlar Murat'ta. **Hazırlık TAMAM:** `scripts/live_gate.py` tek komutla 20+ canlı kapıyı ölçer (kimlik zorunluluğu, HTTPS/CSP, /docs kapalı, KVKK metinleri, brute-force limiti, koç kotası); çıkış kodu 0 değilse beta AÇILMAZ. Runbook'ta canlı-doğrulama + geri-yükleme bölümleri hazır |
| P7 | Kapalı beta | 🟡 | **Altyapı TAMAM:** davetli-only kayıt (#199) + davet üretici + **geri bildirim/hata triyajı (#209)** + cron görünürlüğü (#203). **Kullanım ölçümü TAMAM (H23 / #214):** `beta_metrics` — sessiz terk, onboarding hunisi, tutunma, koç hata oranı; çıktı yalnız sayı (PII testle yasak), dış analitik yok. **Kalan: gerçek davetlilerin kayıt olması** (sunucu sonrası) |
| P8 | Açık beta | 🟡 | **Ön koşul TAMAM:** kayıt enumerasyonu kapatıldı + e-posta doğrulama akışı (#202), destek adresi yapılandırılabilir (#205), giriş yapamayanın destek kanalı (#210). **Eşzamanlı koç kullanımı TAMAM (H17 / #212):** kota rezervasyon desenine geçti (paralel istek tavanı delemiyor) + muhasebe etiketi paylaşılan çalışma-anı durumundan kurtarıldı (günlük kota koruması ölüydü). **Kalan: gerçek trafik** |
| P9 | Publish | 🟡 | **Sürüm yönetimi + CHANGELOG (#200), GERİ ALMA PROVASI (#208), kullanıcı rehberi (#207) TAMAM.** Kalan: duyuru + (opsiyonel) TWA — canlı yayın sonrası |

---

## §12. DEĞİŞİKLİK GÜNLÜĞÜ (yalnız ileri yönlü)

| Sürüm | Tarih | Değişiklik | Gerekçe |
|---|---|---|---|
| v1.0 | 2026-08-04 | İlk yazım: 10 faz, 3 basamak, kapı/kanıt protokolü, ajan protokolü, insan-kapısı listesi | Murat'ın publish goal direktifi |
| v2.0 | 2026-08-05 | **§1.3 DERS-KURALLARI (L1-L10)** eklendi — 41 bug'dan çıkarılan, tekrar etmemesi gereken hata SINIFLARI. Faz kapıları KORUNDU, hiçbiri gevşetilmedi | Murat'ın 3. adımı: "masterprompt'u gerileme/duraksama yönü hariç, kaliteyi artırma amaçlı geliştir" |
| v2.1 | 2026-08-05 | **§1.3'e L11 + L12**, **§1.2'ye H24 + H25** eklendi; §11 P0/P1/P3 kanıt satırları düzeltildi (P1'in "kapsam kilitli" iddiası BUG #217 ile GEÇERSİZ çıktı, yazıldı) | P3.2 turunda ölçülen 4 defekt: kapsam sessizce çöken kapılar (#217), hata yolunda sonsuz istek döngüsü (#218), hata yolunda panel çökmesi (#219), zamana bağlı flaky (#220). Kapı EKLENDİ, hiçbiri gevşetilmedi (§10) |
| v1.1 | 2026-08-04 | **§P3.5 ÜRÜNLEŞME fazı eklendi** (tek-kullanıcı DNA'sının sökülmesi — yayın-engeli) + **§1.2 kalıcı hatırlatma listesi** (H1-H18) + P0/P1 kapıları kanıtla kapatıldı + R7 riski eklendi | Murat: "kullanıcı sorununu da çözmek lazım publish etmeden… ben unutsam da sen hatırla, nicelerini de sen eklersin". Kapı EKLENDİ, hiçbir kapı gevşetilmedi (§10 kuralına uygun) |
