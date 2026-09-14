// UX-035 (BUG #480): başarı anları — ölçülü kutlama.
// Sinyal ÜRETİLMEZ, okunur: borç kilometre taşı backend'den gelir (FEAT-017 `borc_ilerleme`
// › `yeni_milestone`, %10/25/50/75; yalnız koça gidiyordu, arayüz sessizdi), hedef tamamlanması
// sunucunun `achieved` geçişidir. Burada yalnız metin ve "bir kez" kuralı var.
// ÖLÇÜLÜ: konfeti tek sefer (anahtar localStorage'da), 1,8 sn, hareket azaltma tercihinde hiç;
// pankart o gün boyunca kalır (bilgi), konfeti tekrar etmez (gürültü).
import { formatPara } from './money.js';

export const KUTLAMA_ONEKI = 'fos_kutlama_';

export function hareketAzaltilmisMi() {
  try {
    return typeof window !== 'undefined'
      && typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch {
    return false;
  }
}

export function kutlandiMi(anahtar) {
  try { return localStorage.getItem(KUTLAMA_ONEKI + anahtar) === '1'; } catch { return false; }
}

export function kutlandi(anahtar) {
  try { localStorage.setItem(KUTLAMA_ONEKI + anahtar, '1'); } catch { /* özel pencere: sessiz */ }
}

/** Borç kilometre taşı metni; taze geçiş yoksa null (kutlama üretilmez). */
export function borcKutlamasi(bi) {
  if (!bi || !bi.yeni_milestone) return null;
  const yuzde = Number(bi.yeni_milestone);
  const odendi = Number(bi.odendi || 0);
  return {
    anahtar: `borc_${yuzde}_${bi.baslangic_tarih || ''}`,
    baslik: `🏆 Borcunu %${yuzde} azalttın`,
    detay: odendi > 0
      ? `${formatPara(odendi, { ondalik: 0 })} ödendi; kalan ${formatPara(Number(bi.guncel_borc || 0), { ondalik: 0 })}.`
      : null,
  };
}

/** Hedef tamamlanma metni: önceki durum achieved değilken sonraki achieved ise. */
export function hedefKutlamasi(onceki, sonraki) {
  if (!sonraki || sonraki.status !== 'achieved' || onceki?.status === 'achieved') return null;
  return {
    anahtar: `hedef_${sonraki.id}`,
    baslik: `🎉 Hedef tamamlandı: ${sonraki.title}`,
    detay: sonraki.goal_type === 'debt_freedom' ? 'Borç hedefi kapandı.' : `${formatPara(Number(sonraki.target_amount || 0), { ondalik: 0 })} birikti.`,
  };
}
