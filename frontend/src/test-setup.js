// M64: vitest global setup — testing-library jest-dom matcher'ları + cleanup.
import '@testing-library/jest-dom';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

afterEach(() => cleanup());
