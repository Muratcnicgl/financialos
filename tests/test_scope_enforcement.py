"""
M70 (Wave-5, IMPROVEMENT #029) — Scope-filtre zorunluluğu (regresyon kilidi).

P1 (Wave-9 publish yolu, BUG #162 dersi) — İKİNCİ KAPI EKLENDİ: `test_scoped_model_sorgusu_
kapsamsiz_olamaz`. M70 kapısı yalnız **scope'suz `user_id ==`** ihlalini yakalıyordu; bir sorguda
sahiplik filtresi HİÇ YOKSA (örn. `db.query(GoalRule).filter(is_active)` — TÜM kullanıcıların
kuralları) sessizce geçiyordu. BUG #162 tam olarak bu kör noktadan geçti: bir kullanıcının işlemi
başka kullanıcının hedefine allocation yazıyordu. Yeni kapı AST tabanlıdır ve `app/` ağacının
TAMAMINI tarar (yalnız router'ları değil).

Gerekçe (tam-proje-durum-raporu RISK #2 / §B23a-b): workspace izolasyonunun TEK koruması
uygulama katmanı `scope_filter`/`_scope`. Yeni bir endpoint scoped-model'i düz `user_id` ile
filtrelerse workspace verisi **sessizce sızar** (derleme/test hatası YOK). Bu test o boşluğu
kapatır: scoped-model'in her `user_id ==` karşılaştırması ya `scope_filter`/`_scope` içinden
geçmeli ya da açık `# scope-exempt: <sebep>` ile işaretlenmeli. Aksi halde TEST KIRILIR.

Kapsam: app/routers/*.py + app/rules_engine.py + app/goal_engine.py + app/debt_strategy.py.
(M72: goal_engine/debt_strategy eklendi — debt_freedom goal'lerindeki Account.user_id kaçağı
bu iki dosya taranmadığı için M70'te görülmemişti; kör nokta kapandı.) Koç/kişisel modeller
(workspace_id'siz) kapsam dışı — yalnız ADR-036 workspace-scoped 12 model denetlenir.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

# ADR-036 workspace-scoped modeller (workspace_id taşıyan) — bunların user_id filtresi scope'lanmalı
SCOPED_MODELS = {
    "Account", "Transaction", "PersonalDebt", "RecurringIncome", "RecurringExpense",
    "MasterCheckpoint", "PendingAction", "NetWorthSnapshot", "Envelope", "WishlistItem",
    "Goal", "DecisionJournal",
}

_ROOT = Path(__file__).resolve().parent.parent
_TARGETS = list((_ROOT / "app" / "routers").glob("*.py")) + [
    _ROOT / "app" / "rules_engine.py",
    _ROOT / "app" / "goal_engine.py",     # M72: debt_freedom Account kaçağı buradaydı
    _ROOT / "app" / "debt_strategy.py",   # M72: collect_debts kaçağı buradaydı
    _ROOT / "app" / "coach_insights.py",  # M73: nightly batch extractor'ları scoped model okur
    # BUG #250 (D31): koçun TEK yazma yolu kapının kapsamı DIŞINDAYDI — 11 ham
    # `Model.user_id == user_id` filtresi hiç denetlenmiyordu. LLM'in DB'ye dokunduğu
    # tek dosya, kapsam kuralının en çok gerektiği yerdir.
    _ROOT / "app" / "action_executor.py",
]

# `<Model>.user_id ==` (models. öneki opsiyonel)
_PATTERN = re.compile(r"\b(?:models\.)?([A-Z][A-Za-z_]+)\.user_id\s*==")


def _violations() -> list[str]:
    out = []
    for f in _TARGETS:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for m in _PATTERN.finditer(line):
                model = m.group(1)
                if model not in SCOPED_MODELS:
                    continue
                # İzin: scope_filter/_scope içinden VEYA açık exempt yorumu
                if "scope_filter" in line or "_scope(" in line:
                    continue
                if "# scope-exempt" in line:
                    continue
                out.append(f"{f.relative_to(_ROOT).as_posix()}:{i}: {model}.user_id (scope'suz) → {line.strip()}")
    return out


def test_scoped_modeller_scope_filtresiz_user_id_kullanmaz():
    """Scoped-model'in her user_id filtresi scope_filter/_scope veya # scope-exempt olmalı."""
    v = _violations()
    assert not v, (
        "Scope'suz user_id filtresi (workspace sızma riski) — scope_filter/_scope kullan "
        "veya '# scope-exempt: <sebep>' ekle:\n" + "\n".join(v)
    )


