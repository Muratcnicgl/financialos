<!-- OTOMATIK-VERI-MODELI — elle düzenleme; `python scripts/veri_modeli_belgesi.py --yaz` -->

# Veri Modeli

Bu belge `app/models.py` metadata'sından ÜRETİLİR (DOCS-012 / BUG #473). Konvansiyonlar:

- **Para:** `Numeric(19,4)` (ADR-030, kuruş kesinliği; NUMERIC-030 kapısı). Kart bakiyesi BORÇ olarak pozitif.
- **Zaman:** `created_at` sunucu UTC; kullanıcı günü `user_today()` ile (BUG #197/#237). Naive/aware karışımı DATA-007'de kayıtlı.
- **Kapsam:** `user_id` + `workspace_id` (M43); sorgular `scope_filter`/`_scope` ile, istisna `# scope-exempt: <sebep>`.
- **Denetim:** `user_id` + para sütunu olan tablolar `audit_log`'a flush kancasıyla yazar (BUG #418/#443); muaflar/ekler `app/denetim.py`.
- **Bütünlük:** DB CHECK yerine ORM `before_flush` kuralları (`app/butunluk.py`, BUG #444–#447).
- **Saklama:** `app/scheduler.py::SAKLAMA_KURALLARI` (gün); KVKK silme `app/data_subject.py` kaydı.

## `accounts` — denetlenir, workspace kapsamlı

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `user_id` | INTEGER | hayır |  | users.id |  |
| `workspace_id` | INTEGER | evet |  | workspaces.id | index |
| `name` | VARCHAR(100) | hayır |  |  |  |
| `account_type` | VARCHAR(11) | hayır |  |  |  |
| `balance` | NUMERIC(19, 4) | hayır | 0.0 |  | para |
| `notes` | TEXT | evet |  |  |  |
| `credit_limit` | NUMERIC(19, 4) | evet |  |  | para |
| `statement_day` | INTEGER | evet |  |  |  |
| `payment_day` | INTEGER | evet |  |  |  |
| `interest_rate` | FLOAT | evet |  |  |  |
| `min_payment_ratio` | FLOAT | evet |  |  |  |
| `statement_balance` | NUMERIC(19, 4) | evet |  |  | para |
| `monthly_payment` | NUMERIC(19, 4) | evet |  |  | para |
| `remaining_installments` | INTEGER | evet |  |  |  |
| `next_payment_date` | DATE | evet |  |  |  |
| `early_payoff_amount` | NUMERIC(19, 4) | evet |  |  | para |
| `asset_type` | VARCHAR(10) | evet |  |  |  |
| `fund_code` | VARCHAR(20) | evet |  |  |  |
| `lot_count` | FLOAT | evet |  |  |  |
| `cost_per_lot` | NUMERIC(19, 4) | evet |  |  | para |
| `current_price` | NUMERIC(19, 4) | evet |  |  | para |
| `last_price_update` | DATETIME | evet |  |  |  |
| `is_emanet` | BOOLEAN | hayır | False |  |  |
| `created_at` | DATETIME | evet | fn:utcnow |  |  |
| `updated_at` | DATETIME | evet | fn:utcnow |  |  |

İndeks/kısıt: index `ix_accounts_user_type` (user_id, account_type); index `ix_accounts_workspace_id` (workspace_id)

## `action_history`

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `user_id` | INTEGER | hayır |  | users.id |  |
| `action_type` | VARCHAR(50) | hayır |  |  |  |
| `payload` | TEXT | hayır |  |  |  |
| `summary` | TEXT | hayır |  |  |  |
| `source` | VARCHAR(6) | hayır | <ActionSource.user: 'user'> |  |  |
| `pending_action_id` | INTEGER | evet |  | pending_actions.id |  |
| `success` | BOOLEAN | hayır | True |  |  |
| `error_message` | TEXT | evet |  |  |  |
| `net_worth_before` | NUMERIC(19, 4) | evet |  |  | para |
| `net_worth_after` | NUMERIC(19, 4) | evet |  |  | para |
| `cash_before` | NUMERIC(19, 4) | evet |  |  | para |
| `cash_after` | NUMERIC(19, 4) | evet |  |  | para |
| `reverted_at` | DATETIME | evet |  |  |  |
| `reverted_by_action_id` | INTEGER | evet |  | action_history.id |  |
| `applied_at` | DATETIME | hayır | fn:utcnow |  |  |

İndeks/kısıt: index `ix_action_history_user_applied` (user_id, applied_at); index `ix_action_history_user_type` (user_id, action_type)

## `api_call_log` — saklama 90 gün

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `user_id` | INTEGER | hayır |  | users.id |  |
| `provider` | VARCHAR(20) | hayır |  |  |  |
| `model` | VARCHAR(50) | hayır |  |  |  |
| `status` | VARCHAR(12) | hayır | <ApiCallStatus.success: 'success'> |  |  |
| `tokens_in` | INTEGER | evet |  |  |  |
| `tokens_out` | INTEGER | evet |  |  |  |
| `est_cost_usd` | NUMERIC(12, 6) | evet |  |  | para |
| `amac` | VARCHAR(20) | evet |  |  |  |
| `tool_calls_count` | INTEGER | hayır | 0 |  |  |
| `error_code` | VARCHAR(20) | evet |  |  |  |
| `error_message` | TEXT | evet |  |  |  |
| `duration_ms` | INTEGER | evet |  |  |  |
| `called_at` | DATETIME | hayır | fn:utcnow |  |  |

İndeks/kısıt: index `ix_api_calls_user_called` (user_id, called_at); index `ix_api_calls_user_provider_called` (user_id, provider, called_at)

## `audit_log` — saklama 365 gün, workspace kapsamlı

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `user_id` | INTEGER | hayır |  | users.id | index |
| `workspace_id` | INTEGER | evet |  | workspaces.id (SET NULL) | index |
| `entity` | VARCHAR(40) | hayır |  |  |  |
| `entity_id` | INTEGER | evet |  |  |  |
| `action` | VARCHAR(10) | hayır |  |  |  |
| `before_json` | TEXT | evet |  |  |  |
| `after_json` | TEXT | evet |  |  |  |
| `istek_id` | VARCHAR(64) | evet |  |  |  |
| `created_at` | DATETIME | hayır | fn:utcnow |  | index |

İndeks/kısıt: index `ix_audit_log_created_at` (created_at); index `ix_audit_log_user_id` (user_id); index `ix_audit_log_workspace_id` (workspace_id)

## `beta_invites`

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `code` | VARCHAR(40) | hayır |  |  | unique index |
| `email` | VARCHAR(255) | evet |  |  |  |
| `note` | VARCHAR(200) | evet |  |  |  |
| `created_at` | DATETIME | hayır | fn:utcnow |  |  |
| `expires_at` | DATETIME | evet |  |  |  |
| `used_at` | DATETIME | evet |  |  |  |
| `used_by_user_id` | INTEGER | evet |  |  |  |

İndeks/kısıt: unique index `ix_beta_invites_code` (code)

## `categories` — workspace kapsamlı

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `user_id` | INTEGER | hayır |  | users.id | index |
| `workspace_id` | INTEGER | evet |  | workspaces.id | index |
| `slug` | VARCHAR(50) | hayır |  |  |  |
| `ad` | VARCHAR(50) | hayır |  |  |  |
| `kart_varsayilani` | BOOLEAN | hayır | False |  |  |
| `sistem` | BOOLEAN | hayır | False |  |  |
| `gizli` | BOOLEAN | hayır | False |  |  |
| `created_at` | DATETIME | evet | fn:utcnow |  |  |

İndeks/kısıt: index `ix_categories_user_id` (user_id); index `ix_categories_workspace_id` (workspace_id); UniqueConstraint uq_category_user_ws_slug (user_id, workspace_id, slug)

## `coach_insights`

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `user_id` | INTEGER | hayır |  | users.id |  |
| `content` | TEXT | hayır |  |  |  |
| `category` | VARCHAR(50) | evet |  |  |  |
| `priority` | VARCHAR(8) | hayır | <InsightPriority.normal: 'normal'> |  |  |
| `dedup_key` | VARCHAR(80) | evet |  |  |  |
| `source_message_id` | INTEGER | evet |  | coach_memories.id |  |
| `is_active` | BOOLEAN | hayır | True |  |  |
| `expires_at` | DATE | evet |  |  |  |
| `created_at` | DATETIME | evet | fn:utcnow |  |  |
| `last_referenced_at` | DATETIME | evet |  |  |  |
| `insight_type` | VARCHAR(50) | evet |  |  |  |
| `title` | VARCHAR(200) | evet |  |  |  |
| `confidence_basis` | VARCHAR(30) | evet |  |  |  |
| `source_refs` | TEXT | evet |  |  |  |
| `evidence_count` | INTEGER | hayır | 0 |  |  |
| `counter_evidence_count` | INTEGER | hayır | 0 |  |  |
| `last_evidence_at` | DATETIME | evet |  |  |  |
| `last_counter_at` | DATETIME | evet |  |  |  |
| `status` | VARCHAR(20) | evet | 'active' |  |  |
| `activated_at` | DATETIME | evet |  |  |  |
| `last_seen_at` | DATETIME | evet |  |  |  |
| `para_category` | VARCHAR(20) | evet |  |  |  |
| `archived_at` | DATETIME | evet |  |  |  |
| `archived_reason` | VARCHAR(50) | evet |  |  |  |
| `sort_priority` | INTEGER | hayır | 5 |  |  |

İndeks/kısıt: index `ix_insights_user_active_priority` (user_id, is_active, priority); unique index `uix_insights_user_dedup` (user_id, dedup_key); UniqueConstraint uq_insights_type_title (user_id, insight_type, title)

## `coach_memories`

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `user_id` | INTEGER | hayır |  | users.id |  |
| `role` | VARCHAR(20) | hayır |  |  |  |
| `content` | TEXT | hayır |  |  |  |
| `tool_calls_json` | TEXT | evet |  |  |  |
| `tool_call_id` | VARCHAR(64) | evet |  |  |  |
| `pending_action_ids_json` | TEXT | evet |  |  |  |
| `timestamp` | DATETIME | evet | fn:utcnow |  |  |

İndeks/kısıt: index `ix_memories_user_timestamp` (user_id, timestamp)

## `decision_journal` — workspace kapsamlı

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `user_id` | INTEGER | hayır |  | users.id |  |
| `workspace_id` | INTEGER | evet |  | workspaces.id | index |
| `decision_text` | TEXT | hayır |  |  |  |
| `decision_type` | VARCHAR(40) | evet |  |  |  |
| `related_action_id` | INTEGER | evet |  | action_history.id (SET NULL) |  |
| `predicted_outcome` | TEXT | evet |  |  |  |
| `confidence_at_decision` | INTEGER | evet |  |  |  |
| `mc_rules_applied` | TEXT | evet |  |  |  |
| `cockpit_snapshot_hash` | VARCHAR(64) | evet |  |  |  |
| `premortem_scenarios` | TEXT | evet |  |  |  |
| `premortem_run_at` | DATETIME | evet |  |  |  |
| `actual_outcome` | TEXT | evet |  |  |  |
| `outcome_evaluated_at` | DATETIME | evet |  |  |  |
| `outcome_score` | INTEGER | evet |  |  |  |
| `lessons_learned` | TEXT | evet |  |  |  |
| `decided_at` | DATETIME | hayır | server: now() |  |  |
| `para_category` | VARCHAR(20) | hayır | 'project' |  |  |

İndeks/kısıt: index `idx_decision_journal_pending_eval` (user_id); index `idx_decision_journal_user_time` (user_id, decided_at); index `ix_decision_journal_workspace_id` (workspace_id)

## `demo_data_markers`

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `user_id` | INTEGER | hayır |  | users.id | index |
| `table_name` | VARCHAR(40) | hayır |  |  |  |
| `row_id` | INTEGER | hayır |  |  |  |
| `created_at` | DATETIME | evet | fn:utcnow |  |  |

İndeks/kısıt: index `ix_demo_data_markers_user_id` (user_id); index `ix_demo_marker_user_table` (user_id, table_name)

## `envelopes` — denetlenir, workspace kapsamlı

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `user_id` | INTEGER | hayır |  | users.id | index |
| `workspace_id` | INTEGER | evet |  | workspaces.id | index |
| `category` | VARCHAR(50) | hayır |  |  |  |
| `monthly_amount` | NUMERIC(14, 2) | hayır |  |  | para |
| `is_active` | BOOLEAN | hayır | True |  |  |
| `notes` | TEXT | evet |  |  |  |
| `created_at` | DATETIME | evet | fn:utcnow |  |  |

İndeks/kısıt: index `ix_envelopes_user_id` (user_id); index `ix_envelopes_workspace_id` (workspace_id); UniqueConstraint uq_envelope_user_category (user_id, category)

## `error_logs`

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `fingerprint` | VARCHAR(32) | hayır |  |  | unique index |
| `error_type` | VARCHAR(80) | hayır |  |  |  |
| `message` | TEXT | evet |  |  |  |
| `path` | VARCHAR(200) | evet |  |  |  |
| `method` | VARCHAR(10) | evet |  |  |  |
| `traceback_tail` | TEXT | evet |  |  |  |
| `occurrence_count` | INTEGER | hayır | 1 |  |  |
| `first_seen_at` | DATETIME | hayır |  |  |  |
| `last_seen_at` | DATETIME | hayır |  |  |  |
| `last_user_id` | INTEGER | evet |  |  |  |
| `last_istek_id` | VARCHAR(64) | evet |  |  |  |

İndeks/kısıt: unique index `ix_error_logs_fingerprint` (fingerprint)

## `feedback` — workspace kapsamlı

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `user_id` | INTEGER | evet |  | users.id | index |
| `workspace_id` | INTEGER | evet |  | workspaces.id | index |
| `kind` | VARCHAR(20) | hayır |  |  |  |
| `message` | TEXT | hayır |  |  |  |
| `page` | VARCHAR(80) | evet |  |  |  |
| `status` | VARCHAR(20) | hayır | 'new' |  |  |
| `created_at` | DATETIME | hayır | fn:utcnow |  |  |
| `app_version` | VARCHAR(40) | evet |  |  |  |
| `istek_id` | VARCHAR(64) | evet |  |  |  |
| `viewport_w` | INTEGER | evet |  |  |  |
| `tarayici` | VARCHAR(40) | evet |  |  |  |
| `pwa` | BOOLEAN | evet |  |  |  |

İndeks/kısıt: index `ix_feedback_user_id` (user_id); index `ix_feedback_workspace_id` (workspace_id)

## `goal_allocations`

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `goal_id` | INTEGER | hayır |  | goals.id (CASCADE) |  |
| `transaction_id` | INTEGER | hayır |  | transactions.id (CASCADE) |  |
| `amount` | NUMERIC(14, 2) | hayır |  |  | para |
| `source` | VARCHAR(20) | hayır | 'manual' |  |  |
| `rule_id` | INTEGER | evet |  | goal_rules.id (SET NULL) |  |
| `created_at` | DATETIME | hayır | fn:utcnow |  |  |

İndeks/kısıt: index `ix_goal_allocations_goal_id` (goal_id); index `ix_goal_allocations_transaction_id` (transaction_id); UniqueConstraint uq_goal_tx (goal_id, transaction_id)

## `goal_rules`

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `goal_id` | INTEGER | hayır |  | goals.id (CASCADE) |  |
| `name` | VARCHAR(200) | hayır |  |  |  |
| `priority` | INTEGER | hayır | 0 |  |  |
| `criteria` | JSON | hayır |  |  |  |
| `allocation_type` | VARCHAR(20) | hayır |  |  |  |
| `allocation_value` | NUMERIC(10, 2) | evet |  |  | para |
| `is_active` | BOOLEAN | hayır | True |  |  |
| `created_at` | DATETIME | hayır | fn:utcnow |  |  |

İndeks/kısıt: index `ix_goal_rules_goal_id` (goal_id)

## `goals` — denetlenir, workspace kapsamlı

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `goal_type` | VARCHAR(20) | hayır |  |  |  |
| `user_id` | INTEGER | evet |  | users.id | index |
| `workspace_id` | INTEGER | evet |  | workspaces.id | index |
| `title` | VARCHAR(200) | hayır |  |  |  |
| `target_amount` | NUMERIC(14, 2) | hayır |  |  | para |
| `target_date` | DATE | evet |  |  |  |
| `baseline_amount` | NUMERIC(14, 2) | evet |  |  | para |
| `status` | VARCHAR(20) | hayır | 'active' |  |  |
| `current_amount` | NUMERIC(14, 2) | hayır | 0 |  | para |
| `progress_percent` | NUMERIC(5, 2) | hayır | 0 |  | para |
| `projected_completion_date` | DATE | evet |  |  |  |
| `last_refreshed_at` | DATETIME | evet |  |  |  |
| `created_at` | DATETIME | hayır | fn:utcnow |  |  |
| `updated_at` | DATETIME | hayır | fn:utcnow |  |  |
| `achieved_at` | DATETIME | evet |  |  |  |
| `plan` | JSON | evet |  |  |  |

İndeks/kısıt: index `ix_goals_goal_type` (goal_type); index `ix_goals_status` (status); index `ix_goals_user_id` (user_id); index `ix_goals_workspace_id` (workspace_id)

## `master_checkpoints` — denetlenir, workspace kapsamlı

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `user_id` | INTEGER | hayır |  | users.id |  |
| `workspace_id` | INTEGER | evet |  | workspaces.id | index |
| `title` | VARCHAR(200) | hayır |  |  |  |
| `description` | TEXT | hayır |  |  |  |
| `checkpoint_type` | VARCHAR(8) | hayır |  |  |  |
| `priority` | INTEGER | hayır | 2 |  |  |
| `is_active` | BOOLEAN | hayır | True |  |  |
| `is_system` | BOOLEAN | hayır | False |  |  |
| `rule_type` | VARCHAR(40) | evet |  |  |  |
| `rule_params` | TEXT | evet |  |  |  |
| `created_at` | DATETIME | evet | fn:utcnow |  |  |

İndeks/kısıt: index `ix_checkpoints_user_active_priority` (user_id, is_active, priority); index `ix_master_checkpoints_workspace_id` (workspace_id)

## `net_worth_snapshots` — workspace kapsamlı

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `user_id` | INTEGER | hayır |  | users.id |  |
| `workspace_id` | INTEGER | evet |  | workspaces.id | index |
| `snapshot_date` | DATE | hayır |  |  |  |
| `net_worth_seen` | NUMERIC(19, 4) | hayır |  |  | para |
| `net_worth_full` | NUMERIC(19, 4) | hayır |  |  | para |
| `cash` | NUMERIC(19, 4) | hayır |  |  | para |
| `card_debt` | NUMERIC(19, 4) | hayır |  |  | para |
| `loan_debt` | NUMERIC(19, 4) | hayır |  |  | para |
| `investment_value` | NUMERIC(19, 4) | hayır |  |  | para |
| `receivables` | NUMERIC(19, 4) | hayır | 0.0 |  | para |
| `created_at` | DATETIME | evet | fn:utcnow |  |  |

İndeks/kısıt: index `ix_net_worth_snapshots_workspace_id` (workspace_id); index `ix_nws_user_date` (user_id, snapshot_date); UniqueConstraint uq_nws_user_date (user_id, snapshot_date)

## `pending_actions` — denetlenir, workspace kapsamlı

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `user_id` | INTEGER | hayır |  | users.id |  |
| `workspace_id` | INTEGER | evet |  | workspaces.id | index |
| `action_type` | VARCHAR(50) | hayır |  |  |  |
| `payload` | TEXT | hayır |  |  |  |
| `summary` | TEXT | hayır |  |  |  |
| `status` | VARCHAR(8) | hayır | <ActionStatus.pending: 'pending'> |  |  |
| `error_message` | TEXT | evet |  |  |  |
| `warning` | TEXT | evet |  |  |  |
| `created_at` | DATETIME | evet | fn:utcnow |  |  |
| `resolved_at` | DATETIME | evet |  |  |  |
| `source_recurring_id` | INTEGER | evet |  |  |  |
| `source_recurring_type` | VARCHAR(20) | evet |  |  |  |

İndeks/kısıt: index `ix_pending_actions_workspace_id` (workspace_id); index `ix_pending_user_status` (user_id, status)

## `personal_debts` — denetlenir, workspace kapsamlı

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `user_id` | INTEGER | hayır |  | users.id |  |
| `workspace_id` | INTEGER | evet |  | workspaces.id | index |
| `counterparty` | VARCHAR(100) | hayır |  |  |  |
| `direction` | VARCHAR(10) | hayır |  |  |  |
| `amount` | NUMERIC(19, 4) | hayır |  |  | para |
| `description` | TEXT | evet |  |  |  |
| `due_date` | DATE | evet |  |  |  |
| `is_paid` | BOOLEAN | hayır | False |  |  |
| `paid_date` | DATE | evet |  |  |  |
| `settlement_account_id` | INTEGER | evet |  | accounts.id |  |
| `created_at` | DATETIME | evet | fn:utcnow |  |  |

İndeks/kısıt: index `ix_debts_user_due` (user_id, due_date); index `ix_debts_user_paid` (user_id, is_paid); index `ix_personal_debts_workspace_id` (workspace_id)

## `price_history`

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `fund_code` | VARCHAR(20) | hayır |  |  | PK |
| `price_date` | DATE | hayır |  |  | PK |
| `source` | VARCHAR(9) | hayır |  |  | PK |
| `close_price` | NUMERIC(19, 4) | hayır |  |  | para |
| `fetched_at` | DATETIME | hayır | fn:<lambda> |  |  |

İndeks/kısıt: index `ix_price_history_fund_date` (fund_code, price_date)

## `rate_limit_hits`

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `bucket_key` | VARCHAR(160) | hayır |  |  | index |
| `hit_at` | DATETIME | hayır |  |  | index |

İndeks/kısıt: index `ix_rate_limit_hits_bucket_key` (bucket_key); index `ix_rate_limit_hits_hit_at` (hit_at); index `ix_rate_limit_key_time` (bucket_key, hit_at)

## `reasoning_traces` — saklama 90 gün

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `user_id` | INTEGER | hayır |  | users.id |  |
| `trace_id` | VARCHAR(36) | hayır |  |  |  |
| `step_index` | INTEGER | hayır |  |  |  |
| `parent_step_id` | INTEGER | evet |  | reasoning_traces.id |  |
| `coach_memory_id` | INTEGER | evet |  | coach_memories.id |  |
| `operation_name` | VARCHAR(12) | hayır |  |  |  |
| `intent` | TEXT | evet |  |  |  |
| `action_input_json` | TEXT | evet |  |  |  |
| `observation` | TEXT | evet |  |  |  |
| `inference` | TEXT | evet |  |  |  |
| `confidence_score` | FLOAT | evet |  |  |  |
| `provider_system` | VARCHAR(50) | evet |  |  |  |
| `model_name` | VARCHAR(100) | evet |  |  |  |
| `usage_input_tokens` | INTEGER | evet |  |  |  |
| `usage_output_tokens` | INTEGER | evet |  |  |  |
| `latency_ms` | INTEGER | evet |  |  |  |
| `error` | TEXT | evet |  |  |  |
| `created_at` | DATETIME | hayır | server: now() |  |  |

İndeks/kısıt: index `ix_reasoning_traces_coach_memory_id` (coach_memory_id); index `ix_reasoning_traces_created_at` (created_at); index `ix_reasoning_traces_trace_id_step_index` (trace_id, step_index); index `ix_reasoning_traces_user_id` (user_id)

## `recurring_expenses` — denetlenir, workspace kapsamlı

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `user_id` | INTEGER | hayır |  | users.id | index |
| `workspace_id` | INTEGER | evet |  | workspaces.id | index |
| `name` | VARCHAR(100) | hayır |  |  |  |
| `amount` | NUMERIC(19, 4) | hayır |  |  | para |
| `account_id` | INTEGER | evet |  | accounts.id | index |
| `category` | VARCHAR(50) | evet |  |  |  |
| `day_of_month` | INTEGER | hayır |  |  |  |
| `is_active` | BOOLEAN | hayır | True |  |  |
| `last_triggered_year_month` | VARCHAR(7) | evet |  |  |  |
| `notes` | TEXT | evet |  |  |  |
| `created_at` | DATETIME | evet | fn:utcnow |  |  |

İndeks/kısıt: index `ix_recurring_expenses_account_id` (account_id); index `ix_recurring_expenses_user_id` (user_id); index `ix_recurring_expenses_workspace_id` (workspace_id)

## `recurring_incomes` — denetlenir, workspace kapsamlı

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `user_id` | INTEGER | hayır |  | users.id | index |
| `workspace_id` | INTEGER | evet |  | workspaces.id | index |
| `name` | VARCHAR(100) | hayır |  |  |  |
| `amount` | NUMERIC(19, 4) | hayır |  |  | para |
| `day_of_month` | INTEGER | hayır |  |  |  |
| `is_active` | BOOLEAN | hayır | True |  |  |
| `notes` | TEXT | evet |  |  |  |
| `created_at` | DATETIME | evet | fn:utcnow |  |  |
| `last_triggered_year_month` | VARCHAR(7) | evet |  |  |  |

İndeks/kısıt: index `ix_recurring_incomes_user_id` (user_id); index `ix_recurring_incomes_workspace_id` (workspace_id)

## `revoked_tokens` — saklama 0 gün

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `jti` | VARCHAR(64) | hayır |  |  | unique index |
| `revoked_at` | DATETIME | hayır | fn:utcnow |  |  |
| `expires_at` | DATETIME | evet |  |  |  |

İndeks/kısıt: unique index `ix_revoked_tokens_jti` (jti)

## `scheduler_runs` — saklama 90 gün

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `job_name` | VARCHAR(60) | hayır |  |  | index |
| `started_at` | DATETIME | hayır |  |  |  |
| `finished_at` | DATETIME | evet |  |  |  |
| `ok` | BOOLEAN | evet |  |  |  |
| `detail` | VARCHAR(300) | evet |  |  |  |

İndeks/kısıt: index `ix_scheduler_runs_job_name` (job_name)

## `transactions` — denetlenir, workspace kapsamlı

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `user_id` | INTEGER | hayır |  | users.id |  |
| `workspace_id` | INTEGER | evet |  | workspaces.id | index |
| `account_id` | INTEGER | evet |  | accounts.id |  |
| `transaction_type` | VARCHAR(8) | hayır |  |  |  |
| `amount` | NUMERIC(19, 4) | hayır |  |  | para |
| `category` | VARCHAR(50) | evet |  |  |  |
| `description` | TEXT | evet |  |  |  |
| `transaction_date` | DATE | hayır | fn:today |  |  |
| `is_card_expense` | BOOLEAN | hayır | False |  |  |
| `created_at` | DATETIME | evet | fn:utcnow |  |  |

İndeks/kısıt: index `ix_transactions_account_date` (account_id, transaction_date); index `ix_transactions_user_category` (user_id, category); index `ix_transactions_user_date` (user_id, transaction_date); index `ix_transactions_workspace_id` (workspace_id)

## `users`

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `name` | VARCHAR(100) | hayır |  |  |  |
| `email` | VARCHAR(255) | evet |  |  | unique index |
| `password_hash` | VARCHAR(255) | evet |  |  |  |
| `oauth_provider` | VARCHAR(20) | evet |  |  |  |
| `oauth_sub` | VARCHAR(255) | evet |  |  |  |
| `kvkk_consent_at` | DATETIME | evet |  |  |  |
| `kvkk_consent_version` | VARCHAR(20) | evet |  |  |  |
| `is_active` | BOOLEAN | hayır | True |  |  |
| `token_version` | INTEGER | hayır | 0 |  |  |
| `email_verified_at` | DATETIME | evet |  |  |  |
| `timezone` | VARCHAR(40) | evet |  |  |  |
| `currency` | VARCHAR(3) | evet |  |  |  |
| `locale` | VARCHAR(10) | evet |  |  |  |
| `onboarding_dismissed_at` | DATETIME | evet |  |  |  |
| `created_at` | DATETIME | evet | fn:utcnow |  |  |

İndeks/kısıt: unique index `ix_users_email` (email)

## `wishlist_items` — denetlenir, workspace kapsamlı

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `user_id` | INTEGER | hayır |  | users.id |  |
| `workspace_id` | INTEGER | evet |  | workspaces.id | index |
| `item` | VARCHAR(200) | hayır |  |  |  |
| `amount` | NUMERIC(14, 2) | hayır |  |  | para |
| `note` | TEXT | evet |  |  |  |
| `status` | VARCHAR(20) | hayır | 'pending' |  |  |
| `created_at` | DATETIME | evet | fn:utcnow |  |  |
| `resolved_at` | DATETIME | evet |  |  |  |

İndeks/kısıt: index `ix_wishlist_items_workspace_id` (workspace_id); index `ix_wishlist_user_status` (user_id, status)

## `workspace_memberships` — workspace kapsamlı

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `workspace_id` | INTEGER | hayır |  | workspaces.id |  |
| `user_id` | INTEGER | hayır |  | users.id |  |
| `role` | VARCHAR(6) | hayır | <WorkspaceRole.viewer: 'viewer'> |  |  |
| `invited_by` | INTEGER | evet |  | users.id (SET NULL) |  |
| `joined_at` | DATETIME | hayır | fn:utcnow |  |  |

İndeks/kısıt: index `ix_membership_user` (user_id); UniqueConstraint uq_membership_workspace_user (workspace_id, user_id)

## `workspaces`

| Sütun | Tip | Boş | Varsayılan | FK | Not |
|---|---|---|---|---|---|
| `id` | INTEGER | hayır |  |  | PK |
| `owner_user_id` | INTEGER | hayır |  | users.id | index |
| `name` | VARCHAR(100) | hayır |  |  |  |
| `is_personal` | BOOLEAN | hayır | False |  |  |
| `created_at` | DATETIME | hayır | fn:utcnow |  |  |

İndeks/kısıt: index `ix_workspaces_owner_user_id` (owner_user_id)
