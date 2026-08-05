import { createContext, useContext, useState, useCallback, useEffect, useMemo } from 'react';
import { CheckCircle, AlertTriangle, Info, AlertCircle, X } from 'lucide-react';

/**
 * Toast notification altyapisi.
 *
 * Kullanim:
 *   const toast = useToast();
 *   toast.success('Kart kapatildi');
 *   toast.error('Hata olustu', { detail: 'Backend offline' });
 *   toast.info('Cockpit guncellendi');
 *   toast.warning('Limit asildi');
 *
 * Ozellikler:
 *  - 4 tip: success / error / info / warning
 *  - Sag ust kosede yiginlanir (max 3, fazlasi sirada bekler)
 *  - 4 saniye sonra otomatik kaybolur (manuel X ile de)
 *  - Slide-in / fade-out animasyon
 *  - Lucide ikon + tip rengi
 *
 * GUNCELLEMELER
 *  - BUG #218 fix (P3.2): context degeri (`api`) her render'da yeniden yaratiliyordu.
 *    Bir toast gosterilince provider re-render olur, `toast` kimligi degisir ve
 *    `useCallback(..., [toast])` + ona bagli `useEffect` TEKRAR kosar. Istek hata verip
 *    toast.error() cagiran panel boylece SONSUZ ISTEK DONGUSUNE giriyordu (olculdu:
 *    Aile paneli 150 ms'de 54 istek). Deger artik useMemo ile sabit.
 */

const ToastContext = createContext(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}

let toastIdCounter = 0;
const MAX_VISIBLE = 3;
const DURATION_MS = 4000;

const TYPE_META = {
  success: {
    icon: CheckCircle,
    bgClass: 'bg-positive-50 dark:bg-positive-950/40',
    borderClass: 'border-positive-200 dark:border-positive-800',
    iconClass: 'text-positive-600 dark:text-positive-400',
    titleClass: 'text-positive-700 dark:text-positive-300',
  },
  error: {
    icon: AlertCircle,
    bgClass: 'bg-negative-50 dark:bg-negative-950/40',
    borderClass: 'border-negative-200 dark:border-negative-800',
    iconClass: 'text-negative-600 dark:text-negative-400',
    titleClass: 'text-negative-700 dark:text-negative-300',
  },
  info: {
    icon: Info,
    bgClass: 'bg-brand-50 dark:bg-brand-950/40',
    borderClass: 'border-brand-200 dark:border-brand-800',
    iconClass: 'text-brand-600 dark:text-brand-400',
    titleClass: 'text-brand-700 dark:text-brand-300',
  },
  warning: {
    icon: AlertTriangle,
    bgClass: 'bg-warn-50 dark:bg-warn-950/40',
    borderClass: 'border-warn-200 dark:border-warn-800',
    iconClass: 'text-warn-600 dark:text-warn-400',
    titleClass: 'text-warn-700 dark:text-warn-300',
  },
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const dismiss = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const show = useCallback((type, title, options = {}) => {
    const id = ++toastIdCounter;
    const { detail = null, duration = DURATION_MS } = options;
    setToasts(prev => [...prev, { id, type, title, detail, duration }]);
    if (duration > 0) {
      setTimeout(() => dismiss(id), duration);
    }
    return id;
  }, [dismiss]);

  // BUG #218 fix: context degeri MEMOIZE edilmeli. Eskiden `api` her render'da yeniden
  // yaratiliyordu; bir toast gosterilince provider re-render olur, `toast` kimligi degisir,
  // `useCallback(..., [toast])` yenilenir ve ona bagli `useEffect` TEKRAR kosardi. Istek
  // hata verip toast.error() cagiran her panel boylece sonsuz istek dongusune giriyordu
  // (Workspace paneli olcum: 150 ms'de 54 istek, bitmiyor). show/dismiss zaten sabit.
  const api = useMemo(() => ({
    success: (title, options) => show('success', title, options),
    error: (title, options) => show('error', title, options),
    info: (title, options) => show('info', title, options),
    warning: (title, options) => show('warning', title, options),
    dismiss,
  }), [show, dismiss]);

  // Sadece son MAX_VISIBLE goster
  const visible = toasts.slice(-MAX_VISIBLE);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <ToastContainer toasts={visible} onDismiss={dismiss} />
    </ToastContext.Provider>
  );
}

function ToastContainer({ toasts, onDismiss }) {
  if (toasts.length === 0) return null;
  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 max-w-sm w-[calc(100%-2rem)] sm:w-auto sm:min-w-[320px] pointer-events-none">
      {toasts.map(t => (
        <ToastItem key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  );
}

function ToastItem({ toast, onDismiss }) {
  const meta = TYPE_META[toast.type] || TYPE_META.info;
  const Icon = meta.icon;
  const [exiting, setExiting] = useState(false);

  // Cikis animasyonu (eger duration ile auto-dismiss zamani yaklassa)
  useEffect(() => {
    if (toast.duration > 0) {
      const exitTimer = setTimeout(() => setExiting(true), toast.duration - 300);
      return () => clearTimeout(exitTimer);
    }
  }, [toast.duration]);

  const handleClose = () => {
    setExiting(true);
    setTimeout(() => onDismiss(toast.id), 200);
  };

  return (
    <div
      className={`pointer-events-auto card border-2 ${meta.bgClass} ${meta.borderClass} p-3 shadow-lg ${
        exiting ? 'animate-toast-out' : 'animate-toast-in'
      }`}
      role="status"
    >
      <div className="flex items-start gap-3">
        <Icon className={`w-5 h-5 flex-shrink-0 mt-0.5 ${meta.iconClass}`} />
        <div className="flex-1 min-w-0">
          <p className={`text-sm font-semibold ${meta.titleClass}`}>
            {toast.title}
          </p>
          {toast.detail && (
            <p className="text-xs text-zinc-700 dark:text-zinc-300 mt-1 break-words">
              {toast.detail}
            </p>
          )}
        </div>
        <button
          onClick={handleClose}
          className="flex-shrink-0 text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition-colors"
          title="Kapat"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}