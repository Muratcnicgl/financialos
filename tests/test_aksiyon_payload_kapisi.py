"""
BUG #266 — LLM'in urettigi tool argumani DOGRULANMADAN kullaniciya onaya sunuluyordu.

OLCUM (7 Agu 2026, FakeProvider ile gercek koc akisi kosuldu):
  1. `amount: "uc yuz yirmi"` (metin tutar) bekleyen aksiyona YAZILDI ve kullaniciya
     "320 TL market harcamasi kaydedildi" ozetiyle gosterildi. Kullanici onaylarsa
     `_execute_add_transaction` "amount sonlu ve pozitif olmali" der ve HICBIR SEY yazilmaz
     -> kullanici "Kaydettim." cumlesini okuyup onayladi, islem kayboldu.
  2. `summary="320 TL market harcaman kaydedildi"` + `payload={"amount": 3200}` -> ONAYA
     GITTI. Kullanicinin OKUDUGU tutar ile UYGULANACAK tutar 10 kat farkliydi ve hicbir
     denetim yoktu. add_transaction disindaki alti tipte payload arayuzde KAPALI bir
     `<details>` icinde ham JSON -> kullanici pratikte yalniz ozeti gorur.
  3. Eksik anahtarli tool argumani (`{}`, `summary` yok, `payload` string) sessizce
     yutuluyordu: kullaniciya alakasiz "Hangi hesaptan harcadin?" sorusu donuyordu.

Kok neden: `propose_action` yalnizca `action_type`'i dogruluyordu; payload'in SEKLI
tamamen LLM'e birakilmisti ("PAYLOAD SABLONLARINA uy" yalnizca PROMPT'ta yaziliydi).
Oysa `app/action_executor.py`'nin kendi ilkesi "LLM'in prompt'una guvenilmez, kod
seviyesinde bloklanir" diyor — payload icin bu yapilmamisti.

Sozlesme: dogrulama ONAY ONCESINDE, `propose_action` sinirinda yapilir. Tuketiciye
(execute) birakmak, kullanicinin onayladigi seyin hic uygulanamayacagini onaydan SONRA
ogrenmesi demektir.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.action_executor import ACTION_TYPES, propose_action
from app.models import Account, AccountType, Base, PendingAction, User


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(User(id=1, name="payload_test"))
    session.flush()
    session.add(Account(id=1, user_id=1, name="Kasa", account_type=AccountType.cash, balance=5000))
    session.commit()
    yield session
    session.close()


def _oner(db, **kw):
    varsayilan = dict(
        db=db, user_id=1, action_type="add_transaction",
        payload={"transaction_type": "expense", "amount": 320.0, "account_id": 1},
        summary="320 TL market harcaması kaydedildi",
        user_message="320 TL market harcadım nakitten",
    )
    varsayilan.update(kw)
    return propose_action(**varsayilan)


# ----------------------------------------------------------------------------
# 1) Uygulanamayacak payload ONAYA SUNULMAZ
# ----------------------------------------------------------------------------

def test_metin_tutar_onaya_sunulmaz(db):
    """`amount: "uc yuz yirmi"` -> execute'ta zaten reddedilecekti; kullanici bunu ONAYDAN
    SONRA ogrenmemeli."""
    with pytest.raises(ValueError) as e:
        _oner(db, payload={"transaction_type": "expense", "amount": "uc yuz yirmi", "account_id": 1})
    assert "PAYLOAD_GECERSIZ" in str(e.value)
    assert db.query(PendingAction).count() == 0, "gecersiz payload DB'ye yazilmamali"


def test_negatif_tutar_onaya_sunulmaz(db):
    with pytest.raises(ValueError, match="PAYLOAD_GECERSIZ"):
        _oner(db, payload={"transaction_type": "expense", "amount": -50, "account_id": 1})


def test_sonsuz_tutar_onaya_sunulmaz(db):
    """SEC-032 ailesi: inf/nan bakiyeyi ve cockpit'i bozar."""
    with pytest.raises(ValueError, match="PAYLOAD_GECERSIZ"):
        _oner(db, payload={"transaction_type": "expense", "amount": float("inf"), "account_id": 1})


def test_zorunlu_alan_eksik_onaya_sunulmaz(db):
    with pytest.raises(ValueError, match="PAYLOAD_GECERSIZ"):
        _oner(db, payload={"transaction_type": "expense"})   # amount yok


def test_payload_dict_degilse_reddedilir(db):
    with pytest.raises(ValueError, match="PAYLOAD_GECERSIZ"):
        _oner(db, payload="320 TL market")


def test_bozuk_tarih_onaya_sunulmaz(db):
    """`date.fromisoformat` execute icinde patlardi — onay oncesi yakalanmali."""
    with pytest.raises(ValueError, match="PAYLOAD_GECERSIZ"):
        _oner(db, payload={"transaction_type": "expense", "amount": 320.0,
                           "account_id": 1, "transaction_date": "dün"})


def test_gecersiz_islem_tipi_onaya_sunulmaz(db):
    with pytest.raises(ValueError, match="PAYLOAD_GECERSIZ"):
        _oner(db, payload={"transaction_type": "harcama", "amount": 320.0, "account_id": 1})


