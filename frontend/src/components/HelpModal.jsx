import { useEffect } from 'react';
import { X } from 'lucide-react';
import { SEKMELER, gorunurSekmeler, sekmeEtiketi } from '../lib/sekmeler.js';
import { useGorunumModu } from '../hooks/useGorunumModu.js';

/**
 * Klavye kısayolları ekranı.
 *
 * Panel kısayolları artık ELLE YAZILMIYOR: liste `lib/sekmeler.js`'ten, sıra da aktif
 * görünüm modundan gelir. Eski hâl bir belge-kod ayrışmasıydı — tablo "Cmd+6 → Kırmızı
 * Çizgiler" diyor, alt not "Cmd+1..6 her zaman aktif" diyor, kod ise 1..9'u bağlıyordu.
 * Sade görünümde kısayollar görünen sekmelere bağlandığı için bu ekran da moda uymalı;
 * yoksa yardım ekranı yanlış şeyi öğretir.
 */
const SABIT_KISAYOLLAR = [
  { key: '?',                label: 'Bu yardım ekranı' },
  { key: 'Y',                label: 'Bekleyen aksiyonu onayla' },
  { key: 'N',                label: 'Bekleyen aksiyonu reddet' },
  { key: 'E',                label: 'Bekleyen aksiyonu düzenle' },
  { key: 'Enter',            label: 'Koç mesajını gönder' },
  { key: 'Shift + Enter',    label: 'Koç mesajında yeni satır' },
  { key: 'Esc',              label: 'Modal / paleti kapat' },
];

export default function HelpModal({ onClose }) {
  const { basit } = useGorunumModu();
  const panelKisayollari = gorunurSekmeler(basit)
    .slice(0, 9)
    .map((s, i) => ({ key: `Cmd/Ctrl + ${i + 1}`, label: sekmeEtiketi(s, basit) }));
  const SHORTCUTS = [
    { key: 'Cmd/Ctrl + K', label: 'Komut paleti aç / kapat' },
    ...panelKisayollari,
    ...SABIT_KISAYOLLAR,
  ];
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-start justify-center pt-20 px-4 animate-fade-in"
      onClick={onClose}
    >
      <div
        className="card p-6 w-full sm:max-w-md max-h-[70vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">Klavye Kısayolları</h3>
          <button type="button" onClick={onClose} className="btn btn-ghost btn-icon !p-1.5" title="Kapat" aria-label="Kapat">
            <X className="w-4 h-4" />
          </button>
        </div>
        <table className="w-full text-sm">
          <tbody>
            {SHORTCUTS.map(({ key, label }) => (
              <tr key={key} className="border-b border-zinc-100 dark:border-zinc-800 last:border-0">
                <td className="py-2 pr-4 whitespace-nowrap">
                  <kbd className="px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-xs font-mono border border-zinc-300 dark:border-zinc-700">
                    {key}
                  </kbd>
                </td>
                <td className="py-2 text-zinc-600 dark:text-zinc-400">{label}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-[11px] text-zinc-500 dark:text-zinc-400 mt-4">
          Y/N/E → input dışındayken bekleyen aksiyona uygulanır ·
          Cmd+1..{panelKisayollari.length} → her zaman aktif
          {basit && SEKMELER.length > panelKisayollari.length
            && ` · sade görünümde ${SEKMELER.length - panelKisayollari.length} panel Cmd+K ile aranır`}
        </p>
      </div>
    </div>
  );
}
