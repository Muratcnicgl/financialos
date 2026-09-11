/**
 * İstemci hata raporu (BUG #406 / OBS-013).
 *
 * Ölçülen: tarayıcıda çöken panel yalnız kullanıcının konsolunda kalıyordu; sunucu hata
 * defteri (`error_logs`) istemciyi hiç görmüyordu. Şimdi çöken panel (ErrorBoundary),
 * `window.onerror` ve yakalanmamış promise reddi `POST /api/ops/istemci-hata`ya gider.
 *
 * Kurallar:
 *  - Ateşle-unut: rapor başarısız olursa sessiz kalır; raporlama uygulamayı asla bozmaz.
 *  - Oturum başına aynı parmak izi bir kez, toplam en fazla `TAVAN` rapor: bir render
 *    döngüsü saniyede yüzlerce istek üretmesin (sunucu ayrıca 30/dk sınırlar).
 *  - Kimlik yoksa (giriş ekranı) gönderilmez — sunucu zaten 401 dönerdi.
 */
export const TAVAN = 10;
const gonderilen = new Set();
let sayac = 0;

export function parmakIzi({ tip, yol, yigin }) {
  const cerceveler = String(yigin || '').split('\n').map((s) => s.trim()).filter(Boolean).slice(0, 4);
  return `${tip}|${yol}|${cerceveler.join('|')}`;
}

export function sifirla() { gonderilen.clear(); sayac = 0; }

/** Rapor gönderilecek mi? (saf karar — test edilebilir) */
export function raporlanirMi(hata) {
  if (sayac >= TAVAN) return false;
  const fp = parmakIzi(hata);
  if (gonderilen.has(fp)) return false;
  gonderilen.add(fp);
  sayac += 1;
  return true;
}

export function hataBildir({ tip = 'Error', mesaj = '', yigin = '', yol = '' } = {}, gonder) {
  const hata = { tip: String(tip).slice(0, 60), mesaj: String(mesaj).slice(0, 500),
                 yigin: String(yigin).slice(0, 4000), yol: String(yol).slice(0, 120) };
  if (!raporlanirMi(hata)) return false;
  try {
    const p = gonder(hata);
    if (p && typeof p.catch === 'function') p.catch(() => {});
  } catch { /* sessiz */ }
  return true;
}

/** Global yakalayıcıları bağlar; `gonder` sunucuya POST eden fonksiyondur. */
export function globalYakalayicilariBagla(gonder, yolOku = () => window.location.hash || '/') {
  window.addEventListener('error', (e) => {
    hataBildir({ tip: e.error?.name || 'Error', mesaj: e.message, yigin: e.error?.stack, yol: yolOku() }, gonder);
  });
  window.addEventListener('unhandledrejection', (e) => {
    const r = e.reason;
    hataBildir({ tip: r?.name || 'UnhandledRejection', mesaj: r?.message || String(r), yigin: r?.stack, yol: yolOku() }, gonder);
  });
}
