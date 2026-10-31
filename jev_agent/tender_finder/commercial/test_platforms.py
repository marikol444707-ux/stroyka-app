"""Synthetic per-platform fixtures; no claim of live source coverage."""
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import parse_qs,urlsplit

from .b2b import Observation
from .model import Profile,Document
from .platforms import PortalSpec,platform_specs,listing_urls,parse_primary,LISTING_JS
from .portal_reader import collect_portal,source_bundle,portal_adapter
from .policy import assess
from .runner import run
from .sources import Source
from .test_commercial import NOW,SCOPE,candidate,HOSTS

TEXT='''Закупка № fixture-123
Наименование закупки: Капитальный ремонт кровли
Место выполнения работ: Краснодарский край, г. Сочи
Состав работ: Капитальный ремонт кровли
Текущий этап: Приём предложений
Бюджет: 5 000 000 RUB
Дата окончания подачи заявок: 15.11.2026 12:00
Правовой режим: Коммерческая закупка
'''
CARDS={
    'fabrikant':'https://www.fabrikant.ru/v2/trades/procedure/view/fixture-123',
    'tektorg':'https://www.tektorg.ru/223-fz/procedures/123',
    'gpb':'https://etpgpb.ru/procedures/fixture/123.1/',
    'roseltorg':'https://www.roseltorg.ru/procedure/fixture/123',
    'sber':'https://utp.sberbank-ast.ru/VIP/NBT/PurchaseView/1/2/3/123',
    'federation':'https://etpp.ru/tenders/00000000-0000-0000-0000-000000000123',
    'rtender':'https://etp.r-tender.ru/app/LotCard/page?LotCard.lotEntity=LT%3Afixture123',
}


