"""Production blocker UX and canonical legal matching must survive integration."""
import unittest
from unittest.mock import Mock,patch
from . import duplicate_merge as merge
from ..supplier_access.legal_identity import legal_sql

class ProductionSupplierIntegrationTests(unittest.TestCase):
    def test_registered_competitor_lookup_uses_canonical_inn(self):
        cur=Mock();cur.fetchone.side_effect=[None,(1,)]
        reason=merge.inn_completion_blocker(cur,2,20,'77- 11223344')
        sql,args=cur.execute.call_args.args
        self.assertIn(legal_sql('inn',(10,12)),sql)
        self.assertEqual(args,('7711223344',20))
        self.assertIn('другой кабинет',reason)

    def test_shared_cabinet_stops_before_global_identity_lookup(self):
        cur=Mock();cur.fetchone.return_value=(1,)
        self.assertIn('другими организациями',merge.inn_completion_blocker(cur,2,20,'7711223344'))
        self.assertEqual(cur.execute.call_count,1)

    def test_blocker_is_explained_in_preview_and_changes_review_version(self):
        actor=dict(id=1,role='platform_admin',active=True,supplier_team_epoch=0)
        suppliers={10:dict(inn='77- 11223344',ogrn='',user_id=None),20:dict(inn='',ogrn='',user_id=7)}
        with patch.object(merge,'company_lock',return_value={'id':2,'active':True}),patch.object(merge,'source_link'),patch.object(merge,'authorities',return_value=(suppliers,{1:actor})),patch.object(merge.company_merge,'preview',side_effect=lambda *args:{'hasSupplierAccount':True}),patch.object(merge,'inn_completion_blocker',side_effect=[None,'С этим ИНН уже есть другой кабинет. Нужна проверка реквизитов']):
            ready=merge.checked_preview(Mock(),actor,2,10,20)
            blocked=merge.checked_preview(Mock(),actor,2,10,20)
        self.assertTrue(ready['canCompleteInn'])
        self.assertFalse(blocked['canCompleteInn'])
        self.assertIn('другой кабинет',blocked['innCompletionBlocker'])
        self.assertNotEqual(ready['reviewVersion'],blocked['reviewVersion'])
