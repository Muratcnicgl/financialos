// FE-021 (BUG #485): TEFAS fon sayfası URL'i — arayüzde TEK yer.
// Biçim backend `app/fund_tracker.py::get_tefas_url` ile aynıdır; `tests/test_sikistirma_ve_tefas_kapisi.py`
// iki dili aynı örnekte karşılaştırır (iki kopya, tek gerçek). Fon kodu büyük harfe çevrilir
// (backend ile aynı kural; TEFAS küçük harfli kodu bulamaz).
export function tefasUrl(fundCode) {
  return `https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod=${String(fundCode || '').toUpperCase()}`;
}
