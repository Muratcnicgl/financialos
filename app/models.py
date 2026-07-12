"""
SQLAlchemy ORM modelleri — 14 tablo:

ANA TABLOLAR (8):
1. User              — kullanıcı (single-user şu an, multi-user'a hazır)
2. Account           — hesaplar (cash/credit_card/loan/investment)
3. RecurringIncome   — düzenli gelirler (maaş, burs vb.)
4. Transaction       — işlemler (gelir/gider)
5. PersonalDebt      — kişisel borç/alacak (Efe ödemeleri vb.)
6. MasterCheckpoint  — kırmızı çizgiler / kurallar
7. CoachMemory       — koç sohbet geçmişi
8. PendingAction     — onay bekleyen aksiyonlar (function calling)

YENİ TABLOLAR (3) — Wave-1 mukemmellestirme:
9.  ActionHistory    — Onaylanan her aksiyon kalıcı log (Audit + geri al)
10. CoachInsight     — Koç'un kendi kalıcı notları (uzun vadeli hafıza)
11. ApiCallLog       — LLM cagri sayisi (Gemini 1500/gun limiti takibi)

H2G5 GOAL ENGINE TABLOLARI (3) — ADR-024 (Allocation-Based, Monarch Goals 3.0 pattern):
12. Goal             — hedef tanımı (debt_freedom | cash_target)
13. GoalAllocation   — transaction → goal bağlantısı (pozitif=katkı, negatif=çekim)
14. GoalRule         — otomatik allocation kuralları

INDEX STRATEJISI:
- transactions(user_id, transaction_date)  — listelemede sik kullanilir
- transactions(account_id, transaction_date) — hesap gecmisi
- coach_memories(user_id, timestamp)        — kronolojik gecmis cekme
- action_history(user_id, applied_at)       — son aksiyonlar
- api_call_log(user_id, called_at)          — gunluk sayim
- coach_insights(user_id, is_active, priority) — aktif notlari oncelige gore
"""

from datetime import datetime, date, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text,
    Date, DateTime, ForeignKey, Enum as SQLEnum, Index, UniqueConstraint,
    Numeric, PrimaryKeyConstraint, func, text, JSON,
)
from sqlalchemy.orm import relationship
from app.database import Base
import enum


# ============================================================
# ENUM'LAR
# ============================================================

class AccountType(str, enum.Enum):
    cash = "cash"
    credit_card = "credit_card"
    loan = "loan"
    investment = "investment"


class TransactionType(str, enum.Enum):
    income = "income"
    expense = "expense"
    transfer = "transfer"


class DebtDirection(str, enum.Enum):
    receivable = "receivable"  # Bana ödenecek (alacak)
    payable = "payable"        # Ben ödeyeceğim (borç)


class CheckpointType(str, enum.Enum):
    red_line = "red_line"      # Asla geçilmeyecek sınır
    strategy = "strategy"      # Stratejik tercih
    rule = "rule"              # Genel kural
    context = "context"        # Bağlam bilgisi


class ActionStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    executed = "executed"
    failed = "failed"


# === Wave-1 yeni enum'lar ===

class ActionSource(str, enum.Enum):
    """ActionHistory: aksiyonu kim tetikledi?"""
    user = "user"        # Kullanıcı doğrudan girdi (form, hızlı giriş)
    coach = "coach"      # Koç önerdi, kullanıcı onayladı
    system = "system"    # Otomatik (örn: backup, recurring otomatik kayıt)


class InsightPriority(str, enum.Enum):
    """CoachInsight: not önemi."""
    critical = "critical"  # Asla unutulmamalı (örn: 14 Nisan Gürcistan seyahati)
    high = "high"          # Stratejik öneme sahip
    normal = "normal"      # Genel bağlam
    low = "low"            # Geçici, eskiyince temizlenebilir


class ApiCallStatus(str, enum.Enum):
    """ApiCallLog: çağrı durumu."""
    success = "success"
    failed = "failed"
    rate_limited = "rate_limited"


