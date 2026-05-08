# FinancialOS — Mimari Vizyon Geliştirme Raporu

**Tarih:** 8 Mayıs 2026
**Kapsam:** AI mimarisi, backend, frontend, gözlemlenebilirlik, geliştirme süreci
**Yaklaşım:** En iyi tasarlanmış uygulamalardan kalite çıkarımı, kopyalama değil **entegrasyon**

---

## Yönetici Özeti

FinancialOS şu an **Wave-2 mimari üçgenini** tamamlamış durumda: deterministik snapshot (Rules Engine), schema-garantili eylem (action_executor), arka plan reflection (CoachInsight), rolling pattern detection. Bu temel sağlam.

Bu rapor, sistemi DeepSeek/Claude/GPT seviyesindeki ürünlerle aynı mimari olgunluğa taşımak için **6 eksende** somut yönelimler sunuyor:

1. **AI orchestration** — LangGraph state machine ile sub-agent routing
2. **Prompt mühendisliği** — DSPy ile programatik optimizasyon
3. **Backend mimarisi** — async, observability, scaling
4. **Frontend mimarisi** — Feature-Sliced Design ile organizasyon
5. **State yönetimi** — Zustand + TanStack Query ayrımı
6. **Geliştirme süreci** — observability-first, ölçülebilir kalite

Her bölüm "Ne", "Neden", "Senin için somut adım", "Trade-off" şeklinde işliyor.

---

## 1. AI Mimarisi — Tek-LLM'den Sub-Agent Routing'e

### Mevcut Durum

Şu an Coach paneli **tek bir LLM çağrısına** dayalı:
- FallbackProvider → Groq/Cerebras/Gemini/OpenRouter sırası
- V3 GOD MODE prompt → tek mega prompt, her tür soruyu o kapsıyor
- Tool: `propose_action` + `save_insight`

Bu çalışıyor ama bir tavanı var. "Kahve aldım" ile "TLY satayım mı" aynı modele aynı promptla gidiyor — kahve için fazla bağlam, analiz için bazen yetersiz uzmanlık.

### Hedef Mimari — LangGraph State Machine ile Sub-Agent Routing

DeepSeek, Claude, GPT'nin yaptığı şey: **tek bir uzman değil, takım**. Bir intent classifier önce mesajı sınıflandırıyor, sonra ilgili uzman ajan çağrılıyor.

```
[Kullanıcı mesajı]
        ↓
[Intent Classifier] (küçük model, ucuz)
        ↓
        ├─→ Bildirim ajanı     (kahve, market — propose_action only)
        ├─→ Soru cevap ajanı   (durum, balance — read-only)
        ├─→ Analiz ajanı       (TLY, kredi, stratejik — uzun rapor + tools)
        └─→ Hatırlatma ajanı   (proaktif vade bildirimi — şablon-bazlı)
```

**LangGraph neden iyi:**
- Graph-based, state machine — her node bir işlev, her edge bir karar
- **Checkpointing** — herhangi bir noktada durup devam edebilirsin (ödül: asistan arayuzu memory desync sorununun kalıcı çözümü)
- **Conditional edges** — "eğer is_question True ise X node'a, değilse Y node'a"
- Production-grade, finance gibi audit-trail gereken alanlarda gold standard

**Senin için somut yönelim:**

Wave-3 başlangıcında bir POC ile başla:
1. `intent_classifier` node — Groq Llama 8B ile (hızlı + ucuz), 4-5 kategoriye ayır
2. `notification_agent` — sadece propose_action, V3 prompt'un %30'u (sadece eylem kuralları)
3. `analysis_agent` — V3 prompt'un tamamı + RAPOR FORMATI
4. Mevcut Coach panel = LangGraph orchestrator'ı çağırıyor

**Faydalar:**
- Kahve mesajları **5x daha ucuz** olur (8B model + kısa prompt)
- Stratejik analizler **daha derin** olur (uzman prompt + uzun cevap)
- Her node ayrı ayrı test edilir, optimize edilir, gözlenir
- BUG #050 gibi format sorunları sadece ilgili node'da debug edilir

**Trade-off:**
- Ek karmaşıklık — bir LangGraph'ı debug etmek tek-prompt'tan zor
- İlk 2-3 hafta yatırımı
- LangChain'i de import etmek zorundasın (paket boyutu)

