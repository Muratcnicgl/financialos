# Denetim: frontend/src/panels/Coach.jsx

> **M86 güncellik:** 🟡 KISMEN-BAYAT — FCO-006 düzeltildi; FCO-001/002/003/004/005/007 açık


> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [FCO-001] handleSend ve handleReset'te unmount sonrasi state guncelleme korumasi yok
Sorun: Sayfa yuklerken kullanilan history-fetch useEffect'i (satir 158-182) `mounted` flag'i ile unmount sonrasi setState'i engelliyor, ama `handleSend` (satir 198-248) ve `handleReset` (satir 261-287) ayni korumaya sahip degil. Kullanici mesaj gonderip yanit beklerken paneli/sekmeyi degistirip CoachInner unmount olursa, `await coachApi.chat(text)` donduğunde `setMessages`, `setUsage`, `setError`, `setSending` cagrilari unmount olmus bilesen uzerinde calisir.
Kanit (satir 208-247, 265-286): `const res = await coachApi.chat(text); ... setMessages((prev) => [...prev, coachMsg]);` — araya `mounted` kontrolu girmiyor.
Aksiyon: History-fetch useEffect'indeki gibi bir `mounted`/`AbortController` ref'i ekleyip async islemler donduğunde bileşenin hala mount oldugunu kontrol et.
Onem: Orta · Guven: Dogrulanmali (React 18'de bu artik sadece console warning uretir, hard crash degil, ama StrictMode/dev'de gurultu ve teorik olarak stale toast tetikler)

### [FCO-002] Gecmis yukleme hatasi kullaniciya hic gosterilmiyor
Sorun: `coachApi.history(50)` veya `Promise.all` reddederse (satir 175-177), sadece `historyLoaded` true yapiliyor; `error` state'i hic set edilmiyor. Kullanici gercek bir sohbet gecmisine sahipken sadece ag hatasi yuzunden bos "Henuz mesaj yok" ekranini gorur — hic hata bildirimi yok.
Kanit (satir 174-177):
```
.catch(() => {
  if (mounted) setHistoryLoaded(true);
});
```
Aksiyon: catch bloguna `setError('Sohbet gecmisi yuklenemedi')` veya toast.error ekle, boylece kullanici veri kaybi ile bos sohbeti ayirt edebilsin.
Onem: Orta · Guven: Kesin

### [FCO-003] Mesaj listesinde index key kullanimi
Sorun: `messages.map((m, i) => <Message key={i} ...>)` — index'i React key olarak kullaniyor. Su an mesajlar sadece sona ekleniyor ve sifirlamada tum dizi bosaltiliyor oldugu icin pratikte gorsel bug uretmiyor, ama gelecekte optimistic mesaj silme/duzenleme/insert-at-top (ornegin sayfalama ile eski mesajlari basa eklemek) eklenirse yanlis DOM/element eslemesi ve stale ReactMarkdown/TracePanel state'i riski var.
Kanit (satir 448-454): `{messages.map((m, i) => ( <Message key={i} message={m} onActionResolved={handleActionResolved} /> ))}`
Aksiyon: Backend'den gelen `coachMemoryId` veya kullanici mesajlari icin olusturulacak stabil bir `crypto.randomUUID()`/timestamp+role tabanli id kullan.
Onem: Dusuk · Guven: Kesin (index-key kullanimi dogrulanmis; risk senaryosu gelecege donuk)

### [FCO-004] Message bileseni memoize edilmemis — her tus vurusunda tum sohbet yeniden render/parse ediliyor
Sorun: `input` state'i her tus vurusunda degisiyor (satir 144, 475), bu da `CoachInner` render'ini tetikliyor. `Message` React.memo ile sarilmadigi ve `preprocessMarkdown` + `ReactMarkdown` her render'da yeniden calistigi icin (satir 545-547), sohbet uzadikca (50+ mesaj) her karakter yazarken TUM gecmis mesajlarin markdown'i yeniden parse ediliyor. Uzun sohbette input gecikmesi (jank) yaratir.
Kanit (satir 448-454, 544-548): `Message` component'i `function Message(...)` olarak export ediliyor, `React.memo` sarmalamasi yok; `preprocessMarkdown(message.text)` her render'da cagriliyor, `useMemo` yok.
Aksiyon: `const Message = React.memo(function Message(...) {...})` yap ve/veya `preprocessMarkdown` sonucunu `useMemo(() => preprocessMarkdown(message.text), [message.text])` ile onbellekle.
Onem: Orta · Guven: Kesin (kod yapisindan dogrulanabilir; performans etkisi mesaj sayisina bagli)

