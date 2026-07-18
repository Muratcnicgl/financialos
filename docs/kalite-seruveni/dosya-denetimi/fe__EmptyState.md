# Denetim: frontend/src/components/EmptyState.jsx

> **M86 güncellik:** 🟡 KISMEN-BAYAT — FES-001 düzeltildi; FES-002/003/005 açık


> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [FES-001] CTA butonlarinda type="button" eksik
Sorun: Buton elemanlarina explicit type verilmemis. HTML spesifikasyonuna gore bir <button>, bir <form> icinde render edildiginde varsayilan type="submit" olur. EmptyState bir form icinde kullanilirsa (orn. bos sonuc gosteren bir arama/filtre formu icinde), CTA tiklamasi beklenmedik sekilde formu submit edebilir.
Kanit (satir 35): <button onClick={onCta} className="btn btn-primary !text-xs mb-4">{ctaLabel}</button>
Kanit (satir 54): <button onClick={onCta} className="btn btn-primary !text-xs">{ctaLabel}</button>
Aksiyon: Her iki butona da type="button" ekle.
Onem: Orta · Guven: Kesin

### [FES-002] fullHeight ve normal dallarda tam kod tekrari
Sorun: Icon/baslik/aciklama/CTA/children render mantigi 22-39 ve 42-58 satirlari arasinda neredeyse birebir kopyalanmis; tek fark disaridaki wrapper className. Ileride bir alanin (orn. aria etiketi, className) sadece bir dalda guncellenip diger dalda unutulma riski var — zaten satir 24 (px-4, max-w-sm mb-4) ile satir 43-51 (px-8, max-w-sm mx-auto mb-4) arasinda ufak tutarsizliklar mevcut (mx-auto sadece ikinci dalda var, muhtemelen kasitli ama tekrar riskini gosteriyor).
Kanit (satir 22-58)
Aksiyon: Ortak govdeyi tek bir icerik degiskenine/alt bilesene cikarip sadece disaridaki wrapper'i kosullu yap.
Onem: Dusuk · Guven: Kesin

### [FES-003] Baslik seviyesi (h3) sabit, cagiran baglamdan bagimsiz
Sorun: title her zaman <h3> olarak render ediliyor (satir 30, 49). EmptyState farkli panellerde farkli baslik hiyerarsi derinliklerinde kullanilabilir; eger cagiran sayfada h1/h2 atlanip dogrudan h3'e gecerse WCAG 1.3.1 (baslik hiyerarsisi) ihlali olusabilir. Bu dosyanin kendisinde bug yok ama bilesen kullanim yerlerinde dogrulanmadan garanti edilemez.
Kanit (satir 30, 49)
Aksiyon: Gerekirse headingLevel prop'u ekleyip cagiran taraftan kontrol edilebilir hale getir; kullanim yerlerinde h3 sonrasi/oncesi hiyerarsi kontrol edilmeli.
Onem: Dusuk · Guven: Dogrulanmali

### [FES-004] Icon prop tip/varliginin dogrulanmamasi
Sorun: icon prop'u dogrudan JSX component olarak invoke ediliyor (<Icon .../>, satir 27 ve 46). PropTypes veya TS tip kontrolu yok; caller yanlislikla bir React elementi (JSX instance, orn. <Foo/>) yerine component referansi vermek zorunda ama bunu zorlayan hicbir mekanizma yok. Yanlis kullanimda (orn. icon={<Foo/>} verilirse) "Icon is not a function" tarzi runtime hatasi olusur, derleme zamaninda yakalanmaz.
Kanit (satir 14, 25-28, 44-47)
Aksiyon: JSDoc'a icon prop'unun component referansi (JSX degil) olmasi gerektigini acikca belirten bir ornek eklenebilir; proje genelinde PropTypes kullanilmiyorsa bu düşük öncelikli kalir.
Onem: Dusuk · Guven: Dogrulanmali

### [FES-005] ctaLabel/onCta'nin biri verilip digeri verilmezse sessiz gorunmezlik
Sorun: satir 34 ve 53'teki kosul {ctaLabel && onCta && (...)} — gelistirici sadece ctaLabel verip onCta'yi unutursa (veya tam tersi) buton hic render edilmez, konsola hicbir uyari/hata dusmez. Debug sirasinda "butonum neden gorunmuyor" turu sessiz hatalara yol acabilir.
Kanit (satir 34, 53)
Aksiyon: Development modunda console.warn ile eksik prop kombinasyonu icin uyari eklenebilir (opsiyonel, dusuk oncelik).
Onem: Dusuk · Guven: Kesin

Genel not: Dosyada api.js disi fetch, useEffect/temizlik, key/index-key, stale closure, kontrolsuz input, tarih parse (UTC 'Z') konularina iliskin bulgu yok — bilesen tamamen saf/stateless prezentasyonel bir bilesen, bu kategoriler dosyaya uygulanmiyor.