**Karar zamanı:** Wave-2 bittikten sonra. Şu an sistem stabil, vakti gelene kadar bekle.

### Alternatif — Anthropic Claude Agent SDK

LangGraph yerine Anthropic'in kendi Claude Agent SDK'sını kullanmak da bir seçenek:
- Constitutional AI prensipleriyle güvenlik built-in
- Sub-agent handoffs yerleşik
- Tool-use chain default

**Trade-off:** Sadece Claude modellerine kilitlenirsin (free tier provider çeşitliliğin gider). Senin için **LangGraph daha esnek** — Groq + Cerebras + Gemini'yi hâlâ kullanırsın.

---

## 2. Prompt Mühendisliği — Manuel'den DSPy'a

### Mevcut Durum

V3 GOD MODE prompt manuel olarak yazıldı. Her bug fix bir kural ekliyor (Kural 11, 12, 13). Şu an 13+ kural, her biri Llama'nın bir davranışsal sorununa yanıt.

Bu yaklaşımın iki sorunu var:
1. **Kararlı değil** — Llama prompt'a uymadığında manuel iter (BUG #050 paterni)
2. **Ölçülemiyor** — Hangi kuralın etkisi ne? Kural 11'i kaldırırsam ne kötüleşir?

### Hedef Mimari — DSPy Programatik Optimizasyon

DSPy (Stanford Hazy Research) prompt'u **kod gibi** yazmana izin veriyor:
- `Signature` — input/output şeması (prompt + response)
- `Module` — modüler bileşen (Predict, ChainOfThought, ReAct)
- `Optimizer` — örneklere bakarak prompt'u otomatik iyileştiriyor
- `Metric` — başarı tanımı (örn: "format doğru mu", "kategori doğru mu")

```python
# DSPy ile yazılmış FinancialOS Coach
class CoachSignature(dspy.Signature):
    """Murat'ın finansal koçu olarak yanıt ver."""
    cockpit_snapshot: str = dspy.InputField()
    user_message: str = dspy.InputField()
    response: str = dspy.OutputField(desc="Türkçe analiz, ## ile başlıklar")
    proposed_actions: list = dspy.OutputField(desc="JSON list of actions")

coach = dspy.ChainOfThought(CoachSignature)

# 50-100 örnek topla (gerçek konuşmalardan)
training_data = [
    dspy.Example(cockpit_snapshot=..., user_message="200 TL kahve",
                 response="...", proposed_actions=[...]),
    # ...
]

# Otomatik optimize et
optimizer = dspy.MIPROv2(metric=format_quality_metric)
optimized_coach = optimizer.compile(coach, trainset=training_data)
```

**Faydalar:**
- Yeni Llama versiyonu çıkınca → optimizer'ı tekrar çalıştır → otomatik adapte
- Her metric ayrı ölçülebilir (format kalitesi, sayı doğruluğu, kategori isabeti)
- Few-shot examples otomatik seçiliyor (manuel "şu örneği ekle" yok)
- Provider değiştirince (Groq → Cerebras) prompt otomatik adapte

**Senin için somut yönelim:**

Wave-3 fazında, sub-agent routing yaptıktan sonra her ajanın prompt'unu DSPy ile yaz:
1. Önce `notification_agent` — basit, dar görev, optimize edilebilir
2. Sonra `analysis_agent` — complex output, ChainOfThought + birden çok metric
3. Mevcut V3 prompt'tan çıkarılan kuralları DSPy `assertion` olarak ekle

**Trade-off:**
- Eğitim verisi toplaman lazım (50-100 örnek minimum)
- Optimizer çalıştırmak para tüketiyor (LLM çağrıları). Geliştirme zamanında, production'da değil.

**Eşdeğer alternatifler:** Guidance, Outlines, Instructor (sadece structured output için). DSPy en kapsamlısı.

---

## 3. Backend Mimarisi — FastAPI Olgunluğu

### Mevcut Durum

FastAPI + SQLite + SQLAlchemy. Tek dosya `coach.py` 1600+ satır. Provider chain manuel yazıldı. Logging temel `logger.info` seviyesinde.

Çalışıyor ama production-grade bir mimaride şu eksiklikler var:

