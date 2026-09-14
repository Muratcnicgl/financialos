/**
 * A11Y-003 KAPISI — İKON-ONLY BUTON `title` İLE ADLANDIRILAMAZ.
 *
 * Ölçülen (11 Eyl 2026): kaynakta `title=` taşıyıp `aria-label` taşımayan 36 `<button>`
 * vardı; 28'i ikon-only (içinde düz metin yok). `title` fare için ipucudur — ekran
 * okuyucuda güvenilir bir erişilebilir ad DEĞİLDİR ve dokunmatikte hiç görünmez
 * (WCAG 4.1.2). Görünür metni olan butona `aria-label` EKLENMEZ: görünür metni ezer.
 *
 * Bu kapı kaynağı tarar: ikon-only + title var + aria-label yok → 0 olmalı.
 * Sayaç kaynaktan TÜRETİLİR; elle liste yok (L79).
 */
import { describe, it, expect } from 'vitest';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const KOK = join(__dirname);

function jsxDosyalari(dir, out = []) {
  for (const ad of readdirSync(dir)) {
    const yol = join(dir, ad);
    if (statSync(yol).isDirectory()) jsxDosyalari(yol, out);
    else if (ad.endsWith('.jsx') && !ad.includes('.test.')) out.push(yol);
  }
  return out;
}

function ikonOnly(ic) {
  return ic.replace(/<[^>]+>/g, ' ').replace(/\{[^{}]*\}/g, ' ').trim() === '';
}

// BUG #484 (FE-029): açılış etiketi `{...}` FARKINDALIĞIYLA okunur. Eski `/<button\b[^>]*?>/`
// `onClick={() => ...}` içindeki `=>` işaretinde duruyordu: etiket yarım okunuyor, `title=`
// görülmüyor, gövde "metinli" sanılıyordu — 5 ikon-only buton (CategoryManager) ve 2 Wishlist
// butonu kapıdan sessizce geçti. Kapı, korumak istediği şeyin yarısını görmüyordu.
export function acilisEtiketleri(s, ad = 'button') {
  const sonuc = [];
  let i = 0;
  for (;;) {
    const bas = s.indexOf(`<${ad}`, i);
    if (bas < 0) break;
    let derinlik = 0;
    let j = bas;
    for (; j < s.length; j += 1) {
      const ch = s[j];
      if (ch === '{') derinlik += 1;
      else if (ch === '}') derinlik -= 1;
      else if (ch === '>' && derinlik === 0) break;
    }
    if (j >= s.length) break;
    sonuc.push({ index: bas, tag: s.slice(bas, j + 1), sonu: j + 1 });
    i = j + 1;
  }
  return sonuc;
}

function etiketsizIkonButonlar() {
  const bulgular = [];
  for (const f of jsxDosyalari(KOK)) {
    const s = readFileSync(f, 'utf-8');
    for (const { index, tag, sonu } of acilisEtiketleri(s)) {
      if (tag.endsWith('/>')) continue;
      const kapanis = s.indexOf('</button>', sonu);
      if (kapanis < 0) continue;
      const ic = s.slice(sonu, kapanis);
      // Kapsam `title=` taşıyanlar: gövdesi `{ifade}` olan metinli butonlar ikon-only sanılır
      // (ölçüldü: kapsam genişletilince 40 yanlış pozitif) — `title` ipucu, "adım yok" itirafıdır.
      if (tag.includes('title=') && !tag.includes('aria-label') && !tag.includes('aria-labelledby') && ikonOnly(ic)) {
        bulgular.push(`${f.split('src')[1]}:${s.slice(0, index).split('\n').length} ${tag.replace(/\s+/g, ' ').slice(0, 90)}`);
      }
    }
  }
  return bulgular;
}

describe('A11Y-003 — ikon-only butonların erişilebilir adı', () => {
  it('title taşıyıp aria-label taşımayan ikon-only buton YOK', () => {
    const b = etiketsizIkonButonlar();
    expect(b, `aria-label eksik:\n${b.join('\n')}`).toEqual([]);
  });

  it('kapı kendisi çalışıyor: sentetik ikon-only buton yakalanır, metinli buton yakalanmaz', () => {
    expect(ikonOnly('<Trash2 size={14} />')).toBe(true);
    expect(ikonOnly('{loading ? <Loader2 /> : <Save />}')).toBe(true);
    expect(ikonOnly('<Save /> Kaydet')).toBe(false);
  });

  it('BUG #484: açılış etiketi `=>` içeren onClick ile bölünmez', () => {
    const kaynak = `<button type="button" onClick={() => sil(x)} title="Sil">\n  <Trash2 />\n</button>`;
    const [e] = acilisEtiketleri(kaynak);
    expect(e.tag).toContain('title="Sil"');
    expect(e.tag.endsWith('title="Sil">')).toBe(true);
    const kendinden = acilisEtiketleri('<button aria-label="x" onClick={() => a({ b: 1 })} />');
    expect(kendinden[0].tag.endsWith('/>')).toBe(true);
  });
});
