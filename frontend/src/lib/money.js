/**
 * PARA BİÇİMLENDİRME — FRONTEND TEK KAYNAK (H4 / ADR-042 3. aşama, BUG #256).
 *
 * NEDEN BU DOSYA VAR
 * ------------------
 * Para biçimlendirme frontend'de DÖRT ayrı yerde bağımsız yazılmıştı:
 *   1. `api.js` → `formatTL` / `formatTLSuffix` (tr-TR sabit, sonek elle ' TL')
 *   2. `panels/DebtStrategy.jsx` → yerel `TL()` (`style:'currency'`, null'da "₺0" — formatTL '—' derken)
 *   3. `components/HorizonsModal.jsx` → kendi `toLocaleString` + elle ' TL'
 *   4. `components/PremortemModal.jsx` → kendi `toLocaleString` + elle ' TL'
 * Ayrıca 21 üretim dosyasında 91 satırda ham `" TL"` metni ve 12 form etiketinde `"(TL)"`.
 *
 * Aynı kuralın çok yerde kodlanması bu projenin en pahalı hata sınıfıdır (BUG #161/SBN-001
 * ailesi; ders **L26**: bir kuralın gücü, kaynağı SEÇEN kod sayısı kadardır). Dört uygulama
 * dört farklı davranış üretiyordu: biri null'ı '—' yapıyor, biri '₺0'; biri 2 ondalık,
 * biri 0 ondalık; biri sembol, biri sonek.
 *
 * KAPSAM (bilinçli sınır)
 * -----------------------
 * Bu modül GÖRÜNTÜLEME katmanıdır. Çoklu para birimiyle hesap tutma (kur çevrimi, tarihsel
 * kur) KAPSAM DIŞIDIR — ayrı ADR gerektirir. Desteklenen tek para birimi: TRY. Backend de
 * aynı kararı `app/money_format.py` ile taşır; ikisi `PARA_BIRIMI` tanımında hizalıdır.
 */

/** Backend `app/money_format.PARA_BIRIMLERI` ile hizalı olmalı (tek para birimi: TRY). */
export const PARA_BIRIMI = {
  kod: 'TRY',
  etiket: 'TL',
  simge: '₺',
  locale: 'tr-TR',
  ondalik: 2,
};

const _formatlayicilar = new Map();

function _formatlayici(ondalik) {
  const anahtar = `${PARA_BIRIMI.locale}:${ondalik}`;
  if (!_formatlayicilar.has(anahtar)) {
    _formatlayicilar.set(
      anahtar,
      new Intl.NumberFormat(PARA_BIRIMI.locale, {
        minimumFractionDigits: ondalik,
        maximumFractionDigits: ondalik,
      }),
    );
  }
  return _formatlayicilar.get(anahtar);
}

/**
 * Sayıyı kullanıcının biçiminde yazar — para ETİKETİ EKLEMEZ.
 * 1234.56 -> "1.234,56" · null/NaN -> "—"
 */
export function formatSayi(amount, { compact = false, ondalik } = {}) {
  if (amount === null || amount === undefined || Number.isNaN(Number(amount))) return '—';
  const basamak = ondalik !== undefined ? ondalik : (compact ? 0 : PARA_BIRIMI.ondalik);
  return _formatlayici(basamak).format(amount);
}

/**
 * Kullanıcıya gösterilecek para metni — ETİKETLİ.
 * 1234.56 -> "1.234,56 TL" · null -> "—"
 *
 * Ham `" TL"` yazmak yerine BUNU kullan: etiket tek kaynaktan gelir ve para birimi kararı
 * değişirse tüm arayüz birlikte değişir (statik kapı: `tests/test_para_birimi_kapisi.py`).
 */
export function formatPara(amount, opts) {
  const sayi = formatSayi(amount, opts);
  if (sayi === '—') return sayi;
  return `${sayi} ${PARA_BIRIMI.etiket}`;
}

/** Form etiketi vb. için yalnız birim: "TL". */
export function paraEtiketi() {
  return PARA_BIRIMI.etiket;
}

/** Kompakt/sembol gösterim: 1234.56 -> "₺1.235" (grafik ekseni, dar alan). */
export function formatParaSimge(amount, opts) {
  const sayi = formatSayi(amount, { compact: true, ...opts });
  if (sayi === '—') return sayi;
  return `${PARA_BIRIMI.simge}${sayi}`;
}
