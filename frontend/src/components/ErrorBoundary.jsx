import { Component } from 'react';
import { AlertTriangle, RefreshCw, MessageSquarePlus } from 'lucide-react';
import FeedbackWidget from './FeedbackWidget.jsx';

/**
 * FE-003: Global hata sınırı. Bir panel render sırasında çökerse (ör. beklenmedik veri
 * şekli, yeni bir bileşendeki bug) TÜM uygulama beyaz ekrana düşmesin — sınırlı, açıklamalı
 * bir hata kartı gösterilir ve kullanıcı yeniden deneyebilir/sekme değiştirebilir.
 *
 * `resetKey` değişince (ör. aktif sekme) sınır kendini sıfırlar → farklı panele geçince
 * takılı kalmaz.
 *
 * BUG #280 (B3): hata bir sunucu isteğinden geliyorsa (ApiError) korelasyon kimliği
 * KULLANICIYA gösterilir — davetli "şu kod çıktı" der, operatör aynı kodu log'da ve
 * `error_logs`'ta bulur. Saf istemci çökmesinde kod GÖSTERİLMEZ: o çökme sunucuya hiç
 * uğramamıştır, uydurulmuş bir kod hiçbir kayda karşılık gelmez ve kullanıcıyı da
 * operatörü de yanıltır (L33 — prompt'ta/ekranda verilen vaat, sistemde verilmiş değildir).
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, bildirimAcik: false };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    // Konsola yaz — tanılanabilir olsun (üretimde bir gözlemlenebilirlik hook'una bağlanabilir).
    // eslint-disable-next-line no-console
    console.error('Panel çöktü (ErrorBoundary):', error, info?.componentStack);
  }

  componentDidUpdate(prevProps) {
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false, error: null });
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="card p-6 text-center border-negative-200 dark:border-negative-800/50">
          <AlertTriangle className="w-10 h-10 mx-auto text-negative-500 mb-3" />
          <h3 className="text-lg font-semibold text-zinc-800 dark:text-zinc-100 mb-1">
            Bu panel yüklenemedi
          </h3>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
            Beklenmedik bir sorun oldu. Verilerin güvende — başka bir sekmeye geçebilir ya da
            yeniden deneyebilirsin.
          </p>
          {this.state.error?.istekId && (
            <p
              className="text-xs text-zinc-500 dark:text-zinc-400 mb-4"
              data-testid="korelasyon-kimligi"
            >
              Bildirirken şu kodu yaz:{' '}
              <code className="font-mono font-semibold text-zinc-700 dark:text-zinc-200">
                {this.state.error.istekId}
              </code>
            </p>
          )}
          <div className="flex flex-wrap items-center justify-center gap-2">
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="btn btn-secondary !text-xs"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              Yeniden dene
            </button>
            {/* BUG #281 (B2): hatadan geri bildirime TEK TIK. Kullanıcı hatayı gördüğü
                anda bildirebilmeli; "sonra widget'ı bul" demek pratikte bildirmemektir —
                ve kod da o an ekranda, sonra kaybolur. */}
            <button
              onClick={() => this.setState({ bildirimAcik: true })}
              className="btn btn-secondary !text-xs"
              data-testid="hatadan-bildir"
            >
              <MessageSquarePlus className="w-3.5 h-3.5" />
              Bunu bildir
            </button>
          </div>
          {this.state.bildirimAcik && (
            <FeedbackWidget
              page="hata"
              istekId={this.state.error?.istekId || null}
              acik
              onKapat={() => this.setState({ bildirimAcik: false })}
            />
          )}
        </div>
      );
    }
    return this.props.children;
  }
}
