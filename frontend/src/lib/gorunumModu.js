/**
 * GÖRÜNÜM MODU — "basit" ve "detaylı" arayüzün TEK KAYNAĞI.
 *
 * Neden var: geri bildirimde dönen kullanıcı cümlesi şuydu — "anlaması çok zor, çok
 * detay var". Ölçülen durum onu doğruluyor: tek başlıkta 13 sekme, Cockpit'te tek
 * ekranda yirmiye yakın kart. Bilgi YANLIŞ değil, hepsi doğru; sorun HERKESE AYNI ANDA
 * gösterilmesi. Finansa hâkim bir kullanıcı için bu yoğunluk değerlidir; ilk kez bakan
 * biri için duvar.
 *
 * Karar: yoğunluğu SİLMEK yerine SEÇİLİR yapmak.
 *   - `basit`   → günlük karar için gereken çekirdek: bugün ne kadar harcayabilirim,
 *                 ilk adım ne, onay bekleyen ne var, hesaplarım ne durumda.
 *   - `detayli` → bugüne kadarki tam manzara; hiçbir bölüm eksilmez.
 *
 * SÖZLEŞME (bu dosyanın koruduğu şey):
 *  1. Tercih SORULUR, dayatılmaz: hiç seçim yapılmamışsa `okuModu()` null döner ve
 *     arayüz bir kez sorar. "Varsayılan basit" ile "kullanıcı basiti seçti" aynı şey
 *     değildir; ikisini karıştırmak, soruyu her açılışta yeniden sormaya ya da hiç
 *     sormamaya götürür.
 *  2. Seçim GERİ ALINABİLİR ve her iki yöne de tek tıktır (Hesap panelindeki anahtar).
 *     Geri dönüşü olmayan bir sadeleştirme, kullanıcıyı bilgiden mahrum bırakır
 *     (BUG #262 dersi: gizlemenin geri açma yeri olmalı).
 *  3. Basit mod RİSKİ GİZLEMEZ. Kritik uyarılar, onay bekleyen aksiyonlar, atlanan
 *     düzenli kayıtlar ve "ilk adım" her iki modda da görünür. Gizlenen yalnız
 *     ANALİZ katmanıdır ve kaç bölümün gizlendiği kullanıcıya SAYIYLA söylenir
 *     (`KatlanirBolum`'un "özetsiz katlama bilgi eksiltmektir" sözleşmesinin
 *     panel ölçeğindeki karşılığı).
 *
 * Depolama cihaz başınadır (localStorage). Bilinçli: aynı kişi telefonda sade,
 * masaüstünde detaylı isteyebilir — ekran genişliği tercihin bir parçasıdır. Depolama
 * kapalıysa (gizli sekme) uygulama çökmez, o oturumluk seçim yeterlidir.
 */

export const BASIT = 'basit';
export const DETAYLI = 'detayli';

const ANAHTAR = 'fos_gorunum_modu';
export const OLAY = 'fos:gorunum-modu';

/** Geçerli mod adı mı? Depodan gelen çöp değer sessizce "seçilmemiş" sayılır. */
function gecerli(m) {
  return m === BASIT || m === DETAYLI;
}

/**
 * Kayıtlı tercih. HİÇ SEÇİM YAPILMAMIŞSA `null` — bu bir hata değil, sorulacak
 * soru demektir. Çağıran "null ise basit gibi çiz ama soruyu sor" der.
 */
export function okuModu() {
  try {
    const m = localStorage.getItem(ANAHTAR);
    return gecerli(m) ? m : null;
  } catch {
    return null;
  }
}

/** Çizim için etkin mod: seçim yoksa basit (yeni kullanıcı duvara çarpmasın). */
export function etkinMod(secim = okuModu()) {
  return secim === DETAYLI ? DETAYLI : BASIT;
}

/**
 * Tercihi yazar ve AYNI SEKMEDEKİ tüm dinleyicilere duyurur.
 * `storage` olayı yalnız DİĞER sekmelerde tetiklenir; header ile Hesap paneli aynı
 * sekmede yaşadığı için kendi olayımızı yaymazsak biri bayat kalır (arayüzün yarısı
 * basit, yarısı detaylı görünürdü).
 */
export function yazModu(mod) {
  const m = gecerli(mod) ? mod : BASIT;
  try {
    localStorage.setItem(ANAHTAR, m);
  } catch {
    /* depolama yok — bu oturumluk seçim yine de yayılır */
  }
  try {
    window.dispatchEvent(new CustomEvent(OLAY, { detail: m }));
  } catch {
    /* pencere yoksa (SSR/test) sessiz */
  }
  return m;
}

/** Tercihi siler — yalnız testler ve "bana tekrar sor" akışı için. */
export function unutModu() {
  try {
    localStorage.removeItem(ANAHTAR);
  } catch {
    /* önemsiz */
  }
  try {
    window.dispatchEvent(new CustomEvent(OLAY, { detail: null }));
  } catch {
    /* önemsiz */
  }
}
