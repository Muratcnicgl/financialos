# Denetim: frontend/src/components/CommandPalette.jsx

### [FCMD-001] Klavye olay yonetimi sadece input elemanina bagli, odak baska yere gectiginde kirilir
Sorun: `handleKeyDown` (satir 31-42) sadece input'un `onKeyDown`'ina baglanmis (satir 59). Escape, ArrowUp/ArrowDown ve Enter mantigi yalnizca input odaktayken calisir. Kullanici Tab ile kapatma butonuna (satir 63) veya bir komut satirina (satir 72) odaklanirsa, o noktada Escape ile kapatma ve ok tuslariyla gezinme calismaz.
Kanit (satir 31, 59, 63, 72): `handleKeyDown` tanimi input disina baglanmamis; `onKeyDown={handleKeyDown}` sadece satir 59'daki `<input>` uzerinde.
Aksiyon: Klavye dinleyicisini modal container'a (satir 45'teki disaridaki `div`) veya `document`e tasi, boylece odak input disindayken de Escape/ArrowUp/ArrowDown/Enter calissin. Document'e baglaniyorsa `useEffect` cleanup ile `removeEventListener` eklenmeli.
Onem: Yuksek · Guven: Kesin

### [FCMD-002] Odak tuzagi (focus trap) ve ARIA dialog/listbox semantigi yok
Sorun: Modal container (satir 45-91) `role="dialog"`, `aria-modal="true"` veya baslik icin `aria-label`/`aria-labelledby` icermiyor. Input (satir 55-62) icin `aria-label` yok, sadece placeholder var (WCAG 3.3.2 ihlali - placeholder tek basina etiket degildir). Sonuc listesi (satir 71-84) `role="listbox"` degil, her buton `role="option"`/`aria-selected` tasimiyor. Ayrica Tab tusuyla odak modal disina kacabilir (focus trap yok).
Kanit (satir 45, 55-62, 71-84): ilgili elemanlarda hicbir `role`/`aria-*` ozniteligi yok.
Aksiyon: Container'a `role="dialog"` + `aria-modal="true"` + `aria-label="Komut paleti"`; input'a `aria-label="Komut ara"` ve `aria-activedescendant`; sonuc container'ina `role="listbox"`, her butona `role="option"` + `aria-selected={i===selectedIdx}`; basit bir focus-trap (ilk/son odaklanabilir eleman arasinda Tab dongusu) eklenmeli.
Onem: Yuksek · Guven: Kesin

### [FCMD-003] Turkce buyuk/kucuk harf donusumu arama eslesmesini bozabilir (İ/I sorunu)
Sorun: Filtreleme `c.label.toLowerCase().includes(query.toLowerCase())` (satir 20) kullaniyor. JS'in varsayilan (locale-agnostic) `toLowerCase()`'i Turkce noktali buyuk `İ` (U+0130) karakterini `i` + birlesik nokta (U+0307) olarak iki kod noktasina cevirir, kullanicinin normal klavyeden yazdigi düz `i` (U+0069) ile birebir eslesmez. `COMMANDS` icindeki "İşlemler'e geç" (satir 8) gibi etiketlerde kullanici "islemler" yazdiginda arama sonuc bulamayabilir.
Kanit (satir 8, 20): `label: 'İşlemler\'e geç'` + `c.label.toLowerCase().includes(query.toLowerCase())`.
Aksiyon: `toLocaleLowerCase('tr-TR')` kullanilarak Turkce case-folding kurallarina uyulmasi saglanmali; ideal olarak hem etiket hem sorgu bu locale ile kucultulmeli.
Onem: Orta · Guven: Dogrulanmali

### [FCMD-004] Ok tuslariyla secili satir gorunum disina cikabilir, otomatik kaydirma yok
Sorun: `max-h-64 overflow-y-auto` (satir 67) ile sonuc listesi kirpiliyor, ancak `selectedIdx` degistiginde (satir 33-38) secili ogeye `scrollIntoView` gibi bir kaydirma tetiklenmiyor. Liste 64 birimden uzun oldugunda ok tuslariyla asagi/yukari gezinirken secili satir gorunum disina cikabilir.
Kanit (satir 33-38, 67): `setSelectedIdx` guncellemesinde DOM kaydirma yok; scroll container `max-h-64 overflow-y-auto`.
Aksiyon: Secili buton icin bir `ref` dizisi tutup `selectedIdx` degisince `ref.current[selectedIdx]?.scrollIntoView({ block: 'nearest' })` cagirilmali.
Onem: Orta · Guven: Kesin

### [FCMD-005] "Cmd+N" klavye kisayol etiketleri platforma gore yanlis olabilir
Sorun: `COMMANDS` dizisindeki `hint` alanlari (satir 5-11) sabit olarak "Cmd+1".."Cmd+7" yaziyor. Proje Windows ortaminda calisiyor (bkz. env), Windows'ta tipik kisayol modifikatoru "Ctrl"dur; gercek kisayol baglamasi baska bir yerde (orn. App.jsx) `metaKey`/`ctrlKey` kontrolu ile farkli calisiyor olabilir. Sabit "Cmd" metni Windows kullanicisini yanlis yonlendirebilir.
Kanit (satir 5-11): `hint: 'Cmd+1'` ... `hint: 'Cmd+7'` sabit string, platform kontrolu yok.
Aksiyon: `navigator.platform`/`navigator.userAgentData` ile Mac disi platformlarda "Ctrl+N" gosterilmeli veya gercek kisayol baglama kodu ile senkron dogrulanmali.
Onem: Orta · Guven: Dogrulanmali

### [FCMD-006] Liste ogelerinin dokunma hedefi 44px altinda kalabilir
Sorun: Sonuc satirlari `px-4 py-2.5 text-sm` (satir 75) kullaniyor; `py-2.5` (10px ust+alt) + `text-sm` satir yuksekligi yaklasik 20px toplamda ~40px civarinda kaliyor, WCAG/erisilebilirlik icin onerilen 44px dokunma hedefinin altinda kalabilir (mobil kullanim PROJE.md'de D1 hedefi olarak belirtiliyor).
Kanit (satir 75): `className="w-full flex items-center justify-between px-4 py-2.5 text-sm text-left transition-colors ..."`.
Aksiyon: Mobilde `py-3` veya `min-h-[44px]` gibi bir sinif eklenerek dokunma hedefi buyutulmeli.
Onem: Dusuk · Guven: Dogrulanmali

### [FCMD-007] Modal acikken arka plan scroll kilidi yok
Sorun: Palet acildiginda (`fixed inset-0` overlay, satir 46) `document.body` uzerinde scroll kilidi (orn. `overflow: hidden`) uygulanmiyor. Uzun sayfalarda arka plan mouse teker/touch ile kaydirilabilir, bu da modal disindaki icerigin gorunmesine ve odak/scroll karisikligina yol acabilir.
Kanit (satir 44-48): overlay `div` render edilirken body scroll durumu hic degistirilmiyor, ilgili `useEffect` yok.
Aksiyon: `useEffect(() => { document.body.style.overflow = 'hidden'; return () => { document.body.style.overflow = ''; }; }, [])` eklenmeli.
Onem: Dusuk · Guven: Dogrulanmali
