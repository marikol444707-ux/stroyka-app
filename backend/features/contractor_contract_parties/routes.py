"""HTTP action for signing and freezing a contractor contract."""

from typing import Optional

from fastapi import Depends, Header

from .storage import freeze_contract


def register_contractor_contract_party_routes(app, deps):
    @app.post("/brigade-contracts/{contract_id}/signature")
    def sign_contract(
        contract_id: int,
        data: dict,
        x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
        x_company_mode: Optional[str] = Header(default=None, alias="X-Company-Mode"),
        current_user: dict = Depends(deps["get_current_user"]),
    ):
        conn = deps["get_db"]()
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                contract, actor, _project = deps["resolve_contract"](
                    cur, current_user, contract_id, deps["leadership_roles"],
                    x_company_id=x_company_id, x_company_mode=x_company_mode, for_update=True,
                )
                snapshot = freeze_contract(cur, contract["id"], contract["companyId"], data.get("scanUrl"), actor)
                conn.commit()
                return {"ok": True, "status": "Подписан", "signedAt": snapshot["contract"]["signedAt"],
                        "contractScanUrl": snapshot["source"]["fileUrl"], "partySnapshot": snapshot}
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()
