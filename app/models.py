"""
SQLAlchemy ORM modelleri — 11 tablo:

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

INDEX STRATEJISI:
- transactions(user_id, transaction_date)  — listelemede sik kullanilir
- transactions(account_id, transaction_date) — hesap gecmisi
- coach_memories(user_id, timestamp)        — kronolojik gecmis cekme
- action_history(user_id, applied_at)       — son aksiyonlar
- api_call_log(user_id, called_at)          — gunluk sayim
- coach_insights(user_id, is_active, priority) — aktif notlari oncelige gore
"""

from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text,
    Date, DateTime, ForeignKey, Enum as SQLEnum, Index,
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
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    debts = relationship("PersonalDebt", back_populates="user", cascade="all, delete-orphan")
    checkpoints = relationship("MasterCheckpoint", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("CoachMemory", back_populates="user", cascade="all, delete-orphan")
    pending_actions = relationship("PendingAction", back_populates="user", cascade="all, delete-orphan")
    # Wave-1 yeni iliskiler
    action_history = relationship("ActionHistory", back_populates="user", cascade="all, delete-orphan")
    insights = relationship("CoachInsight", back_populates="user", cascade="all, delete-orphan")
    api_calls = relationship("ApiCallLog", back_populates="user", cascade="all, delete-orphan")


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

    user = relationship("User", back_populates="incomes")


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

    # Kaynak izlenebilirlik (opsiyonel)
    source_message_id = Column(Integer, ForeignKey("coach_memories.id"), nullable=True)

    # Yasam dongusu
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(Date, nullable=True)            # Tarih dolunca otomatik pasif (orn: seyahat tarihi gectikten sonra)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_referenced_at = Column(DateTime, nullable=True)  # Sistem prompt'ta en son ne zaman kullanildi

    user = relationship("User", back_populates="insights")

    __table_args__ = (
        Index("ix_insights_user_active_priority", "user_id", "is_active", "priority"),
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