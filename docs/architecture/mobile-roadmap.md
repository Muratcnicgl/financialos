# FinancialOS — Mobil Mimari Tarama

**Hazırlanma tarihi:** 8 Mayıs 2026
**Mevcut stack:** FastAPI + SQLite (backend) + React + Vite + Tailwind (frontend)
**Hedef:** Web'i koruyarak mobil-first deneyime evril, sonunda native iOS/Android uygulaması

---

## 1. Stratejik Karar Noktası — Üç Yol

Mobile'a geçişin üç ana paradigması var. Her birinin trade-off'u farklı, hangisini seçeceğin **uzun vadeli vizyona** bağlı.

### Yol A — PWA (Progressive Web App)

**Ne:** Mevcut React + Vite uygulamana service worker, manifest.json, offline cache ekleyip "ana ekrana ekle" özelliği veriyorsun. Tek kod tabanı, hem web hem "app gibi davranan" mobile.

**Artıları:**
- Mevcut kodun %95'i korunur. 2-4 haftalık iş.
- App Store onay süreci yok, anlık deploy.
- Geliştirme akışın değişmez (asistan araci + PyCharm + uvicorn aynı kalır).
- iOS 16.4+ artık PWA push notification destekliyor.

**Eksileri:**
- iOS'ta hala ikinci sınıf vatandaş — Safari engine'e bağlısın, native API'ler kısıtlı.
- App Store'da yok = keşfedilebilirlik düşük.
- Background sync, biometric auth, widget gibi şeyler limitli.
- Klavye davranışı, scroll, haptic feedback native kadar iyi olmuyor.

**Kim seçer:** "Mevcut sistemi yıkmadan mobile'a yaklaşmak istiyorum" diyenler. **Senin için:** Wave-2/Wave-3 bitene kadar geçici çözüm olarak çok uygun.

### Yol B — React Native + Expo (önerilen ana hedef)

**Ne:** Frontend'i sıfırdan React Native ile yazıyorsun ama JavaScript bilgini ve component patternlerini koruyorsun. Backend (FastAPI + SQLite) **olduğu gibi kalır**.

**Artıları:**
- Native performans, native UI komponentleri (iOS'ta UIKit, Android'de Material).
- **Expo SDK** ile hızlı geliştirme: `expo-sqlite` (yerel DB), `expo-secure-store` (token), `expo-notifications` (push), `expo-haptics` (titreşim), biometrik auth, widget desteği — hepsi hazır.
- React bilgin transfer olur. Tailwind yerine **NativeWind** (RN için Tailwind portu) var.
- App Store + Google Play dağıtımı.
- **EAS Build** ile cloud build, sertifika derdi yok.
- iOS + Android tek kod tabanı.

**Eksileri:**
- Frontend'i yeniden yazmak gerekir (panellerin pattern'i aynı kalır ama JSX → RN component'leri).
- Native module gerektiren özelliklerde "eject" zorluğu (Expo ile büyük oranda kaçınılır).
- Web tarafını da korumak istersen iki ayrı frontend olur (veya **Solito**/Tamagui ile ortak).

**Kim seçer:** "Tek kod tabanı, native deneyim, JS dünyasında kalmak" diyenler. **Senin için:** Wave-3 fazının doğal hedefi.

### Yol C — Flutter

**Ne:** Dart dili öğrenip Flutter ile sıfırdan yazıyorsun. Backend yine FastAPI kalır.

**Artıları:**
- Native'e en yakın performans, custom rendering engine (Skia/Impeller).
- iOS + Android + web + desktop hepsi tek kod.
- Animasyon ve micro-interactionlarda en güçlü framework.
- Google'un ardındaki yatırım (Fuchsia OS).

**Eksileri:**
- **Yeni dil öğrenmek** (Dart). React/JS bilgisini doğrudan kullanamıyorsun.
- Ekosistem RN'den daha küçük, paket çeşitliliği az.
- Türkçe topluluk küçük.

**Kim seçer:** "Performans her şeyden önemli, yeni dil öğrenmeye varım" diyenler. **Senin için:** RN'in ekosistemi ve mevcut React tecrüben göz önüne alınınca **Flutter ikinci tercih kalmalı**.

### Önerilen Strateji — İki Aşamalı

