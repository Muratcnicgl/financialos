// UX-024 (BUG #479): borç planını hedefe bağlama — tek kaynak.
// Analiz (Borç Stratejisi) ile taahhüt (Hedefler › debt_freedom) arasındaki köprü.
// Aktif bir borç hedefi varsa plan ONA yazılır (ikinci hedef üretilmez); yoksa hedef
// yaratılır: tutar = bugünkü toplam borç, tarih = seçilen planın bitişi.
import { formatPara } from './money.js';

export const STRATEJI_ADI = { snowball: 'Kartopu', avalanche: 'Çığ' };

export function planEtiketi(plan) {
  if (!plan) return '';
  const ekstra = Number(plan.aylik_ekstra || 0);
  const ad = STRATEJI_ADI[plan.strateji] || plan.strateji;
  return ekstra > 0 ? `${ad} + ${formatPara(ekstra, { ondalik: 0 })}/ay` : ad;
}

export async function planBenimse({ goalsApi, mevcut, strateji, aylikEkstra, strateji_sonucu, debts }) {
  const plan = { strateji, aylik_ekstra: Number(aylikEkstra || 0) };
  const target_date = strateji_sonucu?.payoff_date || null;
  if (mevcut) {
    return goalsApi.update(mevcut.id, { plan, ...(target_date && { target_date }) });
  }
  const toplamBorc = (debts || []).reduce((t, d) => t + Number(d.balance || 0), 0);
  return goalsApi.create({
    goal_type: 'debt_freedom',
    title: `Borçsuz ol — ${STRATEJI_ADI[strateji] || strateji}`,
    target_amount: toplamBorc > 0 ? toplamBorc : 1,
    target_date,
    plan,
  });
}
