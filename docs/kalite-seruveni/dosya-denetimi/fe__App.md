# Denetim: frontend/src/App.jsx

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [FAPP-001] usagePct hicbir zaman guncellenmiyor - her zaman 0% gosteriyor
Sorun: `useBackendHealth` icinde `usagePct` state'i `useState(0)` ile baslatiliyor ama `setUsagePct` fonksiyonu dosyanin hicbir yerinde cagrilmiyor. `healthApi.check()` (`api.js:344-346`) da sadece `/api/health` GET edip donen deger kullanilmiyor - deger atanmiyor.
Kanit (satir 56, 62-69, 80, 145-151): `const [usagePct, setUsagePct] = useState(0);` tanimlaniyor, `check()` icinde sadece `status` set ediliyor, `return { status, usagePct }` ile hep 0 donuyor, header'da `usagePct > 80` / `> 50` kosullu renklendirme (chip-negative/chip-warn) hicbir zaman tetiklenmiyor, kullaniciya surekli "0%" gosteriliyor.
Aksiyon: Ya backend `/api/health` yanitina gercek bir kullanim/limit yuzdesi ekleyip `setUsagePct(data.usage_pct)` ile baglanmali, ya da bu olculen bir metrik degilse chip tamamen kaldirilmali (yanlis/yanıltici bilgi kullanicidan iyi).
Onem: Orta · Guven: Kesin

### [FAPP-002] Klavye kisayollari TAB_IDS listesi 3 yeni tab'i icermiyor
Sorun: `App.jsx`'teki `TABS` dizisi 10 sekme icerir (satir 22-33), ama `useKeyboardShortcuts.js:3`'teki `TAB_IDS` sadece 7 sekme listeler (`cockpit, coach, accounts, transactions, incomedebt, redlines, reports`). `cashflow`, `debtstrategy`, `goals` (App.jsx satir 30-32) kisayol listesine hic eklenmemis; Ctrl+8/9/0 calismaz, Ctrl+7 zaten "reports"a gidiyor ama daha yeni eklenen 3 sekmeye klavye ile erisim yok.
Kanit (App.jsx satir 22-33 vs useKeyboardShortcuts.js satir 3, 32): `e.key >= '1' && e.key <= '7'` sinirlamasi + 7 elemanli TAB_IDS.
Aksiyon: TAB_IDS'i TABS ile senkron tut (ideal: TABS'tan turetilmis tek kaynak, App.jsx'te tanimlanip hook'a proplanabilir) veya kisayol araligini 1..9,0 olacak sekilde genislet.
Onem: Dusuk · Guven: Kesin

### [FAPP-003] onHelp/onPalette her render'da yeniden yaratiliyor - keydown listener'i her 5 saniyede bir sokup takiyor
Sorun: `AppContent` icinde `onHelp: () => setShowHelp(h => !h)` ve `onPalette: () => setShowPalette(p => !p)` (satir 105-109) her render'da yeni fonksiyon referansi olarak olusturuluyor ve memoize edilmiyor (useCallback yok). `useKeyboardShortcuts` bu iki fonksiyonu useEffect bagimlilik dizisine koyuyor (`useKeyboardShortcuts.js:51`), bu yuzden `AppContent` her yeniden render oldugunda (ornegin `useBackendHealth`'in 5 saniyede bir `setStatus`/interval tetiklemesiyle, ya da `activeTab` degisiminde) global `keydown` listener'i remove+add ediliyor.
Kanit (satir 105-109; useKeyboardShortcuts.js satir 49-51): `window.addEventListener` / `removeEventListener` cift'i her render'da calisiyor; fonksiyonel olarak bug yaratmiyor ama gereksiz churn.
Aksiyon: `onHelp`/`onPalette` fonksiyonlarini `useCallback` ile sarmalamak, boylece referans stabil kalsin ve effect sadece gercekten gerektiginde yeniden kursun.
Onem: Dusuk · Guven: Kesin

