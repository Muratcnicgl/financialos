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