def test_scope_helper_var():
    """Köprü helper'ları mevcut (regresyon)."""
    from app.workspace_deps import scope_filter, require_write  # noqa: F401
    from app.rules_engine import _scope, workspace_scope  # noqa: F401


# ══════════════════════════════════════════════════════════════════════════════
# P1 KAPISI (BUG #162) — KAPSAMSIZ SORGU YASAĞI (AST tabanlı, app/ ağacının tamamı)
# ══════════════════════════════════════════════════════════════════════════════

import ast  # noqa: E402

# Sahiplik taşıyan modeller: user_id VEYA workspace_id sütunu olanlar (models.py'den doğrulandı)
# + sahipliği EBEVEYN üzerinden olan goal çocukları (BUG #162 tam da buradan sızdı).
OWNED_MODELS = {
    "Account", "ActionHistory", "ApiCallLog", "CoachInsight", "CoachMemory",
    "DecisionJournal", "Envelope", "Feedback", "Goal", "MasterCheckpoint",
    "NetWorthSnapshot", "PendingAction", "PersonalDebt", "ReasoningTrace",
    "RecurringExpense", "RecurringIncome", "Transaction", "WishlistItem",
    # sahiplik ebeveyn Goal üzerinden — kendi sütunu yok, bu yüzden DAHA riskli
    "GoalAllocation", "GoalRule",
}

# Sorguyu "kapsamlı" sayan işaretler (biri yeterli)
_SCOPE_TOKENS = (
    "scope_filter", "_scope(", "workspace_scope",
    "user_id", "workspace_id", "user.id", "current_user.id",
    "# scope-exempt",
)

# Kapsam dışı dosyalar: sahiplik kavramı olmayan/altyapı katmanı
_SKIP_FILES = {"models.py"}


def _owned_model_arg(node: ast.Call) -> str | None:
    """Sorgu çağrısında sahipli bir model geçiyor mu — hangi ŞEKİLDE yazılırsa yazılsın.

    BUG #250 fix (D31): eski hâli YALNIZ `db.query(Model)` / `select(Model)` çıplak
    şeklini görüyordu. Paralel triyaj koşturarak ölçtü — bu dört yaygın şekil kapının
    DIŞINDAYDI (hepsi aynı satırları okur/yazar):

        db.get(Model, id)                     → yakalanmıyordu
        db.query(Model.kolon)                 → yakalanmıyordu
        db.query(func.sum(Model.kolon))       → yakalanmıyordu
        select(Model.kolon)                   → yakalanmıyordu

    Kapının kendisi kör noktalıysa "yeşil" hiçbir şey söylemez (L27). Artık çağrının ilk
    argümanı AST olarak GEZİLİR: içinde sahipli bir model adı geçiyorsa sorgu denetlenir.
    """
    f = node.func
    is_query = (isinstance(f, ast.Attribute) and f.attr in ("query", "get")) or (
        isinstance(f, ast.Name) and f.id == "select"
    )
    if not (is_query and node.args):
        return None
    for alt in ast.walk(node.args[0]):
        ad = None
        if isinstance(alt, ast.Name):
            ad = alt.id
        elif isinstance(alt, ast.Attribute):
            # `Model.kolon` → değer tarafı model adı; `models.Model` → attr tarafı
            ad = alt.value.id if isinstance(alt.value, ast.Name) and alt.value.id in OWNED_MODELS                 else alt.attr
        if ad in OWNED_MODELS:
            return ad
    return None


