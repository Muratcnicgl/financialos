"""
Coach Eval Harness — LLM koç kalitesinin OBJEKTİF ölçümü.

Vizyon (wave3-vision Bölüm 6, Eksen J — "eval-driven development"): koç geliştirmeyi
"fix-and-hope"tan objektif ölçüme taşır. Bir koç cevabını DETERMİNİSTİK kriterlerle puanlar —
JUDGE LLM GEREKMEZ; tüm sinyaller chat() çıktısından + grounding'den türetilir. Bu yüzden:
  - Aynı harness hem ScriptedProvider (framework birim testi) hem GERÇEK sağlayıcı
    (canlı kalite ölçümü, scripts/eval_runner.py) ile çalışır.
  - Regresyon ağı: bir prompt/kod değişikliği koç kalitesini düşürürse pass_rate düşer.

Ölçülen kriterler (senaryo bazında seçilir):
  grounded       cevaptaki her TL tutarı cockpit'e izlenebilir (grounding.ok)
  no_action      soru/analiz/gelecek-niyette propose_action OLUŞMAZ (KURAL SIFIR)
  action         gerçekleşmiş eylemde propose_action oluşur
  no_confidence  [CONFIDENCE] işareti kullanıcıya sızmaz
  no_fake        tool çağrılmadan "kaydettim" gibi sahte tamamlama yok
  format         analiz/rapor cevabında ## başlık var
  cevapladi      koç FİİLEN konuştu (BUG #276: olumsuz kriterleri ölü koç da geçiyordu)
  uslup          yazılı üslup sözleşmesi ihlali yok (BUG #277: dalkavukluk/dolgu/"siz"
                 hitabı/iç jargon/boş teselli/nutuk — tek kaynak app/uslup_kurallari.py)
  no_fake_niyet  onay bekleyen kayıt yokken "onayını bekliyorum" iddiası yok
  oz             basit soruya duvar metin yazılmadı (ÖZ VE NET OL)

Bu modül SAF ölçüm mantığıdır (rules_engine ruhu); DB'ye yazmaz.
"""

# kota-exempt: degerlendirme kosum araci (scripts/eval_runner.py) — urun yuzeyi degil,
#              kullanici tetikleyemez. Gercek saglayiciyla kosulursa maliyeti operator ustlenir.

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# BUG #275: sahte-tamamlama tanıması burada KOPYALANMAZ — ürün kodunun tek kaynağı kullanılır.
# Ölçüm: buradaki eski kopya (5 kök) BUG #271'in ölçtüğü 12 cümlenin **7'sini kaçırıyordu**
# ("işleme aldım", "kayda geçirdim", "not olarak girdim", "sisteme yazdım", "hallettim",
# "düştüm", "oluşturdum") → eval, yeniden ortaya çıkan bir regresyonu YEŞİL puanlardı. Ters
# yönde de kırıktı: nesneden bağımsız `tamamladı\w*` kökü "Analizi tamamladım" gibi meşru
# cümlelerde 4/4 yanlış-pozitif verdi → sağlıklı sağlayıcı haksız yere düşerdi.
# Bir kalite kapısının kendi ölçütü, koruduğu sözleşmeden zayıf (ya da farklı) olamaz (L46).
from app.coach import sahte_tamamlama_iddiasi_var
# Wave-K: "beklenen tutar cevapta geçti mi" sorusu, grounding'in AYNA sorusudur ve aynı
# ayıraç kümesine bağlıdır — ikinci bir sayı deseni yazmak BUG #316'yı tekrar ederdi.
from app.grounding import tutar_gecti
# BUG #277: koçun YAZILI üslup sözleşmesi (dalkavukluk/dolgu/hitap/iç jargon/boş teselli/
# nutuk + sahte niyet) tek kaynaktan ölçülür. Ölçüm: bu maddelerin her birini açıkça ihlal
# eden 9 persona, ihlalsiz referansla BİREBİR aynı %100 pass_rate alıyordu — harness koçun
# DOĞRU İŞ yapıp yapmadığını ölçüyor, DÜZGÜN KONUŞUP konuşmadığını hiç ölçmüyordu (L48).
from app.uslup_kurallari import BASIT_CEVAP_TAVANI, ihlaller, sahte_niyet_iddiasi_var

