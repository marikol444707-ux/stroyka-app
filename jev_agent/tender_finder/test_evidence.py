from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import tempfile
import unittest
from unittest.mock import Mock

from .contract import REGION, validate_v2_request
from .evidence import commercial_card, evidence_report, match_topics, parse_deadline, parse_price
from .jobs import process_request
from .presentation import render_report
from .state import Scope

NOW=datetime(2026,10,28,10,tzinfo=timezone.utc)
SCOPE=Scope(37,'fixture-owner')
PAYLOAD={'version':2,'request_id':'search-fixture-001','region':REGION,
         'sources':['commercial'],'commercial_sources':['B2B-Center'],'topics':['кровля']}


def row(**changes):
    return {'source':'B2B-Center','id':'123','url':'https://www.b2b-center.ru/market/synthetic/tender-123/',
            'title':'Капитальный ремонт кровли школы','organizer':'Тестовый организатор',
            'region':REGION,'place':'Ставрополь','region_scope':'worksite',
            'regime':'Коммерческая закупка','status':'Прием заявок','deadline':'30.10.2026 12:00',
            'price':'5 000 000,00 ₽',**changes}


def found(rows=None,**changes):
    data={'ok':True,'sources':[{'provider':'B2B-Center','query':'кровельные работы','ok':True,
                               'url':'https://www.b2b-center.ru/app/next/market-search'}],
          'confirmed':[row()] if rows is None else rows,'review':[],'excluded':{},**changes}
    return {'request_id':PAYLOAD['request_id'],'company_id':37,'status':'completed',
            'outputs':[{'source':'commercial','status':'completed','query':None,'report':data}]}


def report(rows=None, request_changes=None, **changes):
    return evidence_report(validate_v2_request({**PAYLOAD,**(request_changes or {})}),SCOPE,
                           found(rows,**changes),started_at=NOW,completed_at=NOW+timedelta(seconds=2))


