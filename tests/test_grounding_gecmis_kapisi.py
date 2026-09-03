"""
BUG #322 KAPISI — İZİN LİSTESİ, MODELİN GÖRDÜĞÜ VERİYLE AYNI OLMALI.

ÖLÇÜLEN DEFEKT (3 Eylül 2026, davranış seti, sağlayıcı OpenRouter'a sabitlenmiş 3 koşum):
`grounded` düşüşleri tek tek okundu. Düşüren tutarlar arasında **500** ve **240** vardı ve
koçun cümlesi şuydu:

    "Onayını bekleyen 500 TL yemek (nakit) + 240 TL market (kart) işlenirse:
     Nakit: 4.276 -> 3.536 TL · Kart borcu: 11.976 -> 12.216 TL"

Bu bir halüsinasyon DEĞİL: kullanıcı o iki tutarı setin önceki senaryolarında KENDİSİ
söylemişti ("Bugün 500 TL yemek harcadım nakitten" · "240 TL market aldım kartla") ve
`CoachEngine._load_history` son turları modele AYNEN veriyor. Koç doğru hatırladı.

KÖK NEDEN: `check_grounding` izin listesini `cockpit` + **yalnız o anki** `user_message`ten
kuruyordu. Oysa model son `max_history_turns` turu görüyor. Yani izin listesi modele
verilen veriden DAR: konuşma bir tur ilerlediği anda, kullanıcının kendi söylediği tutar
"cockpit'te bulunamayan tutar" oluyordu. Docstring'deki niyet (*"kullanıcının az önce
söylediği tutar ... geçici izinli sayılır"*) tek turluk bir konuşma için yazılmıştı.

ÜRÜNDEKİ ZARAR SESSİZDİ: `chat()` grounding düşünce güveni **0.4'e** çekiyor. Yani koç,
kullanıcının iki mesaj önce söylediği rakamı doğru tekrarladığı için cezalandırılıyordu.

MEŞRULUK SINAMASI (gevşetmeden önce sorulur — bu gevşetme, koruduğu defekti kaçırır mı?):
  · Uydurma bir tutar ne cockpit'te ne de kullanıcının mesajlarında bulunur → HÂLÂ yakalanır.
  · **KOÇUN KENDİ ÖNCEKİ CEVAPLARI BİLİNÇLİ OLARAK İZİNLİ DEĞİL.** İzin verilseydi bir turda
    uydurulan sayı sonraki turda "aklanmış" olurdu — denetlenen şey modelin çıktısıyken,
    izin listesini yine modelin çıktısından beslemek döngüseldir ve kapıyı kendi kör
    noktasına kilitler. Ayrım şudur: kullanıcı mesajı DIŞ bir olgudur, koç cevabı
    denetlenen şeyin ta kendisidir.
"""
from __future__ import annotations

from app.grounding import check_grounding

COCKPIT = {"nakit_kasa": 4276.0, "kart_borcu": 11976.0}


#: Ölçülen canlı cümlenin ÖZÜ. İlk yazımda cümlenin devamındaki `3.536 TL`yi de
#: kopyalamıştım ve kapı testi düşürdü — HAKLIYDI: 3.536 koçun KENDİ ARİTMETİK HATASIYDI
#: (240 TL kart harcamasını nakitten de düşmüş; doğrusu 4.276 − 500 = 3.776). Yani ölçütün
#: konusu olmayan, üstelik yanlış bir sayıyı örneğe taşımışım. Test iddiasına daraltıldı;
#: türev sayıların bu dedektörle doğrulanamaması AYRI bir bulgudur (defterde yazılı).
_CEVAP = "Onayını bekleyen 500 TL yemek ve 240 TL market işleme alınacak."
_GECMIS = ["Bugün 500 TL yemek harcadım nakitten", "240 TL market aldım kartla"]


def test_gecmis_kullanici_mesajindaki_tutar_ihlal_SAYILMAZ():
    # Kullanıcı önceki turda söyledi, koç bu turda doğru hatırlıyor.
    sonuc = check_grounding(_CEVAP, COCKPIT, gecmis_kullanici_mesajlari=_GECMIS)
    assert sonuc["ok"] is True, sonuc


