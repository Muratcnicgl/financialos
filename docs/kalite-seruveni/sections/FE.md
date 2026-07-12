# Frontend mimari & kod kalitesi (kod: FE)

### [FE-001] api.js tek dosyada 13 API grubu + formatter'lar iç içe
- **Kanıt:** `frontend/src/api.js:348-403` (formatter), `:95-336` (13 grup)
- **Aksiyon:** `shared/api/` (konuya göre böl) + `shared/api/client.js`; formatter'lar `shared/lib/format.js`. "Tüm çağrı api'den geçer" kuralı korunur. (FSD)
- **Etki:** Orta · **Efor:** M

### [FE-002] Dinamik Tailwind sınıfları prod build'de purge oluyor (renkler kaybolur) — GERÇEK BUG
- **Sorun:** `text-${color}-600`, `bg-${meta.color}-100` gibi interpolasyonlu sınıflar JIT'te literal aranır, üretilmez; `safelist` yok. positive/negative/warn/brand tonları basılmayabilir.
- **Kanıt:** `Accounts.jsx:141`; `RedLines.jsx:196,200,307,315,318`; `tailwind.config.js` (safelist yok)
- **Aksiyon:** Tam-literal sınıf map'i veya `safelist:[{pattern:/(text|bg|ring|border)-(positive|negative|warn|brand)-(100|400|500|600|950)/,variants:['dark']}]`.
- **Etki:** Yüksek · **Efor:** S

### [FE-003] Global ErrorBoundary yok — tek panel çökerse beyaz ekran ✅ UYGULANDI (12 Tem 2026)
- **Kanıt:** `main.jsx:6-9`; sadece `Coach.jsx:65-115` boundary
- **Aksiyon:** Ortak `components/ErrorBoundary.jsx`; `main.jsx`'te App'i sar + panel-seviyesi izolasyon.
- **Etki:** Yüksek · **Efor:** S

### [FE-004] Modal wrapper 7 kez tekrar, hiçbiri erişilebilir değil
- **Sorun:** role="dialog", aria-modal, focus-trap, Escape, scroll-lock yok.
- **Kanıt:** `Transactions.jsx:711-730`, `IncomeDebt.jsx:1025-1044`, `Accounts.jsx:628-647`, `RedLines.jsx:535-554`, `Cockpit.jsx:629-634`, `Goals.jsx:223-231`
- **Aksiyon:** Tek `components/Modal.jsx` (dialog+Escape+focus trap+scroll kilidi); tüm paneller geçsin.
- **Etki:** Yüksek · **Efor:** M

### [FE-005] Row toggle/mark-paid handler'larında try/catch yok — sessiz rejection ✅ UYGULANDI (12 Tem 2026, IncomeDebt)
- **Kanıt:** `IncomeDebt.jsx:123-126,135-138,147-153`; `RedLines.jsx:121-124`
- **Aksiyon:** try/catch+toast (IncomeDebt useToast ekle) veya TanStack mutation.
- **Etki:** Orta · **Efor:** S

### [FE-006] Coach `onActionResolved` App'te bağlanmamış — dead prop
- **Kanıt:** `App.jsx:201` (`<Coach />` propsuz); `Coach.jsx:499-505,349-355`
- **Aksiyon:** Panel-arası tazeleme sinyali kur, `onActionResolved={triggerCockpitRefresh}` bağla; veya query invalidation.
- **Etki:** Orta · **Efor:** S

### [FE-007] Komut paleti + kısayollar 10 sekmenin yalnız 7'sini biliyor ✅ UYGULANDI (12 Tem 2026)
- **Kanıt:** `useKeyboardShortcuts.js:3,32`; `CommandPalette.jsx:4-12`; `App.jsx:22-33` (10 tab); `e.key <= '7'`
- **Aksiyon:** `TABS`'ı `shared/config/tabs.js`'e; TabBar+CommandPalette+shortcut aynı diziden.
- **Etki:** Orta · **Efor:** S

### [FE-008] Goals paneli tema-duyarlı değil — açık temada okunmaz
- **Kanıt:** `Goals.jsx:13-19,44,55,141,153,229`; `DebtStrategy.jsx:21,117,127`
- **Aksiyon:** `zinc-100/900`→`text-zinc-900 dark:text-zinc-100`+`card`; emerald/rose→positive/negative token.
- **Etki:** Yüksek · **Efor:** M

### [FE-009] Kod-splitting yok — 10 panel + recharts tek bundle
- **Kanıt:** `App.jsx:11-20` (statik import); `Reports.jsx:7-10`+Cashflow (recharts); `vite.config.js:21-24`
- **Aksiyon:** Panelleri `lazy()`+`Suspense`; `manualChunks` ile recharts/lucide vendor chunk.
- **Etki:** Orta · **Efor:** M

