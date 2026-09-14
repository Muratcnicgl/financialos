// DVIZ-011 (BUG #495): tarayıcıda blob indirme — Hesap panelindeki JSON dökümüyle aynı yol.
export function dosyaIndir(blob, ad) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = ad;
  a.click();
  URL.revokeObjectURL(url);
}
