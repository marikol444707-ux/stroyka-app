"""Reuse an unchanged checked original as part of approving a new offer."""
import hashlib
import json
from .access import build_deal_access
from .contract_applicability import offer_project
from .contract_registry import attach_registry
from .reusable_contracts import reusable_contracts

# Compare stored profile values, without inventing defaults for missing fields.
FIELDS = {'fullName':'full_name', 'inn':'inn', 'kpp':'kpp', 'ogrn':'ogrn',
          'legalAddress':'legal_address', 'bankName':'bank_name', 'bik':'bik',
          'rs':'rs', 'ks':'ks', 'directorName':'director_name',
          'directorPosition':'director_position', 'basis':'basis'}


def build_automatic_reuse(deps):
    company_actor, load_offer = build_deal_access(deps)

    def reuse(cur, offer_id, user, header_id=None, header_mode=None):
        offer, actor = load_offer(cur, offer_id, user, 'update', header_id, header_mode)
        if offer['status'] != 'Утверждено':
            return None
        cur.execute('SELECT pg_advisory_xact_lock(73164,%s)', (offer['company_id'],))
        cur.execute('SELECT id FROM supplier_contract_versions WHERE offer_id=%s LIMIT 1', (offer_id,))
        if cur.fetchone():  # Repeated approval never replaces an existing contract.
            return None
        cur.execute('SELECT 1 FROM supplier_invoices WHERE offer_id=%s UNION ALL SELECT 1 FROM supply_deliveries WHERE offer_id=%s LIMIT 1', (offer_id,offer_id))
        if cur.fetchone():
            return None  # Issued documents keep their original contract state.
        cur.execute('SELECT * FROM supplier_deal_parties WHERE offer_id=%s ORDER BY version DESC LIMIT 1', (offer_id,))
        parties = cur.fetchone()
        buyer = parties['buyer_company_id'] if parties else offer['company_id']
        payer = parties['payer_company_id'] if parties else buyer
        for company in sorted({buyer, payer} - {offer['company_id']}):
            company_actor(cur, user, company, 'update')
        cur.execute('SELECT * FROM company_requisites WHERE company_id=ANY(%s) FOR SHARE', ([buyer,payer],))
        profiles = {r['company_id']:dict(r) for r in cur.fetchall()}
        cur.execute('SELECT * FROM suppliers WHERE id=%s FOR SHARE', (offer['supplier_id'],))
        supplier = cur.fetchone() or {}
        profiles = {'buyer':profiles.get(buyer,{}), 'payer':profiles.get(payer,{}),
                    'supplier':{**supplier,'full_name':supplier.get('name'),'bank_name':supplier.get('bank'),
                                'rs':supplier.get('account'),'ks':supplier.get('kor_account')}}
        identities = {side:{'inn':str(profile.get('inn') or '').strip()} for side,profile in profiles.items()}
        identities['buyer']['companyId']=buyer
        identities['payer']['companyId']=payer
        identities['supplier']['supplierId']=offer['supplier_id']
        project = offer_project(cur, offer)
        project_id = project['id'] if project else None
        candidates = reusable_contracts(cur,offer,identities,load_offer,user,header_id,header_mode,project_id,require_complete=True)
        if len(candidates)!=1:
            return None  # Missing/ambiguous contracts stay in the existing review flow.
        candidate=candidates[0]
        snapshot=candidate['snapshot']
        for side,profile in profiles.items():
            for field,column in FIELDS.items():
                current=str(profile.get(column) or '').strip()
                if current and current != str(snapshot.get(side,{}).get(field) or '').strip():
                    return None
        files=[candidate['sourceFileId']]+[a['sourceFileId'] for a in snapshot.get('addenda',[])]
        for file_id in sorted(set(files)):
            cur.execute("SELECT * FROM file_ownership WHERE id=%s AND company_id=%s FOR UPDATE", (file_id,offer['company_id']))
            file=cur.fetchone()
            if not file or (file.get('deletion_status') or 'active')!='active':
                return None
            if file.get('project_id') and (file['project_id']!=project_id or snapshot['applicability']['scope']!='project'):
                return None
        cur.execute('SELECT * FROM supplier_contract_versions WHERE id=%s AND company_id=%s', (candidate['id'],offer['company_id']))
        source=cur.fetchone()
        if not parties:
            cur.execute('''INSERT INTO supplier_deal_parties
                (offer_id,company_id,request_id,supplier_id,buyer_company_id,payer_company_id,
                 version,reason,created_by_id,created_by)
                VALUES (%s,%s,%s,%s,%s,%s,1,%s,%s,%s) RETURNING *''',
                (offer_id,offer['company_id'],offer['request_id'],offer['supplier_id'],buyer,payer,
                 'Покупатель и плательщик — компания заявки',actor['id'],actor.get('name') or ''))
            parties=cur.fetchone()
        saved_snapshot={**snapshot,'reusedFrom':{'contractId':source['id'],'offerId':source['offer_id'],
            'version':source['version'],'snapshotHash':source['snapshot_hash']}}
        encoded=json.dumps(saved_snapshot,sort_keys=True,ensure_ascii=False,separators=(',',':'))
        cur.execute('''INSERT INTO supplier_contract_versions
            (offer_id,company_id,party_version,version,source_file_id,snapshot_json,snapshot_hash,
             reason,reviewed_by_id,reviewed_by,reviewed_at)
            VALUES (%s,%s,%s,1,%s,%s::jsonb,%s,%s,%s,%s,%s) RETURNING *''',
            (offer_id,offer['company_id'],parties['version'],source['source_file_id'],encoded,
             hashlib.sha256(encoded.encode()).hexdigest(),'Автоматически выбран ранее проверенный договор',
             source['reviewed_by_id'],source['reviewed_by'],source['reviewed_at']))
        saved=cur.fetchone()
        attach_registry(cur,saved,parties,source)
        cur.execute('UPDATE file_ownership SET retained_at=COALESCE(retained_at,NOW()) WHERE id=ANY(%s)', (files,))
        return saved['id']
    return reuse
