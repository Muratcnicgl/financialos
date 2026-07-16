# ADR-036 — Workspace + İzin Sistemi (Aile Hesabı)

**Tarih:** 14 Tem 2026 · **Durum:** ✅ KARAR VERİLDİ (Wave-4 M39, D1 + K10) · **İlgili:** ADR-033 (auth/multi-user), KVKK-consent, W3-034 (izolasyon)

## Bağlam

ADR-033 (M11) her satıra `user_id` ekleyerek tek-kullanıcı → çok-kullanıcı temelini kurdu (17 tabloda `user_id`, `get_current_user` JWT). Murat kararı (Karar 3b): **aile hesabı** — bir kullanıcının verisini 2-5 kişilik bir aileyle **rol-bazlı** paylaşabilmesi (owner/editor/viewer + spesifik hesap erişimi). Bu "tek hedef" değil, çok-kullanıcı altyapısının genişlemesi.

Soru: `user_id`-bazlı izolasyonun üstüne **hangi paylaşım modeli** oturur? Düz grup mu, kiracı (tenant) mı, rol-bazlı workspace mi?

## D1 — Sektör Referansları (izin modeli)

| Proje | Paylaşım modeli | Rol | Gizlilik | Çıkarım |
|-------|-----------------|-----|----------|---------|
| **Splitwise** | Grup = düz "wiki"; üye her expense'i **görür + düzenler + siler** | **Rol YOK** (admin bile yok) | Grup içi gizlilik yok — "totalleri doğrulamak için herkes her şeyi görmeli" | Ortak-gider için doğru, **kişisel finans için anti-örnek** (gizlilik sıfır) |
| **YNAB Together** | Grup (max 5), **bütçe-düzeyi opt-in paylaşım** | **Group Manager + Member** | Seçmeli görünürlük (ebeveyn çocuğu görür, çocuk ebeveyni **paylaşılmadıkça görmez**) | Bize **en yakın**: rol + seçmeli görünürlük |
| **Firefly III** | **Yok** — her "administration" tek user'a kilitli | — | Paylaşım için **kullanıcı adı+şifre paylaş** (tek yol) | Açık-kaynak öz-barındırmanın **kronik boşluğu** (issue #372); "şifre paylaş" = yapmama gerekçemiz |

