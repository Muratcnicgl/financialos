/**
 * ÖĞRETİCİ İÇERİĞİNİN TEK KAYNAĞI.
 *
 * Neden tek dosya: aynı açıklama üç yerde gösteriliyor — kurulum sihirbazı (ilk giriş),
 * panel içi ipucu satırı ve sağ alttaki yardım köşesi. Metni üç yere kopyalamak, üçünün
 * zamanla birbirinden ayrılması demektir (projede bunun bedeli ölçüldü: BUG #256 aynı
 * ekranda iki para biçimi, BUG #275 aynı kuralın iki kopyası). Bileşenler yalnız ÇİZER,
 * ne yazacağını buradan okur.
 *
 * Ton (KURAL 1 + app/uslup_kurallari.py): "sen" hitabı, dalkavukluk yok, dolgu yok.
 * Her `ornek` alanı GERÇEK bir örnektir — "örnek: bir hesap ekleyin" değil, kullanıcının
 * birebir yazabileceği bir şey. Öğretici, örnek göstermeyen bir metinden ibaret olamaz.
 */
import { formatPara } from './money.js';

/** Panel başına rehber. Anahtarlar App.jsx'teki TABS id'leriyle birebir aynı olmalı —
 *  `tests/ogretici.test.js` bunu kapıya bağlar (id değişip burası unutulursa kırmızı). */
const p = (n) => formatPara(n, { ondalik: 0 });   // örneklerde kısa gösterim

