"""Keep originals together in immutable reviewed contract snapshots."""
import datetime as dt
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

class Addendum(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    sourceFileId: int = Field(strict=True, gt=0, le=2147483647)
    number: str = Field(min_length=1, max_length=100)
    date: dt.date


def reviewed_addenda(cur, source, data, company_id, project):
    previous = source['snapshot_json'] if source else {}
    items = list(previous.get('addenda') or [])
    if items or data.addendum is not None:
        if source is None or source['source_file_id'] != data.sourceFileId:
            raise HTTPException(422, 'Сохраните основной договор при добавлении соглашения')
        if (data.number, data.date.isoformat()) != (previous.get('number'), previous.get('date')):
            raise HTTPException(422, 'Номер и дата основного договора должны сохраниться')
    if data.addendum is not None:
        item = data.addendum.model_dump(mode='json')
        if item['sourceFileId'] == data.sourceFileId or any(a['sourceFileId'] == item['sourceFileId'] for a in items):
            raise HTTPException(422, 'Загрузите отдельный файл нового допсоглашения')
        if item['date'] < data.date.isoformat():
            raise HTTPException(422, 'Дата допсоглашения раньше даты договора')
        if len(items) >= 100:
            raise HTTPException(422, 'В договоре уже 100 допсоглашений')
        items.append(item)
    for item in sorted(items, key=lambda a:a['sourceFileId']):
        cur.execute("SELECT company_id,project_id,COALESCE(deletion_status,'active') AS state FROM file_ownership WHERE id=%s FOR UPDATE", (item['sourceFileId'],))
        file = cur.fetchone()
        if not file or file['company_id'] != company_id or file['state'] != 'active':
            raise HTTPException(403, 'Нет доступа к файлу допсоглашения')
        if file['project_id'] and (not project or project['id'] != file['project_id']
                or data.applicability is None or data.applicability.scope != 'project'):
            raise HTTPException(422, 'Допсоглашение доступно только для своего объекта')
        cur.execute('UPDATE file_ownership SET retained_at=COALESCE(retained_at,NOW()) WHERE id=%s', (item['sourceFileId'],))
    return items
