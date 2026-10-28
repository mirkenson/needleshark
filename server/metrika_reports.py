"""Read-only Metrika digests; private durable state, no customer data or Direct API."""
import argparse
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import fcntl
import json
import math
import os
import re
from pathlib import Path
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

from loop_delivery import NoRedirect, send_payload

MSK = ZoneInfo('Europe/Moscow')
COUNTER = 112428810
GOAL = 611920414
QUALIFIED_GOAL = 674189833
CONVERSION_METRICS = ['ym:s:visits', f'ym:s:goal{GOAL}reaches',
                      f'ym:s:goal{QUALIFIED_GOAL}reaches']
DETAILS = [('Каналы', 'ym:s:lastTrafficSource'),
           ('UTM-кампании', 'ym:s:lastUTMCampaign'),
           ('Кампании Директа', 'ym:s:lastDirectClickOrder'),
           ('Объявления Директа', 'ym:s:lastDirectClickBanner'),
           ('Размещение Директа', 'ym:s:lastDirectPlatformType'),
           ('Объявления / креативы (UTM)', 'ym:s:lastUTMContent'),
           ('Поисковые запросы Директа', 'ym:s:lastDirectSearchPhrase'),
           ('Поисковые запросы из поиска', 'ym:s:lastSearchPhrase')]
API = 'https://api-metrika.yandex.net/stat/v1/data'
# Current-visit attribution excludes explicitly marked QA without inheriting an older source.
FILTERS = ("ym:s:isRobot=='No' AND NOT(ym:s:lastUTMSource=.('qa','release_check','metrika_check'))"
           " AND NOT(ym:s:lastUTMMedium=.('qa','test'))")
METRICS = ['ym:s:users', 'ym:s:visits', 'ym:s:pageviews', 'ym:s:bounceRate',
           'ym:s:pageDepth', 'ym:s:avgVisitDurationSeconds',
           f'ym:s:goal{GOAL}reaches', f'ym:s:goal{GOAL}visits',
           'ym:s:goal611920074visits', 'ym:s:goal611920219visits',
           'ym:s:goal611919492visits', 'ym:s:goal611918849visits']
KEYS = ['users', 'visits', 'views', 'bounce', 'depth', 'duration',
        'leads', 'lead_visits', 'starts', 'attempts', 'contacts', 'blog_cta']
SOURCES = {'organic': 'Поиск', 'ad': 'Реклама', 'direct': 'Прямые',
           'referral': 'Ссылки с сайтов', 'social': 'Соцсети', 'messenger': 'Мессенджеры',
           'email': 'Почта', 'internal': 'Внутренние', 'saved': 'Сохранённые страницы',
           'recommend': 'Рекомендации'}
# Earlier data on the current counter are incomplete after the domain switch.
RELIABLE_FROM = date(2026, 9, 14)


class ReportError(Exception):
    """Only a fixed neutral error code may leave the reporter."""


@dataclass(frozen=True)
class Period:
    kind: str
    start: date
    end: date
    previous_start: date
    previous_end: date

    @property
    def key(self):
        return f'{self.kind}:{self.start}:{self.end}'


def period_for(kind, run_day):
    if kind == 'daily':
        end = run_day - timedelta(days=1)
        return Period(kind, end, end, end - timedelta(days=7), end - timedelta(days=7))
    if kind == 'weekly':
        end = run_day - timedelta(days=run_day.weekday() + 1)
        return Period(kind, end - timedelta(days=6), end,
                      end - timedelta(days=13), end - timedelta(days=7))
    if kind == 'monthly':
        end = run_day.replace(day=1) - timedelta(days=1)
        start = end.replace(day=1)
        previous_end = start - timedelta(days=1)
        return Period(kind, start, end, previous_end.replace(day=1), previous_end)
    raise ValueError('Unknown report kind')


