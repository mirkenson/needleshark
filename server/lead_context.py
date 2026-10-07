"""Optional catalogue context, shared by validation, CRM and notification delivery."""
import re

CONTEXT_FIELDS = ('product_slug', 'product_name', 'product_size', 'inquiry_type', 'quantity', 'source_path',
                  'business_intent', 'business_company', 'email', 'phone', 'business_direction', 'business_material')
INQUIRY_LABELS = {'direct': 'Заказ напрямую', 'sizing': 'Подбор размера', 'wholesale': 'Партия для бизнеса'}
BUSINESS_LABELS = {'ready': 'Партия готовых изделий', 'custom': 'Изделие на заказ', 'materials': 'Ткани и стропы'}
DIRECTION_LABELS = {'chehly': 'Чехлы на технику и оборудование', 'sumki': 'Специализированные сумки и баулы',
                    'remni': 'Ременные изделия', 'ukrytiya-i-shtory': 'Укрытия и технические шторы', 'po-tz': 'Пошив по ТЗ'}
MATERIAL_LABELS = {'oxford': 'Оксфорд', 'canvas': 'Брезент', 'spunbond': 'Спанбонд', 'cordura': 'Кордура', 'polyester': 'Полиэстеры', 'other': 'Другой материал'}


def validate_context(data):
    result = {}
    limits = {'product_slug': 100, 'product_name': 200, 'product_size': 60, 'inquiry_type': 20, 'source_path': 200,
              'business_intent': 20, 'business_company': 160, 'email': 254, 'phone': 32,
              'business_direction': 40, 'business_material': 40}
    for key, limit in limits.items():
        value = data.get(key)
        if value is None or value == '':
            continue
        if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
            raise ValueError('Проверьте сведения о товаре и заказе.')
        value = value.strip()
        if value:
            result[key] = value
    if result.get('product_slug') and not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', result['product_slug']):
        raise ValueError('Некорректный товар.')
    if bool(result.get('product_slug')) != bool(result.get('product_name')):
        raise ValueError('Укажите название и код товара вместе.')
    if result.get('product_size'):
        if not result.get('product_slug') or not re.fullmatch(r'[1-9]\d{0,3} × [1-9]\d{0,3} × [1-9]\d{0,3}', result['product_size']):
            raise ValueError('Некорректный размер товара.')
    if result.get('inquiry_type') and result['inquiry_type'] not in INQUIRY_LABELS:
        raise ValueError('Некорректный тип обращения.')
    if result.get('business_intent') and result['business_intent'] not in BUSINESS_LABELS:
        raise ValueError('Некорректное направление заявки.')
    for key, allowed in [('business_direction', DIRECTION_LABELS), ('business_material', MATERIAL_LABELS)]:
        if result.get(key) and result[key] not in allowed:
            raise ValueError('Некорректное направление или материал.')
    if result.get('email') and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', result['email']):
        raise ValueError('Проверьте email.')
    if result.get('phone') and (not re.fullmatch(r'\+?[\d\s()-]+', result['phone']) or not 10 <= len(re.sub(r'\D', '', result['phone'])) <= 15):
        raise ValueError('Проверьте телефон.')
    if result.get('email') or result.get('phone'):
        if data.get('contact', '').strip() != (result.get('email') or result['phone']):
            raise ValueError('Основной контакт не соответствует полям формы.')
    if result.get('source_path') and not re.fullmatch(r'/(?:[a-z0-9-]+/)*', result['source_path']):
        raise ValueError('Некорректная страница заявки.')
    quantity = data.get('quantity')
    if quantity is not None:
        if type(quantity) is not int or not 1 <= quantity <= 1_000_000:
            raise ValueError('Укажите целое количество от 1 до 1000000.')
        result['quantity'] = quantity
    return result


def notification_payload(lead):
    """Enrich notification text while preserving structured fields and the original lead."""
    labels = [('product_name', 'Товар'), ('product_slug', 'Код товара'), ('product_size', 'Размер, см'),
              ('inquiry_type', 'Тип обращения'), ('quantity', 'Количество, шт.'), ('source_path', 'Страница'),
              ('business_intent', 'Направление'), ('business_company', 'Компания / сфера'),
              ('email', 'Почта'), ('phone', 'Телефон'), ('business_direction', 'Изделия'), ('business_material', 'Материал')]
    context = []
    for key, label in labels:
        if lead.get(key) is not None and lead.get(key) != '':
            value = INQUIRY_LABELS.get(lead[key], lead[key]) if key == 'inquiry_type' else lead[key]
            if key == 'business_intent':
                value = BUSINESS_LABELS[value]
            if key == 'business_direction':
                value = DIRECTION_LABELS[value]
            if key == 'business_material':
                value = MATERIAL_LABELS[value]
            context.append(f'{label}: {value}')
    if not context:
        return dict(lead)
    return dict(lead, question='\n'.join(context) + '\n\nКомментарий:\n' + lead['question'])


# Compatibility for historical backfill/check tools; no Google network integration.
google_payload = notification_payload
