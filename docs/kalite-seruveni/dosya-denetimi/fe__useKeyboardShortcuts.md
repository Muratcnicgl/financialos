# Denetim: frontend/src/hooks/useKeyboardShortcuts.js

> **M86 güncellik:** 🟡 KISMEN-BAYAT — FKB-001/002/005/006 açık; FKB-003/004 bayat


> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [FKB-001] useEffect her render'da listener'i sokup takiyor (App.jsx entegrasyonunda dogrulandi)
Sorun: `useEffect` bagimlilik dizisi `[setActiveTab, onHelp, onPalette]` (satir 51). `App.jsx`'te hook su sekilde cagriliyor:
```
useKeyboardShortcuts({
  setActiveTab,
  onHelp: () => setShowHelp(h => !h),
  onPalette: () => setShowPalette(p => !p),
});
```
(App.jsx satir 105-109) — `onHelp` ve `onPalette` her `AppContent` render'inda yeni bir fonksiyon referansi olarak olusturuluyor, `useCallback` ile sarmalanmamis. Sonuc: `AppContent` her render oldugunda (tema degisimi, `useBackendHealth` polling'i, herhangi bir state guncellemesi) bu hook'un `useEffect`'i temizlenip yeniden calisiyor -> `window.removeEventListener` + `window.addEventListener` cifti her seferinde tetikleniyor.
Kanit: satir 51 (bagimlilik dizisi) + App.jsx satir 105-109 (memoize edilmemis inline fonksiyonlar).
Aksiyon: `App.jsx` tarafinda `onHelp`/`onPalette` icin `useCallback` kullanilmali, ya da bu hook `useRef` ile en guncel callback'leri tutup `useEffect`'i `[]` bagimliligiyla bir kez kurmali (ref pattern).
Onem: Orta · Guven: Kesin

### [FKB-002] isInputFocused contentEditable elemanlari kapsamiyor
Sorun: `isInputFocused()` sadece `tagName` degerini `INPUT`/`TEXTAREA`/`SELECT` ile karsilastiriyor (satir 5-8). Eger odakta `contenteditable="true"` olan bir eleman varsa (zengin metin alani, gelecekte eklenebilecek bir editor vb.) bu fonksiyon `false` doner ve kullanici o alanda yazi yazarken `?` karakteri girmeye calistiginda satir 43-46'daki yardim modali acilir.
Kanit: satir 5-8, kullanim satir 40.
Aksiyon: `document.activeElement?.isContentEditable` kontrolu de eklenmeli: `tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || document.activeElement?.isContentEditable`.
Onem: Dusuk · Guven: Dogrulanmali (su an DOM'da contenteditable eleman var mi dogrulanmadi, kod savunmasiz oldugu icin bulgu olarak isaretlendi)

### [FKB-003] Docstring ile kod arasinda tutarsizlik (1..6 vs 1..7)
Sorun: Fonksiyon ustu docstring "Cmd/Ctrl+1..6 → panel değiştir" diyor (satir 15), ancak kod `e.key >= '1' && e.key <= '7'` ile 7 tuşu da kabul ediyor (satir 32) ve `TAB_IDS` dizisi 7 eleman iceriyor (satir 3: cockpit..reports). Muhtemelen "reports" sekmesi sonradan eklendi ama docstring guncellenmedi.
Kanit: satir 3 (7 eleman), satir 15 (docstring "1..6"), satir 32 (`<= '7'`).
Aksiyon: Docstring "Cmd/Ctrl+1..7" olarak duzeltilmeli.
Onem: Dusuk · Guven: Kesin

### [FKB-004] Kirilgan string araligi karsilastirmasi ile rakam kontrolu
Sorun: `e.key >= '1' && e.key <= '7'` (satir 32) rakam kontrolunu string'lerin lexicographic karsilastirmasina dayandiriyor. Bu ozel durumda (named key'ler buyuk harfle basladigi icin, ör. "ArrowUp", "F1") pratikte guvenli sonuc veriyor, ama niyeti acik ifade etmiyor ve gelecekte yeni bir key degeriyle (ör. tek karakterli ozel bir tus) sessizce yanlis eslesme riski tasiyan kirilgan bir pattern.
Kanit: satir 32.
Aksiyon: Acik ve okunabilir bir kontrole gecilmeli, ör. `/^[1-7]$/.test(e.key)` ya da `TAB_IDS.includes` tabanli bir index haritasi.
Onem: Dusuk · Guven: Kesin

### [FKB-005] e.repeat kontrolu yok — tus basili tutulunca palet/yardim modali tekrar tekrar tetiklenir
Sorun: Klavye tusu basili tutuldugunda tarayici tekrarli `keydown` olaylari uretir (`e.repeat === true`). `onPalette()` (satir 27) ve `onHelp()` (satir 45) cagrilari toggle mantigiyla calistigi icin (`setShowPalette(p => !p)`), tus basili tutulursa modal/palet acilip kapanmayi hizla tekrarlar (flicker/UX gurultusu).
Kanit: satir 25-29 (`onPalette`), satir 43-46 (`onHelp`); toggle implementasyonu App.jsx satir 107-108.
Aksiyon: `if (e.repeat) return;` kontrolu handler basina eklenmeli.
Onem: Dusuk · Guven: Kesin

### [FKB-006] TAB_IDS, App.jsx'teki sekme tanimindan bagimsiz "magic" dizi
Sorun: `TAB_IDS` (satir 3) App.jsx'teki `TABS` dizisiyle (id/label/icon) ayni sirayi manuel olarak tekrar ediyor. Tek kaynak yok; biri diger'inden bagimsiz degisirse (ör. App.jsx'te sekme sirasi degisir/yeni sekme eklenir ama bu dosya guncellenmezse) Cmd+N kisayollari sessizce yanlis sekmeye atlar, derleme zamaninda hicbir uyari cikmaz.
Kanit: satir 3 (bu dosya) vs App.jsx satir 23-29 (TABS tanimi) — su an manuel olarak senkron ama baglayici bir referans yok.
Aksiyon: `TAB_IDS` App.jsx'teki `TABS` dizisinden turetilip export edilmeli (tek kaynak), ya da en azindan bir yorumla "TABS ile senkron tutulmali" uyarisi eklenmeli.
Onem: Orta · Guven: Kesin
