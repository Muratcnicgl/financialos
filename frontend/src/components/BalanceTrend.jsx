import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ReferenceDot, ResponsiveContainer,
} from 'recharts';
import { formatDate } from '../api.js';
import { formatPara, formatSayi } from '../lib/money.js';

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="card p-3 text-xs shadow-lg border border-zinc-200 dark:border-zinc-700">
      <p className="font-semibold mb-1 text-zinc-700 dark:text-zinc-300">
        {formatDate(d.date, { withYear: true })}
      </p>
      <p className={`font-numeric font-bold ${d.balance >= 0 ? 'text-positive-600 dark:text-positive-400' : 'text-negative-600 dark:text-negative-400'}`}>
        {formatPara(d.balance)}
      </p>
      {d.inflows > 0 && (
        <p className="text-positive-600 dark:text-positive-400 mt-0.5">
          +{formatPara(d.inflows)} giriş
        </p>
      )}
      {d.outflows < 0 && (
        <p className="text-negative-600 dark:text-negative-400 mt-0.5">
          {formatPara(d.outflows)} çıkış
        </p>
      )}
      {d.crunch && (
        <p className="text-negative-600 dark:text-negative-400 font-semibold mt-1">⚠ Sıkışma</p>
      )}
    </div>
  );
}

export default function BalanceTrend({ days, today }) {
  const chartData = days.map(d => ({
    date: d.date,
    balance: d.closing_balance,
    inflows: d.inflows,
    outflows: d.outflows,
    crunch: d.crunch,
  }));

  const crunchDays = chartData.filter(d => d.crunch);

  // X ekseni: sadece her 7. günü etiketle
  const xTicks = chartData
    .filter((_, i) => i % 7 === 0)
    .map(d => d.date);

  return (
    <div className="card p-4">
      <h3 className="text-sm font-semibold mb-3 text-zinc-700 dark:text-zinc-300">
        Bakiye Trendi
      </h3>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="currentColor" strokeOpacity={0.1} />
          <XAxis
            dataKey="date"
            ticks={xTicks}
            tickFormatter={v => formatDate(v)}
            tick={{ fontSize: 10, fill: 'currentColor', opacity: 0.6 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tickFormatter={v => formatSayi(v, { compact: true })}
            tick={{ fontSize: 10, fill: 'currentColor', opacity: 0.6 }}
            axisLine={false}
            tickLine={false}
            width={55}
          />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine
            x={today}
            stroke="#94a3b8"
            strokeDasharray="4 4"
            strokeWidth={1.5}
          />
          <ReferenceLine y={0} stroke="#ef4444" strokeOpacity={0.3} strokeWidth={1} />
          <Line
            type="monotone"
            dataKey="balance"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4, fill: '#3b82f6' }}
          />
          {crunchDays.map((d, i) => (
            <ReferenceDot
              key={i}
              x={d.date}
              y={d.balance}
              r={5}
              fill="#ef4444"
              stroke="#fff"
              strokeWidth={1.5}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
      {crunchDays.length > 0 && (
        <p className="text-xs text-negative-600 dark:text-negative-400 mt-2 flex items-center gap-1">
          <span className="inline-block w-2.5 h-2.5 rounded-full bg-negative-500 flex-shrink-0" />
          {crunchDays.length} gün bakiye eşiğin altında
        </p>
      )}
    </div>
  );
}