# FinancialOS — Kapalı Beta Karşılama

Merhaba. Bu uygulamayı sana ben (Murat) gönderdim ve **davetli listesinde olmayan kimse
giremiyor**. Aşağıdakileri iki dakikada oku; sonra kurulum bir dakika sürüyor.

---

## Bu ne yapar

Kendi paranı **tek ekrandan** görmeni sağlar:

- **Kokpit** — nakit, kart borcu, kredi borcu, yatırım ve net değer; hepsi tek bakışta.
- **İşlemler** — harcama/gelir girersin, bakiyeler otomatik güncellenir.
- **Gelir & Borç** — düzenli gelir/giderler ve kişilerle olan alacak/borçların.
- **Kırmızı Çizgiler** — "buraya dokunmam" dediğin sınırlar; uygulama seni uyarır.
- **Koç** — yazıyla konuştuğun bir finans koçu. "Bugün 320 TL market harcadım" dersen
  kaydı **sana onaylatarak** girer.
- **Hedefler / Bütçe / Borç Stratejisi / Raporlar** — birikim planı, zarf bütçe, hangi
  borcu önce kapatmalı, aylık özet.

## Bu ne YAPMAZ — bunları bilerek okuman önemli

- **Bankana bağlanmaz.** Hiçbir hesap bilgin otomatik çekilmez; ne girersen o vardır.
  Banka şifreni **hiçbir yere yazma**, uygulama zaten istemiyor.
- **Yatırım tavsiyesi vermez.** Koç senin girdiğin sayılarla konuşur; "şunu al" demez.
- **Otomatik para hareketi yapmaz.** Hiçbir ödeme, transfer veya işlem gerçekleştiremez.
- **Koç kendi başına kayıt yazamaz.** Her kayıt önce sana **onay kartı** olarak gelir;
  sen onaylamadan hiçbir şey yazılmaz.

## Hangi aşamadayız — dürüst olmak gerekirse

**Kapalı beta.** Yani: kod çok test edilmiş ama **senin gibi gerçek bir kullanıcı ilk kez
kullanıyor**. Hata çıkabilir. Zaten seni bunun için çağırdım — bulduğun her tuhaflık işime
yarıyor, hiçbiri "boş ver" değil.

Bir sorun görürsen ekranda bir **hata kodu** çıkabilir (örn. `abc23xyz`). O kodu bana
söylersen sorunu tam olarak bulabiliyorum — aşağıdaki geri bildirim düğmesi zaten kodu
kendisi ekliyor, sen sadece ne olduğunu yaz.

## Verin nerede duruyor

- Verilerin **benim çalıştırdığım sunucuda** duruyor; reklam için kullanılmıyor,
  satılmıyor, üçüncü tarafa pazarlanmıyor.
- **Koçu kullandığında** — ve yalnız o zaman — finansal bağlamın bir yapay zekâ
  sağlayıcısına gider. Bunun tam kapsamı KVKK metninde madde madde yazılı.
  **Koçu hiç kullanmayabilirsin**; diğer tüm ekranlar onsuz da tam çalışır.
- Verini **istediğin an dışa aktarabilir**, **istediğin an hesabını silebilirsin** —
  ikisi de uygulamanın içinde, benden izin istemeden.
- Tüm hukuki metinler uygulamada: **Hesap → Hukuki belgeler** (KVKK, kullanım şartları,
  veri işleyen envanteri).

## Geri bildirim — asıl istediğim şey bu

Sağ alttaki **Geri Bildirim** düğmesi her ekranda var. Dört seçenek:

| Seçenek | Ne zaman |
|---|---|
| **Şikayet** | Bir şey bozuk / yanlış sonuç veriyor |
| **İstek** | "Şu da olsa iyi olurdu" |
| **Öneri** | Daha iyi bir yol aklına geldiyse |
| **Kafa karıştırdı** | **Bunu özellikle istiyorum:** bozuk değil ama anlamadın, nereye basacağını bulamadın, ekran kafanı karıştırdı |

Son madde bana en çok yarayanı. "Bu bozuk mu, ben mi anlamadım?" diye düşündüğün her an
o düğmeye bas — cevabı ben bulurum.

**Not:** geri bildirim gönderdiğinde yazdığın metinle birlikte uygulama sürümü, varsa hata
kodu, hangi ekranda olduğun, ekran genişliğin ve tarayıcı ailen (Chrome/Safari gibi)
kaydedilir. **Ekran görüntüsü alınmaz, işlem ve tutarların otomatik kopyalanmaz.**

## Uygulama ne zaman kapalı olabilir

*(Bu bölüm barındırma kararına göre kesinleşecek — kendi makineden yayında kalınacaksa
aşağıdaki cümle kalır, sunucuya geçilirse silinir.)*

Kapalı beta boyunca uygulama **benim bilgisayarımdan** yayınlanıyor. Bilgisayarım kapalıyken
uygulama da kapalı olur. Bir açmadığında "ben mi bozdum?" diye düşünme — birkaç saat sonra
tekrar dene, sorun sürerse bana yaz.

## Kurulum

Telefon ve bilgisayar adımları ayrı yazıldı: **`kapali-beta-kurulum.md`**

---

**Teşekkürler.** Bu uygulamayı üç aydır tek başıma kullanıyordum; senin gözünle bakılması
benim göremediğim şeyleri gösterecek.
