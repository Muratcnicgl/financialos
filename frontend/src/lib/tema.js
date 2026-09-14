// MOB-009 (BUG #499): tema rengi — gövde zeminiyle aynı (Tailwind zinc-950 / zinc-50).
// `theme-init.js` (klasik script, import edemez) aynı iki değeri taşır; `mobil-kabuk.test.jsx`
// ikisini karşılaştırır. Hex burada ve grafikRenkleri.js'te yaşar; .jsx'te literal hex yasak (DVIZ-006).
export const TEMA_RENGI = { dark: '#09090b', light: '#fafafa' };
