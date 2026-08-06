/**
 * Loss Aversion Framing: Kullanici 'Kazanc' veya 'Kayip' bakisi secer.
 * Ayni veri, iki perspektif (Kahneman/Tversky 1979 prospect theory).
 * Default 'gain' (Kahneman gain frame norm) - loss frame opsiyonel, kullanici secer.
 * AI birini dogru diye dayatmaz, iki bakis acisi gosterir (ADR-001).
 */
import { useState, useEffect } from 'react';
import { TrendingUp, X, Calendar, Clock, ArrowRight, Loader2, AlertTriangle, Check } from 'lucide-react';
import { simulationApi, actionsApi } from '../api.js';
import { formatPara, formatSayi, paraEtiketi } from '../lib/money.js';
import { useToast } from '../components/Toast.jsx';

// ============================================================
// YARDIMCI FORMATLAYICILAR
// ============================================================

// BUG #256 (H4): bu dosya kendi `toLocaleString('tr-TR', …)` biçimlendiricisini kuruyor ve
// para etiketini elle ' TL' yazıyordu — api.js'ten bağımsız DÖRDÜNCÜ uygulama. Tek kaynağa
// bağlandı (`lib/money.js`); sayı biçimi ve etiket artık tüm arayüzle birlikte değişir.
const fmt = (v) => formatSayi(v ?? 0);

const fmtDelta = (v, frame = 'gain') => {
  if (v === undefined || v === null || v === 0) return null;
  const paraStr = formatPara(Math.abs(v));
  if (frame === 'gain') {
    return v > 0 ? `+${paraStr} kazanç` : `−${paraStr} kayıp`;
  } else {
    return v > 0 ? `+${paraStr} fırsat` : `−${paraStr} risk`;
  }
};

const summaryText = (val, frame, metric) => {
  if (val === null || val === undefined || val === 0) return null;
  const absStr = formatPara(Math.abs(val));
  const sign = val > 0 ? '+' : '−';
  if (frame === 'gain') {
    const verb = val > 0 ? 'kazanırsın' : 'kaybedersin';
    return `30g sonra ${metric}: ${sign}${absStr} ${verb}`;
  } else {
    const verb = val > 0 ? 'fırsatını kaçırırsın' : 'risk azaltma fırsatını kaçırırsın';
    return `Bu aksiyonu yapmazsan 30g'de ${metric}: ${sign}${absStr} ${verb}`;
  }
};

// ============================================================
// HORIZON KARTI
// ============================================================

const HORIZON_META = [
  { label: 'T+0',  sublabel: 'Bugün',       icon: Clock,      border: 'border-brand-500'    },
  { label: 'T+30', sublabel: '1 Ay Sonra',  icon: Calendar,   border: 'border-warn-500'     },
  { label: 'T+90', sublabel: '3 Ay Sonra',  icon: ArrowRight, border: 'border-positive-500' },
];

