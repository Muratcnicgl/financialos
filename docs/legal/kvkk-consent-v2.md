# KVKK Açık Rıza Metni (v2)

**Yürürlük:** 5 Ağu 2026 · **Versiyon:** v2 (`kvkk_consent_version`)
**v1'den farkı:** v1 metni uygulamayı yalnız **self-host** varsayıyordu ("verileriniz kendi
sunucunuzda"). Kapalı beta ile birlikte uygulama **operatör tarafından barındırılan** bir
kurulumda da sunulmaktadır; bu metin o gerçeği doğru yansıtır (yanlış beyan KVKK ihlalidir).

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

## 3. İşleme amacı
Kişisel finansal yönetim hizmetini sunmak: bakiye/nakit akışı takibi, borç stratejisi, yapay
zekâ finans koçu, hedef takibi. Verileriniz **reklam veya profilleme için kullanılmaz,
satılmaz, üçüncü taraflara pazarlanmaz.**

## 4. Yurt dışına aktarım (ÖNEMLİ)
- Uygulama verisi sunucuda kalır.
- **İstisna — Koç (LLM):** finans koçunu kullandığınızda, koça gönderilen bağlam (cockpit
  özeti: bakiyeler, borç/gelir toplamları, kırmızı çizgi metinleriniz ve yazdığınız mesaj)
  seçili LLM sağlayıcısına gönderilir. Bu sağlayıcılar **yurt dışında** bulunabilir
  (bkz. `veri-isleyen-envanteri.md`). Bu, **yurt dışına aktarım** anlamına gelir.
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
