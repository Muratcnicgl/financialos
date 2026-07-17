# Günlük Kullanım Döngüsü — Murat için 1 Haftalık Kullanım Turu

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

**Giriş:** Google ile devam et → muraticgil@gmail.com. (Bu hesap = user id=1 = 6 gerçek hesabın.)
İlk açılışta stale token varsa uygulama otomatik login ekranına düşer (M61 — artık kilitlemez).

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

- **Fiyat cron'u backend kapalıyken çalışmaz** → TLY fiyatı bayatlayabilir (dev makinesi sınırı; deploy sonrası çözülür).
- **Aile/paylaşımlı workspace** kurulu ama şu an tek kullanıcısın (personal). Header'da workspace seçici >1 workspace olunca çıkar.
- **Kripto/BIST hisse** henüz yok (Wave-4 kalanı ertelendi).

## Sorun çıkarsa

1. Ekran görüntüsü al + hangi adımda olduğunu not et (yukarıdaki tablo No).
2. Backend terminal log'una bak (`logs/financialos.log`).
3. Wave-5 girdisi olarak biriktir — bu turun amacı tam olarak bu.

## Turun sonunda

Bir hafta sonra: hangi adımlar akıcıydı, hangileri sürtünmeliydi, hangi bug'lar çıktı →
Wave-5 charter'ının **gerçek** (hayali değil) baseline'ı bu olacak.
