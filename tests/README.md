# Test Coverage Raporu (M27, 14 Tem 2026)

**TOTAL: %87** (7554 satır, 1003 eksik) · **897 test** + 33 vitest · 1 skipped.

## Komut
```
.\venv\Scripts\python.exe -m pytest tests/ -q --cov=app --cov-report=term-missing --cov-report=html
```

## Kritik Modül Durumu (hedef %80)
| Kategori | Modüller | Kapsam |
|----------|----------|--------|
| ✅ Çekirdek motor | rules_engine, action_executor, coach, debt_strategy, simulation_engine, grounding | %80-97 (Wave-2 disiplinli) |
| ✅ Auth (M11+) | auth, settings, rate_limit, serializers | yüksek |
| ✅ startup.py | catch_up_snapshots | **%100** (M27, 0→100) |
| ⚠️ Router (integration) | expenses %52, goals %58, incomes/reports %70, accounts/debts %73 | endpoint testleri ince |
| ⚠️ External provider | evds_client %47, oauth %61, yfinance %64 | canlı env-bağımlı (mock-sınırlı) |
| ⚠️ scheduler/premortem/fund_tracker | %61-62 | kısmi |

## Hedef (sonraki turlar / Wave-4)
- Router coverage %80: her router için happy-path + error-path endpoint testi (integration).
- External provider: exchange_code/get_evds_price dal testleri (mock derinliği).
- **Not:** çekirdek finansal-doğruluk modülleri zaten yüksek — en yüksek risk kapsanmış.
  Düşük kapsam alanları ya integration-surface (router) ya da env-bağımlı (external) —
  regresyon riski görece düşük.
