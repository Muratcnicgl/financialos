# Günlük Kullanım Döngüsü

> ## ⚠️ BU BELGE 48 GÜN DOKUNULMADI — 5 Eylül 2026'da DENETLENDİ
>
> `scripts/belge_denetimi` bayat belge raporunda çıktı ve **üç iddiası gerçekle
> çelişiyordu**. Aşağıdaki gövde Wave-5 dönemine (Temmuz 2026) aittir ve **bir haftalık
> ilk kullanım turu** için yazılmıştı; o amaç tamamlandı. Tarihsel değeri için duruyor,
> **düzeltmeler yerlerinde işaretlendi.**
>
> **Bugünün gerçeği (ölçüldü):** uygulama kapalı betada **tek adresten** koşuyor
> (`SERVE_SPA=1`, ayrı frontend sunucusu yok) ve `deploy/windows/baslat.ps1` ile
> başlatılıyor. Aşağıdaki iki terminallik kurulum yalnız **geliştirme** içindir.

**Amaç:** W4-KURTARMA (M61-M65) sonrası FinancialOS artık gerçek login + gerçek veri girişine
hazır. Bu rehber, sistemi **gerçekten kullanarak** (mock/curl değil, uygulamanın kendi akışıyla)
1 hafta test etmen için. Çıkan her sorun Wave-5'in gerçek girdisi olacak.

> **Neden bu tur kritik:** 74 gün / 400 commit / 968 test boyunca `transactions` tablosu **0 satır**
> kaldı — sistem kuruldu ama kullanılmadı. Bu turun tek amacı: **döngüyü gerçekten işletmek.**

## Kurulum (bir kez)

```powershell
# Backend (AUTH_ENABLED=true — gerçek login)
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
# Frontend (ayrı terminal)
cd frontend; npm run dev   # http://localhost:5173
```

**Giriş:** Google ile devam et. *(Düzeltme 5 Eyl 2026: bu satır bir e-posta adresi ve
"user id=1" yazıyordu. Kurucunun canlı profili artık **u1 değil**; u1, 3 Ağustos'ta açılmış
ve 5 Ağustos'tan beri kullanılmayan eski bir profildir. Kişisel adres kullanıcıya bakan bir
belgeden çıkarıldı.)* İlk açılışta stale token varsa uygulama otomatik login ekranına düşer
(M61 — artık kilitlemez).

## Günlük döngü (her gün ~2 dakika)

| Adım | Ne yap | Ne beklenir | Bozulursa BUG |
|------|--------|-------------|---------------|
| **1. Harcama gir** | İşlemler → hızlı giriş: `230 yemek` veya form | İşlem eklenir, ilgili hesap bakiyesi düşer, kategori otomatik atanır | tutar/bakiye tutmuyor · kategori boş |
| **2. Cockpit oku** | Cockpit sekmesi | Nakit/kart/kredi/reel bütçe/sağlık güncel; "İlk adım" önerisi mantıklı | sayı değişmedi · reel bütçe yanlış |
| **3. Koça sor** | Koç: "bugün ne kadar harcayabilirim?" / "durumum ne?" | Cockpit rakamlarıyla tutarlı, sert-dürüst Türkçe cevap | koç hata verdi · rakam uydurdu (grounding) |
| **4. Aksiyonu onayla** | Koç bir eylem önerirse (sattım/ödedim) → Onayla | PendingAction → execute → DB güncellenir, ActionHistory'e düşer | onay çalışmadı · çift kayıt |
| **5. Hedefe bak** | Hedefler: bir tasarruf/borç hedefi ilerlemesi | Allocation toplamı + projeksiyon tutarlı | ilerleme donuk |

## Haftalık (bir kez)

- **Maaş geldiğinde:** Gelir/Borç → düzenli gelir "tetikle" (trigger-due) → maaş işlemi önerisi → onayla.
- **Kart ödemesi:** kart borcu ödedikten sonra işlem gir → kart borcu düşsün.
- **Yatırım:** TLY fiyatı güncel mi (backend açıkken 02:45 cron çeker; kapalıysa elle bak).

## Neye dikkat et (bilinen sınırlar — bug değil)

- ~~**Fiyat cron'u backend kapalıyken çalışmaz** → fiyat bayatlayabilir; deploy sonrası çözülür.~~
  **ARTIK YANLIŞ (5 Eyl 2026 düzeltmesi).** BUG #302 (12 Ağu) açılışta
  `kacirilan_isleri_telafi_et()` ekledi ve bu, `PLANLI_ISLER`in **5'ini de** kapsıyor —
  fiyat çekimi dahil. Makine kapalıyken atlanan koşum, açılışta **telafi ediliyor**
  (kanıt: `5/5 is telafi edildi`). Bu satırı okuyan biri fiyatların bayat kaldığını
  sanardı; **kalmıyor, geç geliyor.**
- **Aile/paylaşımlı workspace** kurulu ama şu an tek kullanıcısın (personal). Header'da workspace seçici >1 workspace olunca çıkar.
- **Kripto/BIST hisse** henüz yok (Wave-4 kalanı ertelendi).

## Sorun çıkarsa

1. Ekran görüntüsü al + hangi adımda olduğunu not et (yukarıdaki tablo No).
2. Backend log'una bak (`logs/financialos.log`). ✅ **Bu satır DOĞRU** — `app/logging_config.py:73`
   oraya yazıyor, yapılandırılmış JSON, 10 MB × 5 devir.

   > *Dürüst kayıt: bu belge denetlenirken önce bu satır "yanlış" diye işaretlenip
   > `uvicorn.out.log`'a yönlendirilmişti. **Yanlış olan düzeltmeydi** — dosya ölçülmeden
   > "bayat" varsayıldı; ölçünce bugün 00:04'te yazılmış canlı bir log çıktı. Bayatlık
   > avlarken bayat olmayanı bayat ilan etmek, aynı hatanın ters yönüdür.*
   >
   > Tamamlayıcı log'lar (uygulama log'unun yerine değil, yanına): servis olayları
   > `logs/servis.log` · sağlık/dış yol `logs/saglik.log` · uvicorn'un ham çıktısı
   > `logs/uvicorn.out.log` ve `logs/uvicorn.err.log`.
3. Wave-5 girdisi olarak biriktir — bu turun amacı tam olarak bu.

## Turun sonunda

Bir hafta sonra: hangi adımlar akıcıydı, hangileri sürtünmeliydi, hangi bug'lar çıktı →
Wave-5 charter'ının **gerçek** (hayali değil) baseline'ı bu olacak.
