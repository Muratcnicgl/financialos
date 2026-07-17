import { useState, useEffect, useRef } from 'react';
import { Search, X } from 'lucide-react';

const COMMANDS = [
  { id: 'cockpit',      label: 'Cockpit\'e geç',           hint: 'Cmd+1' },
  { id: 'coach',        label: 'Koç\'a geç',               hint: 'Cmd+2' },
  { id: 'accounts',     label: 'Hesaplar\'a geç',          hint: 'Cmd+3' },
  { id: 'transactions', label: 'İşlemler\'e geç',          hint: 'Cmd+4' },
  { id: 'incomedebt',   label: 'Gelir & Borç\'a geç',      hint: 'Cmd+5' },
  { id: 'redlines',     label: 'Kırmızı Çizgiler\'e geç',  hint: 'Cmd+6' },
  { id: 'reports',      label: 'Raporlar\'a geç',           hint: 'Cmd+7' },
  // FE-007: kalan 4 sekme de palette'te aranabilir (Cmd kısayolları yalnız 1-7 bağlı, hint yok).
  { id: 'cashflow',     label: 'Nakit Akışı\'na geç',      hint: '' },
  { id: 'debtstrategy', label: 'Borç Stratejisi\'ne geç',  hint: '' },
  { id: 'goals',        label: 'Hedefler\'e geç',          hint: '' },
  { id: 'budget',       label: 'Bütçe\'ye geç',            hint: '' },
];

export default function CommandPalette({ onClose, setActiveTab }) {
  const [query, setQuery] = useState('');
  const [selectedIdx, setSelectedIdx] = useState(0);
  const inputRef = useRef(null);

  const filtered = query.trim()
    ? COMMANDS.filter(c => c.label.toLowerCase().includes(query.toLowerCase()))
    : COMMANDS;

  useEffect(() => { inputRef.current?.focus(); }, []);
  useEffect(() => { setSelectedIdx(0); }, [query]);

  const execute = (cmd) => {
    setActiveTab(cmd.id);
    onClose();
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') { onClose(); return; }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIdx(i => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIdx(i => Math.max(i - 1, 0));
    } else if (e.key === 'Enter' && filtered[selectedIdx]) {
      execute(filtered[selectedIdx]);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-start justify-center pt-20 px-4 animate-fade-in"
      onClick={onClose}
    >
      <div
        className="card w-full sm:max-w-md overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-4 py-3 border-b border-zinc-200 dark:border-zinc-700">
          <Search className="w-4 h-4 text-zinc-400 flex-shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Komut ara..."
            className="flex-1 bg-transparent outline-none text-sm placeholder-zinc-400 min-h-0"
          />
          <button type="button" onClick={onClose} className="btn btn-ghost btn-icon !p-1 text-zinc-400">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
        <div className="max-h-64 overflow-y-auto py-1">
          {filtered.length === 0 ? (
            <p className="px-4 py-6 text-sm text-zinc-500 text-center">Komut bulunamadı</p>
          ) : (
            filtered.map((cmd, i) => (
              <button
                key={cmd.id}
                onClick={() => execute(cmd)}
                className={`w-full flex items-center justify-between px-4 py-2.5 text-sm text-left transition-colors ${
                  i === selectedIdx
                    ? 'bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-300'
                    : 'hover:bg-zinc-50 dark:hover:bg-zinc-800/50 text-zinc-800 dark:text-zinc-200'
                }`}
              >
                <span>{cmd.label}</span>
                <kbd className="text-[10px] text-zinc-400 font-mono">{cmd.hint}</kbd>
              </button>
            ))
          )}
        </div>
        <div className="px-4 py-2 border-t border-zinc-100 dark:border-zinc-800 text-[10px] text-zinc-400">
          ↑↓ seç · Enter uygula · Esc kapat
        </div>
      </div>
    </div>
  );
}
