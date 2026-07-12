import { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Plus, Loader2 } from 'lucide-react';
import { subscriptionsApi, accountsApi, formatTL } from '../api.js';
import { useToast } from './Toast.jsx';

/**
 * Tespit edilen abonelikler (FEAT-006) + "Düzenli gidere ekle" (detect→act).
 * Salt tespit; kullanıcı onayıyla RecurringExpense'e çevrilir.
 */
export default function DetectedSubscriptions() {
  const toast = useToast();
  const [subs, setSubs] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null);

  const load = useCallback(async () => {
    try {
      const [s, a] = await Promise.all([subscriptionsApi.list(), accountsApi.list()]);
      setSubs(s);
      setAccounts(a);
    } catch (e) {
      // sessiz — abonelik yoksa/veri azsa bölüm gizlenir
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const convert = async (sub) => {
    const cash = accounts.find((a) => a.account_type === 'cash') || accounts[0];
    if (!cash) { toast.error('Önce bir hesap ekle'); return; }
    const day = sub.son_tarih ? new Date(sub.son_tarih + 'T00:00:00').getDate() : 1;
    try {
      setBusy(sub.anahtar);
      await subscriptionsApi.toRecurring({
        isim: sub.isim, aylik_tutar: sub.aylik_maliyet, account_id: cash.id, day_of_month: day,
      });
      toast.success(`${sub.isim} düzenli gidere eklendi`);
      load();
    } catch (e) {
      toast.error(e.message || 'Eklenemedi');
    } finally {
      setBusy(null);
    }
  };

  if (loading || !subs || !subs.abonelikler?.length) return null;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <RefreshCw className="w-4 h-4 text-zinc-500 dark:text-zinc-400" />
        <h3 className="text-sm font-semibold">Tespit edilen abonelikler</h3>
        <span className="text-xs text-zinc-400 dark:text-zinc-500 ml-auto">
          {formatTL(subs.aylik_toplam)} TL/ay
        </span>
      </div>
      {subs.abonelikler.map((s) => (
        <div key={s.anahtar} className="card p-3 flex items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="font-medium truncate">{s.isim}</p>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              {formatTL(s.aylik_maliyet)} TL/ay · {s.tekrar} kez
              {s.fiyat_degisti && <span className="text-warn-600 dark:text-warn-400"> · zam var</span>}
            </p>
          </div>
          <button onClick={() => convert(s)} disabled={busy === s.anahtar}
                  className="btn btn-secondary !text-xs flex items-center gap-1 shrink-0">
            {busy === s.anahtar ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
            Düzenli gidere ekle
          </button>
        </div>
      ))}
    </div>
  );
}
