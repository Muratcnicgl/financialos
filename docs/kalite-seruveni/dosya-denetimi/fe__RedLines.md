# Denetim: frontend/src/panels/RedLines.jsx

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [FRL-001] handleToggleActive hata yakalama eksigi - unhandled promise rejection
Sorun: `handleToggleActive` (satir 121-124) `checkpointsApi.update` cagrisini try/catch olmadan await ediyor. Bu fonksiyon `CheckpointCard` icindeki Power butonundan dogrudan `onClick={onToggleActive}` ile tetikleniyor (satir 259, 341) - cagri zincirinde hicbir yerde catch yok. `handleSave` (satir 114-119) ve `handleDelete` (satir 126-130) buyuk resimde modal katmaninda try/catch ile sarilirken (satir 381-392, 495-504), toggle icin boyle bir sarmalayici yok.
Kanit (satir 121-124):
```
const handleToggleActive = async (cp) => {
  await checkpointsApi.update(cp.id, { is_active: !cp.is_active });
  handleRefresh();
};
```
`api.js`'deki `request()` basarisiz istekte `ApiError` firlatiyor (dogrulandi: `frontend/src/api.js` satir 184-192).
Aksiyon: `handleToggleActive` icine try/catch ekle; hata durumunda `setError(e.message)` ile kullaniciya goster (mevcut `error` state'i zaten var, satir 57).
Onem: Yuksek · Guven: Kesin

### [FRL-002] useEffect'te unmount sonrasi setState koruma yok (stale/leaked async)
Sorun: `useEffect(() => { load(); }, [load])` (satir 79) hicbir cleanup/iptal mekanizmasi icermiyor. `load` icindeki `setCheckpoints`/`setError`/`setLoading`/`setRefreshing` cagrilar (satir 66-77), component unmount olduktan sonra fetch tamamlanirsa yine calisir - "Can't perform a React state update on an unmounted component" uyarisi ve potansiyel bellek sizintisi riski. `handleRefresh` (satir 81) de ayni `load`'u tekrar tetikliyor, aralarda component unmount olursa ayni risk.
Kanit (satir 66-81).
Aksiyon: `useEffect` icinde bir `let cancelled = false` / `AbortController` ile cleanup ekle, `load` sonunda `if (cancelled) return;` kontrolu koy.
Onem: Orta · Guven: Kesin

### [FRL-003] Power butonuna cift-tiklama korumasi yok - race condition
Sorun: `CheckpointCard` icindeki Power butonu (satir 340-346) `onToggleActive` cagrisi sirasinda disable edilmiyor. Kullanici hizli art arda tiklarsa `checkpointsApi.update` birden fazla kez tetiklenir, yanit sirasi garantisiz oldugundan son state'in ne olacagi belirsizlesir (ornegin aktiften pasife, sonra tekrar aktife hizli tiklayinca yaris durumu son gelen yaniti kazanabilir, kullanicinin gordugu son tiklama degil).
Kanit (satir 340-346), `handleToggleActive` (satir 121-124) hicbir busy/loading state tutmuyor.
Aksiyon: Card bazinda bir `togglingId` / per-card busy state ekleyip istek surerken butonu disable et.
Onem: Dusuk · Guven: Dogrulanmali (UX etkisi kucuk ama gercek bir yaris kosulu)

### [FRL-004] parseInt radix parametresi eksik
Sorun: Satir 386'da `parseInt(priority)` radix argumani olmadan cagriliyor. Bu ornekte `priority` degeri her zaman '1'/'2'/'3' string'i oldugundan pratikte hatali sonuc uretmiyor, ancak radix'siz `parseInt` genel olarak guvensiz bir pattern (ornegin '08' gibi degerlerde eski motorlarda octal yorumlanma riski tarihsel olarak vardi).
Kanit (satir 386): `priority: parseInt(priority),`
Aksiyon: `parseInt(priority, 10)` yaz.
Onem: Dusuk · Guven: Kesin

### [FRL-005] CheckpointFormModal'da unmount sonrasi setState riski
Sorun: `handleSubmit` (satir 373-393) `await onSave(...)` sirasinda component unmount olursa (ornegin ust panel `editing` state'ini disaridan degistirirse), catch blogundaki `setError`/`setBusy(false)` cagrilari unmounted component uzerinde calisabilir. Ayni durum `ConfirmDeleteModal.handleDelete` (satir 495-504) icin de gecerli.
Kanit (satir 389-392, 500-503).
Aksiyon: Kucuk olcekli risk - bir `isMounted` ref veya `AbortController` ile korunabilir; oncelik dusuk cunku modal genelde kullanicinin kendi eylemiyle kapatiliyor.
Onem: Dusuk · Guven: Dogrulanmali

### [FRL-006] Dinamik Tailwind renk siniflari - dogrulama notu (mevcut safelist ile kapsanmis)
Sorun degil, dogrulama: Satir 195, 200, 307, 315, 318, 409, 427'de `text-${meta.color}-600`, `bg-${typeMeta.color}-100`, `ring-${meta.color}-500` gibi dinamik olusturulan Tailwind sinif adlari kullaniliyor. `frontend/tailwind.config.js` satir 10-18'de BUG #061 fix notuyla bu tam senaryo icin (`text|bg|ring|border-(brand|positive|negative|warn)-(100|400|500|600|950)`, dark varyanti dahil) bir safelist zaten eklenmis; `chip-${typeMeta.color}` ve `btn-${meta.color}` gibi bilesen siniflari da `index.css`'te statik @apply ile tanimli (JIT-uretimli degil), yani purge riski tasimiyor. Bu madde yeni bir bulgu degil, onceki denetimin bu dosya icin dogru sekilde kapatildigini teyit ediyor.
Kanit: `frontend/tailwind.config.js` satir 10-18.
Aksiyon: Yok (bilgi amacli).
Onem: Dusuk · Guven: Kesin
