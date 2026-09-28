"""Operator-only mixed-package evidence; no authorization or write admission."""
import json
from .legacy_reconciliation import _reconciliation_preview


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Repeated JSON key')
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError('Invalid JSON number')


def _package(value):
    if not isinstance(value, str) or value != value.strip(' \t\r\n'):
        raise ValueError('Package must be an explicit canonical string')
    return value


def package_review(raw):
    if not isinstance(raw, str) or len(raw.encode('utf-8')) > 1024 * 1024:
        raise ValueError('Expected bounded original JSON text')
    try:
        items = json.loads(raw, object_pairs_hook=_object, parse_constant=_invalid_constant)
    except (ValueError, RecursionError) as error:
        raise ValueError('Invalid original item JSON') from error
    if not isinstance(items, list) or not 1 <= len(items) <= 2000:
        raise ValueError('Expected nonempty bounded item array')
    groups = {}
    for position, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise ValueError('Expected object item')
        values = [_package(item[key]) for key in ('workPackage', 'work_package') if key in item]
        if not values or len(set(values)) != 1:
            raise ValueError('Missing or conflicting package aliases')
        groups.setdefault(values[0], []).append(position)
    return dict(packageCount=len(groups), itemCount=len(items),
                groups=[dict(workPackage=key, positions=groups[key]) for key in sorted(groups)])


def mixed_reconciliation_preview(invoice, warehouses, raw):
    def blocked(reason):
        return dict(scenario='blocked', admissionGranted=False, reason=reason)
    try:
        review = package_review(raw)
        header = _package(invoice['workPackage'])
    except (ValueError, KeyError):
        return blocked('invalidReceiptPackage')
    if review['packageCount'] < 2:
        return blocked('notMixedPackageReceipt')
    if not invoice.get('supplierId') or not invoice.get('projectName'):
        return blocked('missingReceiptIdentity')
    result = _reconciliation_preview(invoice, warehouses, compare_package=False)
    if result['scenario'] != 'matchedLegacyPair':
        return result if result['scenario'] == 'blocked' else blocked('requiresLegacyPair')
    return dict(result, scenario='mixedPackageLegacyPair', packageReview=review,
                requiredPackages=sorted({header} | {row['workPackage'] for row in review['groups']}))
