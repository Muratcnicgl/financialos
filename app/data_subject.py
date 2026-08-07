"""
BUG #243 (denetim D26 + D27 + D28) — KVKK VERİ-SAHİBİ HAKLARI: TEK KAYNAK.

"Tüm verinizi indirin" (KVKK m.11 taşınabilirlik) ve "tüm veriniz kalıcı olarak silinir"
(m.7 unutulma) taahhütleri **elle bakılan listelere** dayanıyordu. Şema büyüdükçe listeler
geride kaldı, üç ayrı defekt üretti:

- **D26:** export kullanıcının **bcrypt şifre hash'ini** ve **OAuth kimliğini** döküyordu
  (`_row_to_dict` / `_row` TÜM kolonları basar). Bu dosya kullanıcının diskine iner,
  e-postayla paylaşılır, buluta yedeklenir; hash çevrimdışı kırılabilir. Kimlik doğrulama
  sırrı taşınabilirlik hakkının kapsamında DEĞİLDİR.
- **D27:** silme sonrası kullanıcının **e-postası ve operatörün kişi hakkındaki notu**
  `beta_invites`'ta kalıyordu (purge yalnız `user_id` kolonuna bakıyordu; oradaki kolon
  `used_by_user_id`).
- **D28:** UI'nin ve KVKK metninin gösterdiği uç (`/api/users/me/export`) iki tabloyu
  (`goal_allocations`, `goal_rules`) hiç dökmüyordu — çünkü **iki ayrı export uygulaması**
  vardı ve tamlık testi ötekini ölçüyordu (BUG #241 ile aynı sınıf: aynı vaadin iki yolu).

Bu modül üç şeyi tek yere toplar:
  1. **KAYIT** — her tablonun kullanıcı verisi olup olmadığı ve nasıl bağlandığı. Şemada
     sınıflandırılmamış tablo kalamaz (`tests/test_kvkk_veri_sahibi_kapisi.py`): yeni tablo
     ekleyen kişi "bu kullanıcı verisi mi" sorusunu yanıtlamak ZORUNDA.
  2. **disa_aktar** — export'un TEK uygulaması (iki uç da bunu döner → ayrışamazlar).
  3. **GIZLENEN_ALANLAR / ANONİMLEŞTİRME** — export'tan çıkarılan kimlik sırları ve silmede
     temizlenen dolaylı atıflar.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.models import (
    Base, User, Workspace, Account, Transaction, RecurringIncome, RecurringExpense,
    PersonalDebt, Goal, GoalAllocation, GoalRule, Envelope, WishlistItem, Feedback, Category,
    DemoDataMarker, MasterCheckpoint, NetWorthSnapshot, CoachMemory, CoachInsight,
    PendingAction, ActionHistory, DecisionJournal, ReasoningTrace, ApiCallLog,
    WorkspaceMembership, BetaInvite, ErrorLog,
)

# Export'a ASLA girmeyen kullanıcı kolonları — kimlik doğrulama sırrı/iç durum.
# (Taşınabilirlik hakkı "hesabıma nasıl girildiğini" değil "verimi" kapsar.)
GIZLENEN_ALANLAR: frozenset[str] = frozenset({
    "password_hash",    # bcrypt hash: çevrimdışı kırılabilir, tekrar kullanılan şifreyi yakar
    "oauth_sub",        # Google/GitHub kalıcı tekil kimliği: profil eşleştirmeye yarar
    "token_version",    # oturum geçersizleştirme sayacı: iç durum, kullanıcı verisi değil
})

# Sır GİBİ görünen ama kullanıcının KENDİ verisi olan kolonlar (gizlenmez) — gerekçeli.
# `tests/test_kvkk_veri_sahibi_kapisi.py` yeni bir "hash/token/secret" kolonunun buraya ya da
# GIZLENEN_ALANLAR'a yazılmasını zorunlu kılar: sınıflandırma unutulamaz.
SIR_GORUNUMLU_AMA_KULLANICI_VERISI: frozenset[str] = frozenset({
    "tokens_in", "tokens_out",                      # LLM kullanım sayaçları (maliyet şeffaflığı)
    "usage_input_tokens", "usage_output_tokens",    # aynı: koç izlerindeki kullanım
    "cockpit_snapshot_hash",                        # karar anındaki durumun bütünlük atıfı
})


@dataclass(frozen=True)
class TabloKaydi:
    """Bir tablonun veri-sahibi hakları karşısındaki konumu."""
    baglanti: str                       # user_id | goal | owner | kullanici_satiri | anonimlestir | kullanici_disi
    model: Optional[type] = None
    disa_aktarma_anahtari: Optional[str] = None
    gerekce: str = ""
    anonim_alanlar: tuple[str, ...] = field(default_factory=tuple)

    @property
    def disa_aktarilir(self) -> bool:
        return self.disa_aktarma_anahtari is not None


def _u(model, anahtar: str) -> TabloKaydi:
    """`user_id` taşıyan sıradan kullanıcı-verisi tablosu."""
    return TabloKaydi("user_id", model, anahtar)


# Şemadaki HER tablo burada sınıflandırılır (kapı bunu dayatır).
KAYIT: dict[str, TabloKaydi] = {
    # — kullanıcının kendi kaydı —
    "users": TabloKaydi("kullanici_satiri", User, "user"),
    # — finansal defter —
    "accounts": _u(Account, "accounts"),
    "transactions": _u(Transaction, "transactions"),
    "recurring_incomes": _u(RecurringIncome, "recurring_incomes"),
    "recurring_expenses": _u(RecurringExpense, "recurring_expenses"),
    "personal_debts": _u(PersonalDebt, "personal_debts"),
    "envelopes": _u(Envelope, "envelopes"),
    # BUG #264 (ADR-046): kategori seti kullanıcının kendi verisidir — yeniden adlandırdığı
    # adlar ve "kart varsayılanı" tercihi onun kararı. Dışa aktarımda yer alır, hesap
    # silinince silinir (aksi halde defterin şeması kullanıcıdan sonra da yaşardı).
    "categories": _u(Category, "categories"),
    "wishlist_items": _u(WishlistItem, "wishlist_items"),
    "master_checkpoints": _u(MasterCheckpoint, "master_checkpoints"),
    "net_worth_snapshots": _u(NetWorthSnapshot, "net_worth_snapshots"),
    "demo_data_markers": _u(DemoDataMarker, "demo_data_markers"),
    "feedback": _u(Feedback, "feedback"),
    # — hedefler (çocukları user_id taşımaz → hedef üzerinden bağlanır, D28) —
    "goals": _u(Goal, "goals"),
    "goal_allocations": TabloKaydi("goal", GoalAllocation, "goal_allocations"),
    "goal_rules": TabloKaydi("goal", GoalRule, "goal_rules"),
    # — eylem/karar/koç kayıtları —
    "pending_actions": _u(PendingAction, "pending_actions"),
    "action_history": _u(ActionHistory, "action_history"),
    "decision_journal": _u(DecisionJournal, "decision_journal"),
    "coach_memories": _u(CoachMemory, "coach_memory"),
    "coach_insights": _u(CoachInsight, "coach_insights"),
    "reasoning_traces": _u(ReasoningTrace, "reasoning_traces"),
    "api_call_log": _u(ApiCallLog, "api_call_log"),
    # — workspace —
    "workspace_memberships": _u(WorkspaceMembership, "workspace_memberships"),
    "workspaces": TabloKaydi("owner", Workspace, "workspaces"),
    # — kullanıcı verisi TAŞIYAN ama silinmeyen (anonimleştirilen) kayıtlar —
    "beta_invites": TabloKaydi(
        "anonimlestir", BetaInvite, None,
        gerekce=("Davet KODU işletme kaydıdır (kod tekrar kullanılamamalı); kişisel kısmı "
                 "— e-posta, operatör notu, kullanıcı atfı — silmede temizlenir (D27)."),
        anonim_alanlar=("email", "note", "used_by_user_id"),
    ),
    "error_logs": TabloKaydi(
        "anonimlestir", ErrorLog, None,
        gerekce=("Hata kaydı operatörün teşhis verisidir (içeriği kullanıcı verisi değil); "
                 "yalnız `last_user_id` atfı silmede temizlenir."),
        anonim_alanlar=("last_user_id",),
    ),
    # — kullanıcı verisi DEĞİL —
    "price_history": TabloKaydi(
        "kullanici_disi", gerekce="Piyasa verisi (fon/hisse fiyatı) — kişiye bağlı değil."),
    "rate_limit_hits": TabloKaydi(
        "kullanici_disi",
        gerekce=("Kova anahtarı `bucket:IP` — hesaba değil isteğe bağlı, kısa ömürlü "
                 "kötüye-kullanım sayacı; kullanıcı kimliği taşımaz.")),
    "revoked_tokens": TabloKaydi(
        "kullanici_disi",
        gerekce="Yalnız token jti + tarih; kişisel veri taşımaz (oturum kara listesi)."),
    "scheduler_runs": TabloKaydi(
        "kullanici_disi", gerekce="Cron çalışma kayıtları — sistem işletim verisi."),
}


# ============================================================
# EXPORT (TEK UYGULAMA — iki uç da buradan döner)
# ============================================================

def _json_deger(v):
    if isinstance(v, enum.Enum):
        return v.value
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def _satir(kayit, gizle: bool = False) -> dict:
    return {c.name: _json_deger(getattr(kayit, c.name))
            for c in kayit.__table__.columns
            if not (gizle and c.name in GIZLENEN_ALANLAR)}


def disa_aktar(db: Session, user: User) -> dict:
    """Kullanıcının TÜM verisi — KAYIT'tan türetilir, kimlik sırları hariç (D26/D28)."""
    veri: dict = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "schema": "financialos-export-v1",
        "user": _satir(user, gizle=True),
    }
    # scope-exempt: KVKK export = kullanıcının TÜM verisi (workspace kapsamı değil, kişi kapsamı)
    hedef_idler = [g.id for g in db.query(Goal).filter(Goal.user_id == user.id).all()]

    for kayit in KAYIT.values():
        if not kayit.disa_aktarilir or kayit.baglanti == "kullanici_satiri":
            continue
        model = kayit.model
        if kayit.baglanti == "user_id":
            satirlar = db.query(model).filter(model.user_id == user.id).all()
        elif kayit.baglanti == "goal":
            satirlar = (db.query(model).filter(model.goal_id.in_(hedef_idler)).all()
                        if hedef_idler else [])
        elif kayit.baglanti == "owner":
            satirlar = db.query(model).filter(model.owner_user_id == user.id).all()
        else:                                   # pragma: no cover — kayıt tutarsızlığı
            continue
        veri[kayit.disa_aktarma_anahtari] = [_satir(s) for s in satirlar]
    return veri


# ============================================================
# SİLME YARDIMCISI (purge_user_data buradan besleniyor)
# ============================================================

def anonimlestirilecekler() -> list[TabloKaydi]:
    """Silinmeyen ama kişisel izi temizlenmesi gereken tablolar (D27)."""
    return [k for k in KAYIT.values() if k.baglanti == "anonimlestir"]