### [FE-010] Liste render'larında array-index key (özellikle mesaj listesi)
- **Kanıt:** `Coach.jsx:450` (`key={i}`); `Cockpit.jsx:232,385,419,457`; `Reports.jsx:450,574`
- **Aksiyon:** Kararlı id (mesajda ts+role; reminder'da `${type}-${name}-${tarih}`). Statik skeleton map'leri sorun değil.
- **Etki:** Orta · **Efor:** S

### [FE-011] Cockpit `load()` her açılışta POST trigger-due çalıştırıyor (GET-görünümlü mutasyon)
- **Kanıt:** `Cockpit.jsx:42-47,63-66`
- **Aksiyon:** trigger-due'yu görünümden ayır; flowSummary promise'ini cancel bayrağına bağla.
- **Etki:** Orta · **Efor:** M

### [FE-012] `useBackendHealth` sonsuz 5sn polling + `usagePct` ölü state (hep %0)
- **Kanıt:** `App.jsx:54-81,145-151`
- **Aksiyon:** Ölü chip'i kaldır veya `coachApi.usage()`'a bağla; polling'i visibilitychange ile kıs/15-30sn.
- **Etki:** Düşük · **Efor:** S

### [FE-013] Panel-arası veri senkronu yok — Zustand adayı
- **Kanıt:** Ayrı yükleyiciler `Cockpit/Accounts/Transactions/IncomeDebt`
- **Aksiyon:** Server-state TanStack Query (FE-014); UI-state (tema/tab/son-mutasyon) Zustand. Zustand'a server verisi koyma.
- **Etki:** Orta · **Efor:** L

### [FE-014] Fetch/loading/error/refresh boilerplate her panelde tekrar (TanStack Query)
- **Kanıt:** `Accounts/Transactions/IncomeDebt/RedLines/Cockpit` aynı iskelet; refetch-all `IncomeDebt.jsx:116-165`
- **Aksiyon:** `useQuery`+`invalidateQueries`; FE-005/006/011/013/015/023/024'ü de çözer.
- **Etki:** Yüksek · **Efor:** L

### [FE-015] `refreshing` deseni tam yeniden yükleme — optimistik yok
- **Kanıt:** `Transactions.jsx:76,138-152`; `Accounts.jsx:49,51-65`
- **Aksiyon:** Mutasyon sonucunu local state'e yansıt; uzun vade Query `onMutate`.
- **Etki:** Orta · **Efor:** M

### [FE-016] Coach'ta tüm mesajlar her render'da yeniden markdown parse (memo yok)
- **Kanıt:** `Coach.jsx:448-454,544-548,15-26`
- **Aksiyon:** `Message`'ı `React.memo`; `preprocessMarkdown`'ı `useMemo`; satır bileşenlerini memo.
- **Etki:** Orta · **Efor:** S

### [FE-017] Tarih parse'ında UTC 'Z' kuralı tutarsız (dokümante buga aykırı)
- **Kanıt:** `api.js:386-393`; `Coach.jsx:125-135`; `Reports.jsx:524,536` (3 farklı ele alış)
- **Aksiyon:** `shared/lib/date.js` `parseServerDate`; tüm parse noktaları buna. GUNCELLEMELER notu ekle.
- **Etki:** Orta · **Efor:** S

### [FE-018] DebtStrategy slider yalnız mouse/touch-up'ta fetch — klavye erişilemez
- **Kanıt:** `DebtStrategy.jsx:164-174`
- **Aksiyon:** Debounce'lu `useEffect([extraMonthly])`; `aria-label`.
- **Etki:** Orta · **Efor:** S

### [FE-019] İkon-only buton dokunma alanları 44px altında (mobil)
- **Kanıt:** `IncomeDebt.jsx:467-475` (`!p-1`), `Transactions.jsx:482-487`, `Accounts.jsx:226-231`
- **Aksiyon:** `p-2`+`min-w/h-[40px]` veya `…` menü. (WCAG 2.5.5)
- **Etki:** Orta · **Efor:** S

### [FE-020] Magic string'ler paylaşılan sabitlere çıkarılmamış
- **Kanıt:** account_type `Transactions.jsx:158,517`, `Accounts.jsx:100-103`; direction `IncomeDebt.jsx:77,104,536,839`
- **Aksiyon:** `shared/config/enums.js` (ACCOUNT_TYPES, TXN_TYPES, DEBT_DIRECTIONS, TAB_IDS).
- **Etki:** Düşük · **Efor:** S

### [FE-021] TEFAS URL'i iki panelde elle inşa; `fundPriceApi.tefasLink` kullanılmıyor
- **Kanıt:** `Cockpit.jsx:627`, `Accounts.jsx:556`; `api.js:250`
- **Aksiyon:** Tek yardımcıya çıkar; `tefasLink`'i kullan veya sil.
- **Etki:** Düşük · **Efor:** S

### [FE-022] Yükleme durumu panelden panele tutarsız (spinner/skeleton/metin)
- **Kanıt:** `Accounts.jsx:71-77` vs `Cockpit.jsx:535-597` vs `Goals.jsx:42-48`
- **Aksiyon:** Skeleton'u standart yap veya tek `<PanelLoading variant>`.
- **Etki:** Düşük · **Efor:** M

### [FE-023] Hata & yükleme UI'ı 5+ panelde birebir kopya
- **Kanıt:** `Accounts.jsx:71-96`, `Transactions.jsx:173-198`, `IncomeDebt.jsx:171-196`, `RedLines.jsx:136-161`, `Cockpit.jsx:83-100`
- **Aksiyon:** `components/PanelState.jsx` (`loading error onRetry`).
- **Etki:** Orta · **Efor:** S

### [FE-024] fetch'te timeout/AbortController yok — asılı istekler iptal edilmiyor
- **Kanıt:** `api.js:33-89` (58-64)
- **Aksiyon:** `request`'e signal+AbortController+timeout; useEffect cleanup'ta abort.
- **Etki:** Orta · **Efor:** M

### [FE-025] Boş/ölü bileşen dosyaları repoda (0 bayt)
- **Kanıt:** `components/Header.jsx`, `Loading.jsx`, `QuickEntry.jsx`, `TabBar.jsx` (0 satır); gerçek QuickEntry `Transactions.jsx:365-427`
- **Aksiyon:** Sil veya FE-004/023 kapsamında doldur.
- **Etki:** Düşük · **Efor:** S

### [FE-026] Hesap alan adı tutarsızlığı: `.ad` vs `.name` (latent bug)
- **Kanıt:** `PendingActions.jsx:79,118` (`.ad`) vs `Transactions.jsx:294`/`Accounts.jsx:218` (`.name`)
- **Aksiyon:** `a.name ?? a.ad` veya kaynağı standardize; backend ad/name farkını netleştir.
- **Etki:** Orta · **Efor:** S

### [FE-027] Goals: kural kriteri kullanıcıya ham `JSON.stringify` ile gösteriliyor
- **Kanıt:** `Goals.jsx:358`; `288-373` (yalnız delete, create yok)
- **Aksiyon:** Okunabilir Türkçe formatter; allocation/rule ekleme formu tamamla veya "salt-görüntüleme" işaretle.
- **Etki:** Orta · **Efor:** M

### [FE-028] `useEffect` exhaustive-deps susturmaları, biri gerçek risk
- **Kanıt:** `Cashflow.jsx:48`; `DebtStrategy.jsx:106`; `PendingActions.jsx:50,209`
- **Aksiyon:** Cashflow'da `include`'ı `includeKey`'den türet, susturmayı kaldır; diğerlerinde gerçek bağımlılık.
- **Etki:** Düşük · **Efor:** S

### [FE-029] İkon butonlar `title` kullanıyor, `aria-label` yok
- **Kanıt:** `IncomeDebt.jsx:467,470,473`; `Accounts.jsx:226,229,640`; `App.jsx:153-159`
- **Aksiyon:** `aria-label` ekle; modal kapatmaya `aria-label="Kapat"`.
- **Etki:** Düşük · **Efor:** S

### [FE-030] Sayı parse (`replace(',','.')`+parseFloat) her modda tekrar, tutarsız
- **Kanıt:** `Cockpit.jsx:611`, `Accounts.jsx:355-359`, `IncomeDebt.jsx:641,750,851`, `Transactions.jsx:525`, `Cashflow.jsx:69`
- **Aksiyon:** `shared/lib/parseTL.js` (`parseTLNumber`); doğrulama mesajları ortak.
- **Etki:** Düşük · **Efor:** S

### [FE-031] Modal açıkken body scroll kilitlenmiyor + focus dönmüyor
- **Kanıt:** Tüm Modal wrapper'ları (örn. `Transactions.jsx:711-730`)
- **Aksiyon:** Ortak Modal'a overflow hidden + focus-restore effect (FE-004 ile).
- **Etki:** Düşük · **Efor:** S

### [FE-032] Prod build sourcemap açık — kaynak sızıntısı
- **Kanıt:** `vite.config.js:22-24`
- **Aksiyon:** Prod'da `sourcemap:false` veya `'hidden'`.
- **Etki:** Düşük · **Efor:** S

### [FE-033] `<button>` içine grid+metin sarılmış Goals kartı — anlamsal/erişilebilirlik kokusu
- **Kanıt:** `Goals.jsx:132-178`
- **Aksiyon:** `<article>`+tek "Detay" butonu veya `role="button" tabIndex=0`+onKeyDown; diğer panellerin desenine uydur.
- **Etki:** Düşük · **Efor:** S

### [FE-034] Coach mesaj listesi memoize/virtualize değil
- **Kanıt:** `Coach.jsx:446-457,160`
- **Aksiyon:** Önce FE-016 memo; gerçekten büyürse react-window. Erken optimize etme.
- **Etki:** Düşük · **Efor:** M

### [FE-035] SSR guard'ı ve gereksiz `React` importları — küçük ölü kod
- **Kanıt:** `App.jsx:37` (SSR guard, SPA'da ölü); `Goals.jsx:1` (kullanılmayan React)
- **Aksiyon:** SSR guard'ını kaldır; kullanılmayan importu sil.
- **Etki:** Düşük · **Efor:** S

---
**Öncelik:** FE-002 (gerçek görsel bug), FE-003, FE-004, FE-008, FE-014 (birçok maddeyi çözer).
**Kaynaklar:** FSD v2; Tailwind dynamic class names; React error boundary/keys/memo; TanStack Query v5; Zustand; Vite manualChunks; WAI-ARIA APG.
