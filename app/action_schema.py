"""
Aksiyon payload sozlesmesi — TEK KAYNAK (BUG #266).

GUNCELLEMELER
- BUG #266 fix (7 Agu 2026): `propose_action` yalnizca `action_type`'i dogruluyordu;
  payload'in SEKLI tamamen LLM'e birakilmisti ve kural yalnizca PROMPT'ta yaziliydi
  ("PAYLOAD SABLONLARINA uygun yaz"). Olcum: `amount: "uc yuz yirmi"` bekleyen aksiyona
  yazilip kullaniciya "320 TL ... kaydedildi" ozetiyle gosteriliyordu; kullanici onayladiginda
  execute "amount sonlu ve pozitif olmali" deyip HICBIR SEY yazmiyordu. Yani dogrulama vardi
  ama YANLIS TARAFTAYDI: onaydan SONRA. `app/action_executor.py`'nin kendi ilkesi
  ("LLM'in prompt'una guvenilmez, kod seviyesinde bloklanir") payload icin uygulanmamisti.

Bu modul UC listeyi tek kaynaga baglar:
  1. `propose_action` dogrulamasi (bu dosya),
  2. `_execute_*` handler'larinin okudugu anahtarlar (kapsam kapisi AST ile dogrular),
  3. sistem prompt'undaki PAYLOAD SABLONLARI (`sablon_metni()` ile URETILIR, elle yazilmaz).

Tasarim kararlari:
- `extra="forbid"`: bilinmeyen alan SESSIZCE YUTULMAZ. LLM `amout` yazarsa tutar kaybolur
  ve kullanici bunu ancak parasi yanlis olunca fark eder (L28). Reddedilen cagri kocun
  retry yoluna duser (HESAP_BELIRSIZ/TARIH_BELIRSIZ ile ayni mekanizma).
- Eksik opsiyonel alan VARSAYILANLA DOLDURULMAZ. Koc `transaction_date` yazmadiysa
  yazmamistir; sunucu gununu buraya koymak BUG #237'nin ta kendisiydi.
- Para alanlari `app/schema_types.py` sonlu-deger tipleridir (SEC-032: inf/nan bakiyeyi ve
  cockpit'i bozar).
"""
from __future__ import annotations

import re
from datetime import date
from typing import Dict, Optional, Type

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.schema_types import FinansBakiye, FinansOptTutar, FinansTutar


class _Temel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _iso_tarih(v):
    """`date.fromisoformat` execute icinde patliyordu — onay oncesi burada yakalanir."""
    if v is None or isinstance(v, date):
        return v
    date.fromisoformat(str(v))   # gecersizse ValueError -> ValidationError'a sarilir
    return str(v)


class UpdateAccountBalance(_Temel):
    account_id: int = Field(gt=0)
    new_balance: FinansBakiye


class AddTransaction(_Temel):
    transaction_type: str = Field(json_schema_extra={"ornek": '"income"|"expense"|"transfer"'})
    amount: FinansTutar
    category: Optional[str] = None
    description: Optional[str] = None
    transaction_date: Optional[str] = Field(default=None, json_schema_extra={"ornek": '"YYYY-MM-DD"'})
    account_id: Optional[int] = Field(default=None, gt=0)
    is_card_expense: Optional[bool] = None
    auto_update_balance: Optional[bool] = None

    @field_validator("transaction_type")
    @classmethod
    def _tip(cls, v):
        if v not in ("income", "expense", "transfer"):
            raise ValueError("transaction_type: income|expense|transfer olmali")
        return v

    _tarih = field_validator("transaction_date")(classmethod(lambda cls, v: _iso_tarih(v)))


class MarkDebtPaid(_Temel):
    debt_id: int = Field(gt=0)
    paid_date: Optional[str] = Field(default=None, json_schema_extra={"ornek": '"YYYY-MM-DD"'})

    _tarih = field_validator("paid_date")(classmethod(lambda cls, v: _iso_tarih(v)))


class PayCreditCard(_Temel):
    # Handler her ikisini de okur (`card_account_id or account_id`) — sozlesme ikisini de tanir,
    # ama en az biri ZORUNLU: ikisi de yoksa execute "gerekli" deyip onaydan sonra duserdi.
    card_account_id: Optional[int] = Field(default=None, gt=0, json_schema_extra={"ornek": "<kart_hesap_id — account_id yazmadiysan ZORUNLU>"})
    account_id: Optional[int] = Field(default=None, gt=0)
    amount: FinansTutar
    source_account_id: Optional[int] = Field(default=None, gt=0, json_schema_extra={"ornek": "<nakit_hesap_id>"})

    @field_validator("account_id")
    @classmethod
    def _kart_gerekli(cls, v, info):
        if v is None and not info.data.get("card_account_id"):
            raise ValueError("card_account_id gerekli")
        return v


