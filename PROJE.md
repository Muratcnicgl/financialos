# PROJE.md

FinancialOS — kişisel finansal işletim sistemi. Tek-kullanıcı MVP (Murat İçgil). Backend FastAPI + SQLite + SQLAlchemy 2.x + Pydantic V2, frontend React + Vite + Tailwind. UI ve alan adları (`nakit_kasa`, `kart_borcu` vb.) **Türkçe korunur** — backend'den frontend'e mapping yok.

## Güncel Durum (baseline)

> **GÜNCEL BASELINE — 2 Eylül 2026 (Wave-K, K0-K3).** Aşağıdaki tarihsel sayılar BAYAT.
> Koşum (`pytest tests/ -q`, kaynak dosyalara eşzamanlı dokunulmadan, 5:41):
> **3304 passed, 18 skipped, 1 failed.** Tek kırmızı KOD DEĞİL, ORTAM:
> `test_multi_asset::test_yfinance_client_bos_none` — Windows **Smart App Control** açık
> (`VerifiedAndReputablePolicyState=1`) ve pandas'ın imzasız `timestamps...pyd` dosyasını
> engelliyor. Aynı ilke `_greenlet...pyd` ve `computer-control-mcp.exe`'yi de kesiyor
> (CodeIntegrity Id 3033/3077, 20 Ağu-2 Eyl arası 36 olay). SAC tek yönlüdür — kapatılırsa
> Windows yeniden kurulmadan geri açılamaz; karar kullanıcınındır, asistan değiştirmez.
> **GÜNCEL (2 Eyl, ikinci tur): 3349 passed, 18 skipped, 0 failed.** Smart App Control
> kullanıcı tarafından KAPATILDI → pandas/greenlet `.pyd` engeli kalktı, `test_multi_asset`
> yeşile döndü. Önceki temiz koşum (1 Eyl): 3272 passed.
>
> **BU TURDA BEŞ KAPI DEĞİŞİKLİĞİMİ REDDETTİ, BEŞİ DE HAKLIYDI** — ölçüm fixture'ını
> `app/`e koymuştum (kişisel veri + prod imajı), `STOPAJ_*` env adlarını `f"..."` ile
> türetmiştim (operatör `grep`leyemez), `bayat_mi` sunucu gününe düşüyordu, boş-durum
> frontend fixture'ı bayatlamıştı, para birimi sabiti sayılmıştı. İkisinde muafiyet yazmak
> mümkündü; yazılmadı — **bir ratchet kapısına doğru cevap çoğu zaman tavanı yükseltmek
> değil, ihtiyacı ortadan kaldırmaktır** (gün zorunlu parametre oldu; env adları
> `money_format.VARSAYILAN_KOD`a hizalanıp `STOPAJ_TRY_*` oldu).
>
> **BUG #317** — `.env`de `LLM_MODEL=  # not` yazımında python-dotenv YORUMU DEĞER sanıyor
> (boş değerde yorum ayıklanmıyor). Aynı tuzak `.env.example`de **13 değişkende** vardı,
> `ANTHROPIC_API_KEY` dahil — yani şablonu kopyalayan herkeste. Düzeltince OpenRouter altın
> sette **%0 → %76,0, GEÇERLİ**. Ders: *model adı çürüdüğünde belirti daima "sağlayıcı bizi
> istemiyor" biçiminde okunur* (BUG #315'ten sonra ikinci kez).
>
> **Sağlayıcılar (ölçüldü):** OpenRouter ✅ tek geçerli altın ölçüm · Groq canlı ama altın
> istek **12.954 tok > 8.000 TPM** · Gemini 429 · Cerebras 402 / Anthropic 400 (para).
>
> **QA BULGUSU — MOBİL LANDSCAPE (kapı kör noktası).** `tema-mobil.spec.js` mobil yüzeyi
> ölçüyordu ama YALNIZ 390x844 portrait; "mobil ölçüldü" cümlesi yarımdı. Landscape'te
> viewport 390 · kabuk 114 · içeriğe kalan **236px**. Üç defekt bulundu ve düzeltildi:
> (1) iki yüzer düğme sağ kenarda 120px şerit = içeriğin **%51'i** → Gelir "Yeni", Bütçe
> 5×"Sil"+3×"Gizle" örtülüydü; kısa viewport'ta stack yataya döndü, **%51 → %19**,
> örtülme 8→0. (2) Koç mesaj listesi **32px'e çöküyordu** → 126px. (3) `EmptyState
> fullHeight` `h-full`+`justify-center` ile içeriği yukarı taşırıyordu → `min-h-full`.
> Yeni kapı `frontend/e2e/mobil-landscape.spec.js`: **yüzer katman bütçesi (tavan %25,
> ratchet)** + ulaşılabilirlik + taşma + konsol. Dokunma hedefi ölçütü BİLEREK yok —
> portrait kapısına ait ve iki yazılı istisnası var; kopyalayınca 26 yanlış pozitif verdi.
> **e2e 8 passed · frontend 214 passed.**
>
> **K-B GÜN SONU (2 Eyl, 3 koşum — TEK KOŞUM GÜRÜLTÜLÜDÜR):** altın set
> **kriter min %88,0 / medyan %88,0 / maks %96,0 · muhakeme min 4/6 / medyan 4/6 / maks 6/6.**
> Sabahki taban **1/6** idi. Senaryo başına: G1 3/3 · G2 3/3 · G4 3/3 · G6 3/3 kararlı,
> G3 1/3 · G5 1/3 kararsız. Kazanımların hiçbiri prompt'a satır eklemekten gelmedi
> (K-KURAL 5); dördü de ÜRÜN düzeltmesi: **#317** (.env yorumu model adı sanıldı),
> **#318** (erken kapama sayısal alana → G1'in 31.115,44 TL'lik yanlış tavsiyesi kapandı),
> **#319** (nakit takvimi parçalıydı, koç gelen parayı gider sayıyordu),
> **#320** (yatırımda bekleyen nakit ayrı ve etiketli kalem; emanet hariç).
> **Metodoloji dersi:** aynı kodla %88 → %84 → %80 ölçüldü; örneklem büyüklüğü
> belirtilmeyen bir oran bir iddiadır, ölçüm değil.
>
> **GÜNCEL BASELINE — 4 EYLÜL 2026 (akşam, Wave-Y sonrası). Süit 3525 passed ·
> 18 skipped · 0 failed** (7:37) · coverage **%94** · kalite kapısı 296 · ölü kod 0.
> **AKTİF HAT: Wave-Y (yayın) — tek doğruluk kaynağı `docs/kalite-seruveni/wave-y-ledger.md`.**
> Wave-K (koç hattı) Y8 kapanana kadar **DONDURULDU**.
>
> **Wave-Y'de kapananlar:** Y1 canlı drift **0** (BUG #339: güncelleme adımı kullanılan
> yolda yoktu — `deploy.sh` Docker içindi; `deploy/windows/guncelle.ps1` yazıldı ve
> KULLANIM-GATE damga eşitliğini ölçüyor) · Y2 kesinti körlüğü bitti (BUG #342 **ölü adam
> anahtarı**: makine ping atar, ping kesilirse alarm çalar — *sessizlik, her şeyin yolunda
> olduğunun değil ALARMIN KENDİSİDİR*; iki halka da canlı kanıtlandı) · Y0 **B0 kararı
> 24 gün sonra kapandı** (ADR-057: kendi makine + Cloudflare Tunnel + satın alınmış alan
> adı; B'ye geçiş tetikleyicileri şimdiden yazılı) · Y5 defter senkronu (MCP defteri
> **kapatıldı** — hiç koşulmayacak bir flush için yakalama yapıyordu) · Y6 **beş yeni ADR (057-061)** — *ölçülen toplam: 58 benzersiz karar / 60 belge; gün içinde yazılan "61" indeks dosyasını da sayıyordu* ·
> Y7 vitrin üreticisi (allowlist) + kapısı.
>
> **BEKLEYEN (üçü de insan-kapısı):** alan adı satın alma (Y3'ün tamamı buna bağlı) ·
> vitrin için boş public depo · davetlilerden geri bildirim (Y4).
>
> **BU TURUN YENİ DEFEKTLERİ:** `#339` güncelleme adımı yoktu · `#340` düzeltme veriye
> bağlıydı, verisi olmayan kullanıcıda ürün hâlâ varsayıyordu · `#341` deploy betiğinin
> çıkış kodu okunamıyordu (üç tur, üçü de "çocuk süreç ebeveynin tanıtıcısını miras
> alıyor") · `#342` kesinti körlüğü · `#343` rapor diskte duran gerçek ölçümü "ölçüm yok"
> sanıyordu (BOM) · `#344` **onarım ölçümü yiyordu** — kendi kendini iyileştiren sistem
> kendi arıza kaydını siliyordu.
> Kalite kapısı 296 (63/63) · ölü kod 0 · belge denetimi ve temiz-DB göç kilidi geçiyor.
> **Kapalı beta AYAKTA.** Tek doğruluk kaynağı: `masterprompt-koc.md` §10 başındaki
> ⏸️ KALDIĞIMIZ YER (4 Eylül).
>
> **BU TUR GERÇEK KULLANIMDAN DOĞDU (11 defekt).** Kullanıcı bankalardan güncel verisini
> çekmek istedi; o iş sırasında ürünün üç yerde yalan söylediği ölçüldü ve canlı sistem
> bir kez kurtarıldı:
> **#326** göç adımı betanın KOŞTUĞU yolda yoktu → beta **24,5 saat kapalıydı** (45
> başarısız deneme; adım `systemd` ve `Docker` yollarında vardı, ikisi de kullanılmıyor) ·
> **#327** `balance`ın tanımı yanlış yazılmıştı → taksit-toplamı yorumu 34.500 TL'lik
> krediyi **102.266 TL borç** gösteriyordu · **#330** kart asgari oranı koda gömülüydü
> (%25; bankanın gerçeği %20 → kullanıcıya **411 TL fazla** söylendi) · **#331** karta
> yazılan gider nakit çıkışı sayılıyordu → sıkışık kullanıcıya **olmayan bir açık**
> gösteriliyordu · **#332** "hesabı o an belli olur" seçeneği yoktu, ürün varsayıyordu ·
> **#333** koçtan aritmetik bekleniyordu · **#328** kesinti sessiz kalıyordu ·
> **#329** CI kırmızıydı ama açık yoktu (npm registry 503, 7 dk deneyip düştü).
>
> **KOÇ ÖLÇÜMÜ (canlı, öncesi/sonrası, aynı soru ve sağlayıcı):** *"Bu ay param yeter mi?"*
> ÖNCE 8.800 TL'lik belirsiz harcamadan hiç bahsetmedi ve "yeter" dedi; SONRA tehditlere
> yazdı ve **sordu**. Grounding **13/13**, sapmaların hepsi ≤%0,02. Hiçbiri prompt'a satır
> eklenerek yapılmadı (K-KURAL 5).
>
> **METODOLOJİ:** bir ratchet kapısı bu turda ÜÇ kez değişikliği reddetti ve üçünde de
> haklı çıktı — tavan değil TASARIM düzeldi. Mutasyon BEŞ kez kapının kendi kör noktasını
> buldurdu. Asistan iki kez bir KOD VARSAYIMINI ölçüm sandı ve kullanıcı düzeltti
> (asgari oran, maaş günü) — *bir sayının nereden geldiğini sormadan onu ölçüm sayma.*
>
> **BUG #323 — ÜRÜN, SÖYLEDİĞİ ŞEYİ YAPMAYI REDDEDİYORDU (3 Eyl 2026).** Kullanıcı
> *"Bugün 500 TL yemek harcadım nakitten"* diyor; harcama **kaydedilmiyor** ve koç
> *"Tarih bilgisi tutarsız… tarih yoksa bugün olarak kaydederim"* cevabını veriyor.
> Kök: BUG #044 koruması "özette tarih var, payload'da yok" durumunu reddeder (amacı
> kaydın sessizce BUGÜNE düşüp kalıcı yanlış gün olması); ama ifade **"bugün"** ise yedek
> değer zaten özetin söylediği gündür → sessiz hata İMKÂNSIZ. Muafiyet dar: özetteki TEK
> tarih ifadesi "bugün" iken. "dün" · "3 Mayıs'ta" · "dün değil bugün" hâlâ reddediliyor.
> Dedektörün sözleşmesi değişmedi. 8 test, **mutasyon 3/4** — biri eşdeğer mutant, bir
> diğeri (payload tarihinin erken dönüşü) **194 testten kaçtı** ve testi kendisi yazdırdı.
> Sebep **ürün koduna DOKUNMADAN** ölçüldü (`AksiyonReddi.__init__` ayrı süreçte geçici
> sarmalandı, 6 denemede bulundu). Süit **3400 passed · 18 skipped · 0 failed**.
>
> **GÜNÜN DESENİ: ÜRÜN, KOÇU DOĞRU DAVRANDIĞI İÇİN CEZALANDIRIYOR.** #322 koç kullanıcının
> söylediğini hatırladığı için, #323 kullanıcının kelimesini tekrarladığı için, `IC_JARGON`
> ise kullanıcının kendi ekranındaki `Reel Bütçe` etiketini kullandığı için düşürüyor —
> üstelik o etiketi koça prompt'un kendisi veriyor (`coach.py:966`) ve yine kendisi
> yasaklıyor (`:327`), arayüz de kullanıcıya öğretiyor (`Cockpit.jsx:312`). Ölçüm:
> üslup düşüşlerinin **%71'i IC_JARGON**, onun da **%85'i "reel bütçe"**. Kararı ürün
> dili yargısı olduğu için **Murat'a bırakıldı** (§8 insan-kapısı).
>
> **K3'ÜN KALAN YARISI SINIFLANDIRILDI — GERÇEK UYDURMA YOK (3 Eyl 2026).** `grounded`
> düşüşlerinin 13'ü de tek tek okundu: **4 türev sayı** (koçun meşru senaryo aritmetiği:
> 9.700 = 11.976 − 2.276 gibi) · **2 kullanıcı beyanı** (BUG #322) · **1 örnekleyici
> yuvarlak sayı** · **0 uydurma.** Yani "zorlama tasarımı" sorusunun cevabı **hiçbiri**:
> bu dedektöre dayanan bir blok, engelleyecek uydurma bulamaz, yalnız koçun matematiğini
> engellerdi. **ASIL BULGU DEDEKTÖRÜN KENDİSİ:** aynı cevapta koçun YANLIŞ hesabı (3.536,
> doğrusu 3.776) alakasız bir kokpit yaprağına (%2 tolerans, `saglikli_borc_hedefi`=3.600)
> denk geldiği için GEÇTİ, doğrusu DÜŞERDİ. **Tesadüf yüzeyi ölçüldü: %10,7** (200.000
> örneklem, 27 yaprak — canlı kokpit daha zengin). Tolerans daraltılmadı (yuvarlanmış
> doğru cevabı düşürürdü, BUG #316 dersi); doğru yön eşleşmeyi izlenebilir kılmak — açık iş.
> **Ders: bir dedektörün BERAATI, mahkûmiyeti kadar ölçülmelidir.**
>
> **BUG #322 — İZİN LİSTESİ MODELİN GÖRDÜĞÜ VERİDEN DARDI.** `chat()` modele son turları
> veriyor, `check_grounding` yalnız O ANKİ mesajı sayıyordu → kullanıcının bir tur önce
> söylediği tutarı **doğru hatırlayan** koç halüsinasyon damgası yiyor ve üretimde güveni
> **0,4'e** düşüyordu. Koçun KENDİ cevapları bilinçli olarak izinli değil (döngüsellik
> yasağı) — ve ürün bunu zaten ihlal ediyordu: iç plan yönlendirmesi (BUG #272) modelin
> çıktısını `role="user"` olarak listeye ekliyor, uydurma sayı kendi kendini aklıyordu.
> 9 test, **mutasyon 5/5** — M1 (rol filtresi) önce HAYATTA KALDI ve kapının kendi kör
> noktasını buldurdu: *bir kapı, sözleşmeyi yazdığı yerde değil ZORLANDIĞI yerde ölçmelidir.*
>
> **ÖLÇÜMÜN KARIŞTIRICISI: `.env` = `fallback`.** Çıplak `eval_runner` koşumu zorunlu
> olarak karışık sağlayıcıdır (Gemini 10 istek/dk; tek koşumda **3 geçiş** ölçüldü).
> Kayıtlı %82,9 davranış tabanı bir kalite ölçümü değil, sağlayıcı karışımı ölçümüymüş:
> **OpenRouter sabit taban medyan %88,6 · `uslup` 13/24 → 18/24.** Kalite karşılaştırması
> artık `--saglayicilar openrouter` ile yapılır; `--dokum` bayrağı TAM cevapları JSON'a yazar.
>
> **K3 ÖNCEKİ TUR — %100 DEĞİL ~%50 (BUG #321).** Davranış setinde `grounded`
> kriteri **0/6** çıkıyordu. Sebep koç değil ÖLÇÜT: `etiketsiz` kuralı bir sayının
> izlenebilir olup olmadığına HİÇ bakmıyordu — koç `"limit 12.000 (%99,8 dolu)"` yazınca
> (12.000 cockpit'te VAR, yalnız etiketsiz) cevap kırmızıya düşüyordu. Düzeltmeden sonra
> **0/6 → 3/6**. BUG #256'nın amacı korundu: uydurma sayı cockpit'te de olmadığı için hâlâ
> yakalanır. Kalan yarının sınıflandırılması açık iş (türev sayı mı, gerçek uydurma mı).
>
> **İSTEK BİLEŞİMİ:** sistem promptu **19.444 kar (%78)**, cockpit bağlamı 5.544 kar;
> 1,93 kar/token. KURAL SIFIR tek başına promptun %32'si — ve `offer_propose=False` iken
> `propose_action` tool listesinde HİÇ YOK (`no_action` 12/12 ölçüldü), yani büyük kısmı
> ölü ağırlık. **Ama kırpma tek başına Groq'u AÇMAZ** (8.000'in altı ~5.000 token indirim
> ister; KURAL SIFIR'ın tamamı 3.258). Kırpma açık iş.
>
> **MANŞET ORAN BİR KARIŞTIRICIDIR:** aynı üç koşumda `grounded` 0/6→3/6 İYİLEŞİRKEN
> manşet %85,7→%82,9 DÜŞTÜ (dokunulmayan `uslup` ekseni, sağlayıcı gürültüsü). Kriter
> başına tablo olmadan yorumlanamaz.
>
> **Stopaj artık kural motorunda** (`app/vergi.py` + `calculate_getiri_esigi`): engel oran =
> en pahalı borcun aylık faizi; ters hesap = eşiği geçmek için gereken brüt yıllık (%4,75/ay
> → **%68,49**). Koç vergi aritmetiği YAPMAZ, okur. Prompt'a tek satır eklenmedi (K-KURAL 5).
>
> Bu turda eklenen beş kapı: `test_saglayici_modeli_kapisi`, `test_prompt_butcesi_kapisi`,
> `test_uslup_zorlama_kapisi`, `test_siz_hitabi_onarim_kapisi`, `test_grounding_ayirac_kapisi`
> (BUG #313, #314, #315, #316) + altıncı kapı `test_altin_senaryo_kapisi` (K-B).
> Tek doğruluk kaynağı: `docs/kalite-seruveni/masterprompt-koc.md` **§9.1** (ondan önce §9.0).
>
> **KOÇ KALİTESİNDE ARTIK İKİ AYRI ORAN VAR — KIYASLANMAZLAR.** Davranış seti (KURAL SIFIR,
> üslup, format) **%80,0 / %82,9**; **ALTIN SET (G1-G6, koçun muhakemesi) %60,0 ve
> `dogru_sonuc` 1/6.** Aradaki uçurum çelişki değil: koç düzgün KONUŞUYOR ama İŞİ yapamıyor.
> Manşet sayımız K0'dan beri birinciydi; "koç %80" denebildiği hâlde koç, iki krediyi
> kapatmak için 79.625,85 TL diyordu (doğrusu 48.510,41) — **31.115,44 TL fazla ödeme
> tavsiyesi**. Altı düşüşün altısı da cevap dökümüyle elle doğrulandı; hiçbiri ölçüt kusuru
> değil. Koşum: `python -m scripts.eval_runner --altin` (`scripts/coach_altin.py`).
> **`grounded` altın sette KULLANILMAZ ve bu kilitli** — erken kapama tutarı veri modelinde
> `notes` METNİ olduğu için doğru cevap "izlenemeyen tutar" damgası yiyor (açık ürün bulgusu).
>
> **DÜZELTİLMİŞ TEŞHİS:** `test_attribution_available_true` 1 Eylül'de kırmızıydı ve
> "önceden girmiş regresyon" diye kaydedilmişti. Gerçek: test `date.today()` kullanıyordu ve
> **yalnız ayın 1'inde** kırılıyordu (o gün bugünün snapshot'ı aynı zamanda referans olur →
> `ref is latest` → `None`). Yani süit **her ay bir gün kırmızıydı ve görünmüyordu** — bu
> baseline'ın "hepsi yeşil" ifadesi o yüzden yanlıştı. Test takvimden bağımsız hâle getirildi,
> ürün davranışı `test_attribution_TAKVIM_semantigi_yazili` ile YAZILI ve mutasyonla kilitli.
>
> **İKİ METODOLOJİ NOTU:** (1) mutasyon testi ile tam süit koşumu AYNI ANDA yapılamaz —
> koşum sürerken kaynak değiştiği için 5s57dk süren bir koşum alakasız bir alanda sahte
> kırmızı verdi. (2) Ayda bir gün görünen bir kırmızı, pratikte görünmez: takvime bağlı
> testler `date.today()` yerine açık tarihle kurulmalı.

- **Test (11 Ağu güncel):** pytest ~3095 passed (BUG #292 kapısı 5 + BUG #289 kapısı 4),
  18 skipped · **frontend 214 vitest** (öğretici 17 + katlanır bölüm 8 yeni) · **e2e 7**
  (BUG #293 ile ölü kapsam testi canlandı). **Süit artık canlı DB'ye BAĞLANAMAZ** (BUG #289:
  conftest `DATABASE_URL`'i geçici dosyaya sabitler; kanıt = tam koşum öncesi/sonrası canlı
  DB parmak izi bit-bit aynı). e2e için `scripts/e2e_izole.py` (ayrı port + ayrı DB — canlı
  beta :8000'de koştuğu için şart). Eski baseline: 3040 passed, 18 skipped (`.\venv\Scripts\python.exe -m pytest tests/ -q`; skip'lerin 8'i Postgres
  gerektiriyor — **CI'da postgres servisiyle GERÇEKTEN koşar**, BUG #238; yerelde `scripts/pg_gate_run.py`) + 175 vitest (frontend) + **6 e2e** (Playwright: M69 kullanım döngüsü + BUG #241 kapanış kanıtı [kimliksizdi, BUG #265'te düzeltildi] + **BUG #265 iki-tema/390px yüzey kapısı**). TOTAL coverage **%94** (27 Ağu 2026, BUG #311 sonrası: 11.360 satır / 698 kapsanmayan = %93,86; aynı gün BUG #308 ölçümü 11.395/728 = %93,61'di — fark ölü kodun silinmesi, önceki "%93 · 9985 satır" ise 6 Ağu'da elle alınmış tek seferlik bir sayıydı ve bayatlamıştı — artık **her CI koşumunda ölçülüyor ve `--cov-fail-under=93` ile korunuyor**, BUG #308). Flaky yok (M90). Mutasyon-testi örneği (M88). **Dual-dialect (Wave-7):** SQLite + PostgreSQL gate'leri (`tests/pg_gate.py` + RLS/Numeric/net-worth/NULL-ordering testleri; postgres yoksa skip). Deterministik (in-memory, FakeProvider) + property-based fuzzing (hypothesis) + `tests/security/` + `tests/auth/` + `tests/test_workspace_*` (M40-M43) + component testleri (M64, @testing-library/react + jsdom). Commit-öncesi test kapısı + MCP-sync (`.githooks/pre-commit` W3-058 + `post-commit` M24).
- **Branch:** `main` (= origin senkron). **Para artık Decimal** — `Numeric(19,4)` canlı DB'de (ADR-030, M5); iç aritmetik Decimal, public sınır `floatify`→float (B1). Canlı DB head **`c3d4e5f8a1b2`** (4 Eyl 2026, ölçüldü) — *önceki kayıt `e7f8a9b0c1d2` diyordu ve **üç göç geride kalmıştı**; bu satır 11 Ağustos'ta doğruydu* (BUG #281, 11 Ağu — `feedback`'e teşhis alanları; önceki
  `d6e7f8a9b0c1` BUG #280 `error_logs.last_istek_id`, ondan önce `c5d6e7f8a9b0` BUG #274, 10 Ağu — `api_call_log`'a `est_cost_usd` + `amac`; canlı defterde 213 satır göç etti: 191 yansıma + 22 koç, hepsi `amac` aldı; önceki `b4c5d6e7f8a9` BUG #264'tü).
- **AKTİF HAT: PUBLISH YOLU (P0-P9) — "Wave" DEĞİL.** Tek doğruluk kaynağı `docs/kalite-seruveni/masterprompt-publish.md`
  **§11.0** ("kaldığımız yer"). Kod tarafında bilinen teknik engel yok; P6-P9 **insan-kapısı** (Oracle VM + domain + canlı
  sırlar). **H4 ve H9 KAPANDI (7 Ağu 2026):** para birimi görüntüleme tek kaynağa indi (BUG #256/ADR-044) ve prompt
  enjeksiyonuna yapı savunması eklendi (BUG #257/ADR-045). **P3.3 onboarding rehberi de KAPANDI (BUG #262,
  7 Ağu):** kart ilk hesap eklenince kayboluyordu ve birincil düğmesi ölü `href="#accounts"` bağlantısıydı;
  adım durumu artık `GET /api/onboarding/rehber` ile backend'de tek kaynak. **P5.5 kapasite sınırları da
  KAPANDI (BUG #263, 7 Ağu):** kapasitenin yalnız dışarı bakan tarafı (Postgres `max_connections`)
  hesaplanmıştı; uygulamanın kendi eşzamanlılığı (iş parçacığı havuzu 40) DB havuzunu (15) kat kat
  aşıyordu → havuz uygulamanın İÇİNDE tükeniyor, `/api/ready` asılıyor, HEALTHCHECK konteyneri
  yeniden başlatıyordu. Tek kaynak `app/capacity.py` (havuz hizalama + yavaş-yol tavanları + açılışta
  fail-fast). **P3.5.3 kategori seti de KAPANDI (BUG #264, 7 Ağu):** kod, bir harcamanın kredi
  kartına yazılıp yazılmayacağını beş sabit Türkçe kategori adına (`_CARD_CATEGORIES`) bakarak
  belirliyordu; kendi kategorisini adlandıran kullanıcıda kural sessizce ölüyor, "market" deyip
  nakit ödeyende ise iki bakiye birden yanlış çıkıyordu. Kategori artık bir KAYIT (`categories`)
  ve karar ADDA değil BAYRAKTA — tek kaynak `app/category_rules.py` (ADR-046). **İKİ TEMA +
  TELEFON YÜZEYİ de KAPANDI (BUG #265 / ADR-047, 7 Ağu):** `darkMode:'class'` iki ayrı sayfa
  üretir ve varsayılan koyudur; hiçbir koşum **açık temayı** ya da **390px genişliği** render
  etmiyordu. Ölçünce dört panel (`Goals`/`DebtStrategy`/`Workspace`/`Login`) tamamen koyu-varsayan
  çıktı → açık temada başlıklar **1.05 kontrastla görünmüyordu**; ters yönde **varsayılan koyu
  temada** net-değer grafiği ve lejant metni 2.82 ile okunmuyordu (renk kararı temayı bilmiyordu).
  Statik sınıf taraması bunu bulamadı — 128 kullanımın 123'ünü kaçırıp "temiz" dedi (**L29**).
  **MESAJ NİYETİ de KAPANDI (BUG #267 / ADR-049, 8 Ağu):** KURAL SIFIR ön-filtresi
  `if is_question(msg): return False` diyordu; yani **soru, gerçekleşmiş eylemi VETO
  ediyordu**. "320 TL harcadım, bütçem ne durumda?" mesajında harcama hiç kaydedilmiyor,
  üstelik soru harcama-ÖNCESİ rakamlarla yanıtlanıyordu (uçtan uca 3/4 yanlış). Sözleşme
  artık `propose_sunulsun = gerceklesmis OR (NOT soru AND NOT gelecek)` — tek kaynak
  `app/intent_rules.py`, karar gerekçesi trace'e düşer (**L31**). İkinci eksen yazımdı:
  Türkçe katlama tek kaynak `app/tr_text.py`; desenler katlanmış yazılır (**L32**). Sınıf
  taraması iki canlı defekt daha buldu: tarih anahtar kelimeleri diakritiksiz görülmüyordu
  (işlem **sessizce bugüne** yazılıyordu) ve koçun açık-soru sayacı `kaç`ı saymıyordu
  (MI oranı düşük görünüyordu). Kapı `tests/test_niyet_kapisi.py` (mutasyon 4/4).
  **KALICI HAFIZA SÖZLEŞMESİ de KAPANDI (BUG #268 / ADR-050, 8 Ağu):** `save_insight`
  argümanları ham indeksleniyordu — metin-olmayan `content` session'ı zehirleyip **tüm koç
  isteğini çökertiyordu** (projenin kendi savepoint anti-pattern maddesi). En sessiz yarısı:
  tool açıklaması "critical: asla unutulmamalı" derken enjeksiyon `sort_priority` + `limit(5)`
  ile sıralıyor ve bu yol o alanı hiç yazmıyordu → kullanıcının "asla kredi çekmem" beyanı
  hafızaya HİÇ girmiyordu (**L33**: prompt'ta verilen vaat, sistemde verilmiş değildir).
  Tek kaynak `app/insight_schema.py`; başarısızlık yönü ADR-048'in tersi — içerik YÜK,
  gerisi ETİKET (**L34**). Kapı `tests/test_icgoru_kapisi.py` (mutasyon 5/5).
  **SAĞLAYICI HATA SINIFLANDIRMASI da KAPANDI (BUG #269 / ADR-051, 8 Ağu):** fallback
  zincirinin üç kararı alt-dizi taramasıyla veriliyordu; 10 gerçekçi hata metninin **3'ü
  yanlış** sınıflanıyordu — hepsi ilgisiz sayıların rakamları yüzünden (**L35**). Sözleşme
  artık **önce yapı (durum kodu), sonra SAYISIZ metin deseni**, öncelik
  **KALICI > KOTA > GEÇİCİ** (yanlış tarafa düşmenin bedeli asimetrik — **L36**). Geri
  çekilmeye tam-jitter eklendi (LLM-011). Tek kaynak `app/provider_errors.py`, kapı
  `tests/test_saglayici_hata_kapisi.py` (mutasyon 5/5). **LLM-002 (prompt caching) bilinçli
  ERTELENDİ:** canlı sağlayıcı Gemini, kazanç bu turda ÖLÇÜLEMEZ (KURAL R3); yapısal engel
  kaydedildi — tool kümesi istek başına değiştiği için Anthropic prefix cache'i her seferinde
  geçersiz olurdu.
  **PREMORTEM ZARF AYRIŞTIRMASI da KAPANDI (BUG #270, 8 Ağu):** `_parse_and_validate` fence'i
  yalnız metnin TAMAMI fence ise soyuyordu; 9 gerçekçi sarmalamanın **5'i** düşüyordu (hepsi
  JSON'un etrafındaki düz metin) ve her düşüş iki deneme hakkından birini yakıyordu. Sınıf
  taraması aynı soruya ZATEN daha dayanıklı ikinci bir cevap buldu (`coach_insights`) —
  **kırılgan olan, kullanıcıya görünen özelliği taşıyordu** (**L37**). Tek kaynak
  `app/llm_json.py` (zarfa toleranslı, içeriğe katı; dizge-duyarlı tarama), kapı
  `tests/test_llm_json_kapisi.py` (mutasyon 5/5).
  **SAHTE TAMAMLAMA GÜVENCESİ de KAPANDI (BUG #271, 8 Ağu):** aksiyon oluşmadıysa koç
  "kaydettim" izlenimi vermemeli kuralı üç yerden delikti — fiil listesi **6/12** kaçırıyor,
  **çok satırlı yanıtta koruma hiç çalışmıyor** (**L38**), EMANET silicisi bölümün
  numaralanmış olmasını şart koşuyordu (**3/6**). Güvence artık **ifadeye değil DURUMA**
  bağlı: saf bildirim + hiç aksiyon yok → dürüst not (**L39**); fiil listesi ikinci savunma
  olarak katlanmış yazıldı ve ölçülen korpusla kapıya bağlandı. Kapı
  `tests/test_sahte_tamamlama_kapisi.py` (mutasyon 5/5 — biri kapının kendi kör noktasını
  buldu).
  **SİSTEM SÖZLEŞMESİNİN SABİTLİĞİ de KAPANDI (BUG #272, 8 Ağu):** retry ve iç plan
  system prompt'u tur içinde mutasyona uğratıyordu (**L41**); yönlendirme artık `messages`
  sonuna eklenir ve üç yönlendirme tek yerde tanımlıdır. Kapı
  `tests/test_sistem_sozlesmesi_kapisi.py` (mutasyon 4/4 — biri sözdizimi kazası olduğu için
  sahte kırmızı sayılıp yeniden yazıldı, **L40**).
  **AKSİYON REDDİ SİNYALLERİ de KAPANDI (BUG #273 / ADR-052, 9 Ağu):** `propose_action`
  ret sinyallerini serbest metinle yayıyor, tüketiciler metni tarayarak karar veriyordu
  (`if "HESAP_BELIRSIZ" in str(e)`) — ADR-051'in sınıfı, bu kez PARA YOLUNDA. Backlog
  "refactor'da sessizce bozulur" diyordu; ölçüm **zaten bozulmuş** olduğunu gösterdi: 4 sinyal
  × 2 tüketici matrisinin bir hücresi yanlıştı — **retry yolu `TARIH_BELIRSIZ` dalını hiç
  taşımıyordu**, yani işlem kaydedilmiyor VE kullanıcıya tarih sorusu da sorulmuyordu. İki
  yan bulgu: iç sinyal adı kullanıcıya görünen trace "Gözlem" satırına yazılıyordu ve
  sinyal-teşhis füzyonu yüzünden iki log satırı kullanıcının TUTARLARINI içeriyordu (BUG #180
  ihlali). Tek kaynak `app/action_errors.py` — karar TİPTE (**L42**), teşhis ayrı alanda
  (**L43**); koçun iki propose gövdesi tek yardımcıya indi (BE-005) ve sessiz kalan recurring
  tetikleyicileri `atlanan` alanıyla konuşur oldu. Kapı `tests/test_aksiyon_sinyali_kapisi.py`
  (mutasyon 6/6 — altıncısı kapının kendi kör noktasını buldu).
  **LLM MALİYET DEFTERİ de KAPANDI (BUG #274 / ADR-053, 10 Ağu):** `api_call_log` "maliyet
  analizi icin veri kaynagi" diye tanımlıydı, `tokens_in`/`tokens_out` şemada duruyordu ve
  sağlayıcıların hepsi `usage` döndürüyordu — parçalar yerindeydi. Ölçüm (6 senaryo, gerçek
  uçlardan akıtılmış trafik): 13 gerçek istek → 13 satır ama **token 0/13**; harcanan 101.756
  girdi token'ı deftere 0 düştü. **Çalışan model 7/13 yanlıştı:** zincirde birincilin modeli
  insan-okur etiketle yazılıyor, premortem/yansıma ise AMACI `model` sütununa koyuyordu
  (ADR-052 ayrımının delinmiş hâli). Backlog'un "token trace'te" iddiası da iyimserdi: trace
  gerçek token'ların **%24'ünü** yakalıyor ve 90 günde siliniyor. Sınıf taraması ölü bir
  **dördüncü yazar** buldu (`_log_api_call`) → kaldırıldı; deftere yazan tek yol `app/llm_quota`.
  Tek kaynak `app/llm_cost.py`: fiyat **(sağlayıcı, model)** çiftinin özelliğidir (**L44**),
  **bilinmeyen fiyat `None` — 0 DEĞİL** ve bilinen sıfırdan (yerel Ollama) ayrı raporlanır
  (**L45**). Fiyatlar KURAL D1 ile araştırıldı; Cerebras/DeepInfra doğrulanamadığı için tabloya
  YAZILMADI (tahmini fiyat, bilinmeyenden zararlıdır). Sonuç token **0/13 → 8/13** (kalan 5
  doğru şekilde bilinmiyor), model **7/13 → 13/13**. Kapı `tests/test_llm_maliyet_kapisi.py`
  (17, mutasyon 6/6); operatör yüzeyi `scripts/beta_metrics.py`.
  **ADR-010'un "global `.btn` gelecekteki butonları da 44px yapar" gerekçesi çürütüldü:** `.btn`
  kullanmayan kontroller 42/35/28/20/13px'ti (**L30**). Kalıcı kapı
  `frontend/e2e/tema-mobil.spec.js` (her panel × her tema: kontrast ≥3:1, taşma yok, hedef ≥44px
  + iki yazılı istisna, konsol temiz; mutasyon 3/3). Grafik renkleri tek kaynak
  `frontend/src/lib/grafikRenkleri.js` (her değer iki temada da ≥3:1). **Yan bulgu:** BUG #241'in
  kapanış kanıtı e2e'si **kimliksiz** yazılmıştı → CI'nin `AUTH_ENABLED=true` ortamında 401 ile
  ölüyordu, eklendiği 6 Ağu'dan beri hiç yeşil olmamış; izole edildi (e2e 4→**6**). Kalan açık iş:
  H4'ün dil/i18n ayağı (kapalı beta TR → yayın-engeli değil), H11 canlı SMTP (insan-kapısı) ve
  backlog'un **262 açık maddesi**. Tam devir belgesi: **`docs/kalite-seruveni/master-durum-raporu-2026-08-06.md`** (31.668 satır, 215 dosya inline).
- **METODOLOJİ KARARI (7 Ağu 2026 — yazılı hale getirildi):** **Milestone/tag disiplini 18 Tem 2026'da BIRAKILDI.** 98 tag'in
  tamamı ≤ 18 Tem; sonraki 103 commit tag'siz. İş artık **P0-P9 fazları + D-bulgu kodları (D01-D40) + BUG numaraları** ile
  yürür. `milestone-log.md` **tarihsel arşivdir**, güncel iş oraya yazılmaz. (Dipnot: `milestone-93` numarası iki ayrı işe
  verilmişti — `wave7-kapanis` + `prod-docker-imaj`; M44-M60/M97-M98/M101 hiç kullanılmadı, M97/M98 = canlı deploy.)
- **MCP MEMORY STATÜSÜ (7 Ağu 2026 — karar):** MCP knowledge graph **tek gerçek kaynak DEĞİL**; statüsü *4 May – 18 Tem 2026
  tarihsel arşiv*. Güncel durumun kaynağı **repo + master durum raporu**. Gerekçe: `memory-auto-sync.md`'nin capture→flush
  tasarımında FLUSH adımı elle koşuluyordu ve 19 gün hiç koşulmadı (`.mcp-sync-pending.log`'da 186 commit birikti) — yani
  izleme çağrısı işin gövdesine yazılmıştı (**L24**). 186 satırlık birikim bilinçli olarak MCP'ye özet halinde YAZILMADI:
  ikinci bir "gerçek kaynak" üretmek borcu ödemez, çoğaltır. **DEFTER 4 EYLÜL 2026'DA KAPATILDI (Wave-Y/Y5).** Ölçüm: flush hiç koşulmadı, ledger **300 satıra** çıktı. Yakalama, hiç koşulmayacak bir flush için çalışıyordu — **sahte yükümlülük borçtan kötüdür, çünkü ödenmez ve unutulmaz.** `post-commit` yakalaması ve `scripts/mcp_sync_report.py` kaldırıldı; güncel durumun tek kaynağı repo.
- **BUG ENVANTERİ (7 Ağu 2026 — karar):** `docs/kalite-seruveni/uygulanan-fixler.md` **tek resmî envanterdir**; her yeni BUG
  numarası oraya satır yazar. **Dürüst kayıt:** repoda 235 benzersiz BUG numarası geçiyor, ledger'da 114'ü var (kalanlar
  `milestone-log.md` + `masterprompt-publish.md` içinde dağınık). Geriye dönük toplama YAPILMADI — ayrı iş.
- **Aktif goal (arşiv):** 🟡 **WAVE-8 DEPLOY + PWA — statik kısım TAMAM, canlı-deploy İNSAN-KAPISINDA** (artık publish
  yolunun P6 fazının içinde yaşıyor). Statik/parasız her şey bitti:
**Blok A** (MA1-MA4, `milestone-93..96`): prod Docker (multi-stage, non-root appuser) + `docker-compose.prod.yml` (5 servis,
web/scheduler ayrımı → cron çift-tetiklenmez) + nginx/HTTPS (Let's Encrypt, HSTS/CSP, A-rating) + `.env.prod` secret fail-fast
(BUG#157, REPLACE-placeholder reddi) + deploy runbook/otomasyon (`scripts/deploy.sh` rollback'li). **Blok C** (MC1-MC2,
`milestone-99-100`): PWA temel (vite-plugin-pwa manifest+workbox SW+iOS meta, maskable ikon) + 390px responsive fix'ler
(ADR-011 44px). **ADR-039** (deploy impl) + **ADR-040** (PWA, mobil=PWA native-değil) yazıldı. **BEKLEYEN (Murat Oracle Free
Tier VM'i — KURAL-3 elle-görev):** Blok B (MB1-MB2 canlı-deploy + KULLANIM-GATE + 24s cron), MC1/MC2 canlı-gate'leri (HTTPS),
Blok D final (Wave-9 iskelet post-deploy önceliklenir + **GOAL TAMAM W8** deploy doğrulanınca). Otonom sunucu/para YASAK,
secret chat'e DÜŞMEZ. Rollback `pre-wave-8`. Charter `goal-charter-wave8.md`, durum `milestone-log.md`. **Önceki (arşiv):**
- **Aktif goal (arşiv):** ✅ **WAVE-7 POSTGRESQL GEÇİŞİ + VERİ-KATMANI BORÇLARI (M49-M53 + M-hisse + M92) TAMAM.** **Hibrit DB
(ADR-038):** dev SQLite / prod PostgreSQL — `app/database.py` dialect-aware (`make_url`), Alembic multi-dialect (M50: enum
ALTER TYPE / boolean sa.false / render_as_batch SQLite-only / workspace-FK Postgres'te fiziksel), **Row-Level Security
(M51:** 12 tabloda ENABLE+FORCE + `ws_isolation` policy, app-katmanı scope_filter birincil + DB-katmanı 2. savunma, GUC
`app.current_workspace_id`), Numeric bit-bütünlük dual-dialect (M52). **SBN-001 + işaret konvansiyonu tek kaynak** (M53:
`app/balance_rules.balance_delta` — BUG #161 ailesi kapandı). **BIST hisse otomasyonu CANLI** (M-hisse: İş Yatırım
fallback, THYAO=329.50 uçtan uca). Postgres bu env'de **pgserver** (docker'sız, `initdb --locale=C`) ile koşuldu;
`tests/pg_gate.py`. **(Wave-8'de ele alındı:** deploy → Docker/compose/nginx statik; mobil → PWA kararı, ADR-040.) **Önceki:**
- **Aktif goal (arşiv):** ✅ **WAVE-6 İÇ SAĞLAMLAŞTIRMA (M82-M91) TAMAM.** 10 milestone, 4 blok: A (M82-84 RULE motoru — action_type
tek-kaynak/BUG #161 drift kilidi + 12 RULE maddesi triyaj [5 fix + 8 R3-belgelendi] + rules_engine %98), B (M85-86 backlog
tam-doğrulama — **521 madde + 74 rapor R3, iki bağımsız stale ölçümü: %35 backlog + %61 rapor**), C (M87-89 KANIT YOK
kapatma + 3 doküman çelişkisi + coverage %90→%92 + **mutasyon-testi örneği** [test boşluğu bulundu+kapatıldı] + ADR index),
D (M90-91 flaky-yok 3× + p95<20ms + kapanış). Çıktı: `goal-charter-wave6.md` + `milestone-log.md`. **Sonraki:** Wave-7
(iskelet: `goal-charter-wave7-iskelet.md` — Murat'a ürün-DNA soruları kripto/VPS/PostgreSQL/mobil; SBN-001 canlı-bug). **Önceki:**
- **Aktif goal (arşiv):** ✅ **WAVE-5 SAĞLAMLAŞTIRMA (M66-M81) TAMAM.** 16 milestone, 6 blok: A (kullanım döngüsü CI + BUG #161 kart-ödeme fix), B (workspace izolasyonu statik+runtime kilitlendi — 3 gerçek leak fix: goals/fund_price/subscriptions + goal_engine/debt_strategy + cron personal-scope), C (21 eksik ADR MCP'den materyalize — "MCP BOŞ" premisi R3 ile çürütüldü + ADR-001 LLM-istisna), D (521 backlog + 75 denetim raporuna DURUM/güncellik + **RULE %42 gerçek stale ölçüldü**), E (25 KANIT YOK kapatıldı + coverage %87→%90 + Docker statik-doğrulama + prod-güvenlik fix). **AUTH_ENABLED=true canlı** — tek user (id=1) = muraticgil@gmail.com + 6 gerçek hesap. **Önceki:** Wave-3/3-Tamamlama + Wave-4 Blok A-B (M36-M43) + W4-KURTARMA (M61-M65). Wave-4 kalanı (kripto/PostgreSQL/deploy) ÜRÜN-DNA ile ERTELENDİ. **Sonraki:** Wave-6 (iskelet: `docs/kalite-seruveni/goal-charter-wave6-iskelet.md` — RULE 12 açık madde, action_type tek-kaynak, backlog tam-doğrulama; Murat ÜRÜN-DNA kararı bekliyor). **Aile/Workspace:** ADR-036 + ADR-037. Tam durum: `tam-proje-durum-raporu.md` + `milestone-log.md`.
- **Kalite Serüveni:** Faz 0 (denetim) tam · Faz 2 (P0 doğruluk) büyük oranda uygulandı · Faz 3+ açık (~472 madde). Kaynak: `docs/kalite-seruveni/`.
- **🟢 KAPALI BETA CANLIDA (11 Ağu 2026):** `https://financialos.tail378d7a.ts.net`
  (Tailscale Funnel, **0 TL**, Murat'ın kendi Windows makinesinden; SQLite + uvicorn +
  `SERVE_SPA=1`, nginx YOK). **3 gerçek kullanıcı girdi.** Açılış zinciri kurulu ve
  ölçüldü (`deploy/windows/gorevleri_kur.ps1` — başlat + 10 dk sağlık + günlük yedek);
  TEK ŞART Windows'a giriş yapılması. Geri bildirim defteri
  `docs/kalite-seruveni/beta-geri-bildirim.md` — **bilinçli olarak DEĞERLENDİRİLMEDİ**
  (karar turu: 3 davetli × 14 gün). Kalıcı plan + VPS tetikleri:
  `docs/deployment/kalici-cozum-plani.md`. **Bu makinede "bende çalışıyor" KANIT DEĞİL**:
  düz istek funnel'ı atlar, Tailscale DNS'i ele geçirir → `curl --resolve` + DoH şart.
- **AKTİF: KAPALI BETA (P6+P7).** Yöneten belgeler `docs/kalite-seruveni/masterprompt-kapali-beta.md`
  + `charter-kapali-beta.md` + `goal-kapali-beta.md`. Rollback etiketi `pre-kapali-beta`.
  **B0/B1/B2/B3 kapandı (11 Ağu, BUG #279-#281); B4 (yayın) Murat'ın barındırma kararını
  bekliyor** (`b0-barindirma-karar-notu.md`). Charter taslağının dört premisi ölçülüp
  çürütüldü (geri bildirim / allowlist / yedek provası / sürüm damgası zaten VARDI) → **L52:
  delta raporda geçmemek, diskte olmamak değildir.**
- **⚠️ CI DİRİLTME (11 Ağu gece, BUG #295-#298):** GitHub Actions'ın **son 30 koşumunun
  30'u kırmızıydı** (≥9 Ağu'dan beri) — yani yazılan hiçbir kapı uzaktan bir şey
  korumuyordu ve BUG #293'ün ölü e2e testi bu yüzden görünmedi. Dört kök neden:
  **#295** `PG_TEST_URL` adresi `localhost`tu, runner'da ::1'e (imajın KENDİ postgres'ine)
  gidiyordu → dual-dialect kapıları fiilen ölüydü (BUG #238'in iddiası: servis eklendi ama
  bağlantı hiç kurulmadı); **#296** `/api/coach/usage` cevabı DB'den üretirken önce LLM
  sağlayıcısı kurmaya çalışıyordu → anahtarsız kurulumda (yeni klon/self-host/CI) Cockpit
  rozeti 500 (**L58: bir uç döndürdüğü veriden fazlasını ön koşul yapmamalı**);
  **#297** test fixture'ları var olmayan env adları kuruyordu (`SMTP_PASSWORD` vs kodun
  `SMTP_PASS`'i; `AUTH_RATE_MAX` vs `RATE_LIMIT_LOGIN_MAX`) — geliştiricinin `.env`'i
  boşluğu doldurduğu için yerelde görünmüyordu (**L59**), kapı `tests/test_env_adi_kapisi.py`;
  **#298** `npm audit` üretim ile geliştirme bağımlılıklarını aynı eşikte topluyordu →
  dev aracının major-sürüm açığı bütün CI'ı kırmızı tutuyordu (üretim tarafı: 0 açık).
  **#299** lock dosyası CI'ın npm sürümüyle tutarsızdı (yerel npm 11 / CI npm 10 →
  `npm ci` reddediyordu; lock npm 10 ile yeniden üretildi, `.nvmrc` + `engines` ile
  hizalandı); **#300** `fresh_pg_database` bağlantı dizesini `str(make_url(...))` ile
  üretiyordu — SQLAlchemy `str(URL)` **şifreyi maskeler** → dual-dialect kapıları hiç
  koşamıyordu. Yerelde görünmemesinin sebebi yerel `pgserver`'ın **trust** auth ile
  açılmasıydı (**L60: `str()` bir gösterim biçimidir, serileştirme biçimi değil**).
  **SONUÇ: CI üç job'da da YEŞİL** (11 Ağu 21:57) — 30+ koşumluk kırmızı seri kırıldı.
  **Görünürlük:** `scripts/ci_durum.py` (son koşum + Y/K şeridi + kırmızı adımlar),
  pre-commit'e `--sessiz` bağlandı — uyarır, commit'i engellemez.
  **#301 (aynı gece, kullanıcılar uyurken):** `vite 5 → 8` + `plugin-react 4 → 6`
  yükseltildi — `npm audit` artık **üretimde ve geliştirmede 0 açık**. Hiçbir şey
  kırılmadı (build/214 vitest/7 e2e yeşil). Peer çakışması kirli ağaçtan geliyordu,
  sıfırdan kurulunca çözüldü. **Node sürümü tek kaynağa indi:** `.nvmrc` (20.19) +
  `engines` (`^20.19.0 || >=22.12.0`, vite 8'in şartı); CI `node-version-file` kullanır.
- **⚠️ YEREL YEŞİL ≠ CI YEŞİL:** CI farklı OS, farklı Node/npm sürümü, **`.env` YOKLUĞU**
  ve gerçek bir PostgreSQL servisiyle koşar. 11 Ağu turunda bulunan altı defektin dördü
  YALNIZCA orada görünüyordu. Süit yeşil diye CI'ı varsayma — `python -m scripts.ci_durum`.
- **⚙️ OPERASYON (12 Ağu gece, BUG #302):** `misfire_grace_time=3600` bir gece işini yalnız
  **1 saat** gecikmeye kadar kurtarıyordu; kapalı beta KİŞİSEL bir makinede koştuğu için
  02:45-04:00 penceresi uykuda geçtiğinde fiyat güncelleme / gece batch'i / iz temizliği o
  gün HİÇ koşmuyordu. `beklenen_periyot_saat` tanımlıydı ve `/api/ops/scheduler` "gecikti"
  diyordu — **işaretlemek koşturmaz** (**L61: ölçen sistem telafi eden sistem değildir**).
  Açılışta `kacirilan_isleri_telafi_et()` (bloklamaz, sırayla, son BAŞARILI koşuma bakar).
  Canlı kanıt: `5/5 is telafi edildi`, smoke `4 api 0 basarisiz`. Ayrıca `scheduler_runs`
  BUG #289'dan kalan 50 test satırından temizlendi (`scripts/defter_temizle.py`, kuru-koşum
  varsayılan) — defterde artık yalnız gerçek operasyon kaydı var.
- **🌐 DAVETLİ ERİŞİMİ (12 Ağu gündüz, BUG #303 + canlı DNS bulgusu):** yeni davetli siteyi
  **Chrome'da da Brave'de de** açamadı; makinede her şey yeşildi. Ölçüm kök nedeni buldu ve
  **bizim tarafımızda değil**: `financialos.<tailnet>.ts.net` adı **Cloudflare çözümleyicisinde
  12 sorgunun 11'inde NXDOMAIN** döndü, Google + AdGuard **12/12** çözdü. Chrome/Brave'in
  **"Güvenli DNS"i işletim sisteminin DNS'ini ATLAYIP Cloudflare'e gider** → davetli giremez,
  operatör göremez (tailnet adı içeriden çözer — "bende çalışıyor" yine kanıt değil). Önbellek
  değil (Cloudflare purge aracı denendi), DNSSEC değil (`cd=1` ile de NXDOMAIN); ingress sağlam
  (IP pinlenince 10/10 200). Geçici yol: davetliye **Güvenli DNS'i kapattır**. Kalıcı yol: kendi
  alan adı — bu, `kalici-cozum-plani.md` hattının ilk **kullanıcıda görülmüş** tetikleyicisi.
  Teşhis reçetesi runbook §8, kaynak `research-log.md`. **BUG #303:** (a) sağlık kontrolü 10
  dakikada bir ekranda **konsol penceresi çakıyordu** (`-WindowStyle Hidden` pencereyi ancak
  açıldıktan SONRA gizler) → `deploy/windows/gizli_calistir.vbs`; sıklığı azaltmak yanlış çözümdü
  (rahatsızlık ölçümün bedeli değil YAN ETKİSİ; seyrekleştirmek düşen tüneli daha uzun süre
  düşük bırakırdı) — yan etki kaldırıldı, **10 dk korundu**. (b) dış yol ölçümü `/api/ready`ye
  (DB sorusu) bakıyor, DoH hatasını "tünel kapalı" sanıyor, tek çözümleyiciye güveniyor ve
  `Invoke-RestMethod` ile **sessizce boş cevap** alıyordu → iki çözümleyici + `/api/health` +
  tekrar denemesi; üç durum ayrı raporlanır. Yeni kapı arızayı **canlı yakaladı**
  (`DNS KISMI KESINTI — cozmeyen: cloudflare`). **L62: kullanıcının ulaşamaması ile servisin
  düşmesi ayrı olaylardır — adres çözümlemesi de üründür.**
- **🔤 ENV ADININ İKİ TARAFI (24 Ağu, BUG #304):** BUG #297'nin kapısı **tek yönlüydü** —
  yalnız "test → kod" eksenine bakıyordu, operatörün gördüğü belge hiç bağlı değildi. İki yönde
  de canlı defekt çıktı: (a) `.env.example` `AUTH_RATE_MAX` / `AUTH_RATE_WINDOW` ilan ediyordu,
  kod bu adları **hiç okumuyor** (gerçekleri `RATE_LIMIT_LOGIN_*`) → operatör rate-limit'i
  gevşettiğini sanır, **hiçbir şey değişmez ve hiçbir hata çıkmaz**; (b) `app/` **58** ad okurken
  örnek dosyalar **53** ilan ediyordu ve **24'ü belgesizdi** — aralarında **`SERVE_SPA`**, yani
  açıkken `frontend/dist` yoksa uygulamayı HİÇ AÇTIRMAYAN anahtar. Kapı artık iki yönü de bağlıyor
  (belgesiz ad 24 → 0, ölü ad 2 → 0); altyapı dosyaları (compose/Dockerfile/Caddyfile/CI/`deploy/`)
  da taranır çünkü `DOMAIN`, `POSTGRES_PASSWORD`, `WEB_CONCURRENCY` Python'da okunmaz ama gerçektir.
  **L63: bir env adının iki tarafı vardır — kodun okuduğu ve belgenin vaat ettiği; ikisi ayrı ayrı
  doğru olabilir ve sistem yine yalan söyler.**
- **🧱 TAZE KLON KURULUMU KAYBEDER (24 Ağu, BUG #305):** format sonrası kurulum `.venv/`
  yaratmıştı; depodaki **21 izlenen dosya** ise `venv\Scripts\python.exe` bekliyor
  (`PROJE.md` komutları, `docs/contributing.md`, `.githooks/pre-commit`, **`deploy/windows/`**).
  `.gitignore` ikisini de yok saydığı için fark görünmedi. Sonuç zinciri: üç zamanlanmış görev
  (`FinancialOS-Baslat/-Saglik/-Yedek`) **hiç kurulamadı** → **canlı beta 4 gün yedeksiz koştu**
  (`data/backups/` son dosya 20 Ağu) ve tünel izlemesi hiç çalışmadı; `core.hooksPath` **ayarsızdı**
  (belgeler "zaten aktif" diyordu); hook kurulsa bile düz `python`'a düşüp **pytest yok** diye her
  Python commit'ini *"TESTLER KIRMIZI"* yanlış teşhisiyle engelleyecekti. Ortam `venv/` adıyla
  yeniden kuruldu — eskisiyle **106'ya 106 paket**, tek fark transitif `peewee`, süit **3122/18
  birebir**. **L64: bir kurulum adımı yalnızca yerel yapılandırmada yaşıyorsa klon onu taşımaz;
  "kurulum tamamlandı" diyen belge kurulumun kendisi değildir — kurulmuşluğu ÖLÇEN bir şey yoksa
  mekanizma sessizce yoktur.**
- **📜 API SÖZLEŞMESİ DONDURULDU (27 Ağu, BUG #306):** `docs/api-reference/README.md` şema
  kaynağı olarak "repo kökü `openapi.json`" diyordu — o dosya `.gitignore:71` ile yok sayılıyor
  ve **diskte hiç yoktu**. Yani 93 yol / **125 handler**'lık API'nin dondurulmuş hiçbir tanımı
  yoktu; bir uç sessizce yol/metot/yanıt değiştirse ya da bir handler'dan `Depends(get_current_user)`
  düşse süit yeşil kalır, kırılma canlı istemcide çıkardı (BUG #287/#288 sınıfı). **Ham OpenAPI
  yetmiyor, ölçüldü:** çıktıda **125 handler'ın 125'i kimliksiz görünüyor** — auth `HTTPBearer` ile
  değil `get_current_user(request: Request)` içinde başlık elle okunarak yapılıyor, FastAPI bunu
  `security` alanına yazamıyor; yalnız OpenAPI'yi dondurmak kapıyı **en çok değer üreteceği yerde
  kör** bırakırdı. Sözleşme iki kaynaktan derlenir: yüzey `app.openapi()`, kimlik rotanın
  `dependant` ağacından → `scripts/sozlesme_dondur.py` + `docs/api-reference/api-sozlesmesi.json`
  (izlenen, LF) + `tests/test_api_sozlesmesi.py`. **125 handler · 106 korumalı · 19 kimliksiz**
  (19'u tek tek incelendi, hepsi meşru; liste testte gerekçeli). Mutasyon **3/3 kırmızı** (koruma
  düşürme / 201→200 / sessiz yeni uç). **L65: bir tarayıcının bulduğu sayı, bulması gerekeni
  bilmeden doğrulanamaz** — ilk tarayıcı `app.routes`'ta yalnız 2 APIRoute görüyordu, çünkü
  FastAPI 0.141 `include_router`'ı düzleştirmiyor (`_IncludedRouter`); 123 uç sessizce kaçıyordu.
  Bu iş `seen-backend` karşılaştırmasından çıktı (rapor: masaüstü `SEEN-VS-FINANCIALOS-BULGULAR.md`,
  beş kod: KAP-01..KAP-05). Karşılaştırma üç premisi de çürüttü ve o üçü UYGULANMADI: env tek-kaynağı
  (financialos zaten önde), Sentry (BUG #195 gerekçeli reddetmiş), migration snapshot'ı
  (`test_fresh_db_migration.py` daha güçlü).
- **🔌 TESTTE AĞ KAPISI (27 Ağu, BUG #307):** süitin dışarı çıkmasını engelleyen hiçbir şey
  yoktu. `pyproject.toml` `llm`/`network`/`slow` markerlarını tanımlayıp "CI'da default skip"
  diyordu; ölçüm **üçünün de hiç kullanılmadığını** gösterdi — koruma diye yazılan şey **ölü
  yapılandırmaydı**. Oysa `app/` içinde beş modül dışarı çağırıyor ve biri **ücretli**
  (`app/coach.py`; ayrıca `fund_tracker.py:316`, `price_providers/evds_client.py:80`,
  `fx_live.py:69`, `llm_cost.py`). Unutulan tek bir mock sessizce gerçek istek atardı: para
  yanar, test dış servisin o anki durumuna bağlanır, geliştiricinin `.env`'i bunu **yerelde
  görünmez** kılar (L59'un sınıfı). `tests/conftest.py` artık dört kanalı birden kapatıyor
  (`getaddrinfo` · `connect` · `connect_ex` · `create_connection`), **modül seviyesinde** —
  sızıntı fixture kurulmadan da olabilir, koruma süreç durumuna dayanmalı (BUG #289 dersi).
  **İzinli tek şey loopback** (CI'daki `PG_TEST_URL` → `127.0.0.1:55432` yaşasın diye) ve
  `getaddrinfo(None,…)` sunucu bağlaması. Ölü `network` markerı **canlandı** — bilinçli dış
  çağrının kaçış kapısı odur. **Dürüst sonuç: kapı bugün tek sızıntı bulmadı** (süit kapı
  açıkken **3134 passed, 18 skipped**); değeri bulmakta değil bundan sonrasını tutmakta —
  BUG #306 sözleşme kapısıyla aynı sınıf. Mutasyon **6/9 kırmızı**; `test_ham_soket_connect_engellenir`
  kapı kapalıyken **gerçekten dışarı TCP açıp 20 sn'de zaman aşımına uğradı**. Kapı
  `tests/test_ag_kapisi.py` (9 test). `llm` ve `slow` markerlarına dokunulmadı (ledger'da
  gerekçeli). KAP-02/5.
- **📊 COVERAGE HİÇ ÖLÇÜLMÜYORDU (27 Ağu, BUG #308):** araç kuruluydu (`pytest-cov`),
  `[tool.coverage.*]` yapılandırması duruyordu, ama **hiçbir koşum onu çağırmıyordu** —
  `grep -rn 'fail.under\|--cov' ci.yml pyproject.toml` boş dönüyordu. `PROJE.md`'deki
  "%93" 6 Ağu'da **elle alınmış tek seferlik** bir sayıydı; yani kazanımı hiçbir kapı
  korumuyordu — bir sonraki commit onu %60'a düşürse CI yeşil kalırdı (L28: bir kez yeşil,
  sürekli yeşil demek değildir). Yeniden ölçüldü: **%93,61** (11.395 satır / 728 kapsanmayan,
  rapor %94) — yani gerçek değer bayat sayıdan YÜKSEKTİ, kimse bilmiyordu. CI artık
  `--cov=app --cov-report=term --cov-fail-under=93` koşuyor; eşik ölçülenin hemen altı,
  **hedef değil TAVAN** (felsefe seen-backend'in `quality-baseline.json`'ından).
  **Eşik bilinçli olarak `pyproject.toml`'a KONMADI:** oraya konduğunda tek dosyalık koşum da
  eşiğe tabi oluyor ve `%36,70` ile **sahte kırmızı** veriyor (ölçüldü) — alt küme tam süit
  değildir, eşiğin orada anlamı yoktur (L40'ın sınıfı). **Payda dürüstlüğü ölçüldü:**
  `source=["app"]` import edilmemiş dosyaları da paydaya katıyor — 9 test koşulduğunda bile
  rapor 104 app dosyasının hepsini ve aynı 11.395 satırı listeliyor, yani ölçülen ÜRÜNÜN
  kapsamı (seen'in `vitest.config.ts`'te acıyla öğrendiği tuzak burada yok). Mekanizma
  ölçüldü: `--cov-fail-under=99` → çıkış 1, `=30` → çıkış 0. Süre bedeli 7:25 → 8:48.
  En düşük kapsamlı modül `app/serializers.py` **%32** — `PROJE.md`'nin kendi uyardığı
  tzinfo tuzağının dosyası; ayrı iş olarak kaydedildi (**BUG #311'de kapandı — ama test
  yazılarak değil, kapsanmayan kısım ÖLÜ ÇIKTIĞI için silinerek**). KAP-03/5.
- **🧮 STATİK ANALİZ YOKTU → GERİLEME SAYACI (27 Ağu, BUG #309):** `mypy.ini`, `ruff.toml`,
  `setup.cfg`, `.pre-commit-config.yaml`, `tox.ini`, `.flake8` — **altısı da yoktu**;
  `pyproject.toml`'da yalnız pytest ve coverage bölümleri vardı. **Dürüst sonuç: ruff bu
  kod tabanında bugün TEK defekt bulmuyor.** Bulguların tamamı incelendi: `E9` **0**
  (sözdizimi temiz), `S` (bandit) 36'nın hiçbiri gerçek açık değil (`S105 "token_type"`
  değeri `"bearer"`; `S310` TCMB `urlopen`'ları; `S608` operatör script'leri), `E711/E712`
  22'nin **tamamı yanlış alarm** (`Debt.due_date != None` bir SQLAlchemy filtresidir,
  `is not None` yazmak sorguyu BOZAR). Yani araç düzeltici olarak değil **bundan sonrasını
  tutmak için** kuruldu → `ruff.toml` (dar küme: `E9,F,B,S`) + `scripts/kalite_kapisi.py`
  + `docs/kalite-seruveni/kalite-baseline.json`. **Tavan aile bazında** (E9 0 · F 203 ·
  B 31 · S 59 = **293**), tek toplam DEĞİL: tek toplam takasa izin verirdi — 5 kullanılmayan
  import temizlenip 5 yeni güvenlik bulgusu eklenince sayı aynı kalır ve kapı susardı.
  **Kapsam dışı bırakılanlar ölçülerek seçildi:** `B008` (229 bulgunun 229'u FastAPI'nin
  `Depends()` deseni — çerçevenin gerektirdiği yazım), `S101` tests/ için (4484 pytest
  assert'i), `DTZ` (212 — proje datetime'ı BİLİNÇLİ naive UTC), `I001`/`UP`/`ruff format`
  (sinyal yok, **403/411 dosyalık diff**; toplu biçimlendirme gerçek değişikliği gizler).
  **Araç sürümü baseline'da SABİT ve kapı tavandan ÖNCE onu doğrular** — bu seen'in
  sayacında yok: linter sürümü değişince sayı anlamını yitirir (zıplarsa sahte kırmızı,
  düşerse gerçek gerileme görünmez). **Mutasyon 5/5:** yeni F bulgusu → kırıldı; yeni S
  bulgusu → kırıldı; sürüm ayrışması → tavana bakmadan durdu; `--yaz` bozuk tavanı
  YÜKSELTMEDİ; iyileşme algılanıp "kazanımı kilitle" dedi. CI'da pytest'ten ÖNCE koşar
  (saniyeler). **Açık iş:** F 203'ün 177'si kullanılmayan import — otomatik düzeltilebilir
  ama ayrı tek-amaçlı commit, üstelik `__init__.py`/alembic'te bazıları yeniden-dışa-aktarım
  olabilir (ölçülmeden `--fix` yapılamaz). KAP-04/5.
- **📄 BELGE DENETİMİ (27 Ağu, BUG #310):** BUG #306'da bulunan yalan sınıfı — belgenin
  işaret ettiği dosyanın diskte olmaması — **mekanik olarak ölçülebilir**, sezgisel değil.
  `scripts/belge_denetimi.py` iki iş yapar, **iki ayrı sertlikte**: (1) **KAPI** — bir belge
  okuyucuyu bir dosyaya GÖNDERİYOR (`bkz.` / `kaynak:` / `tek kaynak`) ve o dosya git'te yok;
  bugün **0** bulgu (o tek örnek #306'da düzeltildi), yani diğer üçü gibi ÖNLEYİCİ. (2) **RAPOR**
  — şimdiki-zaman iddiası taşıyıp 30+ gündür dokunulmamış belgeler: **25** (günlük/arşiv olduğu
  için muaf: **143**). İkincisi bilerek kapı DEĞİL: bir cümlenin bayat olup olmadığına kod karar
  veremez; kapıya çevirmek insanı "sustur" refleksine iter. **Kapı ÖLÇÜLEREK daraltıldı:**
  backtick içindeki her yol-benzeri jetonu kontrol eden geniş tarayıcı **208 bulgu / 27 belge**
  verdi ve neredeyse tamamı yanlış alarmdı (yedek dosya adları, önerilmiş ama yazılmamış
  dosyalar, ve en çok **yokluk beyanları** — `PROJE.md`'nin "`mypy.ini` … yoktu" cümlesi gibi).
  208 gürültüyle doğan kapı ilk gün görmezden gelinir. **Mutasyon 3/3 — ve ikisi kapının KENDİ
  kusurunu buldu:** (a) #306'nın yalanı geri konunca kapı `openapi.json`'u dosya:satır ile
  yakaladı ama **çöktü** — `→` (U+2192) Windows cp1254'te yok, yani kapı tam da söyleyecek sözü
  olduğu anda patlıyordu (**L66: bir kapının hata yolu, başarı yolundan daha dayanıklı olmalı**);
  (b) adında "olmayan" geçen bir dosyaya yapılan gerçek ölü yönlendirme, **dosya adının içindeki
  kelime** yüzünden muaf sayılıyordu — muafiyet cümlenin ne DEDİĞİNE bakmalı, neyi adlandırdığına
  değil; yokluk taraması artık backtick içeriği çıkarılmış düz metinde yapılıyor. Koşum 0,7 sn,
  CI'da pytest'ten önce. KAP-05/5 — **seen karşılaştırmasının beş maddesi de kapandı.**
- **☠️ ÖLÜ KOD DEĞİL, SİLAHLI BEKLEME (27 Ağu, BUG #311 / KAP-06):** KAP-03'ün açık bıraktığı
  *"`app/serializers.py` %32 kapsama"* maddesi test yazılarak değil **silinerek** kapandı —
  kapsanmayan 26 ifadenin tamamı hiçbir yerden çağrılmayan `export_user_data`'ydı. Ölme
  tarihi belli: **`ac08db1` (6 Ağu)**, yani BUG #243'ün KVKK export'unu `disa_aktar`'da
  tek kaynağa topladığı commit — o düzeltme **iki çağıranı yönlendirdi ama gövdeyi
  bırakmıştı**. Gövde 21 gün çağrılmadan durdu **ve zararsız değildi**: `_row()` her kolonu
  koşulsuz bastığı için `disa_aktar`'ın `GIZLENEN_ALANLAR` ile gizlediği `password_hash` ·
  `oauth_sub` · `token_version` alanlarını hâlâ döküyordu (gerçek `User` üzerinde ölçüldü:
  üçü de ölü sürümde dökülüyor, canlı sürümde dökülmüyor). "export" diye arayan biri onu
  çağırsa **D26 aynen geri gelirdi** — üstelik `test_kvkk_veri_sahibi_kapisi.py`'nin
  sınıflandırma kapısını hiç görmeden. Aynı taramada üç ölü fonksiyon daha: **`init_db`**
  (docstring'i olmayan bir çağıranı gösteriyordu ve `create_all` ADR-013'ün yasakladığı
  damgasız şema kurma yolu), `guvenli_metin_veya`, `para_listesi`. Dördü de silindi.
  **`scripts/olu_kod_kapisi.py` TAVAN 0** — diğer kapılardan farkı bu: ruff sayacında 291
  bulgunun hiçbiri gerçek defekt değildi, burada ölçülen **4 bulgunun dördü de gerçekti**.
  Mutasyon **4/4** ve **üçüncüsü kapının kendi kusurunu buldu:** ilk sürüm atıfları düz
  metin sayıyordu, yani bir adın **yorumda/docstring'de** geçmesi "kullanılıyor" demekti —
  `serializers.py`'ye silme gerekçesi yazıldığı anda kapı tam o fonksiyona körleşiyordu.
  **L67: bir kapı, kendisini açıklayan belge yüzünden kör kalamaz** — sayım artık `tokenize`
  ile, yorum ve docstring elenerek yapılıyor (diğer dizgeler sayılmaya devam eder,
  `__all__ = ["foo"]` gerçek kullanımdır). Coverage **%93,61 → %93,86** (silinen 35 ifadenin
  31'i zaten kapsanmayandı), süit **3142 passed**. KAP-06.
- **🔡 BELGELENMİŞ KOMUT BELLEKTE BOZUKTU (27 Ağu, BUG #312):** BUG #311'in kapısı bütün
  izlenen `.py`'leri `ast.parse` ile gezerken bir `DeprecationWarning` düşürdü — kendi işine
  ait değildi, **başka bir defekti açığa çıkardı** (bir tarayıcı kurulduğunda aradığından
  fazlasını görür). İki betiğin modül docstring'i r-önekli değildi ve içinde
  `.\venv\Scripts\python.exe` geçiyordu. Python `\v`'yi **geçerli** sayar (dikey sekme,
  0x0B): kaynakta doğru yazan komut bellekte `.` + 0x0B + `env\Scripts\…` oluyordu (ölçüldü).
  `\S` ise geçersiz — bugün uyarı, **Python 3.14'te derleme hatası**. Kapı `ruff`a
  bırakılamadı (`W605` `W` ailesinde, dar küme `E9,F,B,S`). `tests/test_kacis_dizisi_kapisi.py`
  **iki test taşır çünkü iki farklı sessizlik var:** biri `ast.parse` uyarısını yakalar,
  diğeri docstring'de 0x0B/0x0C arar — `\v` geçerli olduğu için hiç uyarı üretmez ve
  birincisi onu asla göremezdi. Mutasyon 2/2.
- **Bug numaralandırma:** **sonraki `BUG #345` (tavan #344, 4 Eyl 2026 ölçümü).** ⚠️ Bu satır uzun süre *"sonraki #313 (tavan #312)"* diyordu ve **32 numara geride kalmıştı** — o hâliyle okuyan bir oturum #313'ten devam edip var olan numaraların üstüne yazardı. Ölçüm: `grep -ohrE 'BUG #[0-9]+' docs/ app/ tests/ scripts/ deploy/`. **11 Ağu akşam turu — beta
  gözlem turu, tetikleyicisi bir kullanıcının "verilerimi kontrol et" talebiydi:**
  **#294** sürüm damgası YALAN SÖYLÜYORDU — canlı uç `build: 6d3bf26abd62` derken kod
  `fc10e0b`di; `build_commit()` yalnız elle tutulan `BUILD_COMMIT` env'ini okuyordu, bu
  makinede deploy "git pull + restart" olduğu için damga donuyordu. Artık **önce git
  HEAD, sonra env** (konteyner fallback korundu), kirli kopya `+` ile işaretlenir
  (**L57: dolu bir alan doğru olduğunu göstermez — kimliği sahibinden türet**),
  **#292** kayıt gününün net değeri KALICI 0 kalıyordu (create-once snapshot; beta
  kullanıcılarının hepsinde grafik 0 iken cockpit 7.313/20.354/10.350 TL — sözleşme artık
  upsert, **L53**; canlı veri onarıldı), **#289 KAPANDI** — süit canlı DB'ye yazıyordu
  (`api_call_log: 252→254`) **ve okuyordu** (`test_prices_endpoint`'in 7 testi canlı
  DB'deki "ilk kullanıcı"ya güveniyordu → **L55: yazma kirletir, okuma yalan söyler**);
  üçüncü ayak e2e'ydi (`npm run e2e` :8000'deki KAPALI BETA sunucusuna kaydoluyordu →
  `scripts/e2e_izole.py`), **#293** "kapsamsız kapı ölü kapıdır" diyen e2e testinin
  kendisi ölüymüş (regex'te `\b` yerine ham 0x08 baytı; yazıldığından beri hiç geçmemiş —
  **L56**). Önceki tavan #291: sızan oturumu iptal edecek araç yoktu — `token_version`
  mekanizması VARDI ama onu kullanacak yol YOKTU → `scripts/oturum_iptal.py`. Önceki canlı
  bulgular: **#287 CSP arayüzü öldürüyordu** (beyaz ekran; 17 testlik kapı göremedi çünkü
  `TestClient` CSP uygulamaz — L29), **#288 service worker API'yi öldürüyordu**
  (`no-response`; ayrıca bakiyeyi önbelleğe alıyordu → BUG #239 sınıfı), #290 yeniden
  başlatma yarım çalışan sistem bırakıyordu.
- **ÖĞRETİCİ SİSTEM (FEAT-034, 11 Ağu):** içerik tek kaynak `frontend/src/lib/ogretici.js`
  (13 panel × ne-işe-yarar + nasıl + GERÇEK örnek + sık hata); üç yüzey — panel içi ipucu
  şeridi (`Ipucu.jsx`), zorunlu-olmayan kurulum sihirbazı (`OgreticiSihirbaz.jsx`, adım
  durumu backend'den) ve her panelde duran yardım köşesi (`YardimKosesi.jsx`).
  Sadeleştirme EKSİLTMEDEN: `KatlanirBolum.jsx` — katlıyken özet başlıkta kalır, dikkat
  gerektiren durum rozetle görünür. Kapsam kapısı App.jsx TABS ↔ rehber anahtarlarını
  KAYNAKTAN eşleştirir (yeni panel eklenip rehberi unutulursa kırmızı). Önceki sayaç `BUG #282`'den (tavan #281: kapalı beta turu — **#279**
  davet kapısının kapsamı ölçülmüyordu + workspace daveti allowlist dışı adrese sessizce
  gidiyordu; **#280** korelasyon kimliği yoktu, hata kaydediliyordu ama kullanıcının gördüğü
  olayla eşleştirilemiyordu → `app/correlation.py`; **#281** geri bildirim toplanıyordu ama
  teşhis edilemiyordu → sürüm/kimlik/istemci alanları + `kafa_karistirdi` türü). Önceki #278: **LLM-005 KAPANDI — judge +
  yan yana koşum + skor saklama**. Judge'ın dekoratif olmadığı ÖLÇÜLDÜ: 6 çift
  ezber/muhakemeli cevapta 5/6 doğru sıralama, MUHAKEME ölçütü ezberin 6/6'sında KALDI.
  `app/coach_judge.py` (rubrik tek kaynak, skor yoksa `None`, öz-değerlendirme uyarısı),
  `app/eval_store.py` (JSONL, metin taşımaz, düşüş raporu geçersiz koşumu kalite düşüşü
  saymaz), `eval_runner --saglayicilar/--judge/--kaydet/--gecmis`. Yan bulgular: judge
  prompt'u kendi ayracını icat edip prompt-injection savunmasını devre dışı bırakıyordu
  (**L50**) ve para kapısı "İŞARE**TL**E" gibi kelimeleri para sabiti sayıyordu — desen
  kesinleşti, muafiyet azaldı (**L51**). Dış dünya: Gemini ücretsiz katman **20 istek/gün**
  (repo'daki "1000/gün" bayattı, research-log). Önceki #277: **koçun yazılı üslup sözleşmesini
  hiçbir şey ölçmüyordu** — V3 prompt'u dalkavukluk/dolgu/"siz" hitabı/iç jargon/boş teselli/
  nutuk/sahte niyet maddelerini AÇIKÇA yasaklıyor, ama eval'de karşılıkları yoktu: bu maddeleri
  ihlal eden 9 persona ihlalsiz referansla **birebir aynı %100** aldı (**L48**); canlı DB'deki
  12 gerçek cevabın 5'i, fix sonrası canlı koşumda 8 senaryonun 4'ü ihlalli çıktı. İkinci eksen:
  sahte-niyet dedektörü 12 cümlenin 8'ini kaçırıyordu ve kaçanların tamamı **"sen" hitaplı**
  biçimlerdi — yani bir kuralın koruması ikinci bir kuralın İHLALİNE bağlıydı (**L49**); koruma
  yalnız retry dalındaydı, iddia kullanıcıya 8 hücrenin 7'sinde ulaşıyordu → tek kaynak
  `app/uslup_kurallari.py`, prompt listesi oradan üretilir, güvence DURUMA bağlı
  (`bekleyen_onay_var`), eval kriterleri `uslup`/`no_fake_niyet`/`oz`; judge boyutu bilinçli
  AÇIK). Önceki #276: **kalite koşumu tamamen ölü koçu
  %83.3 ile ödüllendiriyordu** — 8 kanonik senaryonun 6'sı yalnız OLUMSUZ kriter taşıyordu
  (`no_action`/`no_fake`/`no_confidence`) ve bunları hiç cevap vermeyen koç bedavaya sağlıyordu;
  "Tamam." diyen sessiz koç da aynı puanı alıyordu, `grounded` ise varsayılan TRUE okuyordu →
  yapısal `llm_kullanilamadi` bayrağı + olumlu `cevapladi` kriteri + cevapsız senaryoda diğer
  kriterlerin sıfırlanması; ölü koç %0.0, sessiz koç %10.0, **L47**).
  Önceki #275: **kalite kapısının kendi ölçütü,
  koruduğu sözleşmeden zayıftı** — `coach_eval` sahte-tamamlama tanımasının kendi kopyasını
  taşıyordu; ölçüm BUG #271'in 12 cümlelik korpusunun **7'sini kaçırdığını** gösterdi (araç,
  regresyonu YEŞİL puanlardı) ve kopya ters yönde **4/4 yanlış-pozitif** üretiyordu ("Analizi
  tamamladım") → tek kaynak `app.coach.sahte_tamamlama_iddiasi_var`, **L46**; LLM-005'in
  "karşılaştırma yok" premisi de R3 ile düzeltildi — `scripts/eval_runner.py` zaten sağlayıcı
  başına koşuyor, eksik olan judge/yan-yana koşum/skor saklama).
  Önceki #274: **maliyet defterinin PARA sütunları
  hiç yazılmıyordu** — `api_call_log` "maliyet analizi icin veri kaynagi" diye tanımlıydı,
  `tokens_in`/`tokens_out` şemada duruyordu ve sağlayıcıların hepsi `usage` döndürüyordu; ölçüm
  13 gerçek istekte **token 0/13** buldu ve çalışan model **7/13 yanlıştı** — zincirde birincilin
  modeli insan-okur etiketle (`... (fallback: 1 ek provider)`) yazılıyor, premortem/yansıma ise
  AMACI `model` sütununa koyuyordu. Backlog'un kendi durumu da iyimserdi: trace gerçek token'ların
  yalnız %24'ünü yakalıyor ve 90 günde siliniyordu → tek kaynak `app/llm_cost.py` (fiyat
  **(sağlayıcı, model)** çiftinin özelliği; **bilinmeyen fiyat None, 0 DEĞİL**; bilinen sıfır
  ayrı) + `amac` sütunu, ADR-053, LLM-006/OBS-005).
  Önceki #273: **iş kuralı sinyali istisna
  STRING'iyle taşınıyordu** — `raise ValueError("HESAP_BELIRSIZ")` + `if "HESAP_BELIRSIZ" in
  str(e)`; ölçüm 4 sinyal × 2 tüketici matrisinin bir hücresini yanlış buldu: **retry yolu
  `TARIH_BELIRSIZ` dalını hiç taşımıyordu** → özette tarih olup payload'da olmayan harcama
  kaydedilmiyor ve kullanıcıya tarih sorusu da sorulmuyordu; ayrıca iç sinyal adı kullanıcıya
  görünen trace satırına, kullanıcının tutarları da log'a düşüyordu → tek kaynak
  `app/action_errors.py`, karar TİPTE teşhis ayrı alanda, ADR-052, BE-006/RESIL-019/BE-005).
  Önceki #272: **yönlendirme, sözleşmenin
  kendisini değiştiriyordu** — `propose` retry'ı `[RETRY: ...]`i system prompt'a ekliyor, iç
  plan ise ANA çağrının system'ine modelin O TURDA ürettiği metni yazıyordu; aynı dosyada
  doğrusu zaten vardı (soru retry'ı nudge'ı messages'a ekliyor) → değişmez artık "bir turdaki
  HER sağlayıcı çağrısı AYNI system prompt'u görür", LLM-021). Önceki #271: **"kaydettim" güvencesi üç ayrı
  yerden delikti** — fiil listesi 12 cümlenin 6'sını kaçırıyor, çok satırlı yanıtta koruma HİÇ
  çalışmıyor (`## Durum` + "kaydettim" uyarısız geçiyordu), EMANET silicisi bölümün
  numaralanmış olmasını şart koşuyordu (3/6 kaçıyor) → güvence artık ifadeye değil DURUMA
  bağlı (saf bildirim + aksiyon yok → dürüst not), LLM-020). Önceki #270: premortem, modelin **nezaket
  cümlesi** yüzünden kayboluyordu — fence yalnız metnin TAMAMI fence ise soyuluyordu, 9
  sarmalamanın 5'i düşüyordu ve kullanıcı premortem'i hiç göremiyordu; sınıf taraması aynı
  soruya kod tabanında ZATEN daha dayanıklı ikinci bir cevap buldu → tek kaynak
  `app/llm_json.py`, sözleşme "zarfa toleranslı içeriğe katı", LLM-009). Önceki #269: fallback zincirinin kararını
  **hatayla ilgisi olmayan bir sayının rakamları** veriyordu — `token count (8504) exceeds`
  içindeki 8504'ün "504"ü yüzünden KALICI hata GEÇİCİ sayılıyor, her istekte 3 kez retry
  ediliyor ve devre kesici hiç açılmıyordu; `req_8429fa1c`/`4290 ms` ise "429" içerdiği için
  KOTA sayılıp sağlıklı sağlayıcıyı düşürüyordu → tek kaynak `app/provider_errors.py`
  (önce yapı/durum kodu, sayısız metin desenleri, öncelik KALICI > KOTA > GEÇİCİ),
  ADR-051, LLM-012 + LLM-011). Önceki #268: koç, kullanıcının **"asla unutma"
  dediği şeyi tam olarak unutuyordu** — tool açıklaması "critical: asla unutulmamalı" derken
  enjeksiyon `sort_priority` + `limit(5)` ile sıralıyor ve `save_insight` bu alanı hiç
  yazmıyordu; ayrıca metin-olmayan `content` session'ı zehirleyip tüm koç isteğini
  çökertiyordu → tek kaynak `app/insight_schema.py` + önem merdiveni, ADR-050, LLM-008 kalanı).
  Önceki #267: koç kapısı **tek bayrakla iki
  bağımsız soruyu** cevaplıyordu — "soruyor mu?" ile "gerçekleşmiş olay bildiriyor mu?"; soru
  gerçekleşmiş eylemi VETO ettiği için "320 TL harcadım, bütçem ne durumda?" mesajında harcama
  hiç kaydedilmiyor ve soru harcama-öncesi rakamlarla yanıtlanıyordu. İkinci eksen yazım:
  desenler yalnız diakritikli hâli tanıyordu (`re.IGNORECASE` ı↔i'yi katlar, ç/ş/ğ/ö/ü'yü
  katlamaz → defekt harfe göre değişir) → tek kaynaklar `app/intent_rules.py` +
  `app/tr_text.py`, ADR-049, backlog LLM-010). Önceki #266: LLM'in ürettiği aksiyon payload'ı
  hiç doğrulanmadan onaya sunuluyordu — metin tutar onaya gidip onaydan sonra hiçbir şey
  yazmıyordu, özet "320 TL" iken payload 3200 olabiliyordu → `app/action_schema.py` tek kaynak,
  ADR-048, backlog LLM-008. Önceki #265: uygulamanın ikinci görünümü —
  açık tema + 390px telefon genişliği — hiç render edilip ölçülmemişti; dört panel koyu-varsayandı
  ve açık temada başlıklar görünmüyordu, koyu temada grafik okunmuyordu → `e2e/tema-mobil.spec.js`
  kapısı + `lib/grafikRenkleri.js` tek kaynağı, ADR-047; ADR-010'un gerekçesi düzeltildi). Önceki #264: kullanıcının parasıyla ilgili iki karar
  sabit Türkçe kategori adlarına bağlıydı — bir harcamanın kredi kartına yazılıp yazılmayacağı beş
  ada, muhasebe-dışlaması bir başka ada; kendi kategorisini adlandıran kullanıcıda ikisi de sessizce
  ölüyordu → `app/category_rules.py` tek kaynak + `categories` tablosu, ADR-046, P3.5.3). Önceki: #263: kapasitenin yalnız dışarı bakan tarafı hesaplanmıştı — iş parçacığı havuzu 40 > DB havuzu 15, havuz uygulamanın içinde tükeniyordu → `app/capacity.py` tek kaynak, P5.5). Önceki: #262 ilk kurulum rehberi ilk adımdan sonra kayboluyordu + birincil düğmesi ölü `href="#..."` bağlantısıydı (P3.3). Önceki: #261 sır sızma denetimi hiç yapılmamıştı → `scripts/sir_taramasi.py` + CI. Önceki: #260 CI'da bağımlılık taraması yoktu, #259 güvenlik başlıkları yalnız nginx'teydi (H22), #258 kalıcı hata metni maskesizdi, #257 prompt enjeksiyonu yapı savunması (ADR-045). Önceki tavanlar: #256 para birimi tek kaynak (ADR-044), #254 şifre politikası kişiye özel tahmini görmüyordu — `ali@x.com` kullanıcısının `ali12345` şifresi geçiyordu; blocklist 30→108). 6 Ağu akşam turunda #241-#254 kapandı: kullanıcı bildirimi (alacak tahsili nakde geçmiyordu) + **doğrulama denetiminin 40 bulgusunun TAMAMI** (D01-D40). **Audit kod sistemi:** `RULE-`/`SEC-`/`DATA-`/`FEAT-`/`BE-`/`LLM-`/… boyut-kodları (eski B/F sistemi terk edildi).

- **LİSANS + ATIF (7 Ağu 2026 kararı):** repo **"Tüm Hakları Saklıdır"** (MIT'ten çevrildi; MIT 6 May–7 Ağu
  arası geçerliydi ve o dönem edinilen kopyalar için geri alınamaz). Commit mesajlarına
  **Commit mesajlarına araç/asistan atfı EKLENMEZ** — yasal zorunluluk değil, proje sahibinin tercihi. Proje tek yazarlıdır ve commit geçmişi bunu yansıtır.
  **Geçmiş temizliği TAMAM (7 Ağu 2026):** `git-filter-repo` mesaj-callback ile 574 commit işlendi,
  311 mesaj değişti, kalan trailer 0; `push --force` (main + 99 tag) yapıldı. Bütünlük kanıtı:
  `HEAD^{tree}` rewrite öncesi/sonrası aynı (`c9a718e7…`) — içerik/yazar/tarih değişmedi, yalnız
  mesajlar. Eski HEAD `a31d64a` → yeni `e861a41`; **dokümanlardaki tüm eski commit hash'leri
  tarihseldir, artık çözülmez.** Geri dönüş yalnız bundle'dan:
  `C:\Users\18155\financialos-yedek-20260807-0908.bundle`.

## Çekirdek Prensipler

- **ADR-001 — Rules Engine karar verir, LLM açıklar.** Tüm matematiksel kararlar `app/rules_engine.py` (+ debt_strategy/goal_engine/cashflow) içinde; LLM (`app/coach.py`) sadece `cockpit` dict'ini bağlam alır, hesap YAPMAZ. "LLM'e soralım öğrensin" tembelliği yasak. ⚠️ Bu ilkenin **gayri-resmi kişi-ismi kod/docstring/commit'te YASAK** — isimsiz form kullan (`docs/architecture/adr-001-*.md`).
- **LLM asla doğrudan DB yazmaz:** `propose_action` → kullanıcı onayı → `execute_pending_action`.
- **Master Checkpoint enforcement** `app/action_executor.py`'de kod seviyesinde (LLM prompt'una güvenilmez). Grounding (`app/grounding.py`): koçun her TL'si cockpit'te izlenebilir olmalı.
- **KURAL SIFIR:** `propose_action` SADECE kullanıcı gerçekleşmiş bir eylemi bildirdiğinde çağrılır — soru/analiz/selamlaşmada asla.
- **DB datetime:** timezone-naive UTC. Frontend'e serialize ederken `tzinfo=timezone.utc` ekle (`app/serializers.py`); eksik bırakırsan JS Türkiye saatinde 3 saat geri gösterir.

## Değişmez Kurallar (KURAL)

Kaynak: MCP `Iletisim Kurallari` entity'si (**erişilebilir** — 6 Ağu 2026 R3 ile doğrulandı;
eski "MCP BOŞ / KURAL_KOPYA_BEKLIYOR" notu ÖLÜ premisdi, kaldırıldı). Aşağısı diskteki tek kaynak:

- **KURAL 1 — Dil/ton:** Türkçe, direkt, preamble yok, dalkavukluk yok ("Harika soru!" yasak).
- **KURAL 2 — Format:** tek mesaj, tek soru, tek adım. "A mı B mi C mi" paketlemesi YASAK; sırayla ver.
- **KURAL 3 — Delege etme:** otomasyonun yapabildiği hiçbir şeyi kullanıcıya yaptırma. "NASIL ANLAT"
  yalnız gerçek elle-görevler için (kimlik doğrulama, GUI, canlı-DB destructive onay) — o zaman da tam
  komut bloğu + beklenen çıktı + hata çözümü.
- **KURAL 4 — Yasaklar:** "yorgunsundur, mola ver, yarın devam" YASAK; molayı kullanıcı söyler. Aşırı
  koruyucu ton ve "iyi gidiyorsun" tarzı vasat takdirler YASAK.
- **KURAL 5 — Gereksiz özet yok:** bağlamı hatırlatma, direkt sonuca git.
- **KURAL 6 — Yeni sohbet:** önce durum oku, sonra "devam" — otomatik seçenek önerme.
- **KURAL 7 — Geri bildirim:** hata denince savunmaya geçme; sebebi anla, düzelt, kalıcı not yaz.
- **KURAL 8 — Zaman:** vakit var; küçük hızlı adım değil kapsamlı kaliteli iş. "Kapsamlı mı pratik mi"
  diye SORMA.
- **KURAL 9 — Komut formatı:** doğrulama adımı + tam komut + sonuç doğrulaması.
- **KURAL 10 (K10) — "sen seç" = muhakeme et:** MUHAKEME + BENİ DÜŞÜN + GENELİ DÜŞÜN. Rastgele/yüzeysel
  seçim yasak. **Ölçek eşiği (6 Ağu 2026):** üç-boyut muhakemesi kullanıcının parasına/verisine dokunan
  ya da geri dönüşü pahalı seçimlerde ZORUNLU; geri alınabilir ve kullanıcıya görünmeyen seçimde tek
  satır gerekçeyle seç ve devam et (tören yapma).
- **KURAL 11 — Gayri-resmi kişi-ismi kod/docstring/commit'te YASAK** (ADR-001 isimsiz form).
- **KURAL 12 — Kalite MUTLAK:** "basit/MVP yeterli/pratik/hızlı/iş yükü az" gerekçe DEĞİL. İki seçenek
  kalitede TAM eşitse basit olan seçilir; kullanıcıya bilişsel yük getiren karmaşıklık zaten kalite
  meselesidir.
- **KURAL R3 — İddia değil kanıt (6 Ağu 2026 genişletildi):** yalnız "memory vs disk" değil. Kanıt
  hiyerarşisi: **koşan komut/test çıktısı > kod > doküman > hafıza.** Doküman da yalan söyler — son beş
  bug bunu kanıtladı (#217 "kapsam kilitli", #237 ADR-042 "uygulandı", #238 ADR-038 "2. savunma",
  #239 "tazelik gösteriliyor"). Bir iddiayı ancak onu ölçen bir koşum kapatır.
- **KURAL D1 — Sektör araştırması (6 Ağu 2026 tetiği daraltıldı):** "her mimari/tasarım/UX kararı"
  kapsamı fiilen töröne dönüşmüştü (`research-log.md`'de tek gerçek kayıt var, Wave-3 kuyruğu hiç
  koşulmadı). Yeni tetik — şu üç sorudan **birine bile EVET ise araştır**, üçü de HAYIR ise araştırma
  YOK, karar ver ve tek satır gerekçe yaz:
  1. Geri dönüşü pahalı mı? (şema, para formatı, sağlayıcı bağımlılığı, dağıtım platformu)
  2. Cevap benim deneyimimde değil DIŞ DÜNYANIN durumunda mı? (API limiti, kütüphane canlılığı,
     platform kısıtı, mevzuat)
  3. Yanlış seçim SESSİZ mi kalır? (test yeşil kalır, hata aylar sonra kullanıcıda çıkar)
  Ve: araştırma `research-log.md`'ye düşmediyse **yapılmamış sayılır**.
- **OTONOM KARAR PROTOKOLÜ** (tıkanınca): charter'daki protokolü uygula — kategori (a/b/c), K10,
  "kalite düşürme reflex'i" yasak.
- **PUSH (6 Ağu 2026):** push için izin sorulmaz — iş bitince commit + push yapılır.

## Kritik Yollar

- `docs/kalite-seruveni/` — **güncel yol haritası** (plan.md, sections/ 18 boyut, dosya-denetimi/ 75 rapor, uygulanan-fixler.md ledger, dersler-gemini.md, goal-charter, milestone-log).
- `docs/architecture/` — ADR'ler. `alembic/versions/` — migration (schema tek doğruluk kaynağı, ADR-013).
- `app/` — backend · `frontend/src/` — React panelleri · `tests/` — pytest.

## Anti-Pattern Listesi (kaçın)

- **Dual-index:** `Column(index=True)` + ayrı `Index()` aynı sütunda → isim çakışması / create_all OperationalError.
- **Savepoint:** loop içinde `db.rollback()` yerine `db.begin_nested()` (IntegrityError'da session zehirlenmesin).
- **Enum karşılaştırma:** `str(enum)` değil `.value` (account_type vb. sessiz ölür).
- **Windows shell:** shell built-in için `cmd /c` wrapper.
- **`Base.metadata.create_all` production'da YASAK (ADR-013):** yeni tablo → Alembic migration şart. Yalnız setup_data/conftest'te.
- **Recharts mount warning:** yeni bileşenlerde CSS progress bar tercih (BUG #059).
- **Finansal float:** `app/schema_types.py` sonlu-değer tipleri kullan (inf/NaN reddi, SEC-032).

## Bug Fix Konvansiyonu

Dosya başındaki `GUNCELLEMELER` docstring'ine `BUG #NNN fix:` + değişen satır yanına inline yorum (numara artar). Backlog ID (`[RULE-001]`) referansla. `uygulanan-fixler.md`'ye satır ekle.

## Sık Kullanılan Komutlar

```powershell
.\venv\Scripts\python.exe -m pytest tests/ -q          # test süiti (774)
.\venv\Scripts\python.exe -m alembic upgrade head       # schema kur/güncelle (ADR-013)
.\venv\Scripts\python.exe scripts/test_fresh_db_migration.py   # temiz DB kurulum kilidi
uvicorn app.main:app --reload --port 8000               # backend
cd frontend; npm run dev                                # frontend (5173)
python -m scripts.backup                                 # SQLite yedek
```
⚠️ `scripts/setup_data.py` `drop_all` yapar (onay guard'lı) — canlı veri silinir, sadece test öncesi.

## Yerel araç yapılandırması (depoya girmez)

- **financialos-kalite-seruveni** (repo-committed) — bu projenin denetim+iyileştirme metodolojisi (18 boyut, 5 aşama, KURAL 12/D1/K10, OTONOM KARAR, 10 meta-ders). Bir dosya denetlerken / kalite ikileminde kullan.
- Geliştirme ortamının kendi sağladığı yardımcıları kullanılır; repo'ya vendor'lanmaz ve depoya girmez.

## Detaylı Belgeler

- **@docs/kalite-seruveni/masterprompt-koc.md — KOÇ ZEKÂSI HATTI (Wave-K).** Publish hattının
  KARDEŞİ, yerine geçmez. "Koç yeterince iyi mi?" sorusunu yönetir. Tek doğruluk kaynağı
  **§9.0 KALDIĞIMIZ YER**; koç kalitesiyle ilgili her oturum oradan devam eder.
  Baseline (1 Eyl 2026): deterministik eval **%71,4** (25/35), 3/8 senaryo, koşum GEÇERSİZ —
  sağlayıcı zincirinin 4 halkasından 3'ü ölü. Aktif faz: **K1**.
- @docs/architecture.md — Rules Engine, LLM provider, HTTP katmanı, datetime, frontend, bug fix konvansiyonu
- @docs/dev-commands.md — Tam komut listesi, .env şeması, test script'leri
- @app/PROJE.md — Backend kuralları (FastAPI, SQLAlchemy 2.x, Pydantic V2, timezone)
- @frontend/PROJE.md — Frontend kuralları (React + Vite + Tailwind, api.js, tarih parse)
