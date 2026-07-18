# Denetim: frontend/src/components/BalanceTrend.jsx

> **M86 güncellik:** 🟢 GÜNCEL — 6 bulgu hepsi açık


> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [FBT-001] ReferenceDot listesinde index key kullanimi
Sorun: crunchDays.map ile uretilen ReferenceDot elemanlarina benzersiz ve stabil olan d.date yerine dizi index'i key olarak veriliyor. crunchDays, tam gunler listesinin filtrelenmis bir alt kumesi oldugundan (esik/veri degisince) index sirasi kayabilir, React'in reconciliation'i yanlis elemani eslestirebilir.
Kanit (satir 90-99):
```
{crunchDays.map((d, i) => (
  <ReferenceDot
    key={i}
    x={d.date}
    ...
```
Aksiyon: key={i} yerine key={d.date} kullanilmali (date alani gunluk projeksiyonda benzersiz).
Onem: Orta · Guven: Kesin

### [FBT-002] days prop icin varsayilan/koruma yok
Sorun: Bilesen `days` prop'unu dogrudan `.map` ile isliyor (satir 36). Su an tek cagiran yer olan Cashflow.jsx bunu `{!loading && data && ...}` ile koruyor (data.days her zaman dolu geliyor), fakat BalanceTrend kendi basina `days=undefined` veya `days=null` ile cagrilirsa TypeError firlatir; savunmaci varsayilan (`days = []`) yok.
Kanit (satir 35-36):
```
export default function BalanceTrend({ days, today }) {
  const chartData = days.map(d => ({
```
Aksiyon: `days = []` varsayilan parametre eklenmesi, bilesenin tek basina yeniden kullanilabilir/test edilebilir olmasini saglar.
Onem: Dusuk · Guven: Kesin (kod gercegi) — su anki tek kullanim noktasinda pratikte tetiklenmiyor (Guven bu kisim icin Dogrulanmali).

### [FBT-003] today prop dogrulanmadan ReferenceLine'a veriliyor
Sorun: `today` (Cashflow.jsx'te `data.start_date`) undefined/bos gelirse ReferenceLine `x={undefined}` ile render edilir; Recharts bu durumda satiri sessizce atlayabilir ya da konsola uyari basabilir. Kod tarafinda herhangi bir guard yok.
Kanit (satir 75-80):
```
<ReferenceLine
  x={today}
  stroke="#94a3b8"
  ...
```
Aksiyon: `{today && <ReferenceLine x={today} ... />}` seklinde kosullu render edilebilir.
Onem: Dusuk · Guven: Dogrulanmali (backend'in start_date'i her zaman doldurdugu varsayimina dayaniyor, dogrulanmadi)

### [FBT-004] Turetilmis diziler memoize edilmiyor
Sorun: chartData, crunchDays ve xTicks her render'da yeniden hesaplaniyor (useMemo yok). Veri boyutu (tipik 30-90 gun) kucuk oldugundan performans etkisi ihmal edilebilir, ancak Cashflow.jsx'teki diger state degisiklikleri (esik input'u gibi) bu bileseni gereksiz yere yeniden hesaplatabilir.
Kanit (satir 36-49): chartData/xTicks/crunchDays tanimlari, render govdesinde dogrudan.
Aksiyon: Gerekirse `useMemo(() => ..., [days])` ile sarilabilir; mevcut veri boyutunda zorunlu degil.
Onem: Dusuk · Guven: Kesin

### [FBT-005] Grafik erisilebilirlik disi (ekran okuyucu/klavye)
Sorun: SVG tabanli LineChart icin aria-label/role='img' veya metinsel ozet yok; ekran okuyucu kullanicisi grafigi hic algilayamaz. Sadece crunch gunleri sayisi metinsel olarak (satir 104-107) veriliyor, bakiye trendinin genel egilimi (yukselen/dusen) icin herhangi bir text alternatifi yok.
Kanit (satir 56, 103-108): ResponsiveContainer/LineChart'ta aria-label yok; crunch ozeti sadece kosullu olarak (crunchDays.length > 0) render ediliyor.
Aksiyon: Kapsayici div'e `role="img" aria-label="Bakiye trendi grafigi"` gibi bir ozet eklenebilir. (Not: bu genel FE/A11Y denetiminde de kapsanmis olabilir, burada dosya-spesifik hatirlatma olarak birakildi.)
Onem: Dusuk · Guven: Kesin

### [FBT-006] Renkler hardcoded hex, tema tokenlariyla tutarsiz
Sorun: Grid/eksen metinleri `currentColor` + opacity ile tema-uyumlu yapilmisken (satir 58, 63, 69), Line/ReferenceLine/ReferenceDot renkleri sabit hex degerleri (#3b82f6, #ef4444, #94a3b8, #fff) olarak kodlanmis. Dark/light tema arasinda kasitli olarak sabit kalmasi beklenen bir tasarim karari olabilir ama kod icinde bunu belirten bir yorum yok.
Kanit (satir 77, 81, 85, 88, 96-97): hex renkler.
Aksiyon: Kasitliyse kisa bir yorum eklensin ("chart renkleri tema-bagimsiz sabit tutulur"); degilse Tailwind/tema degiskenlerine baglanmali.
Onem: Dusuk · Guven: Dogrulanmali (tasarim niyeti bilinmiyor)
