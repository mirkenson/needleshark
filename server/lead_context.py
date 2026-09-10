"""Optional catalogue context, shared by validation, CRM and Google delivery."""
import re

CONTEXT_FIELDS = ('product_slug', 'product_name', 'product_size', 'inquiry_type', 'quantity', 'source_path')
INQUIRY_LABELS = {'direct': 'Заказ напрямую', 'sizing': 'Подбор размера', 'wholesale': 'Партия для бизнеса'}


def validate_context(data):
    result = {}
    limits = {'product_slug': 100, 'product_name': 200, 'product_size': 60, 'inquiry_type': 20, 'source_path': 200}
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
    if result.get('source_path') and not re.fullmatch(r'/(?:[a-z0-9-]+/)*', result['source_path']):
        raise ValueError('Некорректная страница заявки.')
    quantity = data.get('quantity')
    if quantity is not None:
        if type(quantity) is not int or not 1 <= quantity <= 1_000_000:
            raise ValueError('Укажите целое количество от 1 до 1000000.')
        result['quantity'] = quantity
    return result


def google_payload(lead):
    """Keep the existing Sheets columns/mail template; enrich only task text."""
    labels = [('product_name', 'Товар'), ('product_slug', 'Код товара'), ('product_size', 'Размер, см'),
              ('inquiry_type', 'Тип обращения'), ('quantity', 'Количество, шт.'), ('source_path', 'Страница')]
    context = []
    for key, label in labels:
        if lead.get(key) is not None and lead.get(key) != '':
            value = INQUIRY_LABELS.get(lead[key], lead[key]) if key == 'inquiry_type' else lead[key]
            context.append(f'{label}: {value}')
    if not context:
        return dict(lead)
    return dict(lead, question='\n'.join(context) + '\n\nКомментарий:\n' + lead['question'])
