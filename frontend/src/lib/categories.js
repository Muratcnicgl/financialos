/**
 * BUG #264 / ADR-046 — KATEGORİ LİSTESİ: FRONTEND TEK KAYNAK.
 *
 * Eskiden üç panel kendi listesini kodluyordu ve üçü BİRBİRİNDEN FARKLIYDI:
 *   Transactions.jsx : yemek, ulasim, fatura, eglence, sigara, alisveris, saglik,
 *                      borc_geri_odeme, diger
 *   IncomeDebt.jsx   : abonelik, fatura, kira, sigorta, internet, telefon, diger
 *   Budget.jsx       : placeholder metni ("market, yemek, eğlence...")
 * Yani aynı uygulama üç farklı gerçeklik gösteriyordu ve kullanıcı kendi kategorisini
 * hiçbir yerde kuramıyordu. Liste artık kullanıcının kendi kayıtlarından gelir.
 *
 * `money.js` ile aynı sözleşme: tek kaynak, panel içinde yeniden tanımlanamaz.
 */
import { useCallback, useEffect, useState } from 'react';
import { categoriesApi } from '../api.js';

/**
 * Defterin kategorileri.
 * @param {boolean} tumu gizlenenleri de getir (yönetim ekranı için)
 * @returns {{kategoriler: Array, sluglar: string[], yukleniyor: boolean, hata: string|null, yenile: () => Promise<void>}}
 */
export function useCategories(tumu = false) {
  const [kategoriler, setKategoriler] = useState([]);
  const [yukleniyor, setYukleniyor] = useState(true);
  const [hata, setHata] = useState(null);

  const yenile = useCallback(async () => {
    setYukleniyor(true);
    try {
      const veri = await categoriesApi.list(tumu);
      setKategoriler(Array.isArray(veri) ? veri : []);
      setHata(null);
    } catch (e) {
      // Kategori listesi bir KOLAYLIKTIR; alınamadığında panel çalışmaya devam eder
      // (alanlar serbest metin). Sessiz boş liste bırakılır, panel çökmez.
      setHata(e?.message || 'Kategoriler alınamadı');
      setKategoriler([]);
    } finally {
      setYukleniyor(false);
    }
  }, [tumu]);

  useEffect(() => { yenile(); }, [yenile]);

  return {
    kategoriler,
    sluglar: kategoriler.map((k) => k.slug),
    yukleniyor,
    hata,
    yenile,
  };
}

/** Görünen ad — kayıt yoksa slug'ın kendisi (geçmiş işlem kategorisi silinmiş olabilir). */
export function kategoriAdi(kategoriler, slug) {
  if (!slug) return '(kategorisiz)';
  const k = kategoriler.find((x) => x.slug === slug);
  return k ? k.ad : slug;
}
