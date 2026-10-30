-- One-time owner-authorized cleanup, NOT a recurring retention job.
-- First restore a private pg_dump into an isolated database and run this there.
-- Run with psql -X -v ON_ERROR_STOP=1. No secrets/customer data in stdout.
-- Exact allowlist verified 2026-10-30. A rerun intentionally fails closed.
BEGIN;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '60s';
LOCK TABLE customers, orders, lead_submissions, lead_files, lead_deliveries,
    lead_loop_deliveries, lead_amo_deliveries IN ACCESS EXCLUSIVE MODE;

CREATE TEMP TABLE qa_targets ON COMMIT DROP AS
SELECT id, customer_id, submission_id FROM orders WHERE id IN
 (1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,22,25,28,29,31,32,33,34,36);
CREATE TEMP TABLE qa_customers ON COMMIT DROP AS
SELECT DISTINCT customer_id AS id FROM qa_targets;
DO $$
BEGIN
 IF (SELECT count(*) FROM qa_targets) <> 28 OR
    (SELECT count(*) FROM qa_customers) <> 20 THEN
   RAISE EXCEPTION 'Reviewed target count changed';
 END IF;
 IF EXISTS (SELECT 1 FROM orders o JOIN qa_targets q USING(id)
    WHERE NOT ((o.id=11 AND lower(btrim(o.description))='тест') OR
      (o.customer_name ~* '(тест|test|qa)' AND
       o.description ~* '(тест|test|qa|проверка|синтетическ)'))) THEN
   RAISE EXCEPTION 'Reviewed test evidence changed';
 END IF;
 IF EXISTS (SELECT 1 FROM orders WHERE customer_id IN (SELECT id FROM qa_customers)
    AND id NOT IN (SELECT id FROM qa_targets)) THEN
   RAISE EXCEPTION 'A test customer has an unreviewed order; preserve and review';
 END IF;
 IF EXISTS (SELECT 1 FROM lead_deliveries WHERE status='sending'
    AND submission_id IN (SELECT submission_id FROM qa_targets)) OR
    EXISTS (SELECT 1 FROM lead_loop_deliveries WHERE status='sending'
    AND submission_id IN (SELECT submission_id FROM qa_targets)) OR
    EXISTS (SELECT 1 FROM lead_amo_deliveries WHERE status='sending'
    AND submission_id IN (SELECT submission_id FROM qa_targets)) THEN
   RAISE EXCEPTION 'A target is in flight; do not delete';
 END IF;
END $$;

-- Compare every remaining business row, including payloads/files/queue states.
-- Temporary row copies remain inside this transaction, never in public reports.
CREATE TEMP TABLE kept_rows(table_name text, row_data jsonb) ON COMMIT DROP;
INSERT INTO kept_rows SELECT 'customers',to_jsonb(t) FROM customers t WHERE id NOT IN (SELECT id FROM qa_customers);
INSERT INTO kept_rows SELECT 'orders',to_jsonb(t) FROM orders t WHERE id NOT IN (SELECT id FROM qa_targets);
INSERT INTO kept_rows SELECT 'lead_submissions',to_jsonb(t) FROM lead_submissions t WHERE submission_id NOT IN (SELECT submission_id FROM qa_targets);
INSERT INTO kept_rows SELECT 'lead_files',to_jsonb(t) FROM lead_files t WHERE submission_id NOT IN (SELECT submission_id FROM qa_targets);
INSERT INTO kept_rows SELECT 'lead_deliveries',to_jsonb(t) FROM lead_deliveries t WHERE submission_id NOT IN (SELECT submission_id FROM qa_targets);
INSERT INTO kept_rows SELECT 'lead_loop_deliveries',to_jsonb(t) FROM lead_loop_deliveries t WHERE submission_id NOT IN (SELECT submission_id FROM qa_targets);
INSERT INTO kept_rows SELECT 'lead_amo_deliveries',to_jsonb(t) FROM lead_amo_deliveries t WHERE submission_id NOT IN (SELECT submission_id FROM qa_targets);

DELETE FROM lead_deliveries WHERE submission_id IN (SELECT submission_id FROM qa_targets);
DELETE FROM lead_loop_deliveries WHERE submission_id IN (SELECT submission_id FROM qa_targets);
DELETE FROM lead_amo_deliveries WHERE submission_id IN (SELECT submission_id FROM qa_targets);
DELETE FROM lead_files WHERE submission_id IN (SELECT submission_id FROM qa_targets);
DELETE FROM lead_submissions WHERE submission_id IN (SELECT submission_id FROM qa_targets);
DELETE FROM orders WHERE id IN (SELECT id FROM qa_targets);
DELETE FROM customers WHERE id IN (SELECT id FROM qa_customers)
 AND NOT EXISTS (SELECT 1 FROM orders WHERE customer_id=customers.id);

CREATE TEMP TABLE kept_after(table_name text, row_data jsonb) ON COMMIT DROP;
INSERT INTO kept_after SELECT 'customers',to_jsonb(t) FROM customers t;
INSERT INTO kept_after SELECT 'orders',to_jsonb(t) FROM orders t;
INSERT INTO kept_after SELECT 'lead_submissions',to_jsonb(t) FROM lead_submissions t;
INSERT INTO kept_after SELECT 'lead_files',to_jsonb(t) FROM lead_files t;
INSERT INTO kept_after SELECT 'lead_deliveries',to_jsonb(t) FROM lead_deliveries t;
INSERT INTO kept_after SELECT 'lead_loop_deliveries',to_jsonb(t) FROM lead_loop_deliveries t;
INSERT INTO kept_after SELECT 'lead_amo_deliveries',to_jsonb(t) FROM lead_amo_deliveries t;
DO $$
BEGIN
 IF EXISTS ((TABLE kept_rows EXCEPT ALL TABLE kept_after)
    UNION ALL (TABLE kept_after EXCEPT ALL TABLE kept_rows)) THEN
   RAISE EXCEPTION 'Non-target rows changed; rollback';
 END IF;
END $$;
SELECT 'verified_unchanged_non_target_rows', count(*) FROM kept_after;
SELECT 'remaining_customers',count(*) FROM customers;
SELECT 'remaining_orders',count(*) FROM orders;
COMMIT;
-- No sequence reset; no CRM deletion; no environment/schema/runtime change.
