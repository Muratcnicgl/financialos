"""
K2 KAPISI — PROMPT BÜTÇESİ (gerileme sayacı).

ÖLÇÜLEN DEFEKT (1 Eylül 2026, `masterprompt-koc.md` K0):
    `V3_GOD_MODE_PROMPT` **19.444 karakter / 317 satır / ~8.838 token** ve içinde
    **39 adet 🔴 yasak** var. Groq'un `413` gövdesi tek isteğin boyutunu SAYIYLA verdi:
    *"Limit 8000, Requested 12364"*. Yani sistem promptu her isteğin **%71'i**;
    kullanıcının gerçek finansal durumuna kalan pay **%29**.

    Bu bir "büyük dosya" sorunu değil, KENDİNİ BESLEYEN BİR DÖNGÜ:
        prompt şişer → istek büyür → yalnız ucuz+yüksek limitli model kaldırır
        → zayıf muhakeme yeni hata üretir → her hataya yeni bir 🔴 eklenir → başa dön.
    Ölçülen sonuç: sağlayıcı zincirinin 4 halkasından 3'ü bu boyutu kaldıramıyor
    (Groq `413`), koç sınıfının en küçük modeline mahkûm kalıyor ve eval %82,9 → %71,4
    düşüyor. **Bir koçluk ürününün bütçesinin %71'ini "şunu yapma" listesine harcaması
    tasarımın tersidir.**

NEDEN KAPI:
    Şişme HİÇBİR testi kırmıyordu. Her 🔴 tek tek bakıldığında haklıydı — hepsi gerçek
    bir bug'ın izi. Zarar tek tek eklemelerde değil, TOPLAMDA birikiyor ve toplamı kimse
    ölçmüyordu. `masterprompt-koc.md` **K-KURAL 5**: *"Prompt şişmesi bir REGRESYONDUR."*
    Bu dosya o kuralın uygulanmasıdır.

SÖZLEŞME (`kalite-baseline.json` / BUG #309 ile aynı felsefe):
    · Sayılar **HEDEF DEĞİL, TAVAN**. Aşılırsa CI kırılır.
    · Tavan **yalnız AŞAĞI** çekilir. Prompt küçüldüğünde tavan da düşürülür — kazanım
      kilitlenir; aksi halde bir tur küçültüp ertesi tur sessizce geri şişirmek serbest olur.
    · Tavanı YÜKSELTMEK bilinçli bir karardır ve `masterprompt-koc.md` §10'a **yazılı
      gerekçeyle** kaydedilir. Otomatik yükseltme YOKTUR.

ÖLÇÜM BİRİMİ NEDEN KARAKTER:
    Token sayısı sağlayıcıya/tokenizer'a göre değişir ve ağ ya da model dosyası ister —
    bir CI kapısı bunlara bağlanamaz (`tests/test_ag_kapisi.py` ruhu). Karakter sayısı
    deterministiktir ve şişmeyle **tek yönlü** ilişkilidir: karakter artmadan token artamaz.

    ORAN DÜZELTİLDİ (1 Eyl 2026, akşam): ilk sürüm TR için ~2,2 karakter/token VARSAYDI ve
    promptu ~8.838 token sanıyordu. Groq'un GERÇEK tokenizer'ıyla ölçüldü: aynı prompt
    **6.855 token**, yani oran **~2,84 karakter/token**. Varsayımın bedeli sadece bir sayı
    değildi — "prompt isteğin %71'i" tespiti de yanlıştı; gerçek pay **%55**
    (6.855 / 12.364), kalan %45 cockpit + tools. Hedef hesabı buna göre düzeltildi.
    Ölçüm komutu: gerçek sistem promptuyla tek Groq çağrısı → `usage.prompt_tokens`.

MUTASYONLA KANITLANDI:
    M1: prompt'a bir satır eklendi        → KIRMIZI (tavan aşıldı)
    M2: prompt'tan büyük bir blok silindi → KIRMIZI (tavanı aşağı çek, kazanımı kilitle)
    M3: yeni bir 🔴 eklendi               → KIRMIZI (yasak sayacı)
"""
from __future__ import annotations

from app.coach import V3_GOD_MODE_PROMPT

# ============================================================
# TAVANLAR — 1 Eylül 2026'da ÖLÇÜLEN değerler (K0 baseline)
# ============================================================

#: `len(V3_GOD_MODE_PROMPT)` — `{PAYLOAD_SABLONLARI}` ve `{SAHTE_NIYET_ORNEKLERI}`
#: yerleştirildikten SONRAKİ hâli, yani telden gerçekten geçen metin. Alt listeler
#: (örn. `uslup_kurallari.prompt_sahte_niyet_listesi()`) büyürse bu sayı da büyür — kapı
#: onu da görür, çünkü şişme nereden gelirse gelsin aynı bedeli ödetir.
TAVAN_KARAKTER = 19_444

#: 🔴 (U+1F534) işaretli yasak sayısı. Ayrı sayılıyor çünkü döngünün MOTORU bu:
#: her bug'a bir yasak eklemek, promptu büyütmenin varsayılan yolu hâline gelmişti.
#: Karakter tavanı tek başına bunu gizleyebilir (uzun bir blok silinip iki kısa yasak
#: eklenirse toplam düşer ama desen sürer) — iki eksen ayrı ölçülür.
TAVAN_KIRMIZI = 39