class OperationName(str, enum.Enum):
    """ReasoningTrace: hangi operasyon tipi kaydediliyor."""
    RULE_CHECK = "rule_check"
    LLM_CALL = "llm_call"
    EXECUTE_TOOL = "execute_tool"
    OBSERVATION = "observation"
    FINAL_ANSWER = "final_answer"


# ============================================================
# ANA TABLOLAR (8)
# ============================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    accounts = relationship("Account", back_populates="user", cascade="all, delete-orphan")
    incomes = relationship("RecurringIncome", back_populates="user", cascade="all, delete-orphan")
    expenses = relationship("RecurringExpense", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    debts = relationship("PersonalDebt", back_populates="user", cascade="all, delete-orphan")
    checkpoints = relationship("MasterCheckpoint", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("CoachMemory", back_populates="user", cascade="all, delete-orphan")
    pending_actions = relationship("PendingAction", back_populates="user", cascade="all, delete-orphan")
    # Wave-1 yeni iliskiler
    action_history = relationship("ActionHistory", back_populates="user", cascade="all, delete-orphan")
    insights = relationship("CoachInsight", back_populates="user", cascade="all, delete-orphan")
    api_calls = relationship("ApiCallLog", back_populates="user", cascade="all, delete-orphan")
    # B2: Net değer trend
    net_worth_snapshots = relationship("NetWorthSnapshot", back_populates="user", cascade="all, delete-orphan")
    # Wave-2 H1G1: Decision Journal
    decision_journal_entries = relationship(
        "DecisionJournal", back_populates="user", cascade="all, delete-orphan"
    )


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    account_type = Column(SQLEnum(AccountType), nullable=False)

    # Ortak alanlar
    balance = Column(Float, default=0.0, nullable=False)  # Nakit/yatırım: pozitif | Kart/kredi: borç (pozitif)
    notes = Column(Text, nullable=True)

    # === Kredi kartı alanları ===
    credit_limit = Column(Float, nullable=True)
    statement_day = Column(Integer, nullable=True)  # Ayın hangi günü kesim (örn: 2)
    payment_day = Column(Integer, nullable=True)    # Ayın hangi günü son ödeme (örn: 12)

    # === Kredi alanları ===
    interest_rate = Column(Float, nullable=True)         # Aylık faiz oranı (%)
    monthly_payment = Column(Float, nullable=True)       # Aylık taksit
    remaining_installments = Column(Integer, nullable=True)
    next_payment_date = Column(Date, nullable=True)

    # === Yatırım alanları ===
    fund_code = Column(String(20), nullable=True)        # TEFAS kodu (örn: TLY)
    lot_count = Column(Float, nullable=True)             # Lot sayısı
    cost_per_lot = Column(Float, nullable=True)          # Lot başı maliyet
    current_price = Column(Float, nullable=True)         # Son güncel fiyat
    last_price_update = Column(DateTime, nullable=True)
    is_emanet = Column(Boolean, default=False, nullable=False)  # ⚠️ Dokunulmaz emanet

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account")

    __table_args__ = (
        Index("ix_accounts_user_type", "user_id", "account_type"),
    )


class RecurringIncome(Base):
    __tablename__ = "recurring_incomes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    day_of_month = Column(Integer, nullable=False)  # Ayın kaçında gelir (1-31)
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_triggered_year_month = Column(String(7), nullable=True)  # A2: "2026-05" — dedup

    user = relationship("User", back_populates="incomes")


class RecurringExpense(Base):
    """A3: Düzenli giderler — abonelik, fatura, kira vb. Otomatik propose_action üretir."""
    __tablename__ = "recurring_expenses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)  # zorunlu: kart mı nakit mi
    category = Column(String(50), nullable=True)        # "abonelik", "fatura", "kira" vb.
    day_of_month = Column(Integer, nullable=False)       # Ayın kaçında ödenir (1-31)
    is_active = Column(Boolean, default=True, nullable=False)
    last_triggered_year_month = Column(String(7), nullable=True)  # A3 dedup: "2026-05"
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="expenses")


class Envelope(Base):
    """
    FEAT-001: Kategori bazlı aylık BÜTÇE ZARFI (YNAB / Actual Budget zarf yöntemi).
    Her kategoriye aylık tutar ayrılır; o kategorideki harcama zarftan düşülür. Harcama
    ayrı bir allocation tablosunda DEĞİL, mevcut Transaction.category üzerinden izlenir
    (tek doğruluk kaynağı) — bu ay harcanan = SUM(expense, category, bu ay). Zarf aşımında
    görünür uyarı. monthly_amount her ay için geçerli (recurring bütçe).
    """
    __tablename__ = "envelopes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    category = Column(String(50), nullable=False)          # Transaction.category ile eşleşir
    monthly_amount = Column(Numeric(14, 2), nullable=False)  # aylık bütçe (Decimal — RULE-006)
    is_active = Column(Boolean, default=True, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        # (user, category) tekildir — bir kategori için tek zarf. Bu constraint aynı zamanda
        # user_id prefix'li aramalar için index sağlar (dual-index anti-pattern'den kaçınıldı).
        UniqueConstraint("user_id", "category", name="uq_envelope_user_category"),
    )


class WishlistItem(Base):
    """
    FEAT-032: 24-saat impuls bekleme / istek listesi. Büyük/plansız alımı HEMEN yapmak yerine
    listeye ekle; 24 saat sonra koç "hâlâ istiyor musun?" diye sorar (fırsat maliyetiyle —
    FEAT-030). İmpuls harcamayı kırar (davranışsal finans; borç-batık için doğrudan lever).
    Alım gerçekleşirse propose_action → onay → execute (KURAL SIFIR: liste ekleme mutasyon
    değil, niyet kaydı). created_at + 24h = review zamanı (scheduler gerekmez; cockpit türetir).
    """
    __tablename__ = "wishlist_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    item = Column(String(200), nullable=False)             # ne almak isteniyor
    amount = Column(Numeric(14, 2), nullable=False)        # tahmini tutar (Decimal — RULE-006)
    note = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending")  # pending | bought | dismissed
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_wishlist_user_status", "user_id", "status"),
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    transaction_type = Column(SQLEnum(TransactionType), nullable=False)
    amount = Column(Float, nullable=False)
    category = Column(String(50), nullable=True)         # yiyecek, ulaşım, fatura vb.
    description = Column(Text, nullable=True)
    transaction_date = Column(Date, nullable=False, default=date.today)
    is_card_expense = Column(Boolean, default=False, nullable=False)  # Gölge muhasebe için
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="transactions")
    account = relationship("Account", back_populates="transactions")

    __table_args__ = (
        # Listeleme + tarih bazli filtre (en sik kullanim)
        Index("ix_transactions_user_date", "user_id", "transaction_date"),
        # Hesap detay paneli
        Index("ix_transactions_account_date", "account_id", "transaction_date"),
        # Kategori bazli rapor
        Index("ix_transactions_user_category", "user_id", "category"),
    )


