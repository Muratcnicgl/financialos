# KVKK Açık Rıza Metni (v4)

**Yürürlük:** 11 Ağu 2026 · **Versiyon:** v4 (`kvkk_consent_version`)
**v3'ten farkı — TEŞHİS VERİSİ BEYAN EDİLDİ (BUG #281/#282).** Kapalı beta için geri
bildirim kaydına teşhis alanları eklendi: uygulama sürümü, hata korelasyon kodu, ekran
genişliği, tarayıcı **ailesi** ve uygulamanın ana ekrandan mı açıldığı. Bunlar v3'ün
saydığı kategorilerin hiçbirine tam olarak girmiyordu; kapsamı eksik beyan edilen rıza
sakattır, bu yüzden yeni sürüm açıldı. **Ham tarayıcı kimliği (User-Agent) SAKLANMAZ** ve
**otomatik ekran görüntüsü ALINMAZ** — bu iki sınır §2b'de yazılıdır.
**v2'den farkı — KOÇ AKTARIM KAPSAMI DÜZELTİLDİ (BUG #231 / denetim D10).** v2, koça giden
bağlamı "cockpit özeti: bakiyeler, borç/gelir toplamları, kırmızı çizgi metinleri ve
yazdığınız mesaj" ile sınırlı beyan ediyordu. **Gerçekte** koça ham işlem listesi (tarih,
tutar, kategori ve **kendi yazdığınız açıklama metni**), hesap adları ve alacak/borç
kayıtlarındaki **üçüncü kişilerin adları** da gidiyor. Yanlış kapsamla alınan rıza sakattır;
bu sürüm gerçeği eksiksiz anlatır. **v1'den farkı:** v1 uygulamayı yalnız self-host
varsayıyordu; barındırılan kurulum da kapsanır.

6698 sayılı Kişisel Verilerin Korunması Kanunu (KVKK) kapsamında, FinancialOS'u
kullanabilmeniz için aşağıdaki hususlarda açık rızanız alınır.

## 1. Veri sorumlusu
Veri sorumlusu, **bu kurulumu barındıran kişi/kuruluştur**. İki kullanım biçimi vardır:

- **Barındırılan (kapalı beta):** verileriniz beta operatörünün kiraladığı sunucuda
  (Türkiye/AB bölgesi tercih edilir) tutulur. İletişim: uygulama içi geri bildirim
  (Şikâyet/İstek/Öneri) veya operatörün bildirdiği e-posta adresi.
- **Self-host:** uygulamayı kendi sunucunuzda çalıştırıyorsanız veri sorumlusu sizsiniz.

## 2. İşlenen kişisel veriler
- **Kimlik/iletişim:** e-posta adresi, ad (opsiyonel).
- **Kimlik doğrulama:** şifreniz **geri döndürülemez biçimde (bcrypt) hash'lenir** — düz
  metin saklanmaz. Sosyal girişte (Google/GitHub) sağlayıcıdan yalnız e-posta/ad/kimlik alınır.
- **Finansal veriler:** hesaplar, işlemler, borç/alacaklar, hedefler, bütçe, kırmızı çizgiler —
  **yalnızca sizin girdikleriniz**. Banka bağlantısı YOKTUR; hesap bilgileriniz otomatik çekilmez.
- **Kullanım:** koç sohbet geçmişi, koç içgörüleri, aksiyon geçmişi, uygulama günlükleri.
- **Teşhis (v4, yalnız GERİ BİLDİRİM gönderdiğinizde):** yazdığınız metinle birlikte
  uygulama sürümü, varsa hata **korelasyon kodu**, bulunduğunuz ekran, ekran genişliği,
  tarayıcı **ailesi** (Chrome/Safari/Firefox gibi) ve uygulamanın ana ekrana eklenmiş
  hâlinden mi açıldığı kaydedilir. Amaç tek: bildirdiğiniz sorunu bulabilmek.

### 2b. Teşhis verisinde BAĞLAYICI sınırlar
Aşağıdakiler **yapılmaz** — bunlar bir vaat değil, kodda testle kilitlenmiş sınırlardır
(`tests/test_geri_bildirim_teshis_kapisi.py`):
- **Otomatik ekran görüntüsü alınmaz.**
- **İşlem/tutar verileriniz geri bildirim gövdesine otomatik kopyalanmaz.** Kendiniz
  yazarsanız o sizin beyanınızdır.
- **Ham tarayıcı kimliği (User-Agent) saklanmaz** — yalnız aile adı tutulur; sürüm,
  işletim sistemi ve cihaz modeli üçlüsü güçlü bir parmak izidir ve teşhis için gerekmez.
- Kayda giren alan listesi **sabittir**; yeni bir alan eklemek bu metnin güncellenmesini
  ve yeni rıza sürümünü gerektirir (kapı, alan eklenince kırmızıya döner).

