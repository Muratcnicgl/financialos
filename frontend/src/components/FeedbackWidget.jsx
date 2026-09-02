import { useState } from 'react';
import { MessageSquarePlus, X, Send, Check, Loader2 } from 'lucide-react';
import { feedbackApi } from '../api.js';

/**
 * FEAT-033 — Uygulama-içi geri bildirim widget'ı (Şikayet / İstek / Öneri).
 * Her ekranda sağ-altta floating buton; tıklayınca basit modal. Kendi başına
 * success/error yönetir (Toast bağımlılığı yok). `page` = aktif sekme (bağlam).
 */
const KINDS = [
  { id: 'sikayet', label: 'Şikayet' },
  { id: 'istek', label: 'İstek' },
  { id: 'oneri', label: 'Öneri' },
  // BUG #281 (B2): "kafa karıştırdı" hata da istek de değildir — KULLANILABİLİRLİK
  // sinyalidir ve kapalı betanın en değerli çıktısıdır. Kullanıcı "bu bozuk mu, ben mi
  // anlamadım" ikilemine düştüğünde başka kutuya sığmaz ve hiç yazmaz.
  { id: 'kafa_karistirdi', label: 'Kafa karıştırdı' },
];

export default function FeedbackWidget({ page, istekId = null, acik = false, onKapat = null }) {
  const [open, setOpen] = useState(acik);
  const [kind, setKind] = useState('oneri');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  function reset() {
    setKind('oneri'); setMessage(''); setSent(false); setError(''); setBusy(false);
  }
  function close() {
    setOpen(false);
    if (onKapat) onKapat();
    setTimeout(reset, 200);
  }

  async function submit(e) {
    e.preventDefault();
    if (!message.trim() || busy) return;
    setBusy(true); setError('');
    try {
      await feedbackApi.create(kind, message.trim(), page, istekId);
      setSent(true);
    } catch (err) {
      setError(err?.message || 'Gönderilemedi, tekrar dene.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-4 right-4 z-40 flex items-center gap-2 rounded-full bg-brand-600 hover:bg-brand-700 text-white px-4 py-3 shadow-lg transition-colors [@media(max-height:500px)]:px-3"
        title="Geri bildirim gönder"
        aria-label="Geri bildirim gönder"
      >
        <MessageSquarePlus className="w-5 h-5 shrink-0" />
        {/* Kisa viewport'ta etiket gizlenir: genis pill, yardim dugmesiyle yan yana durmaya
            yer birakmiyor ve sag kenardaki ortulme seridini buyutuyor. */}
        <span className="hidden sm:inline [@media(max-height:500px)]:hidden text-sm font-medium">Geri Bildirim</span>
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 p-4"
          onClick={close}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="w-full max-w-sm rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 shadow-xl p-5"
            onClick={(e) => e.stopPropagation()}
          >
            {sent ? (
              <div className="text-center py-4">
                <div className="mx-auto w-12 h-12 rounded-full bg-positive-100 dark:bg-positive-900/30 flex items-center justify-center mb-3">
                  <Check className="w-6 h-6 text-positive-600 dark:text-positive-400" />
                </div>
                <p className="font-semibold text-zinc-800 dark:text-zinc-100">Teşekkürler!</p>
                <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
                  Geri bildirimin alındı, incelenecek.
                </p>
                <button
                  onClick={close}
                  className="mt-4 w-full rounded-lg bg-zinc-100 dark:bg-zinc-800 hover:bg-zinc-200 dark:hover:bg-zinc-700 py-2 text-sm font-medium"
                >
                  Kapat
                </button>
              </div>
            ) : (
              <form onSubmit={submit}>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="font-semibold text-zinc-800 dark:text-zinc-100">Geri Bildirim</h3>
                  <button type="button" onClick={close} aria-label="Kapat"
                          className="text-zinc-500 dark:text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200">
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <div className="flex gap-2 mb-3">
                  {KINDS.map((k) => (
                    <button
                      key={k.id}
                      type="button"
                      onClick={() => setKind(k.id)}
                      className={`flex-1 rounded-lg py-1.5 text-sm font-medium border transition-colors ${
                        kind === k.id
                          ? 'bg-brand-600 border-brand-600 text-white'
                          : 'border-zinc-300 dark:border-zinc-600 text-zinc-600 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800'
                      }`}
                    >
                      {k.label}
                    </button>
                  ))}
                </div>

                {istekId && (
                  <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-2"
                     data-testid="feedback-istek-id">
                    Hata kodu{' '}
                    <code className="font-mono font-semibold text-zinc-700 dark:text-zinc-200">
                      {istekId}
                    </code>{' '}
                    bu bildirime eklenecek.
                  </p>
                )}

                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  rows={4}
                  maxLength={4000}
                  autoFocus
                  placeholder="Ne düşünüyorsun? Bir hata, istek veya öneri yaz..."
                  className="w-full rounded-lg border border-zinc-300 dark:border-zinc-600 bg-white dark:bg-zinc-800 px-3 py-2 text-sm text-zinc-800 dark:text-zinc-100 placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-brand-500 resize-none"
                />

                {error && (
                  <p className="text-xs text-negative-600 dark:text-negative-400 mt-1.5">{error}</p>
                )}

                <button
                  type="submit"
                  disabled={!message.trim() || busy}
                  className="mt-3 w-full flex items-center justify-center gap-2 rounded-lg bg-brand-600 hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed text-white py-2 text-sm font-medium transition-colors"
                >
                  {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                  Gönder
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </>
  );
}
