#!/usr/bin/env node
// `npm run lint` giris noktasi. ESLint dogrudan degil bu sarmalayiciyla cagrilir, cunku
// @eslint/config-array icindeki Windows yol yardimcisi (std__path/windows: relative) iki yolu
// once toLowerCase() ile katlar, ortak on eki kucuk harfli dizede sayar, sonra ORIJINAL dizeyi
// ayni indeksle dilimler. "İ" (U+0130) kucuk harfe donusunce iki kod birimine acilir ("i" + U+0307);
// sonuc bir karakter kayar ("ode_modules/...") ve ignore eslestirmesi hicbir seyi tanimaz:
// node_modules/ ve dist/ dahil her dosya lintlenir, dakikalarca surer, sahte bulgu yagar.
// Node'un kendi path.relative'i bu hatayi tasimaz; belirti yalnizca ESLint'in kopyasinda.
// Cozum: calisma dizini kucuk harfe katlaninca uzuyorsa ESLint dizinin 8.3 kisa (ASCII) adiyla
// calistirilir. Windows disinda ve ASCII yollarda hicbir sey degismez.
const path = require('node:path');
const { execFileSync, spawnSync } = require('node:child_process');

function katlaninaUzuyorMu(yol) {
  return yol.toLowerCase().length !== yol.length;
}

function kisaYol(yol) {
  // Yol, kod sayfasi sorunlarina takilmasin diye PowerShell'e base64 (UTF-16LE) olarak gecer.
  const b64 = Buffer.from(yol, 'utf16le').toString('base64');
  const komut = `$p=[Text.Encoding]::Unicode.GetString([Convert]::FromBase64String('${b64}'));`
    + ' (New-Object -ComObject Scripting.FileSystemObject).GetFolder($p).ShortPath';
  return execFileSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', komut], { encoding: 'utf8' }).trim();
}

const kok = process.cwd();
let calismaDizini = kok;
if (process.platform === 'win32' && katlaninaUzuyorMu(kok)) {
  calismaDizini = kisaYol(kok);
  if (!calismaDizini || katlaninaUzuyorMu(calismaDizini)) {
    console.error('lint: dizin yolu ESLint ignore eslestirmesi icin guvenilir degil; ASCII bir yoldan calistirin.');
    process.exit(2);
  }
}

const eslintBin = path.join(calismaDizini, 'node_modules', 'eslint', 'bin', 'eslint.js');
const argv = process.argv.slice(2);
const hedefVar = argv.some((a) => !a.startsWith('-') && /\.(jsx?|mjs|cjs)$|^(src|e2e|scripts)\b/.test(a));
const hedefler = hedefVar ? argv : ['src', 'e2e', 'scripts', 'eslint.config.js', ...argv];
const sonuc = spawnSync(process.execPath, [eslintBin, ...hedefler], { cwd: calismaDizini, stdio: 'inherit' });
process.exit(sonuc.status ?? 1);
