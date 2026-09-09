/**
 * ARAYÜZ TERCİHİ — ilk açılışta BİR KEZ sorulan soru.
 *
 * Neden sorulur, varsayılmaz: "kullanıcı basit ister" de "kullanıcı detay ister" de
 * birer varsayımdır ve ikisi de yanlış olabilir. Soruyu bir kez sormak, her iki
 * varsayımdan da ucuzdur. Cevap verilmeden ekran kilitlenmez: kapatan kişi basit
 * görünümle devam eder ve soru bir daha çıkmaz (davet edilmemiş bir modal, ikinci
 * gösterimde engeldir — `OgreticiSihirbaz` ile aynı ders).
 *
 * Metin, seçimi TARİF EDER, övmez: hangi modda neyin görüneceği tek cümlede yazılıdır.
 * "Basit" küçümseyici, "Pro" ödüllendirici bir ad olurdu; ikisi de kullanıcıyı
 * kendi seçmediği tarafa iter. Adlar bu yüzden yalnız YOĞUNLUĞU anlatıyor.
 */
import { useEffect } from 'react';
import { LayoutDashboard, SlidersHorizontal, Check } from 'lucide-react';
import { BASIT, DETAYLI } from '../lib/gorunumModu.js';

function Secenek({ ikon: Ikon, ad, ozet, maddeler, onSec, vurgulu }) {
  return (
    <button
      type="button"
      onClick={onSec}
      className={`group text-left rounded-2xl border p-4 transition-all duration-150
        hover:-translate-y-0.5 hover:shadow-lg focus:outline-none focus:ring-2 focus:ring-brand-500
        ${vurgulu
          ? 'border-brand-400 dark:border-brand-500/70 bg-brand-50/60 dark:bg-brand-950/25'
          : 'border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900'}`}
    >
      <div className="flex items-center gap-2.5 mb-2">
        <span className={`w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0
          ${vurgulu ? 'bg-brand-600 text-white' : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300'}`}>
          <Ikon className="w-4 h-4" />
        </span>
        <span className="font-semibold">{ad}</span>
      </div>
      <p className="text-sm text-zinc-600 dark:text-zinc-300 leading-relaxed">{ozet}</p>
      <ul className="mt-2.5 space-y-1">
        {maddeler.map((m) => (
          <li key={m} className="flex items-start gap-1.5 text-xs text-zinc-500 dark:text-zinc-400">
            <Check className="w-3.5 h-3.5 mt-0.5 flex-shrink-0 text-positive-600 dark:text-positive-400" />
            <span>{m}</span>
          </li>
        ))}
      </ul>
    </button>
  );
}

export default function GorunumSecici({ onSec }) {
  // Esc = "karar veremedim": sade ile devam edilir ve soru bir daha çıkmaz. Kaçış yolu
  // olmayan bir modal, cevabı olmayan kullanıcıyı uygulamadan tamamen kilitler.
  // Zemine tıklamak BİLEREK bir şey seçmez — dalgın bir tık, tercihi belirlememeli.
  useEffect(() => {
    const esc = (e) => { if (e.key === 'Escape') onSec(BASIT); };
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [onSec]);

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 animate-fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="gorunum-secici-baslik"
    >
      <div className="card w-full max-w-lg p-5 sm:p-6 !rounded-2xl max-h-[90dvh] overflow-y-auto">
        <h2 id="gorunum-secici-baslik" className="text-lg font-bold">
          Arayüzü nasıl istersin?
        </h2>
        <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">
          İkisi de aynı verilere bakar — fark, aynı anda ne kadarının ekranda durduğu.
          Kararın kalıcı değil: Hesap sayfasından istediğin an değiştirirsin.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
          <Secenek
            ikon={LayoutDashboard}
            ad="Sade"
            ozet="Günlük karar için gereken çekirdek. Ekran boş kalmaz, dolup taşmaz."
            maddeler={[
              'Bugün ne kadar harcayabilirsin',
              'Atılacak ilk adım ve onay bekleyenler',
              'Hesapların ve kritik uyarılar',
            ]}
            onSec={() => onSec(BASIT)}
            vurgulu
          />
          <Secenek
            ikon={SlidersHorizontal}
            ad="Detaylı"
            ozet="Tüm analiz katmanı açık: oranlar, projeksiyonlar, takvimler."
            maddeler={[
              'Faiz sızıntısı, kart kullanım oranı',
              'Nakit akışı, vade takvimi, alacak yaşlandırma',
              '13 panelin tamamı sekme çubuğunda',
            ]}
            onSec={() => onSec(DETAYLI)}
          />
        </div>

        <div className="mt-4 flex items-center justify-between gap-3 flex-wrap">
          <p className="text-xs text-zinc-500">
            Emin değilsen sade ile başla — bir şey eksik gelirse tek tıkla detaylıya geçersin.
          </p>
          <button type="button" onClick={() => onSec(BASIT)}
            className="text-xs underline text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 min-h-[44px] px-1">
            Şimdilik sade ile devam et
          </button>
        </div>
      </div>
    </div>
  );
}
