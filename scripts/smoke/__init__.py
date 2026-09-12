"""Elle koşulan duman betikleri (TEST-032 / BUG #431).

Bunlar pytest testi DEĞİLDİR: gerçek DB'ye (`.env`'deki DATABASE_URL) ve bazıları gerçek
LLM sağlayıcısına bağlanır, konsola akış basar. Eskiden kökte `test_*.py` adıyla duruyordu
ve `tests/` altındaki pytest dosyalarıyla aynı adı taşıyordu (`test_simulation.py` ×2);
IDE'ler onları test sanıp topluyordu. Koşum: `python -m scripts.smoke.<ad>`.

`drop_all` çağıranlar (`coach`, `action_executor`, `simulation`) bellek-içi olmayan bir DB'de
`ALLOW_DESTRUCTIVE_TEST=1` ister (BUG #381); kapı: `tests/test_yikici_kok_betik_kapisi.py`.
"""