**Çıkarım:** (a) Splitwise'ın düz modeli reddedilir — kişisel finansta üye herkesin her şeyi silebilmesi kabul edilemez. (b) Firefly'ın credential-paylaşımı güvenlik felaketi (JWT/KVKK ihlali). (c) **YNAB'ın rol + workspace modeli doğru yön** — ama YNAB'ın "bütçe-düzeyi opt-in görünürlük"ü MVP için fazla granular; aile güven-bağlamında **workspace-düzeyi rol** yeterli (viewer tüm workspace'i okur). İleride hesap-düzeyi kısıtlama (Karar 3b "spesifik hesap erişimi") eklenebilir — şema buna açık bırakılır.

## K10 — Üç Boyut

- **MUHAKEME (hangi model uyar):** **Workspace + Membership (rol-bazlı)**. "Tenant" (her user tek org) fazla katı — bir kullanıcı hem kendi personal'ında hem eşinin workspace'inde olabilmeli (çoktan-çoğa). Düz grup (Splitwise) gizlilik vermez. Doğru model: `Workspace` (kap) + `WorkspaceMembership` (user×workspace×rol, çoktan-çoğa) + mevcut tablolara `workspace_id`. Mevcut `user_id` **korunur** (kaydı kimin oluşturduğu = audit); izin kontrolü `workspace_id` + membership rolü üzerinden.
- **BENİ DÜŞÜN (Murat solo + küçük aile):** Migration riski en büyük tehlike — 17 tabloya `workspace_id`. Strateji: **nullable ekle → her user'a "personal workspace" backfill → NOT NULL'a çevir** (ADR-013 Alembic, canlı veri korunur). Backfill idempotent + backup-önce. Rol enum küçük (owner/editor/viewer) — over-engineering yok (KURAL 12: kalite ≠ karmaşa).
- **GENELİ DÜŞÜN (KVKK + topluluk + büyüme):** KVKK açısından paylaşım = **açık rıza gerektiren veri erişimi**; davet **opt-in** olmalı (davet edilen kabul etmeden veri görmez) — Splitwise'ın "contact ver, otomatik ekle"si KVKK'ya aykırı. Davet **token'lı** (JWT, 1 saat expiry) + kabul-akışı. Workspace silme yalnız owner; üye çıkarma owner. Viewer asla yazamaz. Gelecek büyüme: hesap-düzeyi izin (`AccountAccess`) şeması bugün eklenmez ama `WorkspaceMembership` bunu bloklamaz.

## Karar

1. **Veri modeli:**
   - `Workspace(id, owner_user_id FK, name, is_personal bool, created_at)`
   - `WorkspaceMembership(id, workspace_id FK, user_id FK, role Enum[owner|editor|viewer], invited_by FK nullable, joined_at)` — `UNIQUE(workspace_id, user_id)`.
   - İzole edilecek tablolara `workspace_id` FK (nullable→NOT NULL): `Account, Transaction, Goal, PersonalDebt, PendingAction, MasterCheckpoint, Income, …` (M40'ta tam liste `user_id` taşıyan tablolardan türetilir).
2. **Geriye uyum:** Her mevcut `User` için bir **personal workspace** (`is_personal=True`, owner=kendisi); tüm kayıtları o workspace'e taşınır; user owner rolü alır. `user_id` **silinmez** (audit/oluşturan izi).
3. **İzin matrisi:**
   | Rol | Okuma | Yazma (tx/goal) | Üye davet/çıkar | Workspace sil |
   |-----|-------|-----------------|-----------------|---------------|
   | owner | ✓ | ✓ | ✓ | ✓ |
   | editor | ✓ | ✓ | ✗ | ✗ |
   | viewer | ✓ | ✗ | ✗ | ✗ |
4. **Davet:** `POST /workspaces/{id}/invite` (email+rol) → JWT invite_token (`sub=email, workspace_id, role, exp=1h`) → Brevo email → `GET /workspaces/join?token=` (mevcut session ile kabul). **Opt-in** (KVKK).
5. **Enforcement:** `require_workspace_permission(role)` bağımlılığı endpoint seviyesinde (ADR-001 ruhu: izin kod seviyesinde, prompt'a/istemciye güvenilmez). Aktif workspace `X-Workspace-Id` header veya path param.

## Alternatifler (reddedildi)

- **Düz grup (Splitwise):** rol yok, herkes siler → kişisel finansta gizlilik/güvenlik yok. RED.
- **Credential paylaşımı (Firefly mevcut hali):** şifre paylaş = JWT/KVKK ihlali, audit imkânsız. RED.
- **Tek-tenant (user=org):** çoktan-çoğa üyeliği (bir kişi birden çok aileye) engeller. RED.
- **`user_id`'yi `workspace_id` ile değiştir:** audit/oluşturan izini kaybeder + migration daha riskli. RED — ikisi bir arada.

## Uygulama Planı (M40-M44)

- **M40:** Modeller + Alembic migration (nullable) + `scripts/create_personal_workspaces.py` backfill + NOT NULL + testler.
- **M41:** `require_workspace_permission` + endpoint güncellemesi + workspace CRUD endpoint'leri + izin unit testleri.
- **M42:** Davet servisi (token+Brevo email) + join akışı + `frontend/panels/Workspace.jsx` + canlı davet-kabul.
- **M43:** Frontend workspace selector (header + localStorage `active_workspace_id` + panel context).
- **M44:** Aile özel özellikler (ortak bütçe hedefleri + üyeler arası transfer kaydı).

## Revize Tetiği

Hesap-düzeyi izin (Karar 3b "spesifik hesap erişimi") gerçek talep olursa `AccountAccess(membership_id, account_id, can_write)` tablosu eklenir — bu ADR'nin şeması buna açık. Workspace sayısı büyürse (SaaS) tenant-izolasyonu (PostgreSQL RLS, ADR-Wave4 Blok D) devreye girer.

## Kaynaklar (D1)

- Firefly III — Make it multi-user: https://docs.firefly-iii.org/how-to/firefly-iii/features/multi-user/ · issue #372 (shared data)
- YNAB Together — A Guide: https://support.ynab.com/en_us/ynab-together-B1nS78Cki
- Splitwise — group admin/permissions: https://feedback.splitwise.com/knowledgebase/articles/264547-can-i-set-a-group-admin-or-set-different-permis
