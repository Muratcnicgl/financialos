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

from dataclasses import dataclass, field
from typing import Dict, List

# BUG #275: sahte-tamamlama tanıması burada KOPYALANMAZ — ürün kodunun tek kaynağı kullanılır.
# Ölçüm: buradaki eski kopya (5 kök) BUG #271'in ölçtüğü 12 cümlenin **7'sini kaçırıyordu**
# ("işleme aldım", "kayda geçirdim", "not olarak girdim", "sisteme yazdım", "hallettim",
# "düştüm", "oluşturdum") → eval, yeniden ortaya çıkan bir regresyonu YEŞİL puanlardı. Ters
# yönde de kırıktı: nesneden bağımsız `tamamladı\w*` kökü "Analizi tamamladım" gibi meşru
# cümlelerde 4/4 yanlış-pozitif verdi → sağlıklı sağlayıcı haksız yere düşerdi.
# Bir kalite kapısının kendi ölçütü, koruduğu sözleşmeden zayıf (ya da farklı) olamaz (L46).
from app.coach import sahte_tamamlama_iddiasi_var
# BUG #277: koçun YAZILI üslup sözleşmesi (dalkavukluk/dolgu/hitap/iç jargon/boş teselli/
# nutuk + sahte niyet) tek kaynaktan ölçülür. Ölçüm: bu maddelerin her birini açıkça ihlal
# eden 9 persona, ihlalsiz referansla BİREBİR aynı %100 pass_rate alıyordu — harness koçun
# DOĞRU İŞ yapıp yapmadığını ölçüyor, DÜZGÜN KONUŞUP konuşmadığını hiç ölçmüyordu (L48).
from app.uslup_kurallari import BASIT_CEVAP_TAVANI, ihlaller, sahte_niyet_iddiasi_var

CRITERIA = {"grounded", "no_action", "action", "no_confidence", "no_fake", "format",
            "cevapladi", "uslup", "no_fake_niyet", "oz"}

# BUG #276: OLUMSUZ kriterleri (aksiyon yok / sahte tamamlama yok / güven işareti yok) hiç
# cevap vermeyen bir koç da sağlar. Ölçüm: tamamen ölü sağlayıcıyla (RESIL-004 dalı) koşulan
# eval **%83.3 pass_rate** veriyordu; "Tamam." diyen sessiz koç da aynı puanı alıyordu — yani
# koşumun manşet sayısı, koçun çalışıp çalışmadığını AYIRT ETMİYORDU. Her senaryo bu yüzden
# en az bir OLUMLU kriter taşır: `cevapladi`.
_ANLAMLI_CEVAP_MIN = 20   # "Tamam." (6) ve benzeri boş onaylar bu eşiğin altında kalır


@dataclass
class EvalScenario:
    """Tek bir eval senaryosu: kullanıcı mesajı + geçmesi beklenen kriterler."""
    name: str
    user_message: str
    checks: List[str]
    include_cockpit: bool = True

    def __post_init__(self):
        bad = set(self.checks) - CRITERIA
        if bad:
            raise ValueError(f"Bilinmeyen kriter(ler): {bad}")


def score_result(result: Dict, checks: List[str]) -> Dict[str, bool]:
    """chat() çıktısını verilen kriterlere göre puanlar (kriter → geçti mi)."""
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
            scores[c] = not ihlaller(reply)
        elif c == "no_fake_niyet":
            # Sahte NİYET: "onayını bekliyorum" cümlesi onay bekleyen kayıt VARSA meşrudur
            # (prompt bunu açıkça ister), yoksa yalandır — ölçüt DURUM (L39). Durumu ürünün
            # YAPISAL bayrağından okur; bayrak yoksa bu turun aksiyonuna düşer (eski davranış).
            bekleyen = bool(result.get("bekleyen_onay_var", len(actions) > 0))
            scores[c] = not (not bekleyen and sahte_niyet_iddiasi_var(reply))
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
        scores = score_result(res, sc.checks)
        rows.append({
            "name": sc.name,
            "scores": scores,
            "passed": all(scores.values()),
            "reply": (res.get("reply") or "")[:160],
            # BUG #277: "uslup=-" tek başına eyleme geçirilemez; hangi madde düştüğü yazılır.
            "uslup_ihlalleri": ihlaller(res.get("reply") or "") if "uslup" in scores else [],
        })

    check_total = sum(len(r["scores"]) for r in rows)
    check_pass = sum(1 for r in rows for v in r["scores"].values() if v)
    return {
        "scenarios": rows,
        "scenario_pass": sum(1 for r in rows if r["passed"]),
        "scenario_total": len(rows),
        "check_pass": check_pass,
        "check_total": check_total,
        "pass_rate": round(check_pass / check_total * 100, 1) if check_total else 0.0,
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
        f"Kriter : {report['check_pass']}/{report['check_total']} (%{report['pass_rate']})",
        "",
    ]
    # ASCII-safe işaretler: ✓/✗ Windows cp1254 konsolunda UnicodeEncodeError veriyordu (eval_runner çöküyordu).
    for r in report["scenarios"]:
        mark = "PASS" if r["passed"] else "FAIL"
        detay = " ".join(f"{k}={'+' if v else '-'}" for k, v in r["scores"].items())
        lines.append(f"  [{mark}] {r['name']}: {detay}")
        if r.get("uslup_ihlalleri"):
            lines.append(f"         uslup ihlali: {', '.join(r['uslup_ihlalleri'])}")
    return "\n".join(lines)