### [FAPP-004] Sekme (tab) butonlari erisilebilirlik rolu/aria durumu tasimiyor
Sorun: Nav altindaki sekme butonlari (satir 166-179) semantik olarak bir "tablist/tab" paterni ama `role="tablist"`, `role="tab"`, `aria-selected` gibi ARIA ozellikleri yok. Ekran okuyucu kullanicilari hangi sekmenin aktif oldugunu, kac sekme oldugunu anlayamaz - sadece renk/border-b-2 ile aktiflik gosteriliyor (satir 170-174).
Kanit (satir 166-179): `<button onClick={...} className={...}>` - `aria-selected`, `role` yok; aktiflik sadece CSS class farki (`text-brand-600` / border rengi) ile isaretleniyor, bu da kontrast disinda hicbir programatik sinyal vermiyor.
Aksiyon: Nav container'a `role="tablist"`, her butona `role="tab"` + `aria-selected={activeTab === id}` + `tabIndex` yonetimi eklenmeli.
Onem: Orta · Guven: Kesin

### [FAPP-005] Tema toggle butonu sadece title ile etiketleniyor, aria-label yok
Sorun: Ikon-only tema degistirme butonu (satir 153-159) `title` attribute'una sahip ama `aria-label` yok. Bircok ekran okuyucu `title`'i tutarli sekilde duyurmaz; icon-only butonlar icin `aria-label` standart pratiktir.
Kanit (satir 153-159): `<button onClick={toggleTheme} className="btn btn-ghost btn-icon !p-2" title={...}>`.
Aksiyon: `aria-label={theme === 'dark' ? 'Açık temaya geç' : 'Koyu temaya geç'}` eklenmeli.
Onem: Dusuk · Guven: Kesin

### [FAPP-006] formatTodayTR() sadece mount aninda hesaplaniyor, gun degisiminde guncellenmiyor
Sorun: `formatTodayTR()` (satir 83-88) her `AppContent` render'inda cagriliyor (state'e baglanmadigi icin re-render olmadan degismiyor), ama sayfa gece yarisini gecip acik kalirsa ve baska hicbir state degisikligi tetiklenmezse (health check statusu ayni kalirsa bile aslinda her 5 saniyede interval yuzunden render oluyor - status ayni "online" kalsa da setStatus('online') cagrisi yine de re-render'a sebep olabilir, React ayni deger icin de re-render yapar) tarih genelde guncel kalir; ancak bu bir garanti degil, `useEffect`/interval'a bagli degil, tasarim olarak kirilgan.
Kanit (satir 83-88, 121): `<p ...>{formatTodayTR()}</p>` - render-time cagri, ayri bir zamanlayici yok.
Aksiyon: Kritik degil (health-check interval'i dolayli olarak periyodik render tetikliyor); yine de acikca bir `setInterval` ile gun degisimini yakalamak daha saglam olur. Su anki davranis buyuk ihtimalle dogru calisiyor ama kirilgan.
Onem: Dusuk · Guven: Dogrulanmali

### [FAPP-007] Backend offline oldugunda health-check interval'i sikilmiyor, gereksiz agir yeniden deneme yok ama race/overlap kontrolu yok
Sorun: `check()` fonksiyonu (satir 62-69) her 5 saniyede bir cagriliyor (satir 72) ama bir onceki `check()` cagrisi henuz donmemisse (ornegin backend yavas/timeout uzun surerse) yeni istek yine de baslatiliyor - eszamanli/overlap istek engelleme (in-flight guard) yok.
Kanit (satir 58-78): `interval = setInterval(check, 5000);` - `check` icinde in-flight kontrolu yok.
Aksiyon: Onemsiz risk (health endpoint hafif), ama `isFetching` ref'i ile overlap onlenebilir. Dusuk oncelik.
Onem: Dusuk · Guven: Dogrulanmali