class PlansTests(unittest.TestCase):
    def test_all_seven_native_plans_plus_b2b_are_bound_together(self):
        sources,adapters=source_bundle(open_browser=lambda _:None,clock=lambda:NOW)
        self.assertEqual(set(adapters),set(CARDS)|{'b2b'})
        self.assertEqual(len(sources),22)
        self.assertNotIn('tenderpro',adapters)
        self.assertNotIn('ozon',adapters)

    def test_customer_region_filters_are_not_used_as_worksite_filters(self):
        specs=platform_specs(Profile(),NOW)
        for spec in specs.values():
            for url in spec.listings:
                query=parse_qs(urlsplit(url).query)
                self.assertNotIn('region[]',query)
                self.assertNotIn('customer_region_ids[]',query)
                self.assertNotIn('procedure[regions][0]',query)
        rosel=specs['roseltorg']
        self.assertIn('Краснодарский край',rosel.terms)
        self.assertIn('Ставропольский край',rosel.terms)

    def test_every_native_notice_family_is_allowed_and_foreign_paths_blocked(self):
        for key,spec in platform_specs(Profile(),NOW).items():
            self.assertEqual(spec.approve(CARDS[key]),'card')
            for url in ('https://attacker.example/file','https://'+spec.source.hosts[0]+'/login/'):
                with self.assertRaises(ValueError):spec.approve(url)

    def test_listing_metadata_never_establishes_authoritative_primary_fields(self):
        spec=platform_specs(Profile(),NOW)['roseltorg']
        urls=listing_urls(spec,spec.listings[0],{'url':spec.listings[0],'links':[CARDS['roseltorg']],
            'region':'Ставропольский край','deadline':'2099-01-01','role':'owner'})
        self.assertEqual(urls,[CARDS['roseltorg']])
        doc=Document('card','roseltorg',urls[0],'Карточка','card',NOW,TEXT)
        row=assess(parse_primary(doc,'roseltorg'),NOW,{'roseltorg':spec.source.hosts})
        self.assertEqual(row['values']['work_region'],'Краснодарский край')
        self.assertNotIn('role',row['values'])
        self.assertEqual(row['values']['deadline'],'15.11.2026 12:00')

    def test_unknown_or_conflicting_primary_numbers_are_not_inferred_from_slug(self):
        for text in ('Кровельные работы без номера','Закупка № 123\nТендер № 124'):
            doc=Document('card','fabrikant',CARDS['fabrikant'],'Карточка','card',NOW,text)
            with self.assertRaises(ValueError):parse_primary(doc,'fabrikant')

    def test_gpb_json_discovers_primary_urls_without_copying_inferred_timezone(self):
        spec=platform_specs(Profile(),NOW)['gpb'];url=spec.listings[0]
        row={'id':'123','attributes':{'title':'Кровельные работы','rebranding_truncated_path':'/procedures/fixture/123.1/',
              'end_registration':'2026-11-15T12:00:00','section_category_name':'Закупки.Бизнес'}}
        links=listing_urls(spec,url,{'url':url,'links':[],'text':json.dumps({'data':[row]})})
        self.assertEqual(links,[CARDS['gpb']])
        parsed=parse_primary(Document('card','gpb',links[0],'Карточка','card',NOW,TEXT),'gpb')
        self.assertEqual(parsed.facts['deadline'][0].value,'15.11.2026 12:00')

    def test_tektorg_ssr_uses_verified_shape_and_discards_listing_region_claims(self):
        spec=platform_specs(Profile(),NOW)['tektorg'];url=spec.listings[0]
        row={'id':'123','registryNumber':'fixture-123','title':'Кровельные работы',
             'dates':{},'statusName':'Приём заявок'}
        props={'meta':{'title':'223-ФЗ и коммерческие закупки'},'initialReduxState':{
            'listingProcedures':{'data':[row],'total':1,'totalPages':1,'status':'success',
                                 'sectionsCodes':{'sectionsCodes[0]':'zakupki'}}}}
        links=listing_urls(spec,url,{'url':url,'links':[],'next':json.dumps({'props':{'pageProps':props}})})
        self.assertEqual(links,[CARDS['tektorg']])

    def test_sber_rendered_filter_and_first_party_notice_are_checked(self):
        spec=platform_specs(Profile(),NOW)['sber'];url=spec.listings[0];term=spec.terms[0]
        query=json.loads(parse_qs(urlsplit(url).query)['query'][0])
        dates=query['requestEndDate']
        state={'url':url,'rows':[{'url':CARDS['sber'],'source':'Торги коммерческих заказчиков'}],
            'page_state':'Торги коммерческих заказчиков Строка поиска: '+term+' '+dates['startRequestDate']+' - '+dates['endRequestDate']}
        self.assertEqual(listing_urls(spec,url,state),[CARDS['sber']])
        with self.assertRaises(ValueError):listing_urls(spec,url,{**state,'page_state':'Не тот раздел'})

    def test_rtender_public_json_requires_commercial_active_procedure_shape(self):
        spec=platform_specs(Profile(),NOW)['rtender'];url=spec.listings[0]
        row={'type':'BUYING_COMMERCIAL','state':{'code':'PurchaseLot_St_Dmnds_Started','title':'Прием предложений'},
             'identifier':'fixture-123','uuid':'fixture123','lotLink':CARDS['rtender'],
             'title':'Кровля','organizer':{'title':'Синтетический организатор'}}
        payload={'list':[row],'count':1,'totalCount':1}
        self.assertEqual(listing_urls(spec,url,{'url':url,'text':json.dumps(payload)}),[CARDS['rtender']])
        with self.assertRaises(RuntimeError):listing_urls(spec,url,{'url':url,'text':json.dumps({**payload,'count':2})})