def due_periods(now, enabled_at):
    now = now.astimezone(MSK)
    latest_day = now.date() if now.hour >= 10 else now.date() - timedelta(days=1)
    candidates = [('daily', latest_day),
                  ('weekly', latest_day - timedelta(days=latest_day.weekday())),
                  ('monthly', latest_day.replace(day=1))]
    return [period_for(kind, day) for kind, day in candidates
            if datetime.combine(day, time(10), MSK) >= enabled_at]


def number(value, digits=0):
    return f'{value:,.{digits}f}'.replace(',', ' ').replace('.', ',')


def change(current, previous):
    if previous == 0:
        return 'без изменений' if current == 0 else f'было 0; +{number(current)}'
    return f'{(current / previous - 1) * 100:+.1f}%'.replace('.', ',')


def safe_number(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
        raise ReportError('metrika_invalid_data')
    return value


class Metrika:
    def __init__(self, token):
        if not token or any(c.isspace() for c in token):
            raise ReportError('metrika_token_missing')
        self.token = token
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()))

    def query(self, start, end, metrics, dimension=None):
        params = dict(ids=COUNTER, date1=str(start), date2=str(end), metrics=','.join(metrics),
                      filters=FILTERS, accuracy='full', timezone='+03:00', lang='ru',
                      limit=10000, include_undefined='true')
        if dimension:
            params.update(dimensions=dimension, sort='-ym:s:visits')
        request = urllib.request.Request(API + '?' + urllib.parse.urlencode(params),
            headers={'Authorization': 'OAuth ' + self.token, 'User-Agent': 'NeedleShark-Reports/1.0'})
        try:
            with self.opener.open(request, timeout=30) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
                if len(raw) > 4 * 1024 * 1024:
                    raise ReportError('metrika_response_too_large')
                result = json.loads(raw)
        except urllib.error.HTTPError as error:
            code = error.code
            error.close()
            raise ReportError(f'metrika_http_{code}') from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ReportError('metrika_network_error') from None
        except (ValueError, UnicodeError):
            raise ReportError('metrika_invalid_json') from None
        validate_result(result, metrics, dimension)
        # Do not send a report while the declared lag still overlaps its final day.
        cutoff = datetime.combine(end + timedelta(days=1), time(), MSK)
        if datetime.now(MSK) - timedelta(seconds=result['data_lag']) < cutoff:
            raise ReportError('metrika_data_not_ready')
        return result


def validate_result(result, metrics, dimension=None):
    if not isinstance(result, dict) or result.get('sampled') is not False:
        raise ReportError('metrika_incomplete_or_sampled')
    totals = result.get('totals')
    if not isinstance(totals, list) or len(totals) != len(metrics):
        raise ReportError('metrika_missing_totals')
    for value in totals:
        safe_number(value)
    safe_number(result.get('data_lag'))
    rows = result.get('data')
    if not isinstance(rows, list) or (dimension and result.get('total_rows') != len(rows)):
        raise ReportError('metrika_incomplete_rows')
    for row in rows:
        if not isinstance(row, dict) or len(row.get('metrics', [])) != len(metrics):
            raise ReportError('metrika_invalid_rows')
        for value in row['metrics']:
            safe_number(value)
        if dimension and (not isinstance(row.get('dimensions'), list) or len(row['dimensions']) != 1):
            raise ReportError('metrika_invalid_dimensions')


def collect(client, period):
    current = client.query(period.start, period.end, METRICS)
    previous = client.query(period.previous_start, period.previous_end, METRICS)
    sources = client.query(period.start, period.end, ['ym:s:visits'], 'ym:s:lastTrafficSource')
    pages = client.query(period.start, period.end, ['ym:s:visits'], 'ym:s:startURLPath')
    result = {'current': dict(zip(KEYS, current['totals'])),
            'previous': dict(zip(KEYS, previous['totals'])), 'sources': sources['data'],
            'pages': pages['data'], 'details_limited': bool(pages.get('contains_sensitive_data')),
            'lag': max(x['data_lag'] for x in (current, previous, sources, pages))}
    if period.kind in ('daily', 'weekly'):
        result['conversions'] = collect_conversions(client, period)
    return result


