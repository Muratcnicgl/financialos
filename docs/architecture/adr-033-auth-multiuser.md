# ADR-033 — Auth + Multi-user (JWT vs Firebase, KVKK) + prod-gate güvenlik

**Tarih:** 13 Tem 2026 · **Durum:** 🟡 TASLAK — karar Wave-3 başında (M7 hazırlık, KARAR YOK) · **İlgili:** SEC-001/002, T-17 (Wave-2 ertelenen güvenlik)

## Bağlam
`dependencies.py:get_current_user` şu an "ilk kullanıcı" (MVP). Multi-user = auth buraya bağlanır (mimari sınır: yalnız burası). Wave-2'de güvenlik-sertleştirme (auth/rate-limit/HTTPS, T-17) bilinçli ertelendi (tek-kullanıcı lokal → düşük risk).

## Açık Sorular (KARAR BEKLİYOR)
1. **Auth:** kendi JWT mi, Firebase Auth mı, Supabase mi? (bakım vs bağımlılık).
2. **KVKK:** veri-ikamet (TR sunucu zorunlu mu?), şifreleme-at-rest, silme/taşıma hakkı.
3. **Izolasyon:** row-level (her sorgu user_id — çoğu zaten öyle, P1-11/14 denetlendi); RLS (Postgres) mı app-level mı?
4. **Prod-gate:** rate-limit (SEC-004), HTTPS (SEC-014), CORS (SEC-003), security headers — hangi katman (reverse proxy vs app)?
5. **Depolama:** SQLite → PostgreSQL (multi-user + Decimal tam DECIMAL, ADR-030).

## D1 (Wave-3'te yapılacak) → Research Log
JWT vs Firebase vs Supabase TR-KVKK uyum, FastAPI auth pattern'leri, OWASP ASVS multi-user.

## Karar
**(BOŞ — Wave-3 başında D1 sonrası.)**

## Kaynak
wave-3-master-plan.md §3, SEC boyutu, T-17.
