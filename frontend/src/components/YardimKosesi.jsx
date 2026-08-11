/**
 * YARDIM KÖŞESİ — her panelde, sağ altta duran kalıcı düğme.
 *
 * Neden var: yardım yalnız ilk girişte gösterilirse, kullanıcının gerçekten takıldığı
 * an (üçüncü gün, dördüncü panel) elinde hiçbir şey kalmaz. Bu düğme her ekranda aynı
 * yerdedir ve iki şeye birden cevap verir: "bu ekran ne işe yarar" (aktif panele göre
 * değişir) ve "baştan öğrenmek istiyorum" (sihirbazı yeniden başlatır).
 *
 * Konum kararı: `FeedbackWidget` de sağ altta duruyor — üst üste binmesinler diye bu
 * düğme onun ÜSTÜNE yerleşir (bottom-20). İki ayrı yüzer düğme yerine tek menü altında
 * toplanır; "Sorun bildir" buradan da açılabilsin diye geri bildirim bağlantısı menüde.
 *
 * Erişilebilirlik: dokunma hedefi 44px (ADR-011), Esc ile kapanır, aria-expanded taşır.
 */
import { useState, useEffect, useRef } from 'react';
import { HelpCircle, X, Sparkles, Keyboard, FlaskConical, MessageSquarePlus, ChevronRight } from 'lucide-react';
import { panelRehberi } from '../lib/ogretici.js';

export default function YardimKosesi({ sekme, onSihirbaz, onKisayollar, onOrnekVeri, onGeriBildirim }) {
  const [acik, setAcik] = useState(false);
  const kutu = useRef(null);
  const rehber = panelRehberi(sekme);

  useEffect(() => {
    if (!acik) return undefined;
    const tus = (e) => { if (e.key === 'Escape') setAcik(false); };
    const disari = (e) => { if (kutu.current && !kutu.current.contains(e.target)) setAcik(false); };
    window.addEventListener('keydown', tus);
    window.addEventListener('mousedown', disari);
    return () => {
      window.removeEventListener('keydown', tus);
      window.removeEventListener('mousedown', disari);
    };
  }, [acik]);

  const secenekler = [
    { id: 'sihirbaz', ikon: Sparkles, etiket: 'Kurulum sihirbazı',
      aciklama: 'Adım adım baştan gez', fn: onSihirbaz },
    { id: 'kisayol', ikon: Keyboard, etiket: 'Klavye kısayolları',
      aciklama: 'Hızlı hareketlerin tuşları', fn: onKisayollar },
    { id: 'ornek', ikon: FlaskConical, etiket: 'Örnek veriyle gez',
      aciklama: 'Kendi verini girmeden dene', fn: onOrnekVeri },
    { id: 'bildir', ikon: MessageSquarePlus, etiket: 'Sorun bildir',
      aciklama: 'Takıldığın yeri yaz', fn: onGeriBildirim },
  ].filter((s) => typeof s.fn === 'function');

  return (
    <div ref={kutu} className="fixed right-4 bottom-20 z-40 flex flex-col items-end gap-2">
      {acik && (
        <div className="card w-[min(20rem,calc(100vw-2rem))] p-3 shadow-xl animate-fade-in">
          {rehber && (
            <div className="mb-2 pb-2 border-b border-zinc-200 dark:border-zinc-700">
              <p className="text-[10px] uppercase tracking-wide text-zinc-500 dark:text-zinc-400 mb-0.5">
                Bu ekran
              </p>
              <p className="text-xs font-medium mb-1">{rehber.baslik}</p>
              <p className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">
                {rehber.ozet}
              </p>
              {rehber.ornek && (
                <p className="mt-1.5 text-[11px] font-mono text-zinc-500 dark:text-zinc-400
                              whitespace-pre-line leading-relaxed">
                  {rehber.ornek}
                </p>
              )}
            </div>
          )}

          <ul className="space-y-0.5">
            {secenekler.map(({ id, ikon: Ikon, etiket, aciklama, fn }) => (
              <li key={id}>
                <button
                  type="button"
                  onClick={() => { setAcik(false); fn(); }}
                  className="w-full flex items-center gap-2.5 px-2 py-2 rounded-lg text-left
                             hover:bg-zinc-100 dark:hover:bg-zinc-800 min-h-[44px]"
                >
                  <Ikon className="w-4 h-4 flex-shrink-0 text-zinc-500 dark:text-zinc-400" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-xs font-medium truncate">{etiket}</span>
                    <span className="block text-[11px] text-zinc-500 dark:text-zinc-400 truncate">
                      {aciklama}
                    </span>
                  </span>
                  <ChevronRight className="w-3.5 h-3.5 flex-shrink-0 text-zinc-400" />
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <button
        type="button"
        onClick={() => setAcik((v) => !v)}
        aria-expanded={acik}
        aria-label={acik ? 'Yardımı kapat' : 'Yardıma mı ihtiyacın var?'}
        title={acik ? 'Kapat' : 'Yardıma mı ihtiyacın var?'}
        className="w-11 h-11 rounded-full bg-brand-600 hover:bg-brand-700 text-white
                   shadow-lg flex items-center justify-center transition-colors"
      >
        {acik ? <X className="w-5 h-5" /> : <HelpCircle className="w-5 h-5" />}
      </button>
    </div>
  );
}
