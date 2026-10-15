"""Company-local, exact invoice denials; never rewrite business documents."""
import json

from fastapi import HTTPException

MODE='revoke_invoice_access'
PROFILE_KEY='closedStandaloneInvoiceIds'


class ClosedInvoiceAccess:
    """SELECT-only projection composed with the addressed-recipient projection."""
    def __init__(self,cur,recipients,company,target,invoices,*,contracts=None):
        self.cur,self.recipients,self.company,self.target,self.invoices=cur,recipients,company,target,invoices
        self.profile={PROFILE_KEY:invoices}
        if contracts is not None:self.profile['closedContractVersionIds']=contracts

    def execute(self,query,params=None):
        if not isinstance(query,str) or not query.lstrip().upper().startswith('SELECT '):
            raise ValueError('Invoice projection accepts SELECT statements only')
        self.cur.execute('''WITH supply_request_recipients AS (
            SELECT (jsonb_populate_record(NULL::public.supply_request_recipients,to_jsonb(r) ||
                CASE WHEN r.id=ANY(%s) THEN '{"visible_to_supplier":false}'::jsonb ELSE '{}'::jsonb END)).*
            FROM public.supply_request_recipients r), company_supplier_links AS (
            SELECT (jsonb_populate_record(NULL::public.company_supplier_links,to_jsonb(l) ||
                CASE WHEN l.company_id=%s AND l.supplier_id=%s THEN jsonb_build_object('profile',
                    COALESCE(l.profile,'{}'::jsonb) || %s::jsonb) ELSE '{}'::jsonb END)).*
            FROM public.company_supplier_links l) '''+query,
            [self.recipients,self.company,self.target,json.dumps(self.profile)]+list(params or []))

    def __getattr__(self,key):return getattr(self.cur,key)


def direct_ids(plan):
    return plan.get('closedStandaloneInvoiceIds',[])


def verify_replay(cur,company,target,plan):
    cur.execute('SELECT profile FROM company_supplier_links WHERE company_id=%s AND supplier_id=%s',(company,target))
    row=cur.fetchone()
    if not row or (row['profile'] or {}).get(PROFILE_KEY)!=direct_ids(plan):
        raise HTTPException(409,'Список закрытых счетов изменился. Нужна новая проверка доступа')