CRITERIA = {"grounded", "no_action", "action", "no_confidence", "no_fake", "format",
            "cevapladi", "uslup", "no_fake_niyet", "oz",
            # Wave-K / K-B — ALTIN SENARYO kriterleri (bkz. scripts/coach_altin.py)
            "dogru_sonuc", "tuzak_yok"}

#: Yalnız altın senaryolarda anlamlı olan kriterler — beklenti/tuzak tanımı ister.
ALTIN_KRITERLER = {"dogru_sonuc", "tuzak_yok"}

# BUG #276: OLUMSUZ kriterleri (aksiyon yok / sahte tamamlama yok / güven işareti yok) hiç
# cevap vermeyen bir koç da sağlar. Ölçüm: tamamen ölü sağlayıcıyla (RESIL-004 dalı) koşulan
# eval **%83.3 pass_rate** veriyordu; "Tamam." diyen sessiz koç da aynı puanı alıyordu — yani
# koşumun manşet sayısı, koçun çalışıp çalışmadığını AYIRT ETMİYORDU. Her senaryo bu yüzden
# en az bir OLUMLU kriter taşır: `cevapladi`.
_ANLAMLI_CEVAP_MIN = 20   # "Tamam." (6) ve benzeri boş onaylar bu eşiğin altında kalır


@dataclass
class EvalScenario:
    """
    Tek bir eval senaryosu: kullanıcı mesajı + geçmesi beklenen kriterler.

    ALTIN SENARYO ALANLARI (Wave-K, K-B ölçütü) — koçun BİÇİMİNİ değil MUHAKEMESİNİ ölçer:
      * `beklenen_tutarlar` — doğru cevabın taşımak ZORUNDA olduğu tutarlar (yazım biçiminden
        bağımsız eşleşir; bkz. `grounding.tutar_gecti`).
      * `beklenen_desenler` — doğru cevabın taşıması gereken KAVRAM izleri (regex, IGNORECASE).
        Yalnız sayı istemek yetmez: sayıları sıralayan ama muhakeme etmeyen bir cevap geçerdi.
      * `tuzak_tutarlar`   — yanlış muhakemenin imzası olan tutarlar (ör. kredide "kalan taksit
        toplamı"nı kapama bedeli sanmak).

    TUZAĞIN ŞARTLI OLMASI BİLİNÇLİDİR: tuzak tutar, yalnız `beklenen_tutarlar` cevapta YOKKEN
    ihlal sayılır. Çünkü en iyi cevap ikisini birden söyler ("kalan taksit toplamın 79.625,85
    ama bugün kapatırsan 48.510,41 ödersin") — koşulsuz bir tuzak yasağı tam olarak o EN İYİ
    cevabı düşürürdü. BUG #316'nın dersi: bir zorlama ancak ölçütü kadar iyidir; ölçüt doğru
    cevabı cezalandırıyorsa ölçüt yanlıştır.

    ÖLÇÜTÜN BİLİNEN SINIRI (dürüstçe yazılıdır): bu kriterler bir TABANDIR, tavan değil.
    Doğru sayıları ve kavram kelimelerini içeren ama gerekçesi zayıf bir cevap geçebilir.
    Muhakemenin niteliği desenle ölçülemez; onu `--judge` (app/coach_judge.py) ölçer ve o bir
    CI kapısı değildir. Taban, "koç bu senaryoda YANLIŞ sayıya varmadı"yı garanti eder.
    """
    name: str
    user_message: str
    checks: List[str]
    include_cockpit: bool = True
    beklenen_tutarlar: List[float] = field(default_factory=list)
    beklenen_desenler: List[str] = field(default_factory=list)
    tuzak_tutarlar: List[float] = field(default_factory=list)

    def __post_init__(self):
        bad = set(self.checks) - CRITERIA
        if bad:
            raise ValueError(f"Bilinmeyen kriter(ler): {bad}")
        # VAKUMSAL YEŞİL YASAĞI (L28): beklentisi olmayan bir `dogru_sonuc` HER cevabı geçirir
        # ("hiç beklenti yoktu, hepsi karşılandı"), yani senaryo ölçüyor gibi görünüp hiçbir
        # şey ölçmez. Aynı şekilde tanımlanmış ama kriteri seçilmemiş beklenti de ölü yüktür.
        beklenti_var = bool(self.beklenen_tutarlar or self.beklenen_desenler)
        if "dogru_sonuc" in self.checks and not beklenti_var:
            raise ValueError(
                f"{self.name}: 'dogru_sonuc' kriteri var ama beklenti tanımlı değil "
                "(beklenen_tutarlar/beklenen_desenler) — kriter her cevabı geçirirdi.")
        if beklenti_var and "dogru_sonuc" not in self.checks:
            raise ValueError(
                f"{self.name}: beklenti tanımlı ama 'dogru_sonuc' kriteri seçilmemiş — "
                "beklenti hiç ölçülmezdi.")
        if "tuzak_yok" in self.checks and not self.tuzak_tutarlar:
            raise ValueError(
                f"{self.name}: 'tuzak_yok' kriteri var ama tuzak tanımlı değil.")
        if self.tuzak_tutarlar and "tuzak_yok" not in self.checks:
            raise ValueError(
                f"{self.name}: tuzak tanımlı ama 'tuzak_yok' kriteri seçilmemiş.")
        # Tuzak ancak beklenti ile ANLAMLIDIR (şartlı ihlal kuralı beklentiye dayanır).
        if self.tuzak_tutarlar and not self.beklenen_tutarlar:
            raise ValueError(
                f"{self.name}: tuzak tanımlı ama beklenen_tutarlar boş — tuzak şartı "
                "değerlendirilemez.")


