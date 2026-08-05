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

Durum: ⬜ başlamadı · 🟡 devam · ✅ kapı geçti (kanıtlı) · ⏸️ insan-kapısı bekliyor

| Faz | Konu | Durum | Kanıt / Not |
|---|---|---|---|
| P0 | Temel doğrulama | ✅ | `pytest tests/ -q` → **1318 passed, 5 skipped** (63s); migration/çalışma-ağacı kontrolü yapıldı |
| P1 | Veri izolasyonu | ✅ | 4 bug kapandı (**#162** çapraz-kullanıcı kural sızıntısı, **#163** çok-kullanıcı backfill, **#164** yıkıcı script footgun'ı, **#165** workspace kapsam tutarsızlığı) + statik kapı (3 meta-testle ispatlı) + runtime matris (17 test, kapsam kilitli) + **PostgreSQL RLS gate 13 passed** (`scripts/pg_gate_run.py`) |
| P2 | Güvenlik review | ✅ | **19 bug kapandı + bağımlılık 23→0.** Rapor: `guvenlik-review-publish.md`. Kabul edilen 3 risk gerekçeli yazılı (kayıt enumerasyonu, dolaylı prompt injection, localStorage token). Eski not: **8 başlıktan 6'sı kapandı.** Kapatılan: #170 sıfırlama-token'ı prod'da yanıtta dönüyordu (hesap ele geçirme), #171 prod'da AUTH_ENABLED doğrulanmıyordu (API kimliksiz açık), #172 şifre sıfırlama oturumları düşürmüyordu + tek-kullanım + logout access iptali, #173 viewer paylaşılan workspace'e yazabiliyordu, #174 kimliksiz kullanıcı yaratma, #175 ham exception gövdede, #176/#177/#181 girdi sınırları, #178 prod CORS localhost, #179 OAuth token'ları URL'de, #180 PII log. **Bağımlılık: pip-audit 23 açık → 0** (PyJWT/authlib/starlette/cryptography dahil), npm audit 0. **Gövde sınırı TAMAM (H22 / #213):** sınır yalnız nginx'teydi (ters vekil atlanırsa koruma yok, chunked gövdede `Content-Length` hiç gelmez) → uygulama katmanına taşındı, akan gövde sayılır, 413 hata-izlemeye düşmez, nginx şablonu testle kilitlendi (14 test). **KALAN:** rate-limit çok-worker/proxy-IP (Redis veya nginx limit_req), OAuth PKCE + state store çok-worker, refresh rotasyonu, şifre politikası (blocklist), register enumerasyonu kararı |
| P3 | Operasyonel gerçeklik | ✅ | **Onboarding UI TAMAM (H20)** — Cockpit boş-durum kartı + demo veri akışı. **Kota TAMAM (ADR-041, BUG #188):** kullanıcı-başına LLM tavanı — paylaşılan sağlayıcı kotasını tek kişi tüketip diğerlerini kilitleyemez; tavan dolunca uygulama kapanmaz (Rules Engine deterministik). **#189** OAuth env adı kod↔doküman uyumsuzluğu, **#190** giriş yapmış kullanıcı şifre değiştiremiyordu. Sıfırdan-kullanıcı e2e ✅ (P3.5). **Kalan:** onboarding rehberi + opsiyonel demo veri |
| P3.5 | **Ürünleşme (tek-kullanıcı DNA söküm)** | ✅ | **H1/H2/H3/H5/H21 ✅ + H4 saat dilimi ✅** (para birimi görüntüleme ADR-042 ile P8 öncesine planlı — yayın-engeli değil). Eski not: **H1/H2/H3/H5 ✅** (kullanıcı-tanımlı kural motoru #192, demo veri #194, iz temizliği). **Kalan: H4** (para birimi/dil/saat dilimi/kategori seti kullanıcı başına) — TRY/TR varsayımı hâlâ kodda; çok-para-birimi büyük bir iş, ayrı ADR ile ele alınacak. Eski not: **1. tur:** BUG #166 (metinlerde kişi adı → jenerik + statik kapı), #167 (TR normalize Kiril 'о' + sıra hatası → sessiz veri bozulması), #168 (banka markası koda gömülü → kullanıcının kendi hesap adları). **Kalan:** kullanıcı-tanımlı kural motoru (MC sabitleri), kişiselleştirme alanları, boş-durum + demo veri, sıfırdan-kullanıcı uçtan uca testi, yorum/docstring temizliği |
| P4 | Hukuki/uyum | ✅ | **BUG #191:** rıza metni canlıda ERİŞİLEMEZDİ (imajda docs/ yok → 404). `/api/legal/<slug>` ucu + Dockerfile/dockerignore. Rıza **v2** (v1 "self-host" varsayıyordu — barındırılan betada yanlış beyan), kullanım şartları (SPK/tavsiye-değildir), veri-işleyen envanteri (kodla test-bağlı). Koç panelinde görünür uyarı (H13) |
| P5 | Dayanıklılık/gözlem | ✅ | **Geri yükleme provası TAMAM (H14):** `scripts/restore.py` (onaysız yazmaz, bozuk yedeği reddeder, emniyet kopyası alır) + SQLite drill (7 test) + **PostgreSQL dump→drop→restore→doğrula** provası + runbook geri-yükleme bölümü. **Hata izleme TAMAM (#195):** kendi DB'mizde (dış servise veri gitmez), tekrarlar gruplanır, PII/sır maskelenir, izleme isteği düşürmez. **Canlı-veri migration provası TAMAM (#196):** `alembic/env.py` config URL'ini yok sayıyordu (test/script içinden migration GERÇEK DB'ye gidiyordu) → düzeltildi; prova artık izole DB'de koşuyor ve *gerçek DB'ye dokunulmadığı* da teste bağlı. **Fiyat sağlayıcı çöküşü TAMAM (H16 / #211):** fon-hisse zaten bayat işaretliydi; **döviz** kesintide TAMAMEN susuyordu → son bilinen kur `bayat`/`yas_dakika` ile sunuluyor, koç "şu anki" demiyor, 12 saatten eski değer hiç dönmüyor. **Kalan:** kapasite sınırları |
| P6 | Canlı ortam | ⏸️ | **İNSAN-KAPISI (§9.1-9.3):** Oracle VM + domain/DNS + canlı sırlar Murat'ta. **Hazırlık TAMAM:** `scripts/live_gate.py` tek komutla 20+ canlı kapıyı ölçer (kimlik zorunluluğu, HTTPS/CSP, /docs kapalı, KVKK metinleri, brute-force limiti, koç kotası); çıkış kodu 0 değilse beta AÇILMAZ. Runbook'ta canlı-doğrulama + geri-yükleme bölümleri hazır |
| P7 | Kapalı beta | 🟡 | **Altyapı TAMAM:** davetli-only kayıt (#199) + davet üretici + **geri bildirim/hata triyajı (#209)** + cron görünürlüğü (#203). **Kalan: gerçek davetlilerin kayıt olması** (sunucu sonrası) |
| P8 | Açık beta | 🟡 | **Ön koşul TAMAM:** kayıt enumerasyonu kapatıldı + e-posta doğrulama akışı (#202), destek adresi yapılandırılabilir (#205), giriş yapamayanın destek kanalı (#210). **Eşzamanlı koç kullanımı TAMAM (H17 / #212):** kota rezervasyon desenine geçti (paralel istek tavanı delemiyor) + muhasebe etiketi paylaşılan çalışma-anı durumundan kurtarıldı (günlük kota koruması ölüydü). **Kalan: gerçek trafik** |
| P9 | Publish | 🟡 | **Sürüm yönetimi + CHANGELOG (#200), GERİ ALMA PROVASI (#208), kullanıcı rehberi (#207) TAMAM.** Kalan: duyuru + (opsiyonel) TWA — canlı yayın sonrası |

---

## §12. DEĞİŞİKLİK GÜNLÜĞÜ (yalnız ileri yönlü)

| Sürüm | Tarih | Değişiklik | Gerekçe |
|---|---|---|---|
| v1.0 | 2026-08-04 | İlk yazım: 10 faz, 3 basamak, kapı/kanıt protokolü, ajan protokolü, insan-kapısı listesi | Murat'ın publish goal direktifi |
| v2.0 | 2026-08-05 | **§1.3 DERS-KURALLARI (L1-L10)** eklendi — 41 bug'dan çıkarılan, tekrar etmemesi gereken hata SINIFLARI. Faz kapıları KORUNDU, hiçbiri gevşetilmedi | Murat'ın 3. adımı: "masterprompt'u gerileme/duraksama yönü hariç, kaliteyi artırma amaçlı geliştir" |
| v1.1 | 2026-08-04 | **§P3.5 ÜRÜNLEŞME fazı eklendi** (tek-kullanıcı DNA'sının sökülmesi — yayın-engeli) + **§1.2 kalıcı hatırlatma listesi** (H1-H18) + P0/P1 kapıları kanıtla kapatıldı + R7 riski eklendi | Murat: "kullanıcı sorununu da çözmek lazım publish etmeden… ben unutsam da sen hatırla, nicelerini de sen eklersin". Kapı EKLENDİ, hiçbir kapı gevşetilmedi (§10 kuralına uygun) |