export const PANEL_REHBERI = {
  cockpit: {
    baslik: 'Cockpit',
    ozet: 'Paranın bugünkü tek ekranlık fotoğrafı: elinde ne var, ne kadarı borç, bugün ne kadar harcayabilirsin.',
    nasil: [
      'Üstteki dört sayı sırasıyla nakit, kart borcu, kredi borcu ve yatırım toplamıdır.',
      '"Günlük limit" ay sonuna kalan güne bölünmüş harcanabilir tutardır — bir bütçe değil, bir hız göstergesi.',
      'Uyarılar bölümü boşsa dikkat gerektiren bir şey yok demektir; boş bölüm hiç çizilmez.',
    ],
    ornek: `Nakit ${p(10350)}, kart borcu ${p(0)} ise günlük limit ≈ ${p(493)} (ay sonuna 21 gün kalmışken).`,
    ipucu: 'Sayılar burada hesaplanmaz, sadece gösterilir. Bir rakam yanlışsa kaynağı Hesaplar veya İşlemler panelindedir.',
  },

  coach: {
    baslik: 'Koç',
    ozet: 'Kendi rakamlarını bilen bir finans danışmanı. Soru sorabilir, olan biteni tek cümleyle bildirebilirsin.',
    nasil: [
      'Gerçekleşmiş bir şeyi bildir: koç kaydı hazırlar, SEN onaylayınca yazılır.',
      'Soru sor: koç yalnızca senin verinden cevaplar, tahmin uydurmaz.',
      'Onay kutusundaki tutar/tarih yanlışsa "Düzenle" ile değiştir — onaylamadan hiçbir şey kaydedilmez.',
    ],
    ornek: `"Bugün markete ${p(480)} verdim" → koç işlemi hazırlar. "Bu ay ne kadar harcayabilirim?" → koç cevaplar.`,
    ipucu: `İkisini aynı mesajda birleştirebilirsin: "${p(320)} harcadım, bütçem ne durumda?" Hem kayıt açılır hem soru cevaplanır.`,
  },

  accounts: {
    baslik: 'Hesaplar',
    ozet: 'Nakit, kredi kartı, kredi ve yatırım hesaplarının listesi. Diğer her şey buradaki bakiyelerden türer.',
    nasil: [
      'Her hesabın bir türü var: nakit, kredi kartı, kredi, yatırım. Tür, hesabın nasıl sayılacağını belirler.',
      'Kredi kartı ve kredi bakiyesi BORÇ olarak eksi girilir; nakit ve yatırım artı.',
      'Emanet işaretli hesap net değere girer ama harcanabilir sayılmaz — sana ait olmayan para için.',
    ],
    ornek: `Ad: "Vadesiz hesabım" · Tür: Nakit · Bakiye: ${p(12400)} — sonra kart için: "Kredi kartım" · Kredi kartı · ${p(-8750)}.`,
    ipucu: 'Maaş kartı ve yemek kartını ayrı hesap yap. Tek hesapta topladığında yemek kartı bakiyesi harcanabilir nakit gibi görünür.',
  },

  transactions: {
    baslik: 'İşlemler',
    ozet: 'Gelir ve giderlerin tek tek kaydı. Bir işlem girdiğinde ilgili hesabın bakiyesi kendiliğinden değişir.',
    nasil: [
      'Tutar, kategori, tarih ve hangi hesaptan çıktığı — dördü de gereklidir.',
      'Kategori bir kayıttır, serbest metin değil: kendi kategorini ekleyebilirsin.',
      'Kartla ödediysen işlemi kart hesabına yaz; nakit ödediysen nakit hesabına. Kategori bunu belirlemez, seçtiğin hesap belirler.',
    ],
    ornek: `${p(480)} · Market · bugün · "Vadesiz hesabım" hesabından.`,
    ipucu: 'Geçmiş bir günü girerken tarihi değiştirmeyi unutma — boş bırakılan tarih bugüne yazılır.',
  },

  incomedebt: {
    baslik: 'Gelir & Borç',
    ozet: 'Her ay tekrar eden gelir/giderler ve kişilerle olan borç-alacak ilişkilerin.',
    nasil: [
      'Düzenli gelir/gider bir kez tanımlanır, ayın belirttiğin gününde kendiliğinden işlenir.',
      'Kişisel borç iki yönlüdür: sana borçlu olan (alacak) ve senin borçlu olduğun.',
      'Alacak tahsil edilince işaretle — tutar nakde geçer, sadece listeden silinmez.',
    ],
    ornek: `Gelir: "Maaş" · ${p(21000)} · ayın 1'i. Gider: "Kira" · ${p(10000)} · ayın 1'i.`,
    ipucu: 'Düzenli gideri tanımladığın ay onu elle de girdiysen iki kez sayılmaz — otomatik kayıt bir sonraki aydan başlar.',
  },

  redlines: {
    baslik: 'Kırmızı Çizgiler',
    ozet: 'Kendi koyduğun, sistemin çiğnemesine izin vermediği kurallar. Koç bunları öneri diye değil, sınır olarak görür.',
    nasil: [
      'Bir kural yaz: "acil durum fonuna dokunma" gibi. Öncelik verirsen kritik olanlar önce uygulanır.',
      'Kural kod seviyesinde uygulanır; koç ikna edilerek aşılamaz.',
      'Artık geçerli değilse kapat — silmek zorunda değilsin, geçmişi kalır.',
    ],
    ornek: '"Emanet hesabındaki parayı hiçbir gerekçeyle harcama" · Öncelik: kritik.',
    ipucu: `Kuralı somut yaz. "Dikkatli harca" ölçülemez; "ayda ${p(5000)} üstü tek harcama yapma" ölçülebilir.`,
  },

  reports: {
    baslik: 'Raporlar',
    ozet: 'Nereye ne kadar gittiğinin aylık dökümü — kategori dağılımı, aylık karşılaştırma, net değer eğrisi.',
    nasil: [
      'Kategori grafiği bu ayın giderlerini büyükten küçüğe gösterir.',
      'Net değer eğrisi günlük kaydedilir; kayıt olduğun günden geriye veri yoktur.',
      'Bir kategori beklenenden büyükse üstüne tıklayıp o kategorinin işlemlerine inebilirsin.',
    ],
    ornek: 'Ağustos: Kira 10.000 · Market 3.240 · Ulaşım 890 → giderin %70\'i kira.',
    ipucu: 'İlk ayında grafikler zayıf görünür; anlamlı desen için en az birkaç haftalık kayıt gerekir.',
  },

  cashflow: {
    baslik: 'Akış',
    ozet: 'Önümüzdeki 30/60/90 günde paranın ne zaman gireceği ve çıkacağı — sıkışacağın günü önceden gösterir.',
    nasil: [
      'Takvim, bilinen düzenli gelir/giderlerinden ve taksitlerinden üretilir.',
      'En düşük bakiye noktası, o ufukta paranın en aza indiği gündür.',
      'Ufku 30/60/90 arasında değiştirerek yakın ve uzak resmi ayrı ayrı gör.',
    ],
    ornek: 'Maaş ayın 1\'i giriyor, kira aynı gün çıkıyorsa akış o günü nötr gösterir; kritik gün kiradan önceki gündür.',
    ipucu: 'Buradaki tahmin yalnızca tanımladığın düzenli kalemleri bilir. Eksik kalem varsa akış olduğundan iyimser çıkar.',
  },

  debtstrategy: {
    baslik: 'Borç Stratejisi',
    ozet: 'Birden fazla borcun varsa hangisine önce ödeme yapmanın daha ucuz olduğunu hesaplar.',
    nasil: [
      'Çığ yöntemi faizi en yüksek borcu önceler — toplamda en az faiz ödersin.',
      'Kartopu yöntemi en küçük borcu önceler — daha çabuk "bir borç bitti" hissi verir.',
      'İki yöntemin toplam maliyet farkı ekranda yazar; kararı ona bakarak ver.',
    ],
    ornek: `Kart %4,25 aylık ${p(8750)} · İhtiyaç kredisi %2,9 aylık ${p(24000)} → çığ yöntemi önce kartı kapatır.`,
    ipucu: 'Faiz oranını girmezsen sıralama yalnızca tutara göre yapılır ve yanıltır. Oranları hesap kartında güncelle.',
  },

  goals: {
    baslik: 'Hedefler',
    ozet: 'Birikim ve borçtan kurtulma hedefleri — mevcut hızınla ne zaman varacağını hesaplar.',
    nasil: [
      'Hedef tutarı ve tarihi gir; sistem gereken aylık tempoyu söyler.',
      'İlerleme gerçek verinden gelir, elle güncellemezsin.',
      'Tempo tutmuyorsa hedef "gecikmede" görünür — tarihi ya da tutarı gözden geçir.',
    ],
    ornek: `Hedef: "Acil durum fonu" · ${p(60000)} · 12 ay → ayda ${p(5000)} gerekir.`,
    ipucu: 'Aynı anda üç ya da daha az hedef tut. Fazlası tempoyu bölerken hiçbirini bitirmez.',
  },

  budget: {
    baslik: 'Bütçe',
    ozet: 'Kategori başına aylık zarf: ne kadar ayırdın, ne kadar harcadın, ne kadar kaldı.',
    nasil: [
      'Bir kategoriye aylık tutar ayır — o zarf her ay yenilenir.',
      'İşlem girdiğinde zarfın kalanı kendiliğinden düşer.',
      'Zarf aşıldığında çubuk kırmızıya döner; harcama engellenmez, sadece görünür olur.',
    ],
    ornek: `Market ${p(4000)} · Yeme-içme ${p(2500)} · Ulaşım ${p(1200)}.`,
    ipucu: 'Her kategoriye zarf açma. Üç-dört büyük kalemi kontrol etmek, on kalemi takip etmeye çalışmaktan iyi sonuç verir.',
  },

  workspace: {
    baslik: 'Aile',
    ozet: 'Ortak bir defter — eşin ya da ev arkadaşınla aynı hesapları paylaşmak için.',
    nasil: [
      'Kendi kişisel alanın her zaman ayrıdır; paylaşılan alan ondan bağımsızdır.',
      'Üyeleri e-posta ile davet edersin; rol verirsin (sahip / düzenleyici / görüntüleyici).',
      'Üstteki seçiciden hangi defterde çalıştığını değiştirirsin — girdiğin veri o deftere yazılır.',
    ],
    ornek: '"Ev" adında bir alan aç, eşini "düzenleyici" olarak davet et; kira ve market oraya, maaşın kendi alanına.',
    ipucu: 'Veri girmeden önce üstteki seçiciye bak. Yanlış deftere yazılan işlem taşınmaz, silinip yeniden girilir.',
  },

  hesap: {
    baslik: 'Hesap',
    ozet: 'E-posta, şifre, verilerini dışa aktarma ve hesabını silme. Kurulum rehberini de buradan geri açarsın.',
    nasil: [
      'Verini istediğin zaman tek dosya olarak indirebilirsin — kilit yok.',
      'Hesap silme geri alınamaz ve tüm kayıtlarını siler.',
      'Kapattığın kurulum rehberini buradan yeniden açabilirsin.',
    ],
    ornek: '"Verimi indir" → tüm hesap, işlem ve kurallarının tek dosyada kopyası.',
    ipucu: 'Şifreni değiştirdiğinde diğer cihazlardaki oturumlar kapanır — bu, çalınan bir oturumu iptal etmenin yoludur.',
  },
};

