// M64: vitest global setup — testing-library jest-dom matcher'ları + cleanup.
import '@testing-library/jest-dom';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => {
  cleanup();
  // UX-037 (BUG #462): paneller filtre tercihini localStorage'da tutar; aynı jsdom'da koşan
  // testler birbirinin tercihini görmesin (ilk koşumda 4 test bir öncekinin filtresiyle kırıldı).
  try { localStorage.clear(); } catch { /* depolama yok */ }
});
