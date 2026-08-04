# ADR-041 — Kullanıcı başına LLM kotası (maliyet + adalet guard'ı)

**Durum:** Kabul edildi · **Tarih:** 2026-08-05 · **Faz:** P3 (Wave-9 publish yolu)
**İlgili:** ADR-001 (Rules Engine karar verir, LLM açıklar), ADR-029, BUG #188

## Bağlam

Kapalı betaya çıkarken koç (LLM) maliyeti **paylaşılan** bir kaynaktır: tek bir API anahtarı
tüm kullanıcılara hizmet eder. Mevcut koruma `PROVIDER_DAILY_LIMITS` idi — yani sağlayıcının
(Gemini ücretsiz kademe) günlük kotası. Bu bir kullanıcı guard'ı **değildir**:

1. **Adalet:** Kotayı tüketen tek kullanıcı, diğer herkesin koçunu kapatır.
2. **Maliyet:** Ücretli kademeye geçildiğinde tavan yok — bir kullanıcı faturayı tek başına büyütür.
3. **Kapsam boşluğu:** TPM-limitli sağlayıcılarda (Groq/Cerebras) günlük limit bilinmediği için
   `limit=0` dalı hiçbir engel uygulamıyordu.
4. **Çarpan:** İki-geçiş ("plan-sonra-yaz") mimarisi nedeniyle her koç mesajı **2 çağrı** eder.

## Karar

**Kullanıcı başına günlük LLM çağrı tavanı** uygulanır; sağlayıcı kotasından bağımsızdır.

- Env: `COACH_DAILY_USER_LIMIT` (varsayılan **80 çağrı ≈ 40 mesaj/gün**; `0` = kapalı).
- Sayaç: `ApiCallLog` üzerinden, **UTC günü** (sunucu yerel saatiyle erken sıfırlanmasın — BUG #133 dersi).
- Dayatma noktası: `POST /api/coach/chat`, motor çağrılmadan **önce** (para harcanmadan).
- Şeffaflık: `GET /api/coach/usage` `user_today_count` / `user_daily_limit` döner (UI rozeti).

### Tavan dolduğunda davranış (kritik ürün kararı)

Uygulama **kapanmaz**: Rules Engine deterministiktir ve LLM'siz çalışır (ADR-001). Cockpit,
bütçe, borç stratejisi, hedefler, raporlar — hepsi çalışmaya devam eder. Yalnız sohbet durur ve
kullanıcı **iç yapılandırma sızdırmayan** bir mesaj görür ("Bugünkü koç kullanım hakkın doldu;
paneller ve hesaplamalar çalışmaya devam ediyor"). Eskiden mesaj `.env: LLM_PROVIDER=anthropic`
gibi operatör tavsiyesi içeriyordu — son kullanıcı için anlamsız, iç mimariyi ifşa eder.

## Alternatifler

- **Token-bazlı maliyet muhasebesi:** daha adil (uzun mesaj = daha pahalı) ama sağlayıcı başına
  fiyat tablosu ve sürekli bakım gerektirir. Kapalı beta ölçeğinde çağrı-sayısı yeterli ve
  denetlenebilir. Açık betada (P8) token bazlıya geçiş değerlendirilecek.
- **Yalnızca sağlayıcı kotasına güvenmek:** reddedildi — adaletsiz (bir kullanıcı herkesi
  kilitler) ve ücretli kademede maliyet tavanı yok.
- **Kullanıcı başına API anahtarı:** en temiz izolasyon ama beta kullanıcısından anahtar
  istemek kabul edilebilir bir onboarding değil. Egemen/offline mod (Ollama, LLM-005) isteyen
  kullanıcı için zaten mevcut.

## Sonuçlar

- (+) Bir kullanıcı diğerlerini kilitleyemez; maliyet öngörülebilir.
- (+) Ücretsiz kademe kotası birden fazla kullanıcıya adilce dağılır.
- (−) Yoğun kullanıcı gün içinde durur. Kabul: tavan env ile kullanıcı-tipine göre
  yükseltilebilir; ileride plan/rol bazlı tavan eklenebilir.
- **Kanıt:** `tests/test_coach_user_quota.py` (5 test) — tavan dayatılıyor, bir kullanıcının
  tüketimi diğerini kilitlemiyor, dünkü çağrılar sayılmıyor, mesajda iç jargon yok.
