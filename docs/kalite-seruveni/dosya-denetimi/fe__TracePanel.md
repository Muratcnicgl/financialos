# Denetim: frontend/src/components/TracePanel.jsx

> **M86 güncellik:** 🟢 GÜNCEL — 6 bulgu açık


> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [FTP-001] trace.steps undefined/null ise crash riski
Sorun: Backend `/api/coach/trace/{memoryId}` yanitinda `steps` alani eksik veya null donerse (orn. eski kayit, kismi hata, migration edge-case), `trace.steps.length` cagrisi TypeError firlatir ve tum Coach paneli beyaz ekrana duser (ust seviyede Error Boundary yoksa).
Kanit (satir 99, 105): `trace && trace.steps.length === 0` ve `trace && trace.steps.length > 0` — `trace` truthy kontrolu var ama `trace.steps` icin yok.
Aksiyon: `trace && Array.isArray(trace.steps) && trace.steps.length === 0` seklinde defansif kontrol ekle, ya da `(trace?.steps ?? []).length` kullan.
Onem: Yuksek · Guven: Dogrulanmali (backend kontratini garanti eden bir TS/Pydantic response tipi goremedim, ancak defansif kod eksik oldugu kesin)

### [FTP-002] Fetch tamamlanmadan unmount olursa "state update on unmounted component" sizintisi
Sorun: `handleToggle` icindeki `fetchTrace(memoryId)` cagrisi cleanup/abort/mounted-ref mekanizmasi olmadan calisiyor. `App.jsx`'te tab degisimi Coach panelini `activeTab === 'coach' && <Coach />` seklinde kosullu render ediyor (bkz. App.jsx:201) — yani sekme degistirmek Coach'u tamamen unmount eder. Kullanici trace panelini acip (fetch baslar) fetch tamamlanmadan baska sekmeye gecerse, `setLoading`/`setTrace`/`setError` unmount olmus bilesen uzerinde cagrilir.
Kanit (satir 44-60): `setLoading(true)` ... `await fetchTrace(memoryId)` ... `setTrace(data)`/`setError(...)`/`setLoading(false)` — hicbiri mount durumunu kontrol etmiyor, AbortController/cleanup yok.
Aksiyon: `useRef` ile mounted flag tut (veya AbortController) ve unmount sonrasi state guncellemelerini atla; ya da fetch mantigini `useEffect` + cleanup fonksiyonuna tasi.
Onem: Orta · Guven: Dogrulanmali (React 18'de bu artik sert hata degil, sadece console warning'e donusebilir, ama pattern hatali)

### [FTP-003] memoryId degisirse component state'i sifirlanmiyor (index-key ile birlesince stale trace riski)
Sorun: TracePanel `isOpen`/`trace`/`error` state'ini sadece ilk mount'ta baslatir; `memoryId` prop'u degisirse (ayni component instance'i farkli bir mesaj icin yeniden kullanilirsa) eski `trace` verisi ekranda kalir, cunku `memoryId` degisimini dinleyen bir `useEffect` yok. Cagiran taraf `Coach.jsx:450`'de `messages.map((m, i) => <Message key={i} .../>)` ile **index-key** kullaniyor — mesaj listesi herhangi bir noktada baslangicdan silme/yeniden siralama gorurse (bugun icin append-only olsa da), React ayni index'teki TracePanel instance'ini farkli bir `memoryId` ile yeniden kullanir ve eski `trace`/`isOpen` state'i yanlis mesajin altinda gorunur.
Kanit (satir 34-37): `const [isOpen, setIsOpen] = useState(false); const [trace, setTrace] = useState(null); ...` — memoryId'ye baglanan bir reset effect'i yok.
Aksiyon: `useEffect(() => { setIsOpen(false); setTrace(null); setError(null); }, [memoryId])` ekle; asil kalici cozum Coach.jsx'te `key={i}` yerine `key={m.coachMemoryId ?? m.id ?? i}` kullanmak (bu dosyanin disinda, sadece baglam icin not).
Onem: Orta · Guven: Dogrulanmali (bugun icin mesaj listesi append-only gorunuyor, ama TracePanel kendi basina bu varsayima guvenmemeli)

### [FTP-004] Detay satirlarinda object/non-string deger React child hatasi verebilir
Sorun: `detailsRows` icine `step.observation`, `step.inference`, `step.action_input_json` gibi alanlar dogrudan JSX child olarak basiliyor (`<span>{value}</span>`). Backend bu alanlardan birini string yerine JSON object olarak donerse ("Araç girdisi" gibi bir alan `action_input_json` adindan JSON string bekleniyor ama parse edilmemis/edilmis karisikligi olabilir), React "Objects are not valid as a React child" hatasi firlatir ve panel crash olur.
Kanit (satir 152-157, 211): `if (step.action_input_json) detailsRows.push(['Araç girdisi', step.action_input_json]);` ve `<span ...>{value}</span>`.
Aksiyon: Deger string degilse `JSON.stringify(value)` ile guvenli hale getir veya backend response tipini string olarak garanti et.
Onem: Dusuk · Guven: Dogrulanmali (alan adi `_json` suffix'i tasidigi icin muhtemelen zaten string, ama garantisi kodda yok)

### [FTP-005] Kucuk dokunma hedefleri (mobil erisilebilirlik)
Sorun: Ana toggle butonu (satir 65-72) `text-xs` + kucuk ikon (`w-3.5 h-3.5`) ile, ek dikey padding olmadan render ediliyor; benzer sekilde `TraceStep` butonu (satir 163-170) `px-2 py-1.5 text-xs` kullaniyor. Ikisi de WCAG 2.5.5 / mobil 44x44px dokunma hedefi esigine gorunurde ulasmiyor. Proje roadmap'inde D1 (mobil gorunum) hedefi acik oldugu icin bu onem kazaniyor.
Kanit (satir 65-72, 163-170): ek `py-` veya `min-h-` degeri yok, sadece text/ikon boyutuna dayanan dogal yukseklik.
Aksiyon: Butonlara `min-h-[44px]` (veya en azindan `py-2.5`) ekle ya da mobilde daha genis tiklanabilir alan icin invisible padding kullan.
Onem: Dusuk · Guven: Dogrulanmali (gorsel olcum yapilmadi, sadece class'lardan tahmin)

### [FTP-006] Confidence esikleri ve renk/etiket eslemesi magic number
Sorun: `ConfidenceBadge` icindeki `0.80` ve `0.50` esikleri (satir 233, 237) kod icinde sabit yazili, adlandirilmis bir sabit/env degeri degil. Islevsel bir bug degil ama tekrar kullanim/degistirilebilirlik acisindan zayif nokta; ayni esikler baska bir yerde tekrar gerekirse senkron kalmasi garanti degil.
Kanit (satir 233-244).
Aksiyon: Dosya basina `const CONFIDENCE_HIGH = 0.80; const CONFIDENCE_MEDIUM = 0.50;` seklinde adlandirilmis sabitlere cikar.
Onem: Dusuk · Guven: Kesin
