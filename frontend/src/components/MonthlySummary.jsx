import { useState, useEffect } from 'react';
import { CalendarRange, TrendingUp, TrendingDown } from 'lucide-react';
import { reportsApi } from '../api.js';
import { formatPara, formatSayi } from '../lib/money.js';

/**
 * MonthlySummary — A3 aylık özet kartı (kurucu "durum raporu" görünür hali).
 * İçinde bulunulan ay: gelir / gider / net değişim + önceki aya trend + en çok harcanan kategori.
 * Sessiz fail (flowSummary deseni): veri gelmezse hiç render etmez.
 */
export default function MonthlySummary() {
  const [data, setData] = useState(null);

  useEffect(() => {
    let cancelled = false;
    reportsApi.monthlySummary()
      .then(r => { if (!cancelled) setData(r); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  if (!data) return null;
  const { period, current, trend } = data;
  const hasData = current.transaction_count > 0;

  // Gider artışı KÖTÜ (kırmızı ok yukarı), gelir artışı İYİ.
  const expTrend = trend.expense_delta_pct;
  const incTrend = trend.income_delta_pct;
  const topCat = current.expense_categories?.[0];

  return (
    <div className="card p-4">
      <div className="flex items-center gap-2 mb-3">
        <CalendarRange className="w-4 h-4 text-brand-600 dark:text-brand-400" />
        <h3 className="font-semibold text-sm">Bu Ay — {period.label}</h3>
      </div>

      {!hasData ? (
        <p className="text-xs text-zinc-500 dark:text-zinc-400">Bu ay henüz işlem yok.</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <p className="text-[11px] text-zinc-500 dark:text-zinc-400">Gelir</p>
              <p className="font-numeric text-base sm:text-lg font-bold text-positive-600 dark:text-positive-400">
                {formatSayi(current.total_income)}
              </p>
              {incTrend !== null && (
                <p className={`text-[11px] flex items-center gap-0.5 ${incTrend >= 0 ? 'text-positive-600 dark:text-positive-400' : 'text-zinc-500'}`}>
                  {incTrend >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                  %{Math.abs(incTrend).toFixed(0)}
                </p>
              )}
            </div>
            <div>
              <p className="text-[11px] text-zinc-500 dark:text-zinc-400">Gider</p>
              <p className="font-numeric text-base sm:text-lg font-bold text-negative-600 dark:text-negative-400">
                {formatSayi(current.total_expense)}
              </p>
              {expTrend !== null && (
                <p className={`text-[11px] flex items-center gap-0.5 ${expTrend > 0 ? 'text-negative-600 dark:text-negative-400' : 'text-positive-600 dark:text-positive-400'}`}>
                  {expTrend > 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                  %{Math.abs(expTrend).toFixed(0)}
                </p>
              )}
            </div>
            <div>
              <p className="text-[11px] text-zinc-500 dark:text-zinc-400">Net</p>
              <p className={`font-numeric text-base sm:text-lg font-bold ${current.net_change >= 0 ? 'text-positive-700 dark:text-positive-400' : 'text-negative-700 dark:text-negative-400'}`}>
                {current.net_change >= 0 ? '+' : ''}{formatSayi(current.net_change)}
              </p>
              {current.savings_rate !== null && (
                <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
                  tasarruf %{current.savings_rate.toFixed(0)}
                </p>
              )}
            </div>
          </div>

          {topCat && (
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-3 pt-2 border-t border-zinc-100 dark:border-zinc-800">
              En çok: <span className="font-medium text-zinc-700 dark:text-zinc-300">{topCat.category}</span>{' '}
              {formatPara(topCat.total)} (%{topCat.percentage.toFixed(0)})
              {trend.prev_net_change !== undefined && (
                <span className="ml-1">· geçen ay net {trend.prev_net_change >= 0 ? '+' : ''}{formatPara(trend.prev_net_change)}</span>
              )}
            </p>
          )}
        </>
      )}
    </div>
  );
}