**Aşama 1 (Wave-2 sonu / Wave-3 başı): PWA**
Mevcut webe service worker + manifest ekle. 1-2 hafta. Telefondan "app gibi" kullanılabilir hale gelsin. Acil mobile ihtiyacın için köprü.

**Aşama 2 (Wave-3+): React Native + Expo**
Frontend'i sıfırdan RN ile yaz. Backend (FastAPI) aynı kalır — sadece API client'ı RN'e taşırsın. Hedef: App Store + Google Play yayını.

**Neden bu sıralama:** PWA aşaması mobile UX'i öğrenmeni sağlar. Hangi pattern'lerin çalışıp çalışmadığını web'de test eder, RN'e geçtiğinde "ne yapılmalı" konusunda tecrübeli olursun. Yıkıcı geçiş yerine progresif öğrenme.

---

## 2. Mobil Finans UX — Sektör Liderlerinden Dersler

### Copilot Money (iOS, Apple-only) — Tasarım Standardı

**Ne yapıyor iyi:**
- **Native his**: iOS Tasarım Sistemi'ne tam uyum. SF Symbols, native sheet'ler, haptic feedback.
- **Widget desteği**: Ana ekranda "bu ayki harcama" widget'ı.
- **Apple Watch komplikasyonu**: Saatten anlık balance.
- **Apple Shortcuts entegrasyonu**: "Hey Siri, son hafta kahve harcamam ne kadar?"

**Senin için ders:** Mobile'da **OS-native widget + saat + voice** üçlüsü "bonus özellik" değil, ana fark yaratıcı. Wave-3'te düşün.

### Monarch Money (iOS + Android + Web)

**Ne yapıyor iyi:**
- **Cross-device sync**: Web'de yaptığın değişiklik saniyeler içinde telefonda. Web ve mobile aynı layout mantığı (şaşırtmıyor).
- **Couples mode**: İki kişi aynı veriye, iki ayrı view.
- **Plaid/MX entegrasyonu**: 11.000+ banka otomatik bağlanıyor.

**Senin için ders:** Türkiye'de Plaid yok ama **Open Banking** geliyor (BDDK 2024 yönetmeliği). Bu altyapı 2026-2027'de olgunlaşacak. Şimdiden API katmanını bu beklentiyle tasarla — manuel entry'yi default tut, ileride otomasyon ekle.

### YNAB (zero-based budgeting)

**Ne yapıyor iyi:**
- **Klavye-merkezli web**, **gesture-merkezli mobile**: Web'de Tab/Enter/Esc, mobile'da swipe-to-categorize, swipe-to-approve.
- **Felsefe odaklı**: Her doların bir görevi var. Bu sadece UI değil, mental model.

**Senin için ders:** Senin "FinancialOS" dediğin sistemin de bir felsefesi var (Mustafa mimarisi: Rules Engine karar verir, LLM açıklar). Bu felsefeyi UX'e yansıtmak rakiplerine karşı en büyük diferansiyatörün.

### Bank of America "Erica" — AI Asistanlı Banking

**Ne yapıyor iyi:**
- 2.200+ farklı şekilde "balance" sorusu anlıyor (NLU derinliği).
- Voice + text karışık.
- Proaktif uyarılar ("Bu ay kahveye ortalamadan %40 fazla harcadın").

**Senin için ders:** FinancialOS'in Coach paneli zaten benzer felsefede. Mobile'a geçince **voice input** (`expo-speech` veya iOS native dictation) ekle — kahve sırasında "200 TL kahve" demek, yazmaktan 5x hızlı.

---

## 3. Chat-Merkezli Mobil UX Patternleri

Senin Coach paneli ürünün kalbi. Mobile'da chat UX'i web'den **temelden farklı**:

### Pattern 1 — Bottom-fixed input + safe area

Web'de input genelde ortada/üstte olabilir, mobile'da **alttaki input bar** sabit. Ama iPhone'da home indicator + Android'de gesture bar var — `safe-area-inset-bottom` ile padding eklemen şart, yoksa input ekrana yapışıp tıklanmaz olur.

**Çıkarım:** Mevcut Coach.jsx'te `h-[calc(100vh-180px)]` sabit hesabı mobile'da kırılır. Native'de `KeyboardAvoidingView` + `SafeAreaView` kullanılır.

### Pattern 2 — Quick reply chips (önemli)

Linear, Klarna, Bank of America Erica — hepsi **suggested replies** kullanıyor. Coach son mesajdan sonra 2-3 chip öneriyor: "Bu ay bütçem nasıl?", "TLY satayım mı?", "Kart limitim ne durumda?".

