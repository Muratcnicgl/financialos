/**
 * Grafiklerin metin alternatifi — A11Y-013 (BUG #451).
 *
 * Recharts SVG'si ekran okuyucuya "grafik" bile demez. Her grafik `role="img"` +
 * veriden türetilen bir `aria-label` alır: sayıları aynı biçimlendiriciyle (formatPara)
 * söyler, en fazla 5 kalem sayar (uzun kuyruk "…" ile), boş veride "veri yok" der.
 * Tablo alternatifi bilinçli yok: bu grafiklerin verisi zaten yanlarındaki listelerde
 * (kategori listesi, seri kartları) metin olarak var; özet WCAG 1.1.1 için yeter.
 */
import { formatPara } from './money.js';

const en = (arr, n = 5) => arr.slice(0, n);

export function kategoriOzeti(items, grandTotal) {
  if (!items?.length) return 'Kategori dağılımı: veri yok';
  const parcalar = en(items).map((k) => `${k.category} ${formatPara(k.total)}`
    + (grandTotal ? ` (%${Math.round((Number(k.total) / Number(grandTotal)) * 100)})` : ''));
  return `Kategori dağılımı, ${items.length} kalem: ${parcalar.join(', ')}${items.length > 5 ? ', …' : ''}`;
}

export function netDegerOzeti(items) {
  if (!items?.length) return 'Net değer seyri: veri yok';
  const ilk = items[0], son = items[items.length - 1];
  return `Net değer seyri, ${items.length} gün: görülen ${formatPara(ilk.net_worth_seen)} → ${formatPara(son.net_worth_seen)}`
    + `, tam ${formatPara(ilk.net_worth_full)} → ${formatPara(son.net_worth_full)}`;
}

export function aylikSeriOzeti(seri) {
  if (!seri?.length) return 'Aylık seri: veri yok';
  const parcalar = en(seri, 6).map((a) => `${a.label}: gelir ${formatPara(a.total_income)}, gider ${formatPara(a.total_expense)}`);
  return `Aylık gelir/gider, ${seri.length} ay: ${parcalar.join('; ')}`;
}

export function bakiyeTrendiOzeti(chartData) {
  if (!chartData?.length) return 'Bakiye trendi: veri yok';
  const b = chartData.map((d) => Number(d.balance));
  const enAz = Math.min(...b), enCok = Math.max(...b);
  const kriz = chartData.filter((d) => d.crunch).length;
  return `Bakiye trendi, ${chartData.length} gün: en düşük ${formatPara(enAz)}, en yüksek ${formatPara(enCok)}`
    + (kriz ? `, ${kriz} sıkışma günü` : '');
}

export function sankeyOzeti(sankey) {
  const giris = sankey.links.filter((l) => sankey.nodes[l.target]?.type === 'cash');
  const cikis = sankey.links.filter((l) => sankey.nodes[l.source]?.type === 'cash');
  const top = (ls) => ls.reduce((t, l) => t + Number(l.value || 0), 0);
  return `Nakit akış diyagramı: ${giris.length} giriş kalemi ${formatPara(top(giris))}, ${cikis.length} çıkış kalemi ${formatPara(top(cikis))}`;
}
