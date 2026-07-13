# Katkıda Bulunma (Contributing)

FinancialOS açık kaynak (self-host). Katkılar hoş karşılanır.

## Geliştirme kurulumu
```bash
git clone <repo> && cd financialos
python -m venv venv && ./venv/Scripts/pip install -r requirements.txt
cp .env.example .env   # en az bir LLM key + SECRET_KEY
./venv/Scripts/python -m alembic upgrade head
./venv/Scripts/python -m scripts.setup_data   # demo veri (opsiyonel)
uvicorn app.main:app --reload   # backend :8000
cd frontend && npm install && npm run dev   # :5173
```

## Kurallar
- **Test kapısı zorunlu:** `bash scripts/install-hooks.sh` (commit-öncesi pytest/vitest, W3-058).
- **Mimari (ADR-001):** Rules Engine karar verir, LLM açıklar. Matematiksel hesap
  `rules_engine.py`'de; LLM (coach.py) yalnız cockpit'i açıklar, DB yazmaz.
- **Şema (ADR-013):** Yeni tablo/kolon → Alembic migration (production'da create_all yasak).
- **Türkçe alan adları korunur** (nakit_kasa vb.), backend→frontend mapping yok.
- **Para:** Decimal (Numeric 19,4); frontend TR-locale (`parseTRNumber`).

## PR akışı
1. Branch aç, testleri yeşil tut (`pytest tests/ -q` + `cd frontend && npx vitest run`).
2. `docs/kalite-seruveni/uygulanan-fixler.md`'ye satır ekle (bug/feature ID).
3. PR aç; CI (Wave-4) + review.

## Denetim metodolojisi
`docs/kalite-seruveni/` — 18 boyut, R3 (disk>memory), K10, OTONOM KARAR protokolü.
