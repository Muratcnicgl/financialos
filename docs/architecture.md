# Mimari

## Temel İlke: Rules Engine Karar Verir, LLM Açıklar

Sistemin merkezindeki ayrım — bunu kıran her değişiklik bug üretir:

- **`app/rules_engine.py`** — saf Python, DB'yi okur ama yazmaz. Tüm matematiksel kararlar (bütçe, devreden bakiye/zikzak, kart stratejisi, yatırım K/Z, uyarılar) burada. `generate_cockpit(user_id, today, db)` tüm sayısal anlık görüntüyü tek dict olarak döner.
- **`app/coach.py`** — LLM sadece bu cockpit dict'ini bağlam olarak alır, hesap yapmaz. Bir aksiyon önereceğinde tek bir tool çağırır: `propose_action`.
- **`app/action_executor.py`** — `propose_action` PendingAction tablosuna yazar (status=pending). Kullanıcı onaylayınca `execute_pending_action` payload'ı parse edip DB'yi günceller, status='executed' yapar. **Master Checkpoint enforcement (örn. emanet hesabı satılamaz) burada uygulanır** — LLM'in prompt'ına güvenilmez, kod seviyesinde bloklanır.

LLM hiçbir zaman doğrudan DB'yi yazmaz; akış her zaman propose → kullanıcı onayı → execute.

## LLM Provider Mimarisi (`app/coach.py`)

`LLMProvider` soyut sınıfı + **sekiz** implementation + `FallbackProvider` (zincir).
Tek doğruluk kaynağı `app/coach.py`'deki `_SAGLAYICI_KURUCULARI` sözlüğüdür:
`gemini` · `anthropic` · `groq` · `cerebras` · `openrouter` · `together` · `deepinfra`
— artı koşullu olarak eklenen `ollama` (`OLLAMA_ENABLED=1`, yerel/egemen yol).
Zincir SIRASI ayrı tutulur (`_ZINCIR_SIRASI`), çünkü sıra bir **politika** kararıdır,
ad kümesi değil (M13/ADR-034).
*(5 Eyl 2026 düzeltmesi — DOCS-005: bu satır "üç implementation" diyordu; kod sekiz
taşıyor. Liste artık `tests/test_saglayici_belgesi_kapisi.py` ile koda bağlı, yani bir
sağlayıcı eklenip belge unutulursa süit kırmızı verir.)* `LLM_PROVIDER=fallback` ile birincil 429/quota dolarsa veya boş/bozuk cevap dönerse otomatik bir sonrakine geçilir. Gemini'nin `MALFORMED_FUNCTION_CALL` gibi finish_reason'ları `ProviderEmptyResponseError` olarak raise edilir, FallbackProvider bunları quota gibi davranıp atlar.

`V3_GOD_MODE_PROMPT` system prompt'u koç davranışının tek kaynağıdır — özellikle:
- **KURAL SIFIR**: `propose_action` SADECE kullanıcı gerçekleşmiş bir eylemi bildirdiğinde çağrılır. Soru/analiz/selamlaşmada asla.
- **RAPOR FORMATI**: kullanıcı analiz isterse 5 bölümlü şablon. Boş bölümler (örn. emanet 0) HİÇ yazılmaz — başlık bile çıkmaz.

Llama 3.3 (Groq) düşük temperature'da (0.2) bile yumuşak ifadeleri görmezden geliyor; bu yüzden prompt'ta yasak cümle örnekleri + yanlış/doğru çıktı karşılaştırmaları açıkça veriliyor. Prompt değişikliklerinde bu sertlik düzeyini koru.

## HTTP Katmanı

`app/main.py` küçük tutulur — sadece app yaratımı, CORS, router kayıt, startup'ta `Base.metadata.create_all`. Endpoint'ler `app/routers/` altında konuya göre bölünür (cockpit, coach, accounts, transactions, incomes, debts, checkpoints, actions, fund_price, user). Her router `prefix="/api/<konu>"` kullanır.

`app/dependencies.py` — `get_db` (per-request session) + `get_current_user`. Tek-kullanıcı MVP'sinde `get_current_user` "ilk kullanıcı"yı döner; multi-user'a geçişte buraya JWT bağlanır, başka yere değil.

## Datetime / Timezone

DB'deki tüm `Column(DateTime, default=datetime.utcnow)` alanları **timezone-naive UTC**. Frontend'e tarih yansıtan endpoint'lerde (örn. `coach/history`) helper'da serialize öncesi `tzinfo=timezone.utc` ile aware'e çevrilmeli — aksi halde Pydantic suffix'siz ISO string yayar, JS bunu local time olarak yorumlar ve Türkiye saatinde 3 saat geri görünür. Pattern için bkz. `_memory_to_history_item` (`app/routers/coach.py`).

## Frontend Yapısı

`frontend/src/` — `App.jsx` (tab bar + tema), `panels/` (Cockpit, Coach, Accounts, Transactions, IncomeDebt, RedLines), `components/` (paylaşılan UI), `api.js` (tüm backend çağrılarını sarmalar — `ApiError` fırlatır, panel try/catch ile yakalar). Vite proxy `/api/*`'yi `localhost:8000`'e yollar; CORS dev'de bypass edilir, prod'da `app/main.py`'deki listede.

## Kanonik Test Verisi (`scripts/setup_data.py`)

"Murat'ın 1 Mayıs 2026 finansal manzarasını" yükler (1 nakit + 1 kart + 5 kredi + 1 yatırım hesabı, 13 alacak, 7 master checkpoint). Test scriptleri bu durumla çalışır. **Drop_all + create_all** yapar — manuel veri kaybedilir. DB schema'sını değiştirmeden gerçekçi bir senaryoyu test etmek için bunu çalıştır.

## Bug Fix Konvansiyonu

Düzeltmeler dosya başındaki `GUNCELLEMELER` docstring bloğuna `BUG #NNN fix:` notu ile eklenir, kodda da inline yorumla işaretlenir. Numaralar artıyor (BUG #001, #006, #010-#020 mevcut). Yeni bir fix eklerken hem ilgili dosyanın docstring'ine hem de değişen bloğun yanına satır düş.