# ----------------------------------------------------------------------------
# 2) OZET ile PAYLOAD ayni gercegi soylemek zorunda
# ----------------------------------------------------------------------------

def test_ozetteki_tutar_payload_ile_uyusmali(db):
    """Kullanicinin OKUDUGU tutar ile UYGULANACAK tutar ayni olmali (olcum: 320 vs 3200)."""
    with pytest.raises(ValueError) as e:
        _oner(db, payload={"transaction_type": "expense", "amount": 3200.0, "account_id": 1},
              summary="320 TL market harcaman kaydedildi")
    assert "OZET_PAYLOAD_CELISKISI" in str(e.value)
    assert db.query(PendingAction).count() == 0


def test_ozetteki_tutar_payload_ile_uyusuyorsa_gecer(db):
    p = _oner(db, payload={"transaction_type": "expense", "amount": 320.0, "account_id": 1},
              summary="320 TL market harcaman kaydedildi")
    assert p.id is not None


def test_ozet_binlik_ayraci_ile_yazilmis_olabilir(db):
    """`19.700,50` (TR) ile 19700.5 ayni tutardir — bicim celiskisi degil."""
    p = _oner(db, action_type="pay_credit_card",
              payload={"card_account_id": 1, "amount": 19700.50},
              summary="Kart borcuna 19.700,50 TL ödeme kaydedildi")
    assert p.id is not None


def test_ozet_hic_tutar_icermiyorsa_para_hareketi_reddedilir(db):
    """Para hareketinin ozeti tutari SOYLEMEK zorundadir; aksi halde kullanici neyi
    onayladigini bilmez (add_transaction disindaki tiplerde payload arayuzde kapali)."""
    with pytest.raises(ValueError, match="OZET_PAYLOAD_CELISKISI"):
        _oner(db, payload={"transaction_type": "expense", "amount": 320.0, "account_id": 1},
              summary="Market harcaman kaydedildi")


def test_para_hareketi_olmayan_tipte_tutar_araniamaz(db):
    """`add_master_checkpoint` para hareketi degil — ozetinde tutar aranmaz."""
    p = _oner(db, action_type="add_master_checkpoint",
              payload={"title": "Emanet dokunulmaz", "description": "Kardeşimin parası",
                       "checkpoint_type": "red_line", "priority": 1},
              summary="Yeni kırmızı çizgi eklendi")
    assert p.id is not None


# ----------------------------------------------------------------------------
# 3) Gecerli payload aynen calisir (regresyon)
# ----------------------------------------------------------------------------

def test_gecerli_payload_degismeden_kaydedilir(db):
    p = _oner(db)
    kayitli = json.loads(p.payload)
    assert kayitli["amount"] == 320.0
    assert kayitli["transaction_type"] == "expense"
    assert kayitli["account_id"] == 1


def test_opsiyonel_alanlar_uydurulmaz(db):
    """Dogrulama eksik alani VARSAYILANLA DOLDURMAZ — koc yazmadiysa yazmamistir
    (BUG #237: sunucu gununu yazmak islemi yanlis gune koyuyordu)."""
    p = _oner(db)
    kayitli = json.loads(p.payload)
    assert "transaction_date" not in kayitli


def test_bilinmeyen_aksiyon_turu_reddedilir(db):
    with pytest.raises(ValueError, match="Bilinmeyen aksiyon"):
        _oner(db, action_type="delete_everything", payload={}, summary="sil")


# ----------------------------------------------------------------------------
# 4) KAPSAM TABANI — sema listesi elle tasinmaz (L27)
# ----------------------------------------------------------------------------

def test_her_aksiyon_turunun_semasi_var():
    from app.action_schema import PAYLOAD_SEMALARI
    assert set(PAYLOAD_SEMALARI) == set(ACTION_TYPES), (
        "Yeni action_type eklendiginde semasi da eklenmeli — aksi halde o tur "
        "dogrulamasiz kalir ve kapi sessizce delinir (L27)."
    )


def test_para_alani_bildirimi_semalarla_tutarli():
    """Ozet-payload denetiminin baktigi para alani, o turun semasinda GERCEKTEN var mi?"""
    from app.action_schema import PARA_ALANLARI, PAYLOAD_SEMALARI
    for tur, alan in PARA_ALANLARI.items():
        assert tur in PAYLOAD_SEMALARI, f"{tur} icin sema yok"
        assert alan in PAYLOAD_SEMALARI[tur].model_fields, (
            f"{tur} icin bildirilen para alani '{alan}' semada yok — denetim bos yere kosar"
        )


def test_her_tur_icin_dogrulama_gercekten_kosuyor(db):
    """Kapsam tabani: her action_type'ta BOS payload reddedilmeli (hicbiri dogrulamayi
    atlamamali). Bos payload'i kabul eden bir tur, o turun kapisinin olu oldugu demektir."""
    atlayan = []
    for tur in sorted(ACTION_TYPES):
        try:
            propose_action(db=db, user_id=1, action_type=tur, payload={},
                           summary="test", user_message="test")
            atlayan.append(tur)
        except ValueError:
            pass
    assert atlayan == [], f"bos payload'i kabul eden turler: {atlayan}"