1. **Async tutarsız** — bazı endpoint sync, bazı async, SQLAlchemy 2.x async pattern'i tam uygulanmamış
2. **Observability yok** — hangi endpoint yavaş, hangi LLM çağrısı pahalı, hangi user en çok kullanıyor — bilmiyorsun
3. **Rate limiting yok** — bug avı sırasında 30 mesaj atınca tüm provider'lar dolu
4. **Caching yok** — aynı cockpit snapshot 10 saniye içinde 5 kez üretiliyorsa 4'ü gereksiz
5. **Background tasks ad-hoc** — reflection hook BackgroundTasks ile yapıldı (iyi) ama Celery yok

### Hedef Mimari — Production-Ready FastAPI

**Eksen 1 — Async tutarlılığı:**

```python
# Async engine + session
async_engine = create_async_engine(DATABASE_URL,
                                   pool_size=10, max_overflow=20,
                                   pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(async_engine,
                                       class_=AsyncSession,
                                       expire_on_commit=False)

@app.post("/api/coach")
async def coach_endpoint(message: str,
                        db: AsyncSession = Depends(get_async_db)):
    # Async query
    cockpit = await generate_cockpit_async(db)
    # Async LLM call
    response = await llm_provider.chat_async(message, cockpit)
    return response
```

**Eksen 2 — OpenTelemetry observability:**

Her LLM çağrısının trace'i var:
```
[Request 12345]
├─ generate_cockpit (12ms)
├─ llm_provider.chat (1240ms)
│   ├─ groq attempt (FAILED, 800ms, rate_limit)
│   ├─ cerebras attempt (OK, 440ms, 1245 tokens)
│   └─ tools_used: [propose_action]
├─ action_executor.normalize (3ms)
└─ response (total: 1255ms)
```

**Bu sana ne sağlar:**
- "Niye bu mesaj 4 saniye sürdü?" — trace anında gösteriyor
- "Hangi provider en çok başarısız?" — dashboard
- "Token maliyetimiz aylık ne kadar?" — Grafana
- BUG #028'deki "tüm chain dolu" durumu — trace'te 4 attempt görünür

**Senin için somut yönelim:**

Wave-3 öncesi 2-3 günlük yatırım:
1. `prometheus_client` + `opentelemetry-api` ekle
2. Request middleware → her endpoint için latency + status histogram
3. LLM provider'larda her attempt için span oluştur
4. Grafana dashboard kur (free tier yeterli)

**Eksen 3 — Rate limiting + caching:**

```python
from slowapi import Limiter
limiter = Limiter(key_func=lambda: "single_user")

@app.post("/api/coach")
@limiter.limit("10/minute")  # Bug avı koruma
async def coach_endpoint(...):
    ...

# Redis cache (in-memory dict for single user works)
@cached(ttl=10)  # 10 sn aynı cockpit
async def generate_cockpit_cached(db):
    return await generate_cockpit_async(db)
```

**Eksen 4 — Coach.py'yi parçala:**

1600+ satırlık tek dosya bakım kabusu. Önerilen:

```
app/
├── coach/
│   ├── __init__.py
│   ├── providers/         # Groq, Cerebras, Gemini, OpenRouter
│   │   ├── base.py
│   │   ├── groq.py
│   │   ├── cerebras.py
│   │   └── fallback.py
│   ├── prompts/           # V3_GOD_MODE, future agent prompts
│   ├── tools/             # propose_action, save_insight
│   ├── memory/            # _load_history, _save_message
│   ├── routing.py         # is_question, intent classifier
│   └── orchestrator.py    # main chat() function
```

Wave-3 sub-agent geçişiyle birlikte yapılır. Şimdi büyük refactor risk.

### Eksen 5 — Database scaling hazırlığı

SQLite → mobile için ideal, multi-user web için sınırlı. Mobile/PWA hedefini koruyup web sunucuda PostgreSQL'e geçiş yolu:

1. **Şu an:** SQLite (local-only, single-user)
2. **PWA aşaması:** SQLite (hâlâ local + cloud backup)
3. **RN+Expo aşaması:** SQLite cihazda + PostgreSQL backend (sync için)
4. **Multi-user gelecek:** Tam PostgreSQL

SQLAlchemy soyutlaması zaten geçiş kolaylaştırıyor — schema değişmiyor, connection string değişiyor.

