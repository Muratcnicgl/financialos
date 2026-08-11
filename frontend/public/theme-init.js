/**
 * Tema flash'ini onleyen ilk-kosum script'i.
 *
 * NEDEN AYRI DOSYA (BUG #287): bu kod index.html'de INLINE duruyordu. Ikı katmanin da
 * CSP'si `script-src 'self'` (uygulama SPA modunda ve nginx sablonunda) — inline script
 * bunlarin ikisinde de ENGELLENIR. Sonucu sessizdi: sayfa acilir, tema yanlis baslar ve
 * konsolda bir CSP ihlali durur. Harici dosya `'self'` kapsamindadir; CSP'yi
 * 'unsafe-inline' ile GEVSETMEK yerine kodu kurallara uygun yere tasidik (L51).
 *
 * `<head>` icinde ve async/defer'siz cagrilir: React mount olmadan once koser, yoksa
 * kullanici bir an yanlis temayi gorur.
 */
(function () {
  try {
    var t = localStorage.getItem('financialos-theme');
    if (t === 'light') {
      document.documentElement.classList.remove('dark');
    } else {
      // Varsayilan: koyu tema
      document.documentElement.classList.add('dark');
    }
  } catch (e) {
    document.documentElement.classList.add('dark');
  }
})();
