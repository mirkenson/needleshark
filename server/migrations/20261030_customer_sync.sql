-- Additive registry: no changes to form snapshots, delivery queues or CRM writes.
CREATE TABLE IF NOT EXISTS companies (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 amo_account_id BIGINT NOT NULL, amo_company_id BIGINT NOT NULL,
 name TEXT NOT NULL, inn TEXT, kpp TEXT, details JSONB NOT NULL DEFAULT '{}',
 source_updated_at BIGINT NOT NULL, archived BOOLEAN NOT NULL DEFAULT false,
 UNIQUE(amo_account_id,amo_company_id)
);
ALTER TABLE customers
 ADD COLUMN IF NOT EXISTS company_id BIGINT REFERENCES companies(id),
 ADD COLUMN IF NOT EXISTS is_test BOOLEAN NOT NULL DEFAULT false,
 ADD COLUMN IF NOT EXISTS sync_conflict BOOLEAN NOT NULL DEFAULT false,
 ADD COLUMN IF NOT EXISTS first_touch_at TIMESTAMPTZ,
 ADD COLUMN IF NOT EXISTS first_touch_channel TEXT,
 ADD COLUMN IF NOT EXISTS first_touch_source TEXT,
 ADD COLUMN IF NOT EXISTS first_touch_source_id TEXT,
 ADD COLUMN IF NOT EXISTS first_touch_quality TEXT,
 ADD COLUMN IF NOT EXISTS first_utm_source TEXT,
 ADD COLUMN IF NOT EXISTS first_utm_medium TEXT,
 ADD COLUMN IF NOT EXISTS first_utm_campaign TEXT,
 ADD COLUMN IF NOT EXISTS first_utm_content TEXT,
 ADD COLUMN IF NOT EXISTS first_utm_term TEXT,
 ADD COLUMN IF NOT EXISTS first_source_path TEXT,
 ADD COLUMN IF NOT EXISTS first_ym_client_id TEXT;
