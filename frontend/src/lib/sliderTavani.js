/**
 * Ekstra ödeme kaydırıcısının üst sınırı — UX-025 (BUG #463).
 *
 * Sabit 5.000 üst sınır reel bütçeyle ilgisizdi: reel bütçesi 20.000 olan kullanıcı
 * "ne kadar ayırabilirim" sorusunu kaydırıcıda göremiyordu; 800 olanın kaydırıcısı hep
 * boş kalıyordu. Tavan = reel bütçenin %125'i, 500'e yuvarlanmış, en az 1.000; bütçe
 * bilinmiyorsa/negatifse eski 5.000 (varsayım değil, belgeli eski davranış).
 */
export const VARSAYILAN_TAVAN = 5000;

export function sliderTavani(reelButce) {
  const r = Number(reelButce);
  if (!Number.isFinite(r) || r <= 0) return VARSAYILAN_TAVAN;
  return Math.max(1000, Math.ceil((r * 1.25) / 500) * 500);
}

/** Referans işaretinin kaydırıcı üzerindeki yüzdesi (0–100); bütçe yoksa null. */
export function referansYuzde(reelButce, tavan) {
  const r = Number(reelButce);
  if (!Number.isFinite(r) || r <= 0 || !tavan) return null;
  return Math.min(100, Math.round((r / tavan) * 100));
}
