# Denetim: frontend/src/components/HorizonsModal.jsx

### [FHM-001] Escape tuşu dinleyicisi modal kapaliyken de global olarak bağlı kalıyor
Sorun: Escape keydown handler'i barındıran useEffect, isOpen durumuna bağlı değil (satır 117-121). `isOpen=false` olduğunda component `null` render ediyor (satır 171) ama hook zaten çalışmış ve `window` üzerine `keydown` listener eklenmiş oluyor. Parent component bu modalı `isOpen=false` iken de mount edilmiş tutuyorsa (örn. koşullu render yerine prop ile aç/kapa yapılıyorsa), kullanıcı uygulamanın herhangi bir yerinde Escape'e bastığında bu modalın `onClose()` fonksiyonu tetiklenir — modal görünür olmasa bile.
Kanıt (satır 117-121):
```
useEffect(() => {
  const handler = (e) => { if (e.key === 'Escape') onClose(); };
  window.addEventListener('keydown', handler);
  return () => window.removeEventListener('keydown', handler);
}, [onClose]);
```
Aksiyon: Handler içine `if (!isOpen) return;` guard'ı ekle veya efekti `isOpen` bağımlılığına bağla ve `isOpen` false iken listener'ı hiç eklemeden çık.
Önem: Orta · Güven: Kesin

### [FHM-002] Reddet butonu, onaylama işlemi devam ederken (phase='approving') aktif kalıyor — çakışan istek riski
Sorun: `canAct = phase === 'success' || phase === 'approving'` (satır 173). Reddet butonu `disabled={!canAct}` kullanıyor (satır 328), yani `approving` fazında da **etkin**. Onayla butonu ise ayrıca `phase === 'approving'` kontrolü ile devre dışı bırakılıyor (satır 335) ama Reddet için böyle bir ek kontrol yok. Kullanıcı "Yine de Onayla"ya bastıktan hemen sonra, backend'den cevap gelmeden "Vazgeç (Reddet)"e basabilir; bu durumda `actionsApi.approve` ve `actionsApi.reject` aynı `actionId` için yarışan (race) iki istek olarak backend'e gider.
Kanıt (satır 173, 326-332, 333-337):
```
const canAct = phase === 'success' || phase === 'approving';
...
<button onClick={handleReject} disabled={!canAct} ...>Vazgeç (Reddet)</button>
...
<button onClick={handleApprove} disabled={!canAct || phase === 'approving'} ...>
```
Aksiyon: Reddet butonuna da `|| phase === 'approving'` ekle (`disabled={!canAct || phase === 'approving'}`), ya da ayrı bir `isBusy` state'i ile her iki aksiyon butonunu birlikte kilitle.
Önem: Yüksek · Güven: Kesin

### [FHM-003] runSimulation için abort/mount-guard yok — geç dönen yanıt yanlış actionId'nin sonucunu ekrana yazabilir
Sorun: `runSimulation` (satır 135-146) `await simulationApi.run(actionId)` sonrası doğrudan `setResult`/`setPhase` çağırıyor. Kullanıcı modalı hızlıca kapatıp farklı bir `actionId` ile tekrar açarsa (veya component unmount olursa), önceki isteğin cevabı geç dönüp state'i güncelleyebilir — ya kapalı bir modalda gereksiz state güncellemesi ya da yeni açılan modalda eski `actionId`'nin sonucunun kısa süreliğine görünmesi riski oluşur. AbortController veya bir "bu istek hâlâ güncel mi" bayrağı yok.
Kanıt (satır 135-146):
```
const runSimulation = async () => {
  setPhase('loading');
  setError(null);
  try {
    const res = await simulationApi.run(actionId);
    setResult(res);
    setPhase('success');
  } catch (e) { ... }
};
```
Aksiyon: Effect içinde bir `let cancelled = false` bayrağı kullan, cleanup'ta `cancelled = true` yap; `setResult`/`setPhase` çağrılarını `if (!cancelled)` ile koru. Alternatif olarak `actionId`'yi isteğin closure'ında saklayıp dönen cevabın hâlâ güncel `actionId`'ye ait olduğunu doğrula.
Önem: Orta · Güven: Dogrulanmali