def test_gecmis_YOKKEN_ayni_cevap_dusuyor_kapinin_olctugu_sey_budur():
    # Aynı metin, geçmiş verilmeden: eski davranış. Bu test, düzeltmenin gerçekten
    # geçmişten geldiğini kanıtlar — yoksa diğeri vakumsal yeşil olurdu.
    sonuc = check_grounding(_CEVAP, COCKPIT)
    assert sonuc["ok"] is False
    assert 500.0 in sonuc["unverified"] and 240.0 in sonuc["unverified"], sonuc


def test_UYDURMA_tutar_gecmis_verilse_de_yakalanir():
    # BUG #256'nın amacı korunuyor: hiçbir yerde geçmeyen sayı hâlâ ihlaldir.
    reply = "Hesabında ayrıca 47.800 TL birikim görünüyor."
    gecmis = ["Bugün 500 TL yemek harcadım nakitten"]
    sonuc = check_grounding(reply, COCKPIT, gecmis_kullanici_mesajlari=gecmis)
    assert sonuc["ok"] is False
    assert 47800.0 in sonuc["unverified"], sonuc


def test_KOCUN_KENDI_onceki_cevabi_izin_listesine_GIRMEZ():
    # Döngüsellik yasağı: bir turda uydurulan sayı, sonraki turda aklanamaz.
    # Çağıran taraf yalnız KULLANICI rolündeki mesajları geçirmekle yükümlü; bu test,
    # sözleşmenin yazılı olduğunu ve gevşetilirse kırıldığını kilitler.
    reply = "Dediğim gibi, 47.800 TL birikimin duruyor."
    kocun_onceki_cevabi = "Hesabında 47.800 TL birikim görünüyor."
    sonuc = check_grounding(reply, COCKPIT, gecmis_kullanici_mesajlari=[])
    assert sonuc["ok"] is False and 47800.0 in sonuc["unverified"]
    # ve koçun cevabı yanlışlıkla listeye konursa kapı KÖRLEŞİR — sözleşmenin gerekçesi bu:
    korlesmis = check_grounding(reply, COCKPIT,
                                gecmis_kullanici_mesajlari=[kocun_onceki_cevabi])
    assert korlesmis["ok"] is True, (
        "Bu satır bir DAVRANIŞ beyanı değil, bir UYARIDIR: koç cevabı listeye girerse "
        "kapı körleşir. Çağıran taraf yalnız role=='user' mesajlarını geçirmelidir.")


def test_gecmis_bos_veya_None_eski_davranisi_bozmaz():
    reply = "Nakit kasan 4.276 TL."
    assert check_grounding(reply, COCKPIT)["ok"] is True
    assert check_grounding(reply, COCKPIT, gecmis_kullanici_mesajlari=[])["ok"] is True
    assert check_grounding(reply, COCKPIT, gecmis_kullanici_mesajlari=None)["ok"] is True


def test_gecmisteki_ETIKETSIZ_tutar_da_izinli_olmali():
    # Kullanıcı "500 harcadım" der (etiketsiz); koç "500 TL" diye etiketleyerek tekrarlar.
    # Yazım biçimi ayrımı yaratmamalı — BUG #316/#321'in aynı dersi.
    reply = "Söylediğin 500 TL'lik yemek harcamasını hesaba katıyorum."
    sonuc = check_grounding(reply, COCKPIT,
                            gecmis_kullanici_mesajlari=["bugün 500 harcadım"])
    assert sonuc["ok"] is True, sonuc


def test_BILINEN_BEDEL_kullanici_mesajindaki_para_olmayan_sayi_da_izinli_olur():
    """
    Bu bir kusur DEĞİL, ölçülmüş ve KABUL EDİLMİŞ bir bedeldir — sessiz kalmasın diye yazılı.

    Kullanıcı mesajından tutar çıkarırken artık `metindeki_tutarlar` kullanılıyor (etiketli
    desen değil), çünkü kullanıcı "bugün 500 harcadım" diye ETİKETSİZ yazar. Bedeli: aynı
    mesajdaki para olmayan sayılar (yıl, adet) da izin listesine girer.

    Neden kabul edildi: grounding'in sorusu *"koç, kullanıcının parası hakkında bir rakam
    UYDURDU mu"*dur. Kullanıcının kendi yazdığı bir sayıyı koçun tekrar etmesi, hangi
    anlamda yazılmış olursa olsun, koçun uydurması değildir. Ters yöndeki hata (kullanıcının
    söylediği tutarı halüsinasyon saymak) ÖLÇÜLDÜ ve üretimde güveni düşürüyordu; bu yöndeki
    hata ise yalnız kullanıcının kendi mesajındaki sayılarla sınırlı ve teorik (L36:
    yanlış tarafa düşmenin bedeli asimetriktir).
    """
    sonuc = check_grounding("Toplam borcun 2.026 TL.", COCKPIT,
                            gecmis_kullanici_mesajlari=["2026 yılı için plan yapalım"])
    assert sonuc["ok"] is True, sonuc


