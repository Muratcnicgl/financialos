# Denetim: app/routers/simulation.py

### [RSI-001] reel_butce / daily_limit / kart_kullanim_orani hicbir zaman doldurulmuyor
- **Sorun:** `HorizonSnapshot` semasi `reel_butce`, `daily_limit`, `kart_kullanim_orani` alanlarini vaat ediyor ve `_snapshot_to_horizon` bunlari `snap.get(...)` ile okuyor (satir 73-75). Ama bu dict'leri ureten `app/simulation_engine.py::_snapshot_to_dict` (satir 418-441) SADECE `label, as_of, nakit_kasa, kart_borcu, kredi_borcu, yatirim_deger, emanet_kasa, net_deger, accounts` anahtarlarini yaziyor. `reel_butce`/`daily_limit` rules_engine.generate_cockpit'in shadow-accounting hesabidir (app/rules_engine.py satir 718-783: recurring_income + loan_payments_eom dahil edilerek hesaplaniyor) ve simulation_engine bunu hic tekrarlamiyor/cagirmiyor.
- **Kanit:** simulation.py satir 44-45, 73-75; simulation_engine.py satir 418-441 (anahtar listesi).
- **Aksiyon:** Ya HorizonSnapshot semasindan bu 3 alani cikar (kart_kullanim_orani zaten Optional=None ile "veri yok" gibi gorunuyor ama reel_butce/daily_limit `float` -> `.get(...) or 0.0` ile SESSIZCE 0.0 donuyor, "butceniz sifir/kritik" gibi yanlis okunabilir), ya da simulation_engine'e rules_engine ile tutarli bir reel_butce/daily_limit hesabi ekle.
- **Onem:** Kritik · **Guven:** Kesin

### [RSI-002] 500 hata mesaji ham exception string'ini kullaniciya donuyor
- **Sorun:** `except Exception as e: raise HTTPException(500, detail=f"Simulasyon motoru hatasi: {e}")` (satir 126-131) DB/driver hata mesajini oldugu gibi HTTP yanitina koyuyor. `logger.exception` zaten tam stack trace'i logluyor; ayrica client'a str(e) sizdirmanin faydasi yok, iç yapi (SQL, dosya yolu vb.) sizabilir.
- **Kanit:** satir 126-131.
- **Aksiyon:** Client'a genel bir mesaj don ("Simulasyon motoru beklenmeyen bir hatayla karsilasti"), detayi sadece logger.exception'a birak.
- **Onem:** Orta · **Guven:** Kesin

### [RSI-003] label_to_days eslesmesi kirilgan/olu-varsayima dayali
- **Sorun:** `label_to_days = {"T+0": 0, "T+30": 30, "T+90": 90}` (satir 139) sabit; `simulate_pending_action` her zaman `horizons_days=(0, 30, 90)` ile cagiriyor (satir 124) yani su an calisiyor. Ama `simulate_action`'in varsayilan imzasi `horizons_days: Tuple[int, ...] = (0, 30, 60, 90)` (simulation_engine.py satir 460) — router bu varsayilani KULLANMIYOR, kendi (0,30,90) degerini hardcode ediyor; bu iki sabit birbirinden bagimsiz surdurulmek zorunda. Biri degisip digeri unutulursa `label_to_days.get(...)` sessizce `days=0` doner (satir 141-142), yani T+60 gibi bilinmeyen bir ufuk "days=0" olarak yanlis etiketlenir ve frontend'de T+0 ile karisir.
- **Kanit:** simulation.py satir 124, 139, 141-142; simulation_engine.py satir 460 (varsayilan farkli).
- **Aksiyon:** `label`'dan `days`'i regex/parse ile turet (orn. `int(label.split("+")[1])`) ya da `simulate_action`'in donen sonucuna gun sayisini ayrica ekle; iki yerde ayni sabiti tekrar etme.
- **Onem:** Dusuk · **Guven:** Dogrulanmali (su anki sabit degerlerle calisiyor, sadece gelecekte kirilgan)

### [RSI-004] emanet_kasa API yanitinda tamamen kayboluyor
- **Sorun:** `simulation_engine._snapshot_to_dict` `emanet_kasa` degerini hesapliyor (satir 426) ve `delta_vs_baseline` icinde de tasiyor (satir 447), ama `HorizonSnapshot` semasinda hic alan yok — `_snapshot_to_horizon` bu anahtari okumuyor. Kullanici/LLM T+30'da emanet hesabindaki degisimi (olmasi gerekmiyor ama fon fiyati guncellemesi gibi senaryolarda emanet degeri degisebilir) goremiyor.
- **Kanit:** simulation.py satir 39-47 (HorizonSnapshot alanlari, emanet_kasa yok); simulation_engine.py satir 426.
- **Aksiyon:** Kasitliyse (ADR: emanet gosterilmez) docstring'e not dus; degilse `emanet_kasa` alanini semaya ekle.
- **Onem:** Dusuk · **Guven:** Dogrulanmali

### [RSI-005] ok=False durumunda 200 donuyor ama horizons bos, frontend kontrat karisikligi riski
- **Sorun:** `simulate_action` basarisiz aksiyonda (`_apply_action` False donerse) `snapshots: []` ile doner (simulation_engine.py satir 502-510). Router bunu status kodu degistirmeden (200 OK, `ok=False`) `HorizonsResponse` icine sariyor (satir 133-137, 148-156). `baseline` yine de dolu geliyor ama `horizons=[]`. Bu davranissal olarak dogru (simulasyon karar vermez, sadece bildirir) fakat response_model'de `horizons` bos liste oldugunda frontend'in bunu ayirt edip "aksiyon simulasyonda gecersiz" mesajini `message` alanindan okumasi GEREKIYOR — sema bunu zorunlu kilan bir ayri "ok" disi sinyal saglamiyor (ornegin bos horizons + ok=True teorik olarak da olusabilirdi, sema bunu engellemiyor).
- **Kanit:** satir 133-137, 148-156; simulation_engine.py satir 502-510.
- **Aksiyon:** Sema-seviyesinde netlik icin isteğe bagli: `ok=False` oldugunda horizons'in bos olmasi gerektigini docstring'e yaz (kirilgan cikti formati riskini azaltmak icin). Fonksiyonel bug degil, kontrat netligi.
- **Onem:** Dusuk · **Guven:** Dogrulanmali