### [FHM-004] Event log listesinde index key kullanılıyor
Sorun: `result.event_log.slice(0, 5).map((ev, i) => <li key={i}>...)` (satır 307-309) index'i React key olarak kullanıyor. Liste sırası değişmeyeceği için görünürde risk düşük, ancak `event_log` string dizisinin kendisi zaten stabil bir benzersiz değer olarak (ör. `${ev}-${i}`) kullanılabilirken index-key anti-pattern'i korunmuş.
Kanıt (satır 307-309):
```
{result.event_log.slice(0, 5).map((ev, i) => (
  <li key={i} className="text-xs text-zinc-500 dark:text-zinc-400 font-numeric">{ev}</li>
))}
```
Aksiyon: `key={`${ev}-${i}`}` gibi içerik+index birleşimi kullan ya da backend event_log'a stabil id ekle.
Önem: Düşük · Güven: Kesin

### [FHM-005] handleReject başarısız olduğunda kullanıcıya bildirim yapılmadan modal kapatılıyor
Sorun: `handleReject` (satır 161-169) `catch` bloğunda hata sessizce yutuluyor (`// sessiz`) ve `onClose()` her durumda çağrılıyor. Reddetme API çağrısı backend'de başarısız olursa kullanıcı "reddedildi" izlenimiyle modalı kapatır ama aksiyon aslında hâlâ `pending` durumda kalabilir — kullanıcı bunu fark edemez çünkü `toast.info('Aksiyon reddedildi')` sadece başarı durumunda çağrılıyor, hata durumunda hiçbir toast gösterilmiyor.
Kanıt (satır 161-169):
```
const handleReject = async () => {
  try {
    await actionsApi.reject(actionId);
    toast.info('Aksiyon reddedildi');
  } catch {
    // sessiz
  }
  onClose();
};
```
Aksiyon: Catch bloğuna `toast.error(...)` ekle ve/veya hata durumunda modalı kapatmadan kullanıcıyı tekrar denemeye yönlendir (handleApprove'daki hata-yakalama desenine benzet, bkz. satır 155-158).
Önem: Orta · Güven: Kesin

### [FHM-006] Arka plan tıklaması, onaylama isteği devam ederken (phase='approving') modalı kapatabiliyor
Sorun: Dış konteynerdeki `onClick={onClose}` (satır 176-179) hiçbir fazda kısıtlanmıyor. `approving` fazında kullanıcı arka plana tıklarsa modal kapanır, ancak `handleApprove` içindeki bekleyen `await actionsApi.approve(actionId)` (satır 148-159) devam eder ve döndüğünde `toast.success`/`onApproved?.()`/`onClose()` çağrıları unmount olmuş bir bileşen bağlamında çalışır (FHM-003 ile aynı kök neden — mount-guard yokluğu). Kullanıcı ayrıca bir işlem sürerken modalı "iptal ettiğini" düşünebilir ama backend isteği iptal edilmiyor.
Kanıt (satır 176-179, 148-159): yukarıdaki kod blokları.
Aksiyon: `onClick={onClose}` çağrısını `phase !== 'approving'` koşuluyla sınırla; ayrıca approving sırasında ESC/backdrop kapamasını devre dışı bırak.
Önem: Orta · Güven: Dogrulanmali

### [FHM-007] Modal diyalog erişilebilirlik semantiği eksik (role/aria-modal/focus trap)
Sorun: Modal konteyneri (satır 180-183) `role="dialog"`, `aria-modal="true"` veya `aria-labelledby` taşımıyor; açılışta odak modala taşınmıyor (ör. kapat butonuna veya başlığa `autoFocus`/`ref.focus()` yok) ve tab tuşuyla odak modal dışına kaçabilir (focus trap yok). Ekran okuyucu kullanıcıları için bu bir "3-Ufuklu Karar Masası" diyaloğu olarak duyurulmuyor.
Kanıt (satır 180-183):
```
<div
  className="card p-6 w-full sm:max-w-4xl max-h-[90vh] overflow-y-auto"
  onClick={(e) => e.stopPropagation()}
>
```
Aksiyon: Dış `div`'e `role="dialog"` `aria-modal="true"` `aria-labelledby="horizons-modal-title"` ekle, başlık `h3`'e (satır 189) o id'yi ver; açılışta bir odaklanabilir elemana (ör. kapat butonu) `useRef` + `useEffect` ile focus ver; Tab döngüsünü modal içinde tut.
Önem: Orta · Güven: Kesin

### [FHM-008] Küçük dokunma hedefleri — frame toggle ve kapat butonu 44px altı
Sorun: Kapat butonu `!p-1.5` + `w-4 h-4` ikon (satır 227-233) ve frame toggle butonları `px-3 py-1.5` metin boyutunda (satır 204-226) — ikisi de tipik olarak ~28-32px yüksekliğinde, WCAG 2.5.5 / mobil dokunma hedefi önerisi olan 44x44px'in altında kalıyor. Mobil kullanım (D1 hedefi, wave-2 roadmap) için sürtünme yaratır.
Kanıt (satır 204-233): yukarıdaki buton blokları.
Aksiyon: Mobilde `min-h-11 min-w-11` (44px) sağlayacak padding/`touch-target` utility ekle veya tıklanabilir alanı `p-2.5`+ ile büyüt.
Önem: Düşük · Güven: Dogrulanmali

### [FHM-009] `actionId` boş/undefined iken simülasyon isteği yine de tetikleniyor
Sorun: `isOpen` true olduğunda `runSimulation()` doğrudan çağrılıyor (satır 123-133), `actionId`'nin dolu olup olmadığı kontrol edilmiyor. Parent, `isOpen`'ı `actionId` set edilmeden önce true yaparsa (örn. state güncellemeleri aynı render'da senkron yapılmazsa), `simulationApi.run(undefined)` gibi geçersiz bir istek backend'e gider ve kullanıcıya "Simülasyon motoru cevap veremedi" gibi yanıltıcı bir hata gösterilir.
Kanıt (satır 123-133):
```
useEffect(() => {
  if (!isOpen) { ...; return; }
  runSimulation();
  // eslint-disable-next-line react-hooks/exhaustive-deps
}, [isOpen, actionId]);
```
Aksiyon: `if (!isOpen || actionId == null) { ...; return; }` guard'ı ekle.
Önem: Düşük · Güven: Dogrulanmali

### [FHM-010] Bilinmeyen ufuk etiketi için sessizce T+0 meta'sına düşülüyor
Sorun: `HORIZON_META.find(m => m.label === snap.label) || HORIZON_META[0]` (satır 268) backend yeni bir ufuk etiketi (ör. `T+180`) eklerse veya `snap.label` beklenmedik bir değer taşırsa, hatayı yutup sessizce "T+0 / Bugün" ikonunu ve rengini kullanıcıya gösterir — yanlış zaman çerçevesi izlenimi yaratabilir.
Kanıt (satır 267-272):
```
const meta = HORIZON_META.find(m => m.label === snap.label) || HORIZON_META[0];
```
Aksiyon: Eşleşme bulunamazsa nötr bir fallback meta (`sublabel: snap.label` kullanan jenerik ikon) tanımla, T+0'ın border/renklerini fallback olarak kullanma.
Önem: Düşük · Güven: Dogrulanmali

### [FHM-011] `useToast` import yolu kendi dizinine dolaylı referans veriyor
Sorun: Dosya zaten `frontend/src/components/` içinde iken `import { useToast } from '../components/Toast.jsx';` (satır 10) bir üst dizine çıkıp tekrar `components/` klasörüne geri dönüyor. İşlevsel bir hata değil (doğru dosyaya çözümleniyor) ama kopyala-yapıştır kalıntısı izlenimi veriyor ve dosya taşınırsa/yeniden adlandırılırsa kırılgan.
Kanıt (satır 10): `import { useToast } from '../components/Toast.jsx';`
Aksiyon: `import { useToast } from './Toast.jsx';` şeklinde sadeleştir.
Önem: Düşük · Güven: Kesin
