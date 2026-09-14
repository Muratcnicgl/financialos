"""
LLM-025 (BUG #505): koç motoru açılışta ısıtılır; tembel kurulum yarışsız.

Ölçüm (14 Eyl 2026): SDK importları openai 0,9 s / anthropic 0,8 s / google.genai 1,7 s;
motor ilk istekte kuruluyordu → ilk sohbet ~3,4 s fazladan bekliyor, eksik SDK ilk
kullanıcıda patlıyordu; `_get_engine` kilitsizdi (iki eşzamanlı ilk istek iki motor kurabilir).
Kilitlenen:
  1. `_get_engine` eşzamanlı çağrılarda TEK motor kurar (kilit),
  2. `koc_motorunu_isit`: anahtar yoksa hiçbir şey yapmaz (None), kurulum hatasını yutar ve
     log'lar (uygulama açılışı durmaz), başarıda sağlayıcı adını döner,
  3. `lifespan` ısıtmayı arka iş parçacığında başlatır ve `LLM_WARMUP=0` ile kapatılır (kaynak).
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from app.routers import coach as rc

KOK = Path(__file__).resolve().parent.parent


def test_get_engine_yarissiz(monkeypatch):
    kurulum = {"n": 0}

    class YavasMotor:
        def __init__(self):
            time.sleep(0.05)
            kurulum["n"] += 1

    monkeypatch.setattr(rc, "CoachEngine", YavasMotor)
    monkeypatch.setattr(rc, "_engine", None)
    sonuclar = []
    tarafl = [threading.Thread(target=lambda: sonuclar.append(rc._get_engine())) for _ in range(8)]
    for t in tarafl: t.start()
    for t in tarafl: t.join()
    assert kurulum["n"] == 1, f"eşzamanlı ilk isteklerde {kurulum['n']} motor kuruldu"
    assert len({id(s) for s in sonuclar}) == 1


def test_isitma_anahtarsiz_hicbir_sey_yapmaz(monkeypatch):
    for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "ANTHROPIC_API_KEY", "CEREBRAS_API_KEY", "OPENROUTER_API_KEY", "TOGETHER_API_KEY", "DEEPINFRA_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "fallback")
    monkeypatch.setattr(rc, "_engine", None)
    cagri = {"n": 0}
    monkeypatch.setattr(rc, "CoachEngine", lambda: cagri.__setitem__("n", cagri["n"] + 1))
    assert rc.koc_motorunu_isit() is None and cagri["n"] == 0


def test_isitma_hatayi_yutar_ve_basarida_ad_doner(monkeypatch, caplog):
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setattr(rc, "_engine", None)

    def patlar():
        raise RuntimeError("sdk yok")

    monkeypatch.setattr(rc, "CoachEngine", patlar)
    with caplog.at_level("WARNING"):
        assert rc.koc_motorunu_isit() is None
    assert "isitma basarisiz" in caplog.text

    class Motor:
        provider = type("P", (), {"NAME": "Groq"})()

    monkeypatch.setattr(rc, "_engine", None)
    monkeypatch.setattr(rc, "CoachEngine", Motor)
    assert rc.koc_motorunu_isit() == "Groq"


def test_lifespan_isitmayi_arka_planda_baslatir():
    src = (KOK / "app" / "main.py").read_text(encoding="utf-8")
    assert 'os.getenv("LLM_WARMUP", "1")' in src
    assert 'from app.routers.coach import koc_motorunu_isit as _koc_isit' in src
    assert '_Thread(target=_koc_isit, name="koc-isitma", daemon=True).start()' in src
