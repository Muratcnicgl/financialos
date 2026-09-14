// FE-027 (BUG #490): hedef kuralı kriterlerinin okunabilir metni ve formdan kriter üretimi.
// Kriter anahtarları backend `app/goal_rules.py`nin desteklediği küme: tx_type, amount_min,
// amount_max, account_id, account_type, description_contains. Bilinmeyen anahtar ham gösterilir
// (gizlenmez — kullanıcı kuralın ne yaptığını bilmeli).
import { formatPara } from './money.js';

const TUR = { income: 'gelir', expense: 'gider', transfer: 'transfer' };
const HESAP_TIPI = { cash: 'nakit', credit_card: 'kredi kartı', loan: 'kredi', investment: 'yatırım' };

export function kriterMetni(criteria, accounts = []) {
  if (!criteria || typeof criteria !== 'object' || Object.keys(criteria).length === 0) return 'her işlem';
  const parcalar = [];
  for (const [k, v] of Object.entries(criteria)) {
    if (k === 'tx_type') parcalar.push(`${TUR[v] || v} işlemleri`);
    else if (k === 'amount_min') parcalar.push(`tutar ≥ ${formatPara(Number(v))}`);
    else if (k === 'amount_max') parcalar.push(`tutar ≤ ${formatPara(Number(v))}`);
    else if (k === 'account_id') {
      const h = accounts.find((a) => a.id === Number(v));
      parcalar.push(`hesap: ${h ? (h.name || h.ad) : `#${v}`}`);
    } else if (k === 'account_type') {
      const l = Array.isArray(v) ? v : [v];
      parcalar.push(`hesap tipi: ${l.map((t) => HESAP_TIPI[t] || t).join('/')}`);
    } else if (k === 'description_contains') parcalar.push(`açıklamada "${v}"`);
    else parcalar.push(`${k}=${JSON.stringify(v)}`);
  }
  return parcalar.join(', ');
}

export function ayirmaMetni(rule) {
  if (rule.allocation_type === 'percent') return `%${Number(rule.allocation_value)} ayrılır`;
  if (rule.allocation_type === 'fixed') return `${formatPara(Number(rule.allocation_value))} ayrılır`;
  return 'tamamı ayrılır';
}

/** Form alanlarından kriter nesnesi; boş alan girmez. En az bir kriter zorunlu (aksi: null). */
export function kriterOlustur({ txType, amountMin, descriptionContains }, parseTR) {
  const c = {};
  if (txType) c.tx_type = txType;
  const min = amountMin ? parseTR(amountMin) : null;
  if (min != null && Number.isFinite(min) && min > 0) c.amount_min = min;
  if (descriptionContains && descriptionContains.trim()) c.description_contains = descriptionContains.trim();
  return Object.keys(c).length ? c : null;
}
