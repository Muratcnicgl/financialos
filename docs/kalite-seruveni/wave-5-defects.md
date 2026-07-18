# Wave-5 Defect Log (M66-M67 KULLANIM-GATE bulguları)

Charter: her defect BUG #161+ numarası + MCP. Kapatma M68'de (kök neden + fix + test + tarayıcı tekrar-kanıt).

---

## BUG #161 [OPEN] — Koç "kredi kartı ödemesi"ni kart borcunu ARTIRACAK şekilde modelliyor

- **Bulunma:** M66 tam-döngü e2e (18 Tem 2026, Chrome). Login → koça "Ziraat kredi kartıma 500 TL ödeme
  yaptım" → koç PendingAction #41 önerdi → Onayla → execute → **finansal sonuç YANLIŞ.**
- **Beklenen:** Kart ödemesi kart borcunu 500 AZALTIR (10.180,01 → 9.680,01) + nakiti 500 azaltır (9.547,95 → 9.047,95).
- **Gerçekleşen:** Kart borcu 500 **ARTTI** (10.180,01 → 10.680,01); nakit HİÇ değişmedi.
- **Kök neden:** Koç, kart ödemesini `transaction_type=expense, account=Ziraat Kredi Kartı` olarak modelledi
  (Transaction id=2: expense/500/credit_card_payment/account_id=2). `_apply_to_balance` semantiği:
  `credit_card + expense → balance += amount` (kart harcaması borcu artırır). Yani ödeme, kart HARCAMASI
  gibi işlendi → borç arttı; ödemenin nakit ayağı hiç modellenmedi.
- **Doğru model (M68 kararı):** Kart ödemesi = **nakit → kart transfer** VEYA (a) karta `income` (borç azalır:
  `credit_card + income → balance -= amount`) + (b) nakitten `expense`. Tek-bacaklı kart-gider modeli yanlış.
- **Sınıf:** Finansal-doğruluk (kritik) — koç muhakemesi + action_executor semantik boşluğu. LLM "sadece açıklar"
  ama execute literal uyguluyor → yanlış TL. 4 wave boyunca döngü hiç işletilmediği için görülmedi (§B24).
- **Kanıt:** ActionHistory yazıldı (nw_before −12575,29 → nw_after −13075,29 — net değer YANLIŞ yönde düştü);
  cockpit kart 10680,01. Test artefaktı geri alındı (bakiye restore).
- **Fix:** M68.

## NOT (BUG değil, gözlem) — 37 "rejected" Maas pending birikmesi
- M66 sırasında DB'de 40 PendingAction görüldü: 1 pending (#40 Maas, gerçek recurring) + 37 rejected "Maas geldi"
  + 2 rejected diğer. Rejected pending'ler kullanıcı-görünür değil (cockpit yalnız pending gösterir) ama DB
  clutter. BUG #060 (duplicate Maas) alanı; rejected-retention tasarım gereği. M68'de değerlendirilir (öncelik düşük).
