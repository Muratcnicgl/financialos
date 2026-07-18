# Denetim: frontend/src/panels/Cockpit.jsx

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [FCP-001] Index-key kullanımı: alerts, upcoming_reminders, upcoming_payments, upcoming_receivables listeleri
Sorun: Dört ayrı liste render'ında React key olarak dizi index'i kullanılıyor. Backend her `load()` çağrısında bu dizileri yeniden üretiyor (sıralama/eleman sayısı fetch'ler arasında değişebilir); index-key ile React DOM elemanlarını yanlış eşleştirebilir (stale içerik, gereksiz remount, animasyon/transition glitch).
Kanit (satir 230-232, satir 376-385, satir 417-419, satir 456-459):
```
{data.alerts.map((alert, i) => (
  <div key={i} ...
{data.upcoming_reminders.map((r, i) => {
  ...
  <div key={i} ...
{data.upcoming_payments.map((p, i) => (
  <div key={i} ...
{data.upcoming_receivables.map((r, i) => (
  <div key={i} ...
```
Aksiyon: Backend'den her satır için stabil bir kimlik geliyorsa (örn. receivable id, payment id, reminder id) onu key yap; yoksa backend'e stabil id eklenmesi istenmeli. `price_freshness.items` zaten `item.account_id` ile doğru yapılmış (satir 494), örnek olarak kullanılabilir.
Onem: Orta · Guven: Kesin (index-key kullanımı kodda açık; gerçek kullanıcı etkisinin büyüklüğü veri sıklığına bağlı, bu kısım Dogrulanmali).

### [FCP-002] PriceUpdateModal: erişilebilirlik — dialog semantiği, Escape ile kapama, label ilişkilendirmesi eksik
Sorun: Modal `role="dialog"`/`aria-modal="true"` taşımıyor, klavye ile Escape tuşuna basıldığında kapanmıyor (sadece mouse ile overlay tıklamasıyla kapanıyor), ve fiyat input'unun `<label>` etiketi `htmlFor`/`id` ile programatik olarak bağlı değil (sadece görsel yakınlık).
Kanit (satir 630-634, satir 651-661):
```
<div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4 animate-fade-in" onClick={onClose}>
  <div className="card p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
...
<label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">
  Yeni fiyat (TL)
</label>
<input type="text" value={newPrice} onChange={(e) => setNewPrice(e.target.value)} className="input" placeholder="4929.56" autoFocus />
```
Aksiyon: Dış `div`'e `role="dialog" aria-modal="true" aria-labelledby="price-modal-title"` ekle, başlığa `id="price-modal-title"` ver; `label htmlFor="new-price-input"` + `input id="new-price-input"` bağla; `onKeyDown` ile Escape tuşunda `onClose()` çağıran bir handler ekle (veya `useEffect` içinde `keydown` listener + cleanup).
Onem: Yuksek · Guven: Kesin.

### [FCP-003] load() ve cashflow forecast çağrısı unmount sonrası setState riski (temizlik yok)
Sorun: `useEffect(() => { load(); }, [load])` içinde herhangi bir cleanup/abort mekanizması yok. `load()` içindeki `Promise.all` çözüldüğünde veya satir 64-66'daki bağımsız `cashflowApi.getForecast(...).then(...)` zinciri tamamlandığında, kullanıcı bu sırada sekme değiştirip Cockpit unmount olmuşsa `setData`/`setPendingActions`/`setFlowSummary`/`setError`/`setLoading`/`setRefreshing` unmounted bileşen üzerinde çağrılır.
Kanit (satir 39-69):
```
const load = useCallback(async () => {
  try { ... setData(cockpit); setPendingActions(merged); }
  catch (e) { setError(...); }
  finally { setLoading(false); setRefreshing(false); }
  cashflowApi.getForecast({ days: 30 })
    .then(r => setFlowSummary(r.summary))
    .catch(() => {});
}, []);

useEffect(() => { load(); }, [load]);
```
Aksiyon: `useEffect` içine bir `isMounted`/`AbortController` bayrağı ekleyip cleanup fonksiyonunda `false` yaparak, ilgili `then`/`catch`/`finally` bloklarında state güncellemeden önce kontrol et.
Onem: Dusuk · Guven: Dogrulanmali (React 18'de bu artık console error üretmiyor, ama stale/gecikmiş response geldiğinde yanlış ekrana yazma riski gerçek).

### [FCP-004] carried_forward / nakit_kasa vb. alanlar undefined geldiğinde sessizce NaN/"undefined" render riski
Sorun: `data.carried_forward !== 0` kontrolü `undefined` için de `true` döner (`undefined !== 0`), bu durumda `signClass(undefined)` ve `formatTL(undefined)` çağrılıp muhtemelen "Devreden +undefined TL" gibi bozuk bir metin basılır. Aynı şekilde satir 182/190/198'de `data.reel_butce >= 0`, `data.net_deger >= 0`, `netDegerTam >= 0` karşılaştırmaları alan `undefined` ise sessizce `false` döner ve `MetricCard` `undefined` değeri formatlamaya çalışır.
Kanit (satir 217-223, satir 179-203):
```
{data.carried_forward !== 0 && (
  <span className={signClass(data.carried_forward)}>
    {' '}· Devreden {data.carried_forward > 0 ? '+' : ''}{formatTL(data.carried_forward)} TL
  </span>
)}
...
variant={data.reel_butce >= 0 ? 'positive' : 'negative'}
```
Aksiyon: Cockpit response contract'ı garanti ediyorsa (rules_engine her zaman sayısal döner) bu risk teorik — ama savunmacı kod isteniyorsa `data.carried_forward ?? 0` / `(data.reel_butce ?? 0) >= 0` gibi fallback eklenebilir.
Onem: Dusuk · Guven: Dogrulanmali (backend kontratı `app/rules_engine.py`'de doğrulanmadı, bu dosya kapsamı dışında).

### [FCP-005] PriceUpdateModal fiyat parse: yalnızca ilk virgül değiştiriliyor
Sorun: `newPrice.replace(',', '.')` global flag taşımıyor; kullanıcı birden fazla virgül girerse (örn. yanlışlıkla "4,929,56") yalnızca ilk virgül nokta yapılır, `parseFloat` geri kalanı görmezden gelir ve sessizce hatalı/eksik bir sayı üretebilir (örn. "4.92956" yerine "4.929" gibi kesilmiş bir değer, ya da NaN yerine yanlış geçerli sayı — kullanıcıya hata gösterilmez).
Kanit (satir 611):
```
const price = parseFloat(newPrice.replace(',', '.'));
```
Aksiyon: `newPrice.replace(/,/g, '.')` yerine `newPrice.replace(/\./g, '').replace(',', '.')` (binlik ayraç + ondalık virgül) gibi daha sağlam bir Türkçe sayı parse fonksiyonu kullan; en azından tekrarlı virgülü hata olarak yakala.
Onem: Dusuk · Guven: Kesin (kod satırı net; gerçek kullanıcı etkisi nadir kenar durum).

### [FCP-006] Magic string'ler: alert.seviye, r.type, p.tip değerleri kod içinde tekrar tekrar literal karşılaştırılıyor
Sorun: `'kritik'`, `'income'`, `'gelir'`, `'kredi_taksit'` gibi backend enum değerleri sabit/import edilen bir enum yerine doğrudan string literal olarak birden fazla yerde tekrarlanıyor. Backend bu değerlerden birini yeniden adlandırırsa derleme zamanı hiçbir uyarı vermeden sessizce kırılır (örn. renk/simge her zaman "diğer" dalına düşer).
Kanit (satir 234-252, satir 380-383, satir 427-430):
```
alert.seviye === 'kritik' ? ... : ...
r.type === 'income' ? '+' : '−'
p.tip === 'gelir' ? 'Gelir' : p.tip === 'kredi_taksit' ? 'Kredi taksiti' : p.tip
```
Aksiyon: Zorunlu değil ama önerilir — bu string sabitlerini `api.js` veya ayrı bir `constants.js` içinde tek yerden export edip panel'lerde oradan kullanmak, yazım hatası/rename riskini azaltır.
Onem: Dusuk · Guven: Kesin.

### [FCP-007] PriceUpdateModal aynı anda açıkken account değişirse başlangıç state'i güncellenmez (stale state riski)
Sorun: `PriceUpdateModal`'ın `newPrice` state'i `useState(account.fiyat?.toString() || '')` ile yalnızca mount anında hesaplanıyor. Eğer `priceUpdateAccount` prop'u modal unmount edilmeden (aynı component instance'ı korunarak) başka bir hesaba güncellenirse, input eski hesabın fiyatını göstermeye devam eder. Bu senaryonun bu dosyadaki mevcut tetikleyicilerle (her zaman `onClose` ile null'a çekilip sonra yeniden açılıyor gibi görünüyor) gerçekleşip gerçekleşmediği `AccountCard`'ın buton davranışına bağlı, bu dosyadan kesin doğrulanamadı.
Kanit (satir 517-526, satir 605):
```
{priceUpdateAccount && (
  <PriceUpdateModal
    account={priceUpdateAccount}
    onClose={() => setPriceUpdateAccount(null)}
    onUpdated={() => { setPriceUpdateAccount(null); handleRefresh(); }}
  />
)}
...
const [newPrice, setNewPrice] = useState(account.fiyat?.toString() || '');
```
Aksiyon: Güvenli hale getirmek için `<PriceUpdateModal key={account.id} .../>` şeklinde `key` eklenmesi, account değiştiğinde component'i zorla yeniden mount ederek state'i sıfırlar.
Onem: Dusuk · Guven: Dogrulanmali (tetikleyici yol bu dosyada net değil, AccountCard.jsx incelenmeli).

### [FCP-008] data?.accounts satirinda gereksiz opsiyonel zincirleme (dead defensive code)
Sorun: `data` zaten satir 102'de `if (!data) return null;` ile garanti edilmiş olmasına rağmen satir 135'te `data?.accounts` kullanılıyor. Hatalı değil ama yanıltıcı — okuyucuya `data`'nın burada null olabileceği izlenimini veriyor.
Kanit (satir 135):
```
<PendingActions actions={pendingActions} onResolved={handleActionResolved} accounts={data?.accounts} />
```
Aksiyon: `data.accounts` olarak sadeleştirilebilir (kozmetik, isteğe bağlı).
Onem: Dusuk · Guven: Kesin.
