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
  // İlk dört kalem + kalanların toplamı. Uzun kuyruk ("%1 · %1 · %0,4") listeyi
  // şişirir ve hiçbir karar değiştirmez; tek satırda toplanır.
  const tumKategoriler = current.expense_categories || [];
  const kaymalar = data.kategori_kaymalari || [];
  const kategoriler = (() => {
    const ilk = tumKategoriler.slice(0, 4);
    const kalan = tumKategoriler.slice(4);
    if (!kalan.length) return ilk;
    return [...ilk, {
      category: `diğer (${kalan.length})`,
      total: kalan.reduce((t, k) => t + Number(k.total || 0), 0),
      percentage: kalan.reduce((t, k) => t + Number(k.percentage || 0), 0),
    }];
  })();

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

          {/* HARCAMA NEREYE GİTTİ — tek satır "en çok" yerine oranlı liste.
              Veri zaten elde (`current.expense_categories`, her kalemde `percentage`);
              ek istek YOK. Tek satır yalnız birinci kalemi söylüyordu ve ikinci kalemin
              birinciye yakın mı yoksa önemsiz mi olduğu görünmüyordu — oran çubuğu bunu
              tek bakışta verir. En çok DÖRT kalem çizilir; kalanlar "diğer" olarak tek
              satırda toplanır (uzun kuyruk listeyi şişirip hiçbir şey anlatmıyor). */}
          {kategoriler.length > 0 && (
            <div className="mt-3 pt-3 border-t border-zinc-100 dark:border-zinc-800 space-y-1.5">
              {kategoriler.map((k) => (
                <div key={k.category} className="flex items-center gap-2">
                  <span className="text-xs text-zinc-600 dark:text-zinc-300 w-32 shrink-0 truncate"
                        title={k.category}>{k.category}</span>
                  <span className="flex-1 h-1.5 rounded-full bg-zinc-100 dark:bg-zinc-800 overflow-hidden">
                    <span className="block h-full rounded-full bg-negative-400 dark:bg-negative-500"
                          style={{ width: `${Math.min(100, k.percentage)}%` }} />
                  </span>
                  <span className="font-numeric text-[11px] text-zinc-600 dark:text-zinc-400
                                   w-24 text-right shrink-0">
                    {formatPara(k.total)}
                  </span>
                  <span className="font-numeric text-[11px] text-zinc-500 w-9 text-right shrink-0">
                    %{k.percentage.toFixed(0)}
                  </span>
                </div>
              ))}
              {trend.prev_net_change !== undefined && (
                <p className="text-[11px] text-zinc-500 pt-1">
                  Geçen ay net {trend.prev_net_change >= 0 ? '+' : ''}{formatPara(trend.prev_net_change)}
                </p>
              )}
            </div>
          )}

          {/* FEAT-033 (BUG #430): "geçen aya göre" anlatısı + en çok kayan kategoriler.
              Sayılar backend'den; anlatı deterministik (model yok). Kayma yoksa satır yok. */}
          {data.anlati && (
            <p data-testid="ay-anlatisi" className="text-xs text-zinc-700 dark:text-zinc-300 mt-3 pt-3 border-t border-zinc-100 dark:border-zinc-800">
              {data.anlati}
            </p>
          )}
          {kaymalar.length > 0 && (
            <ul data-testid="kategori-kaymalari" className="mt-1.5 space-y-0.5">
              {kaymalar.map((k) => (
                <li key={k.category} className="flex items-center gap-2 text-[11px]">
                  <span className="text-zinc-600 dark:text-zinc-300 w-32 shrink-0 truncate" title={k.category}>{k.category}</span>
                  <span className={`font-numeric ${k.delta > 0 ? 'text-negative-600 dark:text-negative-400' : 'text-positive-600 dark:text-positive-400'}`}>
                    {k.delta > 0 ? '+' : '−'}{formatPara(Math.abs(k.delta))}
                  </span>
                  <span className="text-zinc-500">
                    {k.durum === 'yeni' ? 'yeni' : k.durum === 'kayboldu' ? 'bu ay yok'
                      : k.delta_pct !== null && k.delta_pct !== undefined ? `%${Math.abs(k.delta_pct).toFixed(0)}` : ''}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
}