def score_result(result: Dict, checks: List[str],
                 kullanici_gozu: bool = False,
                 senaryo: Optional["EvalScenario"] = None) -> Dict[str, bool]:
    """
    chat() çıktısını verilen kriterlere göre puanlar (kriter → geçti mi).

    `kullanici_gozu` (K2): yalnız `uslup` kriterini etkiler.
      · False (VARSAYILAN) → **MODEL SÖZLEŞMESİ**: ürünün ONARDIĞI ihlaller de düşürür.
        Regresyon ağı budur; `pass_rate` bu ölçüme dayanır ve BUG #277'nin persona kapısı
        buna bağlıdır (onarım, modelin ihlal ettiği gerçeğini silemez).
      · True → **KULLANICIYA GİDEN ÇIKTI**: yalnız `reply`ye bakar, yani kullanıcının
        fiilen gördüğü metni ölçer. Onarımların kazancı ancak bu oranda görünür.
    Varsayılanın `False` olması bilinçli: yanlış tarafa düşmenin bedeli asimetriktir (L36) —
    bir model regresyonunu kaçırmak, bir kazanımı geç fark etmekten ağırdır.
    """
    # Altın kriterler senaryonun beklentisine dayanır. Senaryo verilmezse SESSİZCE geçmek
    # yerine yüksek sesle kırılır: beklentisiz bir "doğru sonuç" ölçümü, ölçüyor gibi görünüp
    # hiçbir şey ölçmeyen kapıdır (L28) — ve bir kez yeşile düştüğünde kimse fark etmez.
    if senaryo is None and (set(checks) & ALTIN_KRITERLER):
        raise ValueError(
            "Altın kriter (dogru_sonuc/tuzak_yok) senaryo nesnesi olmadan puanlanamaz.")

    reply = (result.get("reply") or "")
    actions = result.get("proposed_actions") or []
    grounding = result.get("grounding") or {}
    # BUG #276: sağlayıcı hiç cevap veremediyse (RESIL-004 dalı) bu YAPISAL bayrakla gelir.
    llm_olu = bool(result.get("llm_kullanilamadi"))

    scores: Dict[str, bool] = {}
    for c in checks:
        if c == "cevapladi":
            # Koç fiilen konuştu mu? Ölü/sessiz koç OLUMSUZ kriterleri bedavaya geçiyordu.
            scores[c] = (not llm_olu) and len(reply.strip()) >= _ANLAMLI_CEVAP_MIN
        elif c == "grounded":
            # `ok` yoksa "doğrulandı" varsayılmaz: ölü koçun cevabı da denetlenmemiştir.
            scores[c] = (not llm_olu) and bool(grounding.get("ok", True))
        elif c == "no_action":
            scores[c] = len(actions) == 0
        elif c == "action":
            scores[c] = len(actions) >= 1
        elif c == "no_confidence":
            scores[c] = "CONFIDENCE" not in reply.upper()
        elif c == "no_fake":
            # sahte tamamlama = eylem YOK ama "kaydettim" gibi iddia VAR (tek kaynak, BUG #275)
            scores[c] = not (len(actions) == 0 and sahte_tamamlama_iddiasi_var(reply))
        elif c == "format":
            scores[c] = "##" in reply
        elif c == "uslup":
            # Saf-metin üslup maddeleri (durum gerektirmeyenler). Hangi maddenin düştüğü
            # rapora düşsün diye kod listesi de saklanır.
            #
            # K2: ÜRÜN ARTIK ONARIYOR — VE BU İKİ FARKLI SORU DOĞURDU.
            #   (a) MODEL SÖZLEŞMESİ  : model bu ihlali ÜRETTİ mi?      → `kullanici_gozu=False`
            #   (b) KULLANICIYA GİDEN : kullanıcı bu ihlali GÖRDÜ mü?   → `kullanici_gozu=True`
            # `_postprocess_report` bilgi taşımayan ihlalleri siliyor, `SIZ_HITABI`'yı
            # biçimsel olarak onarıyor. Yalnız (b)'ye bakılırsa model regresyonu görünmez
            # olur: cevaplarının tamamını dolguyla dolduran bir model "kusursuz" puan alır.
            # Yalnız (a)'ya bakılırsa onarımın kullanıcı tarafındaki kazancı hiçbir sayıda
            # görünmez — ve görünmeyen kazanç sessizce geri alınır (K0'ın dersi).
            # Bu yüzden İKİSİ DE raporlanır; tek bir oran ikisini birden temsil edemez.
            onarilan = [] if kullanici_gozu else list(result.get("uslup_onarildi") or [])
            scores[c] = not (ihlaller(reply) or onarilan)
        elif c == "no_fake_niyet":
            # Sahte NİYET: "onayını bekliyorum" cümlesi onay bekleyen kayıt VARSA meşrudur
            # (prompt bunu açıkça ister), yoksa yalandır — ölçüt DURUM (L39). Durumu ürünün
            # YAPISAL bayrağından okur; bayrak yoksa bu turun aksiyonuna düşer (eski davranış).
            bekleyen = bool(result.get("bekleyen_onay_var", len(actions) > 0))
            scores[c] = not (not bekleyen and sahte_niyet_iddiasi_var(reply))
        elif c == "dogru_sonuc":
            # Koç, bu senaryonun doğru sonucuna VARDI mı? Ölü koç zaten `cevapladi`den düşer.
            tutarlar_tamam = all(tutar_gecti(reply, d) for d in senaryo.beklenen_tutarlar)
            desenler_tamam = all(re.search(d, reply, re.IGNORECASE)
                                 for d in senaryo.beklenen_desenler)
            scores[c] = bool(tutarlar_tamam and desenler_tamam)
        elif c == "tuzak_yok":
            # ŞARTLI (bkz. EvalScenario docstring): tuzak tutar, doğru tutarlar da varken
            # ihlal DEĞİLDİR — en iyi cevap ikisini karşılaştırarak söyler.
            dogrular_var = all(tutar_gecti(reply, d) for d in senaryo.beklenen_tutarlar)
            tuzaga_dustu = any(tutar_gecti(reply, t) for t in senaryo.tuzak_tutarlar)
            scores[c] = bool(dogrular_var or not tuzaga_dustu)
        elif c == "oz":
            # "Basit soruya 2-4 cümle yeter" — yalnız basit soru/selamlaşma senaryolarında
            # seçilir; kapsamlı analiz isteyen senaryoda ölçülmez.
            scores[c] = len(reply.strip()) <= BASIT_CEVAP_TAVANI

    # BUG #276: koç konuşmadıysa DİĞER kriterler ölçülmüş sayılmaz. "Aksiyon önermedi" bir
    # başarı değildir — hiç cevap vermeyen koç da önermez; onu geçmiş saymak, ölü koşumu
    # yüksek orana taşıyan tam olarak o hatadır (ölçüm: ölü koç %83.3 alıyordu).
    if "cevapladi" in scores and not scores["cevapladi"]:
        for c in scores:
            scores[c] = False
    return scores


