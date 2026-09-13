import { useState, useEffect } from 'react';

/**
 * Oturumlar arası hatırlanan panel tercihi — UX-037 (BUG #462).
 *
 * `useState` gibi kullanılır; değer localStorage'da `fos_filtre_<anahtar>` altında tutulur.
 * Yalnız FİLTRE/GÖRÜNÜM tercihleri için (tarih aralığı gibi "bugüne göre" anlam taşıyan
 * değerler dahil DEĞİL — dünkü tarih aralığı bugün yanlış olur). localStorage yoksa ya da
 * bozuksa varsayılana düşer, hiç fırlatmaz (özel pencere, kapalı depolama).
 * Depolama cihaz başınadır (gorunumModu.js ile aynı bilinçli karar).
 */
const ONEK = 'fos_filtre_';

export function kaliciOku(anahtar, varsayilan) {
  try {
    const ham = localStorage.getItem(ONEK + anahtar);
    return ham === null ? varsayilan : JSON.parse(ham);
  } catch {
    return varsayilan;
  }
}

export function kaliciYaz(anahtar, deger) {
  try { localStorage.setItem(ONEK + anahtar, JSON.stringify(deger)); } catch { /* depolama kapalı */ }
}

export function useKaliciDurum(anahtar, varsayilan) {
  const [deger, setDeger] = useState(() => kaliciOku(anahtar, varsayilan));
  useEffect(() => { kaliciYaz(anahtar, deger); }, [anahtar, deger]);
  return [deger, setDeger];
}
