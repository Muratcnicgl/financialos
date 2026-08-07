import { useState } from 'react';
import { Loader2, Plus, Trash2, Eye, EyeOff, Lock, CreditCard, Pencil, Check, X } from 'lucide-react';
import { categoriesApi } from '../api.js';
import { useCategories } from '../lib/categories.js';
import { useToast } from './Toast.jsx';

/**
 * Kategori yönetimi (BUG #264 / ADR-046) — kategori seti KULLANICININ.
 *
 * Neden burada (Bütçe paneli) ve yeni sekme DEĞİL: uygulamada zaten 13 sekme var ve
 * kategori, zarf bütçesinin birebir konusu (`Envelope.category`). Yeni sekme kullanıcıya
 * bilişsel yük olurdu (KURAL 12).
 *
 * Sözleşme:
 *  - "Kart varsayılanı" işaretli kategoride, hesap belirtmeden bildirilen harcama kredi
 *    kartına yazılır. Bu ESKİDEN koda gömülü beş Türkçe addı; artık kullanıcının kararı.
 *  - Sistem kategorileri (transfer, borç ödeme, kredi taksiti) muhasebe işlemidir:
 *    silinemez, yeniden adlandırılamaz — yalnız gizlenebilir. Kilit ikonuyla gösterilir.
 *  - Kullanılmış kategori silinirken işlemlerin taşınacağı hedef sorulur (birleştirme);
 *    hedefsiz silme geçmiş işlemleri kategorisiz bırakırdı.
 */
