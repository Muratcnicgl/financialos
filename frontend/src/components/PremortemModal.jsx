import { useState, useEffect } from 'react';
import { Brain, X, AlertTriangle, ShieldCheck, Loader2, Check } from 'lucide-react';
import { premortemApi, actionsApi } from '../api.js';
import { useToast } from '../components/Toast.jsx';

const PROB_COLORS = {
  dusuk:   { border: 'border-positive-500',  badge: 'bg-positive-100 dark:bg-positive-900/30 text-positive-700 dark:text-positive-300' },
  orta:    { border: 'border-warn-500',       badge: 'bg-warn-100 dark:bg-warn-900/30 text-warn-700 dark:text-warn-300' },
  yuksek:  { border: 'border-negative-500',   badge: 'bg-negative-100 dark:bg-negative-900/30 text-negative-700 dark:text-negative-300' },
};

function fmtImpact(impact_tl) {
  const abs = Math.abs(impact_tl).toLocaleString('tr-TR', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  if (impact_tl < 0) return `−${abs} TL kayıp`;
  if (impact_tl > 0) return `+${abs} TL`;
  return 'belirsiz';
}

export default function PremortemModal({ isOpen, onClose, actionId, onApproved }) {
  const toast = useToast();
  const [phase, setPhase]   = useState('idle');   // idle | loading | success | error | approving
  const [result, setResult] = useState(null);
  const [error, setError]   = useState(null);

  // Escape ile kapat
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  // isOpen değişince: aç → yükle, kapat → sıfırla
  useEffect(() => {
    if (!isOpen) {
      setPhase('idle');
      setResult(null);
      setError(null);
      return;
    }
    runPremortem();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, actionId]);

  const runPremortem = async () => {
    setPhase('loading');
    setError(null);
    try {
      const res = await premortemApi.run(actionId);
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
      // reject hatası sessiz — modal kapatılsın
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
        className="card p-6 w-full sm:max-w-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* HEADER */}
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="flex items-center gap-2.5">
            <Brain className="w-6 h-6 text-warn-500 flex-shrink-0" />
            <div>
              <h3 className="font-semibold text-zinc-900 dark:text-zinc-50">
                Premortem Analizi
              </h3>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                Bu aksiyon 6 ay sonra neden başarısız olurdu? 5 senaryo:
              </p>
            </div>
          </div>
          <button onClick={onClose} className="btn btn-ghost btn-icon !p-1.5 flex-shrink-0" title="Kapat">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* BODY */}
        {phase === 'loading' && (
          <div className="flex flex-col items-center justify-center py-12 gap-3">
            <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Senaryolar hazırlanıyor… (10–20 saniye)
            </p>
          </div>
        )}

        {phase === 'error' && (
          <div className="py-6 space-y-3">
            <div className="flex items-start gap-2">
              <AlertTriangle className="w-5 h-5 text-negative-500 flex-shrink-0 mt-0.5" />
              <p className="text-sm text-negative-700 dark:text-negative-300">
                Premortem motoru cevap veremedi: {error}
              </p>
            </div>
            <button onClick={runPremortem} className="btn btn-secondary !text-xs">
              Tekrar Dene
            </button>
          </div>
        )}

        {(phase === 'success' || phase === 'approving') && result && (
          <div className="space-y-3 mb-4">
            {result.scenarios.map((s) => {
              const colors = PROB_COLORS[s.probability_label] || PROB_COLORS.orta;
              return (
                <div
                  key={s.id}
                  className={`card p-4 border-l-4 ${colors.border}`}
                >
                  {/* Senaryo başlık + badge */}
                  <div className="flex items-center gap-2 mb-2 flex-wrap">
                    <span className="text-xs font-semibold text-zinc-500 dark:text-zinc-400">
                      {s.id}
                    </span>
                    <span className="font-medium text-sm text-zinc-900 dark:text-zinc-100 flex-1">
                      {s.title}
                    </span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium flex-shrink-0 ${colors.badge}`}>
                      {s.probability_label}
                    </span>
                  </div>

                  {/* Narrative */}
                  <p className="text-sm text-zinc-600 dark:text-zinc-400 italic mb-2 leading-relaxed">
                    {s.narrative}
                  </p>

                  {/* Etki + Mitigation */}
                  <div className="space-y-1.5">
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">
                      Tahmini etki:{' '}
                      <span className={s.impact_tl < 0 ? 'text-negative-600 dark:text-negative-400 font-semibold' : s.impact_tl > 0 ? 'text-positive-600 dark:text-positive-400 font-semibold' : ''}>
                        {fmtImpact(s.impact_tl)}
                      </span>
                    </p>
                    <div className="flex items-start gap-2 bg-zinc-100 dark:bg-zinc-800/60 rounded p-2">
                      <ShieldCheck className="w-3.5 h-3.5 text-positive-500 flex-shrink-0 mt-0.5" />
                      <p className="text-xs text-zinc-700 dark:text-zinc-300">
                        <span className="font-medium">Önleme:</span> {s.mitigation}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}

            {/* Provider bilgisi */}
            <p className="text-xs text-zinc-400 dark:text-zinc-500 text-right">
              {result.provider_used} / {result.model_name}
            </p>
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
