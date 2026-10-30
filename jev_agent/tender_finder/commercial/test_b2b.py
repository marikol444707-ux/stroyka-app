"""Synthetic labeled specimens, NOT captures or live compatibility acceptance."""
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import tempfile
import unittest
from urllib.parse import parse_qs,urlsplit

from .b2b import B2BReader, Observation, parse_card, fields
from .model import Document, Profile
from .policy import assess
from .runner import run
from .sources import source_registry
from .test_commercial import NOW, SCOPE, HOSTS

URL='https://www.b2b-center.ru/market/synthetic-fixture/tender-123456/'
TEXT='''Тендер № 123456
Наименование закупки: Капитальный ремонт корпуса
Организатор: Условный организатор, г. Москва
Сторона договора (заказчик): Синтетическое ООО
Место выполнения работ: Россия, Краснодарский край, г. Сочи, условный объект
Состав работ: Капитальный ремонт кровли площадью 3000 м²
Бюджет: 5 000 000,00 RUB с НДС 22%
Текущий этап: Приём предложений
Дата окончания подачи заявок: 15.11.2026 12:00 (МСК)
Условия оплаты: Аванс 20% под банковскую гарантию, зачёт по этапам
Строительная СРО: Требуется
Проектная СРО: Не требуется
Правовой режим: Коммерческая закупка
'''


def document(text=TEXT):return Document('fixture','b2b',URL,'Карточка B2B','card',NOW,text)


class PrimaryTests(unittest.TestCase):
    def test_extracts_primary_fields_with_verbatim_evidence(self):
        item=parse_card(document())
        row=assess(item,NOW,HOSTS)
        self.assertEqual(row['values']['work_region'],'Краснодарский край')
        self.assertEqual(row['values']['price'],'5000000.00')
        self.assertEqual(row['values']['currency'],'RUB')
        self.assertEqual(row['values']['deadline'],'2026-11-15T12:00:00+03:00')
        self.assertEqual(row['values']['kind'],'capital_repair')
        self.assertEqual(row['values']['vat'],'с НДС 22%')
        for facts in item.facts.values():
            for fact in facts:
                if fact.quote:self.assertIn(fact.quote,TEXT)

    def test_customer_and_brand_do_not_establish_direct_contract(self):
        row=assess(parse_card(document()),NOW,HOSTS)
        self.assertFalse(row['direct_contract_confirmed'])
        self.assertEqual(row['bucket'],'unconfirmed')
        self.assertNotIn('role',row['values'])

    def test_organizer_region_is_never_worksite(self):
        text=TEXT.replace('Место выполнения работ: Россия, Краснодарский край, г. Сочи, условный объект',
                          'Адрес организатора: Ставропольский край')
        row=assess(parse_card(document(text)),NOW,HOSTS)
        self.assertNotIn('work_region',row['values'])

    def test_wrong_number_and_foreign_url_are_rejected(self):
        for doc in (document(TEXT.replace('Тендер № 123456','Тендер № 999999')),
                    replace(document(),url='https://other.example/market/x/tender-123456/')):
            with self.assertRaises(ValueError):parse_card(doc)

    def test_source_missing_price_is_not_zero(self):
        item=parse_card(document(TEXT.replace('5 000 000,00 RUB с НДС 22%','Не указано')))
        self.assertEqual(item.facts['price'][0].missing,'Не указано')
        row=assess(item,NOW,HOSTS)
        self.assertNotIn('price',row['values'])
        self.assertNotIn('Бюджет ниже ориентира',row['exclusions'])

    def test_price_format_foreign_currency_and_no_implicit_rubles(self):
        for value,currency in (('5000000',None),('5 000 000 EUR','EUR'),('5 000 000 ₽','RUB')):
            row=assess(parse_card(document(TEXT.replace('5 000 000,00 RUB с НДС 22%',value))),NOW,HOSTS)
            self.assertEqual(row['values'].get('currency'),currency)
        row=assess(parse_card(document(TEXT.replace('5 000 000,00 RUB с НДС 22%','12 34 RUB'))),NOW,HOSTS)
        self.assertNotIn('price',row['values'])

    def test_no_implicit_timezone_or_invalid_calendar_date(self):
        for raw in ('15.11.2026 12:00','31.02.2026 12:00 (МСК)'):
            row=assess(parse_card(document(TEXT.replace('15.11.2026 12:00 (МСК)',raw))),NOW,HOSTS)
            self.assertEqual(row['values']['deadline'],raw)
            self.assertTrue(any('часовой пояс' in risk for risk in row['risks']))

    def test_closed_primary_overrides_search_active_filter(self):
        row=assess(parse_card(document(TEXT.replace('Текущий этап: Приём предложений','Текущий этап: Завершено'))),NOW,HOSTS)
        self.assertEqual(row['bucket'],'excluded')
        self.assertEqual(row['values']['stage'],'closed')

    def test_no_false_advance_from_negative_statement(self):
        raw='Аванс не предусмотрен, постоплата 30 дней'
        row=assess(parse_card(document(TEXT.replace('Аванс 20% под банковскую гарантию, зачёт по этапам',raw))),NOW,HOSTS)
        self.assertNotIn('payment',row['values'])
        self.assertNotIn('advance_conditions',row['values'])

    def test_independent_sro_and_no_qualification_inference(self):
        row=assess(parse_card(document()),NOW,HOSTS)
        self.assertEqual(row['values']['construction_sro'],'required')
        self.assertEqual(row['values']['design_sro'],'not_required')
        self.assertNotIn('fire_license',row['values'])

    def test_conflicting_duplicate_labels_are_not_silently_selected(self):
        row=assess(parse_card(document(TEXT+'Бюджет: 8 000 000 RUB\n')),NOW,HOSTS)
        self.assertIn('price',row['conflicts'])
        self.assertNotIn('price',row['values'])

    def test_label_only_field_does_not_consume_next_field(self):
        observed=fields('Наименование закупки:\nТекущий этап: Завершено\n')
        self.assertFalse(any(field[0]=='title' for field in observed))
        self.assertEqual(observed[0][0],'stage')


