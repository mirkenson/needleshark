"""Company-only research fields; no person identity or delivery side effects."""
import re

FIELD_SPECS = [
    ('NS_COMPANY_DIRECTIONS', 'Направления работы', 'multiselect'),
    ('NS_OUTREACH_STATUS', 'Контакт с компанией', 'select'),
    ('NS_PRIORITY_CHANNEL', 'Приоритетный канал связи', 'textarea'),
    ('NS_COMPANY_ACTIVITY', 'Деятельность компании', 'textarea'),
    ('NS_SPECIALIST_CONTACTS', 'Профильные контакты / специалисты', 'textarea'),
    ('NS_GENERAL_CONTACTS', 'Общие контакты из базы', 'textarea'),
    ('NS_SUPPLIER_CHANNEL', 'Канал для поставщиков / примечание', 'textarea'),
    ('NS_RESEARCH_SITES', 'Сайты из базы', 'textarea'),
    ('NS_COMPANY_SOURCES', 'Источники информации', 'textarea'),
]
OUTREACH_STATUSES = ['Контакта не было', 'Контакт был', 'Не уточнено']


def values(row):
    return {f.get('field_code') or f.get('field_name'): [v.get('value') for v in f.get('values', [])]
            for f in row.get('custom_fields_values') or []}


def domains(text):
    # Exact hosts only: never combine different tenants of the same parent domain.
    return sorted(set(x.lower().removeprefix('www.') for x in
                      re.findall(r'(?<![@\w-])(?:[a-zа-яё0-9-]+\.)+[a-zа-яё]{2,}', str(text), re.I)))


def projection(row):
    fs = values(row)
    def one(code):
        v = fs.get(code) or []
        return str(v[0]) if v and v[0] is not None else None
    return {
        'directions': [str(v) for v in fs.get('NS_COMPANY_DIRECTIONS', []) if v],
        'outreach_status': one('NS_OUTREACH_STATUS'), 'city': one('Город'),
        'activity': one('NS_COMPANY_ACTIVITY'),
        'websites': sorted(set(str(v) for v in fs.get('WEB', []) if v) |
                           {'https://' + h for h in domains(one('NS_RESEARCH_SITES') or '')}),
        'emails': [str(v) for v in fs.get('EMAIL', []) if v],
        'phones': [str(v) for v in fs.get('PHONE', []) if v],
        'general_contacts': one('NS_GENERAL_CONTACTS'),
        'specialist_contacts': one('NS_SPECIALIST_CONTACTS'),
        'supplier_channel': one('NS_SUPPLIER_CHANNEL'),
        'priority_channel': one('NS_PRIORITY_CHANNEL'),
        'information_sources': one('NS_COMPANY_SOURCES'),
    }


def save_projection(cur, company_id, row):
    data = projection(row)
    assignments = ','.join(key + '=%s' for key in data)
    cur.execute('UPDATE companies SET ' + assignments +
                ' WHERE id=%s AND source_updated_at<=%s',
                (*data.values(), company_id, row['updated_at']))
