import {
  Wallet, CreditCard, TrendingUp, Building2, Lock,
  ExternalLink, Clock,
} from 'lucide-react';
import { formatDate } from '../api.js';
import { formatPara, formatSayi, paraEtiketi } from '../lib/money.js';

/**
 * AccountCard — Bir hesabin detayli karti.
 * Hesap tipine gore farkli gosterim:
 *   cash        -> Sadece bakiye + ad
 *   credit_card -> Bakiye + limit + kullanim orani (progress bar) + kesim/odeme
 *   loan        -> Bakiye + aylik taksit + kalan taksit + sonraki tarih
 *   investment  -> Bakiye + lot + fiyat + maliyet + EMANET rozeti varsa
 *
 * onPriceUpdateClick: investment hesaplari icin "Fiyat guncelle" butonu callback'i
 */
export default function AccountCard({ account, onPriceUpdateClick }) {
  const a = account;

  // Tipi gore ikon ve renk
  const typeMeta = {
    cash:        { icon: Wallet,      label: 'Nakit',     color: 'text-positive-600 dark:text-positive-400', bg: 'bg-positive-50 dark:bg-positive-900/20' },
    credit_card: { icon: CreditCard,  label: 'Kart',      color: 'text-negative-600 dark:text-negative-400', bg: 'bg-negative-50 dark:bg-negative-900/20' },
    loan:        { icon: Building2,   label: 'Kredi',     color: 'text-warn-600 dark:text-warn-400',         bg: 'bg-warn-50 dark:bg-warn-900/20' },
    investment:  { icon: TrendingUp,  label: 'Yatırım',   color: 'text-brand-600 dark:text-brand-400',       bg: 'bg-brand-50 dark:bg-brand-900/20' },
  };

  const meta = typeMeta[a.tip] || typeMeta.cash;
  const Icon = meta.icon;

  return (
    <div className={`card p-4 ${a.is_emanet ? 'border-warn-300 dark:border-warn-700/50' : ''}`}>
      {/* Ust: ikon + ad + tip */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${meta.bg}`}>
            <Icon className={`w-5 h-5 ${meta.color}`} />
          </div>
          <div className="min-w-0">
            <h4 className="font-semibold text-sm truncate">{a.ad}</h4>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">{meta.label}</p>
          </div>
        </div>
        {a.is_emanet && (
          <span className="chip chip-warn text-[10px] flex-shrink-0" title="MC1: Bu hesap dokunulmazdir">
            <Lock className="w-3 h-3" /> EMANET
          </span>
        )}
      </div>

      {/* Bakiye */}
      <p className="font-numeric text-xl font-bold mb-2">
        {formatSayi(a.bakiye)} <span className="text-xs font-normal text-zinc-500">{paraEtiketi()}</span>
      </p>

      {/* Tipe ozel detaylar */}
      {a.tip === 'credit_card' && (
        <div className="space-y-2 text-xs">
          <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
            <span>Limit</span>
            <span className="font-numeric">{formatPara(a.limit)}</span>
          </div>
          <div>
            <div className="flex justify-between text-zinc-600 dark:text-zinc-400 mb-1">
              <span>Kullanım</span>
              <span className={`font-numeric font-semibold ${a.kullanim_orani > 95 ? 'text-negative-600 dark:text-negative-400' : a.kullanim_orani > 75 ? 'text-warn-600 dark:text-warn-400' : 'text-zinc-700 dark:text-zinc-300'}`}>
                %{a.kullanim_orani?.toFixed(1)}
              </span>
            </div>
            <div className="h-2 bg-zinc-200 dark:bg-zinc-800 rounded-full overflow-hidden">
              <div
                className={`h-full transition-all ${a.kullanim_orani > 95 ? 'bg-negative-500' : a.kullanim_orani > 75 ? 'bg-warn-500' : 'bg-positive-500'}`}
                style={{ width: `${Math.min(100, a.kullanim_orani || 0)}%` }}
              />
            </div>
          </div>
        </div>
      )}

      {a.tip === 'loan' && (
        <div className="space-y-1 text-xs text-zinc-600 dark:text-zinc-400">
          <div className="flex justify-between">
            <span>Aylık taksit</span>
            <span className="font-numeric font-semibold text-zinc-800 dark:text-zinc-200">
              {formatPara(a.aylik_taksit)}
            </span>
          </div>
          <div className="flex justify-between">
            <span>Kalan taksit</span>
            <span className="font-numeric">{a.kalan_taksit}</span>
          </div>
          {a.sonraki_taksit && (
            <div className="flex justify-between">
              <span>Sonraki</span>
              <span className="font-numeric">{formatDate(a.sonraki_taksit)}</span>
            </div>
          )}
        </div>
      )}

      {a.tip === 'investment' && (
        <div className="space-y-1 text-xs text-zinc-600 dark:text-zinc-400">
          <div className="flex justify-between">
            <span>Lot</span>
            <span className="font-numeric">{a.lot}</span>
          </div>
          <div className="flex justify-between">
            <span>Fiyat</span>
            <span className="font-numeric">{formatPara(a.fiyat)}</span>
          </div>
          {a.maliyet_per_lot && (
            <div className="flex justify-between">
              <span>Maliyet/lot</span>
              <span className="font-numeric">{formatPara(a.maliyet_per_lot)}</span>
            </div>
          )}
          {!a.is_emanet && onPriceUpdateClick && (
            <button
              onClick={() => onPriceUpdateClick(a)}
              className="mt-2 w-full btn btn-secondary !py-1.5 !text-xs"
              title="Manuel fiyat güncelle"
            >
              <Clock className="w-3 h-3" />
              Fiyat güncelle
            </button>
          )}
        </div>
      )}
    </div>
  );
}