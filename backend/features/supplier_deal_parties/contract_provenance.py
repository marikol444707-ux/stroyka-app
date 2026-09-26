"""Server-derived evidence for explicitly accepted fields at contract save time."""
from typing import List, Literal

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .contract_recognition import RecognitionRequest


class AcceptedField(BaseModel):
    model_config = ConfigDict(extra='forbid')
    side: Literal['buyer', 'payer', 'supplier']
    field: Literal['fullName', 'kpp', 'ogrn', 'legalAddress', 'bankName', 'bik',
                   'rs', 'ks', 'directorName', 'directorPosition', 'basis', 'phone', 'email']


class RecognitionReview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    sourceContentHash: str = Field(strict=True, pattern=r'^[a-f0-9]{64}$')
    acceptedFields: List[AcceptedField] = Field(min_length=1, max_length=39)

    @field_validator('acceptedFields')
    @classmethod
    def unique_fields(cls, fields):
        if len({(item.side, item.field) for item in fields}) != len(fields):
            raise ValueError('Реквизиты не должны повторяться')
        return fields


def prepare_contract_provenance(deps, offer_id, review, user, company_header, mode_header):
    """Authorize and read before write locks. The caller must recheck row metadata."""
    selection = review.recognitionReview
    if selection is None:
        return None, None
    recognize = deps.get('recognize_contract')
    if recognize is None:
        raise HTTPException(503, 'Проверка источника распознанных реквизитов выключена')
    request = RecognitionRequest(sourceFileId=review.sourceFileId,
                                 partyVersion=review.partyVersion, expectedVersion=review.expectedVersion)
    result, source_row = recognize(offer_id, request, user, company_header, mode_header)
    if result['sourceContentHash'] != selection.sourceContentHash:
        raise HTTPException(409, 'Содержимое договора изменилось. Повторите распознавание и проверку')
    evidence = []
    for selected in sorted(selection.acceptedFields, key=lambda item: (item.side, item.field)):
        party = result['parties'][selected.side]
        item = party['fields'].get(selected.field)
        if (party['status'] != 'matched' or not item
                or item['value'] != getattr(getattr(review, selected.side), selected.field)):
            raise HTTPException(409, 'Принятый реквизит не совпадает с источником. Повторите проверку')
        evidence.append({'side': selected.side, 'field': selected.field,
                         'value': item['value'], 'line': item['line'], 'quote': item['quote']})
    return {'schemaVersion': 1, 'source': 'labelled_text', 'sourceFileId': review.sourceFileId,
            'sourceContentHash': result['sourceContentHash'], 'acceptedFields': evidence}, source_row
