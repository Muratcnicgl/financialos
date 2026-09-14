# Finansal Sözlük — terimler, formüller, kaynak

Alan-özel terimlerin **tek tanım yeri** (DOCS-015 / BUG #496). Her madde üç şey söyler:
ne demek, nasıl hesaplanır, kodda **nerede** (tek kaynak). Arayüz metni ve koç üslubu bu
tanımlara dayanır; `tests/test_sozluk_kapisi.py` her `Kaynak:` satırındaki sembolün gerçekten
var olduğunu ölçer — sözlük koddan kopamaz.

Konvansiyon: para `Decimal` (ADR-030), tarih kullanıcı saat dilimi (BUG #197/#237), oranlar
yüzde olarak yazılır, "borç" pozitif sayıdır (işaret formülde).

## Reel bütçe
Ay sonuna kadar **gerçekten harcanabilir** para. Kart harcaması cebinde duran nakdi azaltır
(gölge muhasebe, MC4): kart borcu "harcanmış para"dır; ay sonu kredi taksitleri zorunlu çıkıştır.
Kişisel alacaklar dahil **değildir** — tahsilat muhatabın kontrolündedir.

    reel_butce = nakit + düzenli gelir (bu ay kalan) − kart borcu (tamamı) − bu ayki kredi taksitleri

Kaynak: `app/rules_engine.py::apply_shadow_accounting` · kokpit `butce_dokum` bunu kalem kalem gösterir (FEAT-030).

## Günlük limit
Reel bütçenin ay sonuna kalan güne bölünmüş hali. Gün kalmadıysa 0.

    daily_limit = reel_butce / days_remaining

Kaynak: `app/rules_engine.py::calculate_daily_limit`.

## Zikzak (dinamik limit)
Bugün az harcanınca yarınki limit **kendiliğinden** yükselir, çok harcanınca düşer — çünkü
limit her gün *kalan bütçe / kalan gün* olarak yeniden hesaplanır. Eski "devreden bakiye"yi
limite **eklemek** çift sayımdı ve reddedildi (ADR-026): `carried_forward` bilinçli 0'dır,
`today_target = daily_limit`. Aşım negatif döner (klemp yok): kullanıcı "yarından ne kadar
borçlandım"ı görür (UX-004).

Kaynak: `app/rules_engine.py::calculate_carried_forward` (DEPRECATED gerekçesi başında) · ADR-026.

## Görülen net değer
Cüzdanı açınca görünen değer — operasyonel. Emanet ve kişisel alacak/borç dahil değil.

    net_deger = nakit + yatırım − kart borcu − kredi borcu

Kaynak: `app/balance_rules.py::net_worth_seen` (TEK KAYNAK; backfill de bunu kullanır) · ADR-003.

## Tam net değer
Stratejik değer — görülen net değere sözleşmeli kişisel alacaklar eklenir, kişisel borçlar düşülür.

    net_deger_tam = net_deger + kişisel alacaklar − kişisel borçlar

Kaynak: `app/balance_rules.py::net_worth_full` · ADR-003.

## Emanet
Kullanıcıya ait olmayan, **dokunulmaz** para (başkasının emanet ettiği yatırım/nakit). Kokpitte
ayrı kalem (`emanet_kasa`), net değere **girmez**, koç bu hesaptan çıkış öneremez; `is_emanet`
işaretli hesap kod seviyesinde korunur (MC1, `account_untouchable` kuralı ile aynı sınıf).

Kaynak: `app/models.py::Account.is_emanet` · `app/user_rules.py` (dayatma) · `app/rules_engine.py::generate_cockpit` (emanet_deger ayrımı).

## Yatırım değeri
Yatırım hesabının değeri **lot × güncel fiyat**tır; DB'deki `balance` gösterilmez (kuruş
sapması BUG #007). Fiyat bayatsa (`is_price_stale`) kokpit "bayat" işaretler, koç "güncel" demez.

    deger = lot_count × current_price

Kaynak: `app/rules_engine.py::generate_cockpit` (investment dalı) · `app/fund_tracker.py::is_price_stale`.

## Kart doluluk bandı
Toplam kart borcu / toplam limit. Eşikler kredi-skoru davranışından: **< %30 sağlıklı**,
**30–70 orta**, **70–90 yüksek**, **≥ 90 kritik**. "Sağlıklı borç hedefi" = limitin %30'u.

Kaynak: `app/rules_engine.py::_UTIL_HEALTHY` / `_UTIL_HIGH` / `_UTIL_CRITICAL` (FEAT-016).

## Kart asgari ödemesi ve son ödeme
Asgari, **ekstre borcu** üzerinden hesabın kendi oranıyla hesaplanır; oran bilinmiyorsa yedek
%25 kullanılır ve bunun VARSAYIM olduğu söylenir (BUG #330/#337/#340). Son ödeme günü
`payment_day`, tutar ekstre borcu (bilinmiyorsa güncel borç).

Kaynak: `app/debt_strategy.py::gecerli_asgari_oran` · `app/debt_strategy.py::MIN_CARD_PAYMENT_RATIO` · `app/rules_engine.py::kart_son_odeme`.

## Nakit pisti (runway)
Hiç gelir gelmezse mevcut nakit kaç gün yeter: son 30 günün harcama hızı **artı** aylık kredi
taksiti/30 (BUG #124) ile bölünür. Nakit ≤ 0 → 0 gün; hiç gider yoksa belirsiz (None).

    runway_gun = nakit / ((son 30 gün gider / 30) + aylık taksit / 30)

Kaynak: `app/rules_engine.py::_calculate_cash_runway` (FEAT-010).

## Güvenli harcama
Önümüzdeki 30 günün nakit projeksiyonunda **en düşük bakiye**yi tamponun altına düşürmeden
bugün harcanabilecek en yüksek tutar; kart borcu farkındalıklı (BUG #123).

Kaynak: `app/rules_engine.py::_calculate_safe_to_spend` (FEAT-009) · `app/cashflow.py` (projeksiyon).

## Borç kilometre taşı
Başlangıç borcuna göre ödenen yüzde; **%10 / %25 / %50 / %75** eşikleri ayrık kutlama
noktalarıdır (sürekli metrikten daha motive edici — FEAT-017). Taze geçiş, önceki snapshot
ile karşılaştırılarak bulunur; kokpit pankartı ve koç yalnız taze geçişte kutlar (UX-035).

Kaynak: `app/rules_engine.py::_debt_milestone_band` · `app/rules_engine.py::calculate_debt_progress`.

## Kartopu / Çığ (borç stratejisi)
**Kartopu (snowball)**: en küçük bakiyeden başla — psikolojik ivme. **Çığ (avalanche)**: en
yüksek faizden başla — matematiksel optimum (toplam faiz en az). Kapanış artığı son ödemeye
eklenir (BUG #438); benimsenen plan hedefe bağlanır ve projeksiyon onu okur (UX-024).

Kaynak: `app/debt_strategy.py::compare_strategies` · `app/goal_engine.py::plan_secimi`.

## Nakit tabanı · Tek harcama tavanı · Dokunulmaz hesap
Kullanıcının kendi koyduğu, **kod seviyesinde dayatılan** üç kural: nakit toplamı X'in altına
inecek aksiyon reddedilir; tek işlemde X üstü harcama reddedilir; belirtilen hesaptan çıkış
reddedilir. Serbest metin kural yalnız koça "dikkate al" der — dayatma değildir (H21).

Kaynak: `app/user_rules.py` · `app/routers/checkpoints.py::CheckpointBase` (`rule_type`: `min_cash_floor` / `max_single_expense` / `account_untouchable`).

## Bugün kalan
Günlük limitten bugün harcananın çıkarılmış hali; hızlı girişte aşım onayı bunu kullanır (UX-004/005).

    bugun_kalan = daily_limit − bugün harcanan

Kaynak: `app/rules_engine.py::generate_cockpit` (`bugun_harcanan`, `bugun_kalan`) · `frontend/src/lib/bugunKalan.js`.
