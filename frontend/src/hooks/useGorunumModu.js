import { useState, useEffect, useCallback } from 'react';
import { BASIT, DETAYLI, OLAY, okuModu, etkinMod, yazModu } from '../lib/gorunumModu.js';

/**
 * Görünüm modunu okuyan/yazan ve DEĞİŞİMİ DUYAN hook.
 *
 * Aynı anda üç yer bu tercihe bakar: sekme çubuğu, Cockpit ve Hesap panelindeki
 * anahtar. Biri değiştirdiğinde diğerleri yeniden çizilmezse arayüzün yarısı basit,
 * yarısı detaylı kalır — kullanıcı "değişmedi" der ve tercihi bir daha denemez.
 * Bu yüzden hem kendi olayımız (`fos:gorunum-modu`, aynı sekme) hem tarayıcının
 * `storage` olayı (diğer sekmeler) dinlenir.
 */
export function useGorunumModu() {
  const [secim, setSecim] = useState(() => okuModu());   // null = henüz sorulmadı

  useEffect(() => {
    const guncelle = () => setSecim(okuModu());
    window.addEventListener(OLAY, guncelle);
    window.addEventListener('storage', guncelle);
    return () => {
      window.removeEventListener(OLAY, guncelle);
      window.removeEventListener('storage', guncelle);
    };
  }, []);

  const degistir = useCallback((mod) => { yazModu(mod); }, []);

  const mod = etkinMod(secim);
  return {
    mod,                       // çizim için: 'basit' | 'detayli'
    basit: mod === BASIT,
    secildi: secim !== null,   // kullanıcı gerçekten seçti mi (sormak için)
    degistir,
    BASIT,
    DETAYLI,
  };
}
