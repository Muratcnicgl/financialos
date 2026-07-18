# Mobil & PWA & offline (kod: MOB)

Kapsam: FinancialOS'i telefondan "uygulama gibi" kullanılabilir hale getiren teknik altyapı — PWA kurulumu, service worker/offline cache, safe-area, dokunma ergonomisi, backend senkronizasyon hazırlığı, push altyapısı ve React Native geçiş köprüsü.

`docs/architecture/mobile-roadmap.md` stratejik yol haritasını (PWA -> RN aşamaları, framework kıyası, UX pattern kataloğu) zaten içeriyor; burada o vizyonu **tekrarlamadan** uygulanabilir maddelere çeviriyorum. UX tarafında olan sekme/gesture/pull-to-refresh maddeleri (UX-011, UX-018, UX-024, UX-029) ile FE tarafındaki dokunma hedefi maddeleri (FE-019) burada mobil-teknik derinlikle **tamamlanır**, birebir kopyalanmaz.

Not: Coach paneli mobile-roadmap yazıldığı sırada `h-[calc(100vh-180px)]` sabit yükseklik kullanıyordu; bugünkü kodda (`frontend/src/panels/Coach.jsx:366`, `:471`) zaten flex + `sticky bottom-0` + `pb-[env(safe-area-inset-bottom)]` var. O madde kapandı; aşağıdakiler kalan gerçek eksikler.

---

### [MOB-001] vite-plugin-pwa yok — hiç manifest, hiç service worker
- **Durum:** ⏸️ KAPSAM DIŞI — M85 R3 doğrulama: vite-plugin-pwa yok (PWA-deferred)

- **Sorun:** Uygulama PWA değil. "Ana ekrana ekle" yapılsa bile tam ekran açılmaz, offline çalışmaz, splash/icon yoktur. Mobil-first hedefin (mobile-roadmap Aşama 1) tek somut ön koşulu eksik.
- **Kanıt:** `frontend/package.json:12-27` — bağımlılıklarda `vite-plugin-pwa` yok. `frontend/vite.config.js:10` — `plugins: [react()]`, PWA plugin'i yok. `frontend/index.html:1-32` — `<link rel="manifest">` yok, service worker register eden kod yok.
- **Aksiyon:** `npm i -D vite-plugin-pwa` ekle; `vite.config.js`'te `VitePWA({ registerType: 'prompt', ... })` (autoUpdate yerine prompt — bkz. MOB-008). Bu tek plugin manifest + Workbox SW üretir. Diğer tüm MOB maddeleri bunun üzerine oturur.
- **Etki:** Yüksek (tüm mobil hikayenin temeli) · **Efor:** S (kurulum ~1-2 saat)
- **Kaynak:** [vite-pwa generateSW](https://vite-pwa-org.netlify.app/workbox/generate-sw)

### [MOB-002] manifest.json ikon seti eksik — favicon tek bir inline SVG
- **Durum:** ⏸️ KAPSAM DIŞI — M85 R3 doğrulama: PNG ikon/manifest yok (PWA-deferred)

- **Sorun:** Manifest için gereken 192/512 px PNG ikonları, `maskable` ikon ve iOS için `apple-touch-icon` yok. Bunlar olmadan ana ekran ikonu bozuk/boş çıkar, Android maskeleme kenarları keser.
- **Kanıt:** `frontend/index.html:5` — tek `rel="icon"` bir data-URI SVG (32x32). PNG asset yok; `frontend/public/` altında ikon dosyası bulunmuyor.
- **Aksiyon:** `192x192`, `512x512` ve ayrı bir `512x512 purpose:"maskable"` (güvenli alan ~%80) PNG üret, `apple-touch-icon` (180x180) ekle. VitePWA manifest'inde `icons[]` ve `theme_color: '#0f172a'` / `background_color` tanımla. Marka ₺ logosunu (mevcut brand-400/600 gradyanı, `App.jsx:116`) baz al.
- **Etki:** Orta (kurulan uygulamanın ilk izlenimi) · **Efor:** S

### [MOB-003] App shell precache stratejisi tanımsız — offline'da beyaz ekran
- **Durum:** ⏸️ KAPSAM DIŞI — M85 R3 doğrulama: workbox/precache yok (offline-deferred)

- **Sorun:** SW olmadan bağlantı koptuğunda uygulama hiç açılmaz (JS/CSS bundle yüklenemez). Metro/asansör/uçak modu senaryosu = kullanılamaz uygulama.
- **Kanıt:** `frontend/src/api.js:59-64` — network hatası `ApiError(0)` fırlatır; ama asıl sorun, HTML/JS/CSS'in kendisinin cache'lenmemesi. `vite.config.js`'te `workbox` bloğu yok.
- **Aksiyon:** VitePWA `workbox.globPatterns: ['**/*.{js,css,html,svg,png,woff2}']` ile build çıktısını precache et. Google Fonts `@import` (`index.css:2`) offline'da patlar — fontları `frontend/public/`'e indirip self-host et ya da `runtimeCaching` ile CacheFirst'e al (aksi halde offline'da Inter/JetBrains yüklenmez).
- **Etki:** Yüksek (offline açılış) · **Efor:** M