---

## 4. Frontend Mimarisi — Feature-Sliced Design

### Mevcut Durum

```
frontend/src/
├── panels/         # Cockpit, Coach, Accounts, Transactions, IncomeDebt, RedLines
├── components/     # Karışık (Toast, Markdown, vs)
├── api.js          # Tek dosya, tüm API çağrıları
└── App.jsx         # Tab logic + sayfa switching
```

Bu **type-based** organizasyon (panels, components, api). 6 panel için yeterli ama:
- Bir panele yeni özellik eklemek için 4 dosyayı düzenlemek lazım
- `api.js` 500+ satır olunca bakım zor
- Test yazma daha fazla zorlaşıyor

### Hedef Mimari — Feature-Sliced Design (FSD)

2026'nın React community standardı. Domain-driven, feature-bazlı:

```
src/
├── app/                    # Initialization, providers, routing
├── pages/                  # Cockpit, Coach, Accounts (sayfalar)
├── widgets/                # Cockpit içindeki büyük bloklar
│   ├── pending-actions/
│   ├── upcoming-reminders/
│   └── investment-pl/
├── features/               # Kullanıcı eylemleri
│   ├── add-transaction/
│   │   ├── ui/
│   │   ├── model/          # Zustand store, selectors
│   │   ├── api/
│   │   └── index.ts        # Public API
│   ├── approve-action/
│   ├── edit-recurring/
│   └── coach-message/
├── entities/               # Business kavramları
│   ├── account/
│   ├── transaction/
│   ├── pending-action/
│   └── coach-insight/
└── shared/                 # UI primitives, utils
    ├── ui/                 # Button, Card, Modal
    ├── lib/                # formatTL, turkish_date, etc
    └── api/                # base axios client
```

**Kural:** Yukarıdaki katman aşağıdakini import edebilir, tersi değil. `features/add-transaction` → `entities/account` ve `shared/ui` import edebilir; `entities/account` → `features/add-transaction`'ı **göremez**.

**Senin için somut yönelim:**

D8 (klavye kısayolu) ve Hafta 4 Tema B Görselleştirme'den önce **bir migration sprint** yap:
1. Önce `shared/ui` klasörü oluştur, mevcut ortak UI'ı taşı (Button, Modal, Card)
2. Sonra `entities` klasörü, her domain için (Account, Transaction, etc.)
3. Sonra `features` — her panel kendi feature'larına ayrılır
4. Pages incelir — sadece widget'ları compose eder

**Trade-off:**
- 2-3 haftalık migration. Ama **bir kere yapıyorsun**, ondan sonra her yeni feature net yere düşüyor
- BUG fix sırasında "hangi dosyaya bakayım" kafa karışıklığı biter
- Test yazmak kolaylaşır (her feature izole)

**Yumuşak başlangıç:** Hemen tamamen geçme. Sadece **yeni feature'lar** için FSD kullan. Eski kod yavaş yavaş migrate edilir.

---

## 5. State Yönetimi — Doğru Aracı Doğru Yere

### Mevcut Durum

Mevcut frontend'de useState + props drilling kombinasyonu var. Cockpit'ten Coach'a veri geçişi App.jsx üzerinden refresh trigger'la yapılıyor. Bu küçük ölçekte çalışıyor.

### Sorun