class CollectionTests(unittest.TestCase):
    def read(self,spec,urls):
        def read(url):
            if url in spec.listings:return Observation(url,'ok',NOW,'Выдача',{'url':url,'notice_urls':urls})
            return Observation(url,'ok',NOW,TEXT)
        return read

    def test_same_core_collects_every_native_platform_from_primary_pages(self):
        for key,spec in platform_specs(Profile(queries=('кровля',)),NOW).items():
            calls=[];bound=self.read(spec,[CARDS[key],CARDS[key]])
            def read(url):calls.append(url);return bound(url)
            result=collect_portal(spec,read=read,clock=lambda:NOW)
            self.assertEqual(len(result.candidates),1,key)
            self.assertEqual(result.candidates[0].source,key)
            self.assertEqual(result.candidates[0].number,'fixture-123')
            self.assertEqual(calls.count(CARDS[key]),1)
            self.assertEqual(result.status,'partial')

    def test_selected_trade_filter_rejects_unrelated_work(self):
        row=assess(candidate(),NOW,HOSTS,Profile(queries=('электроснабжение',)))
        self.assertIn('Работы не соответствуют выбранным направлениям',row['exclusions'])
        row=assess(candidate({'title':'Кровельные работы','work_scope':'Капитальный ремонт здания'}),NOW,HOSTS,
                   Profile(queries=('кровля',)))
        self.assertNotIn('Работы не соответствуют выбранным направлениям',row['exclusions'])

    def test_captcha_and_stale_results_are_not_empty_success(self):
        spec=platform_specs(Profile(),NOW)['roseltorg']
        result=collect_portal(spec,read=lambda url:Observation(url,'captcha',NOW),clock=lambda:NOW)
        self.assertEqual(result.status,'captcha')
        result=collect_portal(spec,read=lambda url:Observation(url,'ok',NOW-timedelta(days=1),'старое'),clock=lambda:NOW)
        self.assertEqual(result.status,'error')

    def test_whole_batch_deadline_skips_remaining_sources_without_search(self):
        specs=platform_specs(Profile(),NOW);spec=specs['roseltorg'];calls=[];ticks=iter((0,601))
        with tempfile.TemporaryDirectory() as directory:
            report=run('fixture-budget',SCOPE,directory,sources={'roseltorg':spec.source},
                adapters={'roseltorg':lambda *_:calls.append(True)},clock=lambda:NOW,monotonic=lambda:next(ticks))
        self.assertEqual(calls,[])
        self.assertEqual(report['coverage'][0]['status'],'not_checked_due_budget')


class RecipeTests(unittest.TestCase):
    def test_reviewed_custom_portal_recipe_joins_same_batch(self):
        source=Source('ozon','Ozon','owner',('owner.example',))
        def recipe(profile,now):return PortalSpec(source,('https://owner.example/procurement',),(None,),
                                                notice_pattern=r'/notices/[0-9]+',planned_at=now)
        sources,adapters=source_bundle(open_browser=lambda _:None,clock=lambda:NOW,
                                      reviewed_recipes={'ozon':recipe})
        self.assertEqual(sources['ozon'],source)
        self.assertIn('ozon',adapters)

    def test_recipe_cannot_replace_native_reader_or_mislabel_owner(self):
        with self.assertRaises(ValueError):source_bundle(open_browser=lambda _:None,clock=lambda:NOW,
                                                       reviewed_recipes={'b2b':lambda *_:None})
        with self.assertRaises(ValueError):source_bundle(open_browser=lambda _:None,clock=lambda:NOW,
            reviewed_recipes={'ozon':lambda *_:PortalSpec(Source('other','Other','owner',('x.example',)),(),())})

    def test_generic_browser_context_uses_same_scoped_pipeline(self):
        spec=platform_specs(Profile(),NOW)['roseltorg'];state={};closed=[]
        @asynccontextmanager
        async def browser(source):
            self.assertEqual(source.id,'roseltorg')
            async def call(method,args):
                if method=='Page.navigate':state['url']=args['url'];return {}
                url=state['url']
                if args['expression']==LISTING_JS:return {'result':{'value':{'url':url,'links':[CARDS['roseltorg']]}}}
                return {'result':{'value':{'url':url,'ready':'complete','oversize':False,'text':TEXT,'links':[]}}}
            try:yield call
            finally:closed.append(True)
        factory=lambda profile,now:replace(spec,planned_at=now)
        result=portal_adapter(factory,open_browser=browser,clock=lambda:NOW,scope=SCOPE)(Profile(),NOW)
        self.assertEqual(len(result.candidates),1)
        self.assertEqual(closed,[True])


if __name__=='__main__':unittest.main()
