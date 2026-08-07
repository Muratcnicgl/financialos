/**
 * Ilk kurulum rehberi + istege bagli demo veri (H20 / H5).
 *
 * BUG #194: yeni kullanici bombos bir ekranla karsilasiyordu.
 * BUG #262 (P3.3) — iki defekt kapatildi:
 *   (a) Rehber ILK ADIMDAN SONRA KAYBOLUYORDU: kart yalniz `accounts.length === 0` iken
 *       ciziliyordu, yani kullanici ilk hesabini ekler eklemez kalan uc adim (islem gir →
 *       kendi kuralini yaz → koca sor) hic yonlendirilmiyordu. Kart bir cumleydi, rehber degildi.
 *   (b) Birincil dugme OLUYDU: `<a href="#accounts">` — uygulama hash-router kullanmiyor
 *       (`App.jsx` `activeTab` state'i). Tarayici hata vermez, suit yesil kalir (L28).
 *
 * Adimin "tamam" olup olmadigi bir VERI sorusudur, arayuz sorusu degil: karar
 * `GET /api/onboarding/rehber`'de tek kaynakta, bu bilesen yalniz cizer (ADR-001 ruhu).
 * Demo veri adimlari tamam SAYMAZ — "ornek veriyle gez" diyen kullanici kendi kurulumuna
 * henuz baslamamistir.
 */
import { useState, useEffect, useCallback } from 'react';
import { Sparkles, Trash2, Loader2, ArrowRight, Check, EyeOff } from 'lucide-react';
import { onboardingApi } from '../api.js';

export default function Onboarding({ setActiveTab, onDegisti }) {
  const [rehber, setRehber] = useState(null);
  const [demo, setDemo] = useState(null);
  const [busy, setBusy] = useState(false);
  const [hata, setHata] = useState(null);

  const yukle = useCallback(() => {
    onboardingApi.rehber().then(setRehber).catch(() => setRehber(null));
    onboardingApi.durum().then(setDemo).catch(() => setDemo(null));
  }, []);

  useEffect(() => { yukle(); }, [yukle]);

  const calistir = async (fn) => {
    setBusy(true); setHata(null);
    try {
      await fn();
      yukle();
      onDegisti?.();
    } catch (e) {
      setHata(e.message || 'İşlem başarısız');
    } finally {
      setBusy(false);
    }
  };

  const git = (sekme) => {
    if (setActiveTab) setActiveTab(sekme);
    else window.location.hash = sekme;   // setActiveTab geçilmediyse en azından iz bırak
  };

  // Demo yüklüyse: kaldırma seçeneği HER ZAMAN görünür (kullanıcı kilitlenmesin) —
  // rehber gizlenmiş ya da bitmiş olsa bile.
  const demoSeridi = demo?.yuklu ? (
    <div className="rounded-xl border border-amber-300/60 bg-amber-50 dark:bg-amber-950/20
                    dark:border-amber-700/40 p-3 flex items-center justify-between gap-3">
      <p className="text-xs text-amber-800 dark:text-amber-300">
        <strong>Örnek veri</strong> yüklü ({demo.satir_sayisi} kayıt). Kendi verini
        girmeye başladığında bunu kaldırabilirsin — <strong>yalnız örnek kayıtlar</strong> silinir.
      </p>
      <button onClick={() => calistir(onboardingApi.kaldir)} disabled={busy}
              className="btn btn-secondary flex-shrink-0">
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
        Örnek veriyi kaldır
      </button>
    </div>
  ) : null;

  if (!rehber?.gorunur) return demoSeridi;

  const { adimlar, tamamlanan, toplam } = rehber;
  const yuzde = Math.round((tamamlanan / toplam) * 100);

  return (
    <div className="space-y-3">
      {demoSeridi}

      <div className="rounded-xl border border-brand-300/60 dark:border-brand-700/40
                      bg-brand-50 dark:bg-brand-950/20 p-4 space-y-3">
        <div className="flex items-start gap-3">
          <Sparkles className="w-5 h-5 text-brand-600 dark:text-brand-400 flex-shrink-0 mt-0.5" />
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-semibold text-zinc-900 dark:text-zinc-100">
                Hoş geldin — buradan başla
              </h3>
              <span className="text-xs font-medium text-brand-700 dark:text-brand-300 flex-shrink-0"
                    data-testid="rehber-ilerleme">
                {tamamlanan}/{toplam} adım
              </span>
            </div>
            <p className="text-xs text-zinc-600 dark:text-zinc-400 mt-1">
              FinancialOS senin girdiğin verilerle çalışır; banka bağlantısı yoktur.
            </p>
            {/* Recharts yerine CSS ilerleme çubuğu (BUG #059) */}
            <div className="h-1.5 mt-2 rounded-full bg-brand-200/60 dark:bg-brand-900/50
                            overflow-hidden" role="presentation">
              <div className="h-full bg-brand-500 dark:bg-brand-400 transition-all"
                   style={{ width: `${yuzde}%` }} />
            </div>
          </div>
        </div>

        <ol className="space-y-1.5">
          {adimlar.map((adim, i) => (
            <li key={adim.anahtar}
                data-testid={`rehber-adim-${adim.anahtar}`}
                data-tamam={adim.tamam ? '1' : '0'}
                className="flex items-start gap-3 rounded-lg px-2 py-1.5
                           odd:bg-white/40 dark:odd:bg-black/10">
              <span className={`w-5 h-5 mt-0.5 rounded-full flex items-center justify-center
                                text-[11px] font-semibold flex-shrink-0 ${
                adim.tamam
                  ? 'bg-positive-500 text-white'
                  : 'bg-zinc-200 dark:bg-zinc-700 text-zinc-600 dark:text-zinc-300'}`}>
                {adim.tamam ? <Check className="w-3 h-3" /> : i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <p className={`text-sm font-medium ${adim.tamam
                  ? 'text-zinc-500 dark:text-zinc-500 line-through'
                  : 'text-zinc-900 dark:text-zinc-100'}`}>
                  {adim.baslik}
                </p>
                {!adim.tamam && (
                  <p className="text-xs text-zinc-600 dark:text-zinc-400">{adim.aciklama}</p>
                )}
              </div>
              {!adim.tamam && (
                <button type="button" onClick={() => git(adim.sekme)}
                        className="btn btn-secondary !text-xs flex-shrink-0">
                  Git <ArrowRight className="w-3.5 h-3.5" />
                </button>
              )}
            </li>
          ))}
        </ol>

        <div className="flex flex-wrap items-center gap-2 pt-1">
          {!demo?.yuklu && (
            <button onClick={() => calistir(onboardingApi.yukle)} disabled={busy}
                    className="btn btn-secondary">
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              Örnek veriyle gez
            </button>
          )}
          <button type="button" disabled={busy}
                  onClick={() => calistir(() => onboardingApi.rehberGizle(true))}
                  className="btn btn-ghost !text-xs">
            <EyeOff className="w-3.5 h-3.5" /> Rehberi gizle
          </button>
          <span className="text-[10px] text-zinc-500">
            Gizlersen Hesap sekmesinden geri açabilirsin.
          </span>
        </div>

        {hata && <p className="text-xs text-negative-600 dark:text-negative-400">{hata}</p>}
      </div>
    </div>
  );
}
