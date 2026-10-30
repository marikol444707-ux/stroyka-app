"""Extensible source inventory. A research target is NOT a working connector.

Domains and endpoints must be reviewed by an operator before binding a reader.
No guessed procurement URLs, login, registration or source text execution.
"""
from dataclasses import dataclass

LIMITATION_LABELS={
    'first_pages_only':'просмотрены первые страницы выдачи',
    'primary_parser_not_live_verified':'парсер ещё не проверен на живом сайте',
    'documents_not_read':'документы с условиями не прочитаны',
    'read_budget_exhausted':'достигнут лимит чтения',
    'some_primary_cards_not_verified':'часть первичных карточек не удалось проверить',
}


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    category: str
    hosts: tuple[str, ...] = ()


SOURCES = (
    Source('b2b', 'B2B-Center', 'platform', ('www.b2b-center.ru',)),
    Source('fabrikant', 'Фабрикант', 'platform', ('www.fabrikant.ru', 'fabrikant.ru')),
    Source('tektorg', 'ТЭК-Торг', 'platform', ('www.tektorg.ru',)),
    Source('gpb', 'ЭТП ГПБ', 'platform', ('etpgpb.ru',)),
    Source('roseltorg', 'Росэлторг', 'platform', ('www.roseltorg.ru',)),
    Source('tenderpro', 'Tender.Pro', 'platform'),
    Source('sber', 'Сбер А', 'platform', ('www.sberbank-ast.ru', 'utp.sberbank-ast.ru')),
    Source('federation', 'Торги Федерации', 'platform', ('lk.fedtorgi.ru', 'etpp.ru')),
    Source('rtender', 'Р-ТЕНДЕР', 'platform', ('etp.r-tender.ru',)),
    Source('ozon', 'Ozon', 'owner'),
    *(Source(key, name, 'agriculture') for key, name in (
        ('agrokompleks', 'Агрокомплекс'), ('progress', 'Прогресс Агро'),
        ('step', 'Степь'), ('ecoculture', 'ЭКО-культура'), ('rusagro', 'Русагро'),
        ('yugrusi', 'Юг Руси'), ('pokrovsky', 'Покровский'), ('resurs', 'Ресурс'),
        ('damate', 'Дамате'))),
    Source('sanatoriums', 'Санатории и гостиницы: официальные сайты', 'research'),
    Source('industrial', 'Производственные предприятия: официальные сайты', 'research'),
    Source('logistics', 'Торговые и логистические компании: официальные сайты', 'research'),
)


def source_registry(extra=()):
    result = {}
    for source in (*SOURCES, *extra):
        if (type(source) is not Source or source.id in result
                or not source.id or not source.name
                or source.category not in ('platform', 'owner', 'agriculture', 'research', 'aggregator')):
            raise ValueError('unique_reviewed_source_required')
        result[source.id] = source
    return result
