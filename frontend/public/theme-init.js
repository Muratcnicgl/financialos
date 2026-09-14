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
  // MOB-009 (BUG #499): anahtar `theme` — React tarafı (App.jsx useTheme) bu anahtarı yazar.
  // Ölçüldü (14 Eyl 2026): burası başka bir anahtar okuyordu, kimse onu yazmıyordu → açık
  // tema kullanan herkes her açılışta koyu başlayıp React mount'unda açığa dönüyordu (flash).
  // Kayıt yoksa işletim sistemi tercihi (A11Y-016 ile aynı kural). `theme-color` meta'sı da
  // burada ilk kez, sonra App.jsx her geçişte günceller (durum çubuğu tema rengini alır).
  var koyu = true;
  try {
    var t = localStorage.getItem('theme');
    if (t === 'light') koyu = false;
    else if (t !== 'dark' && window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) koyu = false;
  } catch (e) { koyu = true; }
  if (koyu) document.documentElement.classList.add('dark');
  else document.documentElement.classList.remove('dark');
  var meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', koyu ? '#09090b' : '#fafafa');
})();
