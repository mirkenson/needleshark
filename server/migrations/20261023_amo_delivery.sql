-- Independent outbox for NEW submissions only. Never replay historical orders.
CREATE TABLE IF NOT EXISTS lead_amo_deliveries (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 submission_id UUID NOT NULL UNIQUE REFERENCES lead_submissions(submission_id),
 status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sending','sent')),
 attempts INTEGER NOT NULL DEFAULT 0,
 retry_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 lease_until TIMESTAMPTZ,
 lease_token UUID,
 sent_at TIMESTAMPTZ,
 last_error TEXT,
 create_started BOOLEAN NOT NULL DEFAULT false,
 amo_lead_id BIGINT CHECK (amo_lead_id > 0)
);
CREATE INDEX IF NOT EXISTS lead_amo_deliveries_pending ON lead_amo_deliveries(retry_at) WHERE status <> 'sent';
