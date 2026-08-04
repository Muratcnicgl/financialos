# Veri İşleyen Envanteri

**Güncelleme:** 5 Ağu 2026 · KVKK m.10 aydınlatma yükümlülüğünün dayanağı.
Kullanıcı verisine dokunabilen **her** üçüncü taraf burada listelenir. Yeni bir
sağlayıcı eklendiğinde bu dosya ve KVKK metni **aynı commit'te** güncellenir.

## 1. LLM sağlayıcıları (koç özelliği — YURT DIŞI aktarım)

| Sağlayıcı | Gönderilen veri | Konum | Not |
|---|---|---|---|
| Google Gemini | Cockpit özeti (bakiye/borç/gelir toplamları), kırmızı çizgi metinleri, kullanıcı mesajı | ABD/AB | Ücretsiz kademe; API kullanım verisi sağlayıcı politikasına tabidir |
| Groq / Cerebras | aynı | ABD | Yedek zincir (fallback) |
| OpenRouter | aynı | ABD | Yedek zincir |
| Anthropic | aynı | ABD | Opsiyonel |
| **Ollama (yerel)** | — | **Kullanıcının makinesi** | Egemen mod: veri dışarı ÇIKMAZ |

**Gönderilmeyenler:** şifre/hash, oturum token'ı, e-posta adresi, ham işlem listesi
(yalnız türetilmiş toplamlar ve kullanıcının kendi yazdığı metin gider).

**Kullanıcı kontrolü:** koç kullanılmadığında bu aktarım hiç olmaz; uygulamanın geri kalanı
(cockpit, bütçe, borç stratejisi, hedefler, raporlar) tamamen yereldir ve deterministiktir.

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
