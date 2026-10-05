"""Conditions for archiving a legacy signed brigade contract with no activity."""

from fastapi import HTTPException


def require_empty_signed_duplicate(cur, contract):
    if contract.get("status") != "Подписан":
        return
    if contract.get("partySnapshot") is not None or contract.get("contractScanUrl") or contract.get("actScanUrl"):
        raise HTTPException(409, "Подписанный документ хранится в истории и не удаляется")

    for table in ("brigade_contract_items", "brigade_payments", "brigade_acts", "interim_acts"):
        cur.execute(f"SELECT 1 FROM {table} WHERE contract_id=%s LIMIT 1", (contract["id"],))
        if cur.fetchone():
            raise HTTPException(409, "У договора есть работы или расчёты. Убрать его нельзя")

    identity_sql = "peer.contractor_id=%s"
    identity_params = (contract["contractorId"],)
    if not contract.get("contractorId"):
        identity_sql = "peer.contractor_id IS NULL AND LOWER(BTRIM(peer.brigade_name))=LOWER(BTRIM(%s))"
        identity_params = (contract["brigadeName"],)
    cur.execute(
        "SELECT 1 FROM brigade_contracts peer "
        "WHERE peer.company_id=%s AND peer.project_id=%s "
        "AND COALESCE(NULLIF(peer.work_package,''),'Основная')=%s "
        "AND peer.id<>%s AND peer.status='Подписан' "
        f"AND {identity_sql} "
        "AND EXISTS (SELECT 1 FROM brigade_contract_items item WHERE item.contract_id=peer.id) "
        "LIMIT 1 FOR UPDATE",
        (contract["companyId"], contract["projectId"], contract["workPackage"], contract["id"], *identity_params),
    )
    if not cur.fetchone():
        raise HTTPException(409, "Не найден действующий договор с работами для замены пустого дубля")