class SellInvestment(_Temel):
    investment_id: int = Field(gt=0)
    lots_to_sell: FinansTutar = Field(json_schema_extra={"ornek": "<lot sayisi>"})
    actual_price: FinansOptTutar = None
    credit_to_account_id: Optional[int] = Field(default=None, gt=0)


class UpdateFundPrice(_Temel):
    account_id: int = Field(gt=0)
    new_price: FinansTutar


class AddMasterCheckpoint(_Temel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    checkpoint_type: str = Field(json_schema_extra={"ornek": '"red_line"|"strategy"|"rule"|"context"'})
    priority: Optional[int] = Field(default=None, ge=1, le=3, json_schema_extra={"ornek": "1|2|3"})

    @field_validator("checkpoint_type")
    @classmethod
    def _tip(cls, v):
        if v not in ("red_line", "strategy", "rule", "context"):
            raise ValueError("checkpoint_type: red_line|strategy|rule|context olmali")
        return v


PAYLOAD_SEMALARI: Dict[str, Type[_Temel]] = {
    "update_account_balance": UpdateAccountBalance,
    "add_transaction": AddTransaction,
    "mark_debt_paid": MarkDebtPaid,
    "pay_credit_card": PayCreditCard,
    "sell_investment": SellInvestment,
    "update_fund_price": UpdateFundPrice,
    "add_master_checkpoint": AddMasterCheckpoint,
}

# Ozetin SOYLEMEK ZORUNDA oldugu tutar alani. Buraya girmeyen tur "para hareketi degil"
# demektir (ornegin kirmizi cizgi eklemek) ve ozetinde tutar aranmaz.
PARA_ALANLARI: Dict[str, str] = {
    "update_account_balance": "new_balance",
    "add_transaction": "amount",
    "pay_credit_card": "amount",
    "update_fund_price": "new_price",
}


class PayloadGecersiz(ValueError):
    """Kullaniciya ONAYA SUNULAMAZ payload. `propose_action` bunu ValueError olarak yayar;
    koc akisi HESAP_BELIRSIZ/TARIH_BELIRSIZ ile ayni retry yoluna duser."""


#: `propose_action` tool cagrisinin zorunlu argumanlari (LLM'e verilen sema ile ayni kume).
TOOL_ZORUNLU_ALANLAR = ("action_type", "payload", "summary")


def tool_argumani(inp) -> tuple:
    """Tool-call argumanini `(action_type, payload, summary)` olarak cozer.

    BUG #266: bu cozum iki ayri yerde (ana akis + retry) `inp["action_type"]` seklinde
    HAM INDEKSLEME ile yapiliyordu. Saglayicilarin hepsinde arguman JSON'u bozuk gelirse
    `args = {}`'a dusuyor (alti ayri `except: args = {}`), dolayisiyla eksik anahtar
    KeyError atiyor, `recorder.step` bunu yutuyor ve kullaniciya konuyla ilgisiz bir soru
    donuyordu. Artik eksiklik ADLANDIRILMIS bir hataya donusur ve retry yoluna duser.
    """
    if not isinstance(inp, dict):
        raise PayloadGecersiz(
            f"PAYLOAD_GECERSIZ: tool argumani nesne olmali, {type(inp).__name__} geldi"
        )
    eksik = [a for a in TOOL_ZORUNLU_ALANLAR if a not in inp]
    if eksik:
        raise PayloadGecersiz(f"PAYLOAD_GECERSIZ: tool argumaninda eksik alan: {', '.join(eksik)}")
    return inp["action_type"], inp["payload"], inp["summary"]


def dogrula(action_type: str, payload) -> dict:
    """Payload'i sozlesmeye gore dogrular ve NORMALIZE EDILMIS dict doner.

    Yazilmamis opsiyonel alanlar donen dict'te YOKTUR (uydurulmaz — BUG #237).
    """
    sema = PAYLOAD_SEMALARI.get(action_type)
    if sema is None:
        raise PayloadGecersiz(f"PAYLOAD_GECERSIZ: {action_type} icin sema tanimli degil")
    if not isinstance(payload, dict):
        raise PayloadGecersiz(
            f"PAYLOAD_GECERSIZ: payload bir nesne olmali, {type(payload).__name__} geldi"
        )
    try:
        model = sema.model_validate(payload)
    except ValidationError as e:
        detay = "; ".join(
            f"{'.'.join(str(x) for x in h['loc']) or 'payload'}: {h['msg']}" for h in e.errors()[:4]
        )
        raise PayloadGecersiz(f"PAYLOAD_GECERSIZ: {detay}") from e
    return model.model_dump(exclude_none=True)


# ----------------------------------------------------------------------------
# OZET ↔ PAYLOAD TUTARLILIGI
# ----------------------------------------------------------------------------
# Kullanicinin OKUDUGU tutar ile UYGULANACAK tutar ayni olmak zorundadir. Olcum: koc
# `summary="320 TL market harcaman kaydedildi"` yazip `payload={"amount": 3200}` gonderdiginde
# aksiyon onaya gidiyordu; `add_transaction` disindaki alti turde payload arayuzde KAPALI bir
# `<details>` icinde ham JSON oldugu icin kullanici pratikte yalniz ozeti gorur.
# Bu, `app/grounding.py` ilkesinin (kocun her TL'si izlenebilir olmali) onay yolundaki karsiligidir.

_SAYI = re.compile(r"\d[\d.,]*")


def _ozetteki_sayilar(metin: str) -> list[float]:
    """TR ve EN bicimini birlikte cozer: `19.700,50` ve `19700.50` ayni sayidir."""
    bulunan = []
    for ham in _SAYI.findall(metin or ""):
        ham = ham.rstrip(".,")
        if "," in ham:                       # TR: nokta binlik, virgul ondalik
            aday = ham.replace(".", "").replace(",", ".")
        elif ham.count(".") == 1 and len(ham.split(".")[1]) != 3:
            aday = ham                       # EN ondalik (`.5` / `.50`)
        else:
            aday = ham.replace(".", "")      # binlik ayraci
        try:
            bulunan.append(float(aday))
        except ValueError:
            continue
    return bulunan


def ozet_payload_celiskisi(action_type: str, payload: dict, summary: str) -> Optional[str]:
    """Celiski varsa aciklama, yoksa None doner."""
    alan = PARA_ALANLARI.get(action_type)
    if alan is None:
        return None
    tutar = payload.get(alan)
    if tutar is None:
        return None
    sayilar = _ozetteki_sayilar(summary)
    if not sayilar:
        return (
            f"ozet tutari SOYLEMIYOR ({alan}={tutar}); kullanici neyi onayladigini goremez"
        )
    # Kurus farki ve yuvarlama serbest: 0.01 tolerans.
    if any(abs(s - float(tutar)) <= 0.01 for s in sayilar):
        return None
    return (
        f"ozetteki tutar(lar) {sayilar} ile payload {alan}={tutar} uyusmuyor"
    )


# ----------------------------------------------------------------------------
# SISTEM PROMPT SABLONLARI — semadan URETILIR (elle yazilmaz, L27)
# ----------------------------------------------------------------------------

def _alan_ornegi(ad: str, alan) -> str:
    """Prompt'ta gosterilecek ornek deger.

    Alanin KENDI tanimindaki `ornek` ile birlikte yasar (json_schema_extra) — boylece
    izin verilen degerler kumesi (enum) prompt'a turetilirken KAYBOLMAZ. Turden otomatik
    uretim yalnizca yedek yoldur.
    """
    ek = alan.json_schema_extra or {}
    if isinstance(ek, dict) and ek.get("ornek"):
        return ek["ornek"]
    ann = str(alan.annotation)
    if "bool" in ann:
        return "true|false"
    if "float" in ann:
        return "<TL>"
    if "int" in ann:
        return "<id>"
    return '"<...>"'


def sablon_metni() -> str:
    """Sistem prompt'una gomulen PAYLOAD SABLONLARI bolumu.

    Eskiden prompt'ta ELLE yazili ucuncu bir listeydi; sema degisince sessizce bayatlardi.
    """
    satirlar = ["# PAYLOAD ŞABLONLARI", ""]
    for tur in sorted(PAYLOAD_SEMALARI):
        sema = PAYLOAD_SEMALARI[tur]
        zorunlu, opsiyonel = [], []
        for ad, alan in sema.model_fields.items():
            parca = f'"{ad}": {_alan_ornegi(ad, alan)}'
            (zorunlu if alan.is_required() else opsiyonel).append(parca)
        satirlar.append(f"## {tur}")
        satirlar.append("{" + ", ".join(zorunlu + opsiyonel) + "}")
        if opsiyonel:
            satirlar.append(f"   (opsiyonel: {', '.join(a.split(':')[0] for a in opsiyonel)})")
        satirlar.append("")
    satirlar.append(
        "Şablonda OLMAYAN alan gönderme — reddedilir. Opsiyonel bir alanı bilmiyorsan "
        "HİÇ YAZMA: uydurulan değer kullanıcının işlemini yanlış kaydeder. "
        "Özetteki tutar payload'daki tutarla AYNI olmalı."
    )
    return "\n".join(satirlar)
