"""Two managers, independent buyers and a revoked draft on disposable PG."""
import os
import unittest

from .test_customer_team_postgres import CustomerTeamPostgresTests as Base
from ..supplier_access.test_multicompany_chain import MultiCompanyChainTest


@unittest.skipUnless(os.getenv('SUPPLY_CHAIN_RUN_POSTGRES') == '1', 'isolated PostgreSQL opt-in')
class ManagerRevocationPostgresTests(unittest.TestCase):
    sql, api, quote, command = Base.sql, Base.api, Base.quote, Base.command

    @classmethod
    def setUpClass(cls):
        Base.setUpClass.__func__(cls)

    def seed_managers(self):
        project = MultiCompanyChainTest.seed_second_customer(self)
        offer_a, path, body = self.quote()
        request_b, offer_b = MultiCompanyChainTest.create_offer(self, 'stranger', 3, project)
        user = self.sql("""INSERT INTO users(name,email,role,active)
            VALUES('TEAM second manager','second-manager@local.invalid','поставщик',TRUE)
            RETURNING id""")[0][0]
        self.fixture['users']['manager_b'] = dict(id=user, role='поставщик', name='TEAM second manager',
                                                email='second-manager@local.invalid')
        member = self.sql("""INSERT INTO supplier_team_members(supplier_id,user_id,role)
            VALUES(%s,%s,'manager') RETURNING id""", (self.fixture['supplierId'], user))[0][0]
        assignment = self.command('assign_customer', companyId=2, memberId=self.member_id, version=0)
        self.command('assign_customer', companyId=3, memberId=member, version=0)
        return dict(offerA=offer_a['id'], requestA=offer_a['requestId'], offerB=offer_b, requestB=request_b,
                    memberA=self.member_id, memberB=member, assignmentVersion=assignment['version'],
                    path=path, body=body)

    def test_two_managers_reassignment_revokes_cached_draft_and_reenable_keeps_assignments_empty(self):
        row = self.seed_managers()
        self.assertEqual([r['id'] for r in self.api('manager', 'GET', '/supplier-offers')], [row['offerA']])
        self.assertEqual([r['id'] for r in self.api('manager_b', 'GET', '/supplier-offers')], [row['offerB']])
        self.assertEqual([r['id'] for r in self.api('manager', 'GET', '/supplier-team/customers')], [2])
        self.assertEqual([r['id'] for r in self.api('manager_b', 'GET', '/supplier-team/customers')], [3])
        before = self.sql('SELECT to_jsonb(o) FROM supplier_offers o WHERE id=%s', (row['offerA'],))
        events = self.sql('SELECT count(*) FROM supplier_offer_events WHERE offer_id=%s', (row['offerA'],))
        self.command('assign_customer', companyId=2, memberId=row['memberB'], version=row['assignmentVersion'])
        self.api('manager', 'PUT', row['path'], row['body'], expected=403)
        self.assertEqual(self.api('manager', 'GET', '/supplier-offers'), [])
        self.assertEqual(self.api('manager', 'GET', '/supplier-team/customers'), [])
        self.assertTrue({row['offerA'], row['offerB']} <= {r['id'] for r in self.api('manager_b', 'GET', '/supplier-offers')})
        disabled = self.command('member_active', memberId=row['memberB'], version=1, active=False,
                                reason='Смена ответственного в синтетическом сценарии')
        self.assertEqual(set(disabled['releasedCompanyIds']), {2, 3})
        self.api('manager_b', 'PUT', row['path'], row['body'], expected=403)
        self.command('member_active', memberId=row['memberB'], version=disabled['version'], active=True)
        self.assertEqual(self.api('manager_b', 'GET', '/supplier-offers'), [])
        self.assertEqual(self.api('manager_b', 'GET', '/supplier-team/customers'), [])
        self.assertTrue({row['offerA'], row['offerB']} <= {r['id'] for r in self.api('supplier', 'GET', '/supplier-offers')})
        self.assertEqual(self.sql('SELECT to_jsonb(o) FROM supplier_offers o WHERE id=%s', (row['offerA'],)), before)
        self.assertEqual(self.sql('SELECT count(*) FROM supplier_offer_events WHERE offer_id=%s', (row['offerA'],)), events)
        self.assertEqual(self.sql('SELECT count(*) FROM user_company_roles WHERE user_id=%s',
                                 (self.fixture['users']['manager_b']['id'],)), [(0,)])