class ReaderTests(unittest.TestCase):
    def fixture_reader(self,card_text=TEXT):
        calls=[]
        def read(url):
            calls.append(url)
            if url==URL:return Observation(url,'ok',NOW,card_text)
            term=parse_qs(urlsplit(url).query)['q'][0]
            state={'url':url,'query':term,'selected':['Объявления о закупках','Актуально • 1'],
                   'page_state':'Объявления о закупках Актуально • 1','rows':[{'url':URL}]}
            return Observation(url,'ok',NOW,'Синтетическая выдача',state)
        return read,calls

    def test_two_region_queries_deduplicate_and_read_primary_once(self):
        read,calls=self.fixture_reader()
        result=B2BReader(read=read,clock=lambda:NOW)(Profile(queries=('кровля',)),NOW)
        self.assertEqual(len(result.candidates),1)
        self.assertEqual(calls.count(URL),1)
        terms=[parse_qs(urlsplit(url).query)['q'][0] for url in calls if url!=URL]
        self.assertIn('Ставропольский край',terms);self.assertIn('Краснодарский край',terms)
        self.assertEqual(result.status,'partial')
        self.assertIn('primary_parser_not_live_verified',result.limitations)

    def test_verified_empty_stays_partial_not_global_no_tenders(self):
        def read(url):
            term=parse_qs(urlsplit(url).query)['q'][0]
            return Observation(url,'ok',NOW,'Выдача без результатов',
                {'url':url,'query':term,'selected':['Объявления о закупках','Актуально • 0'],'rows':[]})
        result=B2BReader(read=read,clock=lambda:NOW)(Profile(),NOW)
        self.assertEqual(result.candidates,());self.assertEqual(result.status,'partial')

    def test_captcha_stops_without_retry(self):
        calls=[]
        def read(url):calls.append(url);return Observation(url,'captcha',NOW)
        result=B2BReader(read=read,clock=lambda:NOW)(Profile(),NOW)
        self.assertEqual(result.status,'captcha');self.assertEqual(len(calls),1)

    def test_broken_search_query_is_not_claimed_checked(self):
        read,calls=self.fixture_reader()
        def bad(url):
            observed=read(url)
            return replace(observed,search_state={**observed.search_state,'query':'ДРУГОЙ ЗАПРОС'})
        result=B2BReader(read=bad,clock=lambda:NOW)(Profile(),NOW)
        self.assertEqual(result.candidates,())
        self.assertNotIn(URL,calls)
        self.assertIn('some_primary_cards_not_verified',result.limitations)

    def test_foreign_links_never_reach_transport(self):
        read,calls=self.fixture_reader()
        def bad(url):
            observed=read(url)
            return replace(observed,search_state={**observed.search_state,
                'rows':[{'url':'https://attacker.example/market/x/tender-1/'}]})
        result=B2BReader(read=bad,clock=lambda:NOW)(Profile(),NOW)
        self.assertFalse(result.candidates)
        self.assertFalse(any('attacker' in url for url in calls))

    def test_stale_or_redirected_capture_is_error(self):
        for change in ({'checked_at':NOW-timedelta(days=1)},{'url':'https://www.b2b-center.ru/login/'}):
            reader=B2BReader(read=lambda url:Observation(**{'url':url,'status':'ok','checked_at':NOW,**change}),clock=lambda:NOW)
            self.assertEqual(reader(Profile(),NOW).status,'error')

    def test_scoped_runner_retains_limitations_and_primary_proof(self):
        read,_=self.fixture_reader()
        sources={'b2b':source_registry()['b2b']}
        with tempfile.TemporaryDirectory() as directory:
            report=run('fixture-b2b-run',SCOPE,directory,sources=sources,
                adapters={'b2b':B2BReader(read=read,clock=lambda:NOW)},clock=lambda:NOW)
        self.assertFalse(report['sources_complete'])
        self.assertEqual(report['coverage'][0]['primary_cards'],1)
        self.assertEqual(len(report['sections']['unconfirmed']),1)
        self.assertIn('documents_not_read',report['coverage'][0]['limitations'])

    def test_read_but_unparsed_primary_is_still_counted(self):
        read,_=self.fixture_reader('Неизвестная структура первичной карточки')
        with tempfile.TemporaryDirectory() as directory:
            report=run('fixture-unparsed',SCOPE,directory,sources={'b2b':source_registry()['b2b']},
                adapters={'b2b':B2BReader(read=read,clock=lambda:NOW)},clock=lambda:NOW)
        self.assertEqual(report['coverage'][0]['primary_cards'],1)
        self.assertFalse(report['sections']['priority'])
        self.assertIn('some_primary_cards_not_verified',report['coverage'][0]['limitations'])

    def test_read_budget_is_enforced_without_claiming_complete_coverage(self):
        calls=[]
        def read(url):
            calls.append(url)
            if '/tender-' in url:
                number=url.rsplit('tender-',1)[1].rstrip('/')
                return Observation(url,'ok',NOW,TEXT.replace('123456',number))
            term=parse_qs(urlsplit(url).query)['q'][0]
            rows=[{'url':URL.replace('123456',str(100000+index))} for index in range(45)]
            return Observation(url,'ok',NOW,'Синтетическая выдача',
                {'url':url,'query':term,'selected':['Объявления о закупках','Актуально • 45'],'rows':rows})
        result=B2BReader(read=read,clock=lambda:NOW)(Profile(),NOW)
        self.assertEqual(len(calls),40)
        self.assertEqual(len(result.primary_captures),39)
        self.assertIn('read_budget_exhausted',result.limitations)

    def test_wall_time_budget_prevents_starting_more_reads(self):
        ticks=iter((0,181));calls=[]
        def read(url):calls.append(url);raise AssertionError('must not start after deadline')
        result=B2BReader(read=read,clock=lambda:NOW,monotonic=lambda:next(ticks))(Profile(),NOW)
        self.assertEqual(calls,[])
        self.assertIn('read_budget_exhausted',result.limitations)


if __name__=='__main__':unittest.main()
