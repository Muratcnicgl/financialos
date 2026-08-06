# MASTERPROMPT — PUBLISH YOLU (Wave-9)

> **Bu dosya bir plan değil, bir TALİMATTIR.** asistan araci her oturumda bu dosyayı okur ve
> buradaki protokolü uygular. "Kaldığımız yerden devam" = bu dosyanın §11 DURUM TABLOSU'ndaki
> ilk ⬜/🟡 satırdan devam etmek demektir.
>
> **Sürüm:** v2.0 · **Yazıldı:** 2026-08-04 · **Revize:** 2026-08-05 (41 bug sonrası ders-kuralları) · **Sahip:** Murat İçgil · **Yürütücü:** asistan araci
> **Değişiklik günlüğü:** §12 (yalnız İLERİ yönlü — kapsam daraltma/kalite düşürme yasak)

---

## §0. GÖREVİN TANIMI (tek cümle)

FinancialOS'u, **yabancı insanların gerçek finansal verisini** taşıyabilecek kalitede,
**kapalı betaya açılabilir** ve ardından **publish edilebilir** hale getirmek — hiçbir adımı
varsayımla, geçiştirerek veya "sonra bakarız" diyerek atlamadan.

**Bu bir finans uygulamasıdır.** Bar, sıradan bir CRUD uygulamasının barı DEĞİLDİR:
bir izolasyon açığı = birinin maaşının/borcunun yabancıya görünmesi. Bir hesap hatası =
birinin yanlış finansal karar alması. Bu iki cümle, aşağıdaki her kapının gerekçesidir.

---

## §1. DEĞİŞMEZ KURALLAR (her görevde geçerli, istisnasız)

Bunlar `PROJE.md`'den devralınır ve bu goal boyunca **sertleştirilmiş** haliyle uygulanır:

| # | Kural | Bu goal'de anlamı |
|---|---|---|
| K1 | Türkçe, direkt, dalkavukluk yok | Rapor = bulgu + kanıt. "Harika gidiyoruz" cümlesi yok. |
| K3 | asistan araci'un yapabildiğini kullanıcıya delege etme | Yalnız §9'daki İNSAN-KAPISI listesi delege edilir. Başka hiçbir şey. |
| K12 | Kalite MUTLAK, basitlik gerekçe değil | "MVP yeter / pratik / hızlı / şimdilik" → **yasak gerekçe**, reddedilir. |
| R3 | Memory vs disk çelişirse **disk** gerçek | Her iddia `git`/`pytest`/`alembic`/`inspect`/`curl` ile doğrulanır. |
| D1 | Yeni mimari karar öncesi 2-3 sektör referansı | ADR yazılmadan mimari karar uygulanmaz. |
| K10 | "sen seç" → üç boyut muhakemesi | MUHAKEME + BENİ DÜŞÜN + GENELİ DÜŞÜN. |
| ADR-001 | Rules Engine karar verir, LLM açıklar | Hiçbir kapıyı LLM'e sordurarak geçme. |

### §1.1 Bu goal'e özel EK KURALLAR (Murat'ın 4 Ağustos direktifi)

- **VARSAYIM YASAK.** "Muhtemelen çalışıyor / zaten vardır / test ediliyordur" cümlesi kuruluyorsa,
  o cümle bir **görev**e dönüşür ve doğrulanır. Doğrulanamayan her şey `KANIT YOK` olarak kaydedilir.
- **GEÇİŞTİRME YASAK.** Bir kapı kısmen geçildiyse **geçilmemiştir**. Kısmi = ⬜.
- **TEMBELLİK YASAK.** "Bu dosya büyük, örnek birkaçına bakayım" → yasak. Kapsam tamsa tam taranır.
- **ZAMAN İSRAFI ÖNEMSİZ, KALİTE İSRAFI YASAK.** Uzun süren doğru yol > kısa süren yaklaşık yol.
- **DURMAK YOK.** Bir faz bitince rapor + bir sonraki faza geçiş aynı turda başlar. Onay beklenmez
  (Murat tüm işlemleri önceden onayladı) — **tek istisna §9 İNSAN-KAPISI**.
- **GERİLEME YASAK.** Bu masterprompt yalnız ileri yönlü güncellenir (§12).

### §1.3 DERS-KURALLARI L1-L28 (v2.0+ — YALNIZ EKLENİR)

> Not: `D1` §1'de **sektör referansı** kuralıdır; karışmasın diye ders-kuralları **L** ile numaralanır.

Bu kurallar teorik değil: her biri bu goal'de **gerçekten yaşanmış** bir hatadan çıkarıldı.
Yeni bir iş yaparken bu listeyi bir kontrol listesi gibi geçir.

