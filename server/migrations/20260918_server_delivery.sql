-- Additive: historical orders/Drive links are left untouched.
CREATE TABLE IF NOT EXISTS lead_submissions (
 submission_id UUID PRIMARY KEY REFERENCES orders(submission_id),
 fingerprint TEXT NOT NULL,
 payload JSONB NOT NULL,
 ip_hash TEXT NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS lead_submissions_ip_date ON lead_submissions(ip_hash, created_at);
CREATE TABLE IF NOT EXISTS lead_files (
 submission_id UUID PRIMARY KEY REFERENCES lead_submissions(submission_id),
 name TEXT NOT NULL,
 mime_type TEXT NOT NULL CHECK (mime_type IN ('application/pdf','image/png','image/jpeg')),
 content BYTEA NOT NULL CHECK (octet_length(content) BETWEEN 1 AND 2097152)
);
CREATE TABLE IF NOT EXISTS lead_deliveries (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 submission_id UUID NOT NULL REFERENCES lead_submissions(submission_id),
 channel TEXT NOT NULL CHECK (channel = 'email'),
 recipient TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','sending','sent')),
 attempts INTEGER NOT NULL DEFAULT 0,
 retry_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 lease_until TIMESTAMPTZ,
 lease_token UUID,
 sent_at TIMESTAMPTZ,
 last_error TEXT,
 UNIQUE (submission_id, channel, recipient)
);
CREATE INDEX IF NOT EXISTS lead_deliveries_pending ON lead_deliveries(retry_at) WHERE status <> 'sent';
