"""
SIR TARAMASI KAPISI (BUG #261 / SEC-018).

Backlog SEC-018: *".env diskte mevcut → sızma denetimi yap"* — durumu "AÇIK, gitleaks kanıtı
yok" idi. Yani iddia değil, **kanıt eksikti**. Bu tur o kanıtı üretti:

  * `.env` git geçmişinde HİÇ commit edilmemiş (`git log -- .env` boş),
  * çalışma ağacı ve **tüm geçmiş blob'ları** tarandı → sır izi yok,
  * tarama artık CI'da (her push + haftalık cron) koşuyor.

Bu dosya taramanın KENDİSİNİ ölçer: gerçek bir anahtarı yakalıyor mu, işaretli örneği
affediyor mu, ve CI bağlantısı duruyor mu. (Tarayıcı yakalamıyorsa "temiz" çıktısı
yalnızca bir yanılsamadır — L28.)
"""
from __future__ import annotations

from pathlib import Path

from scripts import sir_taramasi as tarama

KOK = Path(__file__).resolve().parent.parent.parent


def test_gercek_anahtar_sekli_yakalanir():
    # secret-ornek: örnekler UYDURMA — tarayıcıyı test etmenin başka yolu yok
    for ornek in (
        "GEMINI=AIzaSyA" + "b" * 30,
        "OPENAI=sk-" + "c" * 30,
        "GROQ=gsk_" + "d" * 30,
        "-----BEGIN RSA PRIVATE KEY" + "-----",  # secret-ornek: parçalı yazım (tarayıcı kendi dosyasını bulmasın)
    ):
        assert any(d.search(ornek) for _, d in tarama.DESENLER), f"yakalanmadı: {ornek[:20]}"


def test_yer_tutucu_ve_yerel_url_gurultu_uretmez():
    """L22: gürültü üreten kapı ciddiye alınmaz — 13 yanlış-pozitifle başlamıştı."""
    for masum in (
        "postgresql://postgres:postgres@localhost:5432/postgres",
        "postgresql://fos_app:REPLACE_WITH_STRONG_APP_ROLE_PASSWORD@db/f",
        "smtp://user:${SMTP_PASS}@smtp.example.com",
    ):
        assert not any(d.search(masum) for _, d in tarama.DESENLER), f"yanlış-pozitif: {masum}"


def test_muafiyet_isareti_ayni_veya_ustteki_satirda_calisir():
    assert tarama._satir_muaf("x = 'AIza...'  # secret-ornek: uydurma")
    assert tarama._satir_muaf("x = 'AIza...'", "# secret-ornek: uydurma")
    assert not tarama._satir_muaf("x = 'AIza...'", "# normal yorum")


def test_calisma_agaci_su_an_temiz():
    """Kapının asıl iddiası: bugün repo temiz."""
    assert tarama.tara_calisma_agaci() == []


def test_gecmis_temiz_ve_baseline_gerekceli():
    assert tarama.tara_gecmis() == []
    baseline = KOK / "scripts" / "sir_taramasi_baseline.txt"
    assert baseline.exists()
    for satir in baseline.read_text(encoding="utf-8").splitlines():
        s = satir.strip()
        if not s or s.startswith("#"):
            continue
        assert "#" in s, f"baseline satırı gerekçesiz: {s}"
        assert len(s.split("#", 1)[1].strip()) >= 15, f"gerekçe çok kısa: {s}"


def test_ci_de_bagli():
    ci = (KOK / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "scripts.sir_taramasi" in ci, "tarama CI'da koşmuyor — kapı yalnız yerelde yaşar"
    assert "--gecmis" in ci, "geçmiş taraması CI'da yok"


def test_env_hic_commit_edilmemis():
    """R3: iddia değil ölçüm — `.env` git geçmişinde var mı?"""
    import subprocess
    cikti = subprocess.run(["git", "log", "--all", "--oneline", "--", ".env", ".env.prod"],
                           cwd=KOK, capture_output=True, text=True).stdout.strip()
    assert cikti == "", f".env geçmişte commit edilmiş: {cikti[:200]}"


# ── BUG #384 / DEVOPS-019: İNDEKS MODU + PRE-COMMIT BAĞI ─────────────────────
# Ölçülen (11 Eyl 2026): tarama yalnız CI'da koşuyordu — push'tan SONRA. O anda anahtar
# zaten uzak depoda ve geçmiştedir. Commit anında soran yoktu (BUG #364/#380 deseni).

def _gecici_depo(tmp_path):
    import subprocess
    kos = lambda *a: subprocess.run(["git", *a], cwd=tmp_path, check=True,  # noqa: E731,S603,S607
                                    capture_output=True, text=True)
    kos("init", "-q")
    kos("config", "user.email", "t@t")
    kos("config", "user.name", "t")
    return kos


def test_staged_modu_indeksi_okur_calisma_agacini_degil(tmp_path):
    """İndekste olan yakalanır; yalnız diskte olan yakalanmaz; diskten silinip indekste
    kalan yine yakalanır — commit'e giren içerik indekstir, dosya değil."""
    kos = _gecici_depo(tmp_path)
    anahtar = "AIzaSyA" + "b" * 30   # secret-ornek: uydurma
    # 1) stage'lenmiş anahtar → bulunur
    (tmp_path / "a.txt").write_text(f"KEY={anahtar}\n", encoding="utf-8")
    kos("add", "a.txt")
    bulgular = tarama.tara_staged(kok=tmp_path)
    assert bulgular == ["a.txt:1: Google/Gemini"], bulgular
    # 2) diskte anahtar silindi ama indekste duruyor → HÂLÂ bulunur
    (tmp_path / "a.txt").write_text("KEY=yok\n", encoding="utf-8")
    assert tarama.tara_staged(kok=tmp_path) == ["a.txt:1: Google/Gemini"]
    # 3) indeks temizlendi, anahtar yalnız diskte → bulunmaz
    kos("add", "a.txt")
    (tmp_path / "b.txt").write_text(f"KEY={anahtar}\n", encoding="utf-8")
    assert tarama.tara_staged(kok=tmp_path) == []
    # 4) işaretli örnek affedilir
    (tmp_path / "c.txt").write_text(f"# secret-ornek: uydurma\nKEY={anahtar}\n", encoding="utf-8")
    kos("add", "c.txt")
    assert tarama.tara_staged(kok=tmp_path) == []


def test_staged_modu_pre_commit_kapisina_bagli():
    """Hook `--staged` ile çağırır ve kırmızıda commit'i ENGELLER (uyarı değil, kapı)."""
    hook = (KOK / ".githooks" / "pre-commit").read_text(encoding="utf-8")
    i = hook.find("scripts.sir_taramasi --staged")
    assert i > 0, "pre-commit sir taramasını çağırmıyor"
    assert "exit 1" in hook[i:i + 400], "sir taraması kırmızısı commit'i engellemiyor"
    assert "|| true" not in hook[i:hook.find("\n", i)], "kapı '|| true' ile uyarıya indirilmiş"
