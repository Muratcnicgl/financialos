import { formatPara } from '../lib/money.js';

/**
 * "Bu ay" temposu — UX-028 (BUG #466).
 * Ayın ilerleme çubuğu + harcama temposu hükmü (goal-gradient: ne kadar kaldığını ve
 * gidişatı görmek davranışı düzeltir). Hüküm backend'den (`ay_temposu.durum`); burada yalnız
 * gösterim. "erken"/"bilinmiyor" durumlarında hüküm cümlesi kurulmaz, sayı yine gösterilir.
 */
export function tempoCumlesi(t) {
  if (!t) return null;
  if (t.durum === 'erken') return `Ayın ${t.gun}. günü — tempo için henüz erken`;
  if (t.durum === 'bilinmiyor') return `Bu gidişle ay sonu gider ~${formatPara(t.projeksiyon, { ondalik: 0 })} (geçen ay referansı yok)`;
  const yon = t.durum === 'ustunde' ? 'üstünde' : 'hedefte';
  return `Bu gidişle ay sonu ~${formatPara(t.projeksiyon, { ondalik: 0 })} · ${t.referans_ay} (${formatPara(t.referans, { ondalik: 0 })}) temposunun ${yon}`;
}

export default function AyTemposu({ tempo }) {
  if (!tempo) return null;
  const ustunde = tempo.durum === 'ustunde';
  return (
    <div data-testid="ay-temposu" className="mt-3">
      <div className="flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400 mb-1">
        <span>Ayın {tempo.gun}/{tempo.ay_gunu}. günü · %{Math.round(tempo.ilerleme_pct)}</span>
        <span>Harcanan {formatPara(tempo.harcanan, { ondalik: 0 })}</span>
      </div>
      <div className="h-1.5 rounded-full bg-zinc-200 dark:bg-zinc-800 overflow-hidden" role="progressbar"
           aria-valuenow={Math.round(tempo.ilerleme_pct)} aria-valuemin={0} aria-valuemax={100} aria-label="Ay ilerlemesi">
        <div className="h-full rounded-full bg-brand-500" style={{ width: `${Math.min(100, tempo.ilerleme_pct)}%` }} />
      </div>
      <p className={`text-xs mt-1 ${ustunde ? 'text-negative-600 dark:text-negative-400' : 'text-zinc-600 dark:text-zinc-400'}`}>
        {ustunde ? '▲ ' : ''}{tempoCumlesi(tempo)}
      </p>
    </div>
  );
}
