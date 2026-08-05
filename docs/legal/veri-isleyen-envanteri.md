# Veri İşleyen Envanteri

**Güncelleme:** 5 Ağu 2026 · KVKK m.10 aydınlatma yükümlülüğünün dayanağı.
Kullanıcı verisine dokunabilen **her** üçüncü taraf burada listelenir. Yeni bir
sağlayıcı eklendiğinde bu dosya ve KVKK metni **aynı commit'te** güncellenir.

## 1. LLM sağlayıcıları (koç özelliği — YURT DIŞI aktarım)

| Sağlayıcı | Konum | Not |
|---|---|---|
| Google Gemini | ABD/AB | Ücretsiz kademe; API kullanım verisi sağlayıcı politikasına tabidir |
| Groq / Cerebras | ABD | Yedek zincir (fallback) |
| OpenRouter | ABD | Yedek zincir |
| Anthropic | ABD | Opsiyonel |
| **Ollama (yerel)** | **Kullanıcının makinesi** | Egemen mod: veri dışarı ÇIKMAZ |

### Koça her mesajda GÖNDERİLEN veri (tam liste)

> Bu liste `app/coach.py::_build_context_message` çıktısının birebir karşılığıdır ve
> `tests/test_kvkk_beyan_gercek_akis.py` ile koda bağlıdır: bağlama yeni bir alan eklenip
> bu liste güncellenmezse test kırılır. (Önceki sürüm "ham işlem listesi gönderilmez"
> diyordu — **bu beyan yanlıştı**, denetim bulgusu D10 / BUG #231 ile düzeltildi.)

- **Hesap adları** ve bakiyeleri (ör. "Garanti Vadesiz 1234"), hesap türü, kart limiti/kullanımı
- **Son işlemler listesi (ham):** tarih, tutar, kategori ve **kendi yazdığınız açıklama metni**
- Yaklaşan ödemeler/tahsilatlar: tutar, tarih ve **karşı tarafın (üçüncü kişinin) adı**
- Kategori kırılımları ve davranış kalıpları (harcama örüntüleri)
- Kırmızı çizgi / kural metinleriniz, hedefleriniz, abonelikleriniz
- Koç sohbetindeki mesajlarınız ve önceki sohbet geçmişi

**⚠️ Özel nitelikli kişisel veri (KVKK m.6):** işlem açıklaması SERBEST METİNDİR. "Psikiyatri
kontrol", "cemaat bağışı", "sendika aidatı" gibi bir not yazarsanız sağlık/inanç/sendika
verisi de bu aktarıma dahil olur. Koçu kullanacaksanız açıklamalara özel nitelikli bilgi
yazmamayı tercih edebilirsiniz — panellerin çalışması için gerekli değildir.

**⚠️ Üçüncü kişi verisi:** alacak/borç kaydındaki karşı tarafın adı ve tutarı, o kişi
uygulamanın kullanıcısı olmasa bile koç bağlamına girer. Bu kişilerin verisini yurt dışına
aktarma sorumluluğu, kaydı oluşturan kullanıcıdadır; ad yerine takma ad/baş harf
kullanabilirsiniz.

**Gerçekten gönderilmeyenler** (testle korunur): şifre/parola hash'i, oturum/erişim token'ı,
e-posta adresiniz, OAuth kimliğiniz.

**Kullanıcı kontrolü:** koç kullanılmadığında bu aktarımın HİÇBİRİ olmaz; uygulamanın geri
kalanı (cockpit, bütçe, borç stratejisi, hedefler, raporlar) tamamen yereldir ve
deterministiktir. Yerel model (Ollama) seçilirse veri makineden hiç çıkmaz.

## 2. Piyasa verisi sağlayıcıları (kullanıcı verisi GİTMEZ)

| Sağlayıcı | Amaç | Giden veri |
|---|---|---|
| TEFAS / pytefas | Fon fiyatı | Yalnız fon kodu (örn. `TLY`) |
| İş Yatırım | BIST hisse fiyatı | Yalnız hisse kodu |
| TCMB EVDS | Döviz/altın kuru | Yok (genel seri sorgusu) |
| open.er-api | Döviz kuru (yedek) | Yok |

Bu çağrılar **sunucudan** yapılır ve hangi kullanıcının hangi fona sahip olduğu bilgisini
taşımaz (kod bazlı, kullanıcı kimliği içermez).

## 3. Altyapı

| Hizmet | Rol | Veri |
|---|---|---|
| Sunucu sağlayıcı (Oracle Cloud Free Tier vb.) | Barındırma | Tüm uygulama verisi (şifreli disk, HTTPS) |
| Let's Encrypt | TLS sertifikası | Yalnız alan adı |
| SMTP sağlayıcı (Brevo vb.) | Şifre sıfırlama + davet e-postası | E-posta adresi + bağlantı |

## 4. Kullanılmayanlar (bilinçli)

- **Banka bağlantısı / açık bankacılık:** YOK. Hesap verisi otomatik çekilmez.
- **Analitik/izleme (Google Analytics, piksel):** YOK.
- **Reklam ağı:** YOK.
- **Harici kimlik sağlayıcı (Firebase/Auth0):** YOK — kimlik doğrulama kendi
  SECRET_KEY'imizle imzalanır, kullanıcı verisi kendi veritabanımızda kalır.

## 5. Doğrulama

Bu envanterin kodla tutarlılığı `tests/test_legal_docs.py` ile kilitlenir: kodda
tanımlı LLM sağlayıcıları ve fiyat kaynakları bu dosyada listelenmiş olmalıdır.
