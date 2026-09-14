/**
 * UX-034 (BUG #506): mikro-kopya — kullanıcıya görünen metin Türkçe yazımda ve sözlük terimleriyle.
 *
 * Ölçüm (14 Eyl 2026, kaynak taraması): kullanıcıya görünen 2 metin bozuktu — App.jsx rozet
 * ipucu ASCII'ye düşmüş ("Bugunku LLM cagri kullanimi…"), kokpit "Nakit runway" İngilizce
 * (sözlük: nakit pisti). Başlık/cümle büyük-küçük harf farkı (Günlük limit / günlük limit)
 * bağlama bağlıdır, kural değildir. Kilitlenen:
 *  - kullanıcıya görünen öznitelik (title/aria-label/placeholder/alt) ve metin düğümlerinde
 *    ASCII'ye düşmüş Türkçe sözcük yok (belirsizliksiz sözlük: gunluk, bugunku, cagri, …),
 *  - "runway" kullanıcı metninde geçmez (sözlük terimi "nakit pisti"; alan adı `nakit_runway_gun` kalır).
 */
import { describe, it, expect } from 'vitest';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';

const KOK = __dirname;
const ASCII_TR = /\b(gunluk|bugunku|cagri|kullanimi|yuzdesi|sozlesme\w*|gorulen|basarili|basarisiz|yukleniyor|guncelle\w*|olustur\w*|degistir\w*|tesekkur\w*|islem\w*|odeme\w*|gecmis\w*|uyari\w*|butce\w*)\b/;
const TR_HARF = /[çğıöşüÇĞİÖŞÜ]/;

function jsx(dir, out = []) {
  for (const ad of readdirSync(dir)) {
    const yol = join(dir, ad);
    if (statSync(yol).isDirectory()) jsx(yol, out);
    else if (ad.endsWith('.jsx') && !ad.includes('.test.')) out.push(yol);
  }
  return out;
}

function gorunenMetinler(s) {
  const sonuc = [];
  for (const m of s.matchAll(/(?:title|aria-label|placeholder|alt)=["']([^"']+)["']/g)) sonuc.push({ metin: m[1], index: m.index });
  for (const m of s.matchAll(/>\s*([^<>{}]+?)\s*</g)) if (m[1].trim().length > 3) sonuc.push({ metin: m[1].trim(), index: m.index });
  return sonuc;
}

describe('UX-034 — mikro-kopya', () => {
  it('kullanıcıya görünen metinde ASCII\'ye düşmüş Türkçe yok', () => {
    const bulgular = [];
    for (const f of jsx(KOK)) {
      const s = readFileSync(f, 'utf-8');
      for (const { metin, index } of gorunenMetinler(s)) {
        if (ASCII_TR.test(metin) && !TR_HARF.test(metin) && !/[=;{}]/.test(metin)) {
          bulgular.push(`${f.split('src')[1]}:${s.slice(0, index).split('\n').length} ${metin.slice(0, 60)}`);
        }
      }
    }
    expect(bulgular).toEqual([]);
  });

  it('"runway" kullanıcı metninde geçmez (sözlük: nakit pisti)', () => {
    const bulgular = [];
    for (const f of jsx(KOK)) {
      const s = readFileSync(f, 'utf-8');
      for (const { metin, index } of gorunenMetinler(s)) {
        if (/\brunway\b/i.test(metin)) bulgular.push(`${f.split('src')[1]}:${s.slice(0, index).split('\n').length}`);
      }
    }
    expect(bulgular).toEqual([]);
  });
});
