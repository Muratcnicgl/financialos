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
