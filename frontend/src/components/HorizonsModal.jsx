import { useState, useEffect } from 'react';
import { TrendingUp, X, Calendar, Clock, ArrowRight, Loader2, AlertTriangle, Check } from 'lucide-react';
import { simulationApi, actionsApi } from '../api.js';
import { useToast } from '../components/Toast.jsx';

const fmtTL = (v) =>
  (v ?? 0).toLocaleString('tr-TR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const fmtDelta = (v) => {
  if (v === undefined || v === null || v === 0) return null;
  const sign = v > 0 ? '+' : '';
  return `${sign}${fmtTL(v)} TL`;
};

const HORIZON_META = [
  { label: 'T+0',  title: 'Bugün',       icon: Clock,     border: 'border-brand-500'   },
  { label: 'T+30', title: '1 Ay Sonra',  icon: Calendar,  border: 'border-warn-500'    },
  { label: 'T+90', title: '3 Ay Sonra',  icon: ArrowRight, border: 'border-positive-500' },
];

function HorizonCard({ snap, meta }) {
  const delta = snap.delta_vs_baseline || {};
  const Icon = meta.icon;

  const rows = [
    { label: 'Net Değer',  value: snap.net_deger,    deltaKey: 'net_deger'    },
    { label: 'Nakit',      value: snap.nakit_kasa,   deltaKey: 'nakit_kasa'   },
    { label: 'Kart Borcu', value: snap.kart_borcu,   deltaKey: 'kart_borcu'   },
    { label: 'Yatırım',    value: snap.yatirim_deger, deltaKey: 'yatirim_deger' },
  ];

  return (
    <div className={`card p-4 border-l-4 ${meta.border}`}>
      <div className="flex items-center gap-2 mb-3">
        <Icon className="w-4 h-4 text-zinc-500 dark:text-zinc-400 flex-shrink-0" />
        <div>
          <p className="text-xs font-semibold text-zinc-500 dark:text-zinc-400">{snap.label}</p>
          <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">{meta.title}</p>
        </div>
      </div>

      <div className="space-y-1.5">
        {rows.map(({ label, value, deltaKey }) => {
          const d = fmtDelta(delta[deltaKey]);
          const isNet = label === 'Net Değer';
          const dVal = delta[deltaKey];
          return (
            <div key={label} className="flex items-start justify-between gap-2">
              <span className="text-xs text-zinc-500 dark:text-zinc-400 flex-shrink-0">{label}</span>
              <div className="text-right">
                <span className={`text-xs font-numeric font-medium ${isNet && value < 0 ? 'text-negative-600 dark:text-negative-400' : isNet && value > 0 ? 'text-positive-600 dark:text-positive-400' : 'text-zinc-700 dark:text-zinc-300'}`}>
                  {fmtTL(value)} TL
                </span>
                {d && (
                  <p className={`text-[10px] font-numeric ${dVal < 0 ? 'text-negative-500' : 'text-positive-500'}`}>
                    Δ {d}
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

export default function HorizonsModal({ isOpen, onClose, actionId, onApproved }) {
  const toast = useToast();
  const [phase, setPhase]   = useState('idle');
  const [result, setResult] = useState(null);
  const [error, setError]   = useState(null);

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
          <button onClick={onClose} className="btn btn-ghost btn-icon !p-1.5 flex-shrink-0" title="Kapat">
            <X className="w-4 h-4" />
          </button>
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
            <button onClick={runSimulation} className="btn btn-secondary !text-xs">
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
                return <HorizonCard key={snap.label} snap={snap} meta={meta} />;
              })}
            </div>

            {/* Summary karti */}
            {result.summary && Object.keys(result.summary).length > 0 && (
              <div className="card p-4 bg-brand-50/50 dark:bg-brand-950/20 border-brand-200 dark:border-brand-800/50">
                <div className="flex flex-wrap gap-4 text-sm">
                  {result.summary.net_worth_change_30d !== undefined && (
                    <span>
                      <span className="text-zinc-500 dark:text-zinc-400">30g net değer Δ:</span>{' '}
                      <span className={`font-numeric font-semibold ${result.summary.net_worth_change_30d < 0 ? 'text-negative-600 dark:text-negative-400' : 'text-positive-600 dark:text-positive-400'}`}>
                        {result.summary.net_worth_change_30d > 0 ? '+' : ''}{fmtTL(result.summary.net_worth_change_30d)} TL
                      </span>
                    </span>
                  )}
                  {result.summary.cash_change_30d !== undefined && (
                    <span>
                      <span className="text-zinc-500 dark:text-zinc-400">30g nakit Δ:</span>{' '}
                      <span className={`font-numeric font-semibold ${result.summary.cash_change_30d < 0 ? 'text-negative-600 dark:text-negative-400' : 'text-positive-600 dark:text-positive-400'}`}>
                        {result.summary.cash_change_30d > 0 ? '+' : ''}{fmtTL(result.summary.cash_change_30d)} TL
                      </span>
                    </span>
                  )}
                </div>
              </div>
            )}

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
          <button onClick={onClose} className="btn btn-ghost !text-xs">
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
