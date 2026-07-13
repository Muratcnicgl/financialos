# KVKK Açık Rıza Metni (v1)

**Yürürlük:** 13 Tem 2026 · **Versiyon:** v1 (`kvkk_consent_version`)

6698 sayılı Kişisel Verilerin Korunması Kanunu (KVKK) kapsamında, FinancialOS
uygulamasını kullanabilmeniz için aşağıdaki hususlarda açık rızanız alınır.

## 1. Veri Sorumlusu
FinancialOS **self-host** bir uygulamadır. Verileriniz **kendi sunucunuzda** (veya
uygulamayı çalıştıran kişinin sunucusunda) tutulur; üçüncü bir bulut hizmetine
aktarılmaz. Veri sorumlusu, uygulamayı barındıran gerçek/tüzel kişidir.

## 2. İşlenen Kişisel Veriler
- **Kimlik/iletişim:** e-posta adresi, ad (opsiyonel).
- **Kimlik doğrulama:** şifreniz **geri döndürülemez biçimde (bcrypt) hash'lenir** —
  düz metin saklanmaz.
- **Finansal veriler:** hesaplar, işlemler, borç/alacaklar, hedefler, bütçe — yalnızca
  sizin girdiğiniz veriler.
- **Kullanım:** koç sohbet geçmişi, uygulama içi kayıtlar.

## 3. İşleme Amacı
Kişisel finansal yönetim hizmetini sunmak: bakiye/nakit akışı takibi, borç stratejisi,
yapay zekâ finans koçu, hedef takibi. Verileriniz **reklam veya profilleme için
kullanılmaz, satılmaz.**

## 4. Yurt Dışına Aktarım
- Uygulama verileri sunucunuzda kalır.
- **İstisna — Koç (LLM):** Finans koçu özelliğini kullandığınızda, koça sorduğunuz
  bağlam (cockpit özeti) seçtiğiniz LLM sağlayıcısına (örn. Google Gemini) gönderilir.
  Bu, **yurt dışına aktarım** anlamına gelebilir. Koçu kullanmamayı veya **yerel/offline
  model** (Ollama) seçmeyi tercih edebilirsiniz (bkz. dev-commands.md — Egemen mod).

## 5. Haklarınız (KVKK m.11)
- **Erişim/taşınabilirlik:** `GET /api/users/me/export` ile tüm verinizi JSON olarak indirin.
- **Silme (unutulma):** `DELETE /api/users/me` ile hesabınız ve **tüm veriniz kalıcı olarak
  silinir** (geri alınamaz, cascade).
- **Düzeltme:** verilerinizi uygulama üzerinden güncelleyebilirsiniz.

## 6. Saklama Süresi
Verileriniz hesabınız aktif olduğu sürece saklanır. Hesabınızı sildiğinizde tüm veriniz
anında ve kalıcı olarak silinir.

## 7. Açık Rıza
Kayıt (register) sırasında bu metni onaylayarak, kişisel verilerinizin yukarıdaki
kapsam ve amaçlarla işlenmesine **açık rıza** vermiş olursunuz. Rıza zamanınız
(`kvkk_consent_at`) ve metin versiyonu (`kvkk_consent_version`) kaydedilir.