def collect_conversions(client, period):
    # Independent aggregated slices, never join their rows into invented visitor stories.
    result = {'details': [], 'errors': []}
    try:
        summary = client.query(period.start, period.end, CONVERSION_METRICS)
        result['totals'] = summary['totals']
        result['lag'] = summary['data_lag']
    except ReportError:
        result['errors'].append('summary')
        return result
    if not any(summary['totals'][1:]):
        return result
    for label, dimension in DETAILS:
        try:
            response = client.query(period.start, period.end, CONVERSION_METRICS, dimension)
            rows = [row for row in response['data'] if any(row['metrics'][1:])]
            rows.sort(key=lambda row: (row['metrics'][2], row['metrics'][1]), reverse=True)
            result['details'].append({'label': label, 'dimension': dimension, 'rows': rows,
                                      'limited': bool(response.get('contains_sensitive_data'))})
            result['lag'] = max(result['lag'], response['data_lag'])
        except ReportError:
            result['errors'].append(label)
    return result



def fmt_dates(start, end):
    return start.strftime('%d.%m.%Y') if start == end else f'{start:%d.%m.%Y}–{end:%d.%m.%Y}'


def render(period, data, known_pages, *, preview=False):
    if period.kind in ('daily', 'weekly'):
        return render_digest(period, data, known_pages, preview=preview)
    current, previous = data['current'], data['previous']
    title = {'daily': 'за день', 'weekly': 'за неделю', 'monthly': 'за месяц'}[period.kind]
    prefix = 'ПРОВЕРКА ФОРМАТА · ' if preview else ''
    comparable = period.previous_start >= RELIABLE_FROM
    def delta(key):
        return change(current[key], previous[key]) if comparable else 'сравнение неполное'
    lines = [f'**{prefix}Needle Shark · Метрика {title}**',
             fmt_dates(period.start, period.end) + ' · МСК',
             f'Сравнение: {fmt_dates(period.previous_start, period.previous_end)}', '',
             f'Посетители: **{number(current["users"])}** ({delta("users")})',
             f'Визиты: **{number(current["visits"])}** ({delta("visits")})',
             f'Просмотры: **{number(current["views"])}** ({delta("views")})']
    if period.kind == 'monthly':
        days = (period.end - period.start).days + 1
        old_days = (period.previous_end - period.previous_start).days + 1
        daily = current['visits'] / days
        old_daily = previous['visits'] / old_days
        suffix = change(daily, old_daily) if comparable else 'сравнение неполное'
        lines += [f'Визитов в день: **{number(daily, 1)}** ({suffix}); периоды {days} и {old_days} дн.']
    rate = current['lead_visits'] / current['visits'] * 100 if current['visits'] else None
    old_rate = previous['lead_visits'] / previous['visits'] * 100 if previous['visits'] else None
    rate_text = '— (нет визитов)' if rate is None else number(rate, 2) + '%'
    if comparable and rate is not None and old_rate is not None:
        rate_text += ' (' + f'{rate - old_rate:+.2f}'.replace('.', ',') + ' п. п.)'
    lines += ['', f'Цель «Заявка сохранена»: **{number(current["leads"])}** достижений ({delta("leads")})',
              f'Визиты с заявкой: {number(current["lead_visits"])} · конверсия: {rate_text}',
              f'Начало формы: {number(current["starts"])} · попытка отправки: {number(current["attempts"])} (визиты)']
    if period.kind != 'daily':
        bounce = number(current['bounce'], 1) + '%' if current['visits'] else '—'
        duration = number(current['duration']) + ' с' if current['visits'] else '—'
        lines += [f'Клики по контактам: {number(current["contacts"])} · CTA блога: {number(current["blog_cta"])} (визиты)',
                  f'Отказы: {bounce} · среднее время: {duration}']
    grouped = {}
    for row in data['sources']:
        dim = row['dimensions'][0] or {}
        label = SOURCES.get(dim.get('id'), 'Прочие / не определено')
        grouped[label] = grouped.get(label, 0) + row['metrics'][0]
    source_text = '; '.join(f'{label} — {number(value)}' for label, value in
                           sorted(grouped.items(), key=lambda x: -x[1]))
    lines += ['', '**Источники визитов:** ' + (source_text or 'нет данных')]
    top = []
    for row in data['pages']:
        path = (row['dimensions'][0] or {}).get('name')
        if path in known_pages:
            top.append((path, row['metrics'][0]))
    if top:
        lines += ['**Страницы входа:** ' + '; '.join(
            f'[{path}](https://needle-shark.ru{path}) — {number(value)}' for path, value in top[:3])]
    elif current['visits']:
        lines += ['Страницы входа: подробности недоступны для этой выборки.']
    lines += ['', '**Наблюдение:** ' + observation(current, previous, comparable)]
    lines += ['', 'Источник: Метрика 112428810; атрибуция — последний переход. '
              'Роботы и помеченные QA-визиты исключены; непомеченные проверки могут остаться.',
              'Достижения цели — события сохранения формы, не сверка с БД и не оплаченные заказы.']
    if not comparable:
        lines += ['⚠️ Сравнение неполное: приём данных нового домена исправлен 13.09.2026. '
                  f'В предыдущем периоде учтено: {number(previous["users"])} посетителей, '
                  f'{number(previous["visits"])} визитов, {number(previous["leads"])} достижений цели. '
                  'Процент роста не оцениваем.']
    if data.get('details_limited'):
        lines += ['Метрика может скрывать часть детализации при небольшой выборке.']
    lines += ['Данные могут уточняться при обработке поздних визитов. '
              f'Задержка API на момент выгрузки: {number(data["lag"] / 60)} мин.',
              f'[Открыть Метрику](https://metrika.yandex.ru/dashboard?id={COUNTER})',
              f'Отчёт: `{period.key}`']
    return '\n'.join(lines)


