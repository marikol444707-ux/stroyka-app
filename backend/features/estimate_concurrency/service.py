"""Revision checks run inside the caller's authorized transaction, before effects."""
from fastapi import HTTPException


def _revision(row):
    return int(row['revision'] if isinstance(row, dict) else row[0])


def read_estimate_revision(cur, estimate_id, company_id):
    cur.execute('SELECT revision FROM estimates WHERE id=%s AND company_id=%s', (estimate_id, company_id))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, detail='Смета не найдена в выбранной компании')
    return _revision(row)


def require_estimate_revision(cur, estimate_id, company_id, data):
    # Ownership first: do not disclose another company's revision, even on bad input.
    cur.execute('SELECT revision FROM estimates WHERE id=%s AND company_id=%s FOR UPDATE', (estimate_id, company_id))
    row = cur.fetchone()
    if not row:
        raise HTTPException(404, detail='Смета не найдена в выбранной компании')
    expected = (data or {}).get('expectedRevision')
    if expected is None:
        raise HTTPException(428, detail={'code': 'estimate_revision_required', 'message': 'Загрузите актуальную смету перед сохранением.'})
    if type(expected) is not int or not 1 <= expected <= 9007199254740991:
        raise HTTPException(422, detail={'code': 'estimate_revision_invalid', 'message': 'Некорректная ожидаемая ревизия сметы.'})
    current = _revision(row)
    if expected != current:
        raise HTTPException(409, detail={
            'code': 'estimate_revision_conflict',
            'message': 'Смета уже изменена. Локальные правки сохранены в редакторе; загрузите и сравните актуальную смету перед повторным сохранением.',
            'expectedRevision': expected, 'currentRevision': current,
        })
    return expected