# ----------------------------------------------------------------------------
# 5) UC LISTE TEK KAYNAKTAN — sema / handler / prompt drift kilidi (L27)
# ----------------------------------------------------------------------------

def _handler_payload_anahtarlari() -> dict:
    """`_execute_*` handler'larinin GERCEKTEN okudugu payload anahtarlarini AST ile cikarir.

    Elle liste tasinmaz: handler yeni bir alan okumaya baslarsa bu kapi onu kendiliginden
    gorur (L27). Kaynak metni degil sozdizimi agaci okunur — yorumda gecen anahtar saymaz.
    """
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path("app/action_executor.py").read_text(encoding="utf-8"))
    sonuc = {}
    for fn in [n for n in tree.body if isinstance(n, ast.FunctionDef)
               and n.name.startswith("_execute_")]:
        anahtarlar = set()
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "payload"
                    and node.args and isinstance(node.args[0], ast.Constant)):
                anahtarlar.add(node.args[0].value)
            if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                    and node.value.id == "payload" and isinstance(node.slice, ast.Constant)):
                anahtarlar.add(node.slice.value)
        sonuc[fn.name[len("_execute_"):]] = anahtarlar
    return sonuc


def test_handlerin_okudugu_her_alan_semada_var():
    """Handler bir alani okuyor ama sema onu tanimiyorsa `extra=forbid` yuzunden koc o alani
    HIC gonderemez — ozellik sessizce olur."""
    from app.action_schema import PAYLOAD_SEMALARI

    eksikler = {}
    for tur, anahtarlar in _handler_payload_anahtarlari().items():
        sema_alanlari = set(PAYLOAD_SEMALARI[tur].model_fields)
        fark = anahtarlar - sema_alanlari
        if fark:
            eksikler[tur] = sorted(fark)
    assert eksikler == {}, f"handler okuyor ama sema tanimiyor: {eksikler}"


def test_semadaki_her_alan_handler_tarafindan_okunuyor():
    """Ters yon: semada olup hicbir handler'in okumadigi alan, kocu bos yere yazmaya
    tesvik eder (ve kullaniciya 'kaydedildi' hissi verir)."""
    from app.action_schema import PAYLOAD_SEMALARI

    fazlalar = {}
    handler = _handler_payload_anahtarlari()
    for tur, sema in PAYLOAD_SEMALARI.items():
        fark = set(sema.model_fields) - handler[tur]
        if fark:
            fazlalar[tur] = sorted(fark)
    assert fazlalar == {}, f"semada var ama hicbir handler okumuyor: {fazlalar}"


def test_prompt_sablonlari_semadan_uretiliyor():
    """PAYLOAD SABLONLARI prompt'ta ELLE yazili UCUNCU bir listeydi; sema degisince
    sessizce bayatliyordu. Artik uretilir — ve prompt'ta yer tutucu KALMAMALI."""
    from app.action_schema import PAYLOAD_SEMALARI, sablon_metni
    from app.coach import V3_GOD_MODE_PROMPT

    assert "{PAYLOAD_SABLONLARI}" not in V3_GOD_MODE_PROMPT, "yer tutucu cozulmemis"
    uretilen = sablon_metni()
    assert uretilen in V3_GOD_MODE_PROMPT, "prompt uretilen sablonu tasimiyor"
    for tur in PAYLOAD_SEMALARI:
        assert f"## {tur}" in uretilen, f"{tur} sablonda yok"


def test_prompt_sablonu_zorunlu_alanlari_gosteriyor():
    """Sablon opsiyonel/zorunlu ayrimini SOYLEMELI — aksi halde koc zorunlu alani atlar
    ve dogrulama her seferinde reddeder (kullaniciya 'oluşturamadım' doner)."""
    from app.action_schema import PAYLOAD_SEMALARI, sablon_metni

    metin = sablon_metni()
    for tur, sema in PAYLOAD_SEMALARI.items():
        for ad, alan in sema.model_fields.items():
            assert f'"{ad}"' in metin, f"{tur}.{ad} sablonda gecmiyor"
        if any(not a.is_required() for a in sema.model_fields.values()):
            assert "opsiyonel:" in metin


def test_tool_argumaninda_eksik_alan_adlandirilmis_hataya_donusur():
    """Eskiden `inp["action_type"]` KeyError atiyor, trace onu yutuyordu."""
    from app.action_schema import PayloadGecersiz, tool_argumani

    with pytest.raises(PayloadGecersiz, match="eksik alan"):
        tool_argumani({})
    with pytest.raises(PayloadGecersiz, match="eksik alan"):
        tool_argumani({"action_type": "add_transaction", "payload": {}})
    with pytest.raises(PayloadGecersiz):
        tool_argumani("add_transaction")
    assert tool_argumani({"action_type": "t", "payload": {}, "summary": "s"}) == ("t", {}, "s")
