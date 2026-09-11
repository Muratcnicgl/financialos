"""
BE-029 / BUG #400 KAPISI — GECE BATCH'İ KULLANICI BAŞINA AYRI SESSION VE HATA YALITIMI.

Ölçülen (11 Eyl 2026): `nightly_batch_job` ve `k2_batch_job` bütün kullanıcıları TEK
session'da sırayla koşturuyordu. Extractor hataları `run_extractor` içinde yutuluyor ve
rollback ediliyordu (BUG #062); ama kullanıcı-seviyesi bir istisna (workspace sorgusu,
`run_periodic_batch_for_user`ın kendisi) döngüyü kesiyor, kalan kullanıcılar o gece
insight almıyordu — iş kaydı "hata" diyordu, kimin düştüğünü değil.

Kilitlenen: kullanıcı listesi ayrı session; her kullanıcı KENDİ session'ında; birinin
istisnası diğerlerini düşürmez; özet "N kullanici, M hata".
"""
from __future__ import annotations

import asyncio

import pytest

from app import scheduler


class _Sayac:
    def __init__(self):
        self.acilan = 0

    def __call__(self):
        self.acilan += 1
        return _SahteSession()


class _SahteSession:
    def close(self):
        pass


@pytest.fixture
def uc_kullanici(monkeypatch):
    sayac = _Sayac()
    monkeypatch.setattr(scheduler, "SessionLocal", sayac)
    monkeypatch.setattr(scheduler, "_get_active_user_ids", lambda db: [1, 2, 3])
    return sayac


def test_her_kullanici_kendi_sessioninda(uc_kullanici, monkeypatch):
    gorulen = []
    monkeypatch.setattr(scheduler, "run_periodic_batch_for_user",
                        lambda db, uid: gorulen.append((id(db), uid)) or {"ok": True})
    ozet = asyncio.run(scheduler.nightly_batch_job())
    assert ozet == "3 kullanici"
    assert [u for _, u in gorulen] == [1, 2, 3]
    # liste için 1 + kullanıcı başına 1 (+ izleme kayıtları da SessionLocal açar; alt sınır)
    assert uc_kullanici.acilan >= 4, uc_kullanici.acilan
    assert len({s for s, _ in gorulen}) == 3, "kullanıcılar aynı session nesnesini paylaştı"


def test_bir_kullanicinin_hatasi_digerlerini_dusurmez(uc_kullanici, monkeypatch):
    gorulen = []

    def calistir(db, uid):
        if uid == 2:
            raise RuntimeError("workspace sorgusu patladi")
        gorulen.append(uid)
        return {}

    monkeypatch.setattr(scheduler, "run_k2_batch_for_user", calistir)
    ozet = asyncio.run(scheduler.k2_batch_job())
    assert gorulen == [1, 3], "ikinci kullanıcının hatası üçüncüyü de düşürdü"
    assert ozet == "3 kullanici, 1 hata"


def test_iki_is_de_ortak_iskeleti_kullanir():
    import inspect
    for job in (scheduler.nightly_batch_job, scheduler.k2_batch_job):
        kaynak = inspect.getsource(inspect.unwrap(job))
        assert "_kullanici_basina(" in kaynak, f"{job.__name__} ortak iskeleti kullanmıyor"
