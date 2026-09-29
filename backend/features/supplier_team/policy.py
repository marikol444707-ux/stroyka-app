"""Explicit supplier membership; buyer company roles and duplicate hints grant nothing."""
import os
from fastapi import HTTPException


def enabled():
    return os.getenv('SUPPLIER_TEAM_ENABLED') == '1'


def customer_assignments_enabled():
    return os.getenv('SUPPLIER_CUSTOMER_ASSIGNMENTS_ENABLED') == '1'


def _actor(value):
    try:
        return int(value) if not isinstance(value, bool) and int(value) > 0 else None
    except (TypeError, ValueError):
        return None


def leader_policy(user_id, supplier_column='supplier_offers.supplier_id'):
    if supplier_column not in ('supplier_offers.supplier_id', 'si.supplier_id', 's.id'):
        raise ValueError('Unrecognized supplier column')
    actor = _actor(user_id)
    if not actor:
        return 'FALSE', []
    return f'''EXISTS (SELECT 1 FROM suppliers team_supplier
        JOIN users team_actor ON team_actor.id=%s
          AND team_actor.role='поставщик' AND COALESCE(team_actor.active,TRUE)
        WHERE team_supplier.id={supplier_column} AND (
          team_supplier.user_id=team_actor.id OR EXISTS (
            SELECT 1 FROM supplier_team_members team_member
            WHERE team_member.supplier_id=team_supplier.id
              AND team_member.user_id=team_actor.id AND team_member.active
              AND team_member.role='leader')))''', [actor]


def offer_policy(user_id, alias='supplier_offers'):
    if alias not in ('supplier_offers', 'team_offer'):
        raise ValueError('Unrecognized offer alias')
    actor = _actor(user_id)
    if not actor:
        return 'FALSE', []
    # The rollout selects one authority source, never a union of old and new grants.
    assignment_table = ('supplier_customer_assignments' if customer_assignments_enabled()
                        else 'supplier_offer_assignments')
    assignment_key = ('company_id' if customer_assignments_enabled() else 'offer_id')
    offer_key = 'company_id' if customer_assignments_enabled() else 'id'
    # Membership ID binds the grant to its supplier membership.
    return f'''EXISTS (SELECT 1 FROM suppliers team_supplier
        JOIN users team_actor ON team_actor.id=%s
          AND team_actor.role='поставщик' AND COALESCE(team_actor.active,TRUE)
        WHERE team_supplier.id={alias}.supplier_id AND (
          team_supplier.user_id=team_actor.id OR EXISTS (
            SELECT 1 FROM supplier_team_members team_member
            WHERE team_member.supplier_id=team_supplier.id
              AND team_member.user_id=team_actor.id AND team_member.active
              AND (team_member.role='leader' OR (
                team_member.role='manager' AND EXISTS (
                  SELECT 1 FROM {assignment_table} team_assignment
                  WHERE team_assignment.{assignment_key}={alias}.{offer_key}
                    AND team_assignment.supplier_id={alias}.supplier_id
                    AND team_assignment.member_id=team_member.id))))))''', [actor]


def access_ids(cursor, user):
    cursor.execute('''SELECT s.id FROM suppliers s JOIN users u ON u.id=%s
        WHERE u.role='поставщик' AND COALESCE(u.active,TRUE)
          AND (s.user_id=u.id OR EXISTS (
            SELECT 1 FROM supplier_team_members m
            WHERE m.supplier_id=s.id AND m.user_id=u.id AND m.active))
        ORDER BY s.id''', (user.get('id'),))
    return [int(row['id'] if isinstance(row, dict) else row[0]) for row in cursor.fetchall()]


def leader_ids(cursor, user):
    sql, params = leader_policy(user.get('id'), 's.id')
    cursor.execute('SELECT s.id FROM suppliers s WHERE '+sql+' ORDER BY s.id', params)
    return [int(row['id'] if isinstance(row, dict) else row[0]) for row in cursor.fetchall()]


def lock_offer_access(cursor, offer_id, user_id):
    """Hold authority and assignment through the caller's mutation transaction."""
    cursor.execute('SELECT supplier_id FROM supplier_offers WHERE id=%s', (offer_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(403, 'Нет доступа к КП')
    supplier_id = row['supplier_id'] if isinstance(row, dict) else row[0]
    cursor.execute('SELECT id FROM suppliers WHERE id=%s FOR SHARE', (supplier_id,))
    cursor.fetchall()
    cursor.execute('SELECT id FROM users WHERE id=%s FOR SHARE', (user_id,))
    cursor.fetchall()
    cursor.execute('''SELECT id FROM supplier_team_members
        WHERE supplier_id=%s AND user_id=%s ORDER BY id FOR SHARE''', (supplier_id, user_id))
    cursor.fetchall()
    if customer_assignments_enabled():
        cursor.execute('''SELECT a.company_id FROM supplier_customer_assignments a
            WHERE a.supplier_id=%s AND a.company_id=(
                SELECT company_id FROM supplier_offers WHERE id=%s) FOR SHARE''',
            (supplier_id, offer_id))
    else:
        cursor.execute('SELECT offer_id FROM supplier_offer_assignments WHERE offer_id=%s FOR SHARE', (offer_id,))
    cursor.fetchall()
    sql, params = offer_policy(user_id)
    cursor.execute('SELECT id FROM supplier_offers WHERE id=%s AND '+sql, [offer_id]+params)
    if not cursor.fetchone():
        raise HTTPException(403, 'КП не назначено вам или доступ отозван')