**Senin için somut iş:** `is_question()` zaten var. Buna ek olarak `suggest_followups()` üreten bir helper ekle — son cevaba göre 2-3 chip dönsün. Mobile'da yazmaktan 10x hızlı, web'de de işe yarar.

### Pattern 3 — Voice input

Mobile'da klavyede uzun mesaj yazmak işkencedir. iOS'ta dictation, Android'de Google keyboard mic — bunlar zaten var. Sadece input alanına **mic ikonu** koyarak farkındalık yarat. Native'de `expo-speech-recognition` ile özelleştirebilirsin.

### Pattern 4 — Pending action card → swipe gestures

Web'de "Onayla / Reddet / Düzenle" butonları var. Mobile'da bunları **swipe gesture**'larla zenginleştir:
- Sağa kaydır = Onayla (yeşil)
- Sola kaydır = Reddet (kırmızı)
- Tap = Detay aç (bottom sheet)

YNAB ve Apple Mail bu pattern'i kullanıyor, çok ergonomik.

### Pattern 5 — Bottom sheet ≠ Modal

Web'de "modal" doğru pattern. Mobile'da modal kötü — ekranı kapatır. **Bottom sheet** (yarı şeffaf alt panel, drag ile kapatılan) standart. iOS'ta native `UISheetPresentationController`, Android'de Material `BottomSheet`. Expo'da `@gorhom/bottom-sheet` paketi.

**Senin için somut iş:** Pending action detayı, recurring expense ekleme, kategori seçimi — hepsi bottom sheet olmalı, modal değil.

### Pattern 6 — Pull-to-refresh

Mobile'da liste ekranlarında (Cockpit, Transactions) standart. RN'de `RefreshControl` component'i ile bir satır kod. Web'de yapması zor, mobile'da bedavaya gelir.

---

## 4. Offline-First Mimari — Mobile İçin Vazgeçilmez

Mobile'da internet bağlantısı **garanti edilemez**. Metro, asansör, kötü kapsama, uçak modu. Web'de F5 atılır, mobile'da kullanıcı uygulamayı siler.

### Temel Prensip: Local-first

Cihaz kendi kendine yeterli olmalı. Backend = senkronizasyon hedefi, **birincil veri kaynağı değil**. Pattern:

```
[Cihaz UI] → [Yerel SQLite (Expo SQLite)] → [Sync Queue] → [FastAPI Backend]
```

1. Kullanıcı işlem girer → **anında** yerel DB'ye yazılır (optimistic write).
2. UI yerel DB'yi okur, güncel görünür.
3. Arka planda sync queue backend'e gönderir.
4. Çatışma varsa backend "ground truth" — yerel düzeltilir.

### Senin Backend'in Bu İçin Hazır mı?

**Şu an:** FastAPI + SQLite, tek kullanıcılı, local-only. Mobile'a senkronlanmak için 3 şey lazım:

1. **Sürüm kolonu** her tabloda (`version INT` veya `updated_at TIMESTAMP`). Conflict detection için.
2. **Sync endpoint**: `POST /api/sync` — cihazdan gelen pending changes + son sync timestamp. Dönüş: "senin gönderiklerini aldım, ben de şu değişiklikleri yaptım".
3. **Soft delete**: `DELETE FROM transactions` yerine `is_deleted=True` set et. Sync sırasında çakışma olmasın.

### Sync Stratejileri

**Last-write-wins** (en basit): Updated_at karşılaştır, son yazı kazanır. Senin için yeterli — çünkü tek kullanıcısın, gerçek conflict nadir.

**CRDT** (gelişmiş): Otomatik merge, kayıp yok. Yjs veya Automerge kütüphaneleri. Multi-user senaryoları için gerekir, sen ihtiyaç duymuyorsun.

**Operational Transform**: Google Docs'un kullandığı. Aşırı karmaşık, senin için overkill.

### Önerilen Stack (mobile için)

| Katman | Seçim | Neden |
|---|---|---|
| Yerel DB | **expo-sqlite** + **Drizzle ORM** | SQLite zaten backend'inle uyumlu. Drizzle TypeScript-native, schema migration kolay. |
| State | **Zustand** veya **TanStack Query** | Redux fazla. Zustand minimal, TanStack Query server state için optimize. |
| Sync | **Kendi kuyruğun** (custom) veya **PowerSync** | Custom = tam kontrol. PowerSync = Postgres-tabanlı, hazır çözüm ama backend'ini Postgres'e taşırsın. |
| Şifreli depolama | **expo-secure-store** | API token, biometric key. Keychain (iOS) / Keystore (Android) sarmalayıcısı. |

