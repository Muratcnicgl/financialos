import { useEffect, useId, useRef } from 'react';
import { X } from 'lucide-react';

/**
 * Ortak modal (BUG #395 / A11Y-001, FE-004).
 *
 * Ölçülen: dört panel (Accounts, IncomeDebt, RedLines, Transactions) birbirinin kopyası bir
 * `Modal` sarmalayıcı taşıyordu ve dördü de erişilemezdi — `role="dialog"`, `aria-modal`,
 * başlık bağı, Escape, odak yönetimi yoktu (WCAG 4.1.2 / 2.1.2 / 2.4.3). Kopya sayısı
 * kadar düzeltme yerine tek bileşen: sözleşme burada, dört panel yalnız içe aktarır.
 *
 * Davranış (APG "dialog (modal)"):
 *  - `role="dialog" aria-modal="true" aria-labelledby={başlık}`
 *  - Açılışta odak ilk odaklanabilir öğeye (yoksa kutuya); kapanışta tetikleyene döner.
 *  - Escape kapatır; Tab/Shift+Tab kutunun içinde döner (focus trap).
 *  - Arka plana tıklama kapatır; kutuya tıklama yayılmaz.
 */
const ODAKLANABILIR = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export default function Modal({ title, children, onClose, genislik = 'md' }) {
  const baslikId = useId();
  const kutuRef = useRef(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const tetikleyen = document.activeElement;
    const kutu = kutuRef.current;
    // İlk odak İÇERİĞİN ilk alanına (başlıktaki "Kapat" düğmesine değil): kullanıcı formu
    // doldurmaya gelir. Düğme yine sekme sırasındadır; döngü onu da kapsar.
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
  }, []);

  const maxW = genislik === 'lg' ? 'sm:max-w-lg' : 'sm:max-w-md';
  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-2 sm:p-4 animate-fade-in"
      onClick={() => onCloseRef.current?.()}
    >
      <div
        ref={kutuRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={baslikId}
        tabIndex={-1}
        className={`card p-6 w-full ${maxW} max-h-[90vh] overflow-y-auto outline-none`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 id={baslikId} className="font-semibold">{title}</h3>
          <button type="button" onClick={onClose} className="btn btn-ghost btn-icon !p-1.5" title="Kapat" aria-label="Kapat">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div data-modal-icerik>{children}</div>
      </div>
    </div>
  );
}