## 3. İşleme amacı
Kişisel finansal yönetim hizmetini sunmak: bakiye/nakit akışı takibi, borç stratejisi, yapay
zekâ finans koçu, hedef takibi. Verileriniz **reklam veya profilleme için kullanılmaz,
satılmaz, üçüncü taraflara pazarlanmaz.**

## 4. Yurt dışına aktarım (ÖNEMLİ)
- Uygulama verisi sunucuda kalır.
- **İstisna — Koç (LLM):** finans koçunu kullandığınızda, aşağıdaki bağlam seçili LLM
  sağlayıcısına gönderilir. Bu sağlayıcılar **yurt dışında** bulunabilir
  (bkz. `veri-isleyen-envanteri.md`); bu, **yurt dışına aktarım** anlamına gelir (KVKK m.9).

  **Koça giden verinin tam listesi:**
  - Hesap **adlarınız** ve bakiyeleri, hesap türü, kart limiti/kullanımı
  - **Son işlemler listesi (ham):** tarih, tutar, kategori ve **işlem açıklaması olarak
    yazdığınız serbest metin**
  - Yaklaşan ödeme/tahsilatlar: tutar, tarih ve **karşı tarafın (üçüncü kişinin) adı**
  - Kategori kırılımları ve harcama örüntüleri
  - Kırmızı çizgi/kural metinleriniz, hedefleriniz, abonelikleriniz
  - Koç sohbetindeki mesajlarınız ve önceki sohbet geçmişi

  **Gönderilmeyenler:** şifre hash'iniz, oturum token'ınız, e-posta adresiniz, OAuth kimliğiniz.

- **⚠️ Özel nitelikli veri (KVKK m.6):** işlem açıklaması serbest metindir. "Psikiyatri
  kontrol", "cemaat bağışı", "sendika aidatı" gibi bir not yazarsanız sağlık/inanç/sendika
  verisi de bu aktarıma dahil olur. Bu metni onaylayarak **bu kapsamdaki aktarıma da**
  açık rıza vermiş olursunuz. Dilerseniz açıklamalara özel nitelikli bilgi yazmayın —
  panellerin ve hesapların çalışması için gerekli değildir.
- **⚠️ Üçüncü kişi verisi:** alacak/borç kaydındaki kişinin adı ve tutarı, o kişi
  uygulamanın kullanıcısı olmasa bile koça gider. Bu kişilerin verisini aktarma sorumluluğu
  kaydı oluşturan sizdesiniz; ad yerine takma ad/baş harf kullanabilirsiniz.
- **Koçu kullanmama** hakkınız vardır: uygulamanın tüm hesap/panel/rapor işlevleri koç
  olmadan da çalışır (matematik yerel ve deterministiktir).
- **Yerel/offline model** (Ollama) seçilirse hiçbir veri makineden çıkmaz.

## 5. Haklarınız (KVKK m.11)
- **Erişim/taşınabilirlik:** uygulama içinden veya `GET /api/users/me/export` ile **tüm**
  verinizi tek JSON dosyasında indirin.
- **Silme (unutulma):** `DELETE /api/users/me` — hesabınız ve tüm veriniz kalıcı olarak
  silinir (cascade, geri alınamaz). Silme sonrası **yedeklerde** kalan kopyalar, yedek
  saklama süresi (30 gün) dolduğunda kendiliğinden ortadan kalkar.
- **Düzeltme:** verilerinizi uygulama üzerinden dilediğiniz an güncelleyebilirsiniz.
- **Rıza geri alma:** hesabınızı silerek rızanızı geri alabilirsiniz.

## 6. Saklama süresi
Veriler hesabınız aktif olduğu sürece saklanır. Hesap silindiğinde canlı veri anında,
yedeklerdeki kopyalar en geç 30 gün içinde silinir. Koç akıl-yürütme kayıtları 90 gün
sonra otomatik temizlenir.

## 7. Güvenlik
Şifreler bcrypt ile hash'lenir; oturumlar imzalı JWT ile yönetilir; taşıma HTTPS
(Let's Encrypt) üzerindedir; veritabanı satır-seviyesi izolasyon (PostgreSQL RLS) ve
uygulama katmanı kapsam filtreleriyle korunur; bağımlılıklar düzenli olarak taranır.
Hiçbir sistem %100 güvenli değildir; bir ihlal durumunda etkilenen kullanıcılar ve
Kişisel Verileri Koruma Kurumu, mevzuatın öngördüğü sürede bilgilendirilir.

## 8. Beta uyarısı
Bu bir **kapalı beta**dır. Hizmet kesintiye uğrayabilir, veri kaybı riski sıfır değildir;
verilerinizin **kendi yedeğinizi** dışa aktarma özelliğiyle almanız önerilir.
