# Raporlama & görselleştirme (kod: DVIZ)

Denetim kapsamı: `frontend/src/panels/Reports.jsx`, `frontend/src/panels/Cashflow.jsx`, `frontend/src/panels/Cockpit.jsx`, `frontend/src/panels/DebtStrategy.jsx`, `frontend/src/components/BalanceTrend.jsx`, `CashflowCalendar.jsx`, `CashflowSankey.jsx`, `CashflowSummary.jsx`, `app/routers/reports.py`, `app/models.py` (NetWorthSnapshot, PriceHistory).

Mevcut durum özeti: recharts yalnızca 3 dosyada kullanılıyor (`Reports.jsx`, `BalanceTrend.jsx`, `CashflowSankey.jsx`). Var olan grafikler: kategori donut + yatay bar (Reports), net değer çizgisi (Reports), alacak-borç timeline (Reports), bakiye trend çizgisi + takvim + Sankey (Cashflow). Eksik alanlar: fon fiyat performansı (PriceHistory tablosu var ama hiçbir grafik okumuyor), aylık gelir/gider trendi, dönem karşılaştırma, kart doluluk trendi, borç eritme projeksiyonu, CSV/PDF export, grafik erişilebilirliği.

Araştırma kaynakları:
- Finans dashboard hiyerarşisi (üst KPI → orta trend → alt detay), net değer için çizgi, aylık için bar, tahsis için pasta: [Eleken - Financial Dashboard Examples](https://www.eleken.co/blog-posts/financial-dashboard-examples), [Qlik - Financial Dashboards](https://www.qlik.com/us/dashboard-examples/financial-dashboards), [f9finance - Dashboard Design Best Practices](https://www.f9finance.com/dashboard-design-best-practices/)
- Renk körlüğü güvenli palet (Okabe-Ito / Wong, maks 6 renk, mavi-turuncu en güvenli çift), doğrudan etiketleme, WCAG 4.5:1, artıklı kodlama (şekil+desen): [colorblind.io - Data Visualization](https://colorblind.io/guides/data-visualization), [Sigma - Charts for Color Blindness](https://www.sigmacomputing.com/blog/data-charts-color-blindness), [Venngage - Colorblind-Friendly Palettes](https://venngage.com/blog/color-blind-friendly-palette/)

---

### [DVIZ-001] Net Değer Trendi grafiği yatırım değerini aynı Y ekseninde ezik gösteriyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: üç Line tek YAxis, investment right-axis yok

Sorun: `net_worth_seen`, `net_worth_full` ve `investment_value` tek çizgi grafiğinde ortak Y ekseninde çiziliyor. Net değer büyüklüğü (milyonlar mertebesi) ile yatırım değeri çok farklı ölçekte olduğunda yatırım çizgisi dibe yapışır, trendi okunmaz olur. Ayrıca NetWorthSnapshot günlük snapshot'ları alacaksız/alacaklı ayrımını doğru veriyor ama üç serinin görsel ağırlığı dengesiz.

Kanıt: `frontend/src/panels/Reports.jsx:321-347` üç Line aynı YAxis'e bağlı (Reports.jsx:313-317 tek eksen). Snapshot verisi mevcut ve besleniyor: `app/routers/reports.py:104-134`, tablo `app/models.py:492-519`.

Aksiyon: Yatırım değerini ikinci sağ Y eksenine (`yAxisId="right"`) taşı veya ayrı bir mini grafiğe çıkar. Alternatif: "Görülen" ve "Tam" net değeri birincil eksende bırakıp yatırımı ayrı panelde göster.

Etki: orta · Efor: S (yarım saat, tek panel)

---

### [DVIZ-002] Grafik renk paleti renk körlüğü güvenli değil, kırmızı-yeşil bitişik
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: COLORS renk-körü güvenli değil

Sorun: `COLORS` dizisi 10 renk içeriyor ve hem donut hem yatay barda sırayla kullanılıyor. 2. renk yeşil (#16a34a) ile 7. renk kırmızı (#e11d48) protanopi/deuteranopi altında ayırt edilemez; ayrıca 10 kategori tek pastada 5-6 renk sınırını aşar. Araştırma: kategorik kodlamada doğrulanmış paletten (Wong/Okabe-Ito) maks 6 renk önerilir.

Kanıt: `frontend/src/panels/Reports.jsx:15-19` palet tanımı; donut `Reports.jsx:215-217` ve bar `Reports.jsx:245-247` aynı diziyi index ile tüketiyor.

Aksiyon: Okabe-Ito 8 renkli güvenli paletine geç (maks 6 kategori göster, kalanı "Diğer" olarak topla). Bar zaten sayısal etiket taşıyor (LabelList, Reports.jsx:248-253) — bu artıklı kodlama iyi; donut'a da yüzde etiketi ekle ki renge bağımlılık azalsın.

Etki: yüksek · Efor: S

---

### [DVIZ-003] Donut 10 dilime kadar çıkıyor, karşılaştırma için zayıf form
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: donut 10 dilim, top-6/Diğer yok

Sorun: Kategori sayısı çoksa donut okunması güç bir renk yığınına dönüşür; pasta/donut 5-6 dilimden fazlasında karşılaştırma için kötü form. Yanındaki yatay bar zaten aynı veriyi daha okunur veriyor, yani donut çoğu zaman gereksiz ikizleme.

Kanıt: `frontend/src/panels/Reports.jsx:200-224` donut, `Reports.jsx:227-258` aynı `items` verisiyle yatay bar. `innerRadius=65/outerRadius=95` sabit (Reports.jsx:209-210), dilim sayısına göre okunabilirlik ayarı yok.

Aksiyon: Donut'u top-6 + "Diğer" ile sınırla, ya da donut'u kaldırıp bar'ı ana görsel yap. Donut kalırsa ortasına toplam tutarı (grand_total) yaz — boş iç halka değer taşımıyor.

Etki: orta · Efor: S

---

### [DVIZ-004] Aylık gelir/gider trendi yok (Wave-2 A3 aylık özet eksik)
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: monthly-summary kartı geldi ama çok-aylık bar yok

Sorun: `category-breakdown` yalnızca kayan pencere (30/90 gün) toplamı veriyor; ay-be-ay gelir vs gider trendi, önceki aya göre değişim yok. Wave-2 A3 hedefi "aylık özet rapor: gelir/gider/net değişim + kategori + önceki aya trend" karşılanmamış.

Kanıt: `app/routers/reports.py:47-97` tek dönem toplu sorgu; ay gruplaması yok. Reports.jsx'te aylık grouped/stacked bar bileşeni yok (`frontend/src/panels/Reports.jsx` genelinde yalnızca donut+bar+trend+cashflow).

Aksiyon: `GET /api/reports/monthly-summary?months=6` ekle (Transaction'ı `strftime('%Y-%m')` ile gruplayıp ay başına gelir/gider/net döndür). Frontend'de gruplu bar (gelir yeşil, gider kırmızı) + net çizgisi. Araştırma: aylık karşılaştırma için bar ideal form.

Etki: yüksek · Efor: M

---

### [DVIZ-005] Dönem karşılaştırma ve KPI delta yok
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: MonthlySummary delta var ama MetricCard delta yok

Sorun: Cockpit metrik kartları yalnızca mutlak değer gösteriyor; önceki döneme göre yön/delta yok. Finans dashboard'larda KPI kutusunun önceki döneme göre artış/azalış (ok + yüzde) taşıması standart. Kullanıcı "kart borcu geçen aya göre düştü mü" sorusunu göremiyor.

Kanıt: `frontend/src/panels/Cockpit.jsx:148-203` MetricCard'lar yalnızca `value` alıyor, trend/delta prop yok. NetWorthSnapshot geçmişi mevcut olduğu halde (models.py:492-519) delta hesabı hiçbir yerde yapılmıyor.

Aksiyon: MetricCard'a opsiyonel `delta`/`deltaLabel` prop ekle; cockpit response'una önceki snapshot'tan (7 gün / ay başı) değişim ekle. Küçük sparkline (son 30 gün) da eklenebilir — recharts mini LineChart.

Etki: yüksek · Efor: M

---

### [DVIZ-006] Grafiklerde dark mode grid/eksen rengi sabit açık tona kodlanmış
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: grid/ReferenceLine sabit renk

Sorun: Net değer trend grafiğinde CartesianGrid ve referans çizgileri sabit hex ile veriliyor; dark mode'da grid neredeyse görünmez veya yanlış kontrast. Aynı repoda BalanceTrend `currentColor` + opacity ile doğru temaya duyarlı deseni kullanıyor — tutarsızlık var.

Kanıt: Sabit: `frontend/src/panels/Reports.jsx:307` `stroke="#e4e4e7"`, `Reports.jsx:320` ReferenceLine `#71717a`, `TICK_COLOR = '#71717a'` (Reports.jsx:21). Doğru desen: `frontend/src/components/BalanceTrend.jsx:58` `stroke="currentColor" strokeOpacity={0.1}`, `BalanceTrend.jsx:63,69` `fill: 'currentColor'`.

Aksiyon: Reports grafiğini de `currentColor`+opacity desenine geçir. TICK_COLOR zinc-500 iki temada okunur (yorum böyle diyor) ama grid çizgisi #e4e4e7 dark'ta kaybolur — en azından grid'i currentColor yap.

Etki: orta · Efor: S

---

### [DVIZ-007] Fon performans grafiği yok, PriceHistory tablosu kullanılmıyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: fund-history endpoint/grafiği yok

Sorun: `PriceHistory` tablosu fon/hisse fiyat geçmişini "tek doğruluk kaynağı" olarak saklıyor ama hiçbir endpoint veya grafik bu geçmişi okumuyor. Cockpit yalnızca anlık K/Z snapshot'ı gösteriyor; fon fiyatının zaman içindeki seyri (maliyet çizgisiyle birlikte) görselleştirilmiyor.

Kanıt: Tablo `app/models.py:540-588` (kompozit PK fund_code+price_date+source). `app/routers/fund_price.py` içinde history okuyan sorgu yok (grep: PriceHistory/history eşleşmesi yok). Cockpit K/Z: `frontend/src/panels/Cockpit.jsx:291-322` yalnızca anlık 4 metrik.

Aksiyon: `GET /api/reports/fund-history?fund_code=...&days=90` ekle (PriceHistory'den kaynak önceliğiyle tek seri). Frontend'de fiyat çizgisi + `cost_per_lot` referans çizgisi (Account.cost_per_lot, models.py:171). Yatırım tavsiyesi değil, geçmiş fiyat görselleştirmesi.

Etki: orta · Efor: M

---

### [DVIZ-008] Kart doluluk (utilization) oranı ve trendi görselleştirilmiyor
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: FEAT-016 doluluk bar+trend (Cockpit.jsx:354)

Sorun: Kart borcu Cockpit'te mutlak TL olarak gösteriliyor ama `credit_limit`e göre doluluk yüzdesi (kritik metrik — PROJE.md'de "kart %99.8 dolu" temel problem) gauge/bar olarak yok. NetWorthSnapshot günlük `card_debt` sakladığı halde doluluk trendi de çizilmiyor.

Kanıt: `credit_limit` alanı mevcut `app/models.py:158`; günlük kayıt `card_debt` `app/models.py:507`. Cockpit yalnızca mutlak: `frontend/src/panels/Cockpit.jsx:149` `value={data.kart_borcu}`. Doluluk oranı hesabı/gauge bileşeni yok.

Aksiyon: Kart kartına doluluk yüzdesi barı ekle (renk eşiği: >%80 kırmızı, >%50 sarı). Snapshot'lardan doluluk trend mini-çizgisi. Gauge yerine yatay progress bar erişilebilirlik açısından daha güvenli.

Etki: yüksek · Efor: M

---

### [DVIZ-009] Borç eritme (payoff) projeksiyon grafiği yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: payoff projeksiyon grafiği yok

Sorun: DebtStrategy paneli strateji karşılaştırması sunuyor ama hiçbir grafik içermiyor (recharts import yok). 5 krediyi zaman içinde eritme projeksiyonu (kalan bakiye düşüş çizgisi) görsel olarak yok — kullanıcı hangi stratejinin borcu ne zaman sıfırladığını göremiyor.

Kanıt: `frontend/src/panels/DebtStrategy.jsx` içinde recharts/Chart eşleşmesi yok (grep negatif). Backend `app/routers/debt_strategy.py:62` `/compare` strateji döndürüyor ama frontend zaman serisi çizmiyor.

Aksiyon: `/compare` çıktısından aylık kalan-bakiye serisi üret, strateji başına çizgi (snowball vs avalanche) çiz. Sıfırlanma ayını ReferenceDot ile işaretle. Görselleştirme; finansal tavsiye üretme, mevcut motor kararını çiz.

Etki: orta · Efor: M

---

### [DVIZ-010] Bakiye trend grafiği sıkışmayı yalnızca noktayla gösteriyor, alan/eşik bandı yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: Area dolgu/ReferenceArea bandı yok

Sorun: Nakit akışı bakiye trendinde negatif/eşik altı bölge yalnızca kırmızı ReferenceDot ile işaretleniyor; sıfır altına inen alan gölgelenmiyor, crunch eşiği bir bant olarak gösterilmiyor. Bakiyenin ne kadar süre eşik altında kaldığı görsel olarak zayıf okunuyor.

Kanıt: `frontend/src/components/BalanceTrend.jsx:82-100` tek Line + crunch günleri için ReferenceDot; y=0 ince referans çizgisi (BalanceTrend.jsx:81). Eşik değeri (`crunchThreshold`, Cashflow.jsx:23) grafiğe band olarak yansıtılmıyor.

Aksiyon: Area (veya gradient dolgu) ile sıfır altını kırmızı gölgele; `crunchThreshold` için ReferenceArea/ReferenceLine ekle. Böylece sıkışma penceresi tek bakışta görünür.

Etki: orta · Efor: S

---

### [DVIZ-011] CSV / PDF export yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: CSV export yok

Sorun: Ne işlem listesi ne rapor dışa aktarılabiliyor; hiçbir endpoint CSV/PDF üretmiyor. Kullanıcı verisini yedeklemek, muhasebeciye vermek veya harici analiz için çıkaramıyor.

Kanıt: `app/routers/transactions.py` ve `app/routers/reports.py` içinde StreamingResponse/CSV/Content-Disposition eşleşmesi yok (grep negatif). Frontend'de indirme butonu yok.

Aksiyon: (1) `GET /api/transactions/export.csv` — StreamingResponse ile UTF-8 BOM'lu CSV (Türkçe karakter + Excel uyumu). (2) Aylık özet için tarayıcı `window.print()` + print CSS ya da client-side blob CSV (küçük veri, ek bağımlılık gerekmez). PDF için önce print-to-PDF yeterli.

Etki: orta · Efor: M

---

### [DVIZ-012] Net değer trendi varlık/borç kompozisyonunu göstermiyor (veri var, kullanılmıyor)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: net-worth-trend cash/card/loan serialize etmiyor

Sorun: NetWorthSnapshot her gün `cash`, `card_debt`, `loan_debt`, `investment_value`, `receivables` ayrı ayrı saklıyor ama trend endpoint'i yalnızca 3 birleşik toplamı döndürüyor. Net değerin nasıl oluştuğu (varlık kırılımı vs borç kırılımı) stacked area olarak gösterilmiyor — zengin veri boşa gidiyor.

Kanıt: Saklanan alanlar `app/models.py:504-510`; endpoint yalnızca `net_worth_seen/full/investment` döndürüyor `app/routers/reports.py:125-133` (cash/card_debt/loan_debt/receivables serialize edilmiyor).

Aksiyon: Endpoint'e bileşenleri ekle; frontend'de opsiyonel stacked area (varlıklar üstte pozitif, borçlar altta negatif) veya toggle'lı görünüm. Net değer çizgisi bileşenlerin üstüne overlay edilebilir.

Etki: orta · Efor: M

---

### [DVIZ-013] Grafiklerde ARIA/metin alternatifi ve veri tablosu yedeği yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: grafik role=img/tablo yedeği yok

Sorun: Hiçbir ResponsiveContainer/chart `role="img"`, `aria-label`, `<title>` veya erişilebilir veri tablosu yedeği taşımıyor. Ekran okuyucu kullanıcıları grafik içeriğine hiç erişemiyor. Araştırma: renk artıklı kodlamanın yanında metin alternatifi/veri tablosu zorunlu ilk savunma hattı.

Kanıt: `frontend/src/panels/Reports.jsx:203`, `frontend/src/components/BalanceTrend.jsx:56`, `frontend/src/components/CashflowSankey.jsx:79` ResponsiveContainer'larında aria/role yok. Donut legend'i yalnızca renk+ad taşıyor (Reports.jsx:220), sayısal değer legend'de yok.

Aksiyon: Her grafik sarmalayıcısına `role="img"` + özet `aria-label` (örn "Son 30 gün kategori dağılımı, en yüksek: Market 12.300 TL") ekle. "Tabloyu göster" toggle'ı ile aynı veriyi erişilebilir `<table>` olarak sun. Tooltip'ler zaten iyi ama klavye/okuyucuya kapalı.

Etki: orta · Efor: M

---

### [DVIZ-014] Sayı biçimlendirme grafikler arası tutarsız
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: üç ayrı formatter

Sorun: Kısaltma mantığı her grafikte farklı: Reports bar'da `shortTL` (virgüllü, "12,3K"), Reports Y ekseninde `fmtYAxis` (virgülsüz, "12K"), Cashflow'da `formatTL(v, {compact:true})`. Aynı ekranda üç farklı bin/milyon kısaltması kullanıcıyı yanıltır ve markayı dağıtır.

Kanıt: `frontend/src/panels/Reports.jsx:30-33` shortTL, `Reports.jsx:495-498` fmtYAxis, `frontend/src/components/BalanceTrend.jsx:68` `formatTL(v,{compact:true})`, `CashflowCalendar.jsx:112` yine compact. Üç ayrı uygulama.

Aksiyon: Tek `formatTL(..., {compact:true})` (api.js) fonksiyonunu tüm eksen/etiketlerde kullan; Reports'taki yerel `shortTL`/`fmtYAxis` yardımcılarını sil. Tutarlı ondalık ayırıcı (Türkçe virgül) ve K/Mn eşiği.

Etki: düşük · Efor: S

---

### [DVIZ-015] Rapor bilgisi üç panele dağılmış, tek dashboard hiyerarşisi yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: raporlama dağınık, upcoming-cashflow çakışma

Sorun: Görselleştirmeler üç ayrı panele bölünmüş: Reports (kategori + net değer trend + alacak takvimi), Cashflow (bakiye trend + takvim + Sankey), Cockpit (mini akış özeti + K/Z). Aynı alacak-borç verisi hem Reports.jsx hem Cashflow'da farklı formatta tekrar ediyor. Araştırma: iyi finans dashboard'u üç katmanlı tek hiyerarşi ister (üstte KPI → orta trend → alt detay); dağınık yapı kullanıcıyı gezinmeye zorluyor.

Kanıt: Reports uzun tek scroll: `frontend/src/panels/Reports.jsx:140-478` (kategori + trend + cashflow üst üste). Alacak-borç tekrarı: `app/routers/reports.py:154-236` `upcoming-cashflow` ile `Cashflow` forecast'i çakışıyor; Cockpit'te de mini özet `frontend/src/panels/Cockpit.jsx:324-363`.

Aksiyon: Net bir bilgi hiyerarşisi kur: Cockpit = üst KPI + delta (DVIZ-005) + tek sparkline; Reports = trend katmanı (net değer, aylık gelir/gider, kategori); Cashflow = ileriye dönük tahmin. Alacak-borç takvimini tek bileşende topla, iki panelde tekrarlama.

Etki: orta · Efor: L

---
