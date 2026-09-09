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
