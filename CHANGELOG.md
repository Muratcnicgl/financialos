# Değişiklik Günlüğü

Bu dosya **yayınlanan** sürümleri kaydeder (P9). Sürüm numarası `app/version.py`
içindeki `APP_VERSION` ile **aynı** olmalıdır — `tests/test_version_release.py` bunu kilitler.

Biçim: [Semantic Versioning](https://semver.org/lang/tr/) · Tarihler: YYYY-AA-GG

## [Yayınlanmamış]

### Arayüz ve kullanım
- Kokpitteki yaklaşan vade satırı tek tıkla eyleme dönüşür: borç → "Ödedim", alacak →
  "Geldi" (nakit ayağıyla), kart son ödemesi → "Koça sor" (hazır soruyla) (#477).

- Borç Stratejisi'nde "Bu planı benimse": seçilen strateji + aylık ekstra, Borç Ödeme hedefine
  bağlanır; hedefin tahmini bitişi artık benimsenen planla hesaplanır (eskiden hep Kartopu/0) (#479).

- Başarı anları: borç kilometre taşı (%10/25/50/75) kokpitte pankart + tek seferlik kısa konfeti,
  hedef tamamlanınca bir kez kutlama; hareket azaltma tercihine saygılı (#480).

- Boş "Kırmızı Çizgiler" üç tipik başlangıç şablonu sunar (nakit tabanı, tek harcama tavanı,
  dokunulmaz hesap); tutarı kullanıcı yazar (#481).

- Koçta hiç bağlanmamış `onActionResolved` prop'u ve koruma bloğu silindi; panel-arası tazeleme
  yeniden bağlanmayla zaten sağlanıyor (#482).

- Veri listeleri (koç mesajları, kokpit satırları, akış takvimi, raporlar) kararlı anahtar
  kullanır; dizin anahtar kuralı tavanla izlenir (#483).

- Dokuz ikon butonu ekran okuyucu için adlandı (kategori yönetimi, dilek listesi, zarf silme,
  üye çıkarma); kapının kör noktası kapandı; dört boş bileşen dosyası silindi (#484).

- Yanıtlar 1 KB üstünde gzip ile sıkıştırılır (openapi 230 KB → 1/3 altı) (#485).

- İlk yükleme üçte bire indi: paneller tembel yüklenir, grafik kütüphanesi ayrı parçada; altbilgi
  gerçek sürümü gösterir (#486).

- Aksiyon onayı önce/sonra farkı için tam kokpiti iki kez üretmez; tek sorguluk özet (55× hızlı) (#487).

- Koç mesaj kartları yazarken yeniden ayrıştırılmaz (memo) (#488).

- Takılan istekler 30 sn'de (koç 180 sn) açık hatayla düşer; sonsuz "yükleniyor" yok (#489).

- Hedef kuralları Türkçe okunur ve arayüzden eklenebilir (eskiden ham JSON, yalnız silme) (#490).

- 29 tabloda birincil anahtarın yanındaki gereksiz ikinci indeks kaldırıldı (göç) (#491).

- Hız sınırlı uçlar `X-RateLimit-*` başlıkları döner; 429 `Retry-After` taşır (#492).

- Operatör uçları: veritabanı sağlığı (`/api/ops/db` — boyut, WAL, tablo satırları, kilit sayacı)
  ve zamanlanmış işlerin süreleri (#493).

- SQLite yedeği artık uygulamanın kendi zamanlayıcısından (03:15) alınır ve çalışma kaydı bırakır;
  Dependabot bağımlılık güncellemeleri (#494).

- İşlemler CSV olarak indirilebilir (Türkçe Excel uyumlu; tarih aralığı) (#495).

- Finansal sözlük (`docs/sozluk.md`) ve doğru ilk-çalıştırma akışı (README) (#496).

- Açık tema artık açılışta koyu "flash" yapmaz (başlatıcı yanlış anahtar okuyordu); durum çubuğu
  tema rengini alır; çentik güvenli alanı ve eski Safari için 100vh yedeği (#499).

- Koç: sağlayıcı "şu kadar bekle" derse (≤5 sn) aynı sağlayıcıda beklenir, hemen yedeğe düşülmez (#500).

- Koç çıktı tavanı ayarlanabilir (`LLM_MAX_TOKENS`); sınırda kesilen yanıt izde ve log'da görünür (#501).

### Operasyon
- Windows servisi uvicorn'u eşzamanlı bağlantı / keep-alive / backlog sınırlarıyla açar (#497).
- Ölçümle karara bağlanan maddeler: kompozit indeksler plana giriyor; iz adımı başına commit
  sohbet başına 1,4 ms — dayanıklılık için korundu (#498).
- Sağlık görevi, uygulama sağlamken dış yol ölüyse funnel oturumunu kendisi yeniler; kesinti
  kaydı `onarim=1` olarak kalır (#478).

## [0.3.0] — 2026-09-14 — "Ölçülen sistem" (kapalı beta → kalite serüveni)

0.2.0'dan bu yana **#223–#475** arası 253 düzeltme/özellik, 333 commit. Bu sürümün ana
fikri: hiçbir iddia ölçümsüz kalmaz — her kapanış kaynaktan türeyen bir kapı testiyle
kilitlenir (`tests/*_kapisi.py`, `frontend/src/*.test.jsx`), her ölçü mutasyonla sınanır.
Madde madde döküm `docs/kalite-seruveni/uygulanan-fixler.md`; bu not alanlara göre özettir.

### ⚠️ Kırıcı değişiklikler (self-host)
- **`AUTH_ENABLED` varsayılanı AÇIK** (#227). Kimliksiz yerel tek-kullanıcı kurulumu
  `.env`'e `AUTH_ENABLED=false` yazmalıdır; production'da bu da fail-fast ile reddedilir.
- `/api/health` artık yalnız `{"status":"ok"}` döner; sürüm/yapı bilgisi `/api/meta`
  (kimlik ister) ve `/api/ready` uçlarındadır (#436, SEC-027).
- Kök `test_*.py` duman betikleri `scripts/smoke/` altına taşındı; `python -m
  scripts.smoke.<ad>` ile koşulur (#431). Canlı DB'ye `drop_all` artık reddedilir (#381).
- Aksiyon uçları iş kuralı hatasında 422, bulunamayanda 404 döner (BE-011); kısmi
  güncelleme fiili PATCH (API-009). API sözleşmesi dondurulmuştur:
  `docs/api-reference/api-sozlesmesi.json` (#306) — ek alanlar serbest, kaldırma yasak.

### Güvenlik
- Şifre sıfırlama bağlantısı şifre değiştikten sonra ölüyor (#225); OAuth kaydı davet
  kapısından geçiyor (#226); Google ile açılan hesap şifre alabiliyor (#233).
- LLM kotası tüm yollarda tek sayaçtan (#228, #234); prompt enjeksiyonuna yapısal
  savunma (#257, ADR-045); kalıcı hata maskesi ve uygulama katmanı başlıkları (#258–#260);
  sır sızma denetimi commit anında ve git geçmişinde (#261, #384).
- Canlı `Server: uvicorn` başlığı kapandı; CSP arayüzü öldürmüyor (#287); sızan oturumu
  iptal aracı (#291); şifre politikası kişiye özel tahmini görüyor (#254).
- Onay/ret/düzenleme uçlarında hız sınırı (#382); onay geçişi atomik — eşzamanlı iki
  onay çift işlem üretemez (SEC-023); koç motoru kullanıcılar arası yalıtımı ölçüldü
  (SEC-026); sohbet yanıtı kokpit kopyasını istemcinin okuduğu kadar taşır (#435); onay/red kararı denetim izinde (#443).
- Kurucunun ve üçüncü kişilerin gerçek finansal verisi prod imajına giremez (#236);
  kişisel veri ratchet'i test fikstürlerini de tarar (#338).

### Veri doğruluğu ve bütünlük
- Koçun kaydettiği işlem yanlış güne yazılıyordu — kullanıcı saat dilimi (#237); fiyat
  cron'u bakiyeyi güncellemiyordu (#229); bayat fiyat "güncel" sunuluyordu (#239).
- Nakit-akış, borç-stratejisi, premortem ve simülasyon uçları workspace bağlamını kurmuyordu
  (#223–#224). Panelden ödendi işaretlenen alacak nakde geçmiyordu (#241); kayıt gününün net değeri 0
  kalıyordu (#292); net-worth snapshot yarışı (#378).
- Nakit takvimi tek parça: koç gelen parayı gider saymıyor (#319); yatırımda bekleyen
  nakit ayrı kalem (#320); karta yazılan düzenli gider nakit çıkışı sayılmıyor (#331);
  kart asgarisi ekstre borcundan ve hesabın kendi oranından (#330, #337, #340).
- Kredi erken kapama tutarı sayısal alan (#318); borç kapanış artığı son ödemeye eklenir,
  korunum toleransı 1 kuruş (#438); maliyet esası "ağırlıklı ortalama" olarak etiketli.
- ORM bütünlük kuralları flush anında: `is_paid ⇔ paid_date`, `YYYY-MM` tekilleştirme
  anahtarı, `CoachInsight.status` NULL olamaz, `Goal.progress_percent ∈ [0,100]`, kart
  alanları yalnız kredi kartında; ihlal 422 (#444–#447). Para kuralları denetim
  türetiminde (DATA-034); büyüyen tablolarda saklama kuralı (#383); sık filtrelenen FK
  sütunlarına indeks (PERF-010).
- Para birimi tek kaynak (#256, ADR-044); Decimal/NUMERIC saklama kayıpsız ölçüldü
  (DATA-002); kategori seti kullanıcıya ait (#264).

### Koç (LLM) ve kural motoru
- Koç aritmetik yapmaz, kural motoru hesaplar: kötü hâl (#333), stopaj/getiri eşiği
  (Wave-K, `app/vergi.py`), belirsizlikte tek "ay sonu" sayısı yazılmaz (#334).
- Grounding: izin listesi modelin gördüğü veri kadar (#322); "bugün" reddedilmez (#323);
  beraatin gerekçesi var, zayıf beraat işaretlenir (#324–#325); ret sebebi loglanır ve
  retry sebebi öğrenir (#335–#336); koçun düştüğü sözleşmede görünür (#376).
- Soru gerçekleşmiş eylemi veto edemez (#267, ADR-049); "asla unutma" hafızası (#268);
  "kaydettim" güvencesi (#271); yönlendirme sözleşmeyi değiştiremez (#272); premortem
  nezaket cümlesinde kaybolmuyor (#270); onay yaptığı işi tam anlatır (#354).
- Prompt yasakladığı jargonu kendisi öğretmiyor (#374); "reel bütçe" kullanıcının
  gördüğü ad (#379); sabit model kimliği çürüyünce bunu soran biri var (#369).
- Kalite ölçümü: altın senaryo seti (#317), judge + yan yana koşum (#278), ölü koç
  ödüllendirilmiyor (#276), üslup sözleşmesi ölçülüyor (#277), sağlayıcı başına ölçüm
  (`--saglayicilar`, `--bekle`); koç kalite özeti ucu `/api/ops/koc-kalite` (#439).
- Aylık özet: kategori kaymaları ve "geçen aya göre" anlatısı (#430); nakit-akışı
  projeksiyonu kapsamını söyler, kart tamponunu ayrı verir (#432); yaklaşan akış raporu
  tahminle aynı projeksiyonu kullanır (#442).

### Arayüz ve kullanım
- Onboarding rehberi (#262), panel ipuçları ve kurulum sihirbazı, sade/detaylı görünüm
  modu, komut paleti tüm panelleri biliyor (#360), yardım ekranı doğru kısayolları öğretiyor (#361).
- Kokpit: kartlarda "ay başından beri" farkı (#429), "bu ay" temposu (#466), bugün kalan
  limit canlı ve hızlı girişte aşım onayı (#467), günlük limit dökümü, bayat fiyat satırında
  modalsız fiyat girişi (#470), vade satırları ilgili panele gider (#465), karar geçmişi (#471),
  düşük riskli bekleyenler toplu onaylanır (#472), uyarılar katlanır (UX-023).
- Raporlar: ay-be-ay gelir/gider/tasarruf (DVIZ-004), net değer bileşenleri (#458), borç
  eritme projeksiyonu (#459), fon fiyat geçmişi (#460), bakiye trendinde sıkışma bandı ve
  eşik çizgisi, yatırım değeri kendi ekseninde; grafik renkleri tek kaynak ve renk körü
  güvenli 6'lı palet (#453, DVIZ-002).
- Hesap silme onayı gerçek kapsamı söyler (#434); hızlı giriş en sık kategorileri önerir
  (#468); ekstra ödeme kaydırıcısı reel bütçeye ölçekli (#463); panel filtreleri hatırlanır
  (#462); boş durumlar CTA'lı (#464); para girdileri doğru klavye ipucu verir (UX-016).
- Arka plandaki sekme saatte 720 istek üretmiyor (PERF-008); PWA service worker API
  isteklerini öldürmüyor (#288); favicon.

### Erişilebilirlik
- Tüm diyaloglar APG "modal dialog" örüntüsünde: rol, başlık bağı, odak tuzağı, Escape,
  odak iadesi (#395–#396); sekme çubuğu gerçek ARIA sekme örüntüsü (A11Y-002).
- 28 ikon-only butona ad (A11Y-003); meşgulken buton adı düşmüyor (#385); panel yüklemesi
  duyurulur (A11Y-010); her etiket bir girdiye bağlı (#448); form hatası duyurulur (#449);
  koç mesajı duyurulur, OS tema ve hareket tercihi dinlenir (#450).
- Kontrast 4.5:1 ve 0 ihlal (ölçülen: 756 → 0), odak halkası `focus-visible`, "içeriğe
  atla" bağlantısı (#441, A11Y-005/011); grafiklere veriden türeyen metin alternatifi
  (#451); axe-core e2e kapısı (#452); tarih biçimi `Intl` ile (#398); belge başlığı
  panelle değişir, slider adlı (#392).

### Operasyon, dağıtım ve gözlem
- Canlı yayın: Tailscale Funnel / Cloudflare Tunnel runbook'ları, DNS negatif önbellek
  bulgusu, tünel modunda nginx sonsuz yönlendirme (#283–#286); barındırma kararı (ADR-057).
- Windows servis paketi: `baslat.ps1` idempotent ve dizinden bağımsız (#367–#368, #371),
  `guncelle.ps1` çıkış kodu ve derleme (#341, #353, #373), sağlık görevi (#290, #303).
- Kesinti körlüğü bitti: dış izleme + ölü adam anahtarı (#342), onarım ölçümü yemiyor
  (#344, #359), canlı durum commit'e bağlı (#328), "neredeyiz" ölçüme sorulur (#357, #366).
- Sürüm damgası git HEAD'den (#294); korelasyon kimliği log↔yanıt↔ekran (#280); hatadan
  bildirime tek tık (#281); tarayıcı hataları sunucu defterine düşer (OBS-013); finansal
  kaydın güncelleme/silme izi (OBS-020); istek süresi her halkada ölçülür (OBS-016).
- Cron: kaçırılan gece işleri telafi edilir (#302), her iş çalışma kaydı tutar (#240),
  gece batch'i kullanıcı başına session (BE-029); otomatik yedek + geri yükleme provası.

### Geliştirme kalitesi (kalite serüveni)
- CI 30 koşumdur kırmızıydı, hiçbir kapı uzaktan korumuyordu — onarıldı (#295–#300);
  postgres dual-dialect kapıları gerçekten koşuyor; `npm audit` üretim/geliştirme ayrımı (#329).
- Gerileme sayaçları: ruff (#309), eslint (#474, react-hooks; 2 gerçek koşullu-hook
  defekti bulundu), coverage %94 kilitli (#308), ölü kod kapısı (#345, #352), belge
  denetimi (#310, #363), API sözleşmesi dondurma (#306), ağ kapısı (#307), kişisel veri
  ve sır taramaları, mutasyon skorları makine-okunur.
- pre-commit kancası: staged dosyaya göre pytest/vitest/kapı altkümesi/lint/sır taraması
  (#364, #380, #384); CI'da frontend lint + vitest işi (#474).
- Komutların tek kaynağı `python -m scripts.gorev` (#475); üretilen veri modeli belgesi
  (#473); üretilen backlog özeti (#348); 24 API ucu açıklamalı (#394);
  sürüm notu bayatlama kapısı ve yazılı yayın süreci, `v0.2.0`/`v0.3.0` etiketleri (#476).
- Bağımlılıklar tam sabit (#390); vite 8 (#301); alembic zinciri ve fresh-DB göç kilidi.

### Bilinen sınırlar
- Para birimi görüntülemesi TRY varsayımlı (ADR-042).
- Kimlik doğrulama gerektiren canlı doğrulamalar (TLS, 7/24 cron) yalnız gerçek sunucuda
  ölçülebilir; yerel Windows servisi tek makinedir.
- `react-hooks/set-state-in-effect` 27 uyarı tavanla izleniyor (sıfır değil); API `/v1/`
  ön eki yok (API-001 açık); frontend paketleme/dağıtım hattı yerel `guncelle.ps1` ile.

## [0.2.0] — 2026-08-05 — "Kapalı betaya hazırlık" (Wave-9)

Bu sürüm, uygulamayı **tek kişinin sistemi** olmaktan çıkarıp **yabancıların finansal
verisini taşıyabilecek** bir ürüne dönüştüren kapsamlı bir sertleştirme turudur.
39 bug (#162-#200) kapatıldı.

### Güvenlik
- Şifre sıfırlama token'ı production'da HTTP yanıtında dönüyordu (hesap ele geçirme) — kapatıldı (#170).
- `AUTH_ENABLED` production'da doğrulanmıyordu; compose dışı bir deploy TÜM API'yi kimliksiz
  açıyordu — startup fail-fast eklendi (#171).
- Şifre sıfırlama mevcut oturumları düşürmüyordu; çalınmış refresh token yaşamaya devam
  ediyordu — oturum geçersizleme sayacı, tek-kullanımlık sıfırlama, logout'ta access iptali (#172).
- OAuth access+refresh token'ları yönlendirme URL'inde taşınıyordu — tek-kullanımlık değişim
  koduna geçildi (#179); OAuth state stateless + PKCE (#185); refresh rotasyonu + tekrar-kullanım
  tespiti (#186); şifre politikası (#187).
- Rate limit proxy arkasında tek kovaya düşüyor ve çok-worker'da bölünüyordu (#182);
  davet ucunda limit yoktu (#183).
- Ham exception metni kullanıcıya dönüyordu (#175); girdi sınırları (#176, #177, #181);
  prod CORS localhost'a düşüyordu (#178); PII log temizliği (#180).
- Bağımlılıklarda 23 bilinen açık → 0 (PyJWT, authlib, starlette, cryptography dahil).

### Veri izolasyonu (çok kullanıcı)
- Hedef kuralları TÜM kullanıcılardan çekiliyordu: bir kullanıcının işlemi başkasının
  hedefine yazılıyordu (#162). Kalıcı statik + runtime kapılar eklendi.
- Çok-kullanıcı net-değer backfill (#163), yıkıcı temizlik script'i footgun'ı (#164),
  workspace kapsam tutarsızlığı (#165).

### Ürünleşme
- Metinlerde/koda gömülü kişi adları ve banka markaları temizlendi (#166, #168).
- Türkçe normalizasyon Kiril karakter üretiyordu — sessiz veri bozulması (#167).
- **Kullanıcının kendi kuralı artık kod seviyesinde dayatılıyor** (#192): nakit tabanı,
  dokunulmaz hesap, tek harcama tavanı.
- İsteğe bağlı demo veri + tam silinebilirlik (#194); onboarding kartı; kullanıcı saat
  dilimi (#197).

### Operasyon & uyum
- Kullanıcı başına LLM kotası (ADR-041, #188); giriş yapmış kullanıcı şifre değiştirebiliyor (#190).
- KVKK metinleri canlıda erişilemezdi (#191) — `/api/legal/*` + rıza v2 + kullanım şartları
  + veri-işleyen envanteri.
- Yedekten geri yükleme provası (SQLite + PostgreSQL), kendi kendine yeten hata izleme (#195),
  alembic zincir bütünlüğü (#193) ve config-URL izolasyonu (#196).
- Prod konteynerinde saat dilimi tanımsızdı (#169).

### Kapalı beta
- **Kayıt artık davetli-only** (production varsayılanı, fail-closed) — #199.
- Canlı doğrulama kapısı (`scripts/live_gate.py`) + Docker'sız production provası.

### Bilinen sınırlar
- Para birimi görüntülemesi TRY varsayımlı (ADR-042 — açık betadan önce).
- TLS/Let's Encrypt ve 7/24 cron yalnız gerçek sunucuda doğrulanabilir.

## [0.1.0] — 2026 öncesi
Wave-1…Wave-8: çekirdek uygulama, koç, workspace/RLS, PostgreSQL geçişi, deploy paketi, PWA.
