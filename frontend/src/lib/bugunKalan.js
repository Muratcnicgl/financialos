/**
 * Bugünün limit durumu — UX-004 / UX-005 (BUG #467).
 * `bugun_kalan` = günlük limit − bugün harcanan; negatif = aşım. ADR-026 zikzakta aşım yarınki
 * limiti otomatik düşürür; cümle bunu söyler (sanal "borçlanma" değil, gerçek dinamik).
 */
import { formatPara } from './money.js';

export function kalanCumlesi(kalan, limit) {
  if (kalan === null || kalan === undefined || limit === null || limit === undefined) return null;
  if (!Number.isFinite(Number(kalan)) || !Number.isFinite(Number(limit))) return null;
  const k = Number(kalan);
  if (k < 0) return `Bugün limit ${formatPara(-k, { ondalik: 0 })} aşıldı — yarınki limit o kadar düşer`;
  return `Bugün kalan ${formatPara(k, { ondalik: 0 })} / ${formatPara(limit, { ondalik: 0 })}`;
}

/** Hızlı girişteki tutar bugünkü kalanı aşıyorsa aşım miktarı; aşmıyorsa 0. */
export function asimMiktari(tutar, kalan) {
  const t = Number(tutar), k = Number(kalan);
  if (!Number.isFinite(t) || !Number.isFinite(k) || t <= 0) return 0;
  return t > k ? Math.round((t - k) * 100) / 100 : 0;
}

/** "320 market" / "1.250,50 kira" → sayısal tutar; bulunamazsa null. */
export function hizliTutar(metin, parseTRNumber) {
  const m = String(metin || '').trim().match(/^([0-9][0-9.,]*)/);
  if (!m) return null;
  const v = parseTRNumber ? parseTRNumber(m[1]) : Number(m[1]);
  return Number.isFinite(v) ? v : null;
}