def _scan_source(src: str, label: str) -> list[str]:
    """Tek kaynak metnindeki kapsamsız sahipli-model sorgularını döndür.

    Ayrı fonksiyon: meta-testler (aşağıda) sentetik kod besleyip tarayıcının GERÇEKTEN
    yakaladığını ispatlar — kapının sessizce hep-yeşil olma ihtimali kapanır.
    """
    out: list[str] = []
    try:
        tree = ast.parse(src)
    except SyntaxError:  # pragma: no cover — app/ derlenebilir olmalı
        return out

    parent: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[id(child)] = node

    lines = src.splitlines()

    def context_source(node: ast.AST) -> str:
        """Sorgunun ait olduğu ifade + onu izleyen 3 kardeş ifadenin HAM kaynak satırları.

        Ham satır kullanılır (AST segmenti değil): `... .first()  # scope-exempt: ...`
        biçimindeki satır-sonu yorumları AST segmentinin DIŞINDA kalır, oysa gerekçe
        işaretinin görülmesi şart.

        Kardeşler dahildir çünkü meşru desen `q = db.query(M)` / `q = q.filter(...)`
        şeklinde iki adımda kapsanabiliyor (fund_tracker, cockpit). Bu, kapıyı
        gevşetmez: BUG #162'deki sorguyu izleyen ifadelerde de sahiplik işareti YOKTU.
        """
        cur: ast.AST = node
        while id(cur) in parent and not isinstance(cur, ast.stmt):
            cur = parent[id(cur)]
        stmt = cur
        block = None
        holder = parent.get(id(stmt))
        if holder is not None:
            for field in ("body", "orelse", "finalbody"):
                lst = getattr(holder, field, None)
                if isinstance(lst, list) and any(s is stmt for s in lst):
                    block = lst
                    break
        chunk = [stmt]
        if block is not None:
            i = next(k for k, s in enumerate(block) if s is stmt)
            chunk += block[i + 1:i + 4]
        start = min(s.lineno for s in chunk)
        end = max(getattr(s, "end_lineno", s.lineno) or s.lineno for s in chunk)
        # BUG #250 (D31): gerekçe yazmanın DOĞAL yeri sorgunun ÜSTÜDÜR. Pencere yalnız
        # ifadeden aşağı bakarsa yazar `# scope-exempt:` notunu üste koyar, kapı görmez ve
        # gerekçe yazılmış olmasına rağmen kırmızı kalır (yazarı satır-sonu yorumuna
        # zorlamak uzun gerekçeyi imkânsız kılar). Üstteki bitişik yorum satırları dahil.
        ust = start - 1
        while ust > 0 and lines[ust - 1].strip().startswith("#"):
            ust -= 1
        return "\n".join(lines[ust:end])

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        model = _owned_model_arg(node)
        if model is None:
            continue
        if any(tok in context_source(node) for tok in _SCOPE_TOKENS):
            continue
        out.append(f"{label}:{node.lineno}: {model} sorgusu KAPSAMSIZ (sahiplik filtresi yok)")
    return out


def _unscoped_queries() -> list[str]:
    """app/ ağacının tamamını tara."""
    out: list[str] = []
    for path in sorted((_ROOT / "app").rglob("*.py")):
        if "__pycache__" in str(path) or path.name in _SKIP_FILES:
            continue
        out += _scan_source(path.read_text(encoding="utf-8"),
                            path.relative_to(_ROOT).as_posix())
    return out


def test_scoped_model_sorgusu_kapsamsiz_olamaz():
    """Sahipli model sorgusu ya kapsamlı olmalı ya da '# scope-exempt: <gerekçe>' taşımalı.

    BUG #162 regresyon kilidi: kapsamsız sorgu = başka kullanıcının satırlarını okumak/yazmak.
    Gerekçeli istisna (sahipliği başka yerde doğrulanmış id-lookup, sistem-geneli cron vb.)
    açık yorumla işaretlenir — sessiz geçiş yok.
    """
    v = _unscoped_queries()
    assert not v, (
        "Kapsamsız sorgu (çapraz-kullanıcı sızıntı riski) — sahiplik filtresi ekle "
        "veya '# scope-exempt: <gerekçe>' yaz:\n" + "\n".join(v)
    )


# ── Meta-testler: KAPI ÇALIŞIYOR MU? (yeşil kapı, çalışan kapı demek değildir) ──

def test_meta_kapi_bug_162_desenini_yakalar():
    """BUG #162'nin BİREBİR deseni (kapsamsız GoalRule sorgusu) yakalanmalı.

    Bu test olmasaydı, tarayıcı sessizce bozulduğunda (örn. bir regex/AST değişikliği)
    kapı hep-yeşil kalır ve gerçek sızıntıyı kaçırırdı.
    """
    kotu = (
        "rules = (\n"
        "    db.query(models.GoalRule)\n"
        "    .filter(models.GoalRule.is_active.is_(True))\n"
        "    .all()\n"
        ")\n"
        "created = []\n"
    )
    assert _scan_source(kotu, "sentetik.py"), "Tarayıcı BUG #162 desenini kaçırdı"


