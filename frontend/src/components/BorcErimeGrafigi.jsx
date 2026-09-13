import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceDot, ResponsiveContainer } from 'recharts';
import { formatPara, kisaSayi } from '../lib/money.js';
import { KATEGORIK, IZGARA, IZGARA_OPAKLIK, NOKTA_KENAR, lejantMetni } from '../lib/grafikRenkleri.js';

/**
 * Borç eritme projeksiyonu — DVIZ-009 (BUG #459).
 * İki stratejinin ay sonu TOPLAM kalan bakiyesi (backend `kalan_seri`); 0. ay = bugünkü toplam.
 * Sıfırlanma ayı noktayla işaretli. Görselleştirmedir; öneri metni StrategyCard'da kalır.
 */
export function erimeSerisi(baslangic, snowball, avalanche) {
  const n = Math.max(snowball?.kalan_seri?.length || 0, avalanche?.kalan_seri?.length || 0);
  if (!n) return [];
  const rows = [{ ay: 0, snowball: baslangic, avalanche: baslangic }];
  for (let i = 0; i < n; i++) {
    rows.push({
      ay: i + 1,
      snowball: snowball?.kalan_seri?.[i] ?? null,
      avalanche: avalanche?.kalan_seri?.[i] ?? null,
    });
  }
  return rows;
}

export function erimeOzeti(rows, snowball, avalanche) {
  if (!rows.length) return 'Borç eritme projeksiyonu: veri yok';
  return `Borç eritme projeksiyonu: başlangıç ${formatPara(rows[0].snowball)}; kartopu ${snowball?.months_to_freedom ?? '?'} ayda, çığ ${avalanche?.months_to_freedom ?? '?'} ayda sıfırlanır`;
}

export default function BorcErimeGrafigi({ debts, snowball, avalanche }) {
  const baslangic = (debts || []).reduce((t, d) => t + Number(d.balance || 0), 0);
  const rows = erimeSerisi(baslangic, snowball, avalanche);
  if (!rows.length) return null;
  const renk = { snowball: KATEGORIK[1], avalanche: KATEGORIK[0] };
  return (
    <div className="card p-4">
      <h3 className="text-sm font-semibold mb-1 text-zinc-700 dark:text-zinc-300">Eritme projeksiyonu</h3>
      <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-3">Ay sonu toplam kalan borç · nokta = sıfırlanma ayı</p>
      <div style={{ width: '100%', height: 220 }} role="img" aria-label={erimeOzeti(rows, snowball, avalanche)}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={rows} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={IZGARA} strokeOpacity={IZGARA_OPAKLIK} />
            <XAxis dataKey="ay" tickFormatter={(v) => `${v}. ay`} tick={{ fontSize: 11, fill: 'currentColor', opacity: 0.6 }} />
            <YAxis tickFormatter={kisaSayi} tick={{ fontSize: 11, fill: 'currentColor', opacity: 0.6 }} width={52} />
            <Tooltip formatter={(v, ad) => [formatPara(v), ad === 'snowball' ? 'Kartopu' : 'Çığ']} labelFormatter={(v) => `${v}. ay`} />
            <Legend formatter={lejantMetni((v) => (v === 'snowball' ? 'Kartopu' : 'Çığ'))} />
            <Line type="monotone" dataKey="snowball" stroke={renk.snowball} strokeWidth={2} dot={false} connectNulls />
            <Line type="monotone" dataKey="avalanche" stroke={renk.avalanche} strokeWidth={2} dot={false} connectNulls />
            {snowball?.months_to_freedom > 0 && snowball.months_to_freedom <= rows.length - 1 && (
              <ReferenceDot x={snowball.months_to_freedom} y={0} r={5} fill={renk.snowball} stroke={NOKTA_KENAR} />
            )}
            {avalanche?.months_to_freedom > 0 && avalanche.months_to_freedom <= rows.length - 1 && (
              <ReferenceDot x={avalanche.months_to_freedom} y={0} r={5} fill={renk.avalanche} stroke={NOKTA_KENAR} />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
