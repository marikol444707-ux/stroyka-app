"""Evidence DTOs from protected readers, never raw model assertions.

Every fact is bound to a captured quotation, timestamp and document revision.
Semantic extraction remains the responsibility of the reviewed source adapter.
The model cannot declare a primary source trusted or grant itself credentials.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
import hashlib
import ipaddress
import re
from urllib.parse import urlsplit

REGIONS = ('Ставропольский край', 'Краснодарский край')
QUERIES = ('капитальный ремонт', 'кровля', 'фасад', 'отделка', 'ремонт помещений',
           'бассейн СПА', 'водоснабжение', 'канализация', 'отопление', 'вентиляция',
           'электроснабжение', 'комплексные СМР')
TARGET_SECTORS = ('производство', 'сельское хозяйство', 'склады', 'торговля',
                  'административные объекты', 'гостиницы', 'санатории')
MISSING = ('Не указано', 'Не удалось проверить', 'Требует уточнения')
FIELDS = frozenset(('title', 'organizer', 'counterparty', 'counterparty_id', 'object_id', 'procedure_id',
    'role', 'authority', 'work_address', 'work_region', 'work_scope', 'work_volume',
    'kind', 'regime', 'price', 'currency', 'vat', 'stage', 'deadline', 'timezone',
    'design_period', 'construction_period', 'payment', 'advance_conditions',
    'customer_materials', 'payment_period', 'security', 'guarantee', 'retention',
    'experience', 'construction_sro', 'design_sro', 'fire_license', 'accreditation',
    'site_visit', 'submission', 'documents', 'requirements'))
STAGES = ('accepting', 'qualification', 'standing', 'suspended', 'cancelled', 'closed', 'archive')
KINDS = ('capital_repair', 'design_build_repair', 'current_repair', 'engineering_modernization',
         'goods', 'equipment_rental', 'maintenance', 'design_only', 'other')
ENUMS = {'stage': STAGES, 'kind': KINDS,
         'role': ('owner', 'authorized_operator', 'general_contractor', 'unknown'),
         'payment': ('advance', 'staged', 'postpayment', 'unknown'),
         'regime': ('commercial', '44-ФЗ', '223-ФЗ', '615-ПП'),
         'authority': ('confirmed', 'unknown'), 'customer_materials': ('yes', 'no', 'unknown')}
ENUMS.update({name: ('required', 'not_required', 'unknown') for name in
              ('construction_sro', 'design_sro', 'fire_license')})


def aware(value):
    return isinstance(value, datetime) and value.utcoffset() is not None


def public_url(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 2048 or re.search(r'[\s\\\x00-\x1f]', value):
        return False
    try:
        url = urlsplit(value)
        host = url.hostname
        if (url.scheme != 'https' or not host or url.username or url.password
                or url.port not in (None, 443) or url.fragment or '.' not in host):
            return False
        try: ipaddress.ip_address(host); return False
        except ValueError: pass
        return not host.endswith(('.local', '.localhost', '.internal'))
    except ValueError:
        return False


@dataclass(frozen=True)
class Document:
    id: str
    source: str
    url: str
    name: str
    kind: str  # card / terms / contract / quote / authority / aggregator
    checked_at: datetime
    text: str

    def __post_init__(self):
        if (not self.id or not self.name or not self.source or not public_url(self.url)
                or self.kind not in ('card', 'terms', 'contract', 'quote', 'authority', 'aggregator')
                or not aware(self.checked_at) or not isinstance(self.text, str)
                or not 1 <= len(self.text.encode()) <= 512 * 1024):
            raise ValueError('bounded_captured_document_required')

    @property
    def sha256(self):
        return hashlib.sha256(self.text.encode()).hexdigest()


@dataclass(frozen=True)
class Fact:
    value: str | None = None
    document: str | None = None
    quote: str | None = None
    locator: str | None = None
    missing: str | None = None


@dataclass(frozen=True)
class Candidate:
    source: str
    number: str
    documents: tuple[Document, ...]
    facts: dict[str, tuple[Fact, ...]] = field(default_factory=dict)

    def validate(self, now, hosts):
        if (not aware(now) or self.source not in hosts or not self.number or len(self.number) > 128
                or not 1 <= len(self.documents) <= 50 or len(self.facts) > len(FIELDS)
                or set(self.facts) - FIELDS):
            raise ValueError('bounded_candidate_required')
        documents = {doc.id: doc for doc in self.documents}
        if len(documents) != len(self.documents):
            raise ValueError('duplicate_document_identity')
        for doc in self.documents:
            if (doc.source not in hosts or urlsplit(doc.url).hostname not in hosts[doc.source]
                    or doc.checked_at > now + timedelta(seconds=5)):
                raise ValueError('reviewed_source_and_observation_required')
            if doc.kind == 'card' and doc.source != self.source:
                raise ValueError('primary_card_source_identity_required')
        for name, facts in self.facts.items():
            if type(facts) is not tuple or not 1 <= len(facts) <= 8:
                raise ValueError('bounded_field_evidence_required')
            for fact in facts:
                if type(fact) is not Fact:
                    raise ValueError('typed_fact_required')
                if fact.missing is not None:
                    if fact.missing not in MISSING or any(x is not None for x in (fact.value, fact.document, fact.quote, fact.locator)):
                        raise ValueError('distinct_missing_reason_required')
                    continue
                doc = documents.get(fact.document)
                if (doc is None or not isinstance(fact.value, str) or not 1 <= len(fact.value) <= 4000
                        or not fact.quote or len(fact.quote) > 8000 or fact.quote not in doc.text
                        or not fact.locator or len(fact.locator) > 256):
                    raise ValueError('captured_quote_and_locator_required')
                if name in ENUMS and fact.value not in ENUMS[name]:
                    raise ValueError('invalid_normalized_fact')
                if name == 'price':
                    try: amount = Decimal(fact.value)
                    except Exception: raise ValueError('exact_price_required') from None
                    if not amount.is_finite() or amount < 0 or amount > Decimal('1e12'):
                        raise ValueError('exact_price_required')
        return documents


@dataclass(frozen=True)
class Profile:
    regions: tuple[str, ...] = REGIONS
    minimum_rub: Decimal = Decimal('3000000')
    legal_entity: str | None = None
    # Explicit confirmed qualifications of the SELECTED entity, no inferred SRO.
    qualifications: frozenset[str] = frozenset()

    def validate(self):
        if (not self.regions or set(self.regions) - set(REGIONS)
                or not isinstance(self.minimum_rub, Decimal) or not self.minimum_rub.is_finite()
                or self.minimum_rub < 0 or self.qualifications - {
                    'construction_sro', 'design_sro', 'fire_license'}
                or self.qualifications and not self.legal_entity):
            raise ValueError('explicit_executor_profile_required')
