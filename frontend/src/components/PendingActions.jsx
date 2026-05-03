import { useState } from 'react';
import { Check, X, AlertCircle, Loader2 } from 'lucide-react';
import { actionsApi } from '../api.js';

/**
 * PendingActions — Onay bekleyen aksiyonlari listeler.
 * Her aksiyon icin "Onayla" / "Reddet" butonlari, payload onizlemesi.
 *
 * Props:
 *   actions: Aksiyon objesi (id veya action_id taşıyabilir)
 *     - GET /api/actions/pending -> PendingActionOut, 'id' field'i
 *     - POST /api/coach/chat response.proposed_actions -> 'action_id' field'i
 *   onResolved: (actionId, status) => void   [parent panel'de cockpit refresh icin]
 *
 * BUG #017 fix (2 May 2026): Iki farkli kaynak iki farkli field adi
 * kullaniyor. (a.id ?? a.action_id) ile her ikisini de destekliyoruz.
 */
export default function PendingActions({ actions, onResolved }) {
  const [busyId, setBusyId] = useState(null);
  const [errorById, setErrorById] = useState({});

  if (!actions || actions.length === 0) return null;

  // Yardimci: aksiyondan gercek id'yi cikar
  const getActionId = (a) => a?.id ?? a?.action_id;

  const handleApprove = async (actionId) => {
    setBusyId(actionId);
    setErrorById((prev) => ({ ...prev, [actionId]: null }));
    try {
      const res = await actionsApi.approve(actionId);
      onResolved?.(actionId, 'approved', res);
    } catch (e) {
      setErrorById((prev) => ({ ...prev, [actionId]: e.message }));
    } finally {
      setBusyId(null);
    }
  };

  const handleReject = async (actionId) => {
    setBusyId(actionId);
    setErrorById((prev) => ({ ...prev, [actionId]: null }));
    try {
      await actionsApi.reject(actionId);
      onResolved?.(actionId, 'rejected', null);
    } catch (e) {
      setErrorById((prev) => ({ ...prev, [actionId]: e.message }));
    } finally {
      setBusyId(null);
    }
  };

  // Aksiyon turune gore okunaklı baslık
  const typeLabels = {
    update_account_balance: 'Bakiye güncelle',
    add_transaction:        'İşlem ekle',
    mark_debt_paid:         'Borç ödendi',
    sell_investment:        'Yatırım sat',
    update_fund_price:      'Fiyat güncelle',
    add_master_checkpoint:  'Yeni kırmızı çizgi',
  };

  return (
    <div className="space-y-2 animate-slide-up">
      {actions.map((a) => {
        const aid = getActionId(a);
        const busy = busyId === aid;
        const error = errorById[aid];
        const payload = typeof a.payload === 'string' ? a.payload : JSON.stringify(a.payload, null, 2);

        return (
          <div
            key={aid}
            className="card p-4 border-brand-300 dark:border-brand-700/50 bg-brand-50/50 dark:bg-brand-900/10"
          >
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-brand-100 dark:bg-brand-900/30 flex items-center justify-center flex-shrink-0">
                <AlertCircle className="w-4 h-4 text-brand-600 dark:text-brand-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="chip chip-neutral text-[10px]">
                    {typeLabels[a.action_type] || a.action_type}
                  </span>
                  <span className="text-[10px] text-zinc-500">#{aid}</span>
                </div>
                <p className="text-sm text-zinc-800 dark:text-zinc-200 leading-snug">
                  {a.summary}
                </p>

                {/* Payload onizleme (kucuk, gri, mono) */}
                <details className="mt-2">
                  <summary className="text-[11px] text-zinc-500 dark:text-zinc-400 cursor-pointer hover:text-zinc-700 dark:hover:text-zinc-200 select-none">
                    Detay
                  </summary>
                  <pre className="mt-2 text-[11px] bg-zinc-100 dark:bg-zinc-800/50 p-2 rounded font-numeric overflow-x-auto">
                    {payload}
                  </pre>
                </details>

                {a.warning && (
                  <div className="mt-3 bg-warn-50 dark:bg-warn-900/20 border border-warn-300 dark:border-warn-700 rounded-md px-3 py-2 text-sm text-warn-800 dark:text-warn-200">
                    {a.warning}
                  </div>
                )}

                {error && (
                  <div className="mt-2 chip chip-negative text-[11px]">
                    <AlertCircle className="w-3 h-3" />
                    {error}
                  </div>
                )}

                <div className="flex gap-2 mt-3">
                  <button
                    onClick={() => handleApprove(aid)}
                    disabled={busy}
                    className="btn btn-positive !py-1.5 !text-xs"
                  >
                    {busy ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Check className="w-3.5 h-3.5" />
                    )}
                    Onayla
                  </button>
                  <button
                    onClick={() => handleReject(aid)}
                    disabled={busy}
                    className="btn btn-secondary !py-1.5 !text-xs"
                  >
                    <X className="w-3.5 h-3.5" />
                    Reddet
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}