-- Optional campaign snapshots. Historical orders remain NULL; no URL is stored.
ALTER TABLE orders
 ADD COLUMN IF NOT EXISTS utm_source TEXT CHECK (length(utm_source) <= 500),
 ADD COLUMN IF NOT EXISTS utm_medium TEXT CHECK (length(utm_medium) <= 500),
 ADD COLUMN IF NOT EXISTS utm_campaign TEXT CHECK (length(utm_campaign) <= 500),
 ADD COLUMN IF NOT EXISTS utm_content TEXT CHECK (length(utm_content) <= 500),
 ADD COLUMN IF NOT EXISTS utm_term TEXT CHECK (length(utm_term) <= 500);
