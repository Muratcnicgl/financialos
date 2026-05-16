import { useState, useEffect } from 'react';
import { RefreshCw, Loader2 } from 'lucide-react';
import { cashflowApi } from '../api.js';
import { useToast } from '../components/Toast.jsx';
import BalanceTrend from '../components/BalanceTrend.jsx';
import CashflowCalendar from '../components/CashflowCalendar.jsx';
import CashflowSankey from '../components/CashflowSankey.jsx';
import CashflowSummary from '../components/CashflowSummary.jsx';

const HORIZON_OPTIONS = [30, 60, 90];

const FILTER_CHIPS = [
  { key: 'incomes',     label: 'Gelirler'  },
  { key: 'expenses',    label: 'Giderler'  },
  { key: 'receivables', label: 'Alacaklar' },
  { key: 'payables',    label: 'Borçlar'   },
];

export default function Cashflow() {
  const toast = useToast();
  const [horizon, setHorizon] = useState(60);
  const [include, setInclude] = useState(new Set(['incomes', 'expenses', 'receivables', 'payables']));
  const [crunchThreshold, setCrunchThreshold] = useState(0);
  const [thresholdInput, setThresholdInput] = useState('0');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const includeKey = [...include].sort().join(',');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    cashflowApi.getForecast({
      days: horizon,
      include: [...include],
      crunchThreshold,
    }).then(result => {
      if (!cancelled) setData(result);
    }).catch(e => {
      if (!cancelled) toast.error('Nakit akışı yüklenemedi', { detail: e.message });
    }).finally(() => {
      if (!cancelled) { setLoading(false); setRefreshing(false); }
    });

    return () => { cancelled = true; };
  }, [horizon, includeKey, crunchThreshold]);  // eslint-disable-line react-hooks/exhaustive-deps

  const handleRefresh = () => {
    setRefreshing(true);
    // includeKey/horizon bağımlılıkları değişmediğinde effect tetiklenmez, zorla yenile
    cashflowApi.getForecast({ days: horizon, include: [...include], crunchThreshold })
      .then(r => setData(r))
      .catch(e => toast.error('Yenileme hatası', { detail: e.message }))
      .finally(() => setRefreshing(false));
  };

  const toggleFilter = (key) => {
    setInclude(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const applyThreshold = () => {
    const val = parseFloat(thresholdInput.replace(',', '.')) || 0;
    setCrunchThreshold(val);
  };

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Başlık + kontroller */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="flex-1 min-w-0">
          <h2 className="text-lg font-bold">Nakit Akışı Tahmini</h2>
          {data && (
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
              {data.start_date} → {data.end_date} · {data.days.length} gün
            </p>
          )}
        </div>

        <div className="flex items-center gap-2 flex-shrink-0 flex-wrap">
          {/* Horizon toggle */}
          <div className="flex rounded-lg border border-zinc-200 dark:border-zinc-700 overflow-hidden">
            {HORIZON_OPTIONS.map(d => (
              <button
                key={d}
                onClick={() => setHorizon(d)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  horizon === d
                    ? 'bg-brand-500 text-white'
                    : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                }`}
              >
                {d}g
              </button>
            ))}
          </div>

          {/* Yenile */}
          <button onClick={handleRefresh} disabled={loading || refreshing} className="btn btn-secondary !text-xs">
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Yenile</span>
          </button>
        </div>
      </div>

      {/* Filtre chipsleri */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs text-zinc-500 dark:text-zinc-400 flex-shrink-0">Göster:</span>
        {FILTER_CHIPS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => toggleFilter(key)}
            className={`chip transition-colors ${
              include.has(key)
                ? 'chip-positive'
                : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-400 dark:text-zinc-500'
            }`}
          >
            {label}
          </button>
        ))}

        {/* Crunch eşiği */}
        <div className="flex items-center gap-1 ml-auto">
          <span className="text-xs text-zinc-500 dark:text-zinc-400">Eşik:</span>
          <input
            type="text"
            inputMode="numeric"
            value={thresholdInput}
            onChange={e => setThresholdInput(e.target.value)}
            onBlur={applyThreshold}
            onKeyDown={e => e.key === 'Enter' && applyThreshold()}
            className="w-20 px-2 py-1 text-xs font-numeric rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-700 dark:text-zinc-300 text-right"
            placeholder="0"
            title="Sıkışma eşiği (TL)"
          />
          <span className="text-xs text-zinc-400">TL</span>
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-16 gap-2 text-zinc-500 dark:text-zinc-400">
          <Loader2 className="w-5 h-5 animate-spin" />
          <span className="text-sm">Tahmin hesaplanıyor…</span>
        </div>
      )}

      {/* İçerik */}
      {!loading && data && (
        <>
          {/* Özet metrik kartları */}
          <CashflowSummary summary={data.summary} />

          {/* Bakiye trend grafiği */}
          <BalanceTrend days={data.days} today={data.start_date} />

          {/* Alt satır: Takvim + Sankey */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <CashflowCalendar days={data.days} />
            <CashflowSankey sankey={data.sankey} />
          </div>
        </>
      )}
    </div>
  );
}
