/**
 * Onboarding karti (H20 / BUG #194).
 *
 * Yeni kullanici bombos bir ekranla karsilasiyordu: ne yapacagini anlamak icin
 * panelleri tek tek gezmek zorundaydi. Bu kart YALNIZ veri yokken gorunur; iki yol sunar:
 *   1) kendi hesabini ekle (gercek kullanim),
 *   2) ornek veriyle gez (tek tusla TAM silinebilir — kullanicinin kendi verisine dokunmaz).
 *
 * Demo veri jeneriktir (kisi adi/banka markasi yok — BUG #166/#168 ailesi).
 */
import { useState, useEffect } from 'react';
import { Sparkles, Trash2, Loader2, ArrowRight } from 'lucide-react';
import { onboardingApi } from '../api.js';

export default function Onboarding({ bosMu, onDegisti }) {
  const [durum, setDurum] = useState(null);
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState(null);

  useEffect(() => {
    onboardingApi.durum().then(setDurum).catch(() => setDurum(null));
  }, []);

  const calistir = async (fn) => {
    setBusy(true); setHata(null);
    try {
      const d = await fn();
      setDurum(d);
      onDegisti?.();
    } catch (e) {
      setHata(e.message || 'İşlem başarısız');
    } finally {
      setBusy(false);
    }
  };

  // Demo yükl��yse: kaldırma seçeneğini her zaman göster (kullanıcı kilitlenmesin)
  if (durum?.yuklu) {
    return (
      <div className="rounded-xl border border-amber-300/60 bg-amber-50 dark:bg-amber-950/20
                      dark:border-amber-700/40 p-3 flex items-center justify-between gap-3">
        <p className="text-xs text-amber-800 dark:text-amber-300">
          <strong>Örnek veri</strong> yüklü ({durum.satir_sayisi} kayıt). Kendi verini
          girmeye başladığında bunu kaldırabilirsin — <strong>yalnız örnek kayıtlar</strong> silinir.
        </p>
        <button onClick={() => calistir(onboardingApi.kaldir)} disabled={busy}
                className="btn btn-secondary flex-shrink-0">
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
          Örnek veriyi kaldır
        </button>
      </div>
    );
  }

  if (!bosMu) return null;   // verisi olan kullanıcıyı rahatsız etme

  return (
    <div className="rounded-xl border border-brand-300/60 dark:border-brand-700/40
                    bg-brand-50 dark:bg-brand-950/20 p-4 space-y-3">
      <div className="flex items-start gap-3">
        <Sparkles className="w-5 h-5 text-brand-600 dark:text-brand-400 flex-shrink-0 mt-0.5" />
        <div>
          <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">Hoş geldin — buradan başla</h3>
          <p className="text-xs text-zinc-600 dark:text-zinc-400 mt-1">
            FinancialOS senin girdiğin verilerle çalışır; banka bağlantısı yoktur.
            Sırasıyla: <strong>hesap ekle</strong> → <strong>işlem gir</strong> →
            <strong> kendi kuralını yaz</strong> (kural gerçekten uygulanır) → koça sor.
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <a href="#accounts" className="btn btn-primary">
          Kendi hesabımı ekle <ArrowRight className="w-4 h-4" />
        </a>
        <button onClick={() => calistir(onboardingApi.yukle)} disabled={busy}
                className="btn btn-secondary">
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
          Örnek veriyle gez
        </button>
      </div>

      <p className="text-[10px] text-zinc-500">
        Örnek veri tek tuşla tamamen kaldırılır ve senin girdiğin kayıtlara dokunmaz.
      </p>
      {hata && <p className="text-xs text-negative-600 dark:text-negative-400">{hata}</p>}
    </div>
  );
}
