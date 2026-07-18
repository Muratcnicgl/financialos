# Denetim: frontend/src/components/Toast.jsx

> **M86 güncellik:** 🟢 GÜNCEL — 7 bulgu açık


> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [FTO-001] Context value her render'da yeniden yaratiliyor (memoizasyon eksigi)
Sorun: `api` nesnesi `ToastProvider` govdesinde her render'da yeni referansla olusturuluyor ve `ToastContext.Provider value={api}` olarak geciliyor. Bu, `useToast()` kullanan tum tuketici bilesenlerin gereksiz yere yeniden render olmasina yol acar (context value referans esitligiyle karsilastirilir).
Kanit (satir 82-88): `const api = { success: ..., error: ..., info: ..., warning: ..., dismiss };` — `useMemo` veya `useCallback` ile sarmalanmamis.
Aksiyon: `api` nesnesini `useMemo(() => ({...}), [show, dismiss])` ile memoize et.
Onem: Orta · Guven: Kesin

### [FTO-002] Manuel kapatmada (X) otomatik-dismiss zamanlayicisi temizlenmiyor
Sorun: `show()` icinde `setTimeout(() => dismiss(id), duration)` referansi hicbir yerde saklanmiyor/temizlenmiyor. Kullanici X'e basip toast'i erken kapattiginda (`handleClose`), `show()`'daki orijinal zamanlayici hala bellekte bekliyor ve suresi dolunca `dismiss(id)`'i tekrar cagiriyor (no-op ama gereksiz calisma / potansiyel kafa karistirici side-effect kaynagi).
Kanit (satir 76-78): `if (duration > 0) { setTimeout(() => dismiss(id), duration); }` — donen timer id'si yok, `useEffect` cleanup'i yok.
Aksiyon: Timer id'lerini toast state'inde veya bir ref map'te sakla; `dismiss`/`handleClose` cagrildiginda ilgili `clearTimeout` cagir.
Onem: Dusuk · Guven: Kesin

### [FTO-003] Kapat butonu 44px dokunma hedefi altinda
Sorun: X butonu (satir 149-155) sadece `w-4 h-4` (16px) ikon iceriyor, butonun kendisinde padding/min-width/min-height yok. Mobil dokunma hedefi (44x44px) gereksinimini karsilamiyor; bu proje D1 mobil gorunum hedefini tasidigi icin risklidir.
Kanit (satir 149-155): `<button onClick={handleClose} className="flex-shrink-0 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition-colors" title="Kapat">`.
Aksiyon: Butona `p-2` (veya benzeri) ekleyerek gercek tiklanabilir alani en az 44x44px'e cikar.
Onem: Orta · Guven: Kesin

### [FTO-004] Kapat butonunda erisilebilir isim aria-label yerine sadece title'a dayaniyor
Sorun: Buton `title="Kapat"` disinda `aria-label` icermiyor. Ikon-only butonlarda ekran okuyucu tutarliligi icin `aria-label` acik tercih edilir; `title` tarayici/AT kombinasyonuna gore tutarsiz okunabilir ve dokunmatik cihazlarda hic gorunmez.
Kanit (satir 149-153): `title="Kapat"` var, `aria-label` yok.
Aksiyon: `aria-label="Bildirimi kapat"` ekle (title ile birlikte tutulabilir).
Onem: Dusuk · Guven: Dogrulanmali

### [FTO-005] Hata tipi toast'lar icin role="status" kullaniliyor (assertive olmali)
Sorun: Tum toast tipleri (`success`, `error`, `info`, `warning`) ayrim yapilmadan `role="status"` (aria-live="polite" esdegeri) kullaniyor. WAI-ARIA pratiginde hata/kritik bildirimler icin `role="alert"` (assertive) tercih edilir ki ekran okuyucu kullanicisi mevcut okumayi kesip hemen duyursun.
Kanit (satir 135): `role="status"` — `toast.type === 'error'` ayrimi yok.
Aksiyon: `role={toast.type === 'error' ? 'alert' : 'status'}` gibi bir kosul ekle.
Onem: Orta · Guven: Dogrulanmali

### [FTO-006] Kucuk duration degerlerinde cikis animasyonu negatif gecikmeyle tetiklenebilir
Sorun: `setTimeout(() => setExiting(true), toast.duration - 300)` hesaplamasi `toast.duration < 300` oldugunda negatif gecikme uretir; bu durumda `exiting` state'i neredeyse aninda true olur ve toast gorunur olmadan/aninda cikis animasyonuyla render edilebilir. Su an caginlan `show()` API'leri (`success/error/info/warning`) `options.duration` gecebildigi icin cagiran taraf kucuk bir deger geçerse bu senaryo tetiklenir.
Kanit (satir 118-123): `const exitTimer = setTimeout(() => setExiting(true), toast.duration - 300);` — alt sinir kontrolu yok.
Aksiyon: `Math.max(0, toast.duration - 300)` kullan.
Onem: Dusuk · Guven: Kesin

### [FTO-007] toast.title/detail bos veya undefined oldugunda dogrulama yok
Sorun: `toast.title` API tuketicilerinden dogrudan geliyor (orn. `toast.success(title, options)`); bos string veya `undefined` gecilirse bos bir `<p>` render edilir, kullaniciya anlamsiz/bos bir bildirim kutusu gosterilebilir.
Kanit (satir 140-142): `<p className="text-sm font-semibold ${meta.titleClass}">{toast.title}</p>` — bos deger kontrolu yok.
Aksiyon: `show()` icinde `if (!title) return null;` benzeri bir erken cikis veya en azindan gelistirme ortaminda `console.warn` eklenebilir (dusuk oncelik, cagiran taraf disiplinine birakilabilir).
Onem: Dusuk · Guven: Dogrulanmali

## Bulgu Ozeti
Dosyada dogrudan `fetch`/`axios` cagrisi, index-key kullanimi, dinamik (purge riskli) Tailwind sinifi, stale closure veya unhandled promise rejection tespit edilmedi — bu acidan dosya temiz. Yukaridaki bulgular esas olarak memoizasyon, zamanlayici temizligi ve erisilebilirlik (a11y/mobil dokunma hedefi) etrafinda toplaniyor.