class ListingEvidenceTests(unittest.TestCase):
    def test_explicit_rubles_are_exact_and_other_formats_stay_unknown(self):
        for text in ('5 000 000,25 ₽','5\u00a0000\u00a0000,25 руб.','5000000.25 RUB'):
            self.assertEqual(parse_price(text),(Decimal('5000000.25'),'RUB'))
        for value in ('5000000','10 USD','от 1 до 5 млн ₽','не указана','100 ₽ + НДС',-1,None):
            self.assertEqual(parse_price(value),(None,None))
        self.assertEqual(parse_price('0 ₽'),(Decimal('0'),'RUB'))

    def test_deadlines_are_aware_and_date_only_or_invalid_are_not_invented(self):
        self.assertEqual(parse_deadline('30.10.2026 12:00').utcoffset(),timedelta(hours=3))
        self.assertEqual(parse_deadline('2026-10-30T09:00:00Z'),parse_deadline('30.10.2026 12:00'))
        for value in ('2026-10-30','2026-10-30T12:00:00','31.02.2026 10:00','до конца месяца'):
            self.assertIsNone(parse_deadline(value))

    def test_organizer_and_region_scope_do_not_become_customer_or_work_address(self):
        card=commercial_card(row(),NOW)
        self.assertEqual(card.organizer,'Тестовый организатор')
        self.assertIsNone(card.customer);self.assertIsNone(card.work_region)
        self.assertEqual(card.location_basis,'unknown')
        card=commercial_card(row(region_scope='customer_region_filter'),NOW)
        self.assertEqual(card.location_basis,'customer_region')

    def test_upstream_confirmed_does_not_bypass_review_and_price_filter_is_applied(self):
        value=report();card=value['tenders'][0]
        self.assertTrue(card['needs_manual_review'])
        self.assertIn('work_region_unverified',card['reasons'])
        self.assertIn('customer_unknown',card['reasons'])
        self.assertEqual(card['price_rub'],'5000000.00')
        self.assertFalse(value['card_acceptance_complete'])
        value=report(request_changes={'price_min_rub':6000000})
        self.assertEqual(value['tenders'],[])
        self.assertIn('price_below_range',value['excluded'][0]['reasons'])

    def test_unknown_money_stays_review_not_below_range(self):
        value=report([row(price='100 USD')],{'price_min_rub':1000000})
        self.assertEqual(len(value['tenders']),1)
        self.assertIsNone(value['tenders'][0]['price_rub'])
        self.assertIn('price_unknown',value['tenders'][0]['reasons'])

    def test_expired_and_closed_rows_are_excluded_despite_upstream_confirmation(self):
        for changes in ({'deadline':'01.10.2026 12:00'},{'status':'Завершена'}):
            value=report([row(**changes)])
            self.assertEqual(value['tenders'],[])
            self.assertEqual(value['excluded_count'],1)

    def test_topic_matching_is_explicit_not_every_repair(self):
        self.assertIn('roofing',match_topics('Выполнить ремонт кровли школы'))
        self.assertNotIn('roofing',match_topics('Ремонт насосного оборудования'))
        self.assertNotIn('gas',match_topics('газоснабжениеметр'))

    def test_spoofed_or_mismatched_procedure_identity_is_disclosed_not_published(self):
        for changes in ({'id':'999'},{'url':'https://www.b2b-center.ru.evil.example/market/tender-123/'}):
            value=report([row(**changes)])
            self.assertEqual(value['tenders'],[])
            self.assertTrue(value['normalization_issues'])
            self.assertEqual(value['sources_status'][0]['status'],'error')
            self.assertNotEqual(value['status'],'completed')

    def test_missing_source_and_source_outage_do_not_become_verified_empty(self):
        value=report([],sources=[])
        self.assertEqual(value['sources_status'][0]['status'],'not_tested')
        value=report([],sources=[{'provider':'B2B-Center','ok':False}])
        self.assertEqual(value['sources_status'][0]['status'],'error')
        self.assertIsNone(value['sources_status'][0]['url'])

    def test_adapter_exclusion_counts_are_separate_from_known_individual_exclusions(self):
        value=report([],excluded={'regulated_procurement':4})
        self.assertEqual(value['adapter_preexcluded_counts'],{'regulated_procurement':4})
        self.assertEqual(value['excluded_count'],0)
        self.assertTrue(any('исходный адаптер' in warning.casefold() for warning in value['warnings']))

    def test_eis_registry_links_are_not_fabricated_cards(self):
        req=validate_v2_request({**PAYLOAD,'sources':['eis'],'commercial_sources':[],
                                  'legal_regimes':['44-ФЗ','223-ФЗ']})
        link='https://zakupki.gov.ru/epz/order/notice/ea20/view/common-info.html?regNumber=123'
        data={'request_id':req.request_id,'company_id':37,'status':'partial','outputs':[
            {'source':'eis','status':'completed','query':'кровля','report':{
                'url':'https://zakupki.gov.ru/epz/order/extendedsearch/results.html',
                'notice_links':[link]}}]}
        value=evidence_report(req,SCOPE,data,started_at=NOW,completed_at=NOW)
        self.assertEqual(value['tenders'],[])
        self.assertEqual(value['unverified_links'][0]['url'],link)
        self.assertIsNone(value['unverified_links'][0]['title'])
        self.assertIn({'source':'eis:223-ФЗ','code':'unsupported_regime'},value['errors'])

    def test_job_core_stores_evidence_report_and_replay_does_not_refetch(self):
        raw=json.dumps(found()['outputs'][0]['report']).encode()
        invoker=Mock(return_value=(raw,0))
        with tempfile.TemporaryDirectory() as directory:
            first=process_request(PAYLOAD,SCOPE,directory,invoke=invoker,verify_runtime=Mock(),clock=lambda:NOW)
            second=process_request(PAYLOAD,SCOPE,directory,invoke=invoker,verify_runtime=Mock(),clock=lambda:NOW)
            self.assertEqual(first.result['schema_version'],2)
            self.assertEqual(first.result,second.result)
            self.assertIn('work_region_unverified',first.result['tenders'][0]['reasons'])
            self.assertIn('место работ не подтверждено',first.result['completion_preview'])
            invoker.assert_called_once()

    def test_conflicting_deadline_is_unknown_and_other_currencies_are_not_converted(self):
        card=commercial_card(row(deadline_msk='2026-11-10T09:00:00+03:00'),NOW)
        self.assertIsNone(card.deadline)
        card=commercial_card(row(price='1000 EUR'),NOW)
        self.assertIsNone(card.price_rub)
        self.assertEqual(card.raw_price,'1000 EUR')

    def test_goods_and_equipment_repair_are_not_treated_as_building_work(self):
        for title in ('Поставка кровельных материалов','Ремонт насосного оборудования'):
            value=report([row(title=title)])
            self.assertEqual(value['tenders'],[])
            self.assertEqual(value['excluded_count'],1)

    def test_real_adapter_procedure_hosts_are_accepted_without_widening_to_arbitrary_hosts(self):
        card=commercial_card(row(source='Торги Федерации',id='synthetic',
            url='https://etpp.ru/tenders/00000000-0000-0000-0000-000000000001'),NOW)
        self.assertEqual(card.source,'Торги Федерации')
        card=commercial_card(row(source='Фабрикант',url='https://www.fabrikant.ru/v2/trades/procedure/view/synthetic'),NOW)
        self.assertEqual(card.source,'Фабрикант')


class PlainTextReportTests(unittest.TestCase):
    def test_unknowns_are_readable_and_message_does_not_claim_delivery(self):
        text=render_report(report([row(price='Цена не указана',deadline='')]),SCOPE)
        self.assertIn('Результат неполный',text)
        self.assertIn('Цена: не указана',text)
        self.assertIn('Подача до: не указана',text)
        self.assertIn('место работ не подтверждено',text)
        self.assertIn('Организатор:',text)
        self.assertNotIn('Заказчик: Тестовый организатор',text)
        self.assertNotIn('отправлено',text)

    def test_other_company_cannot_render_private_report(self):
        with self.assertRaises(ValueError):render_report(report(),Scope(38,'fixture-owner'))
        with self.assertRaises(ValueError):render_report(report(),Scope(37,'another-owner'))

    def test_limit_discloses_omissions_and_never_cuts_links(self):
        rows=[row(id=str(i),url=f'https://www.b2b-center.ru/market/synthetic/tender-{i}/') for i in range(20)]
        text=render_report(report(rows),SCOPE,max_chars=1500)
        self.assertLessEqual(len(text),1500)
        self.assertIn('не показано записей',text)
        for line in text.splitlines():
            if line.startswith('https://'):self.assertTrue(line.endswith('/'))

    def test_verified_empty_and_failed_empty_are_not_worded_as_no_tenders_exist(self):
        text=render_report(report([],sources=[]),SCOPE)
        self.assertIn('не доказывает отсутствие закупок',text)
        self.assertIn('B2B-Center: не проверен',text)


if __name__=='__main__':unittest.main()
