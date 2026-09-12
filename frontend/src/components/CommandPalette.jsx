import { useState, useEffect, useRef, useMemo } from 'react';
import { useDialog } from '../lib/dialog.js';
import { Search, X } from 'lucide-react';
import { SEKMELER, kisayolSirasi } from '../lib/sekmeler.js';

/**
 * Komut paleti. Liste artık `lib/sekmeler.js`'ten türer.
 *
 * Eski hâlde komutlar elle yazılıydı ve 13 sekmenin YALNIZ 11'i vardı: "Aile" ve
 * "Hesap" panellerine Cmd+K ile hiç ulaşılamıyordu. Kısayol etiketleri (Cmd+1..) de
 * elle sayılmıştı; sıra moda göre değiştiği için artık hesaplanıyor.
 *
 * Palet BİLEREK her iki modda da TÜM panelleri listeler: sade görünüm sekme çubuğunu
 * kısaltır, panelleri silmez. Aramayı bilen kullanıcı sadeliği kaybetmeden derine
 * inebilir — ve palette bir de görünümü değiştiren komut vardır.
 */
function komutlar(basit, onModDegistir) {
  const sira = kisayolSirasi(basit);
  const liste = SEKMELER.map((s) => {
    const i = sira.indexOf(s.id);
    return {
      id: s.id,
      label: s.komut,
      hint: i >= 0 && i < 9 ? `Cmd+${i + 1}` : '',
      calistir: (setActiveTab) => setActiveTab(s.id),
    };
  });
  if (onModDegistir) {
    liste.push({
      id: 'gorunum-modu',
      label: basit ? 'Görünümü detaylıya çevir' : 'Görünümü sadeye çevir',
      hint: '',
      calistir: () => onModDegistir(),
    });
  }
  return liste;
}

export default function CommandPalette({ onClose, setActiveTab, basit = false, onModDegistir }) {
  const [query, setQuery] = useState('');
  const [selectedIdx, setSelectedIdx] = useState(0);
  const inputRef = useRef(null);

  const COMMANDS = useMemo(() => komutlar(basit, onModDegistir), [basit, onModDegistir]);

  const filtered = query.trim()
    ? COMMANDS.filter(c => c.label.toLowerCase().includes(query.toLowerCase()))
    : COMMANDS;

  // BUG #396 (A11Y-001): rol + odak/Escape/Tab döngüsü tek kaynaktan; ilk odak zaten arama kutusu.
  const kutuRef = useRef(null);
  const onCloseRef = useRef(onClose); onCloseRef.current = onClose;
  useDialog(kutuRef, onCloseRef);
  useEffect(() => { setSelectedIdx(0); }, [query]);

  const execute = (cmd) => {
    cmd.calistir(setActiveTab);
    onClose();
  };

  const handleKeyDown = (e) => {
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
        ref={kutuRef} role="dialog" aria-modal="true" aria-label="Komut paleti" tabIndex={-1}
        className="card w-full sm:max-w-md overflow-hidden outline-none"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-4 py-3 border-b border-zinc-200 dark:border-zinc-700">
          <Search className="w-4 h-4 text-zinc-500 dark:text-zinc-400 flex-shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Komut ara..."
            aria-label="Komut ara"
            className="flex-1 bg-transparent outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded text-sm placeholder-zinc-400 min-h-0"
          />
          <button type="button" onClick={onClose} aria-label="Kapat" className="btn btn-ghost btn-icon !p-1 text-zinc-500 dark:text-zinc-400">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
        <div className="max-h-80 overflow-y-auto py-1">
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
                <kbd className="text-[10px] text-zinc-500 dark:text-zinc-400 font-mono">{cmd.hint}</kbd>
              </button>
            ))
          )}
        </div>
        <div className="px-4 py-2 border-t border-zinc-100 dark:border-zinc-800 text-[10px] text-zinc-500 dark:text-zinc-400">
          ↑↓ seç · Enter uygula · Esc kapat
        </div>
      </div>
    </div>
  );
}
