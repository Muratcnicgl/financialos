import { useId, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { fundPriceApi, parseTRNumber } from '../api.js';

/**
 * Tazelik satırında satır içi fiyat girişi — UX-032 (BUG #470).
 * Modal açmadan: kutuya yaz, Enter — `fundPriceApi.update` aynı uç. Boş/geçersiz sayı
 * gönderilmez; hata inline ve role=alert; başarıda ebeveyn yeniler. Emanet hesaplarda
 * da fiyat güncellenebilir (fiyat piyasa verisidir, para hareketi değil).
 */
export default function SatirIciFiyat({ accountId, name, onUpdated }) {
  const [deger, setDeger] = useState('');
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState(null);
  const id = useId();
  const [tamam, setTamam] = useState(false);

  const gonder = async (e) => {
    e.preventDefault();
    const fiyat = parseTRNumber(deger);
    if (!Number.isFinite(fiyat) || fiyat <= 0) { setHata('Geçerli bir fiyat gir'); return; }
    setBusy(true); setHata(null);
    try {
      await fundPriceApi.update(accountId, fiyat);
      setDeger('');
      setTamam(true);   // toast yok: bileşen ToastProvider'sız bağlamda da (test/kokpit) çalışsın
      setTimeout(() => setTamam(false), 2500);
      onUpdated?.();
    } catch (err) {
      setHata(err.message || 'Güncellenemedi');
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={gonder} className="flex items-center gap-1" data-testid="satir-ici-fiyat">
      <label htmlFor={id} className="sr-only">{name} yeni fiyat</label>
      <input id={id} type="text" inputMode="decimal" value={deger} onChange={(e) => setDeger(e.target.value)}
             placeholder="fiyat" disabled={busy} aria-invalid={hata ? true : undefined} aria-describedby={hata ? `${id}-hata` : undefined}
             className="input !text-xs !py-0.5 !min-h-[32px] w-24 font-numeric" />
      <button type="submit" disabled={busy || !deger.trim()} className="btn btn-secondary !text-xs !px-2 !min-h-[32px]" aria-busy={busy}>
        {busy && <Loader2 className="w-3 h-3 animate-spin" aria-hidden="true" />}Kaydet
      </button>
      {hata && <span id={`${id}-hata`} role="alert" className="text-[11px] text-negative-600 dark:text-negative-400">{hata}</span>}
      {tamam && <span role="status" className="text-[11px] text-positive-600 dark:text-positive-400">Güncellendi</span>}
    </form>
  );
}
