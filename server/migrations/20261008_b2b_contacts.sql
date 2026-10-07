-- Additive snapshots for the new four-field form. Historical data stays untouched.
ALTER TABLE orders
 ADD COLUMN IF NOT EXISTS email TEXT,
 ADD COLUMN IF NOT EXISTS phone TEXT,
 ADD COLUMN IF NOT EXISTS business_direction TEXT CHECK (business_direction IN ('chehly','sumki','remni','ukrytiya-i-shtory','po-tz')),
 ADD COLUMN IF NOT EXISTS business_material TEXT CHECK (business_material IN ('oxford','canvas','spunbond','cordura','polyester','other'));
