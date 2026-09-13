/**
 * Hızlı giriş için kategori önerisi — UX-009 (BUG #468).
 * Kullanıcının kendi geçmişinden en sık kullanılan gider kategorileri (istemci tarafı sayım;
 * model yok, istek yok). Metin yalnız tutarken ("320") çip olarak sunulur; tıklayınca
 * "320 market" olur. Sistem/muhasebe kategorileri (borç ödeme vb.) önerilmez: onlar hızlı
 * giriş konusu değil, aksiyon konusu.
 */
const ONERILMEYEN = new Set(['borc_odeme', 'transfer', '(kategorisiz)', 'kategorisiz']);

export function enSikKategoriler(transactions, n = 3) {
  const sayim = new Map();
  for (const t of transactions || []) {
    if (t.transaction_type !== 'expense') continue;
    const k = (t.category || '').trim();
    if (!k || ONERILMEYEN.has(k.toLowerCase())) continue;
    sayim.set(k, (sayim.get(k) || 0) + 1);
  }
  return [...sayim.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'tr')).slice(0, n).map(([k]) => k);
}

/** Metin yalnız tutar mı? ("320", "1.250,50 ") → öneri gösterilir. */
export function yalnizTutar(metin) {
  return /^\s*[0-9][0-9.,]*\s*$/.test(String(metin || ''));
}