class PersonalDebt(Base):
    __tablename__ = "personal_debts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    counterparty = Column(String(100), nullable=False)  # Örn: "Efe"
    direction = Column(SQLEnum(DebtDirection), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    due_date = Column(Date, nullable=True)
    is_paid = Column(Boolean, default=False, nullable=False)
    paid_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="debts")

    __table_args__ = (
        Index("ix_debts_user_due", "user_id", "due_date"),
        Index("ix_debts_user_paid", "user_id", "is_paid"),
    )


class MasterCheckpoint(Base):
    __tablename__ = "master_checkpoints"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    checkpoint_type = Column(SQLEnum(CheckpointType), nullable=False)
    priority = Column(Integer, default=2, nullable=False)  # 1=en yüksek, 3=en düşük
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="checkpoints")

    __table_args__ = (
        Index("ix_checkpoints_user_active_priority", "user_id", "is_active", "priority"),
    )


class CoachMemory(Base):
    __tablename__ = "coach_memories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(20), nullable=False)  # "user" | "assistant" | "tool"
    content = Column(Text, nullable=False)
    # BUG #036 fix: tool-aware history
    tool_calls_json = Column(Text, nullable=True)         # assistant turunda propose_action varsa JSON
    tool_call_id = Column(String(64), nullable=True)      # "tool" rolundeki satirlarda eslestirme ID'si
    pending_action_ids_json = Column(Text, nullable=True) # BUG #046: propose edilen action ID'leri JSON list
    timestamp = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="memories")

    __table_args__ = (
        # En son N mesaji cekmek icin (coach.py _load_history)
        Index("ix_memories_user_timestamp", "user_id", "timestamp"),
    )


