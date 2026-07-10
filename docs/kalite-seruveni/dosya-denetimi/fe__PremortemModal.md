# Denetim: frontend/src/components/PremortemModal.jsx

### [FPM-001] Escape keydown listener isOpen kontrolu olmadan her zaman aktif
Sorun: 29-33. satirdaki useEffect, bagimlilik dizisinde sadece `[onClose]` var; `isOpen`e bakmiyor. React hook kurallari geregi bu effect, bilesen mount edildigi surece (modal kapali gorunse bile, ust bilesen `isOpen={false}` ile PremortemModal'i mount tutuyorsa) window'a keydown listener ekliyor ve her Escape basisinda `onClose()` cagiriyor — modal gorunmuyor olsa dahi.
Kanit (satir 29): `useEffect(() => { const handler = (e) => { if (e.key === 'Escape') onClose(); }; window.addEventListener('keydown', handler); return () => window.removeEventListener('keydown', handler); }, [onClose]);`
Aksiyon: Effect govdesine `if (!isOpen) return;` ekle veya bagimlilik dizisine `isOpen` ekleyip erken cikis yap; boylece modal kapaliyken global Escape yakalanmasin.
Onem: Yuksek · Guven: Kesin

### [FPM-011] "Vazgeç (Reddet)" butonu 'approving' fazinda hala aktif — cift istek riski
Sorun: `canAct = phase === 'success' || phase === 'approving'` (satir 85). Reddet butonu `disabled={!canAct}` kullaniyor (satir 198), yani `approving` sirasinda da tiklanabilir kaliyor. Kullanici "Yine de Onayla"ya bastiktan hemen sonra (approve API cevap vermeden) "Vazgeç (Reddet)"e basarsa, ayni actionId icin `actionsApi.approve` ve `actionsApi.reject` es zamanli tetiklenir — backend'de ayni PendingAction icin celisen iki durum guncellemesi yarisina yol acabilir.
Kanit (satir 196-202): `<button onClick={handleReject} disabled={!canAct} ...>Vazgeç (Reddet)</button>` — approve butonundaki gibi `phase === 'approving'` kontrolu yok.
Aksiyon: Reddet butonuna da `disabled={!canAct || phase === 'approving'}` uygula.
Onem: Yuksek · Guven: Kesin

### [FPM-002] runPremortem icin race condition / iptal mekanizmasi yok
Sorun: 36-45. satirdaki useEffect `actionId` degisince `runPremortem()`i tekrar cagiriyor ama onceki cagriyi iptal etmiyor (AbortController veya "ignore" flag yok). Modal acikken `actionId` prop'u hizla degisirse (ornegin kullanici farkli bir aksiyonu hemen ardindan onaylamaya calisirsa), once baslayan istek daha gec sonuclanirsa `setResult`/`setPhase('success')` ile yeni actionId'nin ekranini eski/yanlis veriyle ezebilir.
Kanit (satir 47-58): `const runPremortem = async () => { setPhase('loading'); ... const res = await premortemApi.run(actionId); setResult(res); setPhase('success'); ... }` — closure'daki `actionId` istek baslarken sabitlenir, cevap gecikirse guncel prop ile karsilastirma yapilmaz.
Aksiyon: Effect icinde bir `let cancelled = false;` bayragi tanimla, cleanup'ta `cancelled = true` yap, `then`/`catch` icinde `if (cancelled) return;` kontrolu ekle.
Onem: Orta · Guven: Dogrulanmali (gercek etkisi actionId'nin modal acikken degisip degismedigine bagli)

### [FPM-003] Modal'da erisilebilirlik (a11y) semantigi eksik
Sorun: Kok container (satir 88-95) `role="dialog"`, `aria-modal="true"`, `aria-labelledby` gibi ozniteliklere sahip degil; ayrica modal acildiginda ilk odaklanabilir elemana focus verilmiyor ve kapanista tetikleyici elemana odak geri donmuyor (hicbir `useRef`/focus-trap kodu yok). Ekran okuyucu kullanicilari icin bu bir dialog oldugu anlasilmaz ve klavye kullanicilari modal disina tab ile kacabilir.
Kanit (satir 88-95): `<div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center px-4 animate-fade-in" onClick={onClose}> <div className="card p-6 ..." onClick={(e) => e.stopPropagation()}>`
Aksiyon: Dis konteynere `role="dialog" aria-modal="true" aria-labelledby="premortem-title"` ekle, basligi `id="premortem-title"` ile isaretle; acilista `useRef` + `useEffect` ile ilk odaklanabilir elemana (or. kapat butonu) focus ver, kapanista tetikleyici elemani geri odaklamayi degerlendir.
Onem: Yuksek · Guven: Kesin

### [FPM-005] Kapat (X) butonunda aria-label yok, sadece title
Sorun: 109-111. satirdaki kapat butonu yalnizca `title="Kapat"` kullaniyor; `aria-label` yok. `title` ozniteligi ekran okuyucular tarafindan tutarli sekilde anons edilmez (destek degiskendir), ikon-only butonlarda `aria-label` standart pratiktir.
Kanit (satir 109): `<button onClick={onClose} className="btn btn-ghost btn-icon !p-1.5 flex-shrink-0" title="Kapat"> <X className="w-4 h-4" /> </button>`
Aksiyon: `aria-label="Kapat"` ekle (title kalabilir, tooltip icin).
Onem: Orta · Guven: Kesin

### [FPM-006] result.scenarios uzerinde null/array guard yok
Sorun: `phase === 'success'` oldugunda `result` var kontrolu yapiliyor (satir 138) ama `result.scenarios`in bir dizi oldugu varsayiliyor; API beklenmedik bir sekilde `scenarios` alanini icermeyen veya `null` doner bir govde geri getirirse `.map` cagrisi TypeError firlatir ve bilesen crash olur (React error boundary yoksa beyaz ekran).
Kanit (satir 140): `{result.scenarios.map((s) => { ... })}`
Aksiyon: `(result.scenarios ?? []).map(...)` kullan veya `runPremortem` icinde `res.scenarios` yoksa `error` fazina dus.
Onem: Orta · Guven: Dogrulanmali (premortemApi.run'in sozlesmesi bu dosyada goruntulenemedi)

### [FPM-010] Backdrop tiklamasi loading/approving fazinda da modali kapatiyor
Sorun: Dis konteynerin `onClick={onClose}` (satir 90) her fazda calisiyor; `phase === 'loading'` iken (premortem uretimi surerken) veya `phase === 'approving'` iken (onay istegi ucarken) kullanici yanlislikla arka plana tiklarsa modal aninda kapanir, ancak arka plandaki `runPremortem`/`handleApprove` promise'i hala calismaya devam eder ve sonuclandiginda (ozellikle `handleApprove` basarili olursa) `toast.success` + `onApproved?.()` sessizce tetiklenir — kullanici modali kapatmisken beklenmedik bir toast/durum degisikligiyle karsilasir.
Kanit (satir 88-90): `<div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center px-4 animate-fade-in" onClick={onClose}>`
Aksiyon: `phase === 'loading' || phase === 'approving'` iken backdrop `onClick`i devre disi birak (`onClick={phase === 'loading' || phase === 'approving' ? undefined : onClose}`).
Onem: Orta · Guven: Kesin

### [FPM-008] Kapat (X) ve İptal butonlari 'approving' fazinda devre disi birakilmiyor
Sorun: Ust kapat butonu (satir 109) ve "İptal" butonu (satir 193) hicbir `disabled` kontrolune sahip degil; `phase === 'approving'` iken de tiklanabilir kaliyorlar. Kullanici onay istegi ucarken modali kapatabilir; istek sonuclandiginda arka planda `toast`/`onApproved` yine tetiklenir, kullanici deneyimi tutarsizlasir (bkz. FPM-010 ile ayni kok neden, farkli tetikleyici).
Kanit (satir 109, 193): `<button onClick={onClose} ...>` (X) ve `<button onClick={onClose} className="btn btn-ghost !text-xs">İptal</button>` — ikisi de `disabled` almiyor.
Aksiyon: `phase === 'approving'` iken bu iki butonu da `disabled` yap veya kullaniciya "istek devam ediyor" uyarisi goster.
Onem: Dusuk · Guven: Dogrulanmali

### [FPM-004] exhaustive-deps lint kurali bastiriliyor
Sorun: 44. satirda `eslint-disable-next-line react-hooks/exhaustive-deps` ile `runPremortem` bagimliligi bilinçli disarida birakiliyor. Su an `runPremortem` her render'da yeniden tanimlandigi ve closure'i guncel `actionId`'yi yakaladigi icin fonksiyonel bir hataya yol acmiyor, ancak bu pattern ileride `runPremortem` icine ek state/prop closure'i eklenirse (ornegin bir `retryCount` state'i) stale closure riskini sessizce gizler; lint kurali bu sinifi hatalari yakalamak icin var.
Kanit (satir 43-45): `runPremortem(); // eslint-disable-next-line react-hooks/exhaustive-deps }, [isOpen, actionId]);`
Aksiyon: `runPremortem`i `useCallback(() => {...}, [actionId])` ile sarip bagimlilik dizisine ekle, boylece disable-line kaldirilabilir.
Onem: Dusuk · Guven: Dogrulanmali

### [FPM-007] Senaryo key'i backend id'sinin varligina/tekilligine kosulsuz guveniyor
Sorun: 144. satirda `key={s.id}` kullaniliyor; `s.id` dogrulanmadan (bos string/undefined/duplicate olabilecegi) React key olarak kullaniliyor. Backend sozlesmesi bu dosyada dogrulanamadi; eger `id` alani eksik veya senaryolar arasinda tekrar ederse React key warning ve potansiyel yanlis DOM diffing (yanlis senaryonun stilinin/badge'inin baska senaryoya sizmasi) olusabilir.
Kanit (satir 140-146): `{result.scenarios.map((s) => { const colors = PROB_COLORS[s.probability_label] || PROB_COLORS.orta; return (<div key={s.id} ...>`
Aksiyon: Backend'in `id` alanini garanti tekil urettigi dogrulanamiyorsa `key={s.id ?? index}` gibi bir fallback yerine, `id` eksikse `error` fazina dusecek bir validasyon eklemek daha guvenli olur.
Onem: Dusuk · Guven: Dogrulanmali

### [FPM-009] Bilesen unmount olursa devam eden async cagrilar icin iptal/temizlik yok
Sorun: `runPremortem` (satir 47-58) ve `handleApprove` (satir 60-71) icindeki `await` sonrasi `setState` cagrilari, bilesen ust bilesen tarafindan tamamen unmount edilirse (sadece `isOpen=false` degil, DOM'dan tamamen kaldirilirsa) calismaya devam eder. React 18 artik bu durumda console warning basmiyor ama gereksiz state guncellemesi ve `toast.success`/`onApproved?.()` gibi yan etkilerin unmount sonrasi tetiklenmesi riski var.
Kanit (satir 51-53, 63-66): `const res = await premortemApi.run(actionId); setResult(res); setPhase('success');` / `const res = await actionsApi.approve(actionId); toast.success(...); onApproved?.(actionId, res); onClose();`
Aksiyon: Bir `isMountedRef`/AbortController ile unmount sonrasi state guncellemelerini ve yan etkileri bastir.
Onem: Dusuk · Guven: Dogrulanmali
