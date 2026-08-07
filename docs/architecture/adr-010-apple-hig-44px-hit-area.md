# ADR-010 — Apple HIG 44px hit area (global .btn class)

**Tarih:** 8 Mayıs 2026 · **Durum:** Kabul edildi — **gerekçesi ADR-047 ile DÜZELTİLDİ (7 Ağu 2026)**
**İlgili:** BUG #052, BUG #054, **ADR-047 / BUG #265**

> **DÜZELTME (BUG #265, 7 Ağu 2026).** Aşağıdaki "Gerekçe" bölümünün *"Global CSS class kalıcı;
> gelecekteki butonlar otomatik 44px alır"* cümlesi **ölçüldü ve yanlış çıktı**. 390px'te render
> edilen 13 panelde `.btn` sınıfını KULLANMAYAN kontroller şu boyutlardaydı: üst sekmeler 42px,
> `.input` (üç filtre `select`'i dâhil) 35px, akış aralık düğmeleri 28px, lejant düğmeleri 20px,
> onay kutusu 13px. Bir sınıf, onu kullanmayan kodu zorlayamaz — ve **hiçbir koşum bunu
> ölçmüyordu**, yani standart 3 aydır iddia olarak yaşadı. "Component bazlı tek tek fix kalıcı
> değildir" tespiti doğruydu; eksik olan sonuçtu: kalıcılığı sağlayan şey sınıf değil, sınıfı
> kullanmayanı da yakalayan **ölçüm**dür → `frontend/e2e/tema-mobil.spec.js`. İki yazılı istisna
> (cümle içi kontrol / label'a sarılı onay kutusu) ADR-047'de tanımlıdır.

> Materyalize: M74 (Wave-5, 18 Tem 2026) — kaynak MCP `adr_log`.

## Bağlam
Dokunmatik hedef alanları Apple HIG'in önerdiği 44px'in altındaydı (BUG #052, #054) — mobilde tıklanması zor butonlar.

## Karar
Global `.btn` class + `.btn-icon` (44×44px) — Apple HIG 44px hit area standardı CSS seviyesinde global uygulanır.

## Alternatifler (reddedildi)
- Component bazlı tek tek fix — kalıcı değil, yeni butonlar yine küçük çıkar.

## Gerekçe
Global CSS class kalıcı; gelecekteki butonlar otomatik 44px alır.

## Kaynak
MCP `adr_log` [8 Mayıs 2026]. Uygulama: `frontend/src/` global CSS.
