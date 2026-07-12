import { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { reportsApi, formatTL } from '../api.js';

/**
 * Net değer analizi (FEAT-021 ayrıştırma + FEAT-024 enflasyon-düzeltilmiş reel).
 * Yeterli snapshot geçmişi yoksa "veri birikince" notu gösterir.
 */
export default function NetWorthAnalysis() {
  const [attr, setAttr] = useState(null);
  const [real, setReal] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    Promise.all([reportsApi.netWorthAttribution(), reportsApi.realNetWorth()])
      .then(([a, r]) => { if (active) { setAttr(a); setReal(r); } })
      .catch(() => {})
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  if (loading) return null;

  const hasAttr = attr?.available;
  const hasReal = real?.available;

  return (
    <div className="space-y-3 pt-2">
      <div>
        <h2 className="text-base font-semibold">Net Değer Analizi</h2>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          Değişimin sürücüleri + enflasyona göre reel durum
        </p>
      </div>

      {!hasAttr && !hasReal ? (
        <div className="card p-4 text-sm text-zinc-500 dark:text-zinc-400">
          Analiz için birkaç günlük net değer geçmişi gerekiyor — sistemi kullandıkça birikecek.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {/* FEAT-021: değişim sürücüleri */}
          {hasAttr && (
            <div className="card p-4">
              <h3 className="text-sm font-semibold mb-2 text-zinc-700 dark:text-zinc-300">
                Bu dönem net değer değişimi
              </h3>
              <p className={`font-numeric text-xl font-bold mb-2 ${attr.degisim >= 0 ? 'text-positive-600 dark:text-positive-400' : 'text-negative-600 dark:text-negative-400'}`}>
                {attr.degisim >= 0 ? '+' : ''}{formatTL(attr.degisim)} TL
              </p>
              <div className="space-y-1">
                {attr.surucureler.map((s) => (
                  <div key={s.ad} className="flex items-center justify-between text-xs">
                    <span className="text-zinc-600 dark:text-zinc-400">{s.ad}</span>
                    <span className={`font-numeric ${s.katki >= 0 ? 'text-positive-600 dark:text-positive-400' : 'text-negative-600 dark:text-negative-400'}`}>
                      {s.katki >= 0 ? '+' : ''}{formatTL(s.katki)} TL
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* FEAT-024: reel (enflasyon-düzeltilmiş) */}
          {hasReal && (
            <div className="card p-4">
              <h3 className="text-sm font-semibold mb-2 text-zinc-700 dark:text-zinc-300">
                Enflasyona göre reel ({Math.round(real.yillik_enflasyon * 100)}%/yıl · {real.gun} gün)
              </h3>
              <div className="flex items-center gap-2 mb-1">
                {real.reel_degisim >= 0 ? <TrendingUp className="w-4 h-4 text-positive-500" /> : <TrendingDown className="w-4 h-4 text-negative-500" />}
                <span className="text-xs text-zinc-500 dark:text-zinc-400">
                  Nominal {real.nominal_degisim >= 0 ? '+' : ''}{formatTL(real.nominal_degisim)} → Reel{' '}
                  <span className={real.reel_degisim >= 0 ? 'text-positive-600 dark:text-positive-400 font-semibold' : 'text-negative-600 dark:text-negative-400 font-semibold'}>
                    {real.reel_degisim >= 0 ? '+' : ''}{formatTL(real.reel_degisim)}
                  </span> TL
                </span>
              </div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400">
                Enflasyon etkisi: <span className={real.enflasyon_etkisi >= 0 ? 'text-positive-600 dark:text-positive-400' : 'text-negative-600 dark:text-negative-400'}>
                  {formatTL(real.enflasyon_etkisi)} TL
                </span>
                {real.enflasyon_etkisi >= 0 ? ' (borç eridi)' : ' (servet aşındı)'}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
