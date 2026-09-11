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

## Commit mesajı ve izlenebilirlik (DOCS-007 / DOCS-013)
Ölçüldü (11 Eyl 2026): son 40 commit'in 33'ü bir kimlik taşıyor. Konvansiyon yazılı olsun
ki geri kalan 7 gibi olmasın:

- **Başlık:** `tip(kapsam): ölçülen sorun — sonuç` · tip ∈ `fix feat docs test chore` ·
  kapsam Türkçe (`koc`, `kapi`, `guvenlik`, `veri`, `arayuz`, `erisilebilirlik`…).
  Başlık bir İÇGÖRÜ olsun, dosya listesi değil: *"sir taramasi commit aninda sorulmuyordu"*.
- **Gövde:** ilk satırda `BUG #NNN` (sıradaki numara: `uygulanan-fixler.md`'deki son + 1) ve
  ilgili backlog kodu (`SEC-004`, `DATA-032`…). Sonra üç blok: **ne ölçüldü** (sayıyla),
  **ne değişti ve neden bu yol**, **kapı nasıl doğrulandı** (mutasyon: kapı kaldırılınca
  kırmızı mı?). Mesaj değişikliği anlatır, süreci değil: dosya listesi ve araç çıktısı yerine
  ölçüm ve gerekçe.
- **Her commit'in üç eşi vardır:** `docs/kalite-seruveni/sections/<BOYUT>.md`'de madde durumu
  (🟡→✅, tarih ve BUG # ile), `python scripts/backlog_ozeti.py --yaz` (indeks ve öncelik
  bloğu ÜRETİLİR, elle yazılmaz), `uygulanan-fixler.md`'ye defter satırı (bulgu · ayrıntı ·
  dosya · kanıt · durum).
- **Kapı yoksa iddia yoktur:** bir maddeyi ✅ yapan değişiklik `tests/*_kapisi.py` (ya da
  `frontend/src/*.test.jsx`) altında kaynaktan TÜRETİLEN bir testle kilitlenir; elle
  liste yerine tarama; muafiyet varsa gerekçesiyle ve testin içinde (sessiz muafiyet yok).

## Yerel kapılar (commit engellenirse)
- `python scripts/kalite_kapisi.py` — ruff gerileme sayacı (B/E9/F/S aile bazında TAVAN).
  Tavanı yükseltmek değil, ihtiyacı kaldırmak beklenir; düşerse `--yaz` tavanı indirir.
- `python -m scripts.sir_taramasi --staged` — indeksteki sır izi. Uydurma örnek için
  satıra (ya da bir üstüne) `# secret-ornek:` işareti.
- Docs/frontend-only commit'lerde `tests/*_kapisi.py` altkümesi koşar (~2,5 dk); `.py`
  değişince tam süit (~4-10 dk).
- CI ayrıca `.env`'siz ve **PostgreSQL** ile koşar: yerelde çift-lehçe kapıları için
  `tests/pg_gate.py` başlığındaki tarif (`pip install pgserver`, `initdb --locale=C`).
