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

function etiketsizIkonButonlar() {
  const bulgular = [];
  for (const f of jsxDosyalari(KOK)) {
    const s = readFileSync(f, 'utf-8');
    const acilis = /<button\b[^>]*?>/gs;
    let m;
    while ((m = acilis.exec(s)) !== null) {
      const tag = m[0];
      const kapanis = s.indexOf('</button>', m.index + tag.length);
      if (kapanis < 0) continue;
      const ic = s.slice(m.index + tag.length, kapanis);
      if (tag.includes('title=') && !tag.includes('aria-label') && ikonOnly(ic)) {
        bulgular.push(`${f.split('src')[1]}: ${tag.slice(0, 80)}`);
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
});
