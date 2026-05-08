import { useEffect } from 'react';

const TAB_IDS = ['cockpit', 'coach', 'accounts', 'transactions', 'incomedebt', 'redlines'];

function isInputFocused() {
  const tag = document.activeElement?.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT';
}

/**
 * Global klavye kısayolları hook'u.
 *
 * Aktif kısayollar:
 *   Cmd/Ctrl+K       → komut paleti aç/kapat
 *   Cmd/Ctrl+1..6    → panel değiştir (input focus'tayken de çalışır)
 *   ?                → yardım modalı aç/kapat (input focus'tayken pasif)
 *   Esc              → açık modal/paletleri kapat (her component kendi Esc'ini yönetir)
 */
export function useKeyboardShortcuts({ setActiveTab, onHelp, onPalette }) {
  useEffect(() => {
    const handler = (e) => {
      const ctrl = e.ctrlKey || e.metaKey;

      // Cmd/Ctrl+K → komut paleti (her durumda aktif)
      if (ctrl && e.key === 'k') {
        e.preventDefault();
        onPalette();
        return;
      }

      // Cmd/Ctrl+1..6 → panel geçişi (input focus'tayken de aktif)
      if (ctrl && e.key >= '1' && e.key <= '6') {
        e.preventDefault();
        const idx = parseInt(e.key, 10) - 1;
        if (TAB_IDS[idx]) setActiveTab(TAB_IDS[idx]);
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
  }, [setActiveTab, onHelp, onPalette]);
}
