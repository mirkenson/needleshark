-- Company research is separate from people, inquiries and marketing permissions.
ALTER TABLE companies
 ADD COLUMN IF NOT EXISTS directions TEXT[] NOT NULL DEFAULT '{}',
 ADD COLUMN IF NOT EXISTS outreach_status TEXT,
 ADD COLUMN IF NOT EXISTS city TEXT,
 ADD COLUMN IF NOT EXISTS activity TEXT,
 ADD COLUMN IF NOT EXISTS websites TEXT[] NOT NULL DEFAULT '{}',
 ADD COLUMN IF NOT EXISTS emails TEXT[] NOT NULL DEFAULT '{}',
 ADD COLUMN IF NOT EXISTS phones TEXT[] NOT NULL DEFAULT '{}',
 ADD COLUMN IF NOT EXISTS general_contacts TEXT,
 ADD COLUMN IF NOT EXISTS specialist_contacts TEXT,
 ADD COLUMN IF NOT EXISTS supplier_channel TEXT,
 ADD COLUMN IF NOT EXISTS priority_channel TEXT,
 ADD COLUMN IF NOT EXISTS information_sources TEXT,
 ADD COLUMN IF NOT EXISTS offer_hints JSONB NOT NULL DEFAULT '[]',
 ADD COLUMN IF NOT EXISTS research_data JSONB NOT NULL DEFAULT '{}';
CREATE INDEX IF NOT EXISTS companies_directions_idx ON companies USING GIN(directions);
CREATE INDEX IF NOT EXISTS companies_outreach_idx ON companies(outreach_status) WHERE NOT archived;
