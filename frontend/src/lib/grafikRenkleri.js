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

/** Kategorik seri paleti (pasta/bar) — 10 ayirt edilebilir hue, hepsi iki temada >= 3:1. */
export const KATEGORIK = [
  '#6366f1', // indigo-500   beyaz 4.47 / koyu 3.97
  '#059669', // emerald-600  3.77 / 4.70
  '#ea580c', // orange-600   3.56 / 4.98
  '#0891b2', // cyan-600     3.68 / 4.81
  '#a855f7', // purple-500   3.96 / 4.48
  '#d97706', // amber-600    3.19 / 5.56
  '#f43f5e', // rose-500     3.67 / 4.83
  '#0d9488', // teal-600     3.74 / 4.73
  '#8b5cf6', // violet-500   4.23 / 4.18
  '#ec4899', // pink-500     3.53 / 5.02
];

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
