"""Attachment enrichment and validation of an explicit protected role review.

Document text never supplies commands or approves its own interpretation. This
module does not infer ownership from Customer/brand labels. A role review is a
server-side specialist binding to exact originals, not a model-facing argument
or an independent cadastral/legal audit.
"""
from dataclasses import dataclass, replace
from datetime import datetime
import re

from .b2b import extract_fields
from .documents import read_attachment, extract_isolated
from .model import Candidate, Fact, aware
from ..state import Scope


@dataclass(frozen=True)
class DirectReview:
    scope_key: str
    reviewer_subject: str
    reviewed_at: datetime
    procedure: Fact
    party: Fact
    party_id: Fact
    object_address: Fact
    role: Fact
    authority: Fact | None
    document_hashes: tuple[tuple[str,str], ...]


def valid_inn(value):
    if type(value) is not str or not re.fullmatch(r'[0-9]{10}|[0-9]{12}',value):return False
    digits=list(map(int,value))
    def check(weights):return sum(a*b for a,b in zip(digits,weights))%11%10
    if len(digits)==10:return check((2,4,10,3,5,9,4,6,8))==digits[9]
    return (check((7,2,4,10,3,5,9,4,6,8))==digits[10]
            and check((3,7,2,4,10,3,5,9,4,6,8))==digits[11])


def apply_review(candidate,review,scope,*,now,hosts):
    if (type(scope) is not Scope or type(review) is not DirectReview or review.scope_key!=scope.key()
            or type(review.reviewer_subject) is not str
            or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_:.@-]{0,127}',review.reviewer_subject)
            or not aware(review.reviewed_at) or not aware(now)
            or review.reviewed_at>now):raise ValueError('protected_scoped_direct_review_required')
    documents=candidate.validate(now,hosts)
    required=(review.procedure,review.party,review.party_id,review.object_address,review.role)
    if review.authority is not None:required+= (review.authority,)
    hashes=dict(review.document_hashes)
    if len(hashes)!=len(review.document_hashes):raise ValueError('unique_review_document_hashes_required')
    for fact in required:
        if type(fact) is not Fact:raise ValueError('review_evidence_required')
        doc=documents.get(fact.document)
        if (doc is None or doc.kind not in ('contract','authority') or not doc.complete
                or hashes.get(doc.id)!=doc.sha256 or not fact.quote or fact.quote not in doc.text
                or not fact.locator or fact.missing is not None):
            raise ValueError('review_original_changed_or_unverified')
    if (review.procedure.value!=candidate.number or not re.search(r'(?<![0-9])'+re.escape(candidate.number)+r'(?![0-9])',review.procedure.quote)
            or not review.party.value or review.party.value not in review.party.quote
            or not valid_inn(review.party_id.value)
            or not re.search(r'(?<![0-9])'+re.escape(review.party_id.value)+r'(?![0-9])',review.party_id.quote)
            or not review.object_address.value or review.object_address.value not in review.object_address.quote
            or review.role.value not in ('owner','authorized_operator','general_contractor')):
        raise ValueError('procedure_party_object_review_required')
    # All anchors need to agree with this exact candidate; matching only names
    # or a document URL is insufficient. No silent counterparty/address switch.
    addresses={fact.value for fact in candidate.facts.get('work_address',()) if fact.value}
    parties={fact.value for fact in candidate.facts.get('counterparty',()) if fact.value}
    if addresses!={review.object_address.value} or parties and parties!={review.party.value}:
        raise ValueError('review_candidate_identity_conflict')
    if review.role.value=='authorized_operator' and (review.authority is None or review.authority.value!='confirmed'):
        raise ValueError('operator_authority_evidence_required')
    facts={key:tuple(value) for key,value in candidate.facts.items()}
    for key,fact in (('counterparty',review.party),('counterparty_id',review.party_id),
                     ('procedure_id',review.procedure),('role',review.role),('authority',review.authority)):
        if fact is not None:facts[key]=tuple(dict.fromkeys((*facts.get(key,()),fact)))
    result=replace(candidate,facts=facts)
    result.validate(now,hosts)
    return result


@dataclass(frozen=True)
class Enrichment:
    candidate: Candidate
    statuses: tuple[dict, ...]


def enrich(candidate,references,scope,*,hosts,fetch,clock,extract=extract_isolated,review=None):
    if type(scope) is not Scope:raise ValueError('protected_document_scope_required')
    scope.key()
    now=clock();documents=candidate.validate(now,hosts)
    if len(references)>8 or len({ref.id for ref in references})!=len(references):
        raise ValueError('bounded_unique_attachment_references_required')
    facts={key:list(value) for key,value in candidate.facts.items()};statuses=[];extra=[]
    for ref in references:
        if ref.id in documents:raise ValueError('existing_document_identity_preserved')
        card=documents.get(ref.card_id)
        result=read_attachment(ref,card,hosts=hosts,fetch=fetch,clock=clock,extract=extract)
        statuses.append({'url':ref.url,'name':ref.name,'status':result.status})
        if result.document is None:
            missing=Fact(missing='Не удалось проверить')
            if missing not in facts.setdefault('documents',[]):facts['documents'].append(missing)
            continue
        extra.append(result.document)
        extracted=extract_fields(result.document)
        for key,entries in extracted.items():
            for fact in entries:
                # Preserve actual page/paragraph location as well as the label.
                block=next((row for row in result.blocks if fact.quote and fact.quote in row['text']),None)
                if block:fact=replace(fact,locator=block['locator']+'; '+fact.locator)
                if fact not in facts.setdefault(key,[]):facts[key].append(fact)
    result=replace(candidate,documents=(*candidate.documents,*extra),facts={key:tuple(value) for key,value in facts.items()})
    result.validate(clock(),hosts)
    if review is not None:result=apply_review(result,review,scope,now=clock(),hosts=hosts)
    return Enrichment(result,tuple(statuses))
