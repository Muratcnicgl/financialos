import { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, ReferenceLine } from 'recharts';
import { reportsApi } from '../api.js';
import { formatSayi, paraEtiketi } from '../lib/money.js';

/**
 * AylikSeri — son N ayın gelir/gider çubukları + tasarruf oranı (BUG #428 / DVIZ-004, FEAT-023).
 *
 * Aylık özet (A3) tek ayı ve önceki aya göre trendi verir; bu bileşen aynı sayıların
 * ay-be-ay seyrini gösterir — "ne kadar biriktiriyorum" sorusunun zaman içindeki cevabı.
 * Kaynak backend `monthly-series` (aylık özetle aynı hesap). Gelirsiz ay için oran
 * "—"dir; ortalama yalnız dolu aylardan.
 */
export default function AylikSeri({ months = 6 }) {
  const [data, setData] = useState(null);
  const [hata, setHata] = useState(null);

  useEffect(() => {
    let cancelled = false;
    reportsApi.monthlySeries({ months })
      .then((r) => { if (!cancelled) setData(r); })
      .catch((e) => { if (!cancelled) setHata(e.message); });
    return () => { cancelled = true; };
  }, [months]);

  if (hata) return <p className="text-xs text-zinc-500">Aylık seri yüklenemedi.</p>;
  if (!data) return <div role="status" aria-live="polite" aria-busy="true" className="card p-4 h-40 animate-pulse"><span className="sr-only">Yükleniyor…</span></div>;

  const seri = data.series.map((s) => ({ ...s, ad: s.label.split(' ')[0].slice(0, 3) }));
  const hepsiBos = seri.every((s) => !s.total_income && !s.total_expense);

  return (
    <div className="card p-4" data-testid="aylik-seri">
      <div className="flex items-baseline justify-between gap-2 mb-2">
        <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">Son {data.months} ay</h3>
        <span className="text-xs text-zinc-500">
          Ort. tasarruf oranı: <span className="font-numeric font-semibold text-zinc-700 dark:text-zinc-200">
            {data.avg_savings_rate === null ? '—' : `%${String(data.avg_savings_rate).replace('.', ',')}`}
          </span>
        </span>
      </div>
      {hepsiBos ? (
        <p className="text-xs text-zinc-500">Bu dönemde işlem yok.</p>
      ) : (
        <div style={{ width: '100%', height: 180 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={seri} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <XAxis dataKey="ad" tick={{ fontSize: 11 }} />
              <YAxis hide />
              <Tooltip formatter={(v, ad) => [`${formatSayi(v)} ${paraEtiketi()}`, ad === 'total_income' ? 'Gelir' : 'Gider']} />
              <Legend formatter={(v) => (v === 'total_income' ? 'Gelir' : 'Gider')} />
              <ReferenceLine y={0} stroke="#a1a1aa" />
              <Bar dataKey="total_income" fill="#16a34a" radius={[3, 3, 0, 0]} />
              <Bar dataKey="total_expense" fill="#dc2626" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      <ul className="mt-2 grid grid-cols-3 sm:grid-cols-6 gap-1 text-[11px] text-zinc-500">
        {seri.map((s) => (
          <li key={`${s.year}-${s.month}`} className="text-center">
            <span className="block">{s.ad}</span>
            <span className={`font-numeric ${s.savings_rate === null ? '' : s.savings_rate >= 0 ? 'text-positive-600 dark:text-positive-400' : 'text-negative-600 dark:text-negative-400'}`}>
              {s.savings_rate === null ? '—' : `%${String(s.savings_rate).replace('.', ',')}`}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
