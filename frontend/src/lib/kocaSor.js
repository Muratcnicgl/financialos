// UX-013 (BUG #477): "Koça sor" — bir paneldeki kalemden koça HAZIR SORUYLA geçiş.
// Soru sessionStorage'a bırakılır, sekme değişir; Coach paneli açılışta alıp girdiye koyar ve
// anahtarı siler (bir kez). Gönderilmez: kullanıcı okur, düzenler, kendisi yollar — koç
// kullanıcı adına soru "sormuş" olmaz. sessionStorage (localStorage değil): sekme kapanınca
// bayat soru kalmasın.
export const HAZIR_SORU_ANAHTARI = 'fos_koc_hazir_soru';

export function kocaSor(setActiveTab, soru) {
  try { sessionStorage.setItem(HAZIR_SORU_ANAHTARI, soru); } catch { /* özel pencere: sessiz */ }
  setActiveTab?.('coach');
}

/** Coach açılışında: bekleyen hazır soru varsa döndür ve sil. */
export function hazirSoruyuAl() {
  try {
    const s = sessionStorage.getItem(HAZIR_SORU_ANAHTARI);
    if (s) sessionStorage.removeItem(HAZIR_SORU_ANAHTARI);
    return s || '';
  } catch {
    return '';
  }
}

/** Kart son ödeme satırından üretilen soru — sayılar satırdan, cümle burada (tek kaynak). */
export function kartSonOdemeSorusu(r, paraMetni) {
  const ne = r.days_until === 0 ? 'bugün' : r.days_until === 1 ? 'yarın' : `${r.days_until} gün sonra`;
  return `${r.account_name || r.name} kartının son ödemesi ${ne}, tutar ${paraMetni}. Nakit durumuma göre nasıl hazırlanayım?`;
}
