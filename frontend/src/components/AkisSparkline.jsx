/**
 * 30 GÜNLÜK BAKİYE ÇİZGİSİ — Cockpit'teki akış özetinin görsel karşılığı.
 *
 * Neden var: veri ZATEN çekiliyordu. `cashflowApi.getForecast({days:30})` her gün için
 * `closing_balance` ve `crunch` bayrağı döndürüyor; Cockpit bundan yalnız üç sayı
 * gösteriyordu (en düşük bakiye, net akış, sıkışma günü sayısı). Üç sayı "önümüzdeki ay
 * nasıl geçecek" sorusunu cevaplamaz; şekli görmek cevaplar — para ne zaman dibe
 * vuruyor, ne zaman toparlıyor.
 *
 * Neden Recharts DEĞİL: deponun anti-pattern listesi yeni bileşenlerde CSS/SVG tercih
 * edilmesini söylüyor (BUG #059 — Recharts mount uyarısı). Burada çizilen şey tek bir
 * poligon; kütüphane getirmek hem gereksiz hem o bug'ın kapısını yeniden açardı.
 *
 * Dürüstlük kuralları:
 *  - Uydurma yumuşatma YOK: noktalar olduğu gibi bağlanır (spline/interpolasyon yok),
 *    çünkü eğri, olmayan bir ara değeri varmış gibi gösterir.
 *  - Sıfır çizgisi bakiye negatife düşüyorsa çizilir; düşmüyorsa çizilmez (olmayan bir
 *    eşiği göstermek gürültüdür).
 *  - En düşük gün ve sıkışma günleri işaretlenir — kullanıcının bakacağı yer orasıdır.
 *  - Nokta sayısı 2'nin altındaysa çizgi çizilmez: iki noktası olmayan bir "eğilim"
 *    iddiası uydurmadır.
 */
export default function AkisSparkline({ gunler, yukseklik = 56, className = '',
                                       degerAlani = 'closing_balance', renk = null }) {
  // Erken dönüş: iki noktası olmayan bir "eğilim" iddiası uydurmadır.
  if (!Array.isArray(gunler) || gunler.length < 2) return null;

  const G = 100;                       // viewBox genişliği (yüzde tabanlı, esner)
  const Y = yukseklik;
  const PAY = 6;                       // üst/alt pay: işaretçiler kırpılmasın

  const degerler = gunler.map((g) => Number(g[degerAlani]) || 0);
  const enAz = Math.min(...degerler);
  const enCok = Math.max(...degerler);
  const aralik = enCok - enAz || 1;

  const x = (i) => (i / (gunler.length - 1)) * G;
  const y = (v) => PAY + (1 - (v - enAz) / aralik) * (Y - 2 * PAY);

  const noktalar = degerler.map((v, i) => `${x(i).toFixed(2)},${y(v).toFixed(2)}`);
  const cizgi = `M ${noktalar.join(' L ')}`;
  const alan = `${cizgi} L ${G},${Y} L 0,${Y} Z`;

  const enDusukIndeks = degerler.indexOf(enAz);
  const sikismalar = gunler
    .map((g, i) => (g.crunch ? i : -1))
    .filter((i) => i >= 0);
  const negatifVar = enAz < 0;
  const sifirY = negatifVar ? y(0) : null;

  // Renk: sıkışma varsa uyarı, bakiye negatife düşüyorsa olumsuz, yoksa marka rengi.
  const ton = renk || (negatifVar ? 'negative' : sikismalar.length ? 'warn' : 'brand');
  const cizgiSinif = {
    negative: 'stroke-negative-500',
    warn: 'stroke-warn-500',
    brand: 'stroke-brand-500',
  }[ton];
  const alanSinif = {
    negative: 'fill-negative-500/10',
    warn: 'fill-warn-500/10',
    brand: 'fill-brand-500/10',
  }[ton];

  return (
    <svg
      viewBox={`0 0 ${G} ${Y}`}
      preserveAspectRatio="none"
      className={`w-full ${className}`}
      style={{ height: Y }}
      role="img"
      aria-label={`30 günlük bakiye seyri: en düşük ${Math.round(enAz)}, en yüksek ${Math.round(enCok)}`}
    >
      {/* Sıfır çizgisi — YALNIZ bakiye negatife düşüyorsa */}
      {sifirY !== null && (
        <line x1="0" y1={sifirY} x2={G} y2={sifirY}
              className="stroke-negative-400" strokeWidth="0.5" strokeDasharray="2 2"
              vectorEffect="non-scaling-stroke" />
      )}

      <path d={alan} className={alanSinif} />
      <path d={cizgi} fill="none" strokeWidth="1.5" vectorEffect="non-scaling-stroke"
            strokeLinejoin="round" strokeLinecap="round" className={cizgiSinif} />

      {/* Sıkışma günleri */}
      {sikismalar.map((i) => (
        <circle key={`s${i}`} cx={x(i)} cy={y(degerler[i])} r="2"
                className="fill-negative-500" vectorEffect="non-scaling-stroke" />
      ))}

      {/* En düşük gün */}
      <circle cx={x(enDusukIndeks)} cy={y(enAz)} r="2.5"
              className={`${ton === 'brand' ? 'fill-brand-600' : 'fill-negative-600'} stroke-white dark:stroke-zinc-900`}
              strokeWidth="1" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