---

## 5. Backend'in Mobile-Hazır Olması İçin Yol Haritası

Backend'i baştan yazmıyorsun. Sadece mobile-uyumlu hale getiriyorsun.

### Şart 1 — Authentication

Şu an FinancialOS auth'suz, single-user, localhost. Mobile'a açılmak demek **internet'e açılmak** demek.

**Önerilen:**
- **JWT token-based auth**. FastAPI'de `fastapi-users` veya manuel JWT.
- **Refresh token** rotation: Access token kısa ömürlü (15dk), refresh uzun (30 gün), her kullanımda yenilenir.
- **Biyometrik auth**: Cihazda Touch ID / Face ID ile token'ı unlock et. `expo-local-authentication`.

### Şart 2 — HTTPS + CORS

Mobile'dan localhost:8000'e bağlanamazsın (telefon başka network'te). Şu yollar var:

1. **Cloudflare Tunnel** (geliştirme): `cloudflared tunnel --url http://localhost:8000` → her oturumda farklı URL.
2. **Tailscale** (hibrit): Telefonun + bilgisayarın aynı VPN'de, statik hostname.
3. **VPS deploy** (production): Hetzner/DigitalOcean'da $5/ay sunucu, kalıcı domain.

Production için **3. seçenek**. Geliştirmede Tailscale en pratik.

### Şart 3 — API tasarımı revizyonu

Şu anki API'lerin tek kullanıcılı varsayımıyla yazıldı. Mobile'da:

- Her endpoint **user_id ile filtrelemeli** (multi-user'a hazır).
- Listeleme endpoint'leri **paginated** olmalı (mobile'da 1000 transaction tek seferde gelmesin).
- **Sürüm kolonları** dönülmeli (sync için).
- **Bulk endpoint'ler**: `POST /api/sync` — birden fazla değişikliği tek istekte gönder.

### Şart 4 — Push Notification

"Vade yaklaştı", "Limit aşıldı", "Beklenen gelir geldi" gibi uyarılar mobile'da push olarak gelmeli. Mimari:

```
[FastAPI] → [APNs (iOS) + FCM (Android)] → [Cihaz]
```

`pyfcm` (FCM) ve `aioapns` (APNs) Python kütüphaneleri var. Cihaz token'ları DB'de tut, vade yaklaşan recurring kayıtlarda `apscheduler` ile günlük cron at, push gönder.

---

## 6. Mevcut Frontend'i Mobile-Hazır Yapma (Aşama 1: PWA)

Wave-3'e gitmeden mevcut webde **mobil uyumluluk** yapmak için yol haritası:

### Adım 1 — Responsive audit (D1, ertelendiydi)

Memory'den çekilen asistan araci teşhis raporu hazır:

- **Coach.jsx (45dk)**: `h-[calc(100vh-180px)]` sabit yerine `h-screen` + flex layout. Input bar `position: sticky bottom-0`. Mesaj scroll alanı `overflow-y-auto flex-1`.
- **Accounts.jsx (30dk)**: Form modallarında `grid-cols-3` → `grid-cols-1 sm:grid-cols-3` (mobile'da tek sütun, sm+ ekranda 3).
- **Transactions.jsx (15dk)**: Üç özet kartta `p-2 sm:p-4` (mobile'da daha kompakt).
- **Cockpit (15dk)**: Investment P&L `grid-cols-2 sm:grid-cols-4`.

Toplam ~1.5 saat. Bu D1 işi mobile'a köprü olarak şimdi yapılabilir.

### Adım 2 — PWA setup (1-2 saat)

Vite için **vite-plugin-pwa** plugin'i:

```bash
npm install -D vite-plugin-pwa
```

`vite.config.js`:
```js
import { VitePWA } from 'vite-plugin-pwa'

export default {
  plugins: [
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'FinancialOS',
        short_name: 'FinOS',
        theme_color: '#0f172a',
        icons: [/* 192x192, 512x512 */]
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png}']
      }
    })
  ]
}
```

Sonra `manifest.json` ve service worker otomatik üretilir. Telefonda Safari/Chrome → "Ana ekrana ekle" → uygulama gibi açılır.

### Adım 3 — Offline cache (basit versiyon)

Service worker'ın varsayılan davranışı: statik dosyaları cache'ler, API isteklerini network'e gönderir. **Network-first, cache fallback** stratejisi:

```js
workbox: {
  runtimeCaching: [{
    urlPattern: /^https:\/\/api\..*\/cockpit$/,
    handler: 'NetworkFirst',
    options: {
      cacheName: 'cockpit-cache',
      networkTimeoutSeconds: 3,
      expiration: { maxAgeSeconds: 300 }
    }
  }]
}
```

Internet kopuksa son cockpit verisi gösterilir.

### Adım 4 — Touch-friendly etkileşimler

- Buton minimum 44x44 px (Apple HIG, Android Material).
- Hover state'lerini `active:` state'lerine ek olarak yaz (`hover:bg-blue-700` → `hover:bg-blue-700 active:bg-blue-800`).
- Long-press menü için `onTouchStart` + setTimeout pattern'i.

### Adım 5 — Bottom navigation

Web'de tab bar üstte. Mobile'da **alt** olmalı (başparmak erişimi). Conditional render:

```jsx
{isMobile ? <BottomNav /> : <TopTabs />}
```

iOS Safari + Android Chrome'da test et.

---

## 7. Aşama 2: React Native + Expo'ya Geçiş Yol Haritası

PWA'dan sonra (3-6 ay), native'e geçiş.

### Hafta 1-2 — Setup ve mimari

```bash
npx create-expo-app financialos-mobile --template
cd financialos-mobile
npx expo install expo-sqlite expo-secure-store expo-notifications
npm install drizzle-orm zustand @tanstack/react-query
npm install nativewind
```

**Klasör yapısı (Clean Architecture):**

```
src/
  data/           # Veri katmanı
    local/        # SQLite, Drizzle schema
    remote/       # FastAPI client
    sync/         # Sync queue
  domain/         # İş mantığı
    entities/     # Account, Transaction, etc.
    usecases/     # AddTransaction, ApprovePending, etc.
  presentation/   # UI
    screens/      # Cockpit, Coach, Accounts...
    components/
    hooks/
  core/
    di/           # Dependency injection
    config/
```

### Hafta 3-4 — Veri katmanı

1. Drizzle ile schema (backend'inle aynı tablolar).
2. SQLite migration sistemı (`drizzle-kit`).
3. Zustand store (UI state için).
4. TanStack Query (server state için).
5. Sync queue: değişiklikleri `sync_pending` tablosuna yaz, online olunca FastAPI'ye gönder.

### Hafta 5-7 — Ana ekranlar

Her panel için ayrı screen:
- `CockpitScreen` — özet metrikler, swipe-able cards.
- `CoachScreen` — chat UI, bottom-fixed input, swipe pending actions.
- `AccountsScreen` — liste, FAB ile ekleme.
- `TransactionsScreen` — liste + filtre bottom sheet.
- `IncomeDebtScreen` — segmented control, recurring CRUD.
- `RedLinesScreen` — drag-to-reorder list.

### Hafta 8 — Native özellikler

- **Biyometrik unlock**: `expo-local-authentication`.
- **Push**: `expo-notifications` + backend'de FCM/APNs.
- **Widget** (iOS): WidgetKit, Swift gerekir — geç eklenir.
- **Haptic**: Onay verirken `expo-haptics` titreşim.
- **Voice**: `expo-speech` veya `@react-native-voice/voice`.

### Hafta 9-10 — Test, polish, deploy

- **EAS Build** ile iOS + Android binary'leri.
- TestFlight (iOS) ve internal track (Android) ile beta test.
- App Store Connect ve Google Play Console submission.

**Tahmini süre:** 8-10 hafta full-time. Senin pace'inde (haftada 10-15 saat) **4-6 ay**.

---

## 8. Mobile-Specific Özellikler — Wave-3 Vizyonu

Bunlar mobile native olunca dramatik fark yaratır:

### Voice-first transaction entry
"Hey FinOS, 200 TL market" → Coach NLU → propose_action. Fiziksel klavye yerine 2 saniyelik konuşma.

### Lock screen widget
Apple Watch / iOS lock screen widget: "Bu ay daily limit: 268 TL". Telefonu açmadan kontrol.

### NFC / barkod entegrasyonu
Market fişi barkodu okutarak otomatik kayıt. `expo-barcode-scanner`.

### Camera receipt OCR
Fişin fotoğrafı → backend'de Tesseract/Google Vision → otomatik amount + merchant extraction.

### Geo-fencing
Belirli lokasyonlara girince hatırlatma: "Migros'a girdin, market kategorisinde bu ay 1500 TL'yi aştın".

### Apple Shortcuts / Android Quick Settings
"Hey Siri, son 7 gün kahve harcamam" → uygulama açılmadan ses cevabı.

### Watch app
Apple Watch / Wear OS: anlık balance, son 5 transaction, complication.

---

## 9. Karar Matrisi — Senin İçin Hangi Yol?

Mevcut durumun göz önüne alınınca:

| Kriter | PWA | RN+Expo | Flutter |
|---|---|---|---|
| Geliştirme hızı (hemen başlayacaksak) | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| Mevcut React tecrübeni kullanma | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ |
| Native his / performans | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| App Store dağıtımı | ❌ | ✅ | ✅ |
| Offline-first kolaylığı | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Push notification | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| Biyometrik auth | ❌ | ✅ | ✅ |
| Widget desteği | ❌ | ✅ (kısmi) | ✅ (kısmi) |
| Backend değişikliği | Yok | Auth + sync ekleme | Auth + sync ekleme |
| Toplam efor (sıfırdan) | 1-2 hafta | 4-6 ay | 6-8 ay |

### Net Tavsiye

**Şu an (Wave-2 Hafta 1):** D1 (mobile responsive audit, 1.5 saat) yap. Telefondan Cloudflare Tunnel ile aç, gerçek kullanım başlasın.

**Wave-2 Hafta 4 - Wave-3 başı (Mayıs sonu - Haziran):** PWA setup. 2-3 günlük iş. Telefonda "ana ekrana ekle" → app gibi açılır. Push henüz yok ama mobil-first UX patternlerini test edersin.

**Wave-3 (Haziran - Eylül):** React Native + Expo'ya geçiş. Backend'i auth + sync için modernize et. 4-6 ay full-time iş, senin pace'inde 6 ay.

**Wave-4+:** Native özellikler (voice, widget, OCR), App Store yayını, Open Banking entegrasyonu (Türkiye'de olgunlaştığında).

---

## 10. Kaynak ve Referanslar

**Mimari kaynaklar:**
- [Expo Local-First Guide](https://docs.expo.dev/guides/local-first/) — RN için offline-first stack seçenekleri
- [Fintech Mobile Clean Architecture (Türkçe-uyumlu)](https://medium.com/@seyhunak/fintech-mobile-architecture-clean-architecture-react-native-expo-supabase-backend-with-zustand-5857fb7a531f) — KVKK + offline-first + Expo
- [Modern SQLite for React Native (Expo blog)](https://expo.dev/blog/modern-sqlite-for-react-native-apps) — Drizzle + expo-sqlite

**UX referansları:**
- Linear — klavye-merkezli desktop, command palette pattern (Cmd+K)
- YNAB — finans-spesifik gesture'lar
- Copilot Money — iOS native UX gold standard
- Bank of America Erica — voice-first finans AI
- Monarch Money — cross-device sync, web ↔ mobile uyum

**Sync ve veri:**
- [PowerSync](https://www.powersync.com/) — Postgres tabanlı, hazır local-first sync
- [WatermelonDB](https://watermelondb.dev/) — RN için lazy-loaded reactive DB
- [Drizzle ORM](https://orm.drizzle.team/) — TypeScript-native ORM, SQLite + Postgres
- [TanStack Query](https://tanstack.com/query) — server state management, optimistic updates

---

## Sonraki Adım

Bu raporu okuduktan sonra **tek karar** vermen lazım:

**A)** "PWA önce, RN sonra" stratejisini benimsiyorum → D1 + PWA setup'a Wave-2 Hafta 1'de başlayalım.

**B)** "Mevcut webe odaklan, mobile geç başlasın" → Wave-2 Hafta 2-3-4 (Tema A bitti, D2-D8 var, Tema B var) tamamen bitsin, sonra mobile düşünelim.

**C)** "Doğrudan RN'e atlayalım, web'i bırakalım" → Çok riskli, mevcut çalışan sistem var. Önermem.