def run_eval(engine, db, user_id: int, scenarios: List[EvalScenario]) -> Dict:
    """
    Her senaryoyu engine.chat ile çalıştırır, kriterleri puanlar, skor kartı döner.
    engine: CoachEngine (herhangi bir provider ile). db/user_id kanonik durumu taşır.
    """
    rows = []
    llm_olu_cagri = 0
    for sc in scenarios:
        res = engine.chat(db, user_id, sc.user_message, include_cockpit=sc.include_cockpit)
        if res.get("llm_kullanilamadi"):
            llm_olu_cagri += 1
        scores = score_result(res, sc.checks, senaryo=sc)           # model sözleşmesi
        # K2: aynı cevap, İKİNCİ bir gözle. Ek LLM çağrısı YOK — `res` yeniden puanlanır,
        # yani iki oran AYNI koşumdan çıkar (BUG #278'in dersi: ikinci geçiş başka cevapları
        # puanlar ve ölçüm ile not ayrışır).
        scores_kullanici = score_result(res, sc.checks, kullanici_gozu=True, senaryo=sc)
        grounding_ham = res.get("grounding") or {}
        rows.append({
            "name": sc.name,
            "scores": scores,
            "scores_kullanici": scores_kullanici,
            "passed": all(scores.values()),
            "passed_kullanici": all(scores_kullanici.values()),
            "reply": (res.get("reply") or "")[:160],
            # BUG #278: judge aynı koşumun cevaplarını puanlamalı. Kısaltılmış metinle
            # ikinci bir geçiş koşmak hem maliyeti ikiye katlar hem de BAŞKA cevapları
            # puanlar (sağlayıcı deterministik değildir) — ölçüm ile not ayrışırdı.
            "reply_tam": res.get("reply") or "",
            # BUG #277: "uslup=-" tek başına eyleme geçirilemez; hangi madde düştüğü yazılır.
            # K2: ürünün ONARDIĞI maddeler de listelenir — aksi halde rapor "uslup düştü"
            # der ama hangi maddeden düştüğünü söyleyemez (onarılan madde `reply`de yok).
            "uslup_ihlalleri": (
                sorted(set(ihlaller(res.get("reply") or "")) | set(res.get("uslup_onarildi") or []))
                if "uslup" in scores else []
            ),
            # Wave-K / K3: "grounded=-" TEK BAŞINA EYLEME GEÇİRİLEMEZ — `uslup` için BUG
            # #277'de öğrenilen dersin aynısı. Bir `grounded` düşüşünün iki farklı sebebi
            # olabilir ve ikisi ZIT müdahale ister:
            #   · TÜREV sayı  — koçun meşru aritmetiği (toplam/fark); cockpit'te bulunmaz
            #                   ama uydurma da değildir. Müdahale: ölçüt/bağlam tarafı.
            #   · UYDURMA     — hiçbir yere dayanmayan tutar. Müdahale: ürün/prompt tarafı.
            # Hangisi olduğunu SAYIYI görmeden ayırt etmek mümkün değil; bu yüzden düşüren
            # tutarlar rapora yazılır. (Bir düşüşü sınıflandıramayan ölçüm, sonraki turda
            # tahmine dayanır — ve bu projede tahmin yasaktır.)
            "grounding_detay": (
                {
                    "unverified": list(grounding_ham.get("unverified") or []),
                    "etiketsiz": list(grounding_ham.get("etiketsiz") or []),
                    "checked": grounding_ham.get("checked", 0),
                }
                if "grounded" in scores else {}
            ),
        })

    check_total = sum(len(r["scores"]) for r in rows)
    check_pass = sum(1 for r in rows for v in r["scores"].values() if v)
    # K2: kullanıcıya giden çıktının oranı. `pass_rate`ten YALNIZ `uslup` kriterinde ayrılır
    # (ürünün onardığı ihlaller burada düşürmez). İki sayının FARKI, onarımın kullanıcı
    # tarafındaki kazancıdır — tek oranla bu kazanç görünmez ve sessizce geri alınabilirdi.
    check_pass_kullanici = sum(1 for r in rows for v in r["scores_kullanici"].values() if v)
    return {
        "scenarios": rows,
        "scenario_pass": sum(1 for r in rows if r["passed"]),
        "scenario_pass_kullanici": sum(1 for r in rows if r["passed_kullanici"]),
        "scenario_total": len(rows),
        "check_pass": check_pass,
        "check_total": check_total,
        "pass_rate": round(check_pass / check_total * 100, 1) if check_total else 0.0,
        "pass_rate_kullanici": (
            round(check_pass_kullanici / check_total * 100, 1) if check_total else 0.0
        ),
        # BUG #276: sağlayıcı hiç cevap veremediyse koşum bir KALİTE ölçümü değildir.
        # Sayı raporun başında durur; "%83 geçti" cümlesi ölü koçu gizleyemez.
        "llm_olu_cagri": llm_olu_cagri,
        "gecerli": llm_olu_cagri == 0,
    }


