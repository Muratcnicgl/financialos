import { TrendingUp, TrendingDown } from 'lucide-react';
import { formatTL } from '../api.js';

/**
 * MetricCard — Cockpit'teki tek bir gostergeyi (nakit, kart borcu vb.)
 * gosteren kart. Renk semantik:
 *   variant = 'positive' | 'negative' | 'warn' | 'neutral' | 'brand'
 *
 * Ozellikler:
 *  - Buyuk numerik deger (mono font, tabular-nums)
 *  - Opsiyonel ikon (Lucide)
 *  - Opsiyonel alt yazi (subtitle)
 *  - Opsiyonel trend (yukari/asagi ok)
 *  - Opsiyonel emanet rozet (DOKUNULMAZ etiketi MC1 icin)
 */
export default function MetricCard({
  title,
  value,
  variant = 'neutral',
  icon: Icon,
  subtitle,
  trend,           // 'up' | 'down' | null
  isEmanet = false,
  prefix = '',
  suffix = ' TL',
  loading = false,
}) {
  const variants = {
    neutral: {
      iconBg:   'bg-zinc-100 dark:bg-zinc-800',
      iconText: 'text-zinc-600 dark:text-zinc-400',
      valueText: 'text-zinc-900 dark:text-zinc-50',
    },
    positive: {
      iconBg:   'bg-positive-100 dark:bg-positive-900/30',
      iconText: 'text-positive-600 dark:text-positive-400',
      valueText: 'text-positive-700 dark:text-positive-400',
    },
    negative: {
      iconBg:   'bg-negative-100 dark:bg-negative-900/30',
      iconText: 'text-negative-600 dark:text-negative-400',
      valueText: 'text-negative-700 dark:text-negative-400',
    },
    warn: {
      iconBg:   'bg-warn-100 dark:bg-warn-900/30',
      iconText: 'text-warn-600 dark:text-warn-400',
      valueText: 'text-warn-700 dark:text-warn-400',
    },
    brand: {
      iconBg:   'bg-brand-100 dark:bg-brand-900/30',
      iconText: 'text-brand-600 dark:text-brand-400',
      valueText: 'text-brand-700 dark:text-brand-400',
    },
  };

  const v = variants[variant] || variants.neutral;

  return (
    <div className={`card p-4 sm:p-5 ${isEmanet ? 'border-warn-300 dark:border-warn-700/50' : ''} animate-fade-in`}>
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2 min-w-0">
          {Icon && (
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${v.iconBg}`}>
              <Icon className={`w-4 h-4 ${v.iconText}`} />
            </div>
          )}
          <h3 className="text-xs sm:text-sm font-medium text-zinc-600 dark:text-zinc-400 truncate">
            {title}
          </h3>
        </div>
        {isEmanet && (
          <span className="chip chip-warn text-[10px] flex-shrink-0">
            🔒 EMANET
          </span>
        )}
      </div>

      <div className="flex items-end gap-2">
        {loading ? (
          <div className="h-8 w-32 bg-zinc-200 dark:bg-zinc-800 rounded animate-pulse" />
        ) : (
          <>
            {/* MC2 (Wave-8): mobilde text-lg (2-kolon grid ~150px'e sığar) + truncate YOK →
                kritik net-değer kesilmesin; realistik TL değeri tek satır sığar. */}
            <p className={`font-numeric text-lg sm:text-2xl font-bold ${v.valueText} leading-tight`}>
              {prefix}{formatTL(value)}{suffix}
            </p>
            {trend === 'up' && (
              <TrendingUp className="w-4 h-4 text-positive-500 mb-1 flex-shrink-0" />
            )}
            {trend === 'down' && (
              <TrendingDown className="w-4 h-4 text-negative-500 mb-1 flex-shrink-0" />
            )}
          </>
        )}
      </div>

      {subtitle && (
        <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1.5 truncate">
          {subtitle}
        </p>
      )}
    </div>
  );
}