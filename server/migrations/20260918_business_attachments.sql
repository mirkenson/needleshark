-- Additive migration; old rows and existing catalogue submissions stay intact.
BEGIN;
ALTER TABLE orders
 ADD COLUMN IF NOT EXISTS business_intent TEXT CHECK (business_intent IN ('ready', 'custom', 'materials')),
 ADD COLUMN IF NOT EXISTS business_company TEXT,
 ADD COLUMN IF NOT EXISTS attachment_url TEXT;
COMMIT;