def test_meta_kapi_kapsamli_sorguyu_yakalamaz():
    """Yanlış-pozitif kontrolü: sahiplik filtresi olan sorgu ihlal sayılmamalı."""
    iyi = (
        "rules = (\n"
        "    db.query(models.GoalRule)\n"
        "    .join(models.Goal)\n"
        "    .filter(scope_filter(models.Goal, tx.user_id, tx.workspace_id))\n"
        "    .all()\n"
        ")\n"
    )
    assert not _scan_source(iyi, "sentetik.py")


def test_meta_kapi_satir_sonu_exempt_yorumunu_gorur():
    """`# scope-exempt:` satır-sonu yorumu (AST segmenti dışında kalır) tanınmalı."""
    exempt = "acc = db.query(Account).filter(Account.id == tx.account_id).first()  # scope-exempt: tx'in kendi hesabı\n"
    assert not _scan_source(exempt, "sentetik.py")
    ciplak = "acc = db.query(Account).filter(Account.id == tx.account_id).first()\n"
    assert _scan_source(ciplak, "sentetik.py")


# ── BUG #250 (D31) meta-testleri: tarayıcının KÖR NOKTALARI kapandı mı ──
#
# Denetimin D31 bulgusu, kapının kendisini ölçerek çıktı: `db.query(Model)` dışındaki dört
# yaygın şekil hiç görülmüyordu. "Yeşil kapı, çalışan kapı demek değildir" — bu yüzden her
# şekil için SENTETİK bir örnek besleyip yakalandığını ispatlıyoruz (L27).

_KOR_NOKTA_ORNEKLERI = {
    "db.get": "acc = db.get(Account, payload['account_id'])\n",
    "kolon-sorgusu": "adlar = db.query(Account.name).all()\n",
    "aggregate": "from sqlalchemy import func\ntoplam = db.query(func.sum(Transaction.amount)).scalar()\n",
    "select-kolon": "satirlar = db.execute(select(Transaction.amount)).all()\n",
}


@pytest.mark.parametrize("ad", sorted(_KOR_NOKTA_ORNEKLERI))
def test_meta_kapi_eski_kor_noktalari_gorur(ad):
    bulgular = _scan_source(_KOR_NOKTA_ORNEKLERI[ad], "sentetik.py")
    assert bulgular, f"Tarayıcı '{ad}' şeklini hâlâ görmüyor (D31 kör noktası açık)"


@pytest.mark.parametrize("ad", sorted(_KOR_NOKTA_ORNEKLERI))
def test_meta_kapsamli_yazim_yanlis_alarm_uretmez(ad):
    """L6: kapı ürünü kıramaz — sahiplik filtresi VARSA sessiz kalmalı."""
    kapsamli = _KOR_NOKTA_ORNEKLERI[ad].replace(
        ".all()", ".filter(Account.user_id == user_id).all()"
    ).replace(".scalar()", ".filter(Transaction.user_id == user_id).scalar()"
    ).replace("db.get(Account, payload['account_id'])",
              "db.get(Account, payload['account_id'])  # scope-exempt: sahiplik çağıranda doğrulandı")
    assert not _scan_source(kapsamli, "sentetik.py"), (
        f"'{ad}' kapsamlı yazımında yanlış alarm üretiliyor"
    )


def test_meta_gerekce_sorgunun_USTUNE_yazilabilir():
    """Gerekçenin doğal yeri sorgunun üstüdür; kapı oraya bakmazsa yazar cezalandırılır."""
    kod = (
        "# scope-exempt: sahiplik ebeveyn üzerinden doğrulandı (uzun gerekçe buraya yazılır)\n"
        "toplam = db.query(func.sum(GoalAllocation.amount)).filter(\n"
        "    GoalAllocation.goal_id == goal.id\n"
        ").scalar()\n"
    )
    assert not _scan_source(kod, "sentetik.py"), "Üstteki gerekçe yorumu görülmüyor"


def test_koc_yazma_yolu_kapi_kapsaminda():
    """D31'in ikinci yarısı: LLM'in TEK yazma yolu kapının dosya kapsamındaydı mı."""
    hedefler = {f.name for f in _TARGETS}
    assert "action_executor.py" in hedefler, (
        "Koçun yazma yolu kapsam kapısının dışında — kural en çok orada gerekli"
    )


def test_kapsam_tabani_taranan_dosya_sayisi():
    """L23: hedef listesi daralırsa kapı sessizce küçülür."""
    assert len(_TARGETS) >= 20, f"Yalnız {len(_TARGETS)} dosya taranıyor — kapsam düşmüş"
