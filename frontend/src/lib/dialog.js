import { useEffect } from 'react';

/**
 * Modal diyalog davranışı (BUG #395/#396 · A11Y-001, APG "dialog (modal)").
 *
 * Bileşenden bağımsız tek kaynak: ortak `Modal` ve kendi düzenini taşıyan diyaloglar
 * (yardım, ufuklar, premortem, komut paleti, hedef, fiyat) aynı davranışı buradan alır.
 *  - Açılışta odak `[data-modal-icerik]` içindeki ilk odaklanabilire, yoksa kutudaki ilk
 *    odaklanabilire, o da yoksa kutuya (`tabIndex={-1}` gerekir).
 *  - Kapanışta odak tetikleyene döner.
 *  - Escape `onClose`; Tab/Shift+Tab kutunun içinde döner.
 * `onClose` kimliği değişse de yeniden bağlanmaz: tek bağımlılık `acik` (isOpen ile kurulan
 * diyaloglar için), güncel kapatıcı her tuşta `onCloseRef` üzerinden okunur — aksi hâlde her
 * render'da odak zıplardı.
 */
export const ODAKLANABILIR = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function useDialog(kutuRef, onCloseRef, acik = true) {
  useEffect(() => {
    if (!acik) return undefined;
    const tetikleyen = document.activeElement;
    const kutu = kutuRef.current;
    const icerik = kutu?.querySelector('[data-modal-icerik]');
    const ilk = icerik?.querySelector(ODAKLANABILIR) || kutu?.querySelector(ODAKLANABILIR);
    (ilk || kutu)?.focus();

    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onCloseRef.current?.();
        return;
      }
      if (e.key !== 'Tab' || !kutu) return;
      const ogeler = [...kutu.querySelectorAll(ODAKLANABILIR)];
      if (ogeler.length === 0) { e.preventDefault(); kutu.focus(); return; }
      const ilkOge = ogeler[0];
      const sonOge = ogeler[ogeler.length - 1];
      if (e.shiftKey && (document.activeElement === ilkOge || !kutu.contains(document.activeElement))) {
        e.preventDefault(); sonOge.focus();
      } else if (!e.shiftKey && document.activeElement === sonOge) {
        e.preventDefault(); ilkOge.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      if (tetikleyen && typeof tetikleyen.focus === 'function') tetikleyen.focus();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [acik]);
}
