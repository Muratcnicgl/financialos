# B0 EKİ — ALAN ADI + BARINDIRMA: GERÇEK FİYAT ARAŞTIRMASI

**Tarih:** 11 Ağustos 2026 · **Tetik:** KURAL D1 (#1 geri dönüşü pahalı — dağıtım platformu;
#2 cevap dış dünyanın durumunda — fiyat listeleri) · **Talep:** GoDaddy dahil, alan adı ve
barındırma AYRI AYRI, gerçek fiyatlarla.

> **Dürüstlük kuralı (L45):** doğrulayamadığım fiyatı tabloya YAZMADIM. "Makul tahmin"le
> doldurulmuş bir hücre, boş hücreden zararlıdır — kendinden emin görünür ve karar onun
> üzerine kurulur. Doğrulanamayanlar §4'te ayrıca listelendi.

---

## 0. ÖNCE TEKNİK KISIT — neyi barındırıyoruz

Karar fiyattan önce **ne koştuğuna** bağlı. `docker-compose.prod.yml` ölçüldü: **6 servis**

| Servis | Ne yapar |
|---|---|
| `db` | PostgreSQL (ADR-038: prod Postgres; RLS ikinci savunma katmanı M51) |
| `backend` | FastAPI, `WEB_CONCURRENCY=2` uvicorn worker |
| `scheduler` | Ayrı servis — cron çift tetiklenmesin (Wave-8 MA2) |
| `web` | nginx (TLS sonlandırma + statik) |
| `certbot` | Let's Encrypt yenileme |
| `backup` | Zamanlanmış yedek (`deploy/pg_backup.sh`) |

**Bundan çıkan üç şart:**
1. **Docker + root erişimi zorunlu.** Paylaşımlı (cPanel) hosting bu yığını çalıştıramaz —
   GoDaddy/Natro tipi "web hosting" paketleri **teknik olarak elenir**, fiyatına bakmaya
   bile gerek yok. Gereken şey **VPS**'tir.
2. **Kalıcı disk zorunlu.** Postgres + yedekler + Let's Encrypt sertifikaları hacimlerde
   yaşıyor. Diski efemer olan platformlar elenir.
3. **RAM tahmini ~1–1,5 GB sürekli** (postgres + 2 worker + scheduler + nginx). **2 GB
   çalışır ama dar; 4 GB rahat.** LLM SDK'ları içe aktarıldığı için backend'in ayak izi
   sade bir CRUD API'sinden büyük.

---

## 1. ALAN ADI — GoDaddy dahil karşılaştırma

**Ölçüt yıllık fiyat DEĞİL, 5 yıllık gerçek maliyettir.** Bu pazarın tuzağı ilk yıl
indirimidir: alan adı taşınabilir ama taşımak da iş, ve çoğu kişi taşımaz.

| Sağlayıcı | .com 1. yıl | .com yenileme | 5 yıl toplam (≈) | Gizlilik (WHOIS) |
|---|---|---|---|---|
| **Cloudflare Registrar** | **10,44 $** | **10,44 $** | **≈ 52 $** | dahil |
| Porkbun | 11,08 $ | 11,08 $ | ≈ 55 $ | dahil |
| Namecheap | 6,79 $ (kupon) | 14,78 $ | ≈ 66 $ | dahil |
| **GoDaddy** | 4,99–11,99 $ | **21,99–22,99 $** | **≈ 100–104 $** | 1. yıl ücretsiz, sonra **9,99 $/yıl** |

**GoDaddy sonucu: en pahalı, farkla.** Yenilemede **+%92** artış ve gizlilik ayrı ücret →
5 yılda Cloudflare'ın **~2 katı**. Ek olarak GoDaddy'nin SSL'i (63,99–299,99 $/yıl) ve
"Premium DNS" (4,99–9,99 $/ay) satışları bizim için **tamamen gereksizdir** — TLS'i zaten
Let's Encrypt ya da Cloudflare kenarı ücretsiz veriyor.

**`.app` uzantısı** (diğer AI'ın önerdiği `financialos.app`): Cloudflare'da **12,18 $/yıl**
(.com'dan ~1,7 $ fazla). Teknik özelliği: `.app` **kalıcı olarak HSTS preload listesinde** —
HTTPS zorunlu ve **listeden çıkarılamaz**. Bizim duruşumuzla uyumlu (BUG #259'dan beri
HSTS zaten yayılıyor); tek pratik sonucu o alan adını asla düz HTTP'den servis edememek.

**Karar girdisi:** Cloudflare Registrar'ın ikinci bir avantajı var — Cloudflare Tunnel'ın
"kalıcı hostname" şartı alan adının **Cloudflare DNS'inde** olmasıdır. Oradan alınırsa o
adım kendiliğinden çözülür.

---

## 2. BARINDIRMA — ÜCRETSİZ KATMANLAR ÖNCE (gerçekten olur mu?)

Sorulan soru "ücretsiz yapabildiğimizi ücretsiz yapalım"dı. Ölçüm:

| Platform | Durum (2026) | Bizim yığın için sonuç |
|---|---|---|
| **Render (free)** | Web servisi **15 dk hareketsizlikte uyur**, uyanma ~1 dk · aylık **750 saat** tavanı · **ücretsiz PostgreSQL 30 GÜN sonra sona erer**, +14 gün içinde ücretliye geçilmezse **VERİ SİLİNİR** · cron servisi **ücretsiz değil** (asgari 1 $/ay) | ❌ **ELENDİ.** Başkasının finansal kaydını 30 günlük ömrü olan bir DB'de tutmak kabul edilemez. Ayrıca uyuyan servis = 02:45 cron'u **hiç koşmaz**. |
| **Fly.io (free)** | Ücretsiz katman **kaldırıldı** (2024); yeni kullanıcıya 2 VM-saat / 7 gün deneme | ❌ Elendi |
| **Railway** | **Ücretsiz katman yok**, saniyelik ücretlendirme | ❌ Elendi |
| **Oracle Cloud Always Free** | ARM Ampere (4 OCPU / 24 GB) **ömür boyu ücretsiz** · **home region kayıttan sonra DEĞİŞTİRİLEMEZ** ve Always Free yalnız home region'da · kapasite kuyruğu gerçek | ⚠️ **Tek gerçek ücretsiz 7/24 seçenek** — ama kapasiteye bağlı bir piyango |
| **Kendi makine + Cloudflare Tunnel** | Tunnel ücretsiz, sınırsız tünel · kalıcı hostname için **kendi alan adı şart** | ✅ Çalışır; bedeli 7/24 olmaması |

**Sonuç: bu yığını barındıran ücretsiz bir PaaS yok.** Ücretsiz 7/24 tek yol Oracle, o da
kapasiteye bağlı. Yani gerçek seçim: **kendi makine (0 TL, 7/24 değil)** ya da **ucuz VPS
(7/24, aylık birkaç euro)**.

---

## 3. VPS — fiyat/performans (yalnız doğrulananlar)

| Sağlayıcı | Paket | Fiyat | Not |
|---|---|---|---|
| **Hetzner** | CX22 · 2 vCPU / 4 GB / 40 GB | **€3,79/ay** | Kaynaklar arasında CX23 · 2 vCPU / 4 GB için **€5,99** da geçiyor — **SKU/fiyat sipariş anında doğrulanacak**, ikisi de aynı sınıf |
| **Netcup** | 2 vCPU / 2 GB / 64 GB | €3,35/ay | 2 GB bizim için **dar** (§0.3) |
| **Contabo** | 4 vCPU / 6 GB / 100 GB | €4,50/ay | RAM/€ oranı en iyi; **ama CPU'yu agresif overselling** yaptığı bağımsız kaynaklarda not düşülüyor |
| **GoDaddy VPS** | 1 vCPU / 2 GB | **8,99 $/ay** — ve bu fiyat **36 ay peşin ödeme** ister; yenilemede **~2 katına** çıkar | Docker ve root var, ama **yarısı kadar kaynak, iki katı fiyat, 3 yıl kilit** |

**GoDaddy VPS sonucu: elenir.** Hetzner'ın yarısı kaynak, iki-üç katı fiyat ve üç yıllık
taahhüt. Kapalı beta gibi **süresi belirsiz** bir iş için taahhütlü ürün yanlış araçtır.

---

## 3b. "ÜCRETSİZ ALAN ADI" İDDİALARININ TARANMASI (11 Ağu, ikinci tur)

**Tetik:** "GoDaddy adını içeren alan adları ücretsizmiş" bilgisi (staj yerinden, ikinci el).

**İddianın literal hâli yanlıştır** — bir markanın adını içeren alan adı almak marka
ihlalidir; ücretsiz olmak şöyle dursun UDRP şikâyeti konusudur. **Kastedilen şey
bulundu:** GoDaddy Website Builder'ın ücretsiz planı `siteadi.godaddysites.com` **alt alan
adı** verir — yani "godaddy adını içeren" ücretsiz bir adres. Gerçek, ama:

- Bir **site kurucudur**, barındırma değil: Docker/FastAPI/PostgreSQL koşturulamaz.
- Sitede **GoDaddy reklamı** görünür.
- Kendi alan adını bağlamak **Basic plan → 9,99 $/AY** ister (yılda ~120 $ — alan adı
  satın almanın 11 katı).
- `godaddysites.com` bölgesinin DNS'i sende değildir → Cloudflare Tunnel'a bağlanamaz.

→ **Bizim yığın için kullanılamaz.**

### Gerçekten ücretsiz alan adı seçenekleri (taranan)

| Seçenek | Durum (2026) | Cloudflare bölgesi olabilir mi? | Bizim için |
|---|---|---|---|
| **eu.org** | Yaşıyor, gönüllü işletiyor; **kendi nameserver'ını (Cloudflare) verebilirsin** | ✅ Evet — Tunnel çalışır | ⚠️ **Onay ELLE**: birkaç gün ~ birkaç hafta, bazen ay. Bedeli para değil **zaman** |
| **is-a.dev** | Aktif, GitHub PR ile kayıt, tam DNS kaydı kontrolü, HTTPS hazır | ⚠️ **DOĞRULANMADI** — Tunnel için `*.cfargotunnel.com` CNAME'i genelde **kendi Cloudflare hesabındaki bölgede** olmak zorundadır | ⚠️ Gönüllü işletiyor, **geri alınabilir**, kullanım politikasına tabi |
| **DuckDNS** | Aktif, kalıcı ad | ❌ IP'ye işaret eder | ⚠️ Port yönlendirme + **ev IP'si açığa çıkar** |
| **Freenom (.tk/.cf/.gq)** | **Ücretsiz iş modeli ÖLDÜ** (Meta davası, 12,6M alan adı kapatıldı); geri döndü ama **€8,22/yıl ücretli** | — | ❌ Üstelik bu uzantılar **spam/phishing itibarı** taşır: şifre sıfırlama e-postalarımız spam'e düşer |

### GoDaddy TR "Ücretsiz Domain" sayfası — iki ayrı teklif (11 Ağu, doğrulandı)

Sayfa iki şey vaat ediyor ve ikisi çok farklı:

**(a) "Yıllık Hosting / WordPress planı al, alan adı ücretsiz."** Alan adı bedava ama
**yıllık peşin bir hosting planı** satın almış oluyorsun — ve o hosting **paylaşımlı /
WordPress** hostingidir. §0'daki üç şart (Docker + root + kalıcı disk) karşılanmaz:
**bizim yığın orada koşmaz.** Yani "ücretsiz" alan adı, kullanamayacağımız bir hosting
planının yanında geliyor. ❌

**(b) "İlk .com yalnızca 0,01 TL."** Bu **gerçek** ve tek başına alınabiliyor. Ama şartı
belirleyici: bulunan kaynaklar bu kampanyanın **3 YILLIK taahhüt** istediğini, 1. yılın
0,01 olup **2. ve 3. yılların 22,99 $** olduğunu söylüyor → 3 yıl toplamı ≈ **46 $**.
Cloudflare'da 3 yıl **31,38 $**. Bu şartla teklif **daha pahalı**.
⚠️ **TR kampanyasının şartı buradan doğrulanamadı** — kesin bilgi **sepet ekranındadır**
(aynı `.app` fiyatı gibi: canlı ekran benim aramamdan üstündür).

### Kararı belirleyen iki YAPISAL gerçek

1. **Kayıt yeri ≠ DNS sağlayıcısı.** Alan adını nereden alırsan al, **nameserver'ları
   Cloudflare'a yöneltmek ücretsizdir** ve alan adı böylece bir Cloudflare bölgesi olur →
   **Tunnel çalışır.** Yani "Cloudflare'dan almak zorundayız" diye bir kısıt YOK; oradan
   almak yalnızca bir adım eksiltir.
2. **60 günlük ICANN transfer kilidi + transferin 1 yıl EKLEMESİ.** Yeni kayıtlı bir alan
   adı 60 gün taşınamaz; 60 gün sonra Cloudflare'a transfer **10,46 $** ve süreye
   **1 yıl ekler** (kalan süre kaybolmaz).

### Bundan çıkan karar kuralı (sepet ekranında bakılacak TEK şey: DÖNEM)

| Sepette görülen | Doğru hamle | Gerçek maliyet |
|---|---|---|
| **1 yıl / 0,01 TL** | GoDaddy'den al → nameserver'ları Cloudflare'a çevir → **60 gün sonra** Cloudflare'a transfer et | ~0,01 TL + 10,46 $ → **~22 ay** alan adı |
| **3 yıl taahhüt (0,01 + 22,99 + 22,99)** | **Alma.** Doğrudan Cloudflare | 3 yıl 31,38 $ (46 $ yerine) |

**Her iki durumda da satın alma anında yapılacaklar:** ① **otomatik yenilemeyi KAPAT**
(unutulursa 12. ayda ~22,99 $ sürpriz fatura), ② sepete kendiliğinden eklenen ek ürünleri
(Domain Protection, e-posta, SSL) **çıkar** — SSL'i zaten ücretsiz alıyoruz, ③ ödeme
öncesi **toplam tutarı** ve **yenileme fiyatını** ekrandan oku.

**Kaynaklar:** godaddy.com/tr-tr/domain/ucretsiz-domain (kampanya sayfası) · theguidex.com
(0,01 $ .com kampanyası 3 yıl taahhütlü) · hostadvice.com + nameexperts.com (yenileme
21,99–22,99 $) · developers.cloudflare.com/registrar (transfer 1 yıl ekler) ·
ICANN transfer politikası (60 gün kilidi)

### Ölçülen sonuç

**Gerçekten 0 TL ve 7/24 olan tek kombinasyon: eu.org + Oracle Always Free.** Bedeli para
değil **iki ayrı kuyruk**: eu.org'un elle onayı ve Oracle'ın ARM kapasitesi. İkisi de
bizim kontrolümüzde değil ve ikisi de betayı **süresiz** erteleyebilir.

**Karşılaştırma için ölçek:** `.com` **10,46 $/yıl ≈ 0,87 $/ay**. Her ücretsiz yol bunun
karşılığında ya haftalarca bekleme, ya başkasının iyi niyetine bağlı **geri alınabilir**
bir ad, ya da **ev IP'sinin açığa çıkması** istiyor. Başkasının finansal verisini tutan
bir uygulamada bu takas kötüdür — ama karar ürün sahibinindir ve para kısıtı gerçektir.

**Kaynaklar:** godaddy.com/websites/website-builder + tooltester.com + digiadagency.co.uk
(ücretsiz plan = `godaddysites.com` alt alan adı, reklamlı; özel alan adı 9,99 $/ay) ·
indexedev.com + blog.51sec.org (eu.org + Cloudflare nameserver) · docs.is-a.dev ·
freestuff.dev (DuckDNS) · domainincite.com + webhosting.today + netcraft.com (Freenom
ücretsiz model kapandı, geri dönüş ücretli, itibar sorunu)

---

## 4. DOĞRULANAMAYANLAR (bilinçli olarak tabloya yazılmadı)

- **Türkiye lokasyonlu VPS'ler (Natro / Turhost / Radore / Komuta vb.).** Arama yalnız
  pazarlama sayfaları ve affiliate listeleri döndürdü; bağımsız kıyas, uptime ölçümü ya da
  Docker/KVM teyidi bulunamadı. Görülen aralık **~103–170 TL/ay** (giriş paketleri, root
  erişimli) — bu bir **gösterge**, fiyat değil. **Gerçek avantajları var ve önemsiz değil:**
  TRY ile fatura (yurt dışı kartı/FX derdi yok), Türkçe destek, Türkiye'ye ~10 ms gecikme
  (Frankfurt ~50 ms). Ciddi düşünülüyorsa tek bir sağlayıcıda **1 ay peşin** deneyip
  ölçmek doğru yol — taahhütsüz.
- **Hetzner CX22 ↔ CX23 fiyat farkı** (§3): iki kaynak çelişiyor, sipariş ekranında
  doğrulanacak.
- **TL kuru:** €/TL ve $/TL çevrimi yapılmadı; kur beyanı ölçüm değildir.
- **Oracle Frankfurt kapasitesi:** Murat'ın beyanı, ölçülmedi.

---

## 5. SONUÇ — üç cümle

1. **Alan adı: GoDaddy'den ALMA.** 5 yılda ~2 katı ödersin. Cloudflare Registrar
   (10,44 $ `.com` / 12,18 $ `.app`, sabit) hem en ucuz hem Tunnel'ın DNS şartını
   kendiliğinden çözüyor.
2. **Ücretsiz PaaS yok.** "Bedava sunucu" arayışı bu yığında Render/Fly/Railway'de biter:
   biri veriyi 30 günde siliyor, ikisinde ücretsiz katman kalmamış. Gerçek ücretsiz tek
   7/24 seçenek Oracle Always Free ve o bir kapasite piyangosu.
3. **VPS'e geçilecekse GoDaddy değil Hetzner.** Yarı fiyata iki katı kaynak, taahhüt yok,
   ve `deploy.sh` + compose + nginx yığınımız tam olarak bu senaryo için yazıldı.

---

## 6. KAYNAKLAR

**Alan adı:** tldprice.org/registrar/cloudflare · startupowl.com (Cloudflare Registrar
10,44 $) · priceworld.com/domains/godaddy · hostingrevelations.com (GoDaddy yenileme
listesi) · nameexperts.com (GoDaddy promosyon vs gerçek maliyet) · domaindetails.com
(5 yıllık gerçek maliyet) · spendbase.co (Cloudflare vs Porkbun `.app` 12,18 $) ·
kb.porkbun.com + comodosslstore.com (`.app` HSTS preload zorunlu)
**Ücretsiz katmanlar:** render.com/changelog (ücretsiz Postgres 30 gün) ·
render.com/docs/free (750 saat, 15 dk uyku) · saaspricepulse.com (Fly.io ücretsiz katman
kaldırıldı) · northflank.com (Railway ücretsiz katman yok)
**VPS:** hetzner.com + vpsfor.dev + experte.com · sliplane.io (Hetzner/Netcup/Contabo
kıyas) · danubedata.ro (Contabo overselling notu) · hostadvice.com + cybernews.com
(GoDaddy VPS 8,99 $, 36 ay peşin, Docker/root var)
**Oracle:** docs.oracle.com/iaas (home region değiştirilemez; Always Free yalnız home
region) · github.com/hitrov/oci-arm-host-capacity (script **home region** içinde çalışır)
**Kendi repo:** `docker-compose.prod.yml` (6 servis), `app/startup.py`,
`app/price_providers/router.py` (geçmiş tarihli fiyat çekimi YOK)
