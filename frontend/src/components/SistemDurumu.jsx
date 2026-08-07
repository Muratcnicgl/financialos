/**
 * P-madde 4 (BUG #253) — KİMLİKSİZ SİSTEM DURUMU: "bende mi, sizde mi?"
 *
 * `/api/meta/durum` ve `/api/ready` uçları vardı ama kullanıcının bakabileceği bir yüzey
 * YOKTU. Giriş yapamayan kullanıcının elindeki tek bilgi "bir şeyler ters gitti"ydi:
 * şifresini mi yanlış giriyor, sunucu mu ölü, ayırt edemiyordu. Bilinmezlik, bilinen
 * kesintiden daha çok destek yükü üretir (ve beta kullanıcısını sessizce kaybettirir).
 *
 * Tasarım kararları:
 * - **Kimlik istemez** — çünkü asıl ihtiyaç duyan giriş YAPAMAYAN kullanıcıdır.
 * - **Ayrıntı sızdırmaz**: hangi tablo, hangi hata, hangi sürüm uyuşmazlığı YAZILMAZ
 *   (bu bilgi saldırgana yarar, kullanıcıya yaramaz). Yalnız "çalışıyor / sorun var".
 * - `/api/ready` 503 dönebilir; bu bir HATA DEĞİL, ölçülen sonucun kendisidir.
 */
import { useEffect, useState } from 'react';
import { CheckCircle2, AlertTriangle, Loader2, RefreshCw, X } from 'lucide-react';

const DURUMLAR = {
  saglikli: { ikon: CheckCircle2, renk: 'text-positive-600 dark:text-positive-500', metin: 'Sistem çalışıyor' },
  sorunlu: { ikon: AlertTriangle, renk: 'text-negative-500', metin: 'Sistemde sorun var' },
  bilinmiyor: { ikon: AlertTriangle, renk: 'text-warn-600 dark:text-warn-500', metin: 'Sunucuya ulaşılamıyor' },
};

async function durumOku() {
  try {
    const r = await fetch('/api/ready', { headers: { Accept: 'application/json' } });
    // 503 = hazır değil (DB/şema). Gövde yine JSON'dur; ayrıntı KULLANICIYA gösterilmez.
    if (r.status === 200) return { durum: 'saglikli', api: true, veritabani: true };
    if (r.status === 503) return { durum: 'sorunlu', api: true, veritabani: false };
    return { durum: 'sorunlu', api: true, veritabani: null };
  } catch {
    return { durum: 'bilinmiyor', api: false, veritabani: null };
  }
}

export default function SistemDurumu({ onClose }) {
  const [sonuc, setSonuc] = useState(null);
  const [yukleniyor, setYukleniyor] = useState(true);

  const yenile = async () => {
    setYukleniyor(true);
    setSonuc(await durumOku());
    setYukleniyor(false);
  };

  useEffect(() => { yenile(); }, []);

  const d = DURUMLAR[sonuc?.durum || 'bilinmiyor'];
  const Ikon = d.ikon;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
         role="dialog" aria-label="Sistem durumu">
      <div className="card w-full max-w-sm p-5 space-y-4">
        <div className="flex items-start justify-between">
          <h3 className="font-semibold">Sistem durumu</h3>
          <button type="button" onClick={onClose} className="btn btn-ghost btn-icon !p-1" title="Kapat">
            <X className="w-4 h-4" />
          </button>
        </div>

        {yukleniyor ? (
          <div className="flex items-center gap-2 text-sm text-zinc-500 dark:text-zinc-400">
            <Loader2 className="w-4 h-4 animate-spin" /> Kontrol ediliyor…
          </div>
        ) : (
          <>
            <div className={`flex items-center gap-2 ${d.renk}`}>
              <Ikon className="w-5 h-5" />
              <span className="font-semibold text-sm">{d.metin}</span>
            </div>
            <ul className="text-xs text-zinc-500 dark:text-zinc-400 space-y-1">
              <li>Uygulama sunucusu: {sonuc.api ? 'yanıt veriyor' : 'yanıt vermiyor'}</li>
              <li>
                Veritabanı: {sonuc.veritabani === true ? 'yanıt veriyor'
                  : sonuc.veritabani === false ? 'yanıt vermiyor' : 'bilinmiyor'}
              </li>
            </ul>
            <p className="text-[11px] text-zinc-500">
              {sonuc.durum === 'saglikli'
                ? 'Sunucu tarafında bilinen bir sorun yok. Giriş yapamıyorsan şifre/davet kodunu kontrol et.'
                : 'Bu bir sunucu sorunu — senin hatan değil. Birazdan tekrar dene; sürerse destek adresine yaz.'}
            </p>
          </>
        )}

        <button type="button" onClick={yenile} disabled={yukleniyor}
                className="btn btn-secondary w-full !text-xs">
          <RefreshCw className={`w-3.5 h-3.5 ${yukleniyor ? 'animate-spin' : ''}`} /> Yeniden kontrol et
        </button>
      </div>
    </div>
  );
}
