-- Optional attribution snapshot. Do not backfill identifiers for historical leads.
ALTER TABLE orders ADD COLUMN IF NOT EXISTS ym_client_id TEXT
 CHECK (ym_client_id ~ '^[0-9]{1,32}$');