def safe_label(value):
    if value is None or value == '':
        return 'не определено'
    text = ' '.join(str(value).split())
    # Report labels may be visitor-controlled; no mentions, links or contact details.
    text = re.sub(r'[^\s@]+@[^\s@]+', '[контакт скрыт]', text)
    text = re.sub(r'(?<!\w)\+?\d[\d ()-]{8,}\d(?!\w)', '[номер скрыт]', text)
    text = text.replace('@', '＠').replace('<', '‹').replace('>', '›')
    text = re.sub(r'https?://\S+', '[ссылка скрыта]', text)
    text = re.sub(r'([\\`*_{}\[\]()!|~])', r'\\\1', text)
    return text[:180]


def render_digest(period, data, known_pages, *, preview=False):
    current, previous = data['current'], data['previous']
    comparable = period.previous_start >= RELIABLE_FROM
    title = 'день' if period.kind == 'daily' else 'неделю'
    prefix = 'ПРОВЕРКА ФОРМАТА · ' if preview else ''
    def comparison(key):
        if not comparable:
            return 'сравнение неполное'
        # Small bases are clearer as absolute counts, not four-digit percentages.
        suffix = f'; {change(current[key], previous[key])}' if previous[key] >= 30 else ''
        return f'было {number(previous[key])}{suffix}'
    rate = (number(current['lead_visits'] / current['visits'] * 100, 2) + '%'
            if current['visits'] else '—, нет визитов')
    conv = data.get('conversions', {})
    totals = conv.get('totals')
    qualified = number(totals[2]) if totals is not None else 'данные недоступны'
    lines = [f'📊 **{prefix}Needle Shark · итоги за {title}**',
             fmt_dates(period.start, period.end) + ' · МСК',
             f'Сравнение: {fmt_dates(period.previous_start, period.previous_end)}', '',
             '🎯 **Заявки и конверсии**',
             f'- Сохранения формы в Метрике: **{number(current["leads"])}** ({comparison("leads")})',
             f'- CRM: целевая заявка — **{qualified}** достижений',
             f'- Визиты с сохранением формы: **{number(current["lead_visits"])}** · конверсия: **{rate}**',
             f'- Начали форму: {number(current["starts"])} · попытались отправить: {number(current["attempts"])} · кликнули по контактам: {number(current["contacts"])} (визиты)',
             'Форма и CRM могут учитывать одну заявку; эти числа не складываем.', '',
             '👥 **Посещаемость**',
             f'- Визиты: **{number(current["visits"])}** ({comparison("visits")})',
             f'- Посетители: **{number(current["users"])}** ({comparison("users")}) · просмотры: **{number(current["views"])}**']
    if period.kind == 'weekly':
        bounce = number(current['bounce'], 1) + '%' if current['visits'] else '—'
        duration = number(current['duration']) + ' с' if current['visits'] else '—'
        lines += [f'- Отказы: {bounce} · среднее время: {duration}',
                  f'- Переходы из CTA блога: {number(current["blog_cta"])} (визиты)']
    lines += ['', '📣 **Источники визитов**']
    grouped = {}
    for row in data['sources']:
        label = SOURCES.get((row['dimensions'][0] or {}).get('id'), 'Прочие / не определено')
        grouped[label] = grouped.get(label, 0) + row['metrics'][0]
    lines += [f'- {label}: **{number(value)}**' for label, value in sorted(grouped.items(), key=lambda x: -x[1])]
    if not grouped:
        lines += ['- Нет визитов в выбранном сегменте.']
    lines += ['', '🧭 **Источники конверсий**']
    if totals is None:
        lines += ['Подробности сейчас недоступны; это не означает отсутствие конверсий.']
    elif not any(totals[1:]):
        lines += ['Метрика пока не зафиксировала конверсий формы и целевой CRM-заявки за период.']
    else:
        lines += ['Отдельные разрезы: «форма / CRM» — достижения целей, не число разных клиентов.']
        for detail in conv.get('details', []):
            lines += [f'**{detail["label"]}**']
            rows = detail['rows']
            for row in rows[:3 if period.kind == 'daily' else 5]:
                dim = row['dimensions'][0] or {}
                label = (SOURCES.get(dim.get('id'), 'Прочие / не определено')
                         if detail['dimension'] == 'ym:s:lastTrafficSource' else safe_label(dim.get('name')))
                identifier = dim.get('direct_id', '')
                if re.fullmatch(r'[NM]-[0-9]{1,24}', identifier):
                    label += f' ({identifier})'
                lines += [f'- {label} — форма: **{number(row["metrics"][1])}**, CRM: **{number(row["metrics"][2])}**']
            cap = 3 if period.kind == 'daily' else 5
            if len(rows) > cap:
                lines += [f'- Ещё строк: {len(rows) - cap}; полный разрез — в Метрике.']
            if not rows:
                lines += ['- Детализация недоступна для этой выборки.']
            elif detail['limited']:
                lines += ['Часть детализации ограничена Метрикой.']
        lines += ['Разрезы не связываются между собой или с конкретной сделкой. Поисковый запрос не подменяется UTM-ключом или автотаргетингом.']
    if conv.get('errors'):
        lines += ['⚠️ Часть данных о конверсиях не получена; основной отчёт сохранён.']
    top = [(row['dimensions'][0].get('name'), row['metrics'][0]) for row in data['pages']
           if row['dimensions'][0] and row['dimensions'][0].get('name') in known_pages]
    if top:
        lines += ['', '📄 **Страницы входа**']
        lines += [f'- [{path}](https://needle-shark.ru{path}) — {number(value)}' for path, value in top[:3]]
    elif current['visits']:
        lines += ['', '📄 Страницы входа: подробности недоступны.']
    if current['visits'] >= 30 and not current['starts'] and not current['leads']:
        note = 'Начала формы не зафиксированы. Стоит сопоставить кампании, страницы входа и клики по контактам; это не доказательство неисправности формы.'
    elif current['leads']:
        note = 'Есть сохранения формы. Источники выше помогут оценить привлечение; качество и результат обращения нужно смотреть в CRM.'
    else:
        note = observation(current, previous, comparable)
    lines += ['', '💡 **На что обратить внимание**', note, '',
              'Метрика 112428810 · последний переход · без роботов и помеченных QA-визитов.',
              'Цели не заменяют сверку с БД/CRM и не означают оплату. CRM-данные могут дополнять прошлые периоды; это не реестр сделок, созданных за день.']
    lag = max(data['lag'], conv.get('lag', 0))
    if lag:
        lines += [f'⏳ Задержка API: {number(lag / 60)} мин. Данные могут уточняться.']
    if not comparable:
        lines += ['⚠️ Предыдущий период содержит неполные данные нового домена; проценты не оцениваем.']
    lines += [f'[Открыть Метрику](https://metrika.yandex.ru/dashboard?id={COUNTER}) · `{period.key}`']
    return '\n'.join(lines)


