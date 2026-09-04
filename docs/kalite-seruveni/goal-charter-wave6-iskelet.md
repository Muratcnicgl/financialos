# Goal Charter — WAVE-6 İSKELETİ (aday girdiler)

> ## ℹ️ 5 Eylül 2026 DENETİMİ — BU İSKELET GERÇEKLEŞTİ, aktif hat başka
>
> Wave-6 (M82-M91) **koşuldu ve kapandı**; bu iskelet artık bir yol haritası değil,
> onun girdi kaydıdır. **Bugün aktif iki hat var:**
> `docs/kalite-seruveni/masterprompt-koc.md` (Wave-K — koç zekâsı) ve
> `docs/kalite-seruveni/wave-y-ledger.md` (Wave-Y — yayın/kalite). Planlama için
> bu belge değil, o ikisi okunur.

**Durum:** 🔲 TASLAK/İSKELET — Wave-5 kapanışında (M81) oluşturuldu. **Henüz aktif goal DEĞİL.**
**Tarih:** 2026-07-18 · **Öncül:** Wave-5 SAĞLAMLAŞTIRMA (M66-M81) TAMAM.

> Bu bir iskelet. Wave-6 başlamadan önce Murat ÜRÜN-DNA kararı verecek (hangi blok, hangi sıra, ne kapsam dışı).
> Charter'ı Wave-5 formatına tam materyalize etmek Wave-6'nın M-ilk işi. Aşağısı Wave-5'in ürettiği KANITLI adaylar.

## Wave-5'in bıraktığı somut girdiler (hepsi diskte kanıtlı)

### A — Rules Engine doğruluk borcu (M76 tam-doğrulamasından)
En kritik boyut RULE'da **12 hâlâ AÇIK + 3 KISMEN** madde (M76'da kod-doğrulandı, `sections/DURUM-INDEX.md`):
- **AÇIK:** RULE-007 (FIFO lot yapısı yok), RULE-012 (_simulate korunum eşiği), RULE-013 (yeni-borç ilerleme maskeleme),
  RULE-022 (detect_alerts testsiz), RULE-025 (avalanche/snowball tie-break yok), RULE-027 (shadow guard yok),
  RULE-028 (negatif limit guard yok), RULE-031 (korunum invariant testi yok), RULE-032 (extra_monthly=0 kötümser),
  RULE-036 (gün-numarası karşılaştırma tam tarih değil), RULE-037 (sıfır-tutar yutma), RULE-038 (magic number + işaret maskesi).
- **KISMEN:** RULE-029 (datetime karışımı default yolda), RULE-030 (kredi kartı döngüsü forecast dışı), RULE-033 (banker's rounding).
- **Not:** RULE-030 (kart döngüsü) MC3 Ziraat dongusu — ADR-021 REV3'te "Wave-3'te kalır" denmişti, hâlâ açık.

### B — Tek doğruluk kaynağı (BUG #161 dersi)
`action_type` **3 yerde ayrı listeleniyor** (coach tool enum + propose_action valid_types + execute dispatcher) →
BUG #161 kaçağı buradan geldi (M68). Tek kaynak (enum/registry) + tutarlılık testi. Wave-6 adayı (M68 notu).

### C — Backlog tam doğrulama (M76 dürüst sınırı)
Diğer 17 boyut (481 madde) `Durum` alanı aldı ama **madde-madde kod-doğrulanmadı**. RULE'da ölçülen %42 stale
oranı ekstrapole edilirse ~200 maddenin zaten düzelmiş olması beklenir (TAHMİN). Her boyut bir subagent turu.

### D — dosya-denetimi tam yeniden-doğrulama (M77 dürüst sınırı)
75 per-dosya rapor banner'landı ama madde-madde doğrulanmadı (1 rapordan 2 bulgu örneklendi, 2/2 stale). ~75 tur.

### E — goals.user_id NOT NULL sıkılaştırma (M75 ertelemesi)
Goal, 17 scoped modelin tek'i user_id nullable=True. SQLite batch-recreate riski (inbound FK) →
**PostgreSQL geçişinde** (Blok D, Wave-4 ertelenen) veya dikkatli SQLite recreate ile.

### F — Gerçek kullanım (Wave-5'in çözemediği kök sorun)
`transactions=0` hâlâ geçerli olabilir — sistem kurulu ama Murat günlük kullanmıyor. Kullanım döngüsü
CI'da otomatik kanıtlanıyor (M69) ama GERÇEK kullanıcı verisi birikmesi ayrı. Wave-6 ÜRÜN-DNA kararı.

### G — Wave-4 ertelenenler (ÜRÜN-DNA ile kapsam dışıydı)
Kripto (Numeric 28,8), PostgreSQL+RLS, canlı VPS deploy (M80 docker'ı statik-doğruladı → canlı ayağa kaldırma),
mobil (ADR-009/032). Murat bir VPS + gerçek kullanım kararı verirse açılır.

## KAPSAM DIŞI hatırlatma (Wave-5 ÜRÜN-DNA'sı — Murat aksini söylemedikçe)
kripto · VPS/deploy-canlı · PostgreSQL · mobil. Bunlar Wave-6'da da Murat açık karar vermeden AÇILMAZ.

## Wave-6 başlarken yapılacak (M-ilk)
1. Bu iskeleti Murat'ın ÜRÜN-DNA kararıyla tam charter'a çevir (blok seçimi + sıra + kapsam).
2. `git tag pre-wave-6` (rollback noktası).
3. Milestone-log'a Wave-6 bölümü.
