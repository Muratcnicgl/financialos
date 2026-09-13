import { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts';
import { accountsApi, reportsApi, formatDate } from '../api.js';
import { formatSayi } from '../lib/money.js';
import { SERI, IZGARA, IZGARA_OPAKLIK, EKSEN } from '../lib/grafikRenkleri.js';

/**
 * Fon fiyat geçmişi — DVIZ-007 (BUG #460).
 * `price_history` gece işiyle günlük fiyat biriktirir; bu kart o geçmişi çizer ve
 * `cost_per_lot` (ort. maliyet) referans çizgisiyle "fiyat maliyetin üstünde mi" sorusunu
 * tek bakışta cevaplar. Geçmiş kısa ise (yeni kurulum) bunu SÖYLER, boş grafik göstermez.
 */
export function fonOzeti(fundCode, items, cost) {
  if (!items?.length) return `${fundCode} fiyat geçmişi: veri yok`;
  const ilk = items[0].price, son = items[items.length - 1].price;
  const degisim = ilk ? ((son - ilk) / ilk) * 100 : 0;
  const maliyet = cost != null ? `; ort. maliyet ${formatSayi(cost, { ondalik: 4 })}, fiyat maliyetin ${son >= cost ? 'üstünde' : 'altında'}` : '';
  return `${fundCode} fiyat geçmişi, ${items.length} gün: ${formatSayi(ilk, { ondalik: 4 })} → ${formatSayi(son, { ondalik: 4 })} (%${degisim.toFixed(1)})${maliyet}`;
}

export default function FonFiyatGecmisi() {
  const [fonlar, setFonlar] = useState([]);
  const [secili, setSecili] = useState(null);
  const [days, setDays] = useState(90);
  const [veri, setVeri] = useState(null);
  const [hata, setHata] = useState(null);

  useEffect(() => {
    let iptal = false;
    accountsApi.list().then((hesaplar) => {
      if (iptal) return;
      const f = (hesaplar || []).filter((a) => a.account_type === 'investment' && a.fund_code);
      setFonlar(f);
      // ilk seçim: fonksiyonel güncelleme — `secili`yi bağımlılığa almadan "yalnız boşsa kur"
      setSecili((onceki) => (onceki == null && f.length ? f[0].id : onceki));
    }).catch(() => {});
    return () => { iptal = true; };
  }, []);

  useEffect(() => {
    if (secili == null) return;
    let iptal = false;
    setHata(null);
    reportsApi.fundHistory(secili, days)
      .then((r) => { if (!iptal) setVeri(r); })
      .catch((e) => { if (!iptal) { setVeri(null); setHata(e.message); } });
    return () => { iptal = true; };
  }, [secili, days]);

  if (!fonlar.length) return null;   // fon hesabı yok — bölüm hiç doğmaz
  const items = veri?.items || [];
  const cost = veri?.cost_per_lot;

  return (
    <div className="space-y-3 pt-2" data-testid="fon-fiyat-gecmisi">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-base font-semibold">Fon Fiyat Geçmişi</h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">Günlük kapanış · kesikli çizgi = ortalama maliyet</p>
        </div>
        <div className="flex gap-2 flex-wrap items-center">
          <select aria-label="Fon hesabı" className="input !text-xs w-auto" value={secili ?? ''}
                  onChange={(e) => setSecili(Number(e.target.value))}>
            {fonlar.map((f) => <option key={f.id} value={f.id}>{f.name} · {f.fund_code}</option>)}
          </select>
          {[30, 90, 365].map((d) => (
            <button type="button" key={d} onClick={() => setDays(d)}
              className={`btn !text-xs !px-3 ${days === d ? 'btn-primary' : 'btn-secondary'}`}>{d}g</button>
          ))}
        </div>
      </div>
      {hata ? (
        <p role="alert" className="text-xs text-negative-600 dark:text-negative-400">{hata}</p>
      ) : items.length < 2 ? (
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          Henüz {items.length} günlük fiyat var — gece işi her gün bir kapanış ekler; eğri birkaç günde oluşur.
        </p>
      ) : (
        <div className="card p-4">
          <div style={{ width: '100%', height: 220 }} role="img" aria-label={fonOzeti(veri.fund_code, items, cost)}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={items} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={IZGARA} strokeOpacity={IZGARA_OPAKLIK} />
                <XAxis dataKey="date" tickFormatter={(v) => formatDate(v)} tick={{ fontSize: 11, fill: EKSEN }} />
                <YAxis domain={['auto', 'auto']} tickFormatter={(v) => formatSayi(v, { ondalik: 2 })} tick={{ fontSize: 11, fill: EKSEN }} width={60} />
                <Tooltip formatter={(v, _ad, p) => [formatSayi(v, { ondalik: 4 }), `Fiyat (${p?.payload?.source})`]} labelFormatter={(v) => formatDate(v, { withYear: true })} />
                {cost != null && (
                  <ReferenceLine y={cost} stroke={SERI.negatif} strokeDasharray="4 4"
                                 label={{ value: `maliyet ${formatSayi(cost, { ondalik: 2 })}`, position: 'insideTopLeft', fontSize: 10, fill: 'currentColor', opacity: 0.7 }} />
                )}
                <Line type="monotone" dataKey="price" stroke={SERI.marka} strokeWidth={2} dot={items.length < 40} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
