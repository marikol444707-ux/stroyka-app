from typing import Optional

from fastapi import Depends, Header, HTTPException
from psycopg2 import Error as DatabaseError
from psycopg2.extras import RealDictCursor

from . import service


def register_intercompany_warehouse_transfers(app, deps):
    get_user = deps["get_current_user"]

    def context(cur, user, company, mode, write=False):
        resolved = deps["resolve_work_company_context"](
            cur, user, None, "write" if write else "read", x_company_id=company, x_company_mode=mode)
        if resolved.get("mode") != "company" or not resolved.get("companyId"):
            raise HTTPException(409, "Выберите одну компанию")
        actors = deps["effective_company_actors"](user, resolved)
        actor = {**actors[0], "companyId": int(resolved["companyId"])} if len(actors) == 1 else {}
        allowed = service.WRITERS if write else service.READERS
        if actor.get("role") not in allowed:
            raise HTTPException(403, "Роль в выбранной компании не позволяет работать с межфирменными перемещениями")
        return actor

    def transaction(user, company, mode, callback, write=False):
        conn = deps["get_db"]()
        conn.autocommit = False
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                actor = context(cur, user, company, mode, write=write)
                cur.execute("SELECT to_regclass('intercompany_warehouse_transfers') AS present")
                if not cur.fetchone()["present"]:
                    raise HTTPException(503, "Межфирменные перемещения ещё не подготовлены")
                if write and not service.enabled():
                    raise HTTPException(409, "Межфирменные перемещения временно отключены")
                result = callback(cur, actor)
            conn.commit()
            return result
        except DatabaseError as error:
            conn.rollback()
            if error.pgcode == "23505":
                raise HTTPException(409, "Операция с таким номером уже обрабатывается") from error
            if error.pgcode in ("40P01", "40001", "55P03"):
                raise HTTPException(409, "Операцию меняет другой пользователь. Повторите запрос") from error
            raise
        except (ValueError, PermissionError) as error:
            conn.rollback()
            status = 403 if isinstance(error, PermissionError) else 409
            raise HTTPException(status, str(error)) from error
        except LookupError as error:
            conn.rollback()
            raise HTTPException(404, str(error)) from error
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @app.get("/intercompany-warehouse-transfers")
    def listing(x_company_id: Optional[str] = Header(None, alias="X-Company-Id"),
                x_company_mode: Optional[str] = Header(None, alias="X-Company-Mode"),
                user: dict = Depends(get_user)):
        return transaction(user, x_company_id, x_company_mode,
            lambda cur, actor: {"items": service.listing(cur, actor["companyId"]), "companyId": actor["companyId"]})

    @app.post("/intercompany-warehouse-transfers")
    def create(data: dict, x_company_id: Optional[str] = Header(None, alias="X-Company-Id"),
               x_company_mode: Optional[str] = Header(None, alias="X-Company-Mode"),
               user: dict = Depends(get_user)):
        return transaction(user, x_company_id, x_company_mode,
            lambda cur, actor: service.create(cur, actor, actor["companyId"], data), write=True)

    def decision(action, transfer_id, data, company, mode, user):
        return transaction(user, company, mode,
            lambda cur, actor: service.decide(cur, actor, actor["companyId"], transfer_id, action,
                                              (data or {}).get("reason") or ""), write=True)

    @app.post("/intercompany-warehouse-transfers/{transfer_id}/accept")
    def accept(transfer_id: int, data: Optional[dict] = None,
               x_company_id: Optional[str] = Header(None, alias="X-Company-Id"),
               x_company_mode: Optional[str] = Header(None, alias="X-Company-Mode"), user: dict = Depends(get_user)):
        return decision("accept", transfer_id, data, x_company_id, x_company_mode, user)

    @app.post("/intercompany-warehouse-transfers/{transfer_id}/reject")
    def reject(transfer_id: int, data: dict, x_company_id: Optional[str] = Header(None, alias="X-Company-Id"),
               x_company_mode: Optional[str] = Header(None, alias="X-Company-Mode"), user: dict = Depends(get_user)):
        return decision("reject", transfer_id, data, x_company_id, x_company_mode, user)

    @app.post("/intercompany-warehouse-transfers/{transfer_id}/cancel")
    def cancel(transfer_id: int, data: dict, x_company_id: Optional[str] = Header(None, alias="X-Company-Id"),
               x_company_mode: Optional[str] = Header(None, alias="X-Company-Mode"), user: dict = Depends(get_user)):
        return decision("cancel", transfer_id, data, x_company_id, x_company_mode, user)
