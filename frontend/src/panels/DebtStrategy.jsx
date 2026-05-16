import { useState, useEffect, useMemo } from 'react';
import { RefreshCw, Loader2, TrendingDown, Mountain, CreditCard, Info } from 'lucide-react';
import { debtStrategyApi } from '../api.js';
import { useToast } from '../components/Toast.jsx';

const TL = (n) =>
  new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY', maximumFractionDigits: 0 }).format(n || 0);

const fmtDate = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('tr-TR', { year: 'numeric', month: 'long' });
  } catch {
    return iso;
  }
};

function StrategyCard({ title, subtitle, icon: Icon, accent, strategy, debtsById }) {
  if (!strategy) {
    return (
      <div className="rounded-lg border border-zinc-700 bg-zinc-800/40 p-5">
        <div className="text-zinc-400 text-sm">Veri yok.</div>
      </div>
    );
  }

  const accentMap = {
    warn:     { border: 'border-warn-600/50',     bg: 'bg-warn-950/30',     text: 'text-warn-300',     badge: 'bg-warn-600/20 text-warn-300'     },
    positive: { border: 'border-positive-600/50', bg: 'bg-positive-950/30', text: 'text-positive-300', badge: 'bg-positive-600/20 text-positive-300' },
  };
  const c = accentMap[accent] || accentMap.warn;

  return (
    <div className={`rounded-lg border ${c.border} ${c.bg} p-5 flex flex-col gap-4`}>
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-md ${c.badge}`}>
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <h3 className={`text-lg font-semibold ${c.text}`}>{title}</h3>
          <p className="text-xs text-zinc-400">{subtitle}</p>
        </div>
      </div>

      <div>
        <div className="text-xs text-zinc-400 mb-2 uppercase tracking-wide">Ödeme Sırası</div>
        <ol className="space-y-1">
          {strategy.order.map((accountId, i) => {
            const debt = debtsById[accountId];
            return (
              <li key={accountId} className="flex items-center gap-2 text-sm">
                <span className={`w-6 h-6 rounded-full ${c.badge} flex items-center justify-center text-xs font-semibold flex-shrink-0`}>
                  {i + 1}
                </span>
                <span className="text-zinc-200">{debt?.name || `Hesap #${accountId}`}</span>
                {debt && (
                  <span className="text-xs text-zinc-500 ml-auto whitespace-nowrap">
                    {TL(debt.balance)} · %{debt.interest_rate_monthly.toFixed(2)}/ay
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      </div>

      <div className="grid grid-cols-3 gap-3 pt-3 border-t border-zinc-700/50">
        <div>
          <div className="text-xs text-zinc-400">Toplam Faiz</div>
          <div className={`text-base font-semibold ${c.text}`}>{TL(strategy.total_interest_paid)}</div>
        </div>
        <div>
          <div className="text-xs text-zinc-400">Süre</div>
          <div className="text-base font-semibold text-zinc-100">{strategy.months_to_freedom} ay</div>
        </div>
        <div>
          <div className="text-xs text-zinc-400">Bitiş</div>
          <div className="text-base font-semibold text-zinc-100 text-sm">{fmtDate(strategy.payoff_date)}</div>
        </div>
      </div>
    </div>
  );
}

export default function DebtStrategy() {
  const toast = useToast();
  const [extraMonthly, setExtraMonthly] = useState(0);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchData = async (extra) => {
    try {
      const isInitial = data === null;
      isInitial ? setLoading(true) : setRefreshing(true);
      const res = await debtStrategyApi.compare({ extraMonthly: extra });
      setData(res);
    } catch (e) {
      toast.error(`Borç stratejisi yüklenemedi: ${e.message}`);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => { fetchData(0); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const debtsById = useMemo(() => {
    if (!data?.debts) return {};
    return Object.fromEntries(data.debts.map((d) => [d.account_id, d]));
  }, [data]);

  const handleExtraCommit = () => fetchData(extraMonthly);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-zinc-400">
        <Loader2 className="w-6 h-6 animate-spin mr-2" /> Yükleniyor…
      </div>
    );
  }

  if (!data || !data.debts || data.debts.length === 0) {
    return (
      <div className="card p-8 text-center">
        <CreditCard className="w-10 h-10 mx-auto text-zinc-500 mb-3" />
        <h3 className="text-lg text-zinc-200 mb-1">Aktif borç yok</h3>
        <p className="text-sm text-zinc-400">Strateji karşılaştırması için en az bir borç hesabı gerekli.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <CreditCard className="w-6 h-6 text-brand-400" />
            Borç Stratejisi
          </h2>
          <p className="text-sm text-zinc-400 mt-1">
            Snowball ve Avalanche stratejilerini karşılaştır. {data.debts.length} aktif borç.
          </p>
        </div>
        <button
          onClick={handleExtraCommit}
          disabled={refreshing}
          className="btn btn-secondary !text-xs"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          Yenile
        </button>
      </div>

      {/* Ekstra ödeme slider */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-2">
          <label className="text-sm text-zinc-300 font-medium">
            Opsiyonel ekstra aylık ödeme
          </label>
          <span className="text-base font-semibold font-numeric text-brand-400">{TL(extraMonthly)}</span>
        </div>
        <input
          type="range"
          min="0"
          max="5000"
          step="100"
          value={extraMonthly}
          onChange={(e) => setExtraMonthly(Number(e.target.value))}
          onMouseUp={handleExtraCommit}
          onTouchEnd={handleExtraCommit}
          className="w-full accent-brand-500"
        />
        <div className="flex justify-between text-xs text-zinc-500 mt-1">
          <span>0 TL</span>
          <span>5.000 TL</span>
        </div>
      </div>

      {/* Strateji kartları */}
      <div className="grid md:grid-cols-2 gap-5">
        <StrategyCard
          title="Snowball (Kartopu)"
          subtitle="Küçük bakiyeden başla — psikolojik motivasyon"
          icon={TrendingDown}
          accent="warn"
          strategy={data.snowball}
          debtsById={debtsById}
        />
        <StrategyCard
          title="Avalanche (Çığ)"
          subtitle="Yüksek faizden başla — matematiksel optimum"
          icon={Mountain}
          accent="positive"
          strategy={data.avalanche}
          debtsById={debtsById}
        />
      </div>

      {/* Karşılaştırma */}
      {data.comparison && (
        <div className="card p-5 border-brand-700/50 bg-brand-950/20">
          <div className="flex items-start gap-3">
            <div className="p-2 rounded-md bg-brand-600/20 flex-shrink-0">
              <Info className="w-5 h-5 text-brand-300" />
            </div>
            <div className="flex-1 space-y-2">
              <h3 className="text-base font-semibold text-brand-200">Karşılaştırma</h3>
              <p className="text-sm text-zinc-300">{data.comparison.recommendation_note}</p>
              <div className="flex flex-wrap gap-6 text-sm pt-2">
                <div>
                  <span className="text-zinc-400">Avalanche ile faiz tasarrufu: </span>
                  <span className="font-semibold font-numeric text-positive-300">{TL(data.comparison.interest_saved_with_avalanche)}</span>
                </div>
                {data.comparison.months_difference !== 0 && (
                  <div>
                    <span className="text-zinc-400">Süre farkı: </span>
                    <span className="font-semibold font-numeric text-zinc-100">{Math.abs(data.comparison.months_difference)} ay</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
