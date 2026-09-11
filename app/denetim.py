"""
Denetim izi (BUG #408 · OBS-020 / SEC-024) — finansal kaydın güncelleme/silme izi.

Ölçülen (12 Eyl 2026): `ActionHistory` yalnız koç aksiyonlarını tutuyordu; panelden yapılan
bir DELETE/PUT (hesap silme, bakiye düzeltme, borç kapama) hiçbir yerde kalmıyordu.
Backlog "router DELETE audit yok" diye 60+ gündür taşıyordu.

Tasarım:
  * Kanca ROUTER'A DEĞİL ORM FLUSH'A takılır (`Session` sınıfı, `before_flush`): hangi
    yoldan gelirse gelsin (router, koç yürütücüsü, betik) silme/güncelleme yakalanır; yeni
    bir router yazan biri kancayı UNUTAMAZ (L14 fail-closed).
  * Hangi modellerin denetleneceği ELLE LİSTELENMEZ (L79): `user_id` taşıyan ve para (Numeric)
    sütunu olan her model denetlenir; muaf olanlar gerekçesiyle burada yazılıdır.
  * `update` yalnız DEĞİŞEN alanları taşır (eski/yeni); `delete` satırın tamamını. Değerler
    `str()` ile serileştirilir (Decimal/tarih/enum). Ekleme (insert) denetlenmez: kayıt
    zaten kendisi kanıttır.
  * Denetim yazımı asla işi düşürmez: hata yutulur ve loglanır.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from sqlalchemy import Numeric, event, inspect, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Base

logger = logging.getLogger(__name__)

#: Kural karşılığı olduğu hâlde denetlenmeyen tablolar — her biri NEDENİYLE.
MUAF: dict[str, str] = {
    "net_worth_snapshots": "türetilmiş günlük özet, her kokpit isteğinde upsert — kullanıcı mutasyonu değil",
    "api_call_log": "LLM maliyet defteri; est_cost_usd para değil tahmin, kendisi zaten bir kayıt",
    "reasoning_traces": "koç muhakeme izi; kendisi zaten bir kayıt (90 gün saklama)",
    "action_history": "koç aksiyon izi; kendisi zaten bir kayıt",
}


#: Sayısal sütunu olmadığı için kurala girmeyen ama denetlenmesi gereken tablolar — NEDENİYLE.
EK_DENETLENEN: dict[str, str] = {
    # BUG #414 (DATA-034): kullanıcının para kuralları (emanet hesap, nakit tabanı, tek harcama
    # tavanı) — sayısal sütun yok (`rule_params` JSON) ama bir kuralın gevşetilmesi/silinmesi
    # en az bir bakiye değişikliği kadar izlenmelidir.
    "master_checkpoints": "kullanıcının para kuralları; rule_params JSON, Numeric sütun yok",
}


def denetlenen_tablolar() -> set[str]:
    """`user_id` + Numeric sütunu olan tablolar (+ gerekçeli ekler), muaflar çıkarılmış."""
    out = set()
    for m in Base.registry.mappers:
        t = m.local_table
        if "user_id" in t.c and any(isinstance(c.type, Numeric) for c in t.c):
            out.add(t.name)
    return (out | set(EK_DENETLENEN)) - set(MUAF)


def _ser(v):
    """JSON'a gidecek değer: None/bool/str aynen; sayı, Decimal, tarih, enum → str.
    Sayılar da str'dir ki DB'den okunan Decimal('100.0000') ile nesneye yazılan 100 aynı
    ölçekte karşılaştırılsın (int/Decimal karışımı sahte 'değişti' üretiyordu)."""
    if v is None or isinstance(v, (bool, str)):
        return v
    v = getattr(v, "value", v)
    try:
        from decimal import Decimal
        if isinstance(v, (int, float, Decimal)):
            return format(Decimal(str(v)).normalize(), "f")
    except Exception:  # noqa: BLE001 — sayı gibi görünen ama çevrilemeyen değer str olur
        logger.debug("[denetim] sayı serileştirilemedi: %r", v)
    return str(v)


def _satir(obj) -> dict:
    return {c.key: _ser(getattr(obj, c.key)) for c in inspect(obj).mapper.column_attrs}


def _degisenler(session, obj) -> tuple[dict, dict]:
    """Değişen sütunlar: eski değer DB'DEN okunur (commit sonrası süresi dolmuş nesnede
    ORM geçmişi eski değeri taşımaz — ölçüldü: `deleted=()`), yeni değer nesneden."""
    durum = inspect(obj)
    degisen = [a.key for a in durum.attrs
               if a.key in durum.mapper.column_attrs and a.load_history().added]
    if not degisen:
        return {}, {}
    tablo = durum.mapper.local_table
    pk = durum.mapper.primary_key
    sutunlar = [tablo.c[durum.mapper.column_attrs[k].columns[0].name] for k in degisen]
    kosul = [c == durum.mapper.primary_key_from_instance(obj)[i] for i, c in enumerate(pk)]
    satir = session.connection().execute(select(*sutunlar).where(*kosul)).first()
    once, sonra = {}, {}
    for i, k in enumerate(degisen):
        eski = _ser(satir[i]) if satir is not None else None
        yeni = _ser(getattr(obj, k))
        if eski == yeni:
            continue
        once[k], sonra[k] = eski, yeni
    return once, sonra


def _istek_id() -> str | None:
    try:
        from app.correlation import istek_id
        k = istek_id()
        return None if k in (None, "-") else k
    except Exception:  # noqa: BLE001 — korelasyon yoksa denetim yine yazılır
        logger.debug("[denetim] korelasyon kimliği okunamadı", exc_info=True)
        return None


@event.listens_for(Session, "before_flush")
def _denetim_yaz(session, flush_context, instances):
    try:
        tablolar = denetlenen_tablolar()
        yeni: list[AuditLog] = []
        for obj in list(session.deleted):
            t = getattr(obj, "__tablename__", None)
            # user_id yoksa aktör yok, iz de yok (Goal.user_id nullable — DATA-009; iz
            # satırının NOT NULL'ı flush'ı düşürmesin: denetim işi düşürmez)
            if t not in tablolar or getattr(obj, "user_id", None) is None:
                continue
            yeni.append(AuditLog(user_id=obj.user_id, workspace_id=getattr(obj, "workspace_id", None),
                                 entity=t, entity_id=getattr(obj, "id", None), action="delete",
                                 before_json=json.dumps(_satir(obj), ensure_ascii=False),
                                 istek_id=_istek_id(), created_at=datetime.utcnow()))
        for obj in list(session.dirty):
            t = getattr(obj, "__tablename__", None)
            if t not in tablolar or getattr(obj, "user_id", None) is None or not session.is_modified(obj):
                continue
            once, sonra = _degisenler(session, obj)
            if not once:
                continue
            yeni.append(AuditLog(user_id=obj.user_id, workspace_id=getattr(obj, "workspace_id", None),
                                 entity=t, entity_id=getattr(obj, "id", None), action="update",
                                 before_json=json.dumps(once, ensure_ascii=False),
                                 after_json=json.dumps(sonra, ensure_ascii=False),
                                 istek_id=_istek_id(), created_at=datetime.utcnow()))
        if yeni:
            session.add_all(yeni)
    except Exception:  # noqa: BLE001 — denetim işi düşürmez
        logger.exception("[denetim] iz yazılamadı (işlem etkilenmedi)")
