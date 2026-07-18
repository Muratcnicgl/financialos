# Denetim: frontend/src/components/HelpModal.jsx

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [FHLP-001] Yardim metni ile kisayol listesi tutarsiz (stale copy)
Sorun: Alt bilgi metni kullaniciya "Cmd+1..6 -> her zaman aktif" diyor, ama SHORTCUTS listesinde Cmd/Ctrl+7 (Raporlar) da tanimli. Raporlar sekmesi eklenirken bu aciklama satiri guncellenmemis.
Kanit (satir 59, karsilastir satir 12): `Y/N/E -> input disindayken bekleyen aksiyona uygulanir · Cmd+1..6 -> her zaman aktif` vs `{ key: 'Cmd/Ctrl + 7', label: 'Raporlar' }`
Aksiyon: Metni "Cmd+1..7" olacak sekilde guncelle, ya da SHORTCUTS uzerinden dinamik aralik uret (orn. min/max key numarasini listeden turet) ki gelecekte tekrar unutulmasin.
Onem: Orta · Guven: Kesin

### [FHLP-002] Modal'da erisilebilirlik (dialog) semantigi eksik
Sorun: Dis kapsayici div (satir 30) ve ic kart (satir 34) icin `role="dialog"`, `aria-modal="true"`, `aria-labelledby` (baslikla eslesen id) tanimlanmamis. Ekran okuyucu kullanicilari bunun bir modal oldugunu ve baslik/icerik iliskisini algilayamaz.
Kanit (satir 30-39): `<div className="fixed inset-0 z-50 ..." onClick={onClose}> ... <h3 className="font-semibold">Klavye Kısayolları</h3>`
Aksiyon: `role="dialog"`, `aria-modal="true"`, `aria-labelledby="help-modal-title"` ekle; h3'e `id="help-modal-title"` ver.
Onem: Yuksek · Guven: Kesin

### [FHLP-003] Odak yonetimi yok (initial focus / focus trap)
Sorun: Modal acildiginda hicbir elemana programatik odak verilmiyor (useRef + focus() veya autoFocus yok) ve Tab tusu ile odak modal disina (arka plandaki sayfaya) kacabilir. Klavye/ekran okuyucu kullanicilari icin standart modal davranisi (odagin modal icine hapsedilmesi) saglanmamis.
Kanit (satir 22-27): `useEffect(() => { const handler = (e) => { if (e.key === 'Escape') onClose(); }; ... }, [onClose]);` — sadece Escape isleniyor, focus trap/initial focus mantigi yok.
Aksiyon: Acilista kapatma butonuna veya modal konteynerine focus() uygula; Tab/Shift+Tab ile odagi modal icindeki odaklanabilir elemanlarla sinirla (basit bir focus-trap veya `inert` ile arka plani disla).
Onem: Yuksek · Guven: Kesin

### [FHLP-004] Kapat butonu dokunma hedefi 44px altinda kalabilir
Sorun: Kapat butonu `btn btn-icon !p-1.5` sinifiyla 4px'lik ikon (w-4 h-4 = 16px) + 1.5 birim (6px) dolgu kullaniyor; toplam gorsel hedef yaklasik 28px civarinda, mobilde onerilen 44x44px dokunma hedefinin altinda kalabilir (`btn`/`btn-icon` global tanimina bagli, kesin px degeri bu dosyadan dogrulanamiyor).
Kanit (satir 40): `<button onClick={onClose} className="btn btn-ghost btn-icon !p-1.5" title="Kapat">`
Aksiyon: Mobilde min `w-11 h-11` (44px) saglayacak sekilde `!p-1.5` yerine daha genis dolgu veya `min-w-[44px] min-h-[44px]` ekle; global `btn-icon` tanimi zaten yeterliyse bu bulguyu dogrula.
Onem: Orta · Guven: Dogrulanmali

### [FHLP-005] Alt bilgi metni dusuk kontrastli renk kullaniyor
Sorun: `text-zinc-400` acik gri, hem light hem dark temada govde metnine gore dusuk kontrastli olabilir; WCAG AA (4.5:1) esigini karsilayip karsilamadigi bu dosyadan dogrulanamiyor, tema/arkaplan rengine bagli.
Kanit (satir 58): `<p className="text-[11px] text-zinc-400 mt-4">`
Aksiyon: Kontrasti `text-zinc-500 dark:text-zinc-400` gibi biraz daha koyu bir tonla veya gercek kontrast olcumuyle dogrula.
Onem: Dusuk · Guven: Dogrulanmali

### [FHLP-006] onClose prop'u icin savunma kontrolu yok
Sorun: `onClose` prop olarak zorunlu varsayiliyor; hicbir yerde tip kontrolu veya varsayilan deger yok. Eger komponent yanlislikla `onClose` olmadan render edilirse hem `useEffect` icindeki handler hem de tiklama/kapama butonlari `onClose()` cagirirken TypeError firlatir.
Kanit (satir 22, 24, 32, 40): `export default function HelpModal({ onClose }) {` ... `onClose()` cagrilari
Aksiyon: PropTypes ekle veya en azindan `onClose?.()` seklinde guvenli cagrim kullan; bu tur UI bilesenlerinde proje genelinde PropTypes/TS kullanilmiyorsa bu bulgu dusuk oncelikli kabul edilebilir.
Onem: Dusuk · Guven: Dogrulanmali