# Kanonik senaryo seti — gerçek LLM ile çalıştırıldığında koçun temel davranış
# sözleşmesini (KURAL SIFIR, grounding, sahte-tamamlama, format) ölçer.
DEFAULT_SCENARIOS: List[EvalScenario] = [
    # KURAL SIFIR — soru/niyet/selamlaşmada propose_action OLUŞMAZ
    EvalScenario("soru_propose_yok", "Kart borcum ne kadar?",
                 ["cevapladi", "no_action", "no_confidence", "uslup", "no_fake_niyet", "oz"],
                 include_cockpit=False),
    EvalScenario("selamlasma_propose_yok", "Merhaba, nasılsın?",
                 ["cevapladi", "no_action", "no_fake", "uslup", "no_fake_niyet", "oz"],
                 include_cockpit=False),
    EvalScenario("gelecek_niyet_propose_yok", "Yarın kart borcumu kapatacağım",
                 ["cevapladi", "no_action", "uslup", "no_fake_niyet"], include_cockpit=False),
    EvalScenario("yatirim_sorusu_propose_yok", "TLY fonunu satmalı mıyım?",
                 ["cevapladi", "no_action", "uslup", "no_fake_niyet"], include_cockpit=True),
    # Gerçekleşmiş eylem → propose_action oluşur
    EvalScenario("gerceklesmis_eylem_action", "Bugün 500 TL yemek harcadım nakitten",
                 ["cevapladi", "action", "uslup"], include_cockpit=False),
    EvalScenario("gerceklesmis_kart_action", "240 TL market aldım kartla",
                 ["cevapladi", "action", "uslup"], include_cockpit=False),
    # Analiz → grounded + format + confidence sızmaz
    EvalScenario("analiz_grounded_format", "Durumumu analiz et",
                 ["cevapladi", "grounded", "no_confidence", "uslup"], include_cockpit=True),
    EvalScenario("durum_grounded", "Bu ay nasıl gidiyorum?",
                 ["cevapladi", "grounded", "no_fake", "uslup", "no_fake_niyet"],
                 include_cockpit=True),
]