CREATE TABLE IF NOT EXISTS customer_identifiers (
 customer_id BIGINT NOT NULL REFERENCES customers(id),
 kind TEXT NOT NULL CHECK(kind IN ('email','phone')),
 value TEXT NOT NULL, source TEXT NOT NULL, active BOOLEAN NOT NULL DEFAULT true,
 PRIMARY KEY(customer_id,kind,value)
);
CREATE INDEX IF NOT EXISTS customer_identifier_lookup ON customer_identifiers(kind,value);
CREATE TABLE IF NOT EXISTS customer_amo_links (
 amo_account_id BIGINT NOT NULL, amo_contact_id BIGINT NOT NULL,
 customer_id BIGINT NOT NULL REFERENCES customers(id), source_updated_at BIGINT NOT NULL,
 archived BOOLEAN NOT NULL DEFAULT false,
 PRIMARY KEY(amo_account_id,amo_contact_id)
);
CREATE TABLE IF NOT EXISTS customer_company_history (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 customer_id BIGINT NOT NULL REFERENCES customers(id),
 previous_company_id BIGINT REFERENCES companies(id), company_id BIGINT REFERENCES companies(id),
 changed_at TIMESTAMPTZ NOT NULL DEFAULT now(), source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS customer_touchpoints (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 customer_id BIGINT NOT NULL REFERENCES customers(id),
 occurred_at TIMESTAMPTZ NOT NULL, received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 channel TEXT NOT NULL, source TEXT NOT NULL, source_id TEXT NOT NULL, quality TEXT NOT NULL,
 utm_source TEXT, utm_medium TEXT, utm_campaign TEXT, utm_content TEXT, utm_term TEXT,
 source_path TEXT, ym_client_id TEXT,
 UNIQUE(source,source_id)
);
CREATE INDEX IF NOT EXISTS customer_touchpoints_first ON customer_touchpoints(customer_id,occurred_at,id);
CREATE TABLE IF NOT EXISTS crm_deals (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 amo_account_id BIGINT NOT NULL, amo_lead_id BIGINT NOT NULL,
 name TEXT NOT NULL, pipeline_id BIGINT NOT NULL, stage_id BIGINT NOT NULL,
 company_id BIGINT REFERENCES companies(id), order_id BIGINT REFERENCES orders(id),
 source_created_at BIGINT NOT NULL, source_updated_at BIGINT NOT NULL,
 archived BOOLEAN NOT NULL DEFAULT false,
 UNIQUE(amo_account_id,amo_lead_id)
);
CREATE TABLE IF NOT EXISTS crm_deal_contacts (
 deal_id BIGINT NOT NULL REFERENCES crm_deals(id),
 customer_id BIGINT NOT NULL REFERENCES customers(id), is_main BOOLEAN NOT NULL DEFAULT false,
 PRIMARY KEY(deal_id,customer_id)
);
CREATE TABLE IF NOT EXISTS deal_stage_log (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 deal_id BIGINT NOT NULL REFERENCES crm_deals(id),
 customer_id BIGINT REFERENCES customers(id),
 source_event_id TEXT NOT NULL,
 previous_pipeline_id BIGINT, previous_stage_id BIGINT,
 new_pipeline_id BIGINT NOT NULL, new_stage_id BIGINT NOT NULL,
 occurred_at TIMESTAMPTZ NOT NULL, received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 event_kind TEXT NOT NULL CHECK(event_kind IN ('baseline','transition','reconciliation')),
 historical BOOLEAN NOT NULL,
 UNIQUE(deal_id,source_event_id)
);
CREATE INDEX IF NOT EXISTS deal_stage_log_latest ON deal_stage_log(deal_id,occurred_at DESC,id DESC);
-- Ambiguous same-second transitions are flagged, not ordered by arrival guesses.
CREATE OR REPLACE VIEW deal_latest_stage AS
 SELECT d.id AS deal_id,d.amo_lead_id,d.pipeline_id AS confirmed_pipeline_id,
 d.stage_id AS confirmed_stage_id,l.customer_id,l.previous_stage_id,l.new_stage_id,
 l.previous_pipeline_id,l.new_pipeline_id,l.occurred_at,l.source_event_id,l.event_kind,l.historical,
 (NOT d.archived AND l.new_stage_id=d.stage_id AND l.new_pipeline_id=d.pipeline_id AND
   (SELECT count(DISTINCT (x.new_pipeline_id,x.new_stage_id)) FROM deal_stage_log x
     WHERE x.deal_id=d.id AND x.occurred_at=l.occurred_at)=1) AS ready_for_trigger,
 d.archived,d.amo_account_id
 FROM crm_deals d LEFT JOIN LATERAL
 (SELECT * FROM deal_stage_log WHERE deal_id=d.id
  ORDER BY occurred_at DESC,source_event_id DESC LIMIT 1) l ON true;
CREATE TABLE IF NOT EXISTS customer_sync_state (
 id INTEGER PRIMARY KEY CHECK(id=1), amo_account_id BIGINT NOT NULL,
 events_until BIGINT NOT NULL DEFAULT 0, activated_at BIGINT NOT NULL,
 last_success_at TIMESTAMPTZ, last_error TEXT,
 baseline_complete BOOLEAN NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS customer_sync_exclusions (
 entity_type TEXT NOT NULL CHECK(entity_type IN ('lead','contact','company')),
 amo_id BIGINT NOT NULL, reason TEXT NOT NULL,
 PRIMARY KEY(entity_type,amo_id)
);
CREATE TABLE IF NOT EXISTS customer_sync_conflicts (
 object_key TEXT PRIMARY KEY, reason TEXT NOT NULL,
 candidate_ids BIGINT[] NOT NULL DEFAULT '{}',
 first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(), last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 resolved_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS marketing_permissions (
 customer_id BIGINT NOT NULL REFERENCES customers(id), email TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'unknown' CHECK(status IN ('unknown','allowed','withdrawn')),
 evidence TEXT, updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 PRIMARY KEY(customer_id,email), CHECK(status<>'allowed' OR length(evidence)>0)
);
CREATE TABLE IF NOT EXISTS unisender_contact_sync (
 email TEXT PRIMARY KEY, customer_id BIGINT NOT NULL REFERENCES customers(id),
 payload_hash TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','accepted','uncertain','blocked')),
 attempts INTEGER NOT NULL DEFAULT 0, retry_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 last_error TEXT, synced_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS crm_stages (
 amo_account_id BIGINT NOT NULL,pipeline_id BIGINT NOT NULL,stage_id BIGINT NOT NULL,
 pipeline_name TEXT NOT NULL,stage_name TEXT NOT NULL,
 PRIMARY KEY(amo_account_id,pipeline_id,stage_id)
);
CREATE TABLE IF NOT EXISTS crm_unresolved_events (
 source_event_id TEXT PRIMARY KEY, event_data JSONB NOT NULL,
 reason TEXT NOT NULL, received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
