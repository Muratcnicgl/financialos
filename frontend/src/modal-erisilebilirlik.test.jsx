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