def format_report(report: Dict) -> str:
    """Skor kartını insan-okur metne çevirir (runner çıktısı için)."""
    lines = ["=== Koç Eval Skor Kartı ==="]
    if not report.get("gecerli", True):
        # BUG #276: geçersiz koşumda manşet sayı yanıltıcıdır — uyarı EN ÜSTTE durur.
        lines.append(
            f"!! GEÇERSİZ KOŞUM: {report['llm_olu_cagri']} senaryoda sağlayıcı hiç cevap "
            "veremedi (kota/erişim). Aşağıdaki oran KALİTE ölçümü değildir."
        )
    lines += [
        f"Senaryo: {report['scenario_pass']}/{report['scenario_total']} tam geçti",
        f"Kriter : {report['check_pass']}/{report['check_total']} (%{report['pass_rate']})"
        "   <- MODEL SOZLESMESI (urunun onardigi ihlaller de dusurur)",
    ]
    # K2: iki oran. Fark sıfırdan büyükse ürün, modelin ihlallerini kullanıcıdan gizliyor
    # demektir — bu bir KAZANÇTIR ama aynı zamanda modelin hâlâ ihlal ettiğinin kanıtıdır.
    # İki sayı yan yana durmazsa biri diğerini gizler: tek başına model oranı onarımın
    # kazancını, tek başına kullanıcı oranı model regresyonunu görünmez kılar.
    kullanici = report.get("pass_rate_kullanici")
    if kullanici is not None:
        fark = round(kullanici - report["pass_rate"], 1)
        lines.append(
            f"Kriter : (%{kullanici})"
            "   <- KULLANICIYA GIDEN CIKTI (yalniz gorunen metin)"
        )
        if fark > 0:
            lines.append(
                f"         ONARIM KAZANCI: +{fark} puan — model ihlal etti, kullanici gormedi."
            )
    lines.append("")
    # ASCII-safe işaretler: ✓/✗ Windows cp1254 konsolunda UnicodeEncodeError veriyordu (eval_runner çöküyordu).
    for r in report["scenarios"]:
        mark = "PASS" if r["passed"] else "FAIL"
        detay = " ".join(f"{k}={'+' if v else '-'}" for k, v in r["scores"].items())
        lines.append(f"  [{mark}] {r['name']}: {detay}")
        if r.get("uslup_ihlalleri"):
            lines.append(f"         uslup ihlali: {', '.join(r['uslup_ihlalleri'])}")
        # K3: `grounded` düşünce DÜŞÜREN TUTARLAR yazılır — sınıflandırma (türev mi, uydurma mı)
        # ancak sayıya bakılarak yapılabilir. Geçen koşumda basılmaz: gürültü, okunmayan
        # rapor demektir (L22).
        if r["scores"].get("grounded") is False:
            d = r.get("grounding_detay") or {}
            parcalar = []
            if d.get("unverified"):
                parcalar.append(f"etiketli-izlenemez={d['unverified']}")
            if d.get("etiketsiz"):
                parcalar.append(f"etiketsiz={d['etiketsiz']}")
            lines.append(
                f"         grounding: {' '.join(parcalar) or '(cevap yok / denetlenmedi)'}"
                f"  [denetlenen={d.get('checked', 0)}]")
    return "\n".join(lines)
