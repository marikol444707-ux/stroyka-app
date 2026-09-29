"""Explicit source payments for atomic refund/allocation revisions. No backfill."""
from alembic import op
revision = '0059_supplier_refund_allocations'
down_revision = '0058_supplier_paired_openings'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('''CREATE TABLE supplier_refund_guard_versions(name TEXT PRIMARY KEY, definition TEXT NOT NULL)''')
    for name in ('supplier_payment_impact_guard', 'supplier_settlement_allocation_guard'):
        op.execute(f"INSERT INTO supplier_refund_guard_versions VALUES('{name}',pg_get_functiondef('{name}()'::regprocedure))")
    op.execute('''CREATE TABLE supplier_payment_refund_links (
        refund_operation_id BIGINT PRIMARY KEY, payment_operation_id BIGINT NOT NULL,
        company_id INTEGER NOT NULL, group_id BIGINT NOT NULL, revision_id BIGINT NOT NULL UNIQUE,
        fingerprint TEXT NOT NULL CHECK(fingerprint ~ '^[0-9a-f]{64}$'),
        FOREIGN KEY(refund_operation_id,company_id) REFERENCES supplier_payment_operations(id,company_id),
        FOREIGN KEY(payment_operation_id,company_id) REFERENCES supplier_payment_operations(id,company_id),
        FOREIGN KEY(revision_id,group_id,company_id) REFERENCES supplier_payment_allocation_revisions(id,group_id,company_id),
        CHECK(refund_operation_id<>payment_operation_id)
    )''')
    op.execute('CREATE INDEX supplier_refund_source ON supplier_payment_refund_links(payment_operation_id)')
    op.execute('CREATE INDEX supplier_refund_group ON supplier_payment_refund_links(group_id)')
    op.execute('''CREATE TRIGGER refund_link_immutable BEFORE UPDATE OR DELETE ON supplier_payment_refund_links
        FOR EACH ROW EXECUTE FUNCTION supplier_payment_immutable()''')
    op.execute('''CREATE TRIGGER refund_link_no_truncate BEFORE TRUNCATE ON supplier_payment_refund_links
        FOR EACH STATEMENT EXECUTE FUNCTION supplier_payment_immutable()''')
    op.execute('''CREATE FUNCTION supplier_refund_link_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE r supplier_payment_operations; p supplier_payment_operations;
                h supplier_payment_allocation_revisions; d supplier_payment_documents;
        BEGIN
        PERFORM supplier_allocation_lock(NEW.company_id);
        SELECT * INTO r FROM supplier_payment_operations WHERE id=NEW.refund_operation_id;
        SELECT * INTO p FROM supplier_payment_operations WHERE id=NEW.payment_operation_id;
        SELECT * INTO h FROM supplier_payment_allocation_revisions WHERE id=NEW.revision_id;
        SELECT x.* INTO d FROM supplier_payment_allocation_groups g
            JOIN supplier_payment_documents x ON x.id=g.invoice_record_id WHERE g.id=NEW.group_id;
        IF r.id IS NULL OR p.id IS NULL OR h.id IS NULL OR d.id IS NULL
          OR r.kind<>'refund' OR p.kind<>'payment' OR r.document_kind<>'invoice'
          OR r.creation_xid IS DISTINCT FROM pg_current_xact_id()
          OR h.creation_xid IS DISTINCT FROM pg_current_xact_id()
          OR (r.company_id,r.payer_company_id,r.supplier_id,r.document_kind,r.document_id)
             IS DISTINCT FROM (p.company_id,p.payer_company_id,p.supplier_id,p.document_kind,p.document_id)
          OR (r.company_id,r.document_id) IS DISTINCT FROM (d.company_id,d.document_id)
          OR (h.company_id,h.group_id) IS DISTINCT FROM (NEW.company_id,NEW.group_id)
          OR NOT EXISTS(SELECT 1 FROM supplier_payment_impacts WHERE operation_id=p.id AND document_record_id=d.id)
          OR EXISTS(SELECT 1 FROM supplier_payment_operations WHERE reverses_id=p.id)
          OR h.id IS DISTINCT FROM (SELECT id FROM supplier_payment_allocation_revisions
               WHERE group_id=NEW.group_id ORDER BY version DESC LIMIT 1) THEN
            RAISE EXCEPTION 'Invalid source refund evidence' USING ERRCODE='23514'; END IF;
        RETURN NEW;
        END $$''')
    op.execute('''CREATE TRIGGER refund_link_guard BEFORE INSERT ON supplier_payment_refund_links
        FOR EACH ROW EXECUTE FUNCTION supplier_refund_link_guard()''')
    # Preserve all old identity, cash, invoice and credit checks. Only a linked
    # refund may coexist with positive allocations, subject to final net caps.
    op.execute('''DO $patch$ DECLARE old TEXT; updated TEXT; BEGIN
        SELECT definition INTO old FROM supplier_refund_guard_versions WHERE name='supplier_payment_impact_guard';
        updated:=replace(old, $$IF operation.kind IN ('refund','credit') AND EXISTS($$,
            $$IF (operation.kind='credit' OR (operation.kind='refund' AND NOT EXISTS(
                SELECT 1 FROM supplier_payment_refund_links WHERE refund_operation_id=operation.id))) AND EXISTS($$);
        IF updated=old THEN RAISE EXCEPTION 'Unexpected settlement guard definition'; END IF;
        EXECUTE updated;
        END $patch$''')
    op.execute('''CREATE OR REPLACE FUNCTION supplier_settlement_allocation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
        PERFORM supplier_allocation_lock(NEW.company_id);
        IF EXISTS(SELECT 1 FROM supplier_payment_allocation_groups g JOIN supplier_payment_documents d ON d.id=g.invoice_record_id
            JOIN supplier_payment_operations o ON o.company_id=d.company_id AND o.document_kind='invoice' AND o.document_id=d.document_id
            WHERE g.id=NEW.group_id AND (o.kind='credit' OR (o.kind='refund' AND NOT EXISTS(
                SELECT 1 FROM supplier_payment_refund_links l WHERE l.refund_operation_id=o.id)))
              AND NOT EXISTS(SELECT 1 FROM supplier_payment_operations rev WHERE rev.reverses_id=o.id)) THEN
            RAISE EXCEPTION 'Unlinked adjustment requires reconciliation' USING ERRCODE='23514'; END IF;
        RETURN NEW;
        END $$''')
    op.execute('''CREATE FUNCTION supplier_refund_complete() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE gid BIGINT; rid BIGINT; target_gid BIGINT;
        BEGIN
        PERFORM supplier_allocation_lock(NEW.company_id);
        IF TG_TABLE_NAME='supplier_payment_operations' THEN
            SELECT g.id INTO target_gid FROM supplier_payment_allocation_groups g
                JOIN supplier_payment_documents d ON d.id=g.invoice_record_id
                WHERE d.company_id=NEW.company_id AND d.document_kind=NEW.document_kind AND d.document_id=NEW.document_id;
        ELSE target_gid:=NEW.group_id;
        END IF;
        -- Recheck only the affected invoice at commit, including direct SQL
        -- and source payment reversals. Unrelated company history is not scanned.
        FOR gid,rid IN SELECT g.id,g.invoice_record_id FROM supplier_payment_allocation_groups g
            WHERE g.id=target_gid AND g.company_id=NEW.company_id AND EXISTS(
                SELECT 1 FROM supplier_payment_refund_links l WHERE l.group_id=g.id)
        LOOP
            IF EXISTS(SELECT 1 FROM supplier_payment_refund_links l
                JOIN supplier_payment_operations r ON r.id=l.refund_operation_id
                JOIN supplier_payment_operations p ON p.id=l.payment_operation_id
                WHERE l.group_id=gid
                  AND NOT EXISTS(SELECT 1 FROM supplier_payment_operations x WHERE x.reverses_id=r.id)
                GROUP BY p.id,p.amount HAVING sum(r.amount)>p.amount
                  OR EXISTS(SELECT 1 FROM supplier_payment_operations x WHERE x.reverses_id=p.id)) THEN
                RAISE EXCEPTION 'Source payment refund capacity exceeded' USING ERRCODE='23514'; END IF;
            IF EXISTS(SELECT 1 FROM supplier_payment_documents d JOIN supplier_payment_operations o
                ON o.document_kind='invoice' AND o.document_id=d.document_id AND o.company_id=d.company_id
                WHERE d.id=rid AND (o.kind='credit' OR (o.kind='refund' AND NOT EXISTS(
                    SELECT 1 FROM supplier_payment_refund_links l WHERE l.refund_operation_id=o.id)))
                  AND NOT EXISTS(SELECT 1 FROM supplier_payment_operations x WHERE x.reverses_id=o.id)) THEN
                RAISE EXCEPTION 'Cannot mix linked refunds and unlinked adjustments' USING ERRCODE='23514'; END IF;
            IF EXISTS(SELECT 1 FROM supplier_payment_allocation_rows a
                JOIN supplier_payment_operations p ON p.id=a.payment_operation_id
                WHERE a.revision_id=(SELECT id FROM supplier_payment_allocation_revisions
                    WHERE group_id=gid ORDER BY version DESC LIMIT 1)
                  AND NOT EXISTS(SELECT 1 FROM supplier_payment_operations x WHERE x.reverses_id=p.id)
                GROUP BY p.id,p.amount HAVING sum(a.amount)>p.amount-(SELECT COALESCE(sum(r.amount),0)
                    FROM supplier_payment_refund_links l JOIN supplier_payment_operations r ON r.id=l.refund_operation_id
                    WHERE l.payment_operation_id=p.id AND NOT EXISTS(
                        SELECT 1 FROM supplier_payment_operations x WHERE x.reverses_id=r.id))) THEN
                RAISE EXCEPTION 'Allocation exceeds payment net of refunds' USING ERRCODE='23514'; END IF;
        END LOOP;
        RETURN NULL;
        END $$''')
    for table in ('supplier_payment_refund_links', 'supplier_payment_operations',
                  'supplier_payment_allocation_revisions', 'supplier_payment_allocation_rows'):
        op.execute(f'''CREATE CONSTRAINT TRIGGER refund_complete AFTER INSERT ON {table}
            DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION supplier_refund_complete()''')


def downgrade():
    op.execute('''LOCK TABLE supplier_payment_refund_links,supplier_payment_operations,
        supplier_payment_allocation_revisions,supplier_payment_allocation_rows IN ACCESS EXCLUSIVE MODE''')
    op.execute("DO $$ BEGIN IF EXISTS(SELECT 1 FROM supplier_payment_refund_links) THEN RAISE EXCEPTION 'Cannot discard refund evidence'; END IF; END $$")
    op.execute('''DO $$ DECLARE r RECORD; BEGIN FOR r IN SELECT definition FROM supplier_refund_guard_versions
        LOOP EXECUTE r.definition; END LOOP; END $$''')
    for table in ('supplier_payment_refund_links', 'supplier_payment_operations',
                  'supplier_payment_allocation_revisions', 'supplier_payment_allocation_rows'):
        op.execute(f'DROP TRIGGER refund_complete ON {table}')
    op.execute('DROP TABLE supplier_payment_refund_links')
    op.execute('DROP FUNCTION supplier_refund_link_guard()')
    op.execute('DROP FUNCTION supplier_refund_complete()')
    op.execute('DROP TABLE supplier_refund_guard_versions')
