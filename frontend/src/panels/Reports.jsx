import { useState, useEffect } from 'react';
import { BarChart3, AlertTriangle } from 'lucide-react';
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, LabelList,
} from 'recharts';
import { reportsApi, formatTL } from '../api.js';
import { Skeleton } from '../components/Skeleton.jsx';
import EmptyState from '../components/EmptyState.jsx';

const COLORS = [
  '#4f46e5', '#16a34a', '#ea580c', '#0891b2',
  '#9333ea', '#ca8a04', '#e11d48', '#0d9488',
  '#7c3aed', '#db2777',
];

const TICK_COLOR = '#71717a'; // zinc-500, hem light hem dark'ta okunabilir

const TYPE_META = {
  expense: { label: 'Gider',  btnClass: 'btn-negative' },
  income:  { label: 'Gelir',  btnClass: 'btn-positive' },
  both:    { label: 'Tümü',   btnClass: 'btn-primary'  },
};

// Çubuk etiketleri için kısa format: 12300 → "12,3K"
function shortTL(value) {
  if (value >= 1000) return (value / 1000).toFixed(1).replace('.', ',') + 'K';
  return value.toFixed(0);
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="card px-3 py-2 text-xs shadow-lg border">
      <p className="font-semibold mb-0.5">{d.category}</p>
      <p className="font-numeric">{formatTL(d.total)} TL</p>
      <p className="text-zinc-500">%{d.percentage.toFixed(1)} · {d.count} işlem</p>
    </div>
  );
}

function ReportsSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div className="card p-4 space-y-4">
        <Skeleton className="h-4 w-24" />
        <div className="flex items-center justify-center py-4">
          <Skeleton className="w-48 h-48 rounded-full" />
        </div>
        <div className="space-y-1.5">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="flex items-center gap-2">
              <Skeleton className="w-3 h-3 rounded-full flex-shrink-0" />
              <Skeleton className="h-3 flex-1" />
            </div>
          ))}
        </div>
      </div>
      <div className="card p-4 space-y-3">
        <Skeleton className="h-4 w-24" />
        {[...Array(6)].map((_, i) => (
          <div key={i} className="flex gap-2 items-center">
            <Skeleton className="h-3 w-20 flex-shrink-0" />
            <Skeleton className="h-5 flex-1" />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Reports() {
  const [days, setDays] = useState(30);
  const [type, setType] = useState('expense');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    reportsApi.categoryBreakdown(days, type)
      .then((res) => { if (active) { setData(res); setLoading(false); } })
      .catch((e) => { if (active) { setError(e.message); setLoading(false); } });
    return () => { active = false; };
  }, [days, type]);

  const items = data?.items || [];
  const grandTotal = data?.grand_total || 0;
  const barHeight = Math.max(220, items.length * 38 + 48);

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Başlık + toggle */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-lg sm:text-xl font-bold mb-1">Raporlar</h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">Kategori dağılımı</p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          {[30, 90].map(d => (
            <button key={d} onClick={() => setDays(d)}
              className={`btn !text-xs !px-3 ${days === d ? 'btn-primary' : 'btn-secondary'}`}>
              {d} gün
            </button>
          ))}
          {Object.entries(TYPE_META).map(([k, meta]) => (
            <button key={k} onClick={() => setType(k)}
              className={`btn !text-xs !px-3 ${type === k ? meta.btnClass : 'btn-secondary'}`}>
              {meta.label}
            </button>
          ))}
        </div>
      </div>

      {/* Özet bant */}
      {!loading && !error && data && items.length > 0 && (
        <div className="card p-4">
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            <span className="font-semibold text-zinc-900 dark:text-zinc-100">
              Toplam {TYPE_META[type].label}:
            </span>{' '}
            <span className="font-numeric font-bold text-lg">
              {formatTL(grandTotal)} TL
            </span>
            <span className="text-zinc-500 ml-2">
              · {items.length} kategori · son {days} gün
            </span>
          </p>
        </div>
      )}

      {/* İçerik */}
      {loading ? (
        <ReportsSkeleton />
      ) : error ? (
        <div className="card p-6 border-negative-300 dark:border-negative-700 bg-negative-50 dark:bg-negative-950/30">
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-negative-600 dark:text-negative-400 flex-shrink-0" />
            <p className="text-sm text-negative-700 dark:text-negative-300">{error}</p>
          </div>
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={BarChart3}
          title="Bu dönemde işlem yok"
          description={`Son ${days} günde ${TYPE_META[type].label.toLowerCase()} kategorisi bulunamadı.`}
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Donut — wrapper div explicit height + height="100%" pattern */}
          <div className="card p-4">
            <h3 className="text-sm font-semibold mb-3 text-zinc-700 dark:text-zinc-300">Dağılım</h3>
            <div style={{ width: '100%', height: 280 }}>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={items}
                    cx="50%"
                    cy="45%"
                    innerRadius={65}
                    outerRadius={95}
                    dataKey="total"
                    nameKey="category"
                    paddingAngle={2}
                  >
                    {items.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                  <Legend iconType="circle" iconSize={8} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Yatay çubuk — wrapper div explicit height + height="100%" pattern */}
          <div className="card p-4">
            <h3 className="text-sm font-semibold mb-3 text-zinc-700 dark:text-zinc-300">Kategoriler</h3>
            <div style={{ width: '100%', height: barHeight }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  layout="vertical"
                  data={items}
                  margin={{ top: 0, right: 56, left: 0, bottom: 0 }}
                >
                  <XAxis type="number" hide />
                  <YAxis
                    type="category"
                    dataKey="category"
                    width={96}
                    tick={{ fontSize: 11, fill: TICK_COLOR }}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  <Bar dataKey="total" radius={[0, 4, 4, 0]}>
                    {items.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                    <LabelList
                      dataKey="total"
                      position="right"
                      formatter={shortTL}
                      style={{ fontSize: 11, fill: TICK_COLOR }}
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
