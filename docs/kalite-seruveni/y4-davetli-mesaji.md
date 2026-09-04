# Y4 — DAVETLİ MESAJI (metin hazır, gönderme Murat'ta)

**Durum:** taslak hazır · **Gönderen:** Murat · **Tarih:** —

---

## Önce bir sıralama itirazı (ve gerekçesi)

Masterprompt Y4'ü **Y3'ten sonraya** koyuyor: *"Y3 bittikten sonra 5 davetliye yeni adresle
tek ve kısa bir mesaj gider."* Mantığı açık — yeni adres varken haber vermek.

**Ama ölçüm bu sıralamayı zayıflatıyor:**

* Davetlilerin neden dönmediği **bilinmiyor**. DNS hipotezi (BUG #303) 4 Eylül'de yeniden
  ölçüldü ve **bugün geçerli değil** (Cloudflare 6/6, Google 6/6 çözüyor).
* Y3 bir **satın almaya** bağlı ve alan adı alınana kadar bekliyor.
* Sormak **hiçbir şeye bağlı değil ve bedava.** Cevaplar Y3'ün neyi hedeflemesi gerektiğini
  söyleyebilir — ya da Y3'ün hedefinin yanlış olduğunu.

**Somut risk:** alan adı alınıp yayın yapılır, sonra davetliler yine dönmezse, iki hafta
sonra hâlâ **sebebi bilmiyor** oluruz. O zaman "adres sorunuydu" varsayımına para ve emek
harcanmış olur — ki o varsayım bugün **ölçümle çürük**.

**Öneri:** mesaj ŞİMDİ gönderilsin, adres değişikliği ayrı bir mesaj olsun. Karar Murat'ın;
metnin iki sürümü de aşağıda hazır.

---

## SÜRÜM A — şimdi gönderilecek (adres beklemeden)

> Selam, FinancialOS'u ağustos başında denemiştin, teşekkürler.
>
> Şunu merak ediyorum: **sonrasında bir daha girmedin — sebebi neydi?**
> Kırıcı bir soru değil, tam tersi: neyin ters gittiğini bilmeden düzeltemiyorum.
>
> Aklıma gelen ihtimaller (hangisiyse onu yaz, ya da başka bir şeyse onu):
> - siteyi açamadın / hata aldın
> - açıldı ama ne yapacağını anlamadın
> - denedin ama işine yaramadı
> - vaktin olmadı, unuttun
>
> Tek cümle yeter. "Sıkıcıydı" da geçerli bir cevap.

**Neden bu biçim:** dört şık, cevap vermeyi bir cümleye indiriyor. Açık uçlu bir soru
("nasıl buldun?") cevapsız kalır; bu deneyimin kaydı zaten var — **5 davetlinin 2'si hiç
giriş yapmadı, 3'ü ilk gün sonrası dönmedi ve tek bir geri bildirim gelmedi.**
"Vaktin olmadı, unuttun" şıkkı bilerek konuldu: en muhtemel cevap oysa, onu da duymak
gerek — ve o cevap gelirse **sorun üründe değil, ürünün hayata girmemiş olmasındadır.**

---

## SÜRÜM B — Y3 bittikten sonra (yeni adresle)

> Selam, FinancialOS artık kendi adresinde: **https://<alan-adı>**
> Eski `.ts.net` adresi bazı tarayıcılarda açılmıyordu; o sorun bitti.
>
> Ağustosta denemiştin ve sonra girmedin — **sebebi neydi?** Bilmeden düzeltemiyorum.
> Tek cümle yeter: açamadın mı, anlamadın mı, işine yaramadı mı, yoksa vakit mi olmadı?
>
> Girmek istersen hesabın duruyor, yeni adresten aynı şekilde giriyorsun.

---

## Cevaplar geldiğinde (masterprompt Y4 şartı)

1. Cevaplar **ham hâliyle** `docs/kalite-seruveni/beta-geri-bildirim-<tarih>.md`'ye yazılır.
   **Özetlenmez, yorumlanmaz, tahminle doldurulmaz.**
2. Çıkan her defekt bir **BUG numarası** alır.
3. 7 gün sonra kullanıcı × işlem × koç × son etkinlik tablosu **yeniden ölçülür** ve
   4 Eylül tablosuyla yan yana konur.

## 4 Eylül tablosu (kıyas tabanı — bu satırlar değişmemeli, ölçüm kaydıdır)

| Kullanıcı | Kayıt | İşlem | Koç | Son etkinlik |
|---|---|---|---|---|
| davetli 1 | 11 Ağu 13:05 | **0** | **0** | **hiç** |
| davetli 2 | 11 Ağu 13:11 | 9 | 5 | 11 Ağu |
| davetli 3 | 11 Ağu 15:37 | 2 | 0 | 11 Ağu |
| **kurucu** | 11 Ağu 15:48 | 2 | 8 | 4 Eyl |
| davetli 4 | 12 Ağu 11:20 | **0** | **0** | **hiç** |

**13 Ağustos'tan beri sistemdeki tek kullanıcı etkinliği kurucununkidir.**
Sistemdeki iki geri bildirimin ikisi de ona ait.

---

## Ne YAPILMAYACAK

* **Cevap tahmin edilmeyecek.** "Muhtemelen arayüz karışık geldi" bir bulgu değil, bir
  varsayımdır; bu defterde varsayım defekt sayılmaz.
* **Hatırlatma spam'i atılmayacak.** Bir mesaj gider; cevap gelmezse *"cevap gelmedi"*
  ölçümün kendisidir ve öyle kaydedilir.
* **Ürün, cevap gelmeden değiştirilmeyecek.** Y4'ün amacı sinyal toplamak; sinyalsiz
  yapılan düzeltme, olmayan bir sorunu çözer.
