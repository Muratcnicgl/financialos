// DEVOPS-003 (BUG #474): frontend lint standardı — tek dosya, düz (flat) config.
// Kurallar: ESLint önerilenleri + React (JSX) + react-hooks önerilenleri (FE-028: exhaustive-deps
// ve React Compiler dönemi kuralları: refs, immutability, static-components, rules-of-hooks).
// Biçimlendirici (prettier) BİLEREK yok: mevcut kod tek bir stil izlemiyor, toptan yeniden
// biçimlendirme 200+ dosyada anlamsız diff üretir ve git blame'i bozar; kural motoru
// (hata/kokuyu yakalayan) biçimden bağımsız olarak değer taşır.
//
// Uyarı (warn) seviyesindeki kurallar SIFIR DEĞİL, TAVANLI: sayıları `docs/kalite-seruveni/
// kalite-baseline.json` › frontend.tavan tutar, `scripts/eslint_kapisi.py` ölçer; artarsa kapı
// kırılır, düşerse tavan iner (ruff sayacıyla aynı felsefe: hedef koyma, gerilemeyi yakala).
import js from '@eslint/js';
import globals from 'globals';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';

export default [
  { ignores: ['dist/**', 'dev-dist/**', 'node_modules/**', 'playwright-report/**', 'test-results/**'] },
  js.configs.recommended,
  {
    files: ['**/*.{js,jsx,mjs,cjs}'],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: 'module',
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: { ...globals.browser, ...globals.node, ...globals.es2021 },
    },
    plugins: { react, 'react-hooks': reactHooks },
    settings: { react: { version: 'detect' } },
    rules: {
      ...react.configs.flat.recommended.rules,
      ...reactHooks.configs['recommended-latest'].rules,
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'off',
      'react/no-unescaped-entities': 'off',
      'no-console': ['warn', { allow: ['warn', 'error'] }],
      // Effect içinde eşzamanlı setState: 27 mevcut yer (ölçüm 14 Eyl 2026). Çoğu "veri gelince
      // türetilmiş durumu sıfırla" deseni; toptan yeniden yazmak davranış riski taşır. Tavanla
      // izlenir, dosyaya dokunuldukça eritilir.
      'react-hooks/set-state-in-effect': 'warn',
    },
  },
  {
    files: ['**/*.cjs'],
    languageOptions: { sourceType: 'commonjs' },
  },
  {
    files: ['**/*.test.{js,jsx}', 'e2e/**', 'src/test-setup.js'],
    languageOptions: { globals: { ...globals.node, ...globals.vitest, ...globals.jest } },
    rules: { 'no-console': 'off' },
  },
];