function HorizonCard({ snap, meta, frame }) {
  const delta = snap.delta_vs_baseline || {};
  const Icon = meta.icon;

  const rows = [
    { label: 'Net Değer',  value: snap.net_deger,     deltaKey: 'net_deger'     },
    { label: 'Nakit',      value: snap.nakit_kasa,    deltaKey: 'nakit_kasa'    },
    { label: 'Kart Borcu', value: snap.kart_borcu,    deltaKey: 'kart_borcu'    },
    { label: 'Yatırım',    value: snap.yatirim_deger, deltaKey: 'yatirim_deger' },
  ];

  return (
    <div className={`card p-4 border-l-4 ${meta.border}`}>
      <div className="flex items-center gap-2 mb-3">
        <Icon className="w-4 h-4 text-zinc-500 dark:text-zinc-400 flex-shrink-0" />
        <div>
          <p className="text-xs font-semibold text-zinc-500 dark:text-zinc-400">{snap.label}</p>
          <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{meta.sublabel}</p>
        </div>
      </div>

      <div className="space-y-1.5">
        {rows.map(({ label, value, deltaKey }) => {
          const dText = fmtDelta(delta[deltaKey], frame);
          const isNet = label === 'Net Değer';
          const dVal = delta[deltaKey];
          return (
            <div key={label} className="flex items-start justify-between gap-2">
              <span className="text-xs text-zinc-500 dark:text-zinc-400 flex-shrink-0">{label}</span>
              <div className="text-right">
                <span className={`text-xs font-numeric font-medium ${
                  isNet && value < 0
                    ? 'text-negative-600 dark:text-negative-400'
                    : isNet && value > 0
                    ? 'text-positive-600 dark:text-positive-400'
                    : 'text-zinc-700 dark:text-zinc-300'
                }`}>
                  {formatPara(value ?? 0)}
                </span>
                {dText && (
                  <p className={`text-[10px] font-numeric ${dVal < 0 ? 'text-negative-500' : 'text-positive-500'}`}>
                    Δ {dText}
                  </p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================
// ANA MODAL
// ============================================================

export default function HorizonsModal({ isOpen, onClose, actionId, onApproved }) {
  const toast = useToast();
  const [phase, setPhase]   = useState('idle');
  const [result, setResult] = useState(null);
  const [error, setError]   = useState(null);
  const [frame, setFrame]   = useState('gain');  // 'gain' | 'loss' — default gain (Kahneman norm)

  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  useEffect(() => {
    if (!isOpen) {
      setPhase('idle');
      setResult(null);
      setError(null);
      setFrame('gain');
      return;
    }
    runSimulation();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, actionId]);

  const runSimulation = async () => {
    setPhase('loading');
    setError(null);
    try {
      const res = await simulationApi.run(actionId);
      setResult(res);
      setPhase('success');
    } catch (e) {
      setError(e.message || 'Bilinmeyen hata.');
      setPhase('error');
    }
  };

  const handleApprove = async () => {
    setPhase('approving');
    try {
      const res = await actionsApi.approve(actionId);
      toast.success('Aksiyon uygulandı');
      onApproved?.(actionId, res);
      onClose();
    } catch (e) {
      toast.error(`Onaylama hatası: ${e.message}`);
      setPhase('success');
    }
  };

  const handleReject = async () => {
    try {
      await actionsApi.reject(actionId);
      toast.info('Aksiyon reddedildi');
    } catch {
      // sessiz
    }
    onClose();
  };

  if (!isOpen) return null;

  const canAct = phase === 'success' || phase === 'approving';

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center px-4 animate-fade-in"
      onClick={onClose}
    >
      <div
        className="card p-6 w-full sm:max-w-4xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* HEADER */}
        <div className="flex items-start justify-between gap-3 mb-5">
          <div className="flex items-center gap-2.5">
            <TrendingUp className="w-6 h-6 text-brand-500 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-zinc-900 dark:text-zinc-50">
                3-Ufuklu Karar Masası
              </h3>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                Bu aksiyon üç farklı zaman ufkunda nasıl sonuç verir?
              </p>
            </div>
          </div>

          {/* Sag: frame toggle + kapat */}
          <div className="flex items-center gap-3 flex-shrink-0">
            <div
              className="flex rounded-lg border border-zinc-200 dark:border-zinc-700 overflow-hidden text-xs"
              title="Bakış açısını değiştir — aynı veri, iki perspektif"
            >
              <button
                onClick={() => setFrame('gain')}
                aria-pressed={frame === 'gain'}
                className={`px-3 py-1.5 font-medium transition-colors ${
                  frame === 'gain'
                    ? 'bg-positive-500 text-white'
                    : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                }`}
              >
                Kazanç
              </button>
              <button
                onClick={() => setFrame('loss')}
                aria-pressed={frame === 'loss'}
                className={`px-3 py-1.5 font-medium transition-colors ${
                  frame === 'loss'
                    ? 'bg-negative-500 text-white'
                    : 'text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800'
                }`}
              >
                Kayıp
              </button>
            </div>
            <button
              onClick={onClose}
              className="btn btn-ghost btn-icon !p-1.5"
              aria-label="Kapat"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* BODY — loading */}
        {phase === 'loading' && (
          <div className="flex flex-col items-center justify-center py-12 gap-3">
            <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Simülasyon hesaplanıyor…
            </p>
          </div>
        )}

        {/* BODY — error */}
        {phase === 'error' && (
          <div className="py-6 space-y-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-5 h-5 text-negative-500 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-negative-700 dark:text-negative-300">
                Simülasyon motoru cevap veremedi: {error}
              </p>
            </div>
            <button type="button" onClick={runSimulation} className="btn btn-secondary !text-xs">
              Tekrar Dene
            </button>
          </div>
        )}

        {/* BODY — success */}
        {(phase === 'success' || phase === 'approving') && result && (
          <div className="space-y-4 mb-4">
            {/* 3 sutun grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {result.horizons?.map((snap) => {
                const meta = HORIZON_META.find(m => m.label === snap.label) || HORIZON_META[0];
                return (
                  <HorizonCard key={snap.label} snap={snap} meta={meta} frame={frame} />
                );
              })}
            </div>

            {/* Summary karti */}
            {result.summary && Object.keys(result.summary).length > 0 && (() => {
              const nwText = summaryText(result.summary.net_worth_change_30d, frame, 'net değer');
              const cashText = summaryText(result.summary.cash_change_30d, frame, 'nakit');
              if (!nwText && !cashText) return null;
              return (
                <div className="card p-4 bg-brand-50/50 dark:bg-brand-950/20 border-brand-200 dark:border-brand-800/50">
                  <div className="flex flex-col gap-1.5 text-sm">
                    {nwText && (
                      <span>
                        <span className={`font-numeric font-semibold ${(result.summary.net_worth_change_30d ?? 0) < 0 ? 'text-negative-600 dark:text-negative-400' : 'text-positive-600 dark:text-positive-400'}`}>
                          {nwText}
                        </span>
                      </span>
                    )}
                    {cashText && (
                      <span>
                        <span className={`font-numeric font-semibold ${(result.summary.cash_change_30d ?? 0) < 0 ? 'text-negative-600 dark:text-negative-400' : 'text-positive-600 dark:text-positive-400'}`}>
                          {cashText}
                        </span>
                      </span>
                    )}
                  </div>
                </div>
              );
            })()}

            {/* Event log */}
            {result.event_log?.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 mb-1">Olaylar:</p>
                <ul className="space-y-0.5">
                  {result.event_log.slice(0, 5).map((ev, i) => (
                    <li key={i} className="text-xs text-zinc-500 dark:text-zinc-400 font-numeric">{ev}</li>
                  ))}
                  {result.event_log.length > 5 && (
                    <li className="text-xs text-zinc-400 dark:text-zinc-500">
                      +{result.event_log.length - 5} daha
                    </li>
                  )}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* FOOTER */}
        <div className="flex flex-wrap gap-2 pt-4 border-t border-zinc-200 dark:border-zinc-700">
          <button type="button" onClick={onClose} className="btn btn-ghost !text-xs">
            İptal
          </button>
          <button
            onClick={handleReject}
            disabled={!canAct}
            className="btn btn-secondary !text-xs"
          >
            Vazgeç (Reddet)
          </button>
          <button
            onClick={handleApprove}
            disabled={!canAct || phase === 'approving'}
            className="btn btn-positive !text-xs ml-auto"
          >
            {phase === 'approving' ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Check className="w-3.5 h-3.5" />
            )}
            Yine de Onayla
          </button>
        </div>
      </div>
    </div>
  );
}
