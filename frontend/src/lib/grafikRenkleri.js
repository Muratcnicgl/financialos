import { createElement } from 'react';

/**
 * Grafik renkleri — TEK KAYNAK (BUG #265).
 *
 * GUNCELLEMELER
 * - BUG #265 fix (7 Agu 2026): grafik renkleri her dosyada ayri ayri hex olarak yaziliydi
 *   (`Reports.jsx` 10'luk COLORS + 3 seri, `BalanceTrend.jsx` 4 hex). Hepsi TEK temaya gore
 *   secilmisti: `#4f46e5` (brand-600) beyaz zeminde 6.29 ama koyu kartta **2.82** — yani
 *   uygulamanin VARSAYILAN temasinda cizgi de, Recharts'in ondan turettigi lejant metni de
 *   okunmuyordu. Renk secimi temayi bilmiyordu.
 *
 * DEGISMEZ: buradaki her renk hem acik (#ffffff) hem koyu (#18181b) kart zemininde
 * **>= 3:1** kontrast verir — yani tek deger iki temada da okunur, tema-anahtari gerekmez.
 * Olcen kapi: `frontend/e2e/tema-mobil.spec.js` (lejant metni seri rengini miras alir).
 * Yeni renk eklerken orani hesapla; "guzel duruyor" gerekce degildir.
 */

/**
 * Kategorik seri paleti (pasta/bar) — DVIZ-002 (BUG #456): RENK KÖRÜ GÜVENLİ, 6 renk.
 *
 * Ölçüldü (13 Eyl 2026, Machado 2009 protan/deutan simülasyonu + CIE76 ΔE): eski 10'luk
 * palette orange-600 ↔ amber-600 deutan altında ΔE 2,1 (ayırt edilemez), indigo ↔ purple
 * protan altında 3,2. Bu 6'lı, iki temada ≥ 3:1 kalan 19 aday arasından en küçük ikili
 * ΔE'yi (normal/protan/deutan) EN BÜYÜK yapan küme: 19,9 / 18,6 / 17,2 — hepsi "belirgin
 * fark" (ΔE > 10). Kategori 6'yı aşarsa kalanı "Diğer" olarak toplanır (Reports).
 * Ölçen kapı: `frontend/src/renk-koru-palet.test.jsx` (aynı simülasyonu JS'te koşar).
 */
export const KATEGORIK = [
  '#0072B2', // Okabe-Ito mavi      beyaz 5.19 / koyu 3.42
  '#D55E00', // Okabe-Ito turuncu   3.87 / 4.58
  '#059669', // emerald-600         3.77 / 4.70
  '#6366f1', // indigo-500          4.47 / 3.97
  '#0891b2', // cyan-600            3.68 / 4.81
  '#0d9488', // teal-600            3.74 / 4.73
];
export const KATEGORIK_TAVAN = KATEGORIK.length;   // bundan fazlası "Diğer"'de toplanır

/** Anlamli seriler — sayfa metniyle ayni anlam yuku (bkz. ADR-044 tek-kaynak ilkesi). */
export const SERI = {
  marka:   '#6366f1', // brand-500  — "Gorulen" net deger
  pozitif: '#059669', // positive-600 — "Tam" net deger, gelir
  negatif: '#ef4444', // negative-500 3.76 / 4.71 — gider, esik alti
  bakiye:  '#3b82f6', // blue-500   3.68 / 4.82 — bakiye seyri
};

/** Eksen yazisi — metin oldugu icin kontrast sarti burada da gecerli (zinc-500: 4.83 / 3.67). */
export const EKSEN = '#71717a';

/** Izgara/ayirici — METIN DEGIL (dekoratif); dusuk kontrast bilincli, iki temada da soluk. */
export const IZGARA = '#a1a1aa';
export const IZGARA_OPAKLIK = 0.35;

/** Nokta kenarligi — cizgiden ayirmak icin; iki temada da notr. */
export const NOKTA_KENAR = '#a1a1aa';

/**
 * A11Y-005 (BUG #441): Recharts lejant METNİ seri rengini miras alır; seri renkleri iki
 * temada >= 3:1 (grafik için yeter) ama gövde metni 4,5 ister ve tek hex ile iki temada
 * 4,5'i tutturmak mümkün değil. Çözüm: renk simgede kalır, metin gövde rengine döner.
 * Her <Legend formatter={lejantMetni(...)}> bunu kullanır; ölçen kapı e2e/tema-mobil.
 */
export const LEJANT_METIN_SINIFI = 'text-zinc-700 dark:text-zinc-300';
export function lejantMetni(etiketle = (v) => v) {
  // Bileşen değil, recharts `formatter` geri çağrısı; display-name burada anlamsız.
  // eslint-disable-next-line react/display-name
  return (value) => createElement('span', { className: LEJANT_METIN_SINIFI }, etiketle(value));
}
