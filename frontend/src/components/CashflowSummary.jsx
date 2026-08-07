import { TrendingDown, TrendingUp, AlertTriangle, Wallet } from 'lucide-react';
import { formatDate } from '../api.js';
import { formatPara, formatSayi } from '../lib/money.js';

export default function CashflowSummary({ summary }) {
  const { lowest_balance, lowest_date, total_receivable, total_payable, net_flow, crunch_count, opening_balance } = summary;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {/* Açılış bakiyesi */}
      <div className="card p-4">
        <div className="flex items-center gap-1.5 mb-2">
          <Wallet className="w-3.5 h-3.5 text-zinc-500 dark:text-zinc-400" />
          <p className="text-xs text-zinc-500 dark:text-zinc-400">Mevcut Nakit</p>
        </div>
        <p className="font-numeric font-bold text-lg text-zinc-900 dark:text-zinc-50">
          {formatPara(opening_balance)}
        </p>
      </div>

      {/* En düşük bakiye */}
      <div className={`card p-4 ${lowest_balance < 0 ? 'border-negative-300 dark:border-negative-700/50' : ''}`}>
        <div className="flex items-center gap-1.5 mb-2">
          <TrendingDown className={`w-3.5 h-3.5 ${lowest_balance < 0 ? 'text-negative-500' : 'text-zinc-500 dark:text-zinc-400'}`} />
          <p className="text-xs text-zinc-500 dark:text-zinc-400">En Düşük Bakiye</p>
        </div>
        <p className={`font-numeric font-bold text-lg ${lowest_balance >= 0 ? 'text-positive-600 dark:text-positive-400' : 'text-negative-600 dark:text-negative-400'}`}>
          {formatPara(lowest_balance)}
        </p>
        <p className="text-xs text-zinc-500 mt-0.5">
          {formatDate(lowest_date, { withYear: true })}
        </p>
      </div>

      {/* Net akış */}
      <div className="card p-4">
        <div className="flex items-center gap-1.5 mb-2">
          {net_flow >= 0
            ? <TrendingUp className="w-3.5 h-3.5 text-positive-600 dark:text-positive-500" />
            : <TrendingDown className="w-3.5 h-3.5 text-negative-500" />
          }
          <p className="text-xs text-zinc-500 dark:text-zinc-400">Net Akış</p>
        </div>
        <p className={`font-numeric font-bold text-lg ${net_flow >= 0 ? 'text-positive-600 dark:text-positive-400' : 'text-negative-600 dark:text-negative-400'}`}>
          {net_flow > 0 ? '+' : ''}{formatPara(net_flow)}
        </p>
        <p className="text-xs text-zinc-500 mt-0.5">
          <span className="text-positive-600 dark:text-positive-500">+{formatSayi(total_receivable)}</span>
          {' / '}
          <span className="text-negative-500">{formatSayi(total_payable)}</span>
        </p>
      </div>

      {/* Sıkışma günleri */}
      <div className={`card p-4 ${crunch_count > 0 ? 'border-negative-300 dark:border-negative-700/50 bg-negative-50/30 dark:bg-negative-950/20' : ''}`}>
        <div className="flex items-center gap-1.5 mb-2">
          <AlertTriangle className={`w-3.5 h-3.5 ${crunch_count > 0 ? 'text-negative-500' : 'text-zinc-500'}`} />
          <p className="text-xs text-zinc-500 dark:text-zinc-400">Sıkışma Günü</p>
        </div>
        <p className={`font-numeric font-bold text-lg ${crunch_count > 0 ? 'text-negative-600 dark:text-negative-400' : 'text-zinc-500'}`}>
          {crunch_count}
        </p>
        <p className="text-xs text-zinc-500 mt-0.5">
          {crunch_count === 0 ? 'Eşik aşılmıyor' : 'Bakiye eşik altında'}
        </p>
      </div>
    </div>
  );
}