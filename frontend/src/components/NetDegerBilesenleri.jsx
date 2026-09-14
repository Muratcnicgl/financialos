import { Area, Line, ComposedChart, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ReferenceLine, ResponsiveContainer } from 'recharts';
import { formatDate } from '../api.js';
import { formatPara, kisaSayi } from '../lib/money.js';
import { KATEGORIK, SERI, EKSEN, IZGARA, IZGARA_OPAKLIK, lejantMetni } from '../lib/grafikRenkleri.js';

/**
 * Net değer KOMPOZİSYONU — DVIZ-012 (BUG #458).
 * Snapshot'ın sakladığı bileşenler (nakit, yatırım, alacak = +; kart borcu, kredi = −) yığılmış
 * alan olarak; tam net değer çizgi olarak üstte. "Net değer nasıl oluşuyor, hangi kalem
 * hareket ediyor" sorusu için; varsayılan çizgi görünümü olduğu gibi kalır (toggle).
 */
const ETIKET = {
  cash: 'Nakit', investment_value: 'Yatırım', receivables: 'Alacak',
  card_debt_neg: 'Kart borcu', loan_debt_neg: 'Kredi', net_worth_full: 'Tam net değer',
};

export function bilesenSerisi(items) {
  return (items || []).map((r) => ({
    date: r.date,
    cash: Number(r.cash || 0),
    investment_value: Number(r.investment_value || 0),
    receivables: Number(r.receivables || 0),
    card_debt_neg: -Math.abs(Number(r.card_debt || 0)),
    loan_debt_neg: -Math.abs(Number(r.loan_debt || 0)),
    net_worth_full: Number(r.net_worth_full || 0),
  }));
}

function Ipucu({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="card p-2 text-xs space-y-0.5">
      <p className="font-medium">{formatDate(label)}</p>
      {payload.map((p) => (
        <p key={p.dataKey} className="font-numeric" style={{ color: p.color || p.stroke }}>
          {ETIKET[p.dataKey] || p.dataKey}: {formatPara(p.value)}
        </p>
      ))}
    </div>
  );
}

export default function NetDegerBilesenleri({ items, tickColor }) {
  const seri = bilesenSerisi(items);
  const [nakit, yatirim, alacak, kart, kredi] = [KATEGORIK[0], KATEGORIK[2], KATEGORIK[4], SERI.negatif, KATEGORIK[1]];
  return (
    // role=img: üst sarmalayıcıda (Reports.jsx net değer kartı) — özet oradaki aria-label'da
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={seri} margin={{ top: 8, right: 16, left: 8, bottom: 0 }} stackOffset="sign">
        <CartesianGrid strokeDasharray="3 3" stroke={IZGARA} strokeOpacity={IZGARA_OPAKLIK} />
        <XAxis dataKey="date" tickFormatter={(v) => formatDate(v)} tick={{ fontSize: 11, fill: tickColor }} />
        <YAxis tickFormatter={kisaSayi} tick={{ fontSize: 11, fill: tickColor }} width={52} />
        <Tooltip content={<Ipucu />} />
        <Legend formatter={lejantMetni((v) => ETIKET[v] || v)} />
        <ReferenceLine y={0} stroke={EKSEN} strokeDasharray="4 2" />
        <Area type="monotone" dataKey="cash" stackId="a" fill={nakit} stroke={nakit} fillOpacity={0.35} />
        <Area type="monotone" dataKey="investment_value" stackId="a" fill={yatirim} stroke={yatirim} fillOpacity={0.35} />
        <Area type="monotone" dataKey="receivables" stackId="a" fill={alacak} stroke={alacak} fillOpacity={0.35} />
        <Area type="monotone" dataKey="card_debt_neg" stackId="a" fill={kart} stroke={kart} fillOpacity={0.3} />
        <Area type="monotone" dataKey="loan_debt_neg" stackId="a" fill={kredi} stroke={kredi} fillOpacity={0.3} />
        <Line type="monotone" dataKey="net_worth_full" stroke={SERI.pozitif} strokeWidth={2} dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