class PendingAction(Base):
    __tablename__ = "pending_actions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action_type = Column(String(50), nullable=False)
    # Aksiyon türleri:
    # - update_account_balance
    # - add_transaction
    # - mark_debt_paid
    # - sell_investment
    # - update_fund_price
    # - add_master_checkpoint

    payload = Column(Text, nullable=False)  # JSON string
    summary = Column(Text, nullable=False)  # Kullanıcıya gösterilecek özet
    status = Column(SQLEnum(ActionStatus), default=ActionStatus.pending, nullable=False)
    error_message = Column(Text, nullable=True)
    warning = Column(Text, nullable=True)   # BUG #027: limit aşımı vb. uyarılar
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    # BUG #047: recurring trigger dedup — hangi kayıttan geldi
    source_recurring_id   = Column(Integer, nullable=True)    # RecurringIncome/Expense id
    source_recurring_type = Column(String(20), nullable=True) # 'income' | 'expense'

    user = relationship("User", back_populates="pending_actions")

    __table_args__ = (
        Index("ix_pending_user_status", "user_id", "status"),
    )


# ============================================================
# WAVE-1 YENİ TABLOLAR (3)
# ============================================================

class ActionHistory(Base):
    """
    Onaylanan ve uygulanan her aksiyonun kalıcı log'u.
    Audit, geri-al, ve "geçen ay neler yaptın" sorgulari icin temel kaynak.

    Kullanim ornekleri:
    - Koc: "geçen 30 gunde 2 kez TLY satisi yaptin"
    - Frontend: "Son aksiyonlar" timeline panel
    - Geri al: reverted_by_action_id ile zincir kuruluyor
    """
    __tablename__ = "action_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Aksiyon tanim ve kaynak
    action_type = Column(String(50), nullable=False)
    payload = Column(Text, nullable=False)             # JSON snapshot
    summary = Column(Text, nullable=False)             # Kullaniciya gosterilen ozet
    source = Column(SQLEnum(ActionSource), default=ActionSource.user, nullable=False)
    pending_action_id = Column(Integer, ForeignKey("pending_actions.id"), nullable=True)

    # Sonuc durumu
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)

    # Onceki/sonraki finansal anlik goruntu (kiyaslama icin)
    net_worth_before = Column(Float, nullable=True)
    net_worth_after = Column(Float, nullable=True)
    cash_before = Column(Float, nullable=True)
    cash_after = Column(Float, nullable=True)

    # Geri al zinciri
    reverted_at = Column(DateTime, nullable=True)
    reverted_by_action_id = Column(Integer, ForeignKey("action_history.id"), nullable=True)

    applied_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="action_history")

    __table_args__ = (
        Index("ix_action_history_user_applied", "user_id", "applied_at"),
        Index("ix_action_history_user_type", "user_id", "action_type"),
    )