| # | Kural | Nereden çıktı |
|---|---|---|
| L1 | **"İkinci kullanıcı geldiğinde ne bozulur?"** — her özellik için sor. Tek kullanıcıda görünmeyen hata, ikinci kullanıcıda VERİ SIZINTISIDIR. | #162 (çapraz-kullanıcı kural sızıntısı), #163 (yalnız ilk kullanıcı), #188 (paylaşılan kota) |
| L2 | **Sessiz kabul, en kötü hatadır.** Geçersiz girdi/ayar kabul edilirse kullanıcı KORUNDUĞUNU SANIR. Yazma anında gürültüyle reddet. | #192 (bozuk kural), #197 (geçersiz saat dilimi), #164 (bozuk yedek) |
| L3 | **Yeşil kapı ≠ çalışan kapı.** Her statik/otomatik kapıya, kapının kendisini sınayan meta-test yaz. | #162'yi kaçıran Wave-5 kapısı |
| L4 | **Provasız güvence yoktur.** "Yedeğimiz var / migration çalışır / deploy hazır" iddiaları ancak TATBİKATLA doğrulanır. | H14 (geri yükleme), #196 (veri-dolu migration), prod provası |
| L5 | **Production varsayılanları FAIL-CLOSED olmalı.** Operatör hiçbir şey yazmazsa sistem güvenli tarafta kalmalı. | #171 (AUTH_ENABLED), #199 (kayıt modu), #170 (sıfırlama token'ı) |
| L6 | **Sertleştirirken geliştirmeyi kilitleme.** Kapsamı prod'a daralt; dev/test akışı bozulursa kapsam yanlıştır. | #202 ilk denemesi 25 testi kırdı → kapsam prod+açık-kayda daraltıldı |
| L7 | **Kapılar birbirini etkileyebilir.** Sıra/yan etki düşün; yoksa kapı YANLIŞ ALARM verir. | #198 (rate-limit testi login kovasını tüketiyordu) |
| L8 | **Belgelenen ≠ ulaşılabilir.** Metin/ayar var diye erişilebilir sanma; canlı yolu ölç. | #191 (KVKK metni prod imajında yoktu) |
| L9 | **Kod ile doküman arasına test koy.** Env adı/sürüm/envanter gibi sözleşmeler elle senkron kalmaz. | #189 (OAuth env adları), #200 (CHANGELOG↔sürüm), veri-işleyen envanteri |
| L10 | **Yalnız yerelde görünmeyeni ara.** Sunucu/konteyner/çok-worker/başka saat dilimi farklı davranır. | #169 (TZ), #182 (proxy/çok-worker), #185 (state process-yerel) |
| L11 | **"Hepsini tarar" diyen kapı, KAÇ TANE taradığını da ölçmeli.** Kapsamı üçüncü-taraf iç yapısından (ör. `app.routes`) türetme; kararlı kamu sözleşmesinden türet ve **taban assert et**. Aksi halde bir kütüphane sürümü kapıyı sessizce körleştirir, kapı yeşil kalır. L3'ün meta-testi bile bunu kaçırır — meta-test kapının MANTIĞINI sınar, KAPSAMINI değil. | #217 (FastAPI 0.141 `_IncludedRouter` → 87 uçtan 1'i taranıyordu; izolasyon kapısı 0 ölçüyordu, ikisi de yeşildi) |
| L13 | **Kurulum adımını denetleyen bir kapı yoksa, o adım eninde sonunda atlanır.** "Runbook'ta yazıyor" bir kapı değildir. Kod ile ÇALIŞAN sistemin durumu (şema sürümü, uygulanmış migration, yapılandırma) arasına startup'ta fail-fast koy — aksi halde sistem yarım çalışır ve sağlık ucu yeşil kalır. | #222 (canlı DB 9 migration geride; koç onayı 500 verirken `/api/health` yeşildi) |
| L12 | **Hata yolu da bir ürün yüzeyidir.** Panel/akış "veri yok" halinde test edilip "istek patladı" halinde test edilmiyorsa yarısı sınanmamıştır — çökme ve **istek döngüsü** oradan çıkar. | #218 (toast kimliği → sonsuz istek), #219 (hata → state null → panel çöktü) |
| L14 | **Güvenlik varsayılanı fail-CLOSED olmalı; koruma "unutulması en kolay değişkene" bağlanamaz.** "Varsayılan kapalı + prod'da fail-fast" kalıbı, prod işaretini kimsenin set etmediği bir dağıtım yolu olduğu anda çöker. Doğru kalıp: korumayı aç, kapatmayı AÇIK BEYAN şartına bağla. Ayrıca dokümanın söylediği kurulum adımını **çalıştırıp sonucunu assert eden** bir test yaz (şablonu kopyala → kimlikli sunucu çıkıyor mu). | #227 (systemd yolu: `cp .env.example .env` → kimliksiz canlı sunucu; #171'in fail-fast'i bu yolda hiç tetiklenmiyordu), #225 (tv claim'i hiç taşınmadığı için sürüm kontrolü sessizce etkisiz kalırdı) |
| L16 | **Tüketici tarafında yapılan düzeltme kaynağı düzeltmez.** Bozuk bir üretici (kirli global durum, yanlış veri, sızan artefakt) tek bir tüketicide filtrelenerek kapatılırsa, aynı üreticiyi okuyan BİR SONRAKİ tüketici aynı tuzağa düşer — üstelik ilk filtre "çözüldü" görüntüsü verdiği için kimse kaynağa bakmaz. Kaynağı düzelt, sonra **filtreyi kaldır** (filtre kalırsa yeni kirlilik sessizce gizlenir). | #235 (test global `app`'e kalıcı uç ekliyordu; #217 turunda envanter tarafında elenmişti — OpenAPI okuyan yeni tarama aynı tuzağa düşerdi) |
| L17 | **"Uygulandı" diyen belge, o işin en tehlikeli haliyle yarım kalmış olabilir — çünkü kimse bir daha bakmaz.** Açık bir borç (`⬜ kalan`) er geç ele alınır; **kapatıldığı İDDİA EDİLEN** bir doğruluk hatası ise denetim listesinden düşer, kabul edilmiş risk sanılır ve sessizce üretime çıkar. Bir ADR/rapor "TÜM X yolları artık Y kullanır" diyorsa bu bir iddiadır, kanıt değil: iddiayı **kapsam ölçen statik kapıya** bağla (kaç yer var, kaçı dönüştü, geri kalanı neden muaf) — aksi halde belge doğru, kod yarım kalır. Kural: bir yolun benimseme oranı ölçülmeden "tamam" yazılmaz. | #237 (ADR-042 "tarih üreten TÜM kullanıcı-bağlamlı yollar `user_today` kullanır" dedi; disk 7 router gösterdi, koçun yazdığı işlem kalıcı olarak yanlış güne düşüyordu), #217 (aynı sınıf: "kapsam kilitli" iddiası yazıldığı anda geçersizdi) |
| L18 | **Bağlam taşınmayan imza, unutulmuş bir çağrı değil — kapatılmış bir kapıdır.** `handler(db, user_id, payload)` gibi bir imza kullanıcı bağlamını taşımıyorsa, o katmandaki HİÇBİR kod doğru davranışa **erişemez**; tek tek çağrıları düzeltmeye çalışmak (ya da "burada unutulmuş" demek) kök sebebi ıskalar. Önce bağlamı erişilebilir kıl (id'den türeten yardımcı ya da açık parametre), sonra çağrıları dönüştür. Aynı desen: prompt/sözleşme sık kullanılan yolu bilerek eksik dalın içine sokuyorsa (LLM'e "tarih EKLEME" demek) kusur **en sık akışta** yaşar, kenar durumda değil. | #237 (executor + cashflow/simulation/goal_engine/debt_strategy yalnız `user_id` alıyordu → `user_today` ulaşılamazdı), #221 (aynı imza workspace bağlamını da taşımıyordu) |
| L15 | **Bir sayacın BİRİMİNİ ve KAPSAMINI teste yazdır.** "Bu sayaç neyi sayıyor" sorusu koddan okunarak güvenilir biçimde cevaplanamaz: yorum "paylaşılan" derken sorgu filtreli, ADR "çağrı" derken satır "mesaj" olabilir. Bir eşik/tavan/kotanın sözleşmesi **iki kullanıcı** ve **gerçek alt-işlem sayısı** ile davranış testine bağlanmalı; aksi halde koruma dalı hiç ateşlemeden ölü kalır ve onu gösteren arayüz de ölü olduğu için kimse fark etmez. | #234 (paylaşılan kota kullanıcı-filtreli sayılıyordu → %80/%100 dalları matematiksel olarak erişilemezdi; tavan mesaj sayıyordu → gerçek maliyet 2-3 kat), #212 (muhasebe etiketi çalışma-anı durumundan türetiliyordu) |
| L19 | **Bir güvenlik katmanının "açık" olması, ONU ETKİSİZ KILAN bir yapılandırmayla birlikte yaşayabilir.** Migration doğru, policy doğru, test doğru olabilir — ve katman yine de sıfır iş yapıyor olabilir, çünkü ölçülmeyen bir ÖNKOŞUL (bağlanılan rol, çalışan kullanıcı, aktif profil) yanlıştır. Katmanın VARLIĞINI değil, **önkoşulunu** teste bağla; üstelik önkoşulu bozan tarif genelde dokümanda yazılıdır, yani operatör *dokümanı doğru uygulayarak* savunmayı kapatır. | #238 (12 tabloda ENABLE+FORCE RLS vardı; uygulama bootstrap SUPERUSER ile bağlanıyordu → her policy bypass; aynı yanlış tarif 4 belgede daha) |
| L20 | **Bir gate'in "prod'u temsil ediyorum" diyen yorumu, doğrulanmamış bir köprüdür.** Kurgusunu kendi eliyle yaratan bir kapı (rol, kullanıcı, ortam) prod'un gerçeğini değil kendi kurgusunu ölçer ve yeşil kalır. Gate, prod'un **gerçek kurulum kodunu** çağırmalı. | #238 (`test_rls_postgres.py` rolü elde yaratıp "prod'daki app-rolünü temsil eder" diyordu; gate koşsaydı bile gerçek rolü ölçmeyecekti) |
| L21 | **Bir sinyal "hesaplanıyor" olabilir ve yine de karar veren katmana HİÇ ulaşmayabilir.** Türetilmiş veriyi (tazelik, risk işareti, bayrak) yalnız bir sunum katmanında (router/panel) üretirsen, aynı kaynağı DOĞRUDAN tüketen diğer yollar (LLM bağlamı, motor, snapshot) onu asla görmez — ve "veri var" görüntüsü kimseyi kaynağa bakmaya sevk etmez. Sinyali üretildiği yere değil, **ona göre karar verilen sözleşmeye** koy; sonra kapsam tabanını assert et. | #239 (`is_stale`/`age_text` yalnız `routers/cockpit.py`'de ekleniyordu; koç/premortem/snapshot cockpit'i doğrudan çağırdığı için bayat fiyatı "güncel değer" diye sunuyorlardı) |
| L23 | **Bir şeyin YOKLUĞUNU raporlaması gereken yüzey, envanterini o şeyin ÇIKTISINDAN türetemez.** "Hangi işler var" sorusunu çalışma kayıtlarından (ya da "hangi kullanıcı var"ı log'dan, "hangi entegrasyon var"ı başarılı isteklerden) türeten her uç, tam da bozuk olan öğeyi — hiç çıktı üretmeyeni — göremez ve **boş liste "her şey yolunda" gibi okunur.** Envanter, izlenenden BAĞIMSIZ bir kaynaktan (beyan edilmiş liste) gelmeli; ölçüm ona göre eşleştirilmeli. Yan tuzak: envanter beyandan gelmeye başlayınca liste hep dolu olur — "kaç kayıt var" ile "kaç iş tanımlı" ölçütünü karıştıran eski tüketici (canlı kapı) sessizce hep-yeşile döner, onu da aynı commit'te düzelt. | #240 (`/api/ops/scheduler` iş adlarını `SchedulerRun` tablosundan türetiyordu → hiç kaydı olmayan 3 iş uçta HİÇ yoktu; canlı kapı `bool(isler)` ile "cron çalıştı" sanıyordu) |
| L24 | **İzleme çağrısı işin GÖVDESİNE yazılıyorsa, unutulması an meselesidir — kaydı planlama noktasına bağla.** "Her iş kaydını açar" bir konvansiyon değil, bir sözleşmedir: sarmalayıcı/kayıt noktası yapısal olarak uygularsa yeni iş ekleyen kişi unutamaz. Ve sözleşmeyi **iş listesinin kendisi üzerinden** assert et (her planlı iş için: koştur → kayıt var mı) — "beş işten üçü unutulmuş" ancak listeyi gezen bir kapıyla görülür. Aynı tarama işin *dışarıda* koşan kardeşlerini de kapsamalı (yedek/timer/compose döngüsü): en kritik iş çoğu zaman uygulama sürecinin dışındadır. | #240 (`_kayit_basla` iki job gövdesine elle yazılmıştı; KVKK 90-gün saklama işi dahil 3'ü kayıtsızdı — prod yedeği de yalnız konteyner log'una yazıyordu) |
| L25 | **Aynı gerçek-dünya olayının birden çok girişi varsa, sözleşme YOLA değil OLAYA yazılır.** Bir olayın (tahsilat, ödeme, iptal) etkisi bir yolun içine kodlanırsa, o yol düzeltildiğinde kardeş yol sessizce eski kalır — ve düzeltmenin kendisi "bu iş bitti" hissi yarattığı için kimse ikinciye bakmaz. Etkiyi tek bir servis/modüle çıkar, HER giriş oradan geçsin, pariteyi **iki yolu yan yana koşturan** bir testle kilitle. Fark testi tek yolu doğrulayan testten daha değerlidir: tek yol testi ayrışmayı göremez. | #241 (BUG #113 koç yolunun nakit ayağını eklemişti; panel yolu — kullanıcının fiilen kullandığı "Ödendi" butonu — bayrağı çevirip nakdi hiç hareket ettirmiyordu, alacak tahsilinde Tam Net Değer eriyordu) |
| L26 | **Bir yasağın (dokunulmaz hesap, salt-okunur kayıt, korumalı kaynak) gücü, onu uygulayan guard'ın değil KAYNAĞI SEÇEN kodun sayısı kadardır.** Guard tek yerde olabilir ve doğru çalışabilir; ama korunan kaynağı "varsayılan" olarak seçen beş ayrı sorgu varsa yasak ya delinir ya da her onayda patlayan sessiz çıkmaz sokaklar üretir. Seçimi tek kaynağa topla ve "kendi seçim sorgusunu yazan var mı" diye **statik** kapı koy. | #241 sınıf taraması (5 ayrı "varsayılan nakit/kart hesabı" sorgusu; hiçbiri `is_emanet` dışlamıyordu, üçü sırasızdı → `app/account_rules.py` + `test_varsayilan_hesap_kapisi.py`) |
| L27 | **Bir kapı, ölçtüğünü iddia ettiği listeyi ELLE taşıyorsa ölçmüyordur — listeyi kaynaktan türet.** Bu oturumda AYNI defekt dört ayrı yerde çıktı: veri-işleyen envanteri 4 sağlayıcı adını sabit kodluyordu (yeni ikisi üç hafta beyansız kaldı), export tamlık testi model adlarını fonksiyon KAYNAK METNİNDE arıyordu (yanlış fonksiyonu doğruluyordu), silme yalnız `user_id` kolonlu tabloları geziyordu (farklı isimli kolon = ıskalanan kişisel veri), migration geri-alınabilirlik kapısı elle yazılmış 9 revizyona bakıyordu. Ölçüt: kapı **şemayı / sınıf ağacını / dosya sistemini** gezmeli ve kapsam tabanını assert etmeli; elle liste ancak GEREKÇELİ İSTİSNA olarak, bayatlığı ayrıca ölçülerek kalabilir. | #242 (envanter), #243 (export+silme), #248 (migration) |
| L28 | **"Çökmedim" başarı değildir; "atlandı" da geçti değildir.** Kendi başarısızlığını `skip`'e çeviren test ve tek bir iş bile yapamadığı hâlde `ok=True` kaydeden cron, koruma YOKLUĞUNDAN daha kötüdür: sayıya dahil olurlar, panelde yeşil görünürler, kimse bakmaz. Aynı aile: bağımlılığına hiç dokunmayan sağlık ucu (DB ölüyken 200 döner → otomatik rollback tetiklenmez). Başarı ölçütünü **işin amacına** bağla (kaç hesap güncellendi, hook çağrıldı mı, DB yanıt veriyor mu) ve başarısızlığı görünür kıl (kayıt detayına mesajı yaz, 503 dön). | #248 (D36 ölü test + D37 hep-başarılı cron), #247 (D39 kör sağlık ucu) |
| L22 | **Doğru sinyalin YANLIŞ EŞİĞİ, sinyalin yokluğu kadar zararlıdır — ve tek eşik iki işi birden yapamaz.** Etiketleme (dürüst, ücretsiz, her zaman) ile alarm (pahalı, dikkat harcar) farklı eşiklerdir; ikisini tek sayıya bağlarsan ya rutin durumda gürültü üretir (uyarı yorgunluğu → gerçek kesinti görünmez olur) ya da gerçek arızada susarsın. Eşiği seçerken alanın takvimini (piyasa tatili, hafta sonu, batch penceresi) yaz ve teste koy. | #239 (24s tazelik eşiği alarm eşiği yapılsaydı TEFAS yayın yapmayan her hafta sonu uyarı üretirdi → 24s etiket / 72s alarm ayrımı) |

---

---

## §1.2 KALICI HATIRLATMA LİSTESİ ("Murat unutsa da sistem hatırlar")

Murat'ın direktifi: *"bu ve bunun gibi detayları da masterprompt'u geliştirirsin… ben unutsam da
sen hatırla diye. Ben bir örnek vereceğim ama nicelerini de sen eklersin."*

Kural: **bu liste yalnız büyür.** Akla gelen her "publish öncesi bu da olmalı" maddesi buraya
yazılır, sonra ilgili faza görev olarak bağlanır. Buraya yazılmayan şey unutulmuş sayılır.

| # | Madde | Kaynak | Bağlı faz | Durum |
|---|---|---|---|---|
| H1 | **Yeni kullanıcı kendi verisini + kendi öznel kurallarını kurabilmeli** — sistem tek kişinin OS'u olmaktan çıkıp ürün olmalı | Murat (4 Ağu) | P3.5 | ✅ kayıt→boş dünya→kendi hesabı→kendi kuralı (dayatılan) uçtan uca testli; kalan: kişiselleştirme alanları (H4) |
| H2 | Kodda/prompt'ta gerçek kişi adı, banka markası, kişisel senaryo kalmamalı (statik kapı ile kilitle) | Claude (ölçüldü) | P3.5.1 | ✅ 45 iz temizlendi (yorum/docstring + kullanıcıya görünen placeholder); kapı TÜM app/+frontend/src |
| H3 | Kullanıcının yazdığı kırmızı çizgi, koddaki MC1 kadar sert dayatılmalı | Claude | P3.5.2 | ✅ BUG #192 — rules-as-data, aksiyon öncesi kod-seviyesi dayatma (11 test) |
| H4 | Para birimi / dil / saat dilimi / kategori seti kullanıcı başına | Claude | P3.5.3 | 🟡→✅ **görüntüleme kısmı KAPANDI (BUG #256 / ADR-044, 7 Ağu):** biçimlendirme yedi yerden **tek kaynağa** indi (`app/money_format.py` + `frontend/src/lib/money.js`), 167 backend + 91 frontend ham "TL" sabiti kalktı, **grounding para birimine bağlandı** (etiket değişince doğrulama sessiz-yeşile düşüyordu). TRY kilidi BİLİNÇLİ kalıyor: çoklu para birimiyle hesap tutma (kur çevrimi) ayrı ADR ister. Saat dilimi zaten ✅ (#197/#237). **Kalan:** dil/i18n ve kategori seti — açık |
| H5 | Boş-durum kırılmamalı + **isteğe bağlı** demo veri (tek tuşla sil) | Claude | P3.5.5 | ✅ BUG #194 — `/api/onboarding/demo`; kaldırma KULLANICININ verisine dokunmaz (testli) |
| H6 | Hesabını silen kullanıcının verisi **gerçekten** silinmeli (KVKK "unutulma"), yedeklerdeki durum yazılı olmalı | Claude | P3.4 / P4.4 | ✅ **BUG #204** — KIRIKTI: verisi olan kullanıcı hesabını silemiyordu (FK ihlali). Şema-türetimli determinist silme + 4 test |
| H7 | Veri dışa aktarma **taşınabilir** formatta (JSON/CSV) ve tam olmalı | Claude | P3.4 | ✅ doğrulandı (14 tablo, goal çocukları dahil) |
| H8 | Kullanıcı başına LLM maliyet tavanı — bir kullanıcı bütçeyi tüketip diğerlerini kilitleyememeli | Claude | P3.1 | ✅ ADR-041 / BUG #188 |
| H9 | Koça yazılan metin **prompt injection** taşıyabilir; koç başkasının verisine ulaşamamalı | Claude | P2.8 | ✅ **BUG #257 / ADR-045** — ölçüldü: kullanıcı, hesap adı/kural başlığı gibi alanlarla koç bağlamında **kendi `## SİSTEM` bölümünü açabiliyordu** (paylaşılan workspace'te başka üyenin koçunu etkiler). `app/prompt_safety.guvenli_metin` ile yapı taşıyan işaretler nötrlendi (satır sonu/başlık/çit/rol-token/görünmez karakter); sınıf taraması kalıcı yolu da buldu (insight → prompt → insight). 15 test + mutasyon + kapsam tabanı. Kabul edilen risk artık yalnız 'model ikna edilebilir' |
| H10 | E-posta şablonları ürün kimliğiyle konuşmalı, kişisel imza taşımamalı | Claude | P3.5.1 | ✅ **BUG #205** — şifre sıfırlama şablonunda kişisel gmail vardı; `SUPPORT_EMAIL` + kapı genişletildi |
| H11 | Şifre sıfırlama/oturum akışı gerçek e-posta ile uçtan uca denenmeli (SMTP canlı) | Claude | P6.3 | ⬜ |
| H12 | Kayıt sırasında KVKK rızası sürüm/tarih ile saklanmalı (mevcut) + metin **yayında erişilebilir** olmalı | Claude | P4.3 | ✅ BUG #191 (v2) |
| H13 | "Yatırım tavsiyesi değildir" uyarısı koç arayüzünde de görünmeli (yalnız sözleşmede değil) | Claude | P4.2 | ✅ koç paneli + kayıt ekranı |
| H14 | Yedekten **geri yükleme provası** yapılmadan yedek sayılmaz | Claude | P5.1 | ✅ SQLite + **PostgreSQL (prod yolu)** provası otomatik koşuyor |
| H15 | Beta kullanıcısının bildirdiği hata, geliştiriciye **kullanıcı verisi sızmadan** ulaşmalı | Claude | P7 | ✅ **BUG #209** — geri bildirim kimseye ULAŞMIYORDU; `scripts/beta_triage.py` (hata kayıtlarıyla yan yana, e-posta maskeli) |
| H16 | Fiyat sağlayıcıları (TEFAS/BIST/döviz) çöktüğünde uygulama çalışmaya devam etmeli, sayı **bayat** işaretlenmeli | Claude | P5.2 | ✅ **BUG #211** — fon/hisse zaten bayat işaretliydi (`fund_tracker.is_stale` → Cockpit "N eski"); **döviz** kör noktaydı: sağlayıcı düşer düşmez kur TAMAMEN kayboluyordu. Son bilinen değer artık `bayat`/`yas_dakika` ile döner, koç "şu anki" DEMEZ, 12 saatten eskisi hiç sunulmaz (8 test) |
| H17 | Çok kullanıcı aynı anda koç kullanınca sağlayıcı kotası/kilit sorunu olmamalı | Claude | P3.1 / P8 | ✅ **BUG #212** — iki defekt: (a) kota akışı "oku → LLM çağır → yaz" olduğu için hakkı 1 kalan kullanıcı paralel istekle tavanı deliyordu (ölçüldü: `[200,200,200]`); rezervasyon desenine geçildi. (b) muhasebe etiketi `FallbackProvider`'ın **paylaşılan** durumundan okunuyordu → `fallback(gemini)` limit tablosunda yok → günlük kota koruması sessizce ölüydü (5 test) |
| H18 | Kullanıcı silme/çıkarma sonrası workspace sahipliği ortada kalmamalı | Claude | P3.4 | ✅ **BUG #206** — VERİ KAYBI: aile workspace'i sahibiyle siliniyordu (eşin verisi yok oluyordu). Sahiplik devri + 3 test |
| H19 | **`alembic/env.py` config URL'ini yok sayıyor** — test/script içinden migration çağrısı GERÇEK DB'ye gidebilir (BUG #196) | Claude (ölçüldü 5 Ağu) | P5.4 | ✅ düzeltildi + veri-dolu migration provası (4 test) |
| H20 | Onboarding UI: demo veri + ilk-kurulum rehberi arayüze bağlanmalı | Claude | P3.3 | ✅ Cockpit'te boş-durum kartı (sıralı yol + örnek veriyle gez/kaldır) |
| H21 | Kullanıcı-tanımlı kural arayüzü: kural tiplerini UI'dan seçebilmeli | Claude | P3.5.2 | ✅ kırmızı-çizgi formunda "otomatik uygulansın mı?" seçimi (3 tip) |
| H22 | **Hiçbir güvenlik sınırı tek katmanda (ters vekilde) yaşamamalı** — nginx atlanabilir, yapılandırma sessizce değişebilir | Claude (ölçüldü 5 Ağu) | P2.9 | ✅ **BUG #213** — gövde sınırı YALNIZ `client_max_body_size 1m` idi; uygulama katmanına taşındı (chunked dahil), nginx şablonu testle kilitlendi |
| H23 | **Operatör betanın kullanılıp kullanılmadığını görebilmeli** — beta'nın en olası başarısızlığı gürültülü çöküş değil SESSİZ TERK'tir | Claude (ölçüldü 5 Ağu) | P7/P8 | ✅ **BUG #214** — yalnız şikâyet edeni gören `beta_triage` vardı; `scripts/beta_metrics.py` (onboarding hunisi, sessiz terk, tutunma, koç hata oranı — **yalnız sayı, PII testle yasak**) |
| H24 | **Kullanıcının GÖRDÜĞÜ katman da boş/hata durumunda sınanmalı** — backend uçları sağlam diye arayüz sağlam değildir; kullanıcı beyaz ekran görür, süit yeşil kalır | Claude (ölçüldü 5 Ağu) | P3.2 | ✅ **BUG #218/#219** — 13 panel hem boş-veri hem hata yolunda taranıyor (`empty-state` + `error-state`, 54 test); mock'lar tahmin değil **gerçek boş-kullanıcı cevapları** (fixture + sözleşme kayması kapısı) |
| H25 | **Kapsam ölçülmeden kapı sayılmaz** — "hepsini tarar" diyen her kapıya taban (minimum sayı) assert et; kütüphane sürümü kapıyı sessizce körleştirebilir | Claude (ölçüldü 5 Ağu) | P0/P1 | ✅ **BUG #217** — iki kapı (boş-durum taraması + izolasyon matrisi kapsamı) fiilen ölüydü; envanter OpenAPI'ye taşındı + taban assert (L11) |
| H26 | **Kullanıcıya YAYINLANAN her beyan ile GERÇEK davranış arasına test koy** — gizlilik/veri-işleyen/KVKK metinleri, "şunu göndermiyoruz" cümleleri ve kurulum dokümanlarının vaatleri. Belge elle senkron kalmaz; yanlış beyan hukuki risktir | Claude (ölçüldü 5 Ağu) | P4 | ✅ **BUG #231** — envanter "ham işlem listesi gönderilmez" diyordu, gerçekte açıklamalar + üçüncü kişi adları gidiyordu. Kapı artık gerçek koç bağlamını üretip beyanla karşılaştırıyor (L9) |

---

## §2. "PUBLISH EDİLEBİLİR" TANIMI (Definition of Done)

Publish tek bir olay değil, **üç kapılı** bir merdivendir. Her basamak, bir öncekinin kapıları
yeşil olmadan açılmaz.

### Basamak A — KAPALI BETA (davetli, 3-10 kişi, tanıdıklar)
Gereksinim: veri izolasyonu ispatlı, güvenlik taban seviyesi geçilmiş, maliyet kontrolü var,
hukuki taban metinleri var, canlı ortam ayakta ve yedekli.
→ Fazlar: **P0, P1, P2, P3, P4, P5, P6, P7**

### Basamak B — AÇIK BETA (bağlantıyı bilen herkes, kayıt açık)
Gereksinim: A'nın tüm kapıları + gerçek kullanıcı davranışıyla sınanmış operasyon (hata izleme,
kota, kötüye kullanım savunması, destek/geri bildirim döngüsü kanıtlı işliyor).
→ Fazlar: **P8**

### Basamak C — PUBLISH (duyuru / Play Store TWA / dizinlere ekleme)
Gereksinim: B'nin tüm kapıları + sürüm yönetimi, geri alma provası, dokümantasyon, destek kanalı.
→ Fazlar: **P9**

**Bu goal'in hedefi: A ve B'nin TAMAMI + C'nin teknik hazırlığı.**

---

## §3. FAZ HARİTASI

Her faz: **GİRİŞ ŞARTI → GÖREVLER → ÇIKIŞ KAPISI (kanıtlı) → ÇIKTI**.
Kapı kanıtı **komut + gerçek çıktı** demektir; "yaptım" demek kanıt değildir.

---

### P0 — TEMEL DOĞRULAMA (baseline)
**Giriş:** yok (ilk faz).
**Görevler:**
1. Tam test süiti koş, gerçek sayıyı kaydet (pytest + vitest + e2e).
2. `alembic upgrade head` temiz DB'de koş (`scripts/test_fresh_db_migration.py`).
3. `git status` temiz mi; bekleyen yerel değişiklik varsa karara bağla (commit / revert).
4. Mevcut açık borçları listele: `KANIT YOK` kayıtları, açık backlog P0/P1 maddeleri.
**Çıkış kapısı:** ✅ tüm testler yeşil + migration temiz + çalışma ağacı bilinçli durumda.
**Çıktı:** bu dosyada §11 tablosunun ilk satırı + baseline sayıları.

---

### P1 — ÇOK-KULLANICI VERİ İZOLASYONU (#1 RİSK)
**Giriş:** P0 yeşil.
**Neden #1:** Tek-kullanıcı kurulumda izolasyon hataları **görünmezdir**; ikinci gerçek kullanıcı
girdiği an veri sızar. Wave-5'te statik+runtime kilit kuruldu ama kapsamı **eksikti** (bkz. BUG #162).

**Görevler:**
1. **Statik tam tarama:** `app/**/*.py` içindeki HER scoped-model sorgusu (`db.query(M)`, `select(M)`)
   üç kategoriden birine girmeli: (a) scope'lu, (b) sahiplik doğrulanmış id-lookup, (c) açık
   `# scope-exempt: <gerekçe>`. Kategorisiz tek satır kalmayacak.
2. **Statik gate'i kalıcılaştır:** `tests/test_scope_enforcement.py` genişletilir — **filtresiz sorgu**
   ihlali de testi kırar (mevcut gate yalnız scope'suz `user_id ==` yakalıyordu; #162'yi kaçırdı).
3. **Runtime çapraz-kullanıcı matrisi:** iki gerçek kullanıcı (A, B) + **her yazma/okuma endpoint'i**
   için B'nin token'ıyla A'nın kaynağına erişim denemesi → 403/404 beklenir. Endpoint listesi
   `app.main`'in route tablosundan **otomatik türetilir** (yeni endpoint eklenince test kendiliğinden kapsar).
4. **Arka plan katmanları:** scheduler/cron, coach_insights, backfill, action_executor, goal_rules —
   kullanıcı sınırını aşan iş var mı, her biri ayrı doğrulanır.
5. **RLS (PostgreSQL) ikinci savunma:** `tests/pg_gate.py` yeşil; RLS politikası kapsamdaki her tabloda.
6. **Bulunan her açık:** BUG numarası + TDD (önce kırmızı test) + fix + ledger.
**Çıkış kapısı:** ✅ statik gate yeşil + otomatik endpoint matrisi yeşil (atlanan endpoint sayısı 0
veya her atlama gerekçeli) + pg RLS gate yeşil + açık bug 0.
**Çıktı:** `docs/kalite-seruveni/izolasyon-denetimi-raporu.md`.

---

### P2 — GÜVENLİK REVIEW
**Giriş:** P1 yeşil.
**Görevler (her başlık ayrı kanıtlanır):**
1. **Kimlik/oturum:** JWT süre/refresh/iptal (`RevokedToken`), şifre politikası, reset akışı,
   OAuth callback state/PKCE, oturum sabitlemesi.
2. **Yetki:** rol matrisi (owner/editor/viewer) her yazma endpoint'inde dayatılıyor mu (BUG #160 dersi).
3. **Girdi:** Pydantic sınırları, para alanları (`schema_types` sonlu-değer), SQL enjeksiyonu
   (raw `text()` kullanımları), XSS (frontend'de `dangerouslySetInnerHTML` var mı), yol/dosya.
4. **Sırlar:** `.env.prod` fail-fast (BUG #157), repo'da sızmış sır taraması (git geçmişi dahil),
   log'a sır/PII sızması.
5. **Taşıma/başlıklar:** HTTPS zorunluluğu, HSTS/CSP/X-Frame, CORS listesi prod'da dar mı, cookie flag'leri.
6. **Oran sınırlama:** login/register/reset/coach uçlarında bucket'lar; brute-force senaryosu testi.
7. **Bağımlılık:** `pip-audit`/`npm audit` — kritik/yüksek açık 0 veya gerekçeli.
8. **LLM'e özel:** prompt injection (kullanıcı metni koça gidiyor), koçun başkasının verisini
   bağlama alması, `propose_action` ile yetkisiz yazma (KURAL SIFIR + Master Checkpoint).
**Çıkış kapısı:** ✅ 8 başlığın her biri kanıtlı; kritik/yüksek bulgu 0; orta bulgular ya kapatılmış
ya da ADR/backlog'a gerekçeli kaydedilmiş.
**Çıktı:** `docs/kalite-seruveni/guvenlik-review-publish.md`.

---

### P3 — ÇOK-KULLANICI OPERASYONEL GERÇEKLİK
**Giriş:** P2 yeşil.
**Görevler:**
1. **Per-user LLM maliyet/kota guard'ı** — koç mesajı başına 2 LLM çağrısı (iki-geçiş mimarisi).
   Kullanıcı başına günlük/aylık limit + limit aşımında **nazik** davranış (koç kapanmaz, düşer).
   `ApiCallLog` şu an yalnız kayıt tutuyor → **dayatma** eklenecek. ADR yazılacak.
2. **Yeni kullanıcı sıfırdan çalışıyor mu:** kayıt → personal workspace → boş cockpit → ilk hesap →
   ilk işlem → koç anlamlı cevap. **Boş-veri hali** her panelde kırılmadan görünmeli (0/None/NaN).
3. **Onboarding akışı:** ilk giriş rehberi + örnek veri seçeneği + "buradan başla" yönlendirmesi.
4. **Hesap yaşam döngüsü:** şifre değiştir, e-posta doğrula, **hesabı sil (veri dahil)**, **veriyi dışa aktar**.
5. **Kötüye kullanım:** kayıt spam'i, davet suistimali, dev payload, dosya/alan boyut sınırları.
**Çıkış kapısı:** ✅ kota dayatması testli + sıfırdan kullanıcı uçtan uca testli + sil/dışa-aktar çalışıyor.
**Çıktı:** ADR (LLM kota) + testler + onboarding paneli.

---

### P3.5 — ÜRÜNLEŞME: TEK-KULLANICI DNA'SININ SÖKÜLMESİ ⚠️ **YAYIN-ENGELİ**
**Giriş:** P1 yeşil (izolasyon), P3 ile paralel yürür.
**Neden (Murat'ın 4 Ağustos direktifi):** Sistem bugün "giriş yapılabilen Murat'ın OS'u"dur.
Publish edilebilir ürün, **her kullanıcının kendi finansal DNA'sını** (hesapları, kuralları,
kırmızı çizgileri, dili, alışkanlıkları) kurabildiği sistemdir. Bir yabancı kayıt olduğunda
uygulamanın hiçbir yerinde başkasının hayatının izine rastlamamalı — ne örnek veride, ne koç
metninde, ne de kod içindeki sabit kurallarda.

**ÖLÇÜLEN GERÇEKLİK (2026-08-04, R3 taraması — varsayım değil):**
- `app/coach.py` sistem prompt'unda **gerçek kişi adı** örnek olarak gömülü ("Efe 9.000 ödedi").
- `app/action_executor.py:98` niyet regex'inde **banka markaları sabit** (`enpara`, `ziraat`) —
  başka bankayı kullanan kullanıcının cümlesi eşleşmez.
- `MC1`/`MC3` gibi **kural numaraları koda gömülü** (`MC1 = emanet dokunulmaz`); kullanıcının
  kendi yazdığı kırmızı çizgi aynı güçle dayatılmıyor.
- `scripts/setup_data.py` **kanonik Murat verisi** yükler (drop_all'lı) — yeni kullanıcıya asla
  bulaşmamalı, ama "örnek veri" ihtiyacı da karşılanmamış durumda.
- `get_current_user` **AUTH kapalıyken ilk kullanıcıya düşer** — production'da bu yol kesin kapalı olmalı.
- ✅ Kayıt akışı doğru çalışıyor: `register` → personal workspace + owner membership (doğrulandı).

**GÖREVLER:**
1. **Kişiye özel iz taraması + kalıcı kapı:** `app/`, `frontend/src/`, prompt metinleri ve
   e-posta şablonlarında gerçek kişi adı / banka markası / kişisel senaryo aranır; temizlenir.
   Ardından **statik test** eklenir (yasaklı sözcük listesi) — yeniden sızarsa süit kırılır.
2. **Kullanıcı-tanımlı kural motoru:** Kullanıcı kendi kırmızı çizgisini/kuralını UI'dan yazar,
   `rules_engine`/`action_executor` bunu **genel** biçimde dayatır (sabit MC numarası yok).
   Emanet/dokunulmazlık bir **hesap özelliği** (`is_emanet`) olarak kalır — kişiye değil, veriye bağlı.
   ADR yazılır (D1: 2-3 sektör referansı — kullanıcı-tanımlı kural/politika motorları).
3. **Kişiselleştirme katmanı:** hitap adı, para birimi, dil/locale, saat dilimi, maaş günü,
   ekstre/ödeme günleri, kategori seti — hepsi **kullanıcı başına**; hiçbiri kodda sabit değil.
4. **Koç kişiselleştirmesi:** koç metni kullanıcının kendi verisinden konuşur; örnek senaryolar
   jenerik veya kullanıcının kendi geçmişinden üretilir.
5. **Boş-durum + örnek veri:** yeni kullanıcı boş sistemde kırılmadan gezebilir; **isteğe bağlı**
   demo veri seti yükleyebilir ve **tek tuşla silebilir** (kendi verisine karışmadan).
6. **Sıfırdan kullanıcı uçtan uca testi:** temiz DB + yeni kayıt → hesap ekle → işlem gir →
   kendi kuralını yaz → koça sor → kural dayatılıyor mu. Otomatik test olarak kalır.
7. **Çok-kullanıcı eşzamanlılık:** iki kullanıcı aynı anda çalışırken kuralların/koçun
   birbirine karışmadığı doğrulanır (P1 matrisi + koç bağlamı).
**Çıkış kapısı:** ✅ yasaklı-iz taraması temiz (statik test kilitli) + kullanıcı-tanımlı kural
uçtan uca dayatılıyor + kişiselleştirme alanları kullanıcı başına + sıfırdan-kullanıcı testi yeşil.
**Çıktı:** ADR (kullanıcı-tanımlı kurallar) + `docs/kalite-seruveni/urunlesme-denetimi.md`.

---

### P4 — HUKUKİ / UYUM TEMELİ
**Giriş:** P3 devam ederken paralel yürüyebilir.
**Görevler:**
1. Gizlilik Politikası (KVKK uyumlu; hangi veri, neden, nerede, ne kadar süre, kiminle — LLM sağlayıcı
   **açıkça** yazılır).
2. Kullanım Şartları + **"lisanslı yatırım/finans tavsiyesi değildir"** uyarısı (uygulama içinde de görünür).
3. Açık rıza akışı: kayıtta onay kutusu, sürüm/tarih kaydı (`docs/legal/kvkk-consent-v1.md` mevcut — UI'ya bağlanacak).
4. Veri sahibi hakları: erişim (dışa aktar), silme, düzeltme — P3.4 ile aynı uçlar.
5. Veri işleyen envanteri: LLM sağlayıcıları, e-posta (SMTP), fiyat sağlayıcıları, hosting.
**Çıkış kapısı:** ✅ 3 metin yayında + rıza akışı çalışıyor + envanter yazılı.
**Çıktı:** `docs/legal/` + frontend sayfaları.

---

### P5 — DAYANIKLILIK & GÖZLEMLENEBİLİRLİK
**Giriş:** P2 yeşil.
**Görevler:**
1. **Yedek + GERİ YÜKLEME PROVASI** (yedek almak yetmez; geri yükleme denenmeden yedek yoktur).
2. Hata izleme (uygulama hatası sessizce kaybolmasın) + yapılandırılmış log + PII sızmaması.
3. Sağlık/uptime uçları, scheduler canlılığı (cron çalıştı mı görünür olsun).
4. Migration güvenliği: canlı veriyle `alembic upgrade` provası + geri alma yolu.
5. Kapasite/limit: eşzamanlı kullanıcı, DB bağlantı havuzu, LLM eşzamanlılığı.
**Çıkış kapısı:** ✅ geri yükleme provası kanıtlı + hata izleme çalışıyor + migration provası kanıtlı.

---

### P6 — CANLI ORTAM (İNSAN-KAPISI karışık)
**Giriş:** P1-P5 yeşil.
**Görevler:**
1. Sunucu provizyonu (**İNSAN-KAPISI** — §9.1).
2. Deploy runbook koşumu (`docs/deployment/runbook.md`), HTTPS/Let's Encrypt, servisler ayakta.
3. Canlı doğrulama gate'leri: sağlık, login, cockpit, koç, cron 24s, yedek.
4. **PWA canlı gate'leri** (Wave-8'den devir): Lighthouse PWA, "ana ekrana ekle", offline shell,
   gerçek mobil viewport uçtan uca.
**Çıkış kapısı:** ✅ canlı HTTPS'te uçtan uca kullanım + PWA gate'leri + 24 saat cron kanıtı.

---

### P7 — KAPALI BETA (Basamak A tamamlanır)
**Görevler:** davet akışı, 3-10 davetli, geri bildirim döngüsü (FEAT-033 widget'ı canlı),
hata/istek triyajı, ilk hafta düzeltme turu, kullanım metrikleri (gizlilik-dostu).
**Çıkış kapısı:** ✅ en az 3 gerçek kullanıcı en az 1 hafta kullandı + kritik bulgu 0 + geri bildirimler triyajlı.

---

### P8 — AÇIK BETA (Basamak B)
**Görevler:** kayıt açılır, kota/abuse savunmaları gerçek trafikte doğrulanır, destek kanalı,
sürüm notları, durum sayfası, ölçeklenme gözlemi.
**Çıkış kapısı:** ✅ açık kayıtla 2 hafta olaysız + kritik bulgu 0.

---

### P9 — PUBLISH (Basamak C)
**Görevler:** sürümleme + değişiklik günlüğü, geri alma provası, Play Store TWA paketi (opsiyonel,
ADR-040), duyuru metni, dokümantasyon (kullanıcı rehberi güncel), destek/iletişim.
**Çıkış kapısı:** ✅ **GOAL TAMAM — PUBLISH**.

---

## §4. YÜRÜTME PROTOKOLÜ (her görev için)

1. **Oku, varsayma.** İlgili dosyayı/komutu gerçek çalıştır. (R3)
2. **TDD.** Bug/özellik → önce başarısız test, sonra fix, sonra yeşil kanıtı.
3. **Bug konvansiyonu.** Sıradaki numara + dosya docstring'i `GUNCELLEMELER` + inline yorum +
   `docs/kalite-seruveni/uygulanan-fixler.md` satırı.
4. **Regresyon.** Değişen alanın süiti + ardından tam süit. Kırmızıysa faz ilerlemez.
5. **Commit.** Anlamlı mesaj, pre-commit hook'u atlama yok (`--no-verify` yasak).
6. **Kayıt.** §11 durum tablosu + `milestone-log.md` güncellenir; kanıt komutu ve çıktısı yazılır.
7. **Kapı.** Kapı ölçütü **ölçülebilir** olmalı ("çalışıyor gibi" değil, "şu komut şu çıktıyı verdi").

### §4.1 Yasak gerekçeler (görülürse görev reddedilir)
> "MVP için yeterli" · "pratikte olmaz" · "şimdilik böyle kalsın" · "sonra bakarız" ·
> "test yazmaya değmez" · "zaten çalışıyordur" · "büyük dosya, örneklem yeter" ·
> "kullanıcı bunu yapmaz" · "tek kullanıcı var nasılsa"

---

## §5. PARALEL AJAN PROTOKOLÜ

Murat paralel çalışmayı onayladı. Ajanlar **keşif ve tarama** için kullanılır, **karar** için değil.

- **Ne zaman ajan:** geniş tarama (çok dosya/dizin), bağımsız denetim boyutları, çok sayıda
  endpoint/dosyanın aynı ölçütle taranması, birbirine bağımsız iş parçaları.
- **Ne zaman ajan DEĞİL:** mimari karar, bug fix'in doğruluğu, kapı geçme kararı — bunlar bende kalır.
- **Ajan brief şablonu:** (1) tek cümle görev, (2) tam kapsam (dosya/dizin listesi), (3) aranan
  ölçüt, (4) beklenen çıktı formatı, (5) **"bulgunu dosya:satır ile kanıtla"**, (6) yasak: fix yapma.
- **AJAN RAPORU KANIT DEĞİLDİR.** Her ajan bulgusu, kapıya sayılmadan önce **benim tarafımdan**
  dosya/komut ile doğrulanır. Doğrulanamayan bulgu düşer.

---

## §6. KANIT FORMATI

Her kapı kaydı şu üç parçayı içerir:

```
KOMUT   : .\venv\Scripts\python.exe -m pytest tests/ -q
ÇIKTI   : 1254 passed, 1 skipped in 92.4s
YORUM   : P1 statik+runtime izolasyon gate'leri dahil; kırmızı yok.
```

Kanıt üretilemeyen madde `KANIT YOK` etiketiyle §11'e yazılır ve **kapı geçilmez**.

---

## §7. RİSK KAYDI (canlı — yeni risk çıkınca eklenir)

| # | Risk | Etki | Karşılık | Durum |
|---|---|---|---|---|
| R1 | Çok-kullanıcı veri sızıntısı | Kritik (yasal + itibar) | P1 statik gate + runtime matris + RLS | 🟡 P1'de |
| R2 | LLM maliyet patlaması | Yüksek (para) | P3 per-user kota + Ollama yedeği | ⬜ |
| R3 | KVKK ihlali | Yüksek (yasal) | P4 metinler + rıza + silme/dışa-aktarma | ⬜ |
| R4 | Veri kaybı | Kritik | P5 yedek + **geri yükleme provası** | ⬜ |
| R5 | Koçun yanlış finansal yönlendirmesi | Yüksek | ADR-001 + grounding + "tavsiye değildir" | 🟡 |
| R6 | Tek kişilik bakım yükü | Orta | P8 destek kanalı + hata izleme | ⬜ |
| R7 | **Ürün "birinin kişisel sistemi" gibi hissettiriyor** (yabancı kullanıcı kendi hayatını kuramıyor) | Yüksek (ürün ölür) | P3.5 ürünleşme + §1.2 hatırlatma listesi | 🟡 |

---

## §8. KAPSAM DIŞI (bilinçli — kapsam kayması önlemi)

- Native mobil uygulama (ADR-040: PWA kararı; TWA yalnız P9 opsiyonu).
- Ödeme/abonelik altyapısı (ücretsiz kapalı/açık beta).
- Çok-dilli arayüz (Türkçe; alan adları Türkçe korunur).
- Kripto/çoklu-varlık genişlemesi (ADR-031 vizyonu — publish sonrası).

---

## §9. İNSAN-KAPISI (KURAL 3 istisnaları — YALNIZ bunlar delege edilir)

Bunlar asistan araci'un yapamayacağı gerçek elle görevlerdir. Her biri için Murat'a **net talimat**
verilir, beklenen çıktı yazılır, geri dönene kadar **başka fazlar paralel yürür**.

1. **§9.1 Sunucu provizyonu** — Oracle Free Tier hesabı/VM/SSH anahtarı. (P6)
2. **§9.2 Alan adı** — domain kaydı + DNS A kaydı. (P6)
3. **§9.3 Canlı sırlar** — `.env.prod` içeriği **sunucuda** oluşturulur; **chat'e düşmez**. (P6)
4. **§9.4 Canlı DB üzerinde yıkıcı işlem onayı** — silme/geri yükleme provası. (P5/P6)
5. **§9.5 Üçüncü taraf hesapları** — LLM API anahtarı, SMTP, (varsa) hata izleme servisi kaydı. (P3/P5)
6. **§9.6 Beta davetlileri** — gerçek insanlara davet göndermek. (P7)

**Otonom para harcama ve sunucu satın alma YASAK.**

---

## §10. MASTERPROMPT'UN KENDİNİ GELİŞTİRMESİ (Murat'ın 3. adımı)

Her faz kapanışında **10 dakikalık geriye-bakış** yapılır ve bu dosya güncellenir:

- Bu fazda **kaçırdığım** ne vardı? → yeni görev/kapı olarak eklenir.
- Hangi kapı **ölçülemez** çıktı? → ölçülebilir hale getirilir.
- Hangi kural işe yaramadı / eksikti? → §1.1'e eklenir.
- Yeni risk çıktı mı? → §7'ye eklenir.

**Kısıt:** güncelleme **yalnız ileri yönlü**. Bir kapıyı kaldırmak, gevşetmek, kapsamı daraltmak
**yasaktır**. Yalnız şu üç yön serbest: (a) kapı **ekleme**, (b) kapıyı **daha ölçülebilir** yapma,
(c) sırayı **verimlilik** için değiştirme (kapı sayısı azalmadan). Her güncelleme §12'ye satır düşer.

---

## §11. DURUM TABLOSU (canlı — tek doğruluk kaynağı)

### §11.0 KALDIĞIMIZ YER (yeni oturum buradan devam eder — 6 Ağustos 2026, akşam turu)

> **7 AĞUSTOS 2026 — H4 ve H9 KAPANDI (§11 açık listesinin 5. ve 6. maddeleri).**
> - **BUG #256 / ADR-044 — para birimi tek kaynak.** Biçimlendirme yedi ayrı yerde kodluydu;
>   167 backend + 91 frontend ham "TL" sabiti kalktı. **Asıl bulgu:** `grounding` deseni "TL"
>   literaline gömülüydü → para birimi değişse doğrulama `{"ok": True}` ile sessiz-yeşile
>   düşerdi; ayrıca koç bağlamının yatırım K/Z ve kart borcu satırları **etiketsiz** tutar
>   yazıyordu (hiç denetlenmiyorlardı). TRY kilidi bilinçli olarak KALDI.
> - **BUG #257 / ADR-045 — prompt enjeksiyonu yapı savunması.** Kullanıcı, hesap adı gibi bir
>   alanla koç bağlamında **kendi `## SİSTEM` bölümünü** açabiliyordu; paylaşılan workspace'te
>   bu, başka bir üyenin koçunu etkiler. Sınıf taraması kalıcı yolu da buldu (insight → prompt
>   → insight). `app/prompt_safety.guvenli_metin` yapı taşıyan işaretleri nötrler, içeriği
>   sansürlemez.
> - **Taban:** 2105 passed / 18 skipped + 159 vitest (8'i yeni) + `npm run build` yeşil.
> - **Kalan açık iş:** onboarding rehberi (P3), kapasite sınırları (P5), H11 canlı SMTP
>   (insan-kapısı), backlog'un 272 açık maddesi ve P6-P9 insan-kapısı.
>
> **📌 7 AĞUSTOS 2026 — DEVİR BELGESİ + ÜÇ YAZILI KARAR (önce bunları oku)**
>
> **(0) Tam devir belgesi:** `docs/kalite-seruveni/master-durum-raporu-2026-08-06.md` — 31.668 satır,
> 215 dosya INLINE gömülü (46 ADR, 12 charter, 521 backlog maddesi, 76 denetim raporu, MCP graph'ın
> tamamı, 565 commit'lik git log). Sıfırdan gelen bir oturum için tek dosya yeterlidir.
>
> **(1) MİLESTONE/TAG DİSİPLİNİ BIRAKILDI.** 98 tag'in tamamı ≤ 18 Tem 2026; 4-6 Ağustos'taki 103
> commit tag'siz ve `milestone-log.md`'ye yazılmadı. Bu **bilinçli metodoloji değişimidir, çürüme
> değildir** — ama bugüne kadar hiçbir yerde yazılı değildi (master rapor YANILGI-7). İş artık
> **P0-P9 fazı + D-bulgu kodu + BUG numarası** ile yürür; `milestone-log.md` tarihsel arşivdir.
>
> **(2) MCP MEMORY = TARİHSEL ARŞİV.** Graph 18 Tem 18:14'te dondu; `.mcp-sync-pending.log`'da 186
> commit bekliyor (14 Tem → 6 Ağu). Capture (git hook) çalışıyor, FLUSH (elle) hiç koşulmadı — yani
> izleme çağrısı işin gövdesine yazılmıştı (**L24**). **Karar:** MCP tek gerçek kaynak değildir;
> güncel durum = repo + master rapor. 186 satırlık birikim özet olarak MCP'ye **yazılmadı** (ikinci
> bir gerçek kaynak üretmek borcu ödemez, çoğaltır). Ledger büyümesini gösteren araç:
> `scripts/mcp_sync_report.py`.
>
> **(3) TEK BUG ENVANTERİ = `uygulanan-fixler.md`.** Repoda 235 benzersiz BUG numarası var, ledger'da
> 114'ü (YANILGI-5). Geriye dönük toplama yapılmadı; bundan sonra her numara ledger'a yazılır.
>
> **Düzeltilen bayat sayılar:** coverage %92 → **%93** (ölçüldü), backlog toplamı 520 → **521**,
> `PROJE.md`'deki "Aktif goal: WAVE-8" satırı → "Aktif hat: PUBLISH YOLU".

**Repo durumu:** çalışma ağacı TEMİZ, her şey commit'li ve **origin'e push'lu**.
**Test tabanı:** `2045 passed, 18 skipped` (backend) + `151 passed` (vitest) + 4 e2e
(Playwright — 2'si bugün eklendi, yerelde koşuldu). Kırmızı yok.
Skip artışı bilinçli: D38 kapısı artık TÜM migration'ları geziyor, 10 bilinen-eski sürüm
gerekçeli istisna olarak skip'liyor.

**Bu oturumda (6 Ağu, akşam) 14 iş kapandı — biri canlı kullanıcı bildirimi, dokuzu denetim
bulgusu, dördü kalite/kapı borcu:**
- **#241 (KULLANICI BİLDİRİMİ):** panelden "Ödendi" işaretlenen alacak nakde HİÇ geçmiyordu
  → tek kaynak `app/services/debt_settlement.py` + `app/account_rules.py`; **canlı veri
  onarıldı** (nakit 1.963,52 → 6.963,52 TL) ve **gerçek tarayıcıda** doğrulandı (e2e + ekran).
- **#242 (D25):** veri-işleyen envanteri "kodla kilitli" diyordu ama 4 ismi sabit kodluyordu →
  kapı koddan türetiyor; sınıf taraması **Google/GitHub kimlik sağlayıcılarının envanterde
  hiç olmadığını** buldu (üstelik §4 "harici kimlik sağlayıcı YOK" diyordu).
- **#243 (D26+D27+D28):** export şifre hash'ini döküyor, iki tabloyu atlıyor, silme e-postayı
  bırakıyordu → `app/data_subject.py` (şemadaki her tablo sınıflandırılmış; export tek uygulama).
- **#244 (D29):** maskeleme yarısını kaçırıyordu ve log dosyasına hiç uygulanmıyordu.
- **#245 (D30):** `.env.prod.example` placeholder'ı fail-fast'i ve canlı kapıyı geçiyordu.
  *(Aynı oturumda düzeltme: ilk fix `live_gate`'i import yüzünden ÇÖKERTMİŞTİ — script
  koşturulunca görüldü; bağımsızlık artık teste bağlı.)*
- **#246 (D32+D33):** `/api/prices/*` kimliksiz dış-çağrı yüzeyiydi; tercihler doğrulanmıyordu.
- **#247 (D39):** `/api/health` DB'ye dokunmuyordu → **`/api/ready`** (DB + şema, 503).
- **#248 (D37+D36+D38):** hep-başarılı fiyat cron'u, kendini `skip`'e çeviren ölü test, elle
  beslenen migration kapısı.
- **#249 (D34+D40):** sistem prompt'unda gerçek kişi adı; runbook komutları prod DB'yi görmüyordu.
- **#250 (D31):** kapsam kapısının KENDİSİ kör noktalıydı (`db.get`/`Model.kolon`/`func(...)`)
  ve **koçun tek yazma yolu kapı kapsamında değildi** → ikisi de kapandı.
- **#251:** para birimi ayarı gösterilemeyen kodları kabul ediyordu (D33'ün asıl şikâyeti).
- **#252:** üç eski kapı kendi kapsamını ölçmüyordu (L23/L27 uygulaması).
- **#253:** giriş yapamayan kullanıcının "bende mi, sizde mi?" sorusu cevapsızdı → kimliksiz
  `SistemDurumu` görünümü.
- **#254:** şifre politikası kişiye özel tahmini görmüyordu (`ali@x.com` → `ali12345` geçiyordu);
  blocklist 30→108.
- **ADR-043 (P2.1):** oturum sabitlemesi kararının yazılı gerekçesi + kanıt tablosu teste bağlı.
- **Kalıcı kapı:** `tests/test_kullanim_turu_degismezleri.py` — bir günlük kullanımı uçlardan
  koşturur, her adımda muhasebe kimliği/beklenen delta/panel-çökmez ölçer (BUG #241 fix'i geri
  alınınca kırmızı olduğu mutasyonla kanıtlandı).
- **Ölçüm:** `scripts/suite_db_izolasyon_kontrolu.py` — "süit canlı veriye dokunmuyor" iddiası
  ölçüldü: **TEMİZ** (2045 test, 31 tabloda 0 satır değişikliği).

**Yeni dersler:** **L25** (sözleşme yola değil OLAYA yazılır), **L26** (yasağın gücü kaynağı
seçen kod sayısı kadardır), **L27** (kapı listeyi elle taşıyorsa ölçmüyordur — kaynaktan türet),
**L28** ("çökmedim" başarı değil, "atlandı" geçti değil).

**Çalışma biçimi notu:** D31-D40 triyajı 4 ajanlı bir workflow ile **paralel** koşturuldu
(her ajan kendi kanıtını çalıştırarak üretti); ana iş SOLO ilerledi. Triyaj çıktısı
bulguların hangisinin hâlâ geçerli olduğunu kanıtla gösterdi — D35 örneğin ARTIK GEÇERSİZ
(BUG #220 ile kapanmış, rapordaki hüküm bloğu bayat).

**Sıradaki:** **doğrulama denetiminin 40 bulgusunun TAMAMI kapandı** (D01-D40; D35 zaten
BUG #220 ile kapanmıştı, rapordaki hüküm bloğu bayattı). Sıradaki iş artık denetim listesi
değil, **P6/P7 insan-kapısı**: Oracle VM + domain + canlı sırlar → `scripts/deploy.sh` →
`scripts/live_gate.py <url>` (bugün yerelde uçtan uca koşturuldu, dev config'te beklenen 6
kapı düşüyor) → gerçek davetliler. Kod tarafında bilinen teknik engel YOK.

> **6 Ağu 2026 — ÜÇÜNCÜ KULLANICI BİLDİRİMİ kapandı (BUG #241) ve "aynı olayın iki yolu
> ayrışır" sınıfı.** Kullanıcı bir alacağı panelden "Ödendi" işaretledi, cockpit'te nakit
> artmadı. Kök neden: aynı gerçek-dünya olayının İKİ girişi vardı ve nakit ayağı **yolun
> içine** kodlanmıştı — koç yolu (`mark_debt_paid`, BUG #113) nakdi hareket ettiriyor, panel
> yolu (`PUT /api/debts/{id}`) yalnız bayrağı çeviriyordu. Yani tahsilat Tam Net Değer'i
> DÜŞÜRÜYOR, borç ödemesi YÜKSELTİYORDU (para buharlaşıyor/üretiliyor). BUG #161/SBN-001
> ailesinin aynısı: kural birden çok yerde ayrı kodlanmış. Fix tüketicide değil sözleşmede:
> `app/services/debt_settlement.py` tek kaynak (yön + hedef hesap + simetri), iki yol da
> oradan geçiyor; kapanış `personal_debts.settlement_account_id` ile **iz bırakıyor** →
> geri alma tam da uygulandığı hesaptan geri sarılıyor, ayağı hiç uygulanmamış eski kayıt
> (NULL) geri alınınca **hayalet para düşmüyor**. Panelde geri-alma yolu da yoktu (backend
> simetrikti ama kullanıcı hatasını düzeltemiyordu) — eklendi. **Ders (L25):** sözleşme yola
> değil olaya yazılır; pariteyi iki yolu yan yana koşturan test kilitler. **Sınıf taraması
> (L11)** ikinci defekti buldu: "varsayılan nakit/kart hesabı" **beş ayrı yerde** seçiliyordu
> (executor ×3, transactions, incomes, sim) ve **hiçbiri emanet hesabı dışlamıyordu** — MC1
> guard'ı tek yerdeyken seçiciler çoğalmıştı; üçü sırasızdı (`.first()`), yani aynı olayın
> uygulanması ve geri sarılması farklı hesaplara düşebilirdi. `app/account_rules.py` tek
> kaynak + statik kapı (**L26**). **Canlı veri:** yedek alındı, migration koşuldu, onarım
> script'i (`scripts/repair_debt_settlements.py`, çift-sayım korumalı: koç yolundan kapatılan
> kayıtları atlar) 1 kapanışı onardı → nakit 1.963,52 → 6.963,52 TL.

> **6 Ağu 2026 — D24 kapandı (BUG #240) ve "envanterini izlediği şeyin çıktısından türeten
> yüzey" sınıfı.** Planlanan beş cron işinden üçü (`k2_batch`, `nightly_trace_cleanup`,
> `weekly_smoke_test`) hiçbir `SchedulerRun` satırı açmıyordu — çünkü kayıt çağrıları iki
> job'ın **gövdesine elle** yazılmıştı. Kullanıcıya KVKK metninde verilen 90-gün saklama
> sözünü uygulayan tek kod yolu haftalarca ölü kalsa kimse göremezdi. Fix tek tek eksik
> çağrıları eklemek değil: `PLANLI_ISLER` tek kaynak + `_izlenen_is` sarmalayıcısı → yeni iş
> ekleyen kişi kaydı **unutamaz** (**L24**); saklama işi kaç satır sildiğini kaydeder, yani
> taahhüt log okumadan sayıyla doğrulanır. İkinci yarısı ucun körlüğüydü: `/api/ops/scheduler`
> iş adlarını `SchedulerRun`'dan türetiyordu, yani **hiç koşmamış = tam da ölü olan** iş hiç
> görünmüyor, boş liste "her şey yolunda" gibi okunuyordu (**L23**) → adlar beyan edilmiş
> listeden gelir, `hic_calismadi`/`gecikti`/`sorunlu_isler` eklendi. **Sınıf taraması (L11)**
> iki şey buldu: (a) aynı defekt compose **yedeğinde** de vardı — `pg_backup.sh` çıkış kodu
> yalnız konteyner log'una düşüyordu, oysa yedek beta verisinin tek kopyası; artık iki yolda
> da `scheduler_runs`'a yazıyor ve aynı uçtan izleniyor. (b) Değişikliğin kendi yarattığı
> tuzak: `live_gate.py` "cron çalıştı mı"yı `bool(isler)` ile ölçüyordu — liste artık hep
> dolu olacağı için kapı sessizce hep-yeşile dönerdi; ölçüt kayıt varlığına taşındı.

> **6 Ağu 2026 — D23 kapandı (BUG #239) ve "veri var, tüketiciye ulaşmıyor" sınıfı.**
> Koç, fiyat sağlayıcısı çöktüğünde 30 günlük fiyattan hesaplanmış *"yatırım değerin X TL,
> %30,60 kârdasın"* cümlesini koşulsuz kuruyordu. Bayatlık verisi (`is_price_stale`,
> `age_text`) ASLINDA VARDI — ama yalnız HTTP katmanında, `generate_cockpit`'ten SONRA
> `routers/cockpit.py`'de ekleniyordu; koç/premortem/snapshot cockpit'i doğrudan çağırdığı
> için o alan onlara hiç ulaşmıyordu. Fix tüketicide değil KAYNAKTA: tazelik artık cockpit
> sözleşmesinin parçası, her tüketici otomatik görüyor. **Ders (L21):** bir sinyal "hesaplanıyor"
> olabilir ve yine de karar veren katmana hiç ulaşmayabilir — sinyali ÜRETİLDİĞİ yere değil,
> ONA GÖRE KARAR VERİLEN sözleşmeye koy. **Ders (L22):** doğru sinyalin YANLIŞ EŞİĞİ, sinyalin
> yokluğu kadar zararlıdır — etiket eşiği (24s, dürüst ve ücretsiz) ile alarm eşiği (72s,
> TEFAS hafta sonu yayın yapmaz) ayrıştırıldı; tek eşik ya her pazar gürültü ya da sessizlik
> üretiyordu. **Sınıf taraması (L11)** çelişme turunun telafi gerekçesini kısmen çürüttü:
> "kullanıcıda görünür sinyal başka yüzeyde var" deniyordu, ama *satış kararının verildiği*
> Hesaplar paneli fiyatı düpedüz **"Güncel fiyat"** diye etiketliyor ve yaşı gösteremiyordu
> (`AccountOut` türetilmiş yaş dönmüyordu). Uç↔panel sözleşmesi iki taraftan da teste bağlandı
> (BUG #232/#233 dersi: iki taraf ayrı ayrı doğru olup uyuşmazlık ARADA kalabiliyor).

> **6 Ağu 2026 — D22 kapandı (BUG #238) ve denetimin kendi çelişme turunun haklı çıktığı yer.**
> Bulgu "kapılar CI'da koşmuyor" (regresyon boşluğu) diye açılmıştı; çelişme turu şiddeti
> düşürürken bir **canlı defekt** not düşmüştü: prod compose uygulamayı `POSTGRES_USER` ile
> bağlıyor, o rol bootstrap **SUPERUSER** ve superuser `FORCE ROW LEVEL SECURITY`'ye rağmen
> RLS'i bypass eder. Yani ADR-038/M51'in "DB-katmanı 2. savunma" beyanı prod'da **hiç yoktu**
> — ve compose'un kendi yorumu "NON-superuser" diyordu. Aynı yanlış tarif dört yerde daha
> yazılıydı (`.env.prod.example`, runbook, ADR-038 madde 4, self-host compose): operatör
> **dokümanı doğru uygulayarak** savunmayı kapatıyordu. Kapatma: iki rol ayrımı (sahip =
> migration/pg_dump, `fos_app` NOSUPERUSER = uygulama trafiği) + entrypoint'te idempotent rol
> provizyonu + **startup fail-fast** (superuser bağlantısıyla uygulama açılmaz) + CI'ya
> postgres servisi (`pytest tests/` tamamı, dosya listesi tutulmuyor). **Ders (L19):** bir
> güvenlik katmanının "açık" olması, ONU ETKİSİZ KILAN bir yapılandırmayla birlikte
> yaşayabilir. Migration'ın 12 tabloya ENABLE+FORCE etmesi doğruydu, policy doğruydu, test
> doğruydu — bağlanılan ROL yanlıştı ve hiçbiri bunu ölçmüyordu. Katmanın varlığını değil,
> **o katmanın önkoşulunu** teste bağla. **Ders (L20):** bir gate'in kendi kurgusunu prod'un
> gerçeğiyle eşitlediğini İDDİA eden yorum (`fos_app` — "prod'daki rolü temsil eder")
> doğrulanmamış bir köprüdür; gate prod'un **gerçek kurulum kodunu** çağırmalı.

> **6 Ağu 2026 — KULLANICI BİLDİRİMİ kapandı (BUG #232, denetim dışı).** "Pasifleştir" basılan
> kural Aktif/Pasif/**Hepsi** hiçbir sekmede görünmüyordu: `GET /api/checkpoints`
> `active_only=True` default'lu, `RedLines.jsx` parametresiz çağırıyordu → pasif kayıt istemciye
> hiç ulaşmıyor, panelin istemci-taraflı filtresi ve sayacı boş veri üzerinde çalışıyordu.
> Soft-delete edilen kural da aynı sebeple "buharlaşıyordu" (router'ın *tarihçe kalır* iddiası
> kullanıcı için fiilen yalandı). İki kapı: `redlines-pasif.test.jsx` (4) + backend sözleşmesi
> `tests/test_checkpoint_pasif_gorunurluk.py` (4). **Ders:** denetim ajanları bu sınıfı
> göremedi — sunucu ve istemci ayrı ayrı doğruydu, uyuşmazlık ARADAYDI. Gerçek kullanım hâlâ
> statik denetimin bulamadığı defekt üretiyor.
>
> **6 Ağu 2026 — ikinci KULLANICI BİLDİRİMİ kapandı (BUG #233).** Google ile açılmış hesabın şifre
> almasının hiçbir yolu yoktu: panel "Mevcut şifren"i zorunlu çiziyordu (çıkmaz sokak),
> `change-password` alternatifsiz 400 dönüyordu, `password-reset-request` ise şifresizleri sessizce
> eliyordu — yani "bağlantı gönderildi" denip **hiç gönderilmiyordu**. Hesap tek bir dış sağlayıcıya
> çivilenmişti; Google erişimi kaybolursa tüm finansal veri kalıcı erişilemez olacaktı. Fix:
> `POST /auth/set-password` (yalnız şifresizler; şifresi olanda 400 → `change-password` doğrulaması
> atlatılamaz) + sıfırlama yolu şifresizlere de açıldı (yanıt aynı → enumerasyon açılmadı) +
> `/auth/me` içinde türetilmiş `has_password` + panelin dallanması. 17 yeni test (11 backend + 6 vitest).
> **Ders:** aynı sınıf — "her hesabın şifresi vardır" varsayımı hem panelde hem uçta ayrı ayrı
> tutarlıydı; kırılan şey ARADAKİ sözleşmeydi. Kullanım-turu bulguları statik denetimden farklı bir
> madenden geliyor; publish öncesi gerçek kullanım turu ayrı bir kapı olarak tutulmalı.

---

#### 🎯 DOĞRULAMA DENETİMİNİN **TÜM YÜKSEK BULGULARI KAPANDI** (bu oturum, 9 commit)

| Bug | Denetim | Konu (tek cümle) |
|---|---|---|
| #223 | D03 | Nakit-akış + borç-stratejisi uçları workspace bağlamı kurmuyordu → aile görünümünde KİŞİSEL borçlar üzerinde strateji, cockpit ile çelişen rakamlar |
| #224 | D03b | Aynı sınıfın kalan iki ucu (premortem + simülasyon); köprü yaprak modül `app/scope.py`'ye taşındı |
| #225 | D04 | Şifre sıfırlama bağlantısı şifre değiştikten sonra hâlâ geçerliydi → kalıcı hesap ele geçirme |
| #226 | D05 | OAuth kaydı kapalı-beta davet kapısını atlıyordu (mevcut süit fail-open'ı KİLİTLİYORDU) |
| #227 | D06 | Belgelenen systemd yolu KİMLİKSİZ canlı sunucu üretiyordu → **`AUTH_ENABLED` varsayılanı AÇIK** (kırıcı değişiklik, CHANGELOG'da geçiş notu) |
| #228 | D07+D16 | LLM kotası tek uca cıvatalanmıştı; premortem + aksiyon yansıması tavanı sıfırlıyordu → `app/llm_quota.py` + statik kapı |
| #229 | D08 | Fiyat cron'u `Account.balance`'ı güncellemiyordu → aynı hesap için Cockpit 36.000 / Hesaplar 30.000 |
| #230 | D11+D12+D13+D09 | Prod yığını belgelenen komutla açılmıyordu (`env_file` yok), scheduler crash-loop'ta, otomatik yedek YOKTU → hepsi kapandı + `deploy.sh` artık sessiz geçmiyor |
| #231 | D10 | KVKK beyanı gerçek veri akışıyla uyuşmuyordu → beyan düzeltildi, rıza **v3**, sunulan metin tek kaynaktan, rıza tazeleme yolu + koç panelinde uyarı |

**Bu turda üretilen YENİ KAPILAR** (hepsi kapsam tabanı assert'li — L11):
`test_cashflow_debt_endpoint_workspace_scope` · `test_premortem_simulation_workspace_scope` ·
`test_pwreset_token_gecerliligi` · `test_oauth_davet_kapisi` · `test_kimliksiz_deploy_kapisi`
(dokümanın gösterdiği HER şablon kimlikli sunucu üretiyor mu) · `test_llm_kota_kapisi`
(statik: `provider.chat` çağıran her dosya kotadan geçer ya gerekçeli muaf) ·
`test_fiyat_cron_bakiye_senkron` (iki panel aynı parayı gösteriyor mu) ·
`test_prod_compose_sozlesmesi` · `test_kvkk_beyan_gercek_akis` (**beyan ↔ gerçek akış**:
koç bağlamına yeni alan eklenip beyan güncellenmezse kırılır).

**Çalışma ritmi (işe yaradı, sürdür):** tek bulgu → denetimin kanıtını **davranış seviyesinde
kırmızı teste çevir** → düzelt → **mutasyon kontrolü** → **sınıf taraması** (L11) → tam süit →
ayrı commit + ledger + denetim raporu satırı. Sınıf taraması bu turda iki ek defekt buldu
(#224 ve D16'nın #228'e katılması).

---

#### 🟡 ORTA BULGU TURU — AÇILDI (6 Ağu, devam ediyor)

| Bug | Denetim | Konu (tek cümle) |
|---|---|---|
| #234 | D14+D15 | LLM kota sayacı paylaşılan havuzu hiç ölçmüyordu (kullanıcı-filtreli sorgu → %80/%100 dalları matematiksel olarak ölü) ve tavan ÇAĞRI değil MESAJ sayıyordu (bir mesaj = 1-4 gerçek istek) → ilan edilen maliyet tavanı gerçeğin 2-3 katına izin veriyordu |
| #235 | D21 | Bir test dosyası üretim `app`'ine kalıcı çöken uç ekliyordu; kapsam kilitleri görmeye başlayınca süit kalıcı kırmızıya düştü → commit kapısı fiilen ölmüştü. Önceki tur bunu ENVANTER tarafında elemişti (tüketici çözümü); kaynak düzeltildi + kirlilik AST kapısına bağlandı |
| #237 | D17 | Koçun kaydettiği işlem KALICI olarak yanlış güne yazılıyordu ("bugün" = sunucunun günü). Kök sebep yapısaldı: `execute_pending_action` handler'lara User geçirmiyordu → hiçbiri `user_today`'e ulaşamıyordu; prompt de LLM'e "tarih EKLEME" dediği için en sık kullanılan yol bilerek bu dala giriyordu. ADR-042 bu zararı kendisi tarif edip "uygulandı" demişti — **kapatıldığı iddia edilen** bir doğruluk hatası |
| #238 | D22 | Belgelenen "DB-katmanı 2. savunma" (RLS) prod'da FİİLEN YOKTU: compose uygulamayı `POSTGRES_USER` = bootstrap SUPERUSER ile bağlıyordu (yorumu "NON-superuser" diyordu) ve superuser FORCE'a rağmen her policy'yi bypass eder. Aynı yanlış tarif 4 yerde daha yazılıydı → operatör dokümanı izleyerek savunmayı kapatıyordu. İkinci yarısı: RLS/dual-dialect kapıları CI'da postgres olmadığı için her koşumda SKIP'ti; gate koşsa bile rolü ELDE yaratıp "prod'u temsil eder" dediği için prod'un gerçek rolünü ölçmeyecekti |
| #236 | D18 | Kurucunun ve adı geçen üçüncü bir kişinin gerçek finansal verisi (tutarlar, 13 aylık borç takvimi, banka markaları) prod Docker imajına giriyordu; aynı dosya `drop_all` yaptığı için prod konteynerinde tek komut tüm beta verisini silebiliyordu. Kapsam artık imajın GERÇEK içeriğine bağlı (Dockerfile COPY + `.dockerignore` simülasyonu) |
| #240 | D24 | Planlanan 5 cron işinden 3'ü hiçbir çalışma kaydı tutmuyordu (kayıt çağrıları iki job'ın GÖVDESİNE elle yazılmıştı) ve görünürlük ucu iş adlarını o tablodan türettiği için bu üçünü HİÇ listeleyemiyordu → KVKK'da söz verilen 90-gün saklama işi haftalarca ölü kalsa kimse göremezdi. Kayıt yapısal kılındı (tek kaynak liste + sarmalayıcı), uç beyan edilmiş listeden besleniyor (`hic_calismadi`/`gecikti`/`sorunlu_isler`), saklama işi silinen satır sayısını kaydediyor. Sınıf taraması: prod yedeği de yalnız log'a yazıyordu (kapandı) + canlı kapı dolu listeyi "çalıştı" sanacaktı (kapandı) |
| #239 | D23 | Koç, sağlayıcı çöktüğünde haftalarca eski fiyatı "güncel" gibi sunuyordu: bayatlık verisi yalnız HTTP katmanında ekleniyordu, cockpit'i doğrudan çağıran koç/premortem/snapshot yolları onu HİÇ görmüyordu → 30 günlük fiyattan "%30 kârdasın". Tazelik kaynağa (cockpit sözleşmesi) taşındı + koç dili değişti ("şu anki DEME"); etiket/alarm eşikleri ayrıştı. Sınıf taraması: Hesaplar paneli fiyatı koşulsuz "Güncel fiyat" diye etiketliyordu — satış kararı tam o ekranda veriliyor |

**Ders (L15 adayı):** bir sayaç için "neyi sayıyor" sorusu koddan okunmakla cevaplanamaz —
**birimini teste yazdır.** Buradaki iki defekt de sözleşme-kod uyuşmazlığıydı: yorum "PAYLAŞILAN"
diyordu ama sorgu filtreliydi; ADR "80 çağrı ≈ 40 mesaj" diyordu ama satır sayısı mesajdı. İkisi
de tek bir davranış testiyle (iki kullanıcı / gerçek çağrı sayısı) anında düşüyor.

**Sınıf taraması (L11) işe yaradı:** aynı tek-satır defekti premortem ve aksiyon yansıması
yollarında da vardı — denetim onları D14/D15 kapsamında görmemişti.

---

#### ⚠️ ÖNCE OKU — devam eden iki not

**(a) CANLI DB — yapıldı (Murat onayıyla, 5 Ağu).** Yedek → `repair_null_workspace --uygula`
→ yedek → `alembic upgrade head` (9 migration) → satır kaybı yok, bakiye değişmedi.
Yedekler: `data/backups/2026-08-05-141912.db` ve `-142714.db`.

**(b) TOKEN BÜTÇESİ — workflow maliyeti ölçüldü.** Denetim 49 ajanla koştu: **~3.97M token,
haftalık limitin ~%50'si.** Pahalı kısım 41 çelişme ajanıydı. Kural: workflow yalnız Murat
açıkça isterse, **tavan konarak** (en fazla 5 ajan) ve çelişme turu yalnız kritik/yüksek
bulgulara. Bu oturumun tamamı SOLO koştu — 9 bulgu, 9 commit.

---

#### SIRADAKİ İŞLER (öncelik sırasıyla)

0. ✅ **KULLANICI BİLDİRİMİ (BUG #241) ve denetimin TÜM ORTA bulguları KAPANDI** (6 Ağu akşam
   turu: #241…#249). Ayrıntı §11.0'da.
1. 🔴 **D31 — kapsam (workspace/kullanıcı) kapısının KÖR NOKTALARI.** Paralel triyajın
   koşturarak ürettiği kanıt: `tests/test_scope_enforcement.py` yalnız `db.query(Model)`
   şeklini görüyor; `db.get(Model, id)`, `db.query(Model.kolon)`, `db.query(func.sum(...))`,
   `select(Model.kolon)` şekilleri kapının dışında. Ayrıca **`app/action_executor.py` kapının
   dosya kapsamında DEĞİL** (LLM'in TEK yazma yolu!) ve orada 11 ham `Model.user_id == user_id`
   filtresi var. Bugün aktif sızıntı YOK (7 aday elle incelendi, sahiplik çağıranda
   doğrulanmış) — ama BUG #162 tam bu sınıftan geçmişti ve yeni yazılan tek bir satır
   suit yeşilken başka kullanıcının verisini okutabilir. **Not:** BUG #241 ile eklenen
   `app/services/debt_settlement.py:92` da tam o kör-nokta şeklini (`db.get`) kullanıyor
   (güvenli: `settlement_account_id` istemciden set edilemez) — yani kör nokta büyüyor.
   İş: (a) tarayıcıya 4+1 şekli ekle + meta-testle kendi kör noktasını ölç, (b) `_TARGETS`'a
   `action_executor.py` ekle ve 11 filtreyi `scope_filter`'a çevir ya da gerekçeli muaf yaz.
2. **Denetimin DÜŞÜK bulguları (D31…D40).** **D39** (health DB'ye dokunmuyor → rollback kapısı
   DB çökmüşken de yeşil) ve **D40** (runbook'taki davet komutu YANLIŞ DB'ye yazıyor) canlı
   deploy öncesi değerli.
3. ✅ **P2.1 — session-fixation kararının yazılı gerekçesi KAPANDI** (6 Ağu): ADR-043 + `tests/auth/test_adr043_oturum_sozlesmesi.py` (ADR'nin kanıt tablosu teste bağlı).
4. ✅ **Durum sayfası KAPANDI** (6 Ağu, BUG #253): giriş ekranından açılan `SistemDurumu` (kimliksiz, `/api/ready`'yi okur, ayrıntı sızdırmaz).
5. **H4 kalanı** (para birimi/locale görüntüleme, ADR-042) · **H9 kalanı** (prompt injection).
6. ✅ **L11 taraması KAPANDI** (6 Ağu, BUG #252): `test_scope_enforcement`, ürünleşme/kişiye-iz
   kapısı, workspace-insert kapısı ve alembic zinciri kapsam tabanı aldı; veri-işleyen envanteri
   zaten yeni kapıyla (BUG #242) taban assert'li yazıldı.

**İNSAN-KAPISI (Claude yapamaz, Murat'ta):** §9 — Oracle VM + domain/DNS + canlı sırlar,
gerçek davetliler, gerçek trafik, duyuru. Canlı deploy olmadan P6/P7/P8/P9 kapanmaz.
**Not:** prod yığını artık gerçekten açılabilir durumda (#230); canlı deploy'un bilinen
teknik engeli kalmadı.


Durum: ⬜ başlamadı · 🟡 devam · ✅ kapı geçti (kanıtlı) · ⏸️ insan-kapısı bekliyor

| Faz | Konu | Durum | Kanıt / Not |
|---|---|---|---|
| P0 | Temel doğrulama | ✅ | `pytest tests/ -q` → **1608 passed, 6 skipped** (2 dk 12 sn) + vitest **125 passed**; migration/çalışma-ağacı kontrolü yapıldı. **BUG #220:** süitte zamana bağlı gizli bir flaky vardı (UTC+14/UTC-11 farkı günün ~1/24'ünde 2 gün) — kapatıldı |
| P1 | Veri izolasyonu | ✅ | 4 bug kapandı (**#162** çapraz-kullanıcı kural sızıntısı, **#163** çok-kullanıcı backfill, **#164** yıkıcı script footgun'ı, **#165** workspace kapsam tutarsızlığı) + statik kapı (3 meta-testle ispatlı) + runtime matris (17 test) + **PostgreSQL RLS gate 13 passed** (`scripts/pg_gate_run.py`). ⚠️ **Düzeltme (BUG #238 / D22, 6 Ağu):** bu "13 passed" ELLE koşulmuş bir kanıttı (CI'da postgres yoktu → her koşumda SKIP) ve ölçtüğü rol prod'un rolü DEĞİLDİ: prod uygulamayı bootstrap superuser ile bağlıyordu, superuser RLS'i bypass eder → **RLS savunması canlıda hiç yoktu.** Kapandı: iki rol ayrımı + startup fail-fast + CI postgres servisi (18 pg testi her push'ta koşar). ⚠️ **Düzeltme (BUG #217, 5 Ağu):** buradaki "kapsam kilitli" iddiası yazıldığı andan itibaren GEÇERSİZDİ — kapsam kilidi `app.routes`'tan besleniyordu ve FastAPI 0.141'de boş dönüyordu, yani hiçbir ucu ölçmüyordu. Kilit OpenAPI'ye taşındı + taban assert edildi; açılır açılmaz `/api/legal/{slug}` matris dışı çıktı (gerekçeli istisnaya yazıldı). Matrisin kendisi (17 test) doğruydu, **kapsamı** ölçülmemişti |
| P2 | Güvenlik review | ✅ | **19 bug kapandı + bağımlılık 23→0.** Rapor: `guvenlik-review-publish.md`. Kabul edilen 3 risk gerekçeli yazılı (kayıt enumerasyonu, dolaylı prompt injection, localStorage token). Eski not: **8 başlıktan 6'sı kapandı.** Kapatılan: #170 sıfırlama-token'ı prod'da yanıtta dönüyordu (hesap ele geçirme), #171 prod'da AUTH_ENABLED doğrulanmıyordu (API kimliksiz açık), #172 şifre sıfırlama oturumları düşürmüyordu + tek-kullanım + logout access iptali, #173 viewer paylaşılan workspace'e yazabiliyordu, #174 kimliksiz kullanıcı yaratma, #175 ham exception gövdede, #176/#177/#181 girdi sınırları, #178 prod CORS localhost, #179 OAuth token'ları URL'de, #180 PII log. **Bağımlılık: pip-audit 23 açık → 0** (PyJWT/authlib/starlette/cryptography dahil), npm audit 0. **Gövde sınırı TAMAM (H22 / #213):** sınır yalnız nginx'teydi (ters vekil atlanırsa koruma yok, chunked gövdede `Content-Length` hiç gelmez) → uygulama katmanına taşındı, akan gövde sayılır, 413 hata-izlemeye düşmez, nginx şablonu testle kilitlendi (14 test). **BU "KALAN" LİSTESİ BAYATTI — 6 Ağu akşam turunda KOŞTURULARAK doğrulandı (R3/L17):** rate-limit çok-worker ✅ (paylaşılan DB sayacı, `_limit_db`, BUG #182), OAuth state çok-worker ✅ (imzalı-stateless + `RevokedToken` ile tek-kullanım, BUG #185) ve **PKCE ✅** (Google S256; GitHub OAuth App'leri desteklemiyor), refresh rotasyonu ✅ (BUG #186), register enumerasyonu ✅ (jenerik yanıt, BUG #202). Şifre politikası vardı ama İNCEYDİ → **BUG #254** ile güçlendirildi: blocklist 30→108, ardışık-dizi kuralı ve **kişiye özel tahmin** (`ali@x.com` → `ali12345` eskiden GEÇİYORDU; ölçüt "içeriyor" değil "harf çekirdeği kimlikle başlıyor" — güçlü şifreyi haksız reddetmemek için). **GERÇEK KALAN:** yok; P2 kapandı (kabul edilen 3 risk gerekçeli yazılı) |
| P3 | Operasyonel gerçeklik | ✅ | **Onboarding UI TAMAM (H20)** — Cockpit boş-durum kartı + demo veri akışı. **Kota TAMAM (ADR-041, BUG #188):** kullanıcı-başına LLM tavanı — paylaşılan sağlayıcı kotasını tek kişi tüketip diğerlerini kilitleyemez; tavan dolunca uygulama kapanmaz (Rules Engine deterministik). **#189** OAuth env adı kod↔doküman uyumsuzluğu, **#190** giriş yapmış kullanıcı şifre değiştiremiyordu. Sıfırdan-kullanıcı e2e ✅ (P3.5). **P3.2 (boş-veri hali her panelde) TAMAM (5 Ağu):** backend tarafı zaten kanıtlıydı ama kapsamı ölçülmemişti (**#217** — 87 uçtan 1'i taranıyordu); arayüz tarafı hiç sınanmamıştı → 13 panel × boş-durum + 13 panel × hata-durumu (54 test, gerçek boş-kullanıcı fixture'ı + sözleşme kayması kapısı). Bulunan gerçek defektler: **#218** (sonsuz istek döngüsü), **#219** (Bütçe paneli hata yolunda çöküyordu). **Kalan:** onboarding rehberi + opsiyonel demo veri |
| P3.5 | **Ürünleşme (tek-kullanıcı DNA söküm)** | ✅ | **H1/H2/H3/H5/H21 ✅ + H4 saat dilimi ✅** (para birimi görüntüleme ADR-042 ile P8 öncesine planlı — yayın-engeli değil). ⚠️ **Düzeltme (BUG #237, 6 Ağu):** buradaki "saat dilimi ✅" iddiası da (ADR-042 ile birlikte) YARIM'dı — yalnız 7 router benimsemişti; koçun kaydettiği işlem SUNUCU gününe, yani farklı saat dilimindeki kullanıcı için KALICI olarak yanlış güne yazılıyordu. Kök sebep yapısaldı (handler'lara User geçmiyordu). Kapatıldı + **iddia artık statik kapıya bağlı** (`tests/test_saat_dilimi_kapisi.py` — her `date.today()` gerekçe zorunlu, 13 modül için adoption kilidi). Ders: L17. Eski not: **H1/H2/H3/H5 ✅** (kullanıcı-tanımlı kural motoru #192, demo veri #194, iz temizliği). **Kalan: H4** (para birimi/dil/saat dilimi/kategori seti kullanıcı başına) — TRY/TR varsayımı hâlâ kodda; çok-para-birimi büyük bir iş, ayrı ADR ile ele alınacak. Eski not: **1. tur:** BUG #166 (metinlerde kişi adı → jenerik + statik kapı), #167 (TR normalize Kiril 'о' + sıra hatası → sessiz veri bozulması), #168 (banka markası koda gömülü → kullanıcının kendi hesap adları). **Kalan:** kullanıcı-tanımlı kural motoru (MC sabitleri), kişiselleştirme alanları, boş-durum + demo veri, sıfırdan-kullanıcı uçtan uca testi, yorum/docstring temizliği |
| P4 | Hukuki/uyum | ✅ | **BUG #191:** rıza metni canlıda ERİŞİLEMEZDİ (imajda docs/ yok → 404). `/api/legal/<slug>` ucu + Dockerfile/dockerignore. Rıza **v2** (v1 "self-host" varsayıyordu — barındırılan betada yanlış beyan), kullanım şartları (SPK/tavsiye-değildir), veri-işleyen envanteri (kodla test-bağlı). Koç panelinde görünür uyarı (H13) |
| P5 | Dayanıklılık/gözlem | ✅ | **Geri yükleme provası TAMAM (H14):** `scripts/restore.py` (onaysız yazmaz, bozuk yedeği reddeder, emniyet kopyası alır) + SQLite drill (7 test) + **PostgreSQL dump→drop→restore→doğrula** provası + runbook geri-yükleme bölümü. **Hata izleme TAMAM (#195):** kendi DB'mizde (dış servise veri gitmez), tekrarlar gruplanır, PII/sır maskelenir, izleme isteği düşürmez. **Canlı-veri migration provası TAMAM (#196):** `alembic/env.py` config URL'ini yok sayıyordu (test/script içinden migration GERÇEK DB'ye gidiyordu) → düzeltildi; prova artık izole DB'de koşuyor ve *gerçek DB'ye dokunulmadığı* da teste bağlı. **Fiyat sağlayıcı çöküşü TAMAM (H16 / #211):** fon-hisse zaten bayat işaretliydi; **döviz** kesintide TAMAMEN susuyordu → son bilinen kur `bayat`/`yas_dakika` ile sunuluyor, koç "şu anki" demiyor, 12 saatten eski değer hiç dönmüyor. **Kalan:** kapasite sınırları |
| P6 | Canlı ortam | ⏸️ | **İNSAN-KAPISI (§9.1-9.3):** Oracle VM + domain/DNS + canlı sırlar Murat'ta. **Hazırlık TAMAM:** `scripts/live_gate.py` tek komutla 20+ canlı kapıyı ölçer (kimlik zorunluluğu, HTTPS/CSP, /docs kapalı, KVKK metinleri, brute-force limiti, koç kotası); çıkış kodu 0 değilse beta AÇILMAZ. Runbook'ta canlı-doğrulama + geri-yükleme bölümleri hazır |
| P7 | Kapalı beta | 🟡 | **Altyapı TAMAM:** davetli-only kayıt (#199) + davet üretici + **geri bildirim/hata triyajı (#209)** + cron görünürlüğü (#203). **Kullanım ölçümü TAMAM (H23 / #214):** `beta_metrics` — sessiz terk, onboarding hunisi, tutunma, koç hata oranı; çıktı yalnız sayı (PII testle yasak), dış analitik yok. **Kalan: gerçek davetlilerin kayıt olması** (sunucu sonrası) |
| P8 | Açık beta | 🟡 | **Ön koşul TAMAM:** kayıt enumerasyonu kapatıldı + e-posta doğrulama akışı (#202), destek adresi yapılandırılabilir (#205), giriş yapamayanın destek kanalı (#210). **Eşzamanlı koç kullanımı TAMAM (H17 / #212):** kota rezervasyon desenine geçti (paralel istek tavanı delemiyor) + muhasebe etiketi paylaşılan çalışma-anı durumundan kurtarıldı (günlük kota koruması ölüydü). **Kalan: gerçek trafik** |
| P9 | Publish | 🟡 | **Sürüm yönetimi + CHANGELOG (#200), GERİ ALMA PROVASI (#208), kullanıcı rehberi (#207) TAMAM.** Kalan: duyuru + (opsiyonel) TWA — canlı yayın sonrası |

---

## §12. DEĞİŞİKLİK GÜNLÜĞÜ (yalnız ileri yönlü)

| Sürüm | Tarih | Değişiklik | Gerekçe |
|---|---|---|---|
| v1.0 | 2026-08-04 | İlk yazım: 10 faz, 3 basamak, kapı/kanıt protokolü, ajan protokolü, insan-kapısı listesi | Murat'ın publish goal direktifi |
| v2.0 | 2026-08-05 | **§1.3 DERS-KURALLARI (L1-L10)** eklendi — 41 bug'dan çıkarılan, tekrar etmemesi gereken hata SINIFLARI. Faz kapıları KORUNDU, hiçbiri gevşetilmedi | Murat'ın 3. adımı: "masterprompt'u gerileme/duraksama yönü hariç, kaliteyi artırma amaçlı geliştir" |
| v2.7 | 2026-08-06 | **§11.0: D24 kapandı (BUG #240, 14 kapı).** §1.3'e **L23** (bir şeyin YOKLUĞUNU raporlaması gereken yüzey, envanterini o şeyin ÇIKTISINDAN türetemez — boş liste "her şey yolunda" gibi okunur; yan tuzak: envanter beyandan gelince eski tüketici hep-yeşile döner) ve **L24** (izleme çağrısı işin GÖVDESİNE yazılıyorsa unutulur — kaydı planlama noktasına bağla, sözleşmeyi iş listesini gezerek assert et, dışarıda koşan kardeş işleri de kapsa) eklendi. Runbook cron-sağlığı bölümü yeni alanlarla güncellendi. Kapı EKLENDİ, hiçbiri gevşetilmedi (§10) | Denetimin D24'ü: 5 cron işinden 3'ü kayıt tutmuyordu, KVKK 90-gün saklama işi dahil sessizce ölebilirdi. Sınıf taraması prod yedeğinde aynı defekti buldu ve fix'in canlı kapıda yarattığı hep-yeşil tuzağını kapattı |
| v2.6 | 2026-08-06 | **§11.0: D23 kapandı (BUG #239, 18 backend + 4 vitest kapı).** §1.3'e **L21** (sinyal hesaplanıyor olabilir ama karar veren katmana hiç ulaşmayabilir — sinyali karar sözleşmesine koy) ve **L22** (etiket eşiği ile alarm eşiği ayrı olmalı; tek eşik ya gürültü ya sessizlik üretir) eklendi. Ayrıca önceki oturumun §11.0'da İLAN ETTİĞİ ama tabloya hiç yazmadığı **L19/L20** materyalize edildi (aynı sınıf: ilan ≠ materyalize, L17). Kapı EKLENDİ, hiçbiri gevşetilmedi (§10) | Denetimin D23'ü: koç bayat fiyattan "%30 kârdasın" diyordu; tazelik verisi vardı ama yalnız HTTP katmanındaydı. Sınıf taraması Hesaplar panelinin fiyatı koşulsuz "Güncel fiyat" diye etiketlediğini buldu — çelişme turunun "başka yüzeyde sinyal var" telafisini kısmen çürüttü |
| v2.5 | 2026-08-06 | **§11.0: D17 kapandı (BUG #237, 49 yeni kapı).** §1.3'e **L17** (bir belgenin "uygulandı" iddiası kanıt değildir — benimseme oranını ölçen statik kapıya bağla; kapatıldığı İDDİA EDİLEN hata, açık borçtan daha tehlikelidir çünkü listeden düşer) ve **L18** (bağlam taşımayan imza unutulmuş çağrı değil, kapatılmış kapıdır — önce bağlamı erişilebilir kıl) eklendi. §5'teki P3.5 satırı H4 saat dilimi için artık teste bağlı. Kapı EKLENDİ, hiçbiri gevşetilmedi (§10) | Denetimin D17'si: koçun kaydettiği işlem kalıcı olarak yanlış güne yazılıyordu; ADR-042'nin kendi iddiası diskte yanlıştı. Sınıf taraması denetimin listelediği 8 yerin ötesinde 12 yer daha buldu (motor katmanı + startup + onboarding) |
| v2.4 | 2026-08-06 | **§11.0: ORTA bulgu turu açıldı** — D14+D15 kapandı (BUG #234, 18 yeni kapı). §1.3'e **L15** adayı yazıldı (bir sayacın BİRİMİNİ teste yazdır: "neyi sayıyor" sorusu koddan okunarak cevaplanamaz — iki defekt de sözleşme↔kod uyuşmazlığıydı). Kapı EKLENDİ, hiçbiri gevşetilmedi (§10) | Denetimin ORTA turu: paylaşılan kota ölçülmüyordu (ölü koruma + ölü UI), tavan mesaj sayıyordu (gerçek maliyet 2-3 kat). Sınıf taraması aynı defekti premortem + yansıma yollarında da buldu |
| v2.3 | 2026-08-05 | **§11.0 yenilendi: denetimin TÜM yüksek bulguları kapandı** (#223-#231, 9 commit). Sıradaki iş ORTA bulgular (D14…D30). §1.2'ye **H26** eklendi (beyan ↔ gerçek veri akışı arasına test koy). Kapı EKLENDİ, hiçbiri gevşetilmedi (§10) | D03/D03b/D04/D05/D06/D07/D08/D09/D10/D11/D12/D13/D16 kapandı; dokuz yeni statik/davranışsal kapı üretildi, hepsi kapsam tabanı assert'li |
| v2.2 | 2026-08-05 | **§11.0 devir-teslim yenilendi** (6 yüksek bulgu kapandı: #223-#228); sıradaki iş listesi D08 → D11/D12/D13+D09 → D10 olarak önceliklendi. **§1.3'e L14** eklendi (güvenlik varsayılanı fail-CLOSED olmalı: koruma 'unutulması en kolay değişkene' bağlanamaz — BUG #227 dersi). Kapı EKLENDİ, hiçbiri gevşetilmedi (§10) | Denetimin yüksek bulgu turu: workspace uç kapsamı (#223/#224), sıfırlama token'ı (#225), OAuth davet kapısı (#226), kimliksiz deploy (#227), LLM kotası (#228). Üçü de yeni STATİK kapı üretti (kapsam tabanı assert'li) |
| v2.1 | 2026-08-05 | **§1.3'e L11 + L12**, **§1.2'ye H24 + H25** eklendi; §11 P0/P1/P3 kanıt satırları düzeltildi (P1'in "kapsam kilitli" iddiası BUG #217 ile GEÇERSİZ çıktı, yazıldı) | P3.2 turunda ölçülen 4 defekt: kapsam sessizce çöken kapılar (#217), hata yolunda sonsuz istek döngüsü (#218), hata yolunda panel çökmesi (#219), zamana bağlı flaky (#220). Kapı EKLENDİ, hiçbiri gevşetilmedi (§10) |
| v1.1 | 2026-08-04 | **§P3.5 ÜRÜNLEŞME fazı eklendi** (tek-kullanıcı DNA'sının sökülmesi — yayın-engeli) + **§1.2 kalıcı hatırlatma listesi** (H1-H18) + P0/P1 kapıları kanıtla kapatıldı + R7 riski eklendi | Murat: "kullanıcı sorununu da çözmek lazım publish etmeden… ben unutsam da sen hatırla, nicelerini de sen eklersin". Kapı EKLENDİ, hiçbir kapı gevşetilmedi (§10 kuralına uygun) |