### [MOB-004] Cockpit için NetworkFirst offline fallback yok
- **Durum:** ⏸️ KAPSAM DIŞI — M85 R3 doğrulama: cockpit runtimeCaching yok (offline-deferred)

- **Sorun:** Cockpit ana ekran; bağlantı koptuğunda son bilinen finansal görüntü bile gösterilemiyor. Kullanıcı en sık bakacağı ekranda "bağlantı hatası" görür.
- **Kanıt:** `frontend/src/api.js:105-107` `cockpitApi.get() -> /api/cockpit`. Cache katmanı yok; `App.jsx:196` main içerik doğrudan canlı fetch'e bağlı.
- **Aksiyon:** VitePWA `runtimeCaching` ile `/api/cockpit` için `handler: 'NetworkFirst'`, `networkTimeoutSeconds: 3`, `expiration: { maxAgeSeconds: 300 }`. 3 sn içinde ağ gelmezse son cache'lenmiş cockpit gösterilir; UI'da "çevrimdışı — son güncelleme HH:MM" rozeti ekle (MOB-007 ile birlikte).
- **Etki:** Yüksek · **Efor:** S
- **Kaynak:** [Workbox NetworkFirst / vite-pwa caching strategies](https://vite-pwa-org.netlify.app/workbox/generate-sw) — NetworkFirst ağı önce dener, timeout/başarısızlıkta cache'e düşer; sık güncellenen API cevapları için önerilen strateji.

### [MOB-005] Salt-okunur listeler için ayrı cache stratejisi yok
- **Durum:** ⏸️ KAPSAM DIŞI — M85 R3 doğrulama: SWR cache yok (offline-deferred)

- **Sorun:** Cockpit dışındaki GET ekranları (raporlar, hesaplar, işlemler, cashflow, hedefler) offline'da tümden boş. Bunların çoğu "son görüneni göster, arkada tazele" mantığına uygun ama tek tip strateji uygulanamıyor.
- **Kanıt:** `frontend/src/api.js` — `reportsApi` (`:235`), `accountsApi.list` (`:114`), `transactionsApi.list` (`:126`), `cashflowApi` (`:269`), `goalsApi.list` (`:293`) hepsi cache'siz GET.
- **Aksiyon:** Bu GET uçları için `StaleWhileRevalidate` (anında cache'ten göster + arkada güncelle), `expiration.maxEntries` sınırlı. Yazma uçları (POST/PUT/PATCH/DELETE) cache'e **girmemeli** — `urlPattern` yalnız GET'i yakalamalı (`method: 'GET'`).
- **Etki:** Orta · **Efor:** M

### [MOB-006] Offline yazma kuyruğu yok — girilen işlem kaybolur
- **Durum:** ⏸️ KAPSAM DIŞI — M85 R3 doğrulama: outbox/BackgroundSync yok (offline-write deferred)

- **Sorun:** Mobil-first mimaride kullanıcı bağlantısızken de işlem/gelir/aksiyon girer. Şu an offline POST/PUT anında `ApiError(0)` ile ölür; optimistic write veya kuyruk yok. Kullanıcı "kaydettim" sanır, veri yok olur.
- **Kanıt:** `frontend/src/api.js:33-64` `request()` — tek atış fetch, retry/queue yok. `transactionsApi.create` (`:120`), `actionsApi.approve` (`:215`) dahil tüm mutasyonlar bu yolu kullanır.
- **Aksiyon:** Kısa vade: mutasyon başarısız olursa IndexedDB/`localStorage` "outbox" kuyruğuna yaz, `navigator.onLine` true olunca flush et; UI'da "gönderilmeyi bekliyor" durumu göster. Orta vade: Workbox `BackgroundSyncPlugin` ile POST'ları otomatik replay. Uzun vade (RN): mobile-roadmap'teki local-first SQLite sync kuyruğu.
- **Etki:** Yüksek (veri güvenliği) · **Efor:** L
- **Kaynak:** [Workbox Background Sync](https://developer.chrome.com/docs/workbox/modules/workbox-background-sync)

### [MOB-007] Uygulama seviyesinde offline durumu yok — sadece backend health polling var
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: navigator.onLine event dinleyici yok (App.jsx:65)

- **Sorun:** Bağlantı durumu yalnızca backend'e 5 sn'de bir atılan health isteğiyle anlaşılıyor; cihazın gerçek offline durumu (`navigator.onLine`, `online`/`offline` event) dinlenmiyor. Offline'da 5 sn'lik gecikme + gereksiz istek trafiği; ayrıca cache'ten servis edilen veri "bayat" olarak işaretlenmiyor.
- **Kanıt:** `frontend/src/App.jsx:54-81` `useBackendHealth` — sadece `setInterval(check, 5000)`. `App.jsx:185-194` offline banner yalnız bu health'e bağlı; `window.addEventListener('offline'...)` yok.
- **Aksiyon:** `navigator.onLine` + `online`/`offline` event dinleyicisi ekle; offline'ken health polling'i durdur (pil/veri tasarrufu). Offline modda cache'ten gelen ekranlara "çevrimdışı — son güncelleme HH:MM" rozeti bas (MOB-004 verisiyle).
- **Etki:** Orta · **Efor:** S

### [MOB-008] Service worker güncelleme akışı planlanmamış — deploy sonrası bayat bundle riski
- **Durum:** ⏸️ KAPSAM DIŞI — M85 R3 doğrulama: service worker yok (PWA-deferred)

- **Sorun:** PWA'da klasik tuzak: SW eski asset'leri precache'te tutar, kullanıcı deploy sonrası günlerce eski sürümü görür. `autoUpdate` sessizce günceller ama açık sekmede yarım güncelleme/kırık state üretebilir.
- **Kanıt:** Henüz SW yok (MOB-001); ama mobile-roadmap örneği `registerType: 'autoUpdate'` öneriyor — finansal uygulamada sessiz güncelleme riskli.
- **Aksiyon:** `registerType: 'prompt'` kullan; `virtual:pwa-register`'in `onNeedRefresh` callback'iyle mevcut Toast altyapısına (`frontend/src/components/Toast.jsx`) "Yeni sürüm hazır — yenile" aksiyonlu bildirim bas. Kullanıcı onaylayınca `updateServiceWorker(true)`.
- **Etki:** Orta · **Efor:** S
- **Kaynak:** [vite-pwa Prompt for update](https://vite-pwa-org.netlify.app/guide/prompt-for-update.html)

### [MOB-009] theme-color meta sabit — açık temada ve standalone status bar yanlış renk
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: theme-color meta statik, useTheme güncellemez

- **Sorun:** Standalone (ana ekrandan açılan) PWA'da status bar / tarayıcı çubuğu rengi `theme-color`'dan gelir. Sabit koyu `#0f172a`, kullanıcı açık temaya geçince (`App.jsx` `useTheme`) uyumsuz kalır — açık temada koyu şerit görünür.
- **Kanıt:** `frontend/index.html:7` `<meta name="theme-color" content="#0f172a">` statik. `frontend/src/App.jsx:43-48` tema değişiminde yalnız `<html>.dark` class'ı güncelleniyor, meta güncellenmiyor.
- **Aksiyon:** `useTheme` effect'inde `document.querySelector('meta[name=theme-color]').setAttribute('content', theme === 'dark' ? '#0f172a' : '#fafafa')`. Alternatif: iki `theme-color` meta'sı `media="(prefers-color-scheme)"` ile.
- **Etki:** Düşük (kozmetik ama standalone'da göze batar) · **Efor:** XS

### [MOB-010] iOS standalone meta etiketleri eksik — Safari çubuğu tam ekranı yer
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: apple-mobile-web-app meta yok

- **Sorun:** iOS'ta ana ekrandan açılan PWA'nın tam ekran davranışı ve status bar stili `apple-mobile-web-app-*` meta'larına bağlı. Yoksa iOS eski/kısıtlı davranış uygular, status bar rengi/şeffaflığı kontrol edilemez.
- **Kanıt:** `frontend/index.html:3-27` head — `apple-mobile-web-app-capable`, `apple-mobile-web-app-status-bar-style`, `apple-mobile-web-app-title` yok.
- **Aksiyon:** Head'e `<meta name="apple-mobile-web-app-capable" content="yes">`, `<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">` (viewport-fit=cover ile birlikte notch altına çizim), `<meta name="apple-mobile-web-app-title" content="FinancialOS">` ekle. `mobile-web-app-capable` (Android) da ekle.
- **Etki:** Orta (iOS deneyimi) · **Efor:** XS
- **Kaynak:** [WebKit — Web Push / Home Screen web apps](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/)

### [MOB-011] Header üst safe-area yok — notch/dynamic island başlığı örtüyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: safe-area-inset-top yok

- **Sorun:** `viewport-fit=cover` zaten açık, yani içerik çentik altına uzanabiliyor; ama sticky header'da `env(safe-area-inset-top)` padding yok. Standalone'da (özellikle iPhone dynamic island) başlık ve sekme çubuğu çentiğin altında kalır/kesilir.
- **Kanıt:** `frontend/index.html:6` `viewport-fit=cover` var. `frontend/src/App.jsx:113-114` header `sticky top-0 ... px-4 py-3` — üst inset padding'i yok.
- **Aksiyon:** Header dış sarmalayıcıya `pt-[env(safe-area-inset-top)]` (Tailwind arbitrary değeri) ekle; header arkaplanı zaten `backdrop-blur` olduğu için inset alan da renklenir. Offline banner (`App.jsx:185`) header altında olduğu için ek inset gerekmez.
- **Etki:** Orta · **Efor:** XS

### [MOB-012] Yatay safe-area yok — landscape'te çentik içeriği kesiyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: safe-area-inset-left/right yok

- **Sorun:** Yatay modda (iPhone landscape) çentik sol/sağdadır; `env(safe-area-inset-left/right)` uygulanmazsa içerik ve dokunma hedefleri çentik altında kalır.
- **Kanıt:** `frontend/src/App.jsx:114`, `:197` — `px-4` sabit yatay padding, safe-area inset yok. Tüm paneller bu `max-w-6xl mx-auto px-4` konteynerinden geçiyor.
- **Aksiyon:** Ana konteyner padding'ini `px-4` yerine `pl-[max(1rem,env(safe-area-inset-left))] pr-[max(1rem,env(safe-area-inset-right))]` yap (veya index.css'te bir `.safe-x` utility). Tek noktada değişiklik tüm panelleri kapsar.
- **Etki:** Düşük-Orta (yalnız landscape) · **Efor:** XS

### [MOB-013] Bottom nav teknik uygulaması yok (UX-011'in mobil-teknik tamamlayıcısı)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: bottom nav yok

- **Sorun:** UX-011 alt navigasyon ihtiyacını (10 sekme yatay scroll'a sıkışıyor) tanımlıyor; burada eksik olan **teknik karar**: standalone tespiti, hangi 5 sekmenin görünüp hangilerinin "Daha" bottom sheet'ine gireceği, ve alt çubuğun home-indicator ile çakışmaması.
- **Kanıt:** `frontend/src/App.jsx:163-182` — tek `<nav>` üstte, `overflow-x-auto`, 10 sekme (`TABS`, `:22-33`). Bottom nav bileşeni yok.
- **Aksiyon:** `md:` altında `fixed bottom-0` alt çubuk: en sık 4 sekme (Cockpit, Koç, İşlemler, Hesaplar) + "Daha" (kalan 6 sekme bottom sheet). Çubuğa `pb-[env(safe-area-inset-bottom)]`; main'e alt çubuk yüksekliği kadar `pb`. Masaüstünde (`md:` üstü) mevcut üst sekmeler kalır. Aktif sekme rengi mevcut brand-500 border pattern'iyle tutarlı.
- **Etki:** Yüksek (mobil temel navigasyon) · **Efor:** M

### [MOB-014] Üst sekme şeridinde aktif sekme görünüre kaydırılmıyor + scroll ipucu yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: aktif sekme scrollIntoView yok

- **Sorun:** 10 sekme yatay scroll'da; klavye kısayoluyla (`useKeyboardShortcuts`) veya derin sekmeye geçince aktif sekme görünür alanın dışında kalabilir, kullanıcı nerede olduğunu görmez. Kaydırılabilir olduğuna dair görsel ipucu (kenar gölgesi) da yok.
- **Kanıt:** `frontend/src/App.jsx:164` `overflow-x-auto`, `:166-179` sekme butonları — aktif sekmede `scrollIntoView` çağrısı yok.
- **Aksiyon:** Aktif sekme değişince `ref.scrollIntoView({ inline: 'center', behavior: 'smooth' })`. Şeridin sağ/sol kenarına `mask-image` linear-gradient ile "devamı var" fade ipucu. (Bottom nav'a geçilse bile masaüstü/tablet üst şerit için geçerli.)
- **Etki:** Düşük · **Efor:** S

### [MOB-015] Üst sekme dokunma hedefleri 44px altında (FE-019'un tab tamamlayıcısı)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: sekme butonu min-h-44px yok

- **Sorun:** FE-019 ikon-only butonların 44px altını genel olarak işaret ediyor; buradaki spesifik ve en çok dokunulan hedef sekme butonları: `py-2.5` (~10px) + `text-sm` satır yüksekliğiyle toplam ~40px, Apple HIG/Material 44-48px eşiğinin altında. Yanlış sekmeye basma mobilde sık.
- **Kanıt:** `frontend/src/App.jsx:170` sekme butonu `px-3 py-2.5 text-sm`. Not: `.btn` ve `.btn-icon` global class'ları `index.css:70-75` zaten `min-h-[44px]` içeriyor — ama sekme butonları bu class'ları kullanmıyor, ham utility.
- **Aksiyon:** Sekme butonlarına `min-h-[44px]` ekle (veya mobilde `py-3`). Bottom nav'a geçilirse orada da her hedef 44x44 taban. Header'daki tema/health chip'leri zaten `btn-icon` ile uyumlu; asıl açık burada.
- **Etki:** Orta · **Efor:** XS

### [MOB-016] Coach textarea sabit 2 satır + yazılım klavyesi girişi örtüyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: textarea auto-grow/visualViewport yok

- **Sorun:** Mobilde uzun mesaj yazarken 2 satır sabit alan yetmez (auto-grow yok); ayrıca yazılım klavyesi açılınca `sticky bottom-0` input klavyenin arkasında kalabilir çünkü layout `h-dvh`'e göre değil klavye-öncesi yüksekliğe göre.
- **Kanıt:** `frontend/src/panels/Coach.jsx:472-481` `<textarea rows={2} ... resize-none>` — auto-grow yok. `:471` input barı `sticky bottom-0 pb-[env(safe-area-inset-bottom)]` (iyi başlangıç) ama klavye görünürlüğüne tepki vermiyor.
- **Aksiyon:** Textarea auto-grow (scrollHeight ile 1-5 satır arası). Klavye için `visualViewport` API dinle: klavye açılınca scroll alanını `visualViewport.height`'a göre daralt, gönder sonrası son mesaja scroll (`scrollRef`, `:188-192` zaten var). `App.jsx:112`'deki `h-dvh` iOS'ta dinamik viewport'u takip eder — bunu koru.
- **Etki:** Orta · **Efor:** M

### [MOB-017] 100vh/dvh doğrulaması ve iOS eski Safari fallback
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: h-dvh fallback yok

- **Sorun:** Kök yükseklik `h-dvh`'e taşınmış (doğru tercih), ama `dvh` desteklemeyen eski WebView/Safari'de (iOS <15.4) layout çökebilir; ayrıca alt sabit input/nav ile birleşince "adres çubuğu gizlenince zıplama" testi yapılmamış.
- **Kanıt:** `frontend/src/App.jsx:112` `h-dvh flex flex-col overflow-hidden`. Fallback (`min-h-screen`) veya `@supports` yok.
- **Aksiyon:** `h-dvh` iyi; ancak `h-[100vh] h-dvh` sıralı fallback (Tailwind: `min-h-screen supports-[height:100dvh]:h-dvh`) ekle. Gerçek cihaz testi: iOS Safari + Android Chrome'da adres çubuğu gizlenirken/görünürken alt input konumu.
- **Etki:** Düşük · **Efor:** XS

### [MOB-018] Backend sync altyapısı yok — tabloların çoğunda updated_at/version/soft-delete yok
- **Durum:** ⏸️ KAPSAM DIŞI — M85 R3 doğrulama: is_deleted/version RN-sync ertelendi

- **Sorun:** Mobil offline-first (mobile-roadmap Bölüm 4) last-write-wins sync gerektirir; bunun ön koşulu her tabloda değişiklik zaman damgası + soft delete. Şu an yalnız iki model bunu taşıyor; Transaction/Debt/Income/Checkpoint gibi çekirdek tablolarda conflict tespiti imkânsız.
- **Kanıt:** `app/models.py:176-177` (Account) ve `:779-781` (Goal) `updated_at ... onupdate=datetime.utcnow` var; ama `:123`, `:197`, `:217`, `:234`, `:261`, `:281`, `:330`, `:420`, `:512` tabloları yalnız `created_at`. Hiçbirinde `version` veya `is_deleted` yok. Silme = fiziksel `DELETE` (`api.js:118`, `:136`, `:148` vb.).
- **Aksiyon:** RN aşamasına girmeden **önce** tüm senkronize edilecek tablolara `updated_at (onupdate)` + `is_deleted Boolean` ekle (Alembic yerine tek migration script'i, `scripts/`). Delete endpoint'lerini soft-delete'e çevir. Bu backend değişikliği web'i bozmaz ama RN sync'in ön koşuludur.
- **Etki:** Yüksek (RN geçişinin bloklayıcısı) · **Efor:** L

### [MOB-019] Sync/pagination ucu yok — büyük listeler tek seferde iniyor
- **Durum:** ⏸️ KAPSAM DIŞI — M85 R3 doğrulama: offset/cursor/updated_since mobil-sync ertelendi

- **Sorun:** Mobilde 1000+ işlem tek istekte inince ilk açılış yavaş + bellek baskısı; ayrıca "son sync'ten beri değişenler" sorgusu (delta sync) mümkün değil — cursor/`since` parametresi yok.
- **Kanıt:** `app/routers/transactions.py:200-208` — `limit: int = 200 ... .limit(limit).all()`, `offset`/cursor yok. `api.js:126` `transactionsApi.list(params)` yalnız düz filtre geçiriyor.
- **Aksiyon:** Liste uçlarına `updated_since` (delta) + cursor/`offset` ekle; dönüş zarfına `next_cursor`/`has_more`. Tek seferlik `POST /api/sync` (cihaz pending + last_sync -> sunucu delta) mobile-roadmap Bölüm 5'te tarif edilmiş — MOB-018 tamamlanınca inşa edilebilir. Web frontend'e dokunmadan additive yapılabilir.
- **Etki:** Orta (mobil ölçek) · **Efor:** M

### [MOB-020] Push bildirim altyapısı yok — cihaz token tablosu/FCM/APNs yok
- **Durum:** ⏸️ KAPSAM DIŞI — M85 R3 doğrulama: device-token/push altyapısı yok

- **Sorun:** "Vade yaklaştı / limit aşıldı / beklenen gelir geldi" uyarıları mobilde push olmadan işe yaramaz. Backend'de zaten `trigger-due` mantığı var (gelir/gider) ama bunları cihaza itecek kanal yok.
- **Kanıt:** `app/models.py` içinde device-token tablosu yok (grep: sadece created_at/updated_at kolonları). `api.js` — push register ucu yok. `incomesApi.triggerDue` (`:149`), `expensesApi.triggerDue` (`:161`) sadece DB'ye işlem yazıyor, bildirim üretmiyor.
- **Aksiyon:** `push_subscriptions` tablosu (user_id, endpoint/token, platform, keys). Web push için VAPID + Workbox `push` event handler; native için sonra FCM/APNs. Backend'de `apscheduler` ile günlük "vade taraması" -> push. Önce web push (PWA) yeterli.
- **Etki:** Yüksek (proaktif koç vizyonu) · **Efor:** L
- **Kaynak:** [WebKit Web Push for Home Screen web apps](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/)

### [MOB-021] iOS web push ön koşulu ele alınmamış — ana ekrana ekleme + kullanıcı jesti şart
- **Durum:** ⏸️ KAPSAM DIŞI — M85 R3 doğrulama: push standalone ertelendi

- **Sorun:** iOS'ta (16.4+) web push **yalnız** PWA ana ekrana eklendiğinde ve izin isteği **doğrudan kullanıcı dokunuşuyla** tetiklendiğinde çalışır. Bu kural kod seviyesinde aşılamaz; UI bunu bilmeli, yoksa iOS kullanıcısına çalışmayan bir "bildirim aç" düğmesi gösterilir.
- **Kanıt:** MOB-020'deki altyapı yok; ayrıca standalone tespiti (`window.matchMedia('(display-mode: standalone)')`) kod tabanında hiç kullanılmıyor (grep: yok).
- **Aksiyon:** İzin isteğini yalnız standalone modda ve açık bir "Bildirimleri aç" butonuna basınca (`Notification.requestPermission`) yap. Standalone değilse iOS'ta "önce Paylaş -> Ana Ekrana Ekle" yönergesi göster (MOB-022 ile ortak). Android/Chrome'da bu kısıt yok.
- **Etki:** Orta · **Efor:** S
- **Kaynak:** [WebKit Web Push blog](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/); [OneSignal iOS web push kurulumu](https://documentation.onesignal.com/docs/web-push-for-ios) — iOS'ta home-screen kurulumu ve kullanıcı jesti zorunluluğu.

### [MOB-022] Install prompt yakalanmıyor — "Ana ekrana ekle" keşfedilemiyor
- **Durum:** ⏸️ KAPSAM DIŞI — M85 R3 doğrulama: beforeinstallprompt (PWA-deferred)

- **Sorun:** Android/Chrome `beforeinstallprompt` event'i yakalanıp saklanmazsa özel bir "Uygulamayı yükle" düğmesi gösterilemez; iOS'ta zaten otomatik prompt yok, manuel yönerge gerekir. Kullanıcı uygulamayı yükleyebileceğini hiç fark etmez.
- **Kanıt:** `frontend/src/App.jsx` genelinde `beforeinstallprompt` dinleyicisi yok (grep: yok). Manifest de olmadığı için (MOB-001) event zaten hiç tetiklenmez.
- **Aksiyon:** Manifest kurulduktan sonra `beforeinstallprompt`'u yakala, `preventDefault` + event'i sakla; uygun bir yerde (örn. header veya ilk açılış toast'ı) "Ana ekrana ekle" düğmesi göster, tıklanınca `prompt()`. iOS için `display-mode: standalone` değilse "Paylaş -> Ana Ekrana Ekle" mini yönergesi.
- **Etki:** Orta (edinim/keşfedilebilirlik) · **Efor:** S

### [MOB-023] Pull-to-refresh teknik uygulaması (UX-024'ün mobil-teknik tamamlayıcısı)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: overscroll-behavior/pull-to-refresh yok

- **Sorun:** UX-024 pull-to-refresh isteğini tanımlıyor; teknik boşluk: main scroll konteyneri tarayıcının native PTR'siyle çakışabilir, `overscroll-behavior` ayarı yok ve standalone'da native PTR olmadığından custom jest gerekir.
- **Kanıt:** `frontend/src/App.jsx:196` `<main className="flex-1 overflow-y-auto overflow-x-hidden">` — `overscroll-behavior` yok; kendi PTR mantığı yok. Cockpit/Transactions listeleri bu main içinde scroll ediyor.
- **Aksiyon:** Standalone PWA'da (native PTR yoktur) touch-tabanlı PTR: scrollTop 0'dayken aşağı çekişte spinner + ilgili panelin fetch'ini yeniden çağır (Cockpit `cockpitApi.get`, Transactions `list`). Yanlışlıkla sayfa yenilemeyi önlemek için `overscroll-behavior-y: contain`. Masaüstünde mevcut yenile butonu kalır.
- **Etki:** Orta · **Efor:** M

### [MOB-024] Modal'lar mobilde tam ekranı kaplıyor — bottom sheet pattern'i yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: paylaşılan BottomSheet yok

- **Sorun:** Merkez modal'lar mobilde ekranı komple örter, tek elle kapatmak zor (kapat düğmesi üstte). Mobile-roadmap Pattern 5 bottom sheet öneriyor; bu maddeler halen merkez-modal.
- **Kanıt:** `frontend/src/components/HelpModal.jsx`, `CommandPalette.jsx`, `PremortemModal.jsx`, `HorizonsModal.jsx` — hepsi merkez overlay. `PendingActions` detay/onay akışı da inline. (Grep: `grid-cols` bu modal dosyalarında var; mobilde tek kolona düşürme + alt yerleşim gerekli.)
- **Aksiyon:** Paylaşılan bir `<BottomSheet>` bileşeni (mobilde `fixed bottom-0`, drag-to-dismiss, `pb-[env(safe-area-inset-bottom)]`); `md:` üstünde mevcut merkez-modal görünümüne düş. Önce en sık kullanılan Pending action onayı ve CommandPalette. Web davranışı `md:` breakpoint üstünde değişmez.
- **Etki:** Orta · **Efor:** M

### [MOB-025] api.js RN'e taşınmaya hazır değil — sabit relative /api, yapılandırılabilir base URL yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: import.meta.env BASE soyutlaması yok

- **Sorun:** mobile-roadmap Aşama 2'de backend aynı kalıp yalnız API client RN'e taşınacak. Ama client Vite proxy'sine (`/api` relative) bağımlı; RN'de proxy yok, mutlak `https://host/api` gerekir. Şu haliyle client doğrudan yeniden kullanılamaz.
- **Kanıt:** `frontend/src/api.js:4-5` yorum: "BASE_URL gerekmiyor, fetch('/api/cockpit') yeterli"; `:34` `let url = path` — mutlak base yok, `import.meta.env`/config yok. (Olumlu: tüm çağrılar tek `request()`'ten geçiyor, `:33` — merkezileştirme RN'e taşımayı kolaylaştırır.)
- **Aksiyon:** `const BASE = import.meta.env.VITE_API_BASE ?? ''` ekle, `request()`'te `BASE + url`. Web'de boş (proxy korunur), RN/prod'da mutlak host verilir. Bu tek satırlık soyutlama, client'ı platform-bağımsız kılıp RN geçişinde kopyalanabilir yapar; ayrıca auth eklendiğinde (mobile-roadmap Şart 1) `Authorization` header'ı tek noktadan enjekte edilir.
- **Etki:** Orta (RN köprüsü + auth hazırlığı) · **Efor:** XS