class CoachInsight(Base):
    """
    Koç'un kendi kalıcı notları. Sohbet biten konularda koc kendi icin
    önemli baglami buraya yazar. Sonraki sohbetlerde sistem prompt'a otomatik
    enjekte edilir — boylece koc Murat'i 6 ay sonra da hatirlar.

    Ornekler:
    - "Murat 28 Nisan'da Gurcistan seyahatinin TLY satisiyla finanse edilecegini soyledi"
    - "Murat kart kapatmak yerine yatirim onerimi 3 kez reddetti — risk profili yuksek"
    - "Murat Temmuz'da Efe alacaklari biteceginden tek basina kalacak"
    """
    __tablename__ = "coach_insights"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    content = Column(Text, nullable=False)              # Tek cumlelik veya kisa paragraf
    category = Column(String(50), nullable=True)        # 'preference', 'event', 'pattern', 'goal' vb.
    priority = Column(SQLEnum(InsightPriority), default=InsightPriority.normal, nullable=False)
    dedup_key = Column(String(80), nullable=True)       # CoachInsight aktif: LLM uretilen slug, upsert dedup

    # Kaynak izlenebilirlik (opsiyonel)
    source_message_id = Column(Integer, ForeignKey("coach_memories.id"), nullable=True)

    # Yasam dongusu
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(Date, nullable=True)            # Tarih dolunca otomatik pasif
    created_at = Column(DateTime, default=datetime.utcnow)
    last_referenced_at = Column(DateTime, nullable=True)  # Wave-3: aktive edilecek, su an yazilmiyor

    # Wave-2 H1G2: Davranissal Hafiza alanlari (ADR-016 Saf Karma A)
    insight_type = Column(String(50), nullable=True)            # 'decision_rhythm', 'mc_reference_frequency' vb.
    title = Column(String(200), nullable=True)                  # UNIQUE(user_id, insight_type, title) icin
    confidence_basis = Column(String(30), nullable=True)        # 'data_grounded' | 'mc_rule' | 'pattern_grounded'
    source_refs = Column(Text, nullable=True)                   # JSON list: ["action_history:42", ...]
    evidence_count = Column(Integer, default=0, nullable=False, server_default="0")
    counter_evidence_count = Column(Integer, default=0, nullable=False, server_default="0")
    last_evidence_at = Column(DateTime, nullable=True)
    last_counter_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="active", nullable=True)  # 'active' | 'invalidated' | 'dormant'
    activated_at = Column(DateTime, nullable=True)
    last_seen_at = Column(DateTime, nullable=True)
    para_category = Column(String(20), nullable=True)
    archived_at = Column(DateTime, nullable=True)
    archived_reason = Column(String(50), nullable=True)
    sort_priority = Column(Integer, default=5, nullable=False, server_default="5")

    user = relationship("User", back_populates="insights")

    __table_args__ = (
        Index("ix_insights_user_active_priority", "user_id", "is_active", "priority"),
        Index("uix_insights_user_dedup", "user_id", "dedup_key", unique=True),
        # Wave-2 H1G2: davranissal hafiza UPSERT kilidi
        UniqueConstraint("user_id", "insight_type", "title", name="uq_insights_type_title"),
    )


class ApiCallLog(Base):
    """
    LLM cagrilarinin gunluk sayisi ve token kullanimi.
    Gemini 1500 ist/gun ucretsiz limit takibi icin kritik. %80'e ulasinca
    Cockpit'te uyari cikar. Ayni zamanda gelecekte maliyet analizi icin de
    veri kaynagi.
    """
    __tablename__ = "api_call_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    provider = Column(String(20), nullable=False)       # 'gemini' | 'anthropic'
    model = Column(String(50), nullable=False)          # 'gemini-2.5-flash' vb.
    status = Column(SQLEnum(ApiCallStatus), default=ApiCallStatus.success, nullable=False)

    # Token sayilari (provider donerse doldurulur, donmezse null)
    tokens_in = Column(Integer, nullable=True)
    tokens_out = Column(Integer, nullable=True)

    # Tool kullanim ozeti
    tool_calls_count = Column(Integer, default=0, nullable=False)

    # Hata bilgisi
    error_code = Column(String(20), nullable=True)
    error_message = Column(Text, nullable=True)

    # Sure (ms) — performans takibi
    duration_ms = Column(Integer, nullable=True)

    called_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="api_calls")

    __table_args__ = (
        # Gunluk sayim icin (called_at >= bugun_basi)
        Index("ix_api_calls_user_called", "user_id", "called_at"),
        # Provider bazli ayri sayim
        Index("ix_api_calls_user_provider_called", "user_id", "provider", "called_at"),
    )


