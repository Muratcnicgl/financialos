# Kullanıcı Rehberi

FinancialOS panelleri ve temel akışlar.

> **Güncelleme (5 Ağu 2026, BUG #207):** Bu rehber Wave-9 öncesinden kalmıştı ve iki hata
> içeriyordu: (1) "demo veri" için `scripts/setup_data` öneriyordu — o script `drop_all`
> yapar, yani **var olan tüm verini siler** ve başka birinin kanonik verisini yükler;
> (2) Wave-9'da eklenen özelliklerin (davet kodu, uygulanan kurallar, güvenli demo veri,
> saat dilimi, hesabı sil/dışa aktar, geri bildirim) hiçbiri yazılı değildi.

## Başlarken

1. **Kayıt.** Kapalı beta sırasında kayıt **davetlidir**: sana verilen **davet kodunu**
   kayıt ekranındaki alana gir. (Kodu operatör üretir; tek kullanımlıktır.)
2. **İlk ekran.** Hiç verin yokken Cockpit'te bir başlangıç kartı çıkar. İki yol var:
   - **Kendi hesabını ekle** (gerçek kullanım),
   - **Örnek veriyle gez** — jenerik demo veri yüklenir ve **tek tuşla tamamen kaldırılır**;
     senin girdiğin kayıtlara dokunmaz.
   > ⚠️ `scripts/setup_data` **kullanma**: geliştirici aracıdır, veritabanını sıfırlar.
3. **Kendi kuralını yaz** (aşağıya bak) — uygulamayı seni koruyacak şekilde ayarla.
4. **Günlük döngü:** işlem gir → Cockpit güncellenir → koça danış.

## Paneller
- **Cockpit:** anlık finansal manzara — net değer (görülen/tam), güvenli-harcama, sağlık
  skoru, uyarılar, "ilk adım" önerisi.
- **Koç:** yapay zekâ finans koçu. Gerçekleşen bir eylem bildirirsen onay-kartı çıkar
  (öner → onayla → uygula); soru/analizde sadece açıklar.
  **Koç yatırım tavsiyesi vermez**; sayısal kararlar kural motorundan gelir.
- **Hesaplar:** nakit/kart/kredi/yatırım. Yatırım fiyatları gece otomatik güncellenir;
  fiyat bayatsa rozetle uyarılırsın.
- **İşlemler:** gelir/gider girişi (TR sayı formatı: 1.234,56).
- **Gelir & Borç:** düzenli gelirler + kişisel borç/alacak.
- **Kırmızı Çizgiler:** kendi kurallarını yazdığın yer (aşağıda ayrıntı).
- **Borç Stratejisi:** snowball/avalanche karşılaştırma, konsolidasyon simülatörü.
- **Hedefler / Bütçe / Akış / Raporlar.**

## Kendi kuralını yazmak (kural gerçekten uygulanır)

Kırmızı Çizgiler panelinde bir kural eklerken **"Bu kural otomatik uygulansın mı?"**
seçeneğini kullanabilirsin:

| Kural | Ne yapar |
|---|---|
| **Nakit tabanı** | Nakdin belirlediğin tutarın altına inecek işlem **engellenir** |
| **Tek harcama tavanı** | Tek seferde belirlediğin tutarın üstü **engellenir** |
| **Dokunulmaz hesap** | O hesabın bakiyesini değiştiren işlem **engellenir** |

Seçmezsen kural serbest metin olarak kalır: koç dikkate alır ama işlem engellenmez.
Uygulanan kurallar **koçun onayına bağlı değildir** — kod seviyesinde çalışır.

## Hesabın ve verin

- **Verini indir:** tüm verin tek JSON dosyası olarak dışa aktarılır (taşınabilirlik).
- **Hesabını sil:** hesabın ve **tüm verin kalıcı olarak** silinir (geri alınamaz).
  Paylaşılan (aile) bir workspace'in sahibiysen o workspace silinmez — sahiplik kalan
  bir üyeye devredilir, diğerlerinin verisi korunur.
- **Yedeklerdeki kopyalar** yedek saklama süresi (30 gün) dolduğunda ortadan kalkar.
- **Şifre:** giriş yaptıktan sonra değiştirebilirsin; şifre değişince **diğer tüm
  oturumlar kapanır** (çalınmış bir oturum varsa ölür).
- **Saat dilimi:** profilinde ayarlarsan "bugün" senin saatinle hesaplanır (gece yarısı
  civarı girilen işlemler doğru güne yazılır).

## Sorun bildirme

Uygulama içindeki **Şikâyet / İstek / Öneri** widget'ını kullan — beta sırasında en hızlı
kanal budur. Giriş yapamıyorsan sana davet kodunu ileten kişiye/adrese yaz.

## Bilinen sınırlar (beta)

- Para birimi **TL** varsayımlıdır (çoklu para birimi planlı — ADR-042).
- Banka bağlantısı **yoktur**: veriler senin girdiklerindir.
- Piyasa verisi (fon/hisse/döviz) üçüncü taraf kaynaklardan gelir, gecikmeli olabilir.
- Bu bir **kapalı betadır**: kesinti olabilir. Verini düzenli dışa aktarman önerilir.

Detay mimari kararlar: `docs/architecture/` · Deploy: `docs/deployment/runbook.md`
