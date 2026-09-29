"""Read-only recognition preview using authorized file IDs, never client URLs."""
from typing import Annotated, Dict, List, Literal, Optional

import psycopg2.extras
from fastapi import Depends, Header, HTTPException, Path, Response
from pydantic import BaseModel, ConfigDict, Field

from .contract_extraction import extract_contract_parties
from .contract_text_source import read_contract_text
from .review_context import build_contract_review_context
from .routes import MAX_ID


class RecognitionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sourceFileId: int = Field(strict=True, gt=0, le=MAX_ID)
    partyVersion: int = Field(strict=True, gt=0, le=MAX_ID)
    expectedVersion: int = Field(strict=True, ge=0, le=MAX_ID)


class SuggestedField(BaseModel):
    value: str
    line: int
    quote: str


class SuggestedParty(BaseModel):
    status: Literal['matched', 'missing', 'ambiguous', 'identity_mismatch']
    fields: Dict[str, SuggestedField]
    warnings: List[str]


class RecognitionResponse(RecognitionRequest):
    offerId: int
    companyId: int
    sourceContentHash: str
    source: Literal['labelled_text']
    parties: Dict[Literal['buyer', 'payer', 'supplier'], SuggestedParty]
    warnings: List[str]
    reviewConfirmed: Literal[False]
    appliedToAccounting: Literal[False]


def build_contract_recognition(deps):
    """Return verified preview and private source metadata; never persist either."""
    load_context = build_contract_review_context(deps)

    def load_source(offer_id, company_id, file_id):
        conn = deps['get_db']()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        try:
            cur.execute('''SELECT id,company_id,project_id,file_url,storage_key,context,original_name,
                           COALESCE(deletion_status,'active') AS deletion_status
                           FROM file_ownership WHERE id=%s''', (file_id,))
            row = cur.fetchone()
            if not row or row['company_id'] != company_id or row['deletion_status'] != 'active':
                raise HTTPException(403, 'Нет доступа к активному файлу договора')
            if row['project_id']:
                cur.execute('''SELECT p.id FROM projects p
                    JOIN supply_requests r ON r.project=p.name AND r.company_id=p.company_id
                    JOIN supplier_offers o ON o.request_id=r.id AND o.company_id=r.company_id
                    WHERE p.id=%s AND p.company_id=%s AND o.id=%s''',
                            (row['project_id'], company_id, offer_id))
                if not cur.fetchone():
                    raise HTTPException(403, 'Файл относится к другому объекту')
            return dict(row)
        finally:
            cur.close()
            conn.close()

    def recognize(id, data, current_user, x_company_id=None, x_company_mode=None):
        context = load_context(id, current_user, x_company_id, x_company_mode)
        if context['partyVersion'] != data.partyVersion or context['expectedVersion'] != data.expectedVersion:
            raise HTTPException(409, 'Состав сторон или версия договора изменились. Обновите карточку')
        row = load_source(id, context['companyId'], data.sourceFileId)
        text, digest = read_contract_text(row, deps)
        result = extract_contract_parties(text, {side: context[side]['inn'] for side in ('buyer', 'payer', 'supplier')})
        # Reads do not reserve membership, parties or files. Recheck after storage I/O;
        # later contract POST still performs its own authoritative validation.
        if (load_context(id, current_user, x_company_id, x_company_mode) != context
                or load_source(id, context['companyId'], data.sourceFileId) != row):
            raise HTTPException(409, 'Данные сделки или исходного файла изменились. Повторите распознавание')
        return {**result, **data.model_dump(), 'offerId': id, 'companyId': context['companyId'],
                'sourceContentHash': digest}, row

    return recognize


def register_contract_recognition(app, deps):
    recognize = build_contract_recognition(deps)

    @app.post('/supplier-offers/{id}/contract-recognition', response_model=RecognitionResponse)
    def preview(
        id: Annotated[int, Path(gt=0, le=MAX_ID)], data: RecognitionRequest, response: Response,
        current_user: dict = Depends(deps['get_current_user']),
        x_company_id: Annotated[Optional[str], Header(alias='X-Company-Id')] = None,
        x_company_mode: Annotated[Optional[str], Header(alias='X-Company-Mode')] = None,
    ):
        response.headers['Cache-Control'] = 'private, no-store'
        result, _ = recognize(id, data, current_user, x_company_id, x_company_mode)
        return result

    return recognize
