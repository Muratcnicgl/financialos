/**
 * KATLANIR BÖLÜM — yoğun panelleri EKSİLTMEDEN sadeleştirmenin tek yolu.
 *
 * Sorun: Cockpit tek ekranda otuza yakın kart/sayı gösteriyordu. Hepsi doğru, hepsi
 * gerekli — ama aynı anda bakıldığında hiçbiri öne çıkmıyor. Yeni kullanıcının ilk
 * ekranda ne yapacağını bilememesinin sebebi bilgi EKSİKLİĞİ değil, bilgi HİYERARŞİSİ
 * eksikliğiydi.
 *
 * Sözleşme — "sadeleştirme" burada gizlemek DEĞİLDİR:
 *  - Katlıyken bile ÖZET başlıkta durur ("4 kalem · 12.400 TL"). Kullanıcı bir bölümü
 *    açmadan da orada ne olduğunu ve önemli olup olmadığını bilir. Özetsiz katlama
 *    bilgi eksiltmektir; bu bileşen özetsiz çağrılırsa da çalışır ama çağıranın
 *    özet vermesi beklenir.
 *  - Dikkat çeken bir şey varsa (`vurgu`), bölüm katlı olsa bile rozet gösterilir.
 *  - Kullanıcının açtığı/kapattığı hâl HATIRLANIR (cihaz başına). Her açılışta aynı
 *    bölümü yeniden açmak zorunda kalmak, katlamayı bir engele çevirir.
 *
 * Erişilebilirlik: başlık gerçek bir <button> (klavyeyle açılır), `aria-expanded`
 * taşır, dokunma hedefi 44px (ADR-011).
 */
import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';

const ONEK = 'bolum_acik_';

function kayitliDurum(anahtar, varsayilan) {
  if (!anahtar) return varsayilan;
  try {
    const v = localStorage.getItem(ONEK + anahtar);
    return v === null ? varsayilan : v === '1';
  } catch {
    return varsayilan;
  }
}

function durumYaz(anahtar, acik) {
  if (!anahtar) return;
  try {
    localStorage.setItem(ONEK + anahtar, acik ? '1' : '0');
  } catch {
    /* depolama yok — bu oturumluk yeterli */
  }
}

export default function KatlanirBolum({
  ikon: Ikon,
  baslik,
  ozet = null,          // katlıyken başlıkta duran bilgi — "eksiltmeden" şartı
  vurgu = null,         // dikkat gerektiren durum rozeti (katlıyken de görünür)
  anahtar = null,       // localStorage tercihi; verilmezse hatırlanmaz
  varsayilanAcik = false,
  children,
}) {
  const [acik, setAcik] = useState(() => kayitliDurum(anahtar, varsayilanAcik));

  const degistir = () => {
    setAcik((v) => { durumYaz(anahtar, !v); return !v; });
  };

  return (
    <div className="card p-4">
      <button
        type="button"
        onClick={degistir}
        aria-expanded={acik}
        className="w-full flex items-center gap-2 min-h-[44px] text-left"
      >
        {acik
          ? <ChevronDown className="w-4 h-4 flex-shrink-0 text-zinc-500" />
          : <ChevronRight className="w-4 h-4 flex-shrink-0 text-zinc-500" />}
        {Ikon && <Ikon className="w-4 h-4 flex-shrink-0 text-brand-600 dark:text-brand-400" />}
        <h3 className="font-semibold text-sm truncate">{baslik}</h3>

        {vurgu && (
          <span className="chip chip-negative text-[10px] flex-shrink-0">{vurgu}</span>
        )}
        {ozet && (
          <span className="ml-auto text-xs text-zinc-500 dark:text-zinc-400 truncate max-w-[55%] text-right">
            {ozet}
          </span>
        )}
      </button>

      {acik && <div className="mt-3">{children}</div>}
    </div>
  );
}
