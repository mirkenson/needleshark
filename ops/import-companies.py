#!/usr/bin/env python3
"""Reviewed company research import. Private input/state; never creates people/deals.

Run with the existing server environment and --server-dir pointing at the release.
POSTs are fenced by a durable journal. Unknown outcomes stop unless read-back
positively identifies the saved object. A missing object never permits blind retry.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time


def clean(value):
    text = str(value or '').strip()
    return '' if text in ('—', '-', '–') else text


def name_key(value):
    return re.sub(r'[^a-zа-яё0-9]', '', value.casefold())


def append_text(old, new):
    old, new = str(old or ''), clean(new)
    # Preserve the original bytes. Only add genuinely new complete source text.
    if not new or new.casefold() in old.casefold():
        return old
    return old + ('\n\n' if old else '') + new


def email_values(text):
    return sorted(set(re.findall(r'(?<![\w.+-])[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+', text)))


def phone_values(text):
    # Do not guess missing city codes or silently discard extensions.
    found = []
    pattern = r'(?<!\d)(?:\+7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}(?:\s*(?:доб\.?|ext\.?)\s*\d+)?(?!\d)'
    for match in re.finditer(pattern, text, re.I):
        found.append(match.group().strip())
    return list(dict.fromkeys(found))


def match_company(row, companies, domains):
    hosts = set(domains(row['sites']))
    matches = []
    for c in companies:
        fs = {f.get('field_code'): f.get('values', []) for f in c.get('custom_fields_values') or []}
        existing_hosts = {h for v in fs.get('WEB', []) + fs.get('NS_RESEARCH_SITES', []) for h in domains(v['value'])}
        if name_key(row['name']) == name_key(c['name']) or hosts & existing_hosts:
            matches.append(c)
    if len(matches) > 1:
        raise ValueError('ambiguous_company_match')
    return matches[0] if matches else None


def field_map(fields, specs):
    result = {}
    for code, name, kind in specs:
        hits = [f for f in fields if f.get('code') == code or f['name'] == name]
        if len(hits) != 1 or hits[0]['type'] != kind:
            raise ValueError('company_field_missing_or_ambiguous:' + code)
        result[code] = hits[0]
    for key, name, kind in [('PHONE', 'Телефон', 'multitext'), ('EMAIL', 'Email', 'multitext'),
                            ('WEB', 'Web', 'url'), ('CITY', 'Город', 'text')]:
        hits = [f for f in fields if f.get('code') == key or f['name'] == name]
        if len(hits) != 1 or hits[0]['type'] != kind:
            raise ValueError('company_field_missing_or_ambiguous:' + key)
        result[key] = hits[0]
    return result


def changes(row, company, mapping, domains):
    current = {f['field_id']: f['values'] for f in (company or {}).get('custom_fields_values') or []}
    result = []
    def add(code, values):
        field_id = mapping[code]['id']
        if values != current.get(field_id, []):
            result.append({'field_id': field_id, 'values': values})
    def scalar(code, value, only_empty=False):
        old = current.get(mapping[code]['id'], [])
        old_text = old[0]['value'] if old else ''
        new = old_text if only_empty and old_text else append_text(old_text, value)
        if new and new != old_text:
            add(code, [{'value': new}])
    for code, key in [('CITY', 'city'), ('NS_COMPANY_ACTIVITY', 'activity'),
                      ('NS_SPECIALIST_CONTACTS', 'specialist'), ('NS_GENERAL_CONTACTS', 'general'),
                      ('NS_SUPPLIER_CHANNEL', 'supplier'), ('NS_PRIORITY_CHANNEL', 'priority_channel'),
                      ('NS_RESEARCH_SITES', 'sites'), ('NS_COMPANY_SOURCES', 'sources')]:
        scalar(code, row[key])
    sites = domains(row['sites'])
    if sites:
        scalar('WEB', 'https://' + sites[0], only_empty=True)
    for code, texts in [('EMAIL', email_values(row['general'])), ('PHONE', phone_values(row['general']))]:
        old = current.get(mapping[code]['id'], [])
        norm = lambda v: v.casefold().strip() if code == 'EMAIL' else re.sub(r'^8(?=\d{10}$)', '7', re.sub(r'\D', '', v))
        known = {norm(str(v['value'])) for v in old}
        added = [dict(value=t, enum_code='WORK') for t in texts if norm(t) not in known]
        if added:
            add(code, old + added)
    code = 'NS_COMPANY_DIRECTIONS'
    old = current.get(mapping[code]['id'], [])
    known = {v['value'] for v in old}
    enums = {e['value']: e['id'] for e in mapping[code]['enums']}
    extra = [dict(value=v, enum_id=enums[v]) for v in row['directions'] if v not in known]
    if extra:
        add(code, old + extra)
    code = 'NS_OUTREACH_STATUS'
    if not current.get(mapping[code]['id']):
        value = 'Не уточнено' if company else 'Контакта не было'
        enum_id = next(e['id'] for e in mapping[code]['enums'] if e['value'] == value)
        add(code, [dict(value=value, enum_id=enum_id)])
    return result


class Journal:
    def __init__(self, path, fingerprint):
        self.path = Path(path)
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {'fingerprint': fingerprint, 'rows': {}}
        if self.data['fingerprint'] != fingerprint:
            raise ValueError('journal_input_mismatch')
    def save(self):
        tmp = self.path.with_suffix('.next')
        with open(tmp, 'w', encoding='utf-8') as f:
            os.chmod(tmp, 0o600)
            json.dump(self.data, f, ensure_ascii=False, indent=2)
            f.flush(); os.fsync(f.fileno())
        os.replace(tmp, self.path)
        fd = os.open(self.path.parent, os.O_RDONLY)
        try: os.fsync(fd)
        finally: os.close(fd)


def run(args):
    import fcntl
    with open(args.state + '.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return run_locked(args)


def run_locked(args):
    sys.path.insert(0, args.server_dir)
    import amo_delivery
    import customer_sync
    import company_profile as profile
    import delivery_store
    class CompanyClient(amo_delivery.Client):
        def request(self, method, path, payload=None):
            allowed = re.fullmatch(r'/api/v4/companies(?:/\d+)?(?:/notes)?', path)
            field_create = path == '/api/v4/companies/custom_fields' and method == 'POST'
            if method != 'GET' and not (method in ('POST', 'PATCH') and (allowed or field_create)):
                raise ValueError('company_only_write_guard')
            if payload is not None:
                for item in payload if isinstance(payload, list) else [payload]:
                    if '_embedded' in item:
                        raise ValueError('company_links_forbidden')
            return super().request(method, path, payload)
    raw = Path(args.input).read_bytes(); source = json.loads(raw)
    rows = source['companies']
    journal = Journal(args.state, hashlib.sha256(raw).hexdigest())
    c = CompanyClient(amo_delivery.configuration())
    account = c.request('GET', '/api/v4/account')['id']
    if account != source['account_id']:
        raise ValueError('company_account_mismatch')
    fields = list(c.list('companies/custom_fields', {}))
    desired_directions = list(dict.fromkeys(d for r in rows for d in r['directions']))
    for code, name, kind in profile.FIELD_SPECS:
        existing = [f for f in fields if f.get('code') == code or f['name'] == name]
        if existing:
            if len(existing) != 1 or existing[0]['type'] != kind:
                raise ValueError('existing_field_conflict:' + code)
            continue
        if not args.apply:
            continue
        pending_fields = journal.data.setdefault('field_started', {})
        if pending_fields.get(code):
            raise ValueError('company_field_create_unconfirmed:' + code)
        payload = dict(code=code, name=name, type=kind, sort=100 + len(fields), is_api_only=False)
        options = desired_directions if kind == 'multiselect' else profile.OUTREACH_STATUSES if kind == 'select' else []
        if options: payload['enums'] = [dict(value=v, sort=i+1) for i,v in enumerate(options)]
        pending_fields[code] = True; journal.save()
        c.request('POST', '/api/v4/companies/custom_fields', [payload])
        fields = list(c.list('companies/custom_fields', {}))
    mapping = field_map(fields, profile.FIELD_SPECS) if args.apply else None
    companies = list(c.list('companies', {'with': 'contacts,leads'}))
    totals = dict(rows=len(rows), created=0, updated=0, unchanged=0, notes=0, verified=0)
    for row in rows:
        state = journal.data['rows'].setdefault(row['key'], {})
        company = match_company(row, companies, profile.domains)
        if row.get('expected_id') and (not company or company['id'] != row['expected_id']):
            raise ValueError('reviewed_match_changed')
        if state.get('company_id'):
            if not company or company['id'] != state['company_id']:
                raise ValueError('journal_company_mismatch')
        if not args.apply:
            totals['updated' if company else 'created'] += 1
            continue
        if company:
            company = c.request('GET', '/api/v4/companies/' + str(company['id']) + '?with=contacts,leads')
            if state.get('create_started') and not state.get('company_id'):
                if (company.get('created_at', 0) < state['create_started'] or
                    company['name'] != row['name'] or changes(row, company, mapping, profile.domains)):
                    raise ValueError('company_create_reconciliation_ambiguous')
                state['created_by_import'] = True
            state['company_id'] = company['id']; journal.save()
        elif state.get('create_started'):
            raise ValueError('company_create_unconfirmed')
        delta = changes(row, company, mapping, profile.domains)
        if company is None:
            state['create_started'] = int(time.time()); journal.save()
            payload = dict(name=row['name'], custom_fields_values=delta)
            result = c.request('POST', '/api/v4/companies', [payload])
            rid = result['_embedded']['companies'][0]['id']
            state['company_id'] = rid; state['created_by_import'] = True; journal.save()
            company = c.request('GET', '/api/v4/companies/' + str(rid) + '?with=contacts,leads')
            companies.append(company); totals['created'] += 1
        elif delta:
            c.request('PATCH', '/api/v4/companies/' + str(company['id']), {'custom_fields_values': delta})
            company = c.request('GET', '/api/v4/companies/' + str(company['id']) + '?with=contacts,leads')
            totals['updated'] += 1
        else:
            totals['unchanged'] += 1
        # The exact same additive merge must now be empty, including standard channels.
        if changes(row, company, mapping, profile.domains):
            raise ValueError('company_readback_mismatch')
        if state.get('created_by_import') and (company.get('_embedded', {}).get('contacts') or company.get('_embedded', {}).get('leads')):
            raise ValueError('unexpected_links_on_imported_company')
        note = row['offer_note']
        if note:
            path = 'companies/' + str(company['id']) + '/notes'
            notes = list(c.list(path, {'filter[note_type]': 'common'}))
            matches = [n for n in notes if n.get('params', {}).get('text') == note]
            if len(matches) > 1: raise ValueError('duplicate_offer_note')
            if matches:
                state['note_id'] = matches[0]['id']
            else:
                if state.get('note_started'): raise ValueError('company_note_unconfirmed')
                state['note_started'] = True; journal.save()
                c.request('POST', '/api/v4/' + path, [dict(note_type='common', params={'text': note})])
                matches = [n for n in c.list(path, {'filter[note_type]': 'common'}) if n.get('params', {}).get('text') == note]
                if len(matches) != 1: raise ValueError('company_note_readback_mismatch')
                state['note_id'] = matches[0]['id']; totals['notes'] += 1
        # Save the full selected source and hints independently of replaceable CRM snapshots.
        with delivery_store.connection() as conn, conn.cursor() as cur:
            cur.execute('SELECT pg_advisory_xact_lock(1849202618)')
            cur.execute('''INSERT INTO companies(amo_account_id,amo_company_id,name,details,source_updated_at)
                VALUES(%s,%s,%s,%s::jsonb,%s) ON CONFLICT(amo_account_id,amo_company_id) DO UPDATE SET
                details=EXCLUDED.details,name=EXCLUDED.name,source_updated_at=EXCLUDED.source_updated_at,archived=false
                WHERE companies.source_updated_at<=EXCLUDED.source_updated_at RETURNING id''',
                (account,company['id'],company['name'],json.dumps(profile.values(company),ensure_ascii=False),company['updated_at']))
            saved = cur.fetchone()
            if not saved:
                cur.execute('SELECT id FROM companies WHERE amo_account_id=%s AND amo_company_id=%s',(account,company['id']))
                saved = cur.fetchone()
            cid = saved[0]
            profile.save_projection(cur, cid, company)
            data = dict(row, source_url=source['source_url'], amo_note_id=state.get('note_id'))
            cur.execute('UPDATE companies SET research_data=research_data || %s::jsonb WHERE id=%s',
                        (json.dumps({row['key']:data},ensure_ascii=False),cid))
            if row['offer']:
                hint = dict(direction=row['directions'],text=row['offer'],source_key=row['key'],amo_note_id=state['note_id'])
                cur.execute('''UPDATE companies SET offer_hints=offer_hints || %s::jsonb
                    WHERE id=%s AND NOT offer_hints @> %s::jsonb''',
                    (json.dumps([hint],ensure_ascii=False),cid,json.dumps([hint],ensure_ascii=False)))
        state['verified'] = True; journal.save(); totals['verified'] += 1
        if totals['verified'] % 20 == 0:
            print(json.dumps(totals), flush=True)
    print(json.dumps(totals), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--state', required=True)
    parser.add_argument('--server-dir', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    try:
        run(args)
    except Exception as error:
        # No source data, remote bodies or credentials in shared logs.
        print('company_import_stopped:' + type(error).__name__ + ':' +
              (str(error) if isinstance(error, ValueError) else getattr(error, 'code', 'private_error')), file=sys.stderr)
        raise SystemExit(1)
