-- Independent text-only outbox. Existing mail monitoring/file retention stay unchanged.
-- Deliberately no backfill: only new, committed submissions create LOOP jobs.
CREATE TABLE IF NOT EXISTS lead_loop_deliveries (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 submission_id UUID NOT NULL UNIQUE REFERENCES lead_submissions(submission_id),
 status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sending','sent')),
 attempts INTEGER NOT NULL DEFAULT 0,
 retry_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 lease_until TIMESTAMPTZ,
 lease_token UUID,
 sent_at TIMESTAMPTZ,
 last_error TEXT
);
CREATE INDEX IF NOT EXISTS lead_loop_deliveries_pending ON lead_loop_deliveries(retry_at) WHERE status <> 'sent';
