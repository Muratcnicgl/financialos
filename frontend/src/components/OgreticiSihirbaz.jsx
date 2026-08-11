/**
 * KURULUM SİHİRBAZI — ilk girişte açılan, ZORUNLU OLMAYAN öğretici.
 *
 * Tasarım kararları (ve nedenleri):
 *  - İçerik `lib/ogretici.js`'te; bu bileşen yalnız çizer ve gezinir.
 *  - "Yaptım mı?" sorusunun cevabı BACKEND'den gelir (`GET /api/onboarding/rehber` →
 *    `adimlar[].tamam`). Sihirbaz kendi sayacını tutmaz: BUG #262'nin dersi, adım
 *    durumunun bir VERİ sorusu olduğu — arayüzün hafızası değil.
 *  - Kapatmak her adımda mümkün ve KAYIPSIZ: kapatınca ilerleme silinmez, yardım
 *    köşesinden kaldığı yerden açılır. Zorunlu sihirbaz, ilk günü bir engele çevirir.
 *  - "Şimdi yap" kullanıcıyı ilgili panele götürür ve sihirbazı kapatır — arkasında
 *    modal bekleten bir akış, kullanıcıyı iki kez düşünmeye zorlar.
 *  - Klavye: Esc kapatır, ← → adım değiştirir. Odak modala hapsedilmez (kullanıcı
 *    arkadaki paneli okumak isteyebilir) ama açılışta ilk düğmeye odaklanır.
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { X, ArrowRight, ArrowLeft, Check, Loader2, Sparkles } from 'lucide-react';
import { SIHIRBAZ_ADIMLARI } from '../lib/ogretici.js';
import { onboardingApi } from '../api.js';

export default function OgreticiSihirbaz({ onKapat, setActiveTab, baslangicAdimi = 0 }) {
  const [adim, setAdim] = useState(baslangicAdimi);
  const [rehber, setRehber] = useState(null);
  const [kapatiliyor, setKapatiliyor] = useState(false);
  const ilkDugme = useRef(null);

  useEffect(() => {
    onboardingApi.rehber().then(setRehber).catch(() => setRehber(null));
  }, []);

  useEffect(() => { ilkDugme.current?.focus(); }, []);

  const sonAdim = SIHIRBAZ_ADIMLARI.length - 1;
  const mevcut = SIHIRBAZ_ADIMLARI[adim];

  const ileri = useCallback(() => setAdim((a) => Math.min(a + 1, sonAdim)), [sonAdim]);
  const geri = useCallback(() => setAdim((a) => Math.max(a - 1, 0)), []);

  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'Escape') onKapat();
      else if (e.key === 'ArrowRight') ileri();
      else if (e.key === 'ArrowLeft') geri();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onKapat, ileri, geri]);

  /** Bir adımın gerçekten yapılıp yapılmadığı — backend rehberinden okunur. */
  const adimTamamMi = (a) => {
    if (!a.dogrulamaAnahtari || !rehber?.adimlar) return null;   // ölçülemiyorsa iddia edilmez
    return rehber.adimlar.find((x) => x.anahtar === a.dogrulamaAnahtari)?.tamam === true;
  };

  const bitir = async () => {
    setKapatiliyor(true);
    try {
      await onboardingApi.rehberGizle(true);   // "bir daha açılışta çıkma" — geri alınabilir
    } catch {
      /* kaydedilemese bile kullanıcı kilitlenmemeli; modal kapanır */
    } finally {
      setKapatiliyor(false);
      onKapat();
    }
  };

  const simdiYap = () => {
    if (mevcut.hedefSekme && setActiveTab) setActiveTab(mevcut.hedefSekme);
    onKapat();
  };

  const tamam = adimTamamMi(mevcut);

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-end sm:items-center justify-center
                 px-0 sm:px-4 animate-fade-in"
      onClick={onKapat}
      role="dialog"
      aria-modal="true"
      aria-label="Kurulum sihirbazı"
    >
      <div
        className="card w-full sm:max-w-lg rounded-b-none sm:rounded-2xl p-5 sm:p-6
                   max-h-[85vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Başlık + adım sayacı */}
        <div className="flex items-start justify-between gap-3 mb-4">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 rounded-lg bg-brand-100 dark:bg-brand-900/40
                            flex items-center justify-center flex-shrink-0">
              <Sparkles className="w-4 h-4 text-brand-700 dark:text-brand-300" />
            </div>
            <div className="min-w-0">
              <h3 className="font-semibold truncate">{mevcut.baslik}</h3>
              <p className="text-[11px] text-zinc-500 dark:text-zinc-400">
                Adım {adim + 1} / {SIHIRBAZ_ADIMLARI.length}
              </p>
            </div>
          </div>
          <button
            type="button" onClick={onKapat} aria-label="Sihirbazı kapat" title="Kapat"
            className="btn btn-ghost btn-icon !p-2 flex-shrink-0"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* İlerleme çubuğu — Recharts değil CSS (BUG #059) */}
        <div className="h-1 rounded-full bg-zinc-200 dark:bg-zinc-800 mb-4 overflow-hidden">
          <div
            className="h-full bg-brand-500 transition-all duration-300"
            style={{ width: `${((adim + 1) / SIHIRBAZ_ADIMLARI.length) * 100}%` }}
          />
        </div>

        {/* Gövde */}
        <p className="text-sm text-zinc-700 dark:text-zinc-300 leading-relaxed">
          {mevcut.metin}
        </p>

        {mevcut.ornek && (
          <div className="mt-3 rounded-xl bg-zinc-100 dark:bg-zinc-800/60 px-3 py-2.5">
            <p className="text-[10px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400 mb-1">
              Örnek
            </p>
            <p className="text-xs font-mono text-zinc-800 dark:text-zinc-100 whitespace-pre-line leading-relaxed">
              {mevcut.ornek}
            </p>
          </div>
        )}

        {tamam === true && (
          <p className="mt-3 inline-flex items-center gap-1.5 text-xs font-medium
                        text-emerald-700 dark:text-emerald-400">
            <Check className="w-3.5 h-3.5" /> Bu adımı zaten tamamladın.
          </p>
        )}

        {/* Gezinme */}
        <div className="mt-5 flex items-center justify-between gap-2">
          <button
            type="button" onClick={geri} disabled={adim === 0}
            className="btn btn-ghost disabled:opacity-40"
          >
            <ArrowLeft className="w-4 h-4" /> Geri
          </button>

          <div className="flex items-center gap-2">
            {mevcut.hedefSekme && (
              <button ref={ilkDugme} type="button" onClick={simdiYap} className="btn btn-secondary">
                Şimdi yap
              </button>
            )}

            {adim < sonAdim ? (
              <button type="button" onClick={ileri} className="btn btn-primary">
                {mevcut.hedefSekme ? 'Sonra' : 'Devam'} <ArrowRight className="w-4 h-4" />
              </button>
            ) : (
              <button type="button" onClick={bitir} disabled={kapatiliyor} className="btn btn-primary">
                {kapatiliyor ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                Bitir
              </button>
            )}
          </div>
        </div>

        <p className="mt-3 text-[11px] text-zinc-500 dark:text-zinc-400">
          İstediğin an kapatabilirsin — ilerlemen kaybolmaz, sağ alttaki yardım
          düğmesinden kaldığın yerden devam edersin.
        </p>
      </div>
    </div>
  );
}
