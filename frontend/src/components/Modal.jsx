import { useId, useRef } from 'react';
import { X } from 'lucide-react';
import { useDialog } from '../lib/dialog.js';

/**
 * Ortak modal (BUG #395 / A11Y-001, FE-004).
 *
 * Ölçülen: dört panel (Accounts, IncomeDebt, RedLines, Transactions) birbirinin kopyası bir
 * `Modal` sarmalayıcı taşıyordu ve dördü de erişilemezdi — `role="dialog"`, `aria-modal`,
 * başlık bağı, Escape, odak yönetimi yoktu (WCAG 4.1.2 / 2.1.2 / 2.4.3). Kopya sayısı
 * kadar düzeltme yerine tek bileşen: sözleşme burada, dört panel yalnız içe aktarır.
 *
 * Davranış `lib/dialog.js` `useDialog`ta (BUG #396: kendi düzenini taşıyan diyaloglar da
 * aynı kaynağı kullanır): rol/aria-modal/başlık bağı burada, odak/Escape/Tab döngüsü orada.
 * Arka plana tıklama kapatır; kutuya tıklama yayılmaz.
 */
export default function Modal({ title, children, onClose, genislik = 'md' }) {
  const baslikId = useId();
  const kutuRef = useRef(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useDialog(kutuRef, onCloseRef);

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
