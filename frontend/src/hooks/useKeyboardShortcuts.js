import { useEffect } from 'react';
import { kisayolSirasi } from '../lib/sekmeler.js';

// Sekme listesi burada KOPYALANMIYOR: tek kaynak `lib/sekmeler.js`. Eski hâlde 11 id
// elle yazılıydı ve App'teki 13 sekmeyle ayrışmıştı (workspace/hesap kısayolsuzdu).
// Sıra görünüm moduna göre değişir; çağıran geçmezse detaylı sıra varsayılır.

function isInputFocused() {
  const tag = document.activeElement?.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
}

/**
 * Global klavye kısayolları hook'u.
 *
 * Aktif kısayollar:
 *   Cmd/Ctrl+K       → komut paleti aç/kapat
 *   Cmd/Ctrl+1..9    → GÖRÜNEN panellerin sırasına göre panel değiştir
 *   ?                → yardım modalı aç/kapat (input focus'tayken pasif)
 *   Esc              → açık modal/paletleri kapat (her component kendi Esc'ini yönetir)
 */
export function useKeyboardShortcuts({ setActiveTab, onHelp, onPalette, sekmeIdleri }) {
  useEffect(() => {
    const handler = (e) => {
      const ctrl = e.ctrlKey || e.metaKey;

      // Cmd/Ctrl+K → komut paleti (her durumda aktif)
      if (ctrl && e.key === 'k') {
        e.preventDefault();
        onPalette();
        return;
      }

      // Cmd/Ctrl+1..9 → panel geçişi (input focus'tayken de aktif).
      // Sade görünümde yalnız görünen sekmeler bağlanır: kullanıcıyı çubukta olmayan
      // bir panele ışınlayan kısayol, aktif sekmesi görünmeyen bir arayüz bırakır.
      if (ctrl && e.key >= '1' && e.key <= '9') {
        e.preventDefault();
        const idx = parseInt(e.key, 10) - 1;
        const idler = sekmeIdleri?.length ? sekmeIdleri : kisayolSirasi(false);
        if (idler[idx]) setActiveTab(idler[idx]);
        return;
      }

      // Aşağıdakiler input/textarea focus'tayken pasif
      if (isInputFocused()) return;

      // ? → yardım modalı
      if (e.key === '?') {
        e.preventDefault();
        onHelp();
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [setActiveTab, onHelp, onPalette, sekmeIdleri]);
}
