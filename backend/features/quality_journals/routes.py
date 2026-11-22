"""Routes moved verbatim from backend/main.py."""

from fastapi import APIRouter, Depends, Request, Response
try:
    from backend.features.quality_journals.access import journal_operation
except ModuleNotFoundError:
    from features.quality_journals.access import journal_operation

def register_quality_journal_routes(app, deps):
    CLIENT_ACCOUNT_ROLES = deps['CLIENT_ACCOUNT_ROLES']
    PLATFORM_STAFF_ROLES = deps['PLATFORM_STAFF_ROLES']
    PROJECT_DOCUMENT_ROLES = deps['PROJECT_DOCUMENT_ROLES']
    PROJECT_DOCUMENT_WRITE_ROLES = deps['PROJECT_DOCUMENT_WRITE_ROLES']
    WORKER_EXECUTION_ROLES = deps['WORKER_EXECUTION_ROLES']
    YANDEX_API_KEY = deps['YANDEX_API_KEY']
    YANDEX_FOLDER_ID = deps['YANDEX_FOLDER_ID']
    get_current_user = deps['get_current_user']
    get_db = deps['get_db']
    package_access_filter = deps['package_access_filter']
    visible_project_names = deps['visible_project_names']
    router = APIRouter()

    def _quality_journal_dependencies():
        return {
            'get_db': get_db, 'read_roles': PROJECT_DOCUMENT_ROLES,
            'write_roles': (*PROJECT_DOCUMENT_WRITE_ROLES, 'кладовщик', 'снабженец'),
            'worker_roles': WORKER_EXECUTION_ROLES, 'visible_projects': visible_project_names,
            'package_filter': package_access_filter, 'platform_staff_roles': PLATFORM_STAFF_ROLES,
            'client_account_roles': CLIENT_ACCOUNT_ROLES,
        }

    def _owned_quality_journal(user, request, table, **operation):
        return journal_operation(_quality_journal_dependencies(), user, request.headers, table, **operation)

    def _owned_quality_suggestion(user, request, table, row_id):
        try:
            from backend.features.quality_journals.suggestions import suggest_journal
        except ModuleNotFoundError:
            from features.quality_journals.suggestions import suggest_journal
        return suggest_journal(_quality_journal_dependencies(), user, request.headers, table, row_id,
                              api_key=YANDEX_API_KEY, folder_id=YANDEX_FOLDER_ID)

    def _quality_journal_reader(user: dict = Depends(get_current_user)):
        return user

    def _quality_journal_writer(user: dict = Depends(get_current_user)):
        return user

    @router.get("/material-inspection")
    def list_material_inspections(request: Request, response: Response, project_name: str = None, _current_user: dict = Depends(_quality_journal_reader)):
        rows = _owned_quality_journal(_current_user, request, 'material_inspection_journal', project_name=project_name)
        response.headers['X-Quality-Journal-Snapshot'] = 'owned-v1'
        return rows

    @router.put("/material-inspection/{id}")
    def update_material_inspection(id: int, data: dict, request: Request, _current_user: dict = Depends(_quality_journal_writer)):
        return _owned_quality_journal(_current_user, request, 'material_inspection_journal', row_id=id, data=data)

    @router.post("/material-inspection/{id}/ai-suggest")
    def ai_suggest_material_inspection(id: int, request: Request, _current_user: dict = Depends(_quality_journal_writer)):
        return _owned_quality_suggestion(_current_user, request, 'material_inspection_journal', id)

    @router.get("/cable-journal")
    def list_cable_journal(request: Request, response: Response, project_name: str = None, _current_user: dict = Depends(_quality_journal_reader)):
        rows = _owned_quality_journal(_current_user, request, 'cable_journal', project_name=project_name)
        response.headers['X-Quality-Journal-Snapshot'] = 'owned-v1'
        return rows

    @router.put("/cable-journal/{id}")
    def update_cable_journal(id: int, data: dict, request: Request, _current_user: dict = Depends(_quality_journal_writer)):
        return _owned_quality_journal(_current_user, request, 'cable_journal', row_id=id, data=data)

    @router.post("/cable-journal/{id}/ai-suggest")
    def ai_suggest_cable_journal(id: int, request: Request, _current_user: dict = Depends(_quality_journal_writer)):
        return _owned_quality_suggestion(_current_user, request, 'cable_journal', id)

    app.include_router(router)

