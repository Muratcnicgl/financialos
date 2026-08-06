# Veri İşleyen Envanteri

**Güncelleme:** 6 Ağu 2026 · KVKK m.10 aydınlatma yükümlülüğünün dayanağı.
Kullanıcı verisine dokunabilen **her** üçüncü taraf burada listelenir. Yeni bir
sağlayıcı eklendiğinde bu dosya ve KVKK metni **aynı commit'te** güncellenir.

## 1. LLM sağlayıcıları (koç özelliği — YURT DIŞI aktarım)

| Sağlayıcı | Bağlanılan adres (host) | Konum | Not |
|---|---|---|---|
| Google Gemini | `generativelanguage.googleapis.com` (SDK) | ABD/AB | Varsayılan; ücretsiz kademe, API kullanım verisi sağlayıcı politikasına tabidir |
| Groq | `api.groq.com` (SDK) | ABD | Yedek zincir (fallback) |
| Cerebras | `api.cerebras.ai` | ABD | Yedek zincir |
| OpenRouter | `openrouter.ai` | ABD | Yedek zincir |
| Together AI | `api.together.xyz` | ABD | Yedek zincir — **yalnız `TOGETHER_API_KEY` tanımlıysa devreye girer** |
| DeepInfra | `api.deepinfra.com` | ABD | Yedek zincir — **yalnız `DEEPINFRA_API_KEY` tanımlıysa devreye girer** |
| Anthropic | `api.anthropic.com` (SDK) | ABD | Opsiyonel |
| **Ollama (yerel)** | `localhost` | **Kullanıcının makinesi** | Egemen mod: veri dışarı ÇIKMAZ |

> Zincirdeki sağlayıcı sırası `LLM_PROVIDER=fallback` modunda: Gemini → OpenRouter → Cerebras
> → Together → DeepInfra → Groq → Ollama. Anahtarı tanımlı OLMAYAN sağlayıcı zincire hiç
> girmez; yani listedeki bir isim "veri şu an oraya gidiyor" demek değil, "operatör anahtarı
> tanımlarsa gidebilir" demektir. Hangi anahtarların tanımlı olduğunu operatör bilir.

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

| Sağlayıcı | Bağlanılan adres (host) | Amaç | Giden veri |
|---|---|---|---|
| TEFAS / pytefas | `www.tefas.gov.tr` | Fon fiyatı | Yalnız fon kodu (örn. `TLY`) |
| İş Yatırım | `www.isyatirim.com.tr` | BIST hisse fiyatı | Yalnız hisse kodu |
| TCMB EVDS | `evds3.tcmb.gov.tr` | Döviz/altın kuru | Yok (genel seri sorgusu) |
| open.er-api | `open.er-api.com` | Döviz kuru (yedek) | Yok |

Bu çağrılar **sunucudan** yapılır ve hangi kullanıcının hangi fona sahip olduğu bilgisini
taşımaz (kod bazlı, kullanıcı kimliği içermez).

## 3. Altyapı

| Hizmet | Bağlanılan adres (host) | Rol | Veri |
|---|---|---|---|
| Sunucu sağlayıcı (Oracle Cloud Free Tier vb.) | — (barındırma) | Barındırma | Tüm uygulama verisi (şifreli disk, HTTPS) |
| Let's Encrypt | — (ACME, nginx) | TLS sertifikası | Yalnız alan adı |
| SMTP sağlayıcı (Brevo vb.) | `.env`'deki `SMTP_HOST` | Şifre sıfırlama + davet e-postası | E-posta adresi + bağlantı |

## 3b. Kimlik sağlayıcıları (sosyal giriş — OPSİYONEL, yalnız o düğmeye basarsanız)

| Sağlayıcı | Bağlanılan adres (host) | Konum | Giden/gelen veri |
|---|---|---|---|
| Google ile giriş | `accounts.google.com`, `oauth2.googleapis.com`, `openidconnect.googleapis.com` | ABD | Tarayıcınız Google'a yönlendirilir (Google bu uygulamaya giriş yaptığınızı bilir); uygulamaya **e-posta adresiniz, adınız ve Google kullanıcı kimliğiniz (sub)** döner |
| GitHub ile giriş | `github.com`, `api.github.com` | ABD | Aynı akış; uygulamaya **e-posta adresiniz, kullanıcı adınız ve GitHub kullanıcı kimliğiniz** döner |

Bu akış **yalnız sosyal giriş düğmesine basarsanız** çalışır. E-posta + şifre ile açılan
hesapta hiçbir kimlik sağlayıcısına istek gitmez. Sosyal girişle açılmış bir hesaba sonradan
şifre belirleyip (`Hesap → Şifre belirle`) sağlayıcıdan bağımsız hale gelebilirsiniz.

## 4. Kullanılmayanlar (bilinçli)

- **Banka bağlantısı / açık bankacılık:** YOK. Hesap verisi otomatik çekilmez.
- **Analitik/izleme (Google Analytics, piksel):** YOK.
- **Reklam ağı:** YOK.
- **Kimlik-hizmeti platformu (Firebase/Auth0 gibi kullanıcı veritabanını DIŞARIDA
  tutan servisler):** YOK — oturumlar kendi `SECRET_KEY`'imizle imzalanır, kullanıcı kaydı
  kendi veritabanımızda kalır. (Google/GitHub ile giriş **opsiyonel** olarak vardır ve
  §3b'de ayrıca beyan edilir; orada dışarıda tutulan bir kullanıcı veritabanı yoktur,
  yalnız giriş anında kimlik doğrulanır.)

## 5. Doğrulama

Bu envanterin kodla tutarlılığı `tests/test_veri_isleyen_envanteri_kapisi.py` ile
kilitlenir. Kapı iki bağımsız türetme yapar ve İKİSİNİ de bu dosyayla karşılaştırır:

1. **Sınıf türetmesi:** `app.coach.LLMProvider`'ın somut alt sınıfları (SDK ile konuşan
   sağlayıcılar URL literali taşımaz — Gemini/Anthropic/Groq bu yolla görünür).
2. **Host türetmesi:** `app/` içindeki her `https://…` literalinin host'u; host adı bu
   dosyada **birebir** yazılı olmalıdır (marka adı eşleştirmesi belirsiz olduğu için
   kabul edilmez).

Böylece yeni bir LLM sağlayıcısı, fiyat kaynağı, kimlik sağlayıcısı veya herhangi bir dış
HTTP entegrasyonu eklenip bu dosya güncellenmezse süit KIRILIR. (Önceki sürüm bu iddiayı
`tests/test_legal_docs.py`'ye dayandırıyordu; o test dört ismi SABİT kodluyor, kodu hiç
okumuyordu — Together AI ve DeepInfra üç hafta boyunca beyan edilmeden zincirde kaldı.
Denetim bulgusu D25 / BUG #242.)
