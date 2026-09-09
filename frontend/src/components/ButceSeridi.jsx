/**
 * BÜTÇE ŞERİDİ — günlük limitin nereden geldiğini TEK BAKIŞTA gösterir.
 *
 * Veri `butce_dokum`'dan gelir ve HER kullanıcıda vardır (rules_engine hesaplar,
 * ADR-001: motor hesaplar, arayüz gösterir). Bugüne kadar bu döküm yalnız katlanır
 * bir metin listesiydi ("Nakit … + Beklenen gelir … − Kart borcu …"); sayıları
 * okumadan hangi kalemin baskın olduğu görünmüyordu.
 *
 * Şerit iki taraflıdır ve ORAN gösterir, tutar değil:
 *   üstte  EKLEYENLER  (nakit + bu ay beklenen gelir)
 *   altta  DÜŞENLER    (kart borcunun tamamı + bu ayki kredi taksiti)
 * İki şerit AYNI ölçeğe göre çizilir (toplam giren), böylece "borç, girenin ne
 * kadarını yiyor" sorusu göz kararı cevaplanır.
 *
 * Dürüstlük kuralları:
 *  - Ölçek toplam GİRENdir; düşenler girenden büyükse şerit taşmaz, %100'de kesilir
 *    ve durum metinle söylenir (kırpılmış bir çubuk "az" gibi görünmemeli).
 *  - Sıfır olan kalem hiç çizilmez; sıfır genişlikte bir dilim, olmayan bir kalemi
 *    varmış gibi gösteren bir çizgi bırakır.
 *  - Yüzdeler yuvarlanır ama etiketlerde TUTAR yazılır: oran görsel, gerçek sayıdır.
 */
import { formatPara } from '../lib/money.js';

export default function ButceSeridi({ dokum }) {
  if (!dokum) return null;

  const nakit = Number(dokum.nakit) || 0;
  const gelir = Number(dokum.beklenen_gelir) || 0;
  const kart = Number(dokum.kart_borcu) || 0;
  const taksit = Number(dokum.bu_ayki_taksit) || 0;

  const giren = nakit + gelir;
  const cikan = kart + taksit;
  if (giren <= 0 && cikan <= 0) return null;

  const olcek = Math.max(giren, 1);
  const yuzde = (v) => Math.min(100, (v / olcek) * 100);
  const cikanTasiyor = cikan > giren;

  const dilim = (deger, sinif, etiket) =>
    deger > 0 && (
      <div
        key={etiket}
        className={`h-full ${sinif}`}
        style={{ width: `${yuzde(deger)}%` }}
        title={`${etiket}: ${formatPara(deger)}`}
      />
    );

  return (
    <div className="mt-3">
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
        {dilim(nakit, 'bg-positive-500', 'Nakit')}
        {dilim(gelir, 'bg-positive-300 dark:bg-positive-700', 'Beklenen gelir')}
      </div>
      <div className="mt-1 flex h-2 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
        {dilim(kart, 'bg-negative-500', 'Kart borcu')}
        {dilim(taksit, 'bg-negative-300 dark:bg-negative-700', 'Bu ayki taksit')}
      </div>

      <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]
                      text-zinc-600 dark:text-zinc-400">
        {nakit > 0 && (
          <span className="inline-flex items-center gap-1">
            <i className="w-2 h-2 rounded-full bg-positive-500" aria-hidden="true" />
            Nakit <span className="font-numeric">{formatPara(nakit)}</span>
          </span>
        )}
        {gelir > 0 && (
          <span className="inline-flex items-center gap-1">
            <i className="w-2 h-2 rounded-full bg-positive-300 dark:bg-positive-700" aria-hidden="true" />
            Beklenen gelir <span className="font-numeric">{formatPara(gelir)}</span>
          </span>
        )}
        {kart > 0 && (
          <span className="inline-flex items-center gap-1">
            <i className="w-2 h-2 rounded-full bg-negative-500" aria-hidden="true" />
            Kart borcu <span className="font-numeric">{formatPara(kart)}</span>
          </span>
        )}
        {taksit > 0 && (
          <span className="inline-flex items-center gap-1">
            <i className="w-2 h-2 rounded-full bg-negative-300 dark:bg-negative-700" aria-hidden="true" />
            Taksit <span className="font-numeric">{formatPara(taksit)}</span>
          </span>
        )}
      </div>

      {/* Şerit %100'de kesildiyse bunu SÖYLE — kırpılmış çubuk "az" gibi görünmemeli. */}
      {cikanTasiyor && (
        <p className="mt-1 text-[11px] text-negative-600 dark:text-negative-400">
          Yükümlülükler girenden fazla; alt şerit tam dolu çizildi (gerçek oran daha yüksek).
        </p>
      )}
    </div>
  );
}
