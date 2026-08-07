# ADR-047 — Uygulamanın iki görünümü vardır; ikisi de RENDER EDİLEREK ölçülür

**Durum:** Kabul edildi · **Tarih:** 2026-08-07 · **Faz:** PUBLISH / kapalı beta öncesi yüzey borcu
**İlgili:** ADR-010 (44px dokunma hedefi — bu ADR onun gerekçesini düzeltir), ADR-040 (mobil = PWA),
ADR-044 (para birimi tek kaynak — aynı "anlam koda kaçmış" sınıfı), ADR-011 (renk paleti değil,
fiyat sağlayıcı — karıştırılmasın)
**Bug:** #265

## Bağlam

Uygulama `darkMode: 'class'` ile **iki ayrı görünüm** üretir (`<html>` ve `<html class="dark">`),
varsayılan koyudur, tercih `localStorage`'da saklanır. Mobil strateji PWA'dır (ADR-040) — yani
kapalı betaya davet edilen kişilerin çoğu uygulamayı **telefon genişliğinde** açacak.

Ölçüm (7 Ağu 2026, 390×844 viewport, 13 panel × 2 tema, gerçek tarayıcıda render):

| Bulgu | Kanıt |
|---|---|
| Dört panel tamamen **koyu-varsayan** yazılmıştı (Hedefler, Borç Stratejisi, Aile, Giriş) | `Goals.jsx` 33, `DebtStrategy.jsx` 28, `Workspace.jsx` 27, `Login.jsx` 13 kullanım |
| Açık temada **başlık görünmüyordu** | "Hedefler" → `rgb(244,244,245)` / `rgb(250,250,250)` = **1.05** |
| Boş-durum yazıları görünmüyordu | "Hedef yok" / "Aktif borç yok" = **1.27** |
| Aile panelinin üye satırları okunmuyordu | **1.22** ve **1.42** |
| İkincil metin WCAG altındaydı | `text-zinc-400` beyaz üzerinde **2.46–2.56** |
| **Koyu** temada grafik serisi ve lejant metni okunmuyordu | `#4f46e5` / `rgb(24,24,27)` = **2.82** |
| Dokunma hedefleri 44px altındaydı | sekmeler 42px, `.input` 35px, aralık düğmeleri 28px, lejant 20px, onay kutusu 13px |

Statik sınıf taraması bu tabloyu **üretemedi**: ilk tarayıcı sürümü 128 kullanımın 123'ünü
kaçırdı (`className="…"` yakalaması hatalıydı) ve 5 bulgu raporladı — yani "taradım, temiz"
denilebilecek bir sonuç verdi. İkinci görünüm ancak **render edilince** ölçülür.

## Karar

1. **Ölçülen değişmez, render edilen sayfadadır.** Kalıcı kapı `frontend/e2e/tema-mobil.spec.js`:
   her panel × her tema, 390×844'te açılır ve dört şey ölçülür — metin kontrastı ≥ 3:1,
   yatay taşma yok, dokunma hedefi ≥ 44px, konsol hatası yok. Kapı CI'nın `e2e` işinde koşar.
2. **Kontrast eşiği 3:1'dir** — WCAG AA'nın *büyük metin* eşiği. Bu bir hedef değil **alt
   sınırdır**: 3:1'in altı "okunmuyor" demektir, üstü "iyi" demek değildir. Eşiğin gövde metni
   için 4.5 olması gerektiği doğrudur; bugünkü tabanın gerçeği 3.0'dır ve **bayat bir 4.5
   iddiası, dürüst bir 3.0 ölçümünden kötüdür**. Yükseltme ayrı bir iştir (A11Y boyutu).
3. **Renk kararı temayı bilmek zorundadır.** İki yol vardır: (a) `x dark:y` çifti (Tailwind
   sınıfları), (b) **iki temada da ≥ 3:1 veren tek değer** (grafikler). Grafiklerde (b) seçildi
   çünkü Recharts renkleri SVG *özniteliği* olarak alır — CSS değişkeni orada çözülmez, tema
   okumak için ayrı bir abonelik mekanizması gerekirdi ve bu, rengin ikinci bir gerçek kaynağını
   üretirdi. Tek kaynak: `frontend/src/lib/grafikRenkleri.js`; her değerin iki orandı yorumda
   yazılıdır ve lejant metni seri rengini miras aldığı için **kapı onu da ölçer**.
4. **Dokunma hedefinin iki YAZILI istisnası vardır** (başkası yok):
   (a) cümle içindeki kontrol — WCAG 2.5.8 "inline" istisnası; boyut satır yüksekliğiyle
   kısıtlıdır, büyütmek metni bozar. (b) `<label>` içine sarılmış onay/seçim kutusu — tıklanabilir
   hedef label'dır, ölçülen odur.

## ADR-010'un düzeltilen gerekçesi

ADR-010 "global `.btn` class kalıcıdır; gelecekteki butonlar otomatik 44px alır" diyordu.
Ölçüm bunu çürüttü: `.btn`'i **kullanmayan** kontroller (ham `px-3 py-2`, `.input`, `.chip`)
13–42px çıkıyordu ve hiçbir koşum bunu görmüyordu. Bir sınıf, onu kullanmayanı zorlayamaz.
**Standardı kalıcı yapan sınıf değil, sınıfı kullanmayanı da yakalayan ölçümdür.**

## Alternatifler (reddedildi)

- **Statik sınıf kapısı (vitest).** Hızlıdır ve pre-commit'te koşar; ama ölçtüğü şey *sınıf
  adıdır*, iddia edilen şey *kontrasttır*. İkinci ve zayıf bir "gerçek kaynak" üretir: beyaz
  zemin üstündeki beyaz metni yakalayamaz, `text-white`'ı muaf tutmak zorundadır ve varyant
  zincirlerinde (`dark:hover:text-zinc-200`) yanlış-pozitif verir. Bir iddiayı ancak onu ölçen
  koşum kapatır (KURAL R3).
- **Tema-duyarlı grafik paleti (hook + MutationObserver).** Daha "doğru" görünür; ama renk
  için ikinci bir karar noktası ve abonelik yaşam döngüsü ekler. İki temada da geçen tek değer
  aynı sonucu daha az parça ile verir (KURAL 12: kalitede eşitse basit olan).
- **Açık temayı kaldırmak.** Tercih zaten kullanıcıda ve `localStorage`'da; kaldırmak defekti
  değil kullanıcının seçimini siler.

## Sonuç

`frontend/e2e/tema-mobil.spec.js` yeşil olduğu sürece "uygulama iki temada da okunur ve telefonda
kullanılabilir" bir **ölçüm**dür, iddia değil. Mutasyon kanıtı 3/3: başlığı `text-zinc-100`'e
geri al → kırmızı; `.input`'tan `min-h-[44px]` kaldır → kırmızı; grafik serisini `#4f46e5`'e
geri al → kırmızı.
