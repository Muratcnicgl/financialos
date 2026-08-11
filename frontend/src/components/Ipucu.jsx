/**
 * Panel içi ipucu şeridi — "bu ekran ne işe yarar" sorusunun ekrandan ayrılmayan cevabı.
 *
 * Tasarım kararları:
 *  - İçerik burada DEĞİL, `lib/ogretici.js`'te. Bu bileşen yalnız çizer.
 *  - Kapatılabilir ve kapatılınca hatırlanır (cihaz başına, localStorage). Kapatma
 *    KALICI ama GERİ ALINABİLİR: yardım köşesinden aynı metin her zaman açılır. Geri
 *    dönüşü olmayan bir "kapat" kullanıcıyı kilitler (BUG #262 dersi).
 *  - Varsayılan olarak KAPALI değil, DARALTILMIŞ gelir: tek satır özet görünür, detay
 *    (nasıl kullanılır + örnek) tıklayınca açılır. Böylece deneyimli kullanıcının ekranını
 *    işgal etmez, yeni kullanıcı ise yardımın var olduğunu görür.
 *  - `localStorage` erişimi try/catch içinde: gizli sekmede veya depolama kapalıyken
 *    bileşen çökmemeli (panelin tamamını ErrorBoundary'ye düşürürdü).
 */
import { useState } from 'react';
import { Lightbulb, ChevronDown, ChevronUp, X } from 'lucide-react';
import { panelRehberi } from '../lib/ogretici.js';

const ANAHTAR_ONEK = 'ipucu_gizli_';

function gizliMi(sekmeId) {
  try {
    return localStorage.getItem(ANAHTAR_ONEK + sekmeId) === '1';
  } catch {
    return false;   // depolama yoksa ipucu görünsün — sessizce kaybolmasın
  }
}

function gizleKaydet(sekmeId) {
  try {
    localStorage.setItem(ANAHTAR_ONEK + sekmeId, '1');
  } catch {
    /* depolama yok — bu oturumluk gizlemek yeterli */
  }
}

export default function Ipucu({ sekme }) {
  const rehber = panelRehberi(sekme);
  const [gizli, setGizli] = useState(() => gizliMi(sekme));
  const [acik, setAcik] = useState(false);

  if (!rehber || gizli) return null;

  const kapat = () => { gizleKaydet(sekme); setGizli(true); };

  return (
    // flex-shrink-0: Koç paneli `h-full flex flex-col` içinde yaşar; şerit orada sıkışmasın.
    <div className="flex-shrink-0 rounded-xl border border-sky-300/60 dark:border-sky-700/40
                    bg-sky-50 dark:bg-sky-950/20 px-3 py-2.5 mb-4">
      <div className="flex items-start gap-2.5">
        <Lightbulb className="w-4 h-4 mt-0.5 flex-shrink-0 text-sky-700 dark:text-sky-300" />

        <div className="min-w-0 flex-1">
          <p className="text-xs text-sky-900 dark:text-sky-200 leading-relaxed">
            {rehber.ozet}
          </p>

          {acik && (
            <div className="mt-2.5 space-y-2">
              <ol className="space-y-1 list-decimal list-inside">
                {rehber.nasil.map((satir) => (
                  <li key={satir} className="text-xs text-sky-900/90 dark:text-sky-200/90 leading-relaxed">
                    {satir}
                  </li>
                ))}
              </ol>

              {rehber.ornek && (
                <div className="rounded-lg bg-white/70 dark:bg-sky-900/30 px-2.5 py-2">
                  <p className="text-[10px] uppercase tracking-wide text-sky-700 dark:text-sky-400 mb-0.5">
                    Örnek
                  </p>
                  <p className="text-xs font-mono text-sky-900 dark:text-sky-100 whitespace-pre-line">
                    {rehber.ornek}
                  </p>
                </div>
              )}

              {rehber.ipucu && (
                <p className="text-xs text-sky-800 dark:text-sky-300/90 leading-relaxed">
                  <strong className="font-medium">Dikkat:</strong> {rehber.ipucu}
                </p>
              )}
            </div>
          )}

          <button
            type="button"
            onClick={() => setAcik((v) => !v)}
            aria-expanded={acik}
            className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium
                       text-sky-800 dark:text-sky-300 hover:underline min-h-[44px] sm:min-h-0 sm:py-0"
          >
            {acik ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            {acik ? 'Kapat' : 'Nasıl kullanılır'}
          </button>
        </div>

        <button
          type="button"
          onClick={kapat}
          title="Bu ipucunu gizle (yardım köşesinden geri açılır)"
          aria-label="İpucunu gizle"
          /* ADR-011: dokunma hedefi >= 44px. İlk hâli `p-2` + 14px ikon = 30x30 idi ve
             bunu e2e tema/mobil kapısı yakaladı (13 panelin hepsinde raporladı). */
          className="flex-shrink-0 -m-1 rounded-lg text-sky-700 dark:text-sky-400
                     hover:bg-sky-100 dark:hover:bg-sky-900/40
                     min-w-[44px] min-h-[44px] flex items-center justify-center"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
