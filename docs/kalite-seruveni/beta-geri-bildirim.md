# KAPALI BETA — GERİ BİLDİRİM DEFTERİ

**Açıldı:** 11 Ağustos 2026 · **Kapsam:** kapalı beta (P7) boyunca gelen tüm geri bildirim.

## Bu defter nasıl kullanılır

- **Ham kayıt önce gelir.** Gelen her şey **olduğu gibi** yazılır; yorum ve karar ayrı
  bölümdedir. Geri bildirimi kaydederken değerlendirmek, onu kendi beklentimize göre
  yeniden yazmak demektir.
- **Hiçbir madde silinmez.** B6 ritüeli: her madde ya bir **BUG numarası** alır ya da
  **gerekçesiyle "yapılmayacak"** işaretlenir. *İşlenmemiş madde bırakılmaz* — ama
  "işlenmiş" olması "yapılmış" demek değildir.
- **Durum alanları:** `NOT ALINDI` (henüz değerlendirilmedi) · `BUG #NNN` · `REDDEDİLDİ (gerekçe)`
  · `ERTELENDİ (tetik)`
- **Sessizlik başarı sayılmaz (L47):** geri bildirim gelmiyorsa ayrımı kullanım sayısıyla
  yap (`scripts/beta_metrics.py`).

---

## Kanal notu — kayda değer

İlk geri bildirim **uygulama içi widget'tan değil, WhatsApp'tan** geldi. Bu bir defekt
değil ama bir gerçektir: davetli tanıdıksa doğal kanal sohbettir. Widget'ın ölçtüğü şey
"kaç kişi yazdı" ise, o sayı gerçek geri bildirimi **eksik** gösterecektir. Sohbetten
gelenler bu deftere elle işlenir.

---

# 2026-08-11 · Davetli #1 (abi) — ilk oturum

**Bağlam:** Google ile giriş yaptı, **boş hesapla** başladı, sonra örnek/demo veri ekledi.
Büyük ekrandan (masaüstü) inceledi. Süre: ~15 dakika.

## A. Çalışan / beğenilen

| # | Gözlem | Durum |
|---|---|---|
| A1 | Google ile giriş sorunsuz çalıştı | NOT ALINDI (doğrulama) |
| A2 | **Boş durumda ekran "normal"** — kötü görünmüyor | NOT ALINDI (boş-durum tasarımı tuttu) |
| A3 | Büyük ekranda **bozulma yok** | NOT ALINDI |
| A4 | **Harcama hedefi** bölümü "çok iyi" | NOT ALINDI |
| A5 | Geri bildirim bölümünü fark etti | NOT ALINDI |
| A6 | Koç **gerçekten yapay zekâ**; "iskelet güzel" — model zayıflığı "şu aşamada çok önemli değil, ilerde model değişir" | NOT ALINDI |

## B. Eleştiri — ASIL DEĞERLİ KISIM

| # | Geri bildirim (kendi ifadesiyle) | Durum |
|---|---|---|
| **B1** | **"Çok fazla detay var. Kullanıcı daha basit metrikler görmek ister."** | NOT ALINDI |
| **B2** | **"Yapay zekânın metrikleri falan bile çıkıyor."** → *hangileri olduğu soruldu, **cevap gelmedi** — takip edilecek* | NOT ALINDI · **AÇIK SORU** |
| **B3** | **"Her yerde bir sayı, yazı falan… kafası karışıyor bir insanın, yalan yok."** | NOT ALINDI |
| **B4** | Öneri: **"Basit 3-5 özellik, ama kullanıcının ilk girişte anlayacağı düzeyde"** — daha etkili olur | NOT ALINDI |
| **B5** | Öneri: **"Lite" bir sürüm/mod** üretmek *(Murat da aynı fikirde: "lite model de üretmek lazım")* | NOT ALINDI |
| **B6** | **"v1 için fazla kapsamlı."** Sağlam ilerleyip **adım adım** özellik eklemek daha iyi | NOT ALINDI |
| **B7** | Çekirdek önerisi: **gelir · gider · borç · koç** | NOT ALINDI |
| **B8** | Strateji: gelişmiş kısımlar **elde kalsın ama publish edilmesin**; yayınlanan kısım "gerçekten test ettiğin, içine sinen, basit güzel şeyler" olsun | NOT ALINDI |

## C. Kafa karışıklığı — gerçek kullanılabilirlik bulgusu

| # | Ne oldu | Durum |
|---|---|---|
| **C1** | **"Burada borcum niye gözükmedi? Normal mi böyle olması? Örnek datada görünüyordu borç."** → Murat açıkladı: *"O, başkasına olan borç/alacak — birine borçluysan ya da biri sana borçluysa."* Yani **kredi borcu** ile **kişiler arası borç/alacak** ayrımı kullanıcıya kendini anlatmıyor. | NOT ALINDI |

**Neden bu madde ayrı tutuldu:** kullanıcı bunu *hata* diye bildirmedi, *soru* olarak sordu
ve cevabı operatörden aldı. Uygulama tek başınayken bu soruyu cevaplayamıyor. Bizim
"Kafa karıştırdı" türünü eklememizin sebebi tam olarak bu sınıf.

---

## Operatör notları (bu oturumdan, geri bildirim DEĞİL)

- Davetli **demo/örnek veri** akışını kendiliğinden buldu ve kullandı.
- Murat kendi hesabında dolu veri olduğu için **boş-durum görünümünü kontrol edemiyordu**;
  davetli olmasa bu ölçülemezdi. (Kapalı betanın amacı tam olarak bu.)
- Koçun zayıflığı **ücretsiz LLM katmanından** kaynaklanıyor ve davetli bunu sorun
  saymadı — ama bu, ölçülmüş bir kalite değil, tek kişilik bir izlenimdir.

---

## Değerlendirme kuralı (şimdilik uygulanmıyor)

Murat'ın kararı: **"şimdilik sadece not alalım, sonra zamanla değerlendiririz."**
Bu bilinçli bir erteleme ve doğrudur — tek kullanıcının izlenimiyle ürün yönü değiştirmek,
2-3 kişi daha aynı şeyi söyleyip söylemeyeceğini bilmeden karar vermektir.

**Değerlendirme ne zaman yapılır:** en az 3 davetli × en az 14 gün kullanım sonrası
(kapalı beta çıkış ölçütü). O turda her madde ya BUG numarası alır ya gerekçeyle reddedilir.

**Erken karar YASAK olan iki şey:**
1. **Özellik silmek/gizlemek** — "fazla detay" geri bildirimi bir kişiden geldi; ikinci
   kişi tersini söyleyebilir (bkz. B1/B3 vs A4 "harcama hedefi çok iyi").
2. **Yeni özellik eklemek** — faz sınırı: kapalı betada yeni özellik açılmaz.
