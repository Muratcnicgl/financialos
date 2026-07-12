import { Component } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

/**
 * FE-003: Global hata sınırı. Bir panel render sırasında çökerse (ör. beklenmedik veri
 * şekli, yeni bir bileşendeki bug) TÜM uygulama beyaz ekrana düşmesin — sınırlı, açıklamalı
 * bir hata kartı gösterilir ve kullanıcı yeniden deneyebilir/sekme değiştirebilir.
 *
 * `resetKey` değişince (ör. aktif sekme) sınır kendini sıfırlar → farklı panele geçince
 * takılı kalmaz.
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
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
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="btn btn-secondary !text-xs mx-auto"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Yeniden dene
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
