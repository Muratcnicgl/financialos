import { useState, useEffect } from 'react';
import {
  BarChart3, AlertTriangle, TrendingUp,
  CalendarDays, ArrowDownLeft, ArrowUpRight, Building2, Receipt,
} from 'lucide-react';
import {
  PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, LabelList,
  LineChart, Line, CartesianGrid, ReferenceLine,
} from 'recharts';
import { reportsApi } from '../api.js';
import NetWorthAnalysis from '../components/NetWorthAnalysis.jsx';
import { Skeleton } from '../components/Skeleton.jsx';
import EmptyState from '../components/EmptyState.jsx';
import { formatPara } from '../lib/money.js';

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
      <p className="font-numeric">{formatPara(d.total)}</p>
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

  // B2: Net Değer Trend
  const TREND_RANGES = [
    { days: 30,  label: "1 Ay"  },
    { days: 90,  label: "3 Ay"  },
    { days: 180, label: "6 Ay"  },
    { days: 365, label: "1 Yil" },
  ];
  const [trendDays, setTrendDays] = useState(30);
  const [trendData, setTrendData] = useState(null);
  const [loadingTrend, setLoadingTrend] = useState(true);
  const [errorTrend, setErrorTrend] = useState(null);

  useEffect(() => {
    let active = true;
    setLoadingTrend(true);
    setErrorTrend(null);
    reportsApi.netWorthTrend(trendDays)
      .then((res) => { if (active) { setTrendData(res); setLoadingTrend(false); } })
      .catch((e) => { if (active) { setErrorTrend(e.message); setLoadingTrend(false); } });
    return () => { active = false; };
  }, [trendDays]);

  const trendItems = trendData?.items || [];

  // B3: Alacak-Borç Takvimi
  const [cashflowDays, setCashflowDays] = useState(30);
  const [cashflowData, setCashflowData] = useState(null);
  const [loadingCashflow, setLoadingCashflow] = useState(true);
  const [errorCashflow, setErrorCashflow] = useState(null);

  useEffect(() => {
    let active = true;
    setLoadingCashflow(true);
    setErrorCashflow(null);
    reportsApi.upcomingCashflow(cashflowDays)
      .then((res) => { if (active) { setCashflowData(res); setLoadingCashflow(false); } })
      .catch((e) => { if (active) { setErrorCashflow(e.message); setLoadingCashflow(false); } });
    return () => { active = false; };
  }, [cashflowDays]);

  const cashflowItems = cashflowData?.items || [];

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
            <button type="button" key={d} onClick={() => setDays(d)}
              className={`btn !text-xs !px-3 ${days === d ? 'btn-primary' : 'btn-secondary'}`}>
              {d} gün
            </button>
          ))}
          {Object.entries(TYPE_META).map(([k, meta]) => (
            <button type="button" key={k} onClick={() => setType(k)}
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
              {formatPara(grandTotal)}
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

      {/* ===== B2: NET DEĞER TRENDİ ===== */}
      <div className="space-y-3 pt-2">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-base font-semibold">Net Değer Trendi</h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Görülen (alacaksız) · Tam (alacaklı)
            </p>
          </div>
          <div className="flex gap-2 flex-wrap">
            {TREND_RANGES.map(r => (
              <button type="button" key={r.days} onClick={() => setTrendDays(r.days)}
                className={`btn !text-xs !px-3 ${trendDays === r.days ? 'btn-primary' : 'btn-secondary'}`}>
                {r.label}
              </button>
            ))}
          </div>
        </div>

        {loadingTrend ? (
          <div className="card p-4 space-y-3">
            <Skeleton className="h-4 w-36" />
            <Skeleton className="h-64 w-full" />
          </div>
        ) : errorTrend ? (
          <div className="card p-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-negative-600 flex-shrink-0" />
              <p className="text-sm text-negative-700 dark:text-negative-300">{errorTrend}</p>
            </div>
          </div>
        ) : trendItems.length === 0 ? (
          <EmptyState
            icon={TrendingUp}
            title="Net değer geçmişi henüz yok"
            description="Cockpit'e her girişte bugünkü değer kaydedilir. Geçmiş veri için: python -m scripts.backfill_net_worth"
          />
        ) : (
          <div className="card p-4">
            <div style={{ width: '100%', height: 320 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={trendItems}
                  margin={{ top: 8, right: 16, left: 8, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e4e4e7" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={fmtXDate}
                    tick={{ fontSize: 11, fill: TICK_COLOR }}
                  />
                  <YAxis
                    tickFormatter={fmtYAxis}
                    tick={{ fontSize: 11, fill: TICK_COLOR }}
                    width={52}
                  />
                  <Tooltip content={<TrendTooltip />} />
                  <Legend />
                  <ReferenceLine y={0} stroke="#71717a" strokeDasharray="4 2" />
                  <Line
                    type="monotone"
                    dataKey="net_worth_seen"
                    name="Görülen"
                    stroke="#4f46e5"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="net_worth_full"
                    name="Tam"
                    stroke="#16a34a"
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 4 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="investment_value"
                    name="Yatirim Degeri"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={false}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>

      {/* FEAT-021/024: net değer analizi (ayrıştırma + reel) */}
      <NetWorthAnalysis />

      {/* ===== B3: ALACAK-BORÇ TAKVİMİ ===== */}
      <div className="space-y-3 pt-2">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h2 className="text-base font-semibold">Alacak-Borç Takvimi</h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Gelecek {cashflowDays} günde net akış
            </p>
          </div>
          <div className="flex gap-2">
            {[30, 60].map(d => (
              <button type="button" key={d} onClick={() => setCashflowDays(d)}
                className={`btn !text-xs !px-3 ${cashflowDays === d ? 'btn-primary' : 'btn-secondary'}`}>
                {d} gün
              </button>
            ))}
          </div>
        </div>

        {loadingCashflow ? (
          <div className="space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="card p-4 space-y-2">
                  <Skeleton className="h-3 w-28" />
                  <Skeleton className="h-7 w-32" />
                </div>
              ))}
            </div>
            <div className="card p-4 space-y-2">
              <Skeleton className="h-12 w-full" />
              {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}
            </div>
          </div>
        ) : errorCashflow ? (
          <div className="card p-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-negative-600 flex-shrink-0" />
              <p className="text-sm text-negative-700 dark:text-negative-300">{errorCashflow}</p>
            </div>
          </div>
        ) : cashflowItems.length === 0 ? (
          <EmptyState
            icon={CalendarDays}
            title="Yaklaşan kalem yok"
            description={`Sonraki ${cashflowDays} günde vadesi gelen borç veya alacak bulunmuyor.`}
          />
        ) : (
          <>
            {/* Özet kartları */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="card p-4">
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-1">Bekleyen tahsilat</p>
                <p className="font-numeric text-lg font-bold text-positive-600 dark:text-positive-400">
                  +{formatPara(cashflowData.summary.total_receivable)}
                </p>
              </div>
              <div className="card p-4">
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-1">Bekleyen ödeme</p>
                <p className="font-numeric text-lg font-bold text-negative-600 dark:text-negative-400">
                  {formatPara(cashflowData.summary.total_payable)}
                </p>
              </div>
              <div className="card p-4">
                <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-1">Net beklenen akış</p>
                <p className={`font-numeric text-lg font-bold ${
                  cashflowData.summary.net_flow >= 0
                    ? 'text-positive-600 dark:text-positive-400'
                    : 'text-negative-600 dark:text-negative-400'
                }`}>
                  {cashflowData.summary.net_flow >= 0 ? '+' : ''}{formatPara(cashflowData.summary.net_flow)}
                </p>
              </div>
            </div>

            {/* Timeline */}
            <div className="card px-4 py-3">
              <p className="text-xs text-zinc-400 mb-2">Zaman çizelgesi · bugün → +{cashflowDays} gün</p>
              <CashflowTimeline items={cashflowItems} days={cashflowDays} today={cashflowData.today} />
            </div>

            {/* Tarih gruplu liste */}
            <div className="card divide-y divide-zinc-100 dark:divide-zinc-800">
              {Object.entries(groupByDate(cashflowItems)).map(([dateStr, dayItems]) => {
                const dayNet = dayItems.reduce((s, i) => s + i.amount, 0);
                return (
                  <div key={dateStr} className="p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
                        {formatLongDate(dateStr)}
                      </span>
                      <span className="chip chip-neutral text-[10px]">{relativeDate(dateStr)}</span>
                    </div>
                    <div className="space-y-2">
                      {dayItems.map((item, i) => (
                        <div key={i} className="flex items-center gap-3">
                          {cfIcon(item)}
                          <p className="flex-1 text-sm text-zinc-800 dark:text-zinc-200 min-w-0 truncate">
                            {item.label}
                          </p>
                          <p className={`font-numeric text-sm font-semibold flex-shrink-0 ${
                            item.amount >= 0
                              ? 'text-positive-600 dark:text-positive-400'
                              : 'text-negative-600 dark:text-negative-400'
                          }`}>
                            {item.amount >= 0 ? '+' : ''}{formatPara(Math.abs(item.amount))}
                          </p>
                        </div>
                      ))}
                    </div>
                    {dayItems.length > 1 && (
                      <p className={`text-right text-xs font-numeric mt-1.5 ${
                        dayNet >= 0 ? 'text-positive-600' : 'text-negative-600'
                      }`}>
                        Net: {dayNet >= 0 ? '+' : ''}{formatPara(Math.abs(dayNet))}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ============================================================
// TREND YARDIMCILARI
// ============================================================

const TR_MONTHS_SHORT = ['Oca','Şub','Mar','Nis','May','Haz','Tem','Ağu','Eyl','Eki','Kas','Ara'];

function fmtXDate(iso) {
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return iso;
  return `${parseInt(m[3])} ${TR_MONTHS_SHORT[parseInt(m[2]) - 1]}`;
}

function fmtYAxis(v) {
  if (Math.abs(v) >= 1000) return (v / 1000).toFixed(0) + 'K';
  return String(v);
}

function TrendTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="card px-3 py-2 text-xs shadow-lg border">
      <p className="font-semibold mb-1">{fmtXDate(label)}</p>
      {payload.map(p => (
        <p key={p.dataKey} style={{ color: p.stroke }} className="font-numeric">
          {p.name}: {formatPara(p.value)}
        </p>
      ))}
    </div>
  );
}

// ============================================================
// CASHFLOW YARDIMCILARI
// ============================================================

const TR_MONTHS_LONG = ['Ocak','Şubat','Mart','Nisan','Mayıs','Haziran',
                        'Temmuz','Ağustos','Eylül','Ekim','Kasım','Aralık'];
const TR_WEEKDAYS = ['Pazar','Pazartesi','Salı','Çarşamba','Perşembe','Cuma','Cumartesi'];

function relativeDate(dateStr) {
  const t = new Date(); t.setHours(0, 0, 0, 0);
  const d = new Date(dateStr + 'T00:00:00');
  const diff = Math.round((d - t) / 86400000);
  if (diff === 0) return 'bugün';
  if (diff === 1) return 'yarın';
  if (diff === -1) return 'dün';
  if (diff > 0) return `${diff} gün sonra`;
  return `${-diff} gün önce`;
}

function formatLongDate(dateStr) {
  const m = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!m) return dateStr;
  const d = new Date(dateStr + 'T00:00:00');
  return `${parseInt(m[3])} ${TR_MONTHS_LONG[parseInt(m[2]) - 1]} ${TR_WEEKDAYS[d.getDay()]}`;
}

function groupByDate(items) {
  return items.reduce((acc, item) => {
    if (!acc[item.date]) acc[item.date] = [];
    acc[item.date].push(item);
    return acc;
  }, {});
}

function cfIcon(item) {
  const cls = 'w-4 h-4 flex-shrink-0';
  if (item.type === 'receivable') {
    if (item.source === 'income') return <TrendingUp className={`${cls} text-positive-600`} />;
    return <ArrowDownLeft className={`${cls} text-positive-600`} />;
  }
  if (item.source === 'loan') return <Building2 className={`${cls} text-negative-600`} />;
  if (item.source === 'personal_debt') return <ArrowUpRight className={`${cls} text-negative-600`} />;
  return <Receipt className={`${cls} text-negative-600`} />;
}

function CashflowTimeline({ items, days, today: todayStr }) {
  const todayMs = new Date(todayStr + 'T00:00:00').getTime();
  const horizonMs = todayMs + days * 86400000;
  const totalMs = horizonMs - todayMs;

  return (
    <div className="relative h-12">
      <div className="absolute top-1/2 left-0 right-0 h-px bg-zinc-200 dark:bg-zinc-700" />
      <div className="absolute top-0 bottom-0 left-0 w-0.5 bg-brand-400 opacity-70" title="Bugün" />
      {items.map((item, i) => {
        const itemMs = new Date(item.date + 'T00:00:00').getTime();
        const pct = Math.max(0.5, Math.min(99, ((itemMs - todayMs) / totalMs) * 100));
        const r = Math.min(14, Math.max(6, Math.abs(item.amount) / 600));
        return (
          <div
            key={i}
            title={`${fmtXDate(item.date)}: ${item.label} — ${item.amount >= 0 ? '+' : ''}${formatPara(item.amount)}`}
            className="absolute top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white dark:border-zinc-900 hover:scale-125 transition-transform cursor-default"
            style={{
              left: `${pct}%`,
              width: r * 2,
              height: r * 2,
              backgroundColor: item.type === 'receivable' ? '#16a34a' : '#e11d48',
            }}
          />
        );
      })}
    </div>
  );
}