/**
 * KURULUM SİHİRBAZI — ilk girişte açılır, zorunlu değildir, her an kapatılır ve
 * yardım köşesinden yeniden başlatılır.
 *
 * `hedefSekme` verilen adımda "Şimdi yap" düğmesi kullanıcıyı doğrudan o panele götürür.
 * `dogrulama` alanı, adımın gerçekten yapılıp yapılmadığını BACKEND rehber durumundan
 * okur (`GET /api/onboarding/rehber` → `adimlar[].tamam`) — sihirbaz kendi başına
 * "yaptın sayıyorum" demez (BUG #262'nin dersi: adım durumu bir veri sorusudur).
 */
export const SIHIRBAZ_ADIMLARI = [
  {
    id: 'karsilama',
    baslik: 'Üç adımda kurulum',
    metin: 'Bu uygulama senin paranı takip eder ve sorularını kendi rakamlarınla cevaplar. ' +
           'Çalışması için üç şey gerekir: hesapların, harcamaların ve düzenli gelir-giderin. ' +
           'Yaklaşık üç dakika sürer, istediğin an bırakabilirsin.',
    ornek: null,
    hedefSekme: null,
  },
  {
    id: 'hesap_ekle',
    baslik: 'Hesaplarını ekle',
    metin: 'Nereye ne kadar paran olduğunu gir. Kredi kartı ve kredi borçlarını da ekle — ' +
           'borcu görmeyen bir tablo işe yaramaz.',
    ornek: `Vadesiz hesabım · Nakit · ${p(12400)}\nKredi kartım · Kredi kartı · ${p(-8750)}`,
    hedefSekme: 'accounts',
    dogrulamaAnahtari: 'hesap',
  },
  {
    id: 'islem_gir',
    baslik: 'Bir harcama gir',
    metin: 'Bugün yaptığın bir harcamayı kaydet. Tutarı, kategoriyi ve hangi hesaptan ' +
           'çıktığını seç — bakiye kendiliğinden düşer.',
    ornek: `${p(480)} · Market · bugün · Vadesiz hesabım`,
    hedefSekme: 'transactions',
    dogrulamaAnahtari: 'islem',
  },
  {
    id: 'duzenli',
    baslik: 'Düzenli gelir ve giderini tanımla',
    metin: 'Her ay tekrar eden kalemleri bir kez yaz; sistem onları kendiliğinden işler ve ' +
           'ileriye dönük akışını buradan hesaplar.',
    ornek: `Maaş · ${p(21000)} · ayın 1'i\nKira · ${p(10000)} · ayın 1'i`,
    hedefSekme: 'incomedebt',
  },
  {
    id: 'kural_yaz',
    baslik: 'Kendi kuralını koy',
    metin: 'Bir kırmızı çizgi yaz — senin izin vermediğin şeyi sistem de yapmaz. ' +
           'Koç bu kuralı öneri değil sınır kabul eder ve ikna edilerek aşamaz.',
    ornek: '"Acil durum fonuna hiçbir gerekçeyle dokunma"',
    hedefSekme: 'redlines',
    dogrulamaAnahtari: 'kural',
  },
  {
    id: 'koca_sor',
    baslik: 'Koça bir soru sor',
    metin: 'Koç senin rakamlarını görür. Bir şey uydurmaz; veri yoksa yok der. ' +
           'Gerçekleşmiş bir harcamayı da tek cümleyle bildirebilirsin — onayı sen verirsin.',
    ornek: `"Bu ay ne kadar harcayabilirim?"\n"Bugün markete ${p(480)} verdim"`,
    hedefSekme: 'coach',
    dogrulamaAnahtari: 'koc',
  },
  {
    id: 'bitti',
    baslik: 'Kurulum tamam',
    metin: 'Bundan sonrası birikimli çalışır: ne kadar çok işlem girersen tahminler o kadar ' +
           'isabetli olur. Takıldığın yerde sağ alttaki yardım düğmesi her panelde durur.',
    ornek: null,
    hedefSekme: null,
  },
];

/** Yardım köşesindeki sabit girdiler (panel rehberinin altında listelenir). */
export const YARDIM_BAGLANTILARI = [
  { id: 'sihirbaz', etiket: 'Kurulum sihirbazını başlat',
    aciklama: 'Adım adım kurulum — istediğin adımdan devam edersin.' },
  { id: 'kisayol', etiket: 'Klavye kısayolları',
    aciklama: 'Sık kullanılan hareketlerin tuş karşılıkları.' },
  { id: 'ornek_veri', etiket: 'Örnek veriyle gez',
    aciklama: 'Kendi verini girmeden nasıl göründüğüne bak; tek tuşla kaldırılır.' },
  { id: 'geri_bildirim', etiket: 'Sorun bildir',
    aciklama: 'Takıldığın ya da yanlış gördüğün şeyi yaz.' },
];

/** Panel rehberini güvenli getir — bilinmeyen sekme için null (bileşen hiç çizmez). */
export function panelRehberi(sekmeId) {
  return PANEL_REHBERI[sekmeId] ?? null;
}