class NetWorthSnapshot(Base):
    """
    Günlük net değer snapshot'ı — B2 Net Değer Trend Grafiği için.
    Her Cockpit isteğinde bugünkü değer otomatik kaydedilir (ensure_today_snapshot).
    Geçmiş veriler backfill scripti ile doldurulur.
    """
    __tablename__ = "net_worth_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    snapshot_date = Column(Date, nullable=False)

    net_worth_seen = Column(Float, nullable=False)       # Görülen (operasyonel, alacaksız)
    net_worth_full = Column(Float, nullable=False)       # Tam (stratejik, alacaklı)
    cash = Column(Float, nullable=False)
    card_debt = Column(Float, nullable=False)
    loan_debt = Column(Float, nullable=False)
    investment_value = Column(Float, nullable=False)
    receivables = Column(Float, nullable=False, default=0.0)

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="net_worth_snapshots")

    __table_args__ = (
        UniqueConstraint("user_id", "snapshot_date", name="uq_nws_user_date"),
        Index("ix_nws_user_date", "user_id", "snapshot_date"),
    )


# ═══════════════════════════════════════════════════════════════
# Price History (Wave-2 B4 Aşama 2 - ADR-012)
# ═══════════════════════════════════════════════════════════════

class PriceSource(str, enum.Enum):
    """Fiyat verisinin nereden geldiğini gösterir.

    Okuma önceliği (app/price_providers/router.py'de):
    manual > tefas > yfinance > isyatirim

    Yeni kaynak eklemek için ADR güncellenmeli.
    """
    TEFAS = "tefas"
    MANUAL = "manual"
    YFINANCE = "yfinance"
    ISYATIRIM = "isyatirim"


