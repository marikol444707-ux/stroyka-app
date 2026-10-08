"""Read-only ranking of complete, current, technically comparable quotations."""
import datetime as dt
import json
from decimal import Decimal, InvalidOperation

from .technical_matcher import compare_required_to_offer, normalize_name, normalize_unit


def number(value):
    if value is None or isinstance(value, bool):
        raise ValueError('Не указано число')
    result = Decimal(str(value))
    if not result.is_finite() or abs(result) >= Decimal('1e12'):
        raise ValueError('Некорректное число')
    return result


def lines(value):
    rows = json.loads(value) if isinstance(value, str) else value
    if not isinstance(rows, list) or not rows or len(rows) > 100 or any(not isinstance(row, dict) for row in rows):
        raise ValueError('Нужно проверить состав КП')
    return rows


def line_name(row):
    return row.get('materialName') or row.get('name') or ''


def full_basket(required, offered):
    remaining = list(offered)
    total = Decimal(0)
    for wanted in required:
        if not isinstance(line_name(wanted), str) or not line_name(wanted).strip():
            raise ValueError('Не указано название материала в заявке')
        matches = [row for row in remaining if normalize_name(line_name(row)) == normalize_name(line_name(wanted))]
        if not matches:
            matches = [row for row in remaining if compare_required_to_offer(
                line_name(wanted), line_name(row), required_unit=wanted.get('unit') or '',
                offered_unit=row.get('unit') or '').decision in ('exact', 'comparable')]
        if len(matches) != 1:
            raise ValueError('Состав КП не совпадает с заявкой или требует проверки')
        row = matches[0]
        qty, price = number(row.get('quantity')), number(row.get('pricePerUnit'))
        if (qty != number(wanted.get('quantity')) or qty <= 0 or price <= 0
                or not wanted.get('unit') or normalize_unit(row.get('unit') or '') != normalize_unit(wanted['unit'])
                or (row.get('workPackage') or 'Основная') != (wanted.get('workPackage') or 'Основная')):
            raise ValueError('Проверьте количество, единицы и цены позиций')
        subtotal = (qty * price).quantize(Decimal('.01'))
        if row.get('totalPrice') is not None and abs(number(row['totalPrice'])-subtotal) > Decimal('.05'):
            raise ValueError('Сумма позиции не совпадает с ценой и количеством')
        total += subtotal
        remaining.remove(row)
    if remaining:
        raise ValueError('В КП есть лишние позиции')
    return total


def compare_commercial_offers(request, offers, *, today=None):
    today = today or dt.date.today()
    try:
        required = lines(request.get('items_json') or [dict(materialName=request.get('material_name'),
            quantity=request.get('quantity'), unit=request.get('unit'), workPackage=request.get('work_package'))])
        required = [dict(row, workPackage=row.get('workPackage') or request.get('work_package') or 'Основная') for row in required]
    except (ValueError, TypeError):
        return dict(bestOfferId=None, bestSupplier=None, ranking=[], excludedOffers=[],
                    error='Проверьте позиции заявки перед сравнением')
    ranking, excluded = [], []
    for offer in offers:
        supplier = offer.get('supplier_name') or 'Поставщик #'+str(offer['supplier_id'])
        try:
            expiry = offer.get('valid_until')
            if expiry and dt.date.fromisoformat(str(expiry)[:10]) < today:
                raise ValueError('Срок действия КП истёк')
            total = full_basket(required, lines(offer.get('items_kp_json')))
            if total <= 0 or abs(total-number(offer.get('total_price'))) > Decimal('.05'):
                raise ValueError('Проверьте итоговую сумму КП')
            days = number(offer.get('delivery_days'))
            if days < 0 or days != int(days):
                raise ValueError('Проверьте срок доставки')
            if type(offer.get('vat_included')) is not bool:
                raise ValueError('Не указано, включён ли НДС в цену')
            rating = number(offer.get('rating') or 0)
            if not 0 <= rating <= 5:
                raise ValueError('Проверьте рейтинг поставщика')
            ranking.append(dict(offerId=offer['id'], supplier=supplier, rating=float(rating),
                pricePerUnit=float(total/number(required[0]['quantity'])) if len(required) == 1 else None,
                totalPrice=float(total), deliveryDays=int(days), paymentTerms=offer.get('payment_terms') or '',
                vatIncluded=offer['vat_included'], validUntil=str(expiry) if expiry else None))
        except (ValueError, TypeError, KeyError, InvalidOperation) as exc:
            excluded.append(dict(offerId=offer['id'], supplier=supplier,
                reason=str(exc) if isinstance(exc, ValueError) else 'Проверьте заполнение КП'))
    prices = [number(row['totalPrice']) for row in ranking]
    days = [number(row['deliveryDays']) for row in ranking]
    def normalized(value, values):
        return Decimal(1) if max(values) == min(values) else (max(values)-number(value))/(max(values)-min(values))
    for row in ranking:
        terms = row['paymentTerms'].lower()
        risk = Decimal(0) if 'предоплат' in terms and '100' in terms else Decimal(1) if 'постоплат' in terms or 'отсрочк' in terms else Decimal('.5')
        score = normalized(row['totalPrice'], prices)*Decimal('.4') + normalized(row['deliveryDays'], days)*Decimal('.2') + risk*Decimal('.2') + (number(row['rating'])/5 if row['rating'] else Decimal('.5'))*Decimal('.2')
        row['score'] = float((score*100).quantize(Decimal('.1')))
    ranking.sort(key=lambda row: (-row['score'], row['totalPrice'], row['deliveryDays'], row['offerId']))
    result = dict(bestOfferId=ranking[0]['offerId'] if ranking else None,
        bestSupplier=ranking[0]['supplier'] if ranking else None, ranking=ranking,
        excludedOffers=excluded, comparableOffersCount=len(ranking), automaticApprovalAllowed=False)
    if not ranking:
        result['error'] = 'Нет КП, которые можно сравнить по всей заявке. Проверьте замечания.'
    return result


def verified_explanation(text, best_offer_id):
    try:
        text = text.strip()
        if text.startswith('```') and text.endswith('```'):
            text = text[3:-3].strip()
            if text.startswith('json\n'):
                text = text[5:].strip()
        result = json.loads(text)
        explanation = result.get('explanation')
        if isinstance(explanation, list) and 1 <= len(explanation) <= 3 and all(isinstance(part, str) for part in explanation):
            explanation = ' '.join(explanation)
        if type(result.get('bestOfferId')) is int and result['bestOfferId'] == best_offer_id and isinstance(explanation, str) and 0 < len(explanation.strip()) <= 2000:
            return explanation.strip()
    except (ValueError, TypeError, AttributeError):
        pass
    return None