#: Kazanım kilidi: ölçülen değer tavanın bu kadar ALTINA inerse kapı, tavanın
#: güncellenmesini ister. Gevşek bırakmak, sonraki turun sessizce geri şişmesine izin verir.
#: 400 karakter ≈ 180 token ≈ orta boy bir 🔴 blok; gürültüyü tolere eder, kazanımı kaçırmaz.
KILIT_PAYI = 400

_KIRMIZI = "\U0001F534"


def _olcum() -> tuple[int, int]:
    return len(V3_GOD_MODE_PROMPT), V3_GOD_MODE_PROMPT.count(_KIRMIZI)


def test_prompt_tavani_asilmadi():
    """
    K-KURAL 5. Prompt'a satır eklemek bir kusuru düzeltmenin VARSAYILAN yolu değildir.

    Bu kırmızıysa sorulacak soru "tavanı yükseltelim mi?" DEĞİL, şudur: eklemek istediğin
    kural (a) kodla/kapıyla zaten korunuyor mu, (b) yalnız zayıf modelde mi gerekiyor,
    (c) gerçekten sözleşme mi? (a) ve (b) prompt'a YAZILMAZ — koda yazılır.
    """
    karakter, _ = _olcum()
    assert karakter <= TAVAN_KARAKTER, (
        f"Sistem promptu şişti: {karakter} > tavan {TAVAN_KARAKTER} "
        f"(+{karakter - TAVAN_KARAKTER} karakter ≈ +{(karakter - TAVAN_KARAKTER) / 2.2:.0f} token, "
        f"HER İSTEKTE ödenir).\n"
        "Prompt şişmesi bir REGRESYONDUR (masterprompt-koc.md K-KURAL 5): istek büyüdükçe "
        "güçlü modeller erişilemez hâle gelir ve koç en zayıf modele mahkûm kalır — "
        "ölçüldü: Groq ücretsiz katmanı 12.364 token'lık isteği 413 ile reddediyor.\n"
        "Tavanı yükseltmek bilinçli bir karardır ve masterprompt-koc.md §10'a yazılı "
        "gerekçeyle kaydedilir."
    )


def test_kirmizi_yasak_sayaci_asilmadi():
    """
    Döngünün motoru: her bug'a bir 🔴 eklemek. Sayaç bunu görünür kılar.

    Yeni bir yasak GERÇEKTEN gerekiyorsa, önce eskilerden birinin koda taşınıp
    prompt'tan çıkarılması beklenir (tavan sabit kalır, sözleşme netleşir).
    """
    _, kirmizi = _olcum()
    assert kirmizi <= TAVAN_KIRMIZI, (
        f"🔴 yasak sayısı arttı: {kirmizi} > tavan {TAVAN_KIRMIZI}.\n"
        "Bir yasağı prompt'a eklemeden önce sor: bu kural kodla zorlanabilir mi? "
        "(örnek: sahte tamamlama `sahte_tamamlama_iddiasi_var` ile, tool eşiği "
        "`intent_rules.propose_sunulsun_mu` ile ZORLANIYOR — prompt'taki metin ikinci "
        "savunma hattıdır, birinci değil.)"
    )


def test_kazanim_kilitlendi():
    """
    Tavan yalnız AŞAĞI çekilir. Prompt küçüldüyse tavan da düşürülmelidir; yoksa bir tur
    kazanılan yer, sonraki turda sessizce geri doldurulur (ruff baseline'ının
    `kalite-baseline.json`'daki aynı ilkesi: "düşerse tavan aşağı çekilir ve kazanım
    kilitlenir").
    """
    karakter, kirmizi = _olcum()
    assert karakter > TAVAN_KARAKTER - KILIT_PAYI, (
        f"Prompt küçülmüş ({karakter} ≤ tavan {TAVAN_KARAKTER} - {KILIT_PAYI}) ama tavan "
        f"güncellenmemiş. TAVAN_KARAKTER = {karakter} yaz ve kazanımı kilitle; "
        "masterprompt-koc.md §9.0'daki oranı da güncelle."
    )
    assert kirmizi > TAVAN_KIRMIZI - 5 or kirmizi == TAVAN_KIRMIZI, (
        f"🔴 sayısı belirgin düşmüş ({kirmizi} vs tavan {TAVAN_KIRMIZI}) — "
        f"TAVAN_KIRMIZI = {kirmizi} yazarak kazanımı kilitle."
    )


def test_olcum_raporu_bilgi_amacli(capsys):
    """
    Kapı değil, GÖRÜNÜRLÜK: `-s` ile koşulduğunda güncel bütçeyi basar. Bir sayının
    kapıya bağlı olması onu görünür yapmaz; K0'ın dersi buydu — eval üç hafta koşulmadı.
    """
    # L66: kapının çıktısı cp1254 (Windows varsayılan) konsolda da basılabilmelidir —
    # 🔴 karakterinin KENDİSİ yazdırılırsa UnicodeEncodeError ile kapı, ölçtüğü şeyden
    # bağımsız bir sebeple kırmızıya döner. Sayacın adı yazıyla geçer.
    karakter, kirmizi = _olcum()
    satir = V3_GOD_MODE_PROMPT.count("\n") + 1
    print(
        f"\n  PROMPT BUTCESI: {karakter} karakter / {satir} satir / ~{karakter / 2.2:.0f} token"
        f" / {kirmizi} kirmizi-yasak"
        f"\n  TAVAN         : {TAVAN_KARAKTER} karakter / {TAVAN_KIRMIZI} kirmizi-yasak"
        f"\n  HEDEF (K2)    : istegin <= %40'i (bugun ~%71 - Groq olcumu 12.364 token/istek)"
    )
    assert karakter > 0
