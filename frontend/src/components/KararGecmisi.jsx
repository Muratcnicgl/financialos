import { useEffect, useState } from 'react';
import { History } from 'lucide-react';
import { actionsApi, formatDate } from '../api.js';
import KatlanirBolum from './KatlanirBolum.jsx';

/**
 * Karar geçmişi — UX-027 (BUG #471).
 * Onaylanan / reddedilen / başarısız son aksiyonlar; reddin gerekçesi görünür. Kaynak
 * `pending_actions` (audit_log da aynı geçişi tutar). Katlı gelir: geçmiş bilgi, acil değil.
 */
const DURUM = {
  executed: ['Onaylandı', 'text-positive-600 dark:text-positive-400'],
  approved: ['Onaylandı', 'text-positive-600 dark:text-positive-400'],
  rejected: ['Reddedildi', 'text-zinc-500 dark:text-zinc-400'],
  failed: ['Başarısız', 'text-negative-600 dark:text-negative-400'],
};

export function durumEtiketi(status) {
  return DURUM[status] || [status, 'text-zinc-500'];
}

export default function KararGecmisi({ yenilemeSayaci = 0 }) {
  const [kayitlar, setKayitlar] = useState(null);
  useEffect(() => {
    let iptal = false;
    actionsApi.gecmis(20).then((r) => { if (!iptal) setKayitlar(r || []); }).catch(() => { if (!iptal) setKayitlar([]); });
    return () => { iptal = true; };
  }, [yenilemeSayaci]);
  if (!kayitlar || kayitlar.length === 0) return null;
  const red = kayitlar.filter((k) => k.status === 'rejected').length;
  return (
    <KatlanirBolum ikon={History} baslik="Karar geçmişi" anahtar="cockpit_karar_gecmisi"
                   ozet={`son ${kayitlar.length} · ${red} red`} varsayilanAcik={false}>
      <ul className="space-y-1.5" data-testid="karar-gecmisi">
        {kayitlar.map((k) => {
          const [etiket, renk] = durumEtiketi(k.status);
          return (
            <li key={k.id} className="text-xs flex items-start justify-between gap-2 border-b border-zinc-100 dark:border-zinc-800 last:border-0 py-1">
              <span className="min-w-0">
                <span className="text-zinc-700 dark:text-zinc-300">{k.summary}</span>
                {k.status === 'rejected' && k.error_message && (
                  <span className="block text-zinc-500 dark:text-zinc-400">Gerekçe: {k.error_message}</span>
                )}
              </span>
              <span className={`flex-shrink-0 text-right ${renk}`}>
                {etiket}
                <span className="block text-zinc-500 dark:text-zinc-400">{formatDate(k.resolved_at || k.created_at)}</span>
              </span>
            </li>
          );
        })}
      </ul>
    </KatlanirBolum>
  );
}
