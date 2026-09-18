CREATE TABLE IF NOT EXISTS customers (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 name TEXT NOT NULL,
 contact TEXT NOT NULL,
 contact_key TEXT NOT NULL UNIQUE,
 first_inquiry_at TIMESTAMPTZ NOT NULL,
 last_inquiry_at TIMESTAMPTZ NOT NULL,
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 notes TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS orders (
 id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 submission_id UUID NOT NULL UNIQUE,
 customer_id BIGINT NOT NULL REFERENCES customers(id),
 created_at TIMESTAMPTZ NOT NULL,
 customer_name TEXT NOT NULL,
 contact TEXT NOT NULL,
 description TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'new',
 attachment_name TEXT,
 consent BOOLEAN NOT NULL,
 consent_documents JSONB NOT NULL DEFAULT '[]',
 notes TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS orders_customer_date ON orders(customer_id,created_at DESC);
CREATE INDEX IF NOT EXISTS orders_date ON orders(created_at DESC);

-- Nullable catalogue context keeps earlier homepage requests compatible.
ALTER TABLE orders
 ADD COLUMN IF NOT EXISTS product_slug TEXT,
 ADD COLUMN IF NOT EXISTS product_name TEXT,
 ADD COLUMN IF NOT EXISTS product_size TEXT,
 ADD COLUMN IF NOT EXISTS inquiry_type TEXT,
 ADD COLUMN IF NOT EXISTS quantity INTEGER CHECK (quantity BETWEEN 1 AND 1000000),
 ADD COLUMN IF NOT EXISTS source_path TEXT;

ALTER TABLE orders
 ADD COLUMN IF NOT EXISTS business_intent TEXT CHECK (business_intent IN ('ready', 'custom', 'materials')),
 ADD COLUMN IF NOT EXISTS business_company TEXT,
 ADD COLUMN IF NOT EXISTS attachment_url TEXT;

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
