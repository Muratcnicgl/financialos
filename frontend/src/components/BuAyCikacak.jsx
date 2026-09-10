/**
 * BU AY GERÇEKTEN ÇIKACAK — "Bugün harcayabileceğin"in yanındaki İKİNCİ sayı.
 *
 * NEDEN VAR (kullanıcı bildirimi, 10 Eyl 2026): ekranda "Bugün harcayabileceğin −49,97 TL"
 * yazıyordu ve kullanıcı bunu "saçma" buldu. Sayı YANLIŞ değildi; MC4 gölge muhasebesinin
 * cevabıydı — *kart borcu = harcanmış para*, tamamı düşülür:
 *     15.828,48 nakit − 10.020,75 kart − 6.857,12 taksit = −1.049,39 → 21 güne −49,97
 * Ama o kartın 10.020,75'inin yalnız 6.576,90'ı bu ay çıkıyor; 3.443,85 kesimden SONRA
 * yapılmış harcama ve gelecek ekstreye yazılı. Yani ekrandaki tek sayı, bir STOK (toplam
 * kart borcu) ile bir AKIŞI (bu ayki taksitler) aynı kefeye koyuyordu.
 *
 * KARAR: MC4 kaldırılmadı — kurucu kural, muhafazakâr olması bilinçli. Bunun yerine ikinci
 * sayı GÖRÜNÜR yapıldı. Bilgi saklanmıyor, seçim kullanıcının: biri "borcunla birlikte ne
 * kadarsın", öteki "bu ay kasandan ne çıkacak".
 *
 * KENDİ HESABINI YAPMAZ (ADR-001): tüm sayılar `nakit_takvimi`den okunur — o takvim zaten
 * düzenli geliri, kart son ödemesini, kredi taksitlerini ve vadesi gelen borçları TARİHLİ
 * ve İŞARETLİ olarak taşıyor (Wave-K/G3). Burada aritmetik tekrarlamak, aynı sayının iki
 * yerde ayrışması demekti — bu bileşenin düzelttiği defektin ta kendisi.
 *
 * DÜRÜSTLÜK:
 *  - Kart tutarı ekstreden değil güncel borçtan geliyorsa (ekstre bilinmiyor) SÖYLENİR;
 *    yoksa iki satır aynı varsayımı iki kez gösterip birbirini doğruluyormuş gibi durur.
 *  - Hesabı belirsiz giderler bakiyeye girmez ama görünmez de kalmaz.
 *  - Ay sonu artıda kapanıp ayın ORTASINDA dibe vuruyorsa bu ayrıca söylenir; ay sonu
 *    bakiyesi tek başına "idare eder" dedirtebilir.
 */
import { formatPara } from '../lib/money.js';

export default function BuAyCikacak({ takvim, gunKaldi }) {
  if (!takvim) return null;

  const cikis = Number(takvim.toplam_cikis) || 0;
  const giris = Number(takvim.toplam_giris) || 0;
  if (cikis <= 0 && giris <= 0) return null;   // takvimde kalem yoksa satır da yok

  const kalan = Number(takvim.ay_sonu_bakiye) || 0;
  const gun = Number(gunKaldi) || 0;
  const gunluk = gun > 0 ? kalan / gun : null;

  const belirsiz = Number(takvim.hesabi_belirsiz_toplam) || 0;
  // Kart kalemi ekstreden mi geliyor? `ekstre_biliniyor` alanı YALNIZ kart kalemlerinde var.
  const kartVarsayimi = (takvim.kalemler || []).some(
    (k) => k.tip === 'kart_odeme' && k.ekstre_biliniyor === false,
  );

  return (
    <div className="mt-3 pt-3 border-t border-zinc-200/70 dark:border-zinc-800">
      <p className="text-xs text-zinc-600 dark:text-zinc-400">
        Bu ay gerçekten çıkacak{' '}
        <span className="font-numeric font-semibold text-zinc-900 dark:text-zinc-100">
          {formatPara(cikis)}
        </span>
        {giris > 0 && (
          <>
            {' '}· bu ay girecek{' '}
            <span className="font-numeric text-positive-700 dark:text-positive-400">
              {formatPara(giris)}
            </span>
          </>
        )}
        {' → '}kalan{' '}
        <span className={`font-numeric font-semibold ${
          kalan < 0 ? 'text-negative-600 dark:text-negative-400'
                    : 'text-positive-700 dark:text-positive-400'}`}>
          {formatPara(kalan)}
        </span>
        {gunluk !== null && (
          <> · günlük <span className="font-numeric">{formatPara(gunluk)}</span></>
        )}
      </p>

      {/* Ay sonu artıda ama ay ORTASINDA dibe vuruyorsa: plan yine de açıktır. */}
      {takvim.acik_var && kalan >= 0 && (
        <p className="text-[11px] text-warn-700 dark:text-warn-400 mt-1">
          Ay sonu artıda kapanıyor ama {takvim.en_dusuk_tarih} tarihinde bakiye{' '}
          <span className="font-numeric">{formatPara(takvim.en_dusuk_bakiye)}</span>'ye
          iniyor — sıkışma orada.
        </p>
      )}

      {kartVarsayimi && (
        <p className="text-[11px] text-zinc-500 dark:text-zinc-500 mt-1">
          Kart tutarı güncel borçtan alındı; ekstre borcunu girersen bu sayı netleşir.
        </p>
      )}

      {belirsiz > 0 && (
        <p className="text-[11px] text-zinc-500 dark:text-zinc-500 mt-1">
          Hesabı belirtilmemiş <span className="font-numeric">{formatPara(belirsiz)}</span> gider
          bu toplama girmedi (nakit mi kart mı belli değil).
        </p>
      )}
    </div>
  );
}
