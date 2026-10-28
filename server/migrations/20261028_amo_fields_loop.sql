ALTER TABLE lead_amo_deliveries ADD COLUMN IF NOT EXISTS note_started BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE lead_amo_deliveries ADD COLUMN IF NOT EXISTS amo_note_id BIGINT;
CREATE TABLE IF NOT EXISTS amo_loop_cursor (id INTEGER PRIMARY KEY CHECK(id=1), scanned_until BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS amo_loop_notifications (
 lead_id BIGINT PRIMARY KEY CHECK(lead_id>0),
 title TEXT NOT NULL,
 created_at BIGINT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','sending','sent','uncertain')),
 attempts INTEGER NOT NULL DEFAULT 0,
 retry_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 sent_at TIMESTAMPTZ,
 last_error TEXT
);