# ---- ÇAĞIRAN TARAFIN SÖZLEŞMESİ (uçtan uca) ------------------------------
#
# Bu bölümü MUTASYON yazdırdı. `check_grounding` seviyesindeki testler, `chat()`in izin
# listesini NEREDEN kurduğunu ölçmüyordu: rol filtresini kaldıran mutasyon (asistan
# cevapları da izinli) 51 testin HİÇBİRİNDEN düşmedi. Yani sözleşme yazılıydı ama
# ölçülmüyordu — kapının kendi kör noktası (aynı sınıf: BUG #311/L67).

from sqlalchemy import create_engine                       # noqa: E402
from sqlalchemy.orm import sessionmaker                    # noqa: E402

from app.models import Base, User, Account, AccountType    # noqa: E402
from app.coach import CoachEngine, LLMResponse             # noqa: E402


class _SabitCevap:
    NAME = "Scripted"; model = "scripted-1"; last_used_provider = "scripted"

    def __init__(self, text):
        self.text = text

    def chat(self, system_prompt, messages, tools):
        return LLMResponse(text=self.text, tool_calls=[],
                           usage={"input_tokens": 1, "output_tokens": 1},
                           provider_used="scripted", model_name="scripted-1")


def _db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="m"))
    s.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=5000.0))
    s.commit()
    return s


def test_UYDURMA_BIR_TURDA_AKLANAMAZ_iki_turluk_uctan_uca():
    """
    Koç 1. turda uydurur, 2. turda TEKRAR eder. İkinci tur da ihlal saymalı.

    Aklanırsa denetim çöker: modelin çıktısı, kendi çıktısının kanıtı olur. Bu yüzden
    `chat()` izin listesine YALNIZ `role == "user"` mesajlarını koyar ve onları geçmiş
    YÜKLENDİĞİ anda alır (tur içi yönlendirmeler modelin metnini `role="user"` ile
    listeye ekliyor — BUG #272 tasarımı; ölçüldü).
    """
    db = _db()
    try:
        motor = CoachEngine(provider=_SabitCevap("Dikkat, 47.800 TL beklenmedik borç var."))
        tur1 = motor.chat(db, 1, "durum nedir?", include_cockpit=True)
        assert tur1["grounding"]["ok"] is False, tur1["grounding"]

        motor2 = CoachEngine(provider=_SabitCevap("Dediğim gibi, 47.800 TL borcun duruyor."))
        tur2 = motor2.chat(db, 1, "peki ne yapmalıyım?", include_cockpit=True)
        assert tur2["grounding"]["ok"] is False, (
            "1. turda uydurulan tutar 2. turda AKLANDI — izin listesi koçun kendi "
            f"cevaplarından besleniyor. {tur2['grounding']}")
        assert 47800.0 in tur2["grounding"]["unverified"]
    finally:
        db.close()


def test_KULLANICININ_onceki_turda_soyledigi_tutar_uctan_uca_IZINLI():
    """Aynı uçtan uca yolun ters yönü — BUG #322'nin ölçülen defektinin ta kendisi."""
    db = _db()
    try:
        CoachEngine(provider=_SabitCevap("Not aldım.")).chat(
            db, 1, "Bugün 500 TL yemek harcadım nakitten", include_cockpit=False)
        sonuc = CoachEngine(provider=_SabitCevap(
            "Söylediğin 500 TL yemek harcaması henüz işlenmedi.")).chat(
            db, 1, "durumu özetle", include_cockpit=True)
        assert sonuc["grounding"]["ok"] is True, sonuc["grounding"]
    finally:
        db.close()