export default function CategoryManager({ onDegisti }) {
  const toast = useToast();
  const { kategoriler, yukleniyor, hata, yenile } = useCategories(true);
  const [ad, setAd] = useState('');
  const [kart, setKart] = useState(false);
  const [kaydediliyor, setKaydediliyor] = useState(false);
  const [duzenlenen, setDuzenlenen] = useState(null);   // {id, ad}
  const [silinecek, setSilinecek] = useState(null);     // {id, slug}
  const [hedef, setHedef] = useState('');

  const tazele = async () => { await yenile(); onDegisti?.(); };

  const ekle = async (e) => {
    e.preventDefault();
    if (!ad.trim()) return;
    try {
      setKaydediliyor(true);
      await categoriesApi.create({ ad: ad.trim(), kart_varsayilani: kart });
      setAd(''); setKart(false);
      toast.success('Kategori eklendi');
      await tazele();
    } catch (e2) {
      toast.error(e2.message || 'Eklenemedi');
    } finally {
      setKaydediliyor(false);
    }
  };

  const guncelle = async (id, veri) => {
    try {
      await categoriesApi.update(id, veri);
      await tazele();
    } catch (e2) {
      toast.error(e2.message || 'Güncellenemedi');
    }
  };

  const sil = async (kategori) => {
    try {
      await categoriesApi.remove(kategori.id);
      toast.success('Kategori silindi');
      await tazele();
    } catch (e2) {
      // 409 = kullanılıyor → hedef sor (birleştirme akışı)
      if (e2.status === 409 && /hedef/i.test(e2.message || '')) {
        setSilinecek(kategori);
        setHedef('');
        return;
      }
      toast.error(e2.message || 'Silinemedi');
    }
  };

  const birlestir = async () => {
    if (!hedef) return;
    try {
      await categoriesApi.remove(silinecek.id, hedef);
      toast.success(`İşlemler "${hedef}" kategorisine taşındı`);
      setSilinecek(null);
      await tazele();
    } catch (e2) {
      toast.error(e2.message || 'Taşınamadı');
    }
  };

  if (yukleniyor) {
    return (
      <div className="card p-4 flex items-center gap-2 text-sm text-zinc-500">
        <Loader2 className="w-4 h-4 animate-spin" /> Kategoriler yükleniyor...
      </div>
    );
  }

  if (hata) {
    return (
      <div className="card p-4 space-y-2 text-center">
        <p className="text-sm text-negative-600 dark:text-negative-400">Kategoriler yüklenemedi.</p>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">{hata}</p>
        <button type="button" onClick={yenile} className="btn btn-secondary">Tekrar dene</button>
      </div>
    );
  }

  return (
    <div className="card p-4 space-y-3">
      <div>
        <h3 className="text-sm font-semibold">Kategoriler</h3>
        <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
          Kendi kategorilerini kur. “Kart varsayılanı” işaretlediklerinde, hesap belirtmeden
          bildirdiğin harcama kredi kartına yazılır.
        </p>
      </div>

      <form onSubmit={ekle} className="flex flex-wrap items-end gap-2">
        <div className="flex-1 min-w-[140px]">
          <label className="text-xs text-zinc-500 dark:text-zinc-400">Yeni kategori</label>
          <input className="input w-full" placeholder="spor, aidat, kitap..."
                 value={ad} onChange={(e) => setAd(e.target.value)} />
        </div>
        <label className="flex items-center gap-1.5 text-xs text-zinc-600 dark:text-zinc-300 min-h-[44px]">
          <input type="checkbox" checked={kart} onChange={(e) => setKart(e.target.checked)} />
          Kart varsayılanı
        </label>
        <button type="submit" disabled={kaydediliyor || !ad.trim()}
                className="btn btn-primary flex items-center gap-1">
          {kaydediliyor ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />} Ekle
        </button>
      </form>

      <ul className="divide-y divide-zinc-200 dark:divide-zinc-700">
        {kategoriler.map((k) => (
          <li key={k.id} className="py-2 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0">
              {k.sistem && <Lock className="w-3.5 h-3.5 text-zinc-500 dark:text-zinc-400 shrink-0"
                                 title="Sistem kategorisi — muhasebe işlemi" />}
              {duzenlenen?.id === k.id ? (
                <input
                  className="input !py-1 !text-sm" value={duzenlenen.ad} autoFocus
                  onChange={(e) => setDuzenlenen({ ...duzenlenen, ad: e.target.value })}
                />
              ) : (
                <span className={`truncate ${k.gizli ? 'text-zinc-500 dark:text-zinc-400 line-through' : ''}`}>{k.ad}</span>
              )}
              {k.kart_varsayilani && (
                <CreditCard className="w-3.5 h-3.5 text-brand-500 shrink-0" title="Kart varsayılanı" />
              )}
            </div>

            <div className="flex items-center gap-1 shrink-0">
              {duzenlenen?.id === k.id ? (
                <>
                  <button type="button" title="Kaydet"
                          className="min-w-[44px] min-h-[44px] inline-flex items-center justify-center text-positive-600"
                          onClick={async () => {
                            await guncelle(k.id, { ad: duzenlenen.ad.trim() });
                            setDuzenlenen(null);
                          }}>
                    <Check className="w-4 h-4" />
                  </button>
                  <button type="button" title="Vazgeç"
                          className="min-w-[44px] min-h-[44px] inline-flex items-center justify-center text-zinc-500 dark:text-zinc-400"
                          onClick={() => setDuzenlenen(null)}>
                    <X className="w-4 h-4" />
                  </button>
                </>
              ) : (
                <>
                  {!k.sistem && (
                    <label className="flex items-center gap-1 text-[11px] text-zinc-500 dark:text-zinc-400">
                      <input type="checkbox" checked={!!k.kart_varsayilani}
                             onChange={(e) => guncelle(k.id, { kart_varsayilani: e.target.checked })} />
                      kart
                    </label>
                  )}
                  {!k.sistem && (
                    <button type="button" title="Yeniden adlandır"
                            className="min-w-[44px] min-h-[44px] inline-flex items-center justify-center text-zinc-500 dark:text-zinc-400 hover:text-brand-500"
                            onClick={() => setDuzenlenen({ id: k.id, ad: k.ad })}>
                      <Pencil className="w-4 h-4" />
                    </button>
                  )}
                  <button type="button" title={k.gizli ? 'Göster' : 'Gizle'}
                          className="min-w-[44px] min-h-[44px] inline-flex items-center justify-center text-zinc-500 dark:text-zinc-400 hover:text-brand-500"
                          onClick={() => guncelle(k.id, { gizli: !k.gizli })}>
                    {k.gizli ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                  {!k.sistem && (
                    <button type="button" title="Sil"
                            className="min-w-[44px] min-h-[44px] inline-flex items-center justify-center text-zinc-500 dark:text-zinc-400 hover:text-negative-500"
                            onClick={() => sil(k)}>
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </>
              )}
            </div>
          </li>
        ))}
      </ul>

      {/* Birleştirme: kullanılmış kategori silinirken işlemler nereye taşınsın? */}
      {silinecek && (
        <div className="rounded-lg border border-warn-300 dark:border-warn-800/60 bg-warn-50/60 dark:bg-warn-950/20 p-3 space-y-2">
          <p className="text-sm">
            <span className="font-medium">{silinecek.ad}</span> kategorisi işlemlerde kullanılıyor.
            Silmek için işlemlerin taşınacağı kategoriyi seç:
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <select className="input flex-1 min-w-[140px]" value={hedef}
                    onChange={(e) => setHedef(e.target.value)}>
              <option value="">Hedef kategori...</option>
              {kategoriler.filter((k) => k.id !== silinecek.id && !k.sistem).map((k) => (
                <option key={k.id} value={k.slug}>{k.ad}</option>
              ))}
            </select>
            <button type="button" className="btn btn-primary" disabled={!hedef} onClick={birlestir}>
              Taşı ve sil
            </button>
            <button type="button" className="btn btn-secondary" onClick={() => setSilinecek(null)}>
              Vazgeç
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