class PriceHistory(Base):
    """Fon/hisse fiyat geçmişi - tek doğruluk kaynağı (ADR-012).

    Aynı (fund_code, price_date) için birden fazla kaynaktan fiyat
    saklanabilir. Okuma sırasında öncelik kod tarafında belirlenir
    (app/price_providers/router.py).

    Account.current_price denormalize cache olarak kalır - okuma hızı için.
    Tek doğruluk kaynağı bu tablodur.

    Kompozit PK: (fund_code, price_date, source)
    Sektör paterni: Quantstart Securities Master + Beancount pedantic mod.
    """
    __tablename__ = "price_history"

    fund_code = Column(String(20), nullable=False)
    price_date = Column(Date, nullable=False)
    source = Column(
        SQLEnum(
            PriceSource,
            name="pricesource",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    close_price = Column(Numeric(19, 4), nullable=False)
    fetched_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        PrimaryKeyConstraint(
            "fund_code", "price_date", "source",
            name="pk_price_history",
        ),
        Index("ix_price_history_fund_date", "fund_code", "price_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<PriceHistory("
            f"fund_code={self.fund_code!r}, "
            f"date={self.price_date}, "
            f"source={self.source}, "
            f"price={self.close_price})>"
        )


# ============================================================
# Decision Journal (Wave-2 Hafta 1 - Bridgewater + Munger paterni)
# ============================================================


class DecisionJournal(Base):
    """
    Bridgewater Decision Journal + Munger Premortem entegrasyonu.

    Pain + Reflection = Progress dongusu:
    - Karar verilirken: predicted_outcome + confidence + mc_rules + cockpit_hash
    - Karar verilirken (opsiyonel): premortem_scenarios (Hafta 2 Gun 3'te dolar)
    - Ay sonu: actual_outcome + outcome_score + lessons_learned

    cockpit_snapshot_hash Hafta 1 Gun 4 Replayable Trajectory ile eslesir.
    """

    __tablename__ = "decision_journal"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # index tek-sutunlu degil; idx_decision_journal_user_time composite'i kapsıyor

    # KARAR
    decision_text = Column(Text, nullable=False)
    decision_type = Column(String(40), nullable=True)
    related_action_id = Column(
        Integer,
        ForeignKey("action_history.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ONCESI (karar verilirken)
    predicted_outcome = Column(Text, nullable=True)
    confidence_at_decision = Column(Integer, nullable=True)
    mc_rules_applied = Column(Text, nullable=True)  # JSON list
    cockpit_snapshot_hash = Column(String(64), nullable=True)  # SHA256

    # PREMORTEM (Hafta 2 Gun 3'te dolar)
    premortem_scenarios = Column(Text, nullable=True)  # JSON list
    premortem_run_at = Column(DateTime(timezone=True), nullable=True)

    # SONRASI (ay sonu retro)
    actual_outcome = Column(Text, nullable=True)
    outcome_evaluated_at = Column(DateTime(timezone=True), nullable=True)
    outcome_score = Column(Integer, nullable=True)

    # DERS
    lessons_learned = Column(Text, nullable=True)

    # ZAMAN
    decided_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # PARA KATEGORI (Tiago Forte CODE)
    para_category = Column(
        String(20), nullable=False, default="project", server_default="project"
    )

    # ILISKILER
    user = relationship("User", back_populates="decision_journal_entries")
    related_action = relationship("ActionHistory")

    __table_args__ = (
        Index("idx_decision_journal_user_time", "user_id", "decided_at"),
        Index(
            "idx_decision_journal_pending_eval",
            "user_id",
            sqlite_where=text("outcome_evaluated_at IS NULL"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<DecisionJournal(id={self.id}, type={self.decision_type}, "
            f"decided_at={self.decided_at}, "
            f"evaluated={self.outcome_evaluated_at is not None})>"
        )


class ReasoningTrace(Base):
    __tablename__ = "reasoning_traces"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    trace_id = Column(String(36), nullable=False)
    step_index = Column(Integer, nullable=False)
    parent_step_id = Column(Integer, ForeignKey("reasoning_traces.id"), nullable=True)
    coach_memory_id = Column(Integer, ForeignKey("coach_memories.id"), nullable=True)

    operation_name = Column(SQLEnum(OperationName), nullable=False)
    intent = Column(Text, nullable=True)
    action_input_json = Column(Text, nullable=True)
    observation = Column(Text, nullable=True)
    inference = Column(Text, nullable=True)

    confidence_score = Column(Float, nullable=True)

    provider_system = Column(String(50), nullable=True)
    model_name = Column(String(100), nullable=True)
    usage_input_tokens = Column(Integer, nullable=True)
    usage_output_tokens = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)

    error = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    coach_memory = relationship("CoachMemory", backref="reasoning_traces")
    parent = relationship("ReasoningTrace", remote_side=[id], backref="children")

    __table_args__ = (
        Index("ix_reasoning_traces_trace_id_step_index", "trace_id", "step_index"),
        Index("ix_reasoning_traces_coach_memory_id", "coach_memory_id"),
        Index("ix_reasoning_traces_created_at", "created_at"),
        Index("ix_reasoning_traces_user_id", "user_id"),
    )


# ============================================================
# H2G5 GOAL ENGINE (ADR-024) — Allocation-Based Goal Tracking
# Pattern: Monarch Money Goals 3.0 (transaction-linked goals)
# ============================================================


class GoalRule(Base):
    """Otomatik allocation kurali. Yeni tx geldiginde evaluate_rules_for_transaction
    tarafindan degerlendirilir; eslesen kurallara gore GoalAllocation yaratilir."""
    __tablename__ = "goal_rules"

    id = Column(Integer, primary_key=True, index=True)
    goal_id = Column(Integer, ForeignKey("goals.id", ondelete="CASCADE"),
                     nullable=False)  # index __table_args__'da

    name = Column(String(200), nullable=False)
    priority = Column(Integer, nullable=False, default=0)

    criteria = Column(JSON, nullable=False)
    # Ornek: {"tx_type": "transfer", "destination_account_type": ["savings", "cash"]}
    # Ornek: {"tx_type": "income", "amount_min": 5000}

    allocation_type = Column(String(20), nullable=False)
    # 'full' | 'percent' | 'fixed'
    allocation_value = Column(Numeric(10, 2), nullable=True)
    # percent: (0, 100], fixed: TL tutari; full icin NULL

    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    goal = relationship("Goal", back_populates="rules")

    __table_args__ = (
        Index("ix_goal_rules_goal_id", "goal_id"),
    )


class Goal(Base):
    """Finansal hedef — debt_freedom veya cash_target.

    current_amount + progress_percent + projected_completion_date:
    GoalAllocation toplamından hesaplanır (goal_engine.refresh_goal).
    Her refresh_goal çağrısında güncellenir, cache olarak tutulur.
    """
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)

    goal_type = Column(String(20), nullable=False)
    # 'debt_freedom' | 'cash_target' — index __table_args__'da

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    title = Column(String(200), nullable=False)
    target_amount = Column(Numeric(14, 2), nullable=False)
    target_date = Column(Date, nullable=True)

    # debt_freedom için goal yaratım anındaki toplam borç (Account.loan + credit_card)
    baseline_amount = Column(Numeric(14, 2), nullable=True)

    status = Column(String(20), nullable=False, default="active")
    # 'active' | 'achieved' | 'paused' | 'abandoned' — index __table_args__'da

    # Progress cache — refresh_goal() tarafından güncellenir
    current_amount = Column(Numeric(14, 2), nullable=False, default=0)
    progress_percent = Column(Numeric(5, 2), nullable=False, default=0)
    projected_completion_date = Column(Date, nullable=True)
    last_refreshed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow,
                        onupdate=datetime.utcnow)
    achieved_at = Column(DateTime, nullable=True)

    allocations = relationship("GoalAllocation", back_populates="goal",
                               cascade="all, delete-orphan")
    rules = relationship("GoalRule", back_populates="goal",
                         cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_goals_goal_type", "goal_type"),
        Index("ix_goals_status", "status"),
    )


class GoalAllocation(Base):
    """Tek transaction'ın tek goal'e ne kadar katkı verdiği.

    amount > 0: tasarruf/katkı (contribution)
    amount < 0: çekim/azalma (withdrawal)

    Aynı (goal_id, transaction_id) çifti birden fazla kez kaydedilemez
    — unique constraint uq_goal_tx bunu engeller.
    """
    __tablename__ = "goal_allocations"

    id = Column(Integer, primary_key=True, index=True)
    goal_id = Column(Integer, ForeignKey("goals.id", ondelete="CASCADE"),
                     nullable=False)  # index __table_args__'da
    transaction_id = Column(Integer,
                            ForeignKey("transactions.id", ondelete="CASCADE"),
                            nullable=False)  # index __table_args__'da

    amount = Column(Numeric(14, 2), nullable=False)
    source = Column(String(20), nullable=False, default="manual")
    # 'manual' | 'rule' | 'system'

    rule_id = Column(Integer,
                     ForeignKey("goal_rules.id", ondelete="SET NULL"),
                     nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    goal = relationship("Goal", back_populates="allocations")
    transaction = relationship("Transaction")
    rule = relationship("GoalRule", foreign_keys=[rule_id])

    __table_args__ = (
        UniqueConstraint("goal_id", "transaction_id", name="uq_goal_tx"),
        Index("ix_goal_allocations_goal_id", "goal_id"),
        Index("ix_goal_allocations_transaction_id", "transaction_id"),
    )