"""Read immutable act balances only for already-authorized contract/company pairs."""

def read_settlement_summaries(cur, contracts):
    if not contracts:
        return {}
    cur.execute('''SELECT a.contract_id,a.company_id,COUNT(*),SUM(a.gross_amount),
        SUM(a.fine_amount),SUM(a.net_amount),SUM(COALESCE(p.paid,0)),
        SUM(a.net_amount-COALESCE(p.paid,0)),
        COUNT(*) FILTER(WHERE COALESCE(s.scan_url,'')='')
        FROM work_contract_acts a
        LEFT JOIN work_contract_act_signatures s ON s.act_id=a.act_id
        LEFT JOIN LATERAL (
            SELECT SUM(bp.amount) AS paid FROM work_contract_act_payments l
            JOIN brigade_payments bp ON bp.id=l.payment_id
                AND bp.company_id=a.company_id AND bp.contract_id=a.contract_id
            WHERE l.act_id=a.act_id
        ) p ON TRUE
        WHERE (a.contract_id,a.company_id) IN
            (SELECT * FROM unnest(%s::integer[],%s::integer[]))
        GROUP BY a.contract_id,a.company_id''',
        ([pair[0] for pair in contracts], [pair[1] for pair in contracts]))
    summaries = {pair: dict(actCount=0, grossAmount=0, fineAmount=0,
                           netAmount=0, paidAmount=0, remainingAmount=0, unsignedActCount=0)
                 for pair in contracts}
    for row in cur.fetchall():
        pair = (row[0], row[1])
        if pair in summaries:
            summaries[pair] = dict(zip(
                ('actCount','grossAmount','fineAmount','netAmount','paidAmount','remainingAmount','unsignedActCount'),
                (int(row[2]), *(float(value or 0) for value in row[3:8]), int(row[8]))))
    cur.execute('''SELECT bc.id,bc.company_id FROM brigade_contracts bc
        WHERE (bc.id,bc.company_id) IN
            (SELECT * FROM unnest(%s::integer[],%s::integer[]))
        AND (EXISTS(SELECT 1 FROM brigade_payments bp
            WHERE bp.contract_id=bc.id AND bp.company_id=bc.company_id
            AND NOT EXISTS(SELECT 1 FROM work_contract_act_payments l WHERE l.payment_id=bp.id))
        OR EXISTS(SELECT 1 FROM brigade_acts b WHERE b.contract_id=bc.id
            AND COALESCE(b.status,'')<>'Аннулирован'
            AND NOT EXISTS(SELECT 1 FROM work_contract_acts a WHERE a.act_id=b.id)))''',
        ([pair[0] for pair in contracts], [pair[1] for pair in contracts]))
    for row in cur.fetchall():
        if (row[0], row[1]) in summaries:
            summaries[(row[0], row[1])]['needsReconciliation'] = True
    return summaries
