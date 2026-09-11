/**
 * A11Y-010 KAPISI (kalan yarı) — MEŞGULKEN BUTONUN ERİŞİLEBİLİR ADI DÜŞMEMELİ.
 *
 * Ölçülen (11 Eyl 2026): `{busy ? <Loader2/> : 'Kaydet'}` deseni 5 dosyada 13 butonda —
 * meşgulken metin kaybolur, buton ekran okuyucuda ADSIZ kalır (WCAG 4.1.2) ve durum
 * değişimi duyurulmaz (4.1.3). Backlog "23 dosya" diyordu; ölçüm ikon↔ikon takasını
 * (`{busy ? <Loader2/> : <Send/>} Gönder` — metin ayrı, ad korunur) ayırdı: 13.
 *
 * Kilitlenen desen: spinner `&&` ile eklenir, metin hep durur, `<button aria-busy>`.
 * Kapı kaynağı tarar: sağ dalı metin olan `? <Loader2 .../> : …` ternary'si → 0.
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

// Sağ dal (etiketler ayıklanınca) bir STRING taşıyorsa buton metni ternary'nin içindedir
// ve meşgulken düşer. İkon↔ikon zinciri (`: isRegister ? <UserPlus/> : <LogIn/>`) metnini
// dışarıda tutar — etiketler ayıklanınca geriye string kalmaz, yakalanmaz (Login.jsx).
const DESEN = /\?\s*<Loader2[^>]*\/>\s*:\s*([^}]*)\}/g;

function metniDusenler(kaynak) {
  const b = [];
  let m;
  while ((m = DESEN.exec(kaynak)) !== null) {
    const sag = m[1].replace(/<[^>]*>/g, ' ');
    if (/['"`]/.test(sag)) b.push(m[0].slice(0, 70).replace(/\s+/g, ' '));
  }
  return b;
}

describe('A11Y-010 — meşgul butonun adı', () => {
  it('meşgulken metni kaybolan buton YOK', () => {
    const bulgular = [];
    for (const f of jsxDosyalari(KOK)) {
      for (const b of metniDusenler(readFileSync(f, 'utf-8'))) bulgular.push(`${f.split('src')[1]}: ${b}`);
    }
    expect(bulgular, `metni düşen buton:\n${bulgular.join('\n')}`).toEqual([]);
  });

  it('kapı kendisi çalışıyor: metin dalı yakalanır, ikon↔ikon takası yakalanmaz', () => {
    expect(metniDusenler(`{busy ? <Loader2 className="w-4" /> : 'Kaydet'}`)).toHaveLength(1);
    expect(metniDusenler(`{busy ? <Loader2 /> : (isNew ? 'Ekle' : 'Kaydet')}`)).toHaveLength(1);
    expect(metniDusenler(`{busy ? <Loader2 /> : <Send />} Gönder`)).toHaveLength(0);
    expect(metniDusenler(`{busy ? <Loader2 className="w-4" />
 : isRegister ? <UserPlus className="w-4" />
 : <LogIn />}
{submitLabel}`)).toHaveLength(0);
    expect(metniDusenler(`{busy && <Loader2 aria-hidden="true" />}{'Kaydet'}`)).toHaveLength(0);
  });

  it('kilitlenen desen: aria-busy taşıyan her buton spinner + metin', () => {
    let sayi = 0;
    for (const f of jsxDosyalari(KOK)) {
      const s = readFileSync(f, 'utf-8');
      const acilis = /<button\b[^>]*aria-busy=\{(\w+)\}[^>]*>/g;
      let m;
      while ((m = acilis.exec(s)) !== null) {
        const ic = s.slice(m.index + m[0].length, s.indexOf('</button>', m.index));
        expect(ic, `${f.split('src')[1]}: aria-busy var ama spinner && ile değil`).toMatch(new RegExp(`\{${m[1]} && <Loader2`));
        sayi += 1;
      }
    }
    expect(sayi, 'kapsam tabanı: dönüştürülen 13 buton (L45)').toBeGreaterThanOrEqual(13);
  });
});