Şu an 3 tür state karışık:
1. **UI state** — modal açık mı, hangi tab seçili
2. **Server state** — cockpit verisi, transaction listesi (backend'den geliyor)
3. **Client business state** — pending action seçimi, undo geçmişi

Bunları aynı useState'le yönetmek karmaşık olur.

### Hedef Mimari — İki-Araç Bölümü

**Server state için: TanStack Query (React Query)**

```typescript
const { data: cockpit, isLoading } = useQuery({
  queryKey: ['cockpit'],
  queryFn: () => api.cockpit.fetch(),
  staleTime: 10 * 1000,  // 10 sn taze say
})

// Mutation (transaction ekleme)
const addTransaction = useMutation({
  mutationFn: api.transactions.create,
  onSuccess: () => queryClient.invalidateQueries(['cockpit']),
})
```

Faydalar:
- **Otomatik caching** — Cockpit verisi 10 saniye taze, network çağrısı yok
- **Optimistic updates** — kart "Onayla"ya basınca anında UI güncellenir, backend cevabı gelmeden
- **Automatic refetch on window focus** — sekmeyi değiştirip dönünce taze veri
- **Error handling** standart, retry built-in

**UI/Client state için: Zustand**

```typescript
const useUIStore = create((set) => ({
  selectedTab: 'cockpit',
  modalOpen: false,
  setTab: (tab) => set({ selectedTab: tab }),
  openModal: () => set({ modalOpen: true }),
}))

// Component'te
const tab = useUIStore(state => state.selectedTab)
```

Faydalar:
- Minimal API, Provider gerektirmiyor
- Bundle boyutu Redux'tan 10x küçük
- TypeScript-friendly
- Selector pattern ile fine-grained re-render

**Senin için somut yönelim:**

D6/D7/D8'den sonra, FSD migration sprint'iyle birlikte:
1. TanStack Query ekle, `api.js`'deki çağrıları useQuery wrapper'a sar
2. Zustand ekle, App.jsx'teki `activeTab`, modal state'leri taşı
3. Mevcut prop drilling'i yavaş yavaş sök

**Trade-off:** İki yeni paket. Ama her ikisi de minimal (~10kb), getirileri büyük.

**Önemli kural:** Server state'i Zustand'da tutma. İki kaynak doğru oluyor, stale data bug'ları kaçınılmaz. TanStack Query bunun için var.

---

## 6. Geliştirme Süreci — Observability-First

### Mevcut Durum

Bug çıkıyor → asistan araci teşhis ediyor → fix → manuel test. Bu çalışıyor ama **proaktif değil reaktif**. BUG meydana çıkmadan tahmin etmek zor.

### Hedef Mimari — Ölçülebilir Kalite

**Eksen 1 — LLM Quality Metrics**

Her LLM cevabını otomatik değerlendir:
- Format doğruluğu (## başlık var mı, sayılar Türkçe formatta mı)
- Tool call doğruluğu (proposed_action varsa schema valid mi)
- Hallüsinasyon var mı (claimed sayılar cockpit ile match ediyor mu)
- Kategori isabeti (kahve → market mı, eğlence mi)

```python
# Bir "judge LLM" kullanarak otomatik scoring
@background_task
async def evaluate_response(response: str, cockpit: dict, user_msg: str):
    score = await judge_llm.evaluate(response, criteria=[
        "format_compliance",
        "number_accuracy",
        "category_correctness",
    ])
    metrics.gauge("response_quality", score, tags={"provider": ...})
```

Bu gece, "hangi provider en kaliteli cevap veriyor" sorusunun cevabını alırsın. Şu an kararsızsın.

**Eksen 2 — Continuous evaluation**

DSPy + bir test set ile her commit'te otomatik eval:
- 20 standart senaryo (kahve, TLY analiz, kart sorusu, vade hatırlatma, vs.)
- Her senaryonun beklenen format/kategori/sayı çıktısı
- Commit öncesi otomatik çalış, regresyon varsa block et

```yaml
# .github/workflows/llm_eval.yml
- name: LLM regression test
  run: python scripts/eval_runner.py
  # 5/20 başarısız ise commit fail
```

**Eksen 3 — User behavior analytics**

Şu an sistemi sen tek başına kullanıyorsun. Mobile gelince başkaları da kullanacak. Hangi panel en çok ziyaret ediliyor? Hangi feature kullanılmıyor? PostHog (free tier) veya Plausible ile track et. Privacy-first, KVKK uyumlu olanları seç.

**Eksen 4 — Error tracking**

Sentry (free tier 5000 event/ay). Frontend exception'lar + backend stack trace'ler. Bug çıkmadan sen biliyorsun.

**Senin için somut yönelim:**

Wave-3 başlangıcında bir "Quality Sprint":
1. 20 standart senaryo yaz, expected output ile birlikte
2. `eval_runner.py` script'i (DSPy veya manuel)
3. Sentry + Prometheus + Grafana setup (1 gün)
4. PostHog opsiyonel (mobile çıktığında)

---

## 7. Vizyon-Misyon Entegrasyonu

Tüm bu önerilerin filtresi: **Mustafa mimarisi** ve **Murat'ın vizyonu** (160 IQ stratejist, dalkavukluk yapmayan, gerçek aksiyon alabilen, hatırlayan koç).

### Önerilerin Mustafa Mimarisi'ne Uyumu

| Öneri | Rules Engine | Action Schema | Reflection | Insight Memory |
|---|---|---|---|---|
| LangGraph routing | Genişletir (intent classifier deterministik) | Korur | Korur | Korur |
| DSPy optimizasyon | Etkilemez | Güçlendirir (assertion) | Güçlendirir (metric-based) | Korur |
| FSD frontend | Yansıtır (entities/features ayrımı) | UI'da netleşir | UI'da netleşir | UI'da netleşir |
| TanStack Query | Cockpit cache fast feedback | Korur | Korur | Korur |
| Observability | Kararları görünür kılar | Hangi action başarılı görür | Hangi insight değerli görür | Eski insight'lar silinir |

Hiçbiri Mustafa mimarisini bozmuyor — hepsi **mevcut mimarinin daha iyi enstrümante edilmiş, daha modüler hali**. Yıkıcı değil evrimsel.

### Vizyon Uyumu — "DeepSeek/Claude/GPT seviyesindeki tek farkın sub-agent routing"

Memory'de 6 May 17:00'de yazılı: *"Bu mimarinin DeepSeek/Claude/GPT seviyesindeki tek farki sub-agent routing eksikligi - Wave-3 isi"*. Bu rapor o vizyona somut bir yol haritası sunuyor:

1. **Sub-agent routing** = Bölüm 1 (LangGraph)
2. **Structured output garanisi** = Bölüm 2 (DSPy)
3. **Prompt optimization** = Bölüm 2 (DSPy optimizers)

Bu üçlü, FinancialOS'i "stateless explainer'dan öğrenen koç'a" geçişin (Wave-2'de yapıldı) bir sonraki adımı: **öğrenen koç'tan uzmanlaşan ekibe**.

---

## 8. Önerilen Wave-3 Yol Haritası

Wave-2 (3-30 May) bittiğinde:

### Wave-3 Hafta 1-2 — Observability foundation
- Prometheus + Grafana setup
- OpenTelemetry tracing
- LLM quality metrics (judge LLM)
- 20 standart senaryo + regression script

**Çıktı:** Her LLM çağrısının cost + latency + quality skoru görünür.

### Wave-3 Hafta 3-4 — Backend modernizasyon
- coach.py refactor (modüler yapı)
- Async tutarlılık (SQLAlchemy 2.x async)
- Rate limiting + cache
- Auth (JWT) — mobile öncesi şart

### Wave-3 Hafta 5-6 — Sub-agent routing POC
- LangGraph kurulum
- 4 ajan: notification, qa, analysis, reminder
- A/B test: tek-LLM vs LangGraph (quality + cost karşılaştırma)

### Wave-3 Hafta 7-10 — Mobile (RN+Expo)
- Daha önce hazırlanan mobil mimari raporundaki plan

### Wave-3 Hafta 11-12 — DSPy entegrasyonu
- Her ajanın prompt'unu DSPy ile yaz
- 50-100 örnek topla
- Optimize + deploy

### Wave-3 Hafta 13-14 — FSD migration + state mgmt
- Frontend Feature-Sliced Design'a geç
- TanStack Query + Zustand entegrasyonu

**Toplam:** ~3.5 ay. Senin pace'inde 4-5 ay.

---

## 9. Aklında Olmayan Yönler

Sen "aklıma gelmeyen her yön" istedin. İşte hesaba katılmamış olabilecekler:

### A — Privacy & KVKK

Mobile'a geçtiğinde başkaları kullandığında: kişisel finansal veri toplanıyor. Türkiye'de KVKK var. Önemliler:
- Veri local kalsın (cihazda) veya end-to-end encrypted bulutta
- Kullanıcı veri silme hakkı (DELETE /api/user) — şu an yok
- Veri export hakkı (GDPR Article 20 + KVKK 11) — JSON dump endpoint
- Cookie consent (web'de — şu an yok)

### B — i18n hazırlığı

Şu an Türkçe-only. Mobile dağıtınca farklı diller talep gelir. **i18next** (React) erken eklemek sonra eklemekten 10x kolay. Tüm string'ler `t('key')` üzerinden geçer, çeviri JSON dosyalarında.

### C — Monetization mimarisi

FinancialOS sadece sen kullanıyorsan bedava. Yayına çıkınca:
- Free tier vs paid (LLM çağrı limiti)
- Stripe entegrasyonu (FastLaunchAPI'de hazır şablon var)
- Subscription management
- Trial period

Bu mimari kararları erken almak, sonra retrofit etmekten kolay.

### D — Multi-tenant hazırlığı

Şu an `user_id = 1` her yerde implicit. Multi-user'a geçince her query'de `user_id` filtresi şart. Bunu şimdiden defensive olarak yaz, tek-user'da bile.

```python
# Şu an
def get_accounts(db):
    return db.query(Account).all()

# Önerilen (multi-user-ready)
def get_accounts(db, user_id: int):
    return db.query(Account).filter(Account.user_id == user_id).all()
```

### E — Disaster recovery

D3 ile backup script eklendi (iyi). Ama:
- Backup'lar nereye kopyalanıyor? Şu an sadece local. Cloud (S3, Backblaze B2) kopya?
- Restore süreci test edildi mi? Hangi adımlarla geri yükleniyor?
- DB schema migration sırasında veri kaybı yaşanırsa? (Alembic kullanmadın, ALTER TABLE manuel)

### F — Accessibility (a11y)

Mobile dağıtırken App Store accessibility istiyor. Şu an:
- Screen reader uyumu test edilmedi
- Klavye-only navigation çalışmıyor (D8 kapsamında değil — gerçek WCAG)
- Color contrast (özellikle dark mode'da metric numaraları)

WCAG 2.1 AA compliance — mobile çıkmadan eklenmesi şart.

### G — Performance budget

Frontend bundle boyutu büyüyor (Recharts + Lucide + ReactMarkdown + ...). Mobile'da 3MB JS yüklemek 3G'de saatler sürer. **Performance budget** koy:
- İlk paint < 1.5s
- Interactive < 3s
- Bundle < 500KB gzipped

Vite zaten lazy-load destekliyor, sadece React.lazy() ile her panel ayrı chunk.

### H — Versioning + breaking changes

API'n mobile app'le konuşmaya başlayınca, eski mobile app'leri kırma şansın yok. Versioning şart:
```
GET /api/v1/cockpit  # Eski mobile app
GET /api/v2/cockpit  # Yeni mobile app
```

FastAPI router prefix ile kolay. Şimdiden hazırlık.

### I — Caching tier'ları

LLM cevapları cache'lenebilir mi? Aynı user aynı soruyu 5 dk içinde sorarsa? Bu DSPy `dspy.Cache` ile yapılıyor. Maliyeti %30-50 düşürür.

### J — Eval-driven development

Test-driven development'ın LLM çağı versiyonu: önce test/eval yaz, sonra fix yap. Şu an reverse: önce fix, sonra umuyorsun çalışsın. Wave-3'te bunu tersine çevir.

---

## 10. Sonuç — Tek Karar Yerine Beş

Bu rapor mimari yolun olası adımlarını sundu. Hepsini birden yapmak zorunda değilsin. Önemlilik sırasına göre:

**Yüksek öncelik (Wave-3 başında):**
1. Observability (Bölüm 3) — kararları görünür yapar, gerisi bunun üstüne kurulur
2. Backend auth + async tutarlılığı (Bölüm 3) — mobile şart

**Orta öncelik (Wave-3 ortası):**
3. Sub-agent routing POC (Bölüm 1) — kalite sıçraması
4. State management (Bölüm 5) — frontend bakım kolaylığı

**Düşük öncelik (Wave-3 sonu / Wave-4):**
5. DSPy (Bölüm 2) — uzun vadeli kararlılık
6. FSD migration (Bölüm 4) — büyük yatırım, henüz acil değil

Hepsi birbirine bağlı ama bağımsız değerlendirilebilir. Wave-2 bitince hangisinden başlayacağına o zaman karar verirsin.

Şu an: D1 mobile responsive bitir → BUG #052/#054 doğrulanırsa commit → memory güncelle → yeni sohbet → BUG/feature listesinden devam.

Bu rapor referans dosyası olarak duracak, vakti gelince dönüş yapılır.
