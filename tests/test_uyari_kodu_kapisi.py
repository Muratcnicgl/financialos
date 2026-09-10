"""
UYARI KİMLİĞİ KAPISI — her cockpit uyarısının kararlı bir `kod`u olmalı.

NEDEN VAR (ölçülen defekt, 10 Eyl 2026): arayüzde aynı gerçek iki kez yazılıyordu —
"Kart kullanımı %80 (9.600/12.000)" adanmış kartı ile "Kart kullanım oranı yüksek —
Kart 80.0% dolu" uyarısı; "asgari-ödeme tuzağı: 21 ay · faiz 1.855,15" kartı ile aynı
içerikli uyarı. Dört kutu, iki bilgi. Adanmış kart zengin (çubuk + sayı), uyarı yalnız
düzyazı; doğrusu kart çiziliyorken uyarıyı bastırmak.

Ama bastırma bir KİMLİĞE dayanmalı. O gün uyarıların yalnız `baslik` dizesi vardı ve
başlığa göre eşleştirmek, başlık her düzeltildiğinde (bir yazım hatası bile) sessizce
çalışmayı bırakan bir kural üretirdi. Bu yüzden önce `kod` eklendi, sonra arayüz
bastırma yaptı.

KİLİTLENEN DEĞİŞMEZLER:
  1. Kaynakta uyarı üreten HER sözlükte `kod` var. (AST taraması — çalışma zamanında
     tetiklenmeyen dallar da kapsanır; yalnız bir senaryo koşturmak, koşulu sağlanmayan
     uyarıyı hiç görmezdi.)
  2. Kodlar benzersiz: iki farklı uyarı aynı kimliği taşıyamaz, yoksa arayüz birini
     bastırırken ötekini de bastırır.
  3. Kodlar makine-okunur biçimde: küçük harf, rakam ve alt çizgi (arayüzde sabit
     olarak yazılıyorlar; boşluk/Türkçe karakter kırılganlık üretir).
  4. Arayüzün bastırdığı kodlar GERÇEKTEN üretiliyor: arayüz olmayan bir kodu bastırmaya
     çalışırsa kural ölü demektir ve tekrar geri gelir.
"""
from __future__ import annotations

import ast
import io
import os
import re

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KAYNAK = os.path.join(KOK, "app", "rules_engine.py")
ARAYUZ = os.path.join(KOK, "frontend", "src", "panels", "Cockpit.jsx")


def _uyari_sozlukleri() -> list[ast.Dict]:
    """Uyarı gibi duran sözlük değişmezleri: hem `seviye` hem `baslik` anahtarı olanlar."""
    agac = ast.parse(io.open(KAYNAK, encoding="utf-8").read())
    bulunan = []
    for d in ast.walk(agac):
        if not isinstance(d, ast.Dict):
            continue
        anahtarlar = {k.value for k in d.keys
                      if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        if {"seviye", "baslik"} <= anahtarlar:
            bulunan.append(d)
    return bulunan


def _kodlar() -> list[str]:
    kodlar = []
    for d in _uyari_sozlukleri():
        for k, v in zip(d.keys, d.values, strict=True):
            if isinstance(k, ast.Constant) and k.value == "kod":
                assert isinstance(v, ast.Constant), "kod SABİT olmalı (f-string değil)"
                kodlar.append(v.value)
    return kodlar


def test_her_uyarinin_kodu_var():
    sozlukler = _uyari_sozlukleri()
    # Kapsam tabanı: tarayıcı bozulursa "0 uyarı bulundu, hepsi temiz" demesin.
    assert len(sozlukler) >= 10, (
        f"yalnız {len(sozlukler)} uyarı sözlüğü bulundu — tarayıcı çalışmıyor olabilir"
    )
    kodsuz = []
    for d in sozlukler:
        anahtarlar = {k.value for k in d.keys
                      if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        if "kod" not in anahtarlar:
            baslik = next((v for k, v in zip(d.keys, d.values, strict=True)
                           if isinstance(k, ast.Constant) and k.value == "baslik"), None)
            kodsuz.append(getattr(baslik, "value", ast.dump(baslik)[:60]))
    assert not kodsuz, f"kodsuz uyarı(lar): {kodsuz}"


def test_kodlar_benzersiz():
    kodlar = _kodlar()
    tekrar = {k for k in kodlar if kodlar.count(k) > 1}
    assert not tekrar, f"aynı kodu taşıyan uyarılar: {tekrar}"


def test_kodlar_makine_okunur():
    hatali = [k for k in _kodlar() if not re.fullmatch(r"[a-z0-9_]+", k)]
    assert not hatali, f"kod biçimi bozuk (küçük harf/rakam/alt çizgi bekleniyor): {hatali}"


def test_arayuzun_bastirdigi_kodlar_gercekten_uretiliyor():
    """Arayüz olmayan bir kodu bastırmaya çalışıyorsa o kural ÖLÜDÜR.

    Ölü bir bastırma kuralı sessizdir: tekrar eden uyarı geri gelir, kimse fark etmez.
    """
    jsx = io.open(ARAYUZ, encoding="utf-8").read()
    blok = re.search(r"KART_KARTI_OLAN_UYARILAR\s*=\s*\{(.*?)\};", jsx, re.S)
    assert blok, "Cockpit.jsx içinde KART_KARTI_OLAN_UYARILAR eşlemesi bulunamadı"
    arayuz_kodlari = set(re.findall(r"'([a-z0-9_]+)'", blok.group(1)))
    assert arayuz_kodlari, "bastırma listesi boş görünüyor"

    uretilen = set(_kodlar())
    olu = arayuz_kodlari - uretilen
    assert not olu, f"arayüz üretilmeyen kodları bastırıyor (ölü kural): {olu}"
