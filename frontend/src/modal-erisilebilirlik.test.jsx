/**
 * A11Y-001 KAPISI (BUG #395) — ORTAK MODAL ERİŞİLEBİLİR.
 *
 * Ölçülen (11 Eyl 2026): 14 dosyada tam-ekran kaplama var, 4'ünde `role="dialog"`; dört
 * panel (Accounts, IncomeDebt, RedLines, Transactions) birbirinin kopyası, erişilemez bir
 * `Modal` sarmalayıcı taşıyordu (rol yok, başlık bağı yok, Escape yok, odak yönetimi yok).
 * Kopya sayısı kadar düzeltme yerine tek bileşen; dört panel yalnız içe aktarır.
 *
 * Kilitlenen: rol/aria-modal/başlık bağı · açılışta odak içeride, kapanışta tetikleyene
 * dönüş · Escape kapatır · Tab kutunun içinde döner · dört panelde yerel Modal yok.
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import Modal from './components/Modal.jsx';

function kur(onClose = vi.fn()) {
  const tetik = document.createElement('button');
  tetik.textContent = 'aç';
  document.body.appendChild(tetik);
  tetik.focus();
  const r = render(
    <Modal title="Deneme başlığı" onClose={onClose}>
      <input aria-label="ilk" />
      <button type="button">son</button>
    </Modal>
  );
  return { ...r, onClose, tetik };
}

describe('A11Y-001 — ortak Modal', () => {
  it('rol, aria-modal ve başlık bağı', () => {
    kur();
    const d = screen.getByRole('dialog');
    expect(d).toHaveAttribute('aria-modal', 'true');
    expect(d).toHaveAccessibleName('Deneme başlığı');
  });

  it('açılışta odak içeriğin ilk alanında (Kapat düğmesinde değil), kapanışta tetikleyene döner', () => {
    const { unmount, tetik } = kur();
    expect(document.activeElement).toBe(screen.getByLabelText('ilk'));
    unmount();
    expect(document.activeElement).toBe(tetik);
    tetik.remove();
  });

  it('Escape kapatır', () => {
    const { onClose } = kur();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('Tab son öğeden ilk odaklanabilire (Kapat), Shift+Tab oradan sona döner', () => {
    kur();
    const kapat = screen.getByRole('button', { name: 'Kapat' });
    const son = screen.getByRole('button', { name: 'son' });
    son.focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(document.activeElement).toBe(kapat);
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(document.activeElement).toBe(son);
  });

  it('dört panel yerel Modal tanımlamaz, ortak olanı içe aktarır', () => {
    for (const p of ['Accounts', 'IncomeDebt', 'RedLines', 'Transactions']) {
      const src = readFileSync(join(__dirname, 'panels', `${p}.jsx`), 'utf-8');
      expect(src, `${p}: yerel Modal`).not.toMatch(/function Modal\(/);
      expect(src, `${p}: ortak Modal içe aktarılmamış`).toMatch(/import Modal from '\.\.\/components\/Modal\.jsx'/);
    }
  });
});

// ── BUG #396: kendi düzenini taşıyan diyaloglar da aynı davranışı alır ────────────────
import { readdirSync, statSync } from 'node:fs';

function jsxDosyalari(dir, out = []) {
  for (const ad of readdirSync(dir)) {
    const yol = join(dir, ad);
    if (statSync(yol).isDirectory()) jsxDosyalari(yol, out);
    else if (ad.endsWith('.jsx') && !ad.includes('.test.')) out.push(yol);
  }
  return out;
}

describe('A11Y-001 — tam-ekran kaplama taşıyan her dosya diyalog rolü taşır', () => {
  it('kaplama sayısı = dialog rolü sayısı (dosya bazında); davranış tek kaynaktan', () => {
    let kaplama = 0, hook = 0;
    for (const f of jsxDosyalari(__dirname)) {
      // Yorum satırları sayılmaz (Modal.jsx docstring'i rolü anlatır, taşımaz).
      const src = readFileSync(f, 'utf-8').split('\n').filter((l) => !/^\s*(\*|\/\/|\/\*)/.test(l)).join('\n');
      const k = (src.match(/fixed inset-0/g) || []).length;
      if (k === 0) continue;
      kaplama += k;
      const rol = (src.match(/role="dialog"/g) || []).length;
      const paylasilan = /import Modal from '\.\.\/components\/Modal\.jsx'/.test(src);
      expect(rol > 0 || paylasilan, `${f.split('src')[1]}: kaplama var, dialog rolü yok`).toBe(true);
      if (!paylasilan) expect(rol, `${f.split('src')[1]}: ${k} kaplama / ${rol} dialog`).toBe(k);
      if (/useDialog\(/.test(src)) hook += 1;
    }
    expect(kaplama, 'kapsam tabanı (L45)').toBeGreaterThanOrEqual(10);
    expect(hook, 'useDialog benimseyen DOSYA sayısı — ölçülen 7 (6 dosyada 7 diyalog + ortak Modal)').toBeGreaterThanOrEqual(7);
  });
});