### [FCO-005] Ikon-sadece kontrollerde erisilebilir isim aria-label yerine sadece title'a dayaniyor
Sorun: Mobilde (`sm` altinda) Yeni sohbet butonunun metni gizleniyor (`hidden sm:inline`, satir 387) ve geriye sadece ikon + `title` attribute'u kaliyor; gonder butonu da hep ikon-sadece (satir 482-489) ve sadece `title` var. `title` ekran okuyucular tarafindan tutarli sekilde erisilebilir isim olarak okunmaz (touch cihazlarda hic gorunmez), `aria-label` daha guvenilir.
Kanit (satir 380-388): `<button onClick={handleReset} ... title="Yeni sohbet (geçmişi sıfırla)"> ... <span className="hidden sm:inline">Yeni sohbet</span></button>`; (satir 482-489): `<button onClick={handleSend} ... title="Gönder (Enter)">`.
Aksiyon: Her iki butona da acik `aria-label` ekle (ornegin `aria-label="Yeni sohbet"` / `aria-label="Gönder"`), textarea'ya da `aria-label="Koça mesaj yaz"` ekle (satir 472-481, sadece placeholder var).
Onem: Orta · Guven: Dogrulanmali (dimension audit'te a11y kapsanmis olabilir, bu satir-spesifik gap yine de gecerli)

### [FCO-006] parseHistoryDate, proje genelindeki UTC 'Z' suffix parse kuralini uygulamiyor
Sorun: `frontend/PROJE.md` acikca `new Date(dateStr + (dateStr.endsWith('Z') ? '' : 'Z'))` pattern'ini zorunlu kiliyor çünkü backend bazi endpoint'lerde suffix'siz UTC donduruyor. `parseHistoryDate` bu korumayi uygulamadan dogrudan `new Date(raw)` cagiriyor.
Kanit (satir 125-135):
```
function parseHistoryDate(item) {
  const raw = item?.created_at ?? item?.timestamp;
  if (!raw) return null;
  try {
    const d = new Date(raw);
```
Aksiyon: `architecture.md`'de belirtilen `_memory_to_history_item` zaten `tzinfo=timezone.utc` ekleyip `+00:00` suffix'li donduruyorsa bu satir güvenli olabilir; yine de savunma amacli `raw.endsWith('Z') || raw.includes('+')` kontrolu eklemek gelecekteki bir backend regresyonuna karsi frontend'i korur.
Onem: Dusuk · Guven: Dogrulanmali (backend tarafi docs'a gore zaten duzeltilmis olabilir; bu sadece savunma katmani eksikligi)

### [FCO-007] handleKeyDown ve preprocessMarkdown her render'da yeniden olusturuluyor, useCallback/useMemo yok
Sorun: `handleKeyDown` (satir 250-255) plain fonksiyon olarak her render'da yeniden yaratiliyor ve textarea'ya prop olarak geciliyor; `handleSend` ise `useCallback` ile sariliyor ama bagimliligi `[input, sending, toast]` oldugu icin input her degistiginde zaten yeniden olusuyor, dolayisiyla `useCallback` burada pratik fayda saglamiyor (referans stabilitesi hicbir zaman korunmuyor).
Kanit (satir 198-248, 250-255).
Aksiyon: Kritik degil ama tutarlilik icin ya `handleKeyDown`'u da `useCallback` ile sar ya da `handleSend`'in referans instabilitesinin kabul edilebilir oldugunu belgeleyip `useCallback`'i kaldir (kod okunurlugu icin).
Onem: Dusuk · Guven: Kesin