def observation(current, previous, comparable):
    if not current['visits']:
        return 'За период нет визитов в выбранном сегменте. По одной сводке причину определить нельзя.'
    if current['visits'] < 30:
        return 'Мало данных для устойчивых выводов. Оцениваем накопленную неделю и месяц.'
    if current['attempts'] and not current['lead_visits']:
        return 'Есть визиты с попыткой отправки, но нет визитов с целью сохранения. Стоит проверить форму и учёт цели; это не доказательство ошибки.'
    if comparable and previous['visits'] >= 30:
        return 'Изменение числа визитов к сопоставляемому периоду: ' + change(current['visits'], previous['visits']) + '. Причины требуют проверки источников и страниц.'
    return 'Данных для устойчивой оценки динамики пока недостаточно.'


def write_state(path, state):
    temp = path.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8') as handle:
        os.chmod(temp, 0o600)
        json.dump(state, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def dispatch(state, path, now, build, send):
    failures = []
    enabled_at = datetime.fromisoformat(state['enabled_at'])
    for period in due_periods(now, enabled_at):
        if period.key in state['sent']:
            continue
        try:
            text = build(period)
            send({'text': text, 'skip_slack_parsing': True})
        except ReportError as error:
            failures.append(str(error))
            continue
        except Exception:
            failures.append('loop_unconfirmed')
            continue
        state['sent'][period.key] = now.isoformat()
        write_state(path, state)
    if failures:
        raise ReportError(','.join(sorted(set(failures))))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['init', 'check', 'preview', 'run'])
    parser.add_argument('--kind', choices=['daily', 'weekly', 'monthly'], default='daily')
    parser.add_argument('--date', type=date.fromisoformat)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--state-dir', type=Path, default=Path('/var/lib/needle-metrika'))
    args = parser.parse_args()
    os.umask(0o077)
    now = datetime.now(MSK)
    if args.mode == 'init':
        args.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = args.state_dir / 'state.json'
        with (args.state_dir / 'lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if not path.exists():
                write_state(path, {'enabled_at': now.isoformat(), 'sent': {}})
        print('Reporter initialized; no reports sent')
        return
    client = Metrika(os.environ.get('METRIKA_TOKEN', ''))
    known_pages = set(json.loads(Path(__file__).with_name('metrika_pages.json').read_text()))
    def build(period):
        return render(period, collect(client, period), known_pages)
    if args.mode in ('check', 'preview'):
        period = period_for(args.kind, args.date or now.date())
        text = build(period)
        if args.mode == 'preview':
            if not args.output:
                raise ReportError('private_output_path_required')
            with args.output.open('w', encoding='utf-8') as handle:
                os.chmod(args.output, 0o600)
                handle.write(text + '\n')
        print('Metrika report validated; no messages sent')
        return
    path = args.state_dir / 'state.json'
    with (args.state_dir / 'lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        state = json.loads(path.read_text())
        dispatch(state, path, now, build,
                 lambda payload: send_payload(payload, os.environ.get('LOOP_LEADS_WEBHOOK_URL')))
    print('Report schedule checked')


if __name__ == '__main__':
    try:
        main()
    except ReportError as error:
        print('Report unavailable: ' + str(error), file=sys.stderr)
        sys.exit(1)
    except Exception:
        print('Report unavailable: internal_error', file=sys.stderr)
        sys.exit(1)
