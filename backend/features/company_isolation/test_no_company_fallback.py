
from pathlib import Path

def test_no_implicit_company_fallback_in_main():
    main = Path('backend/main.py').read_text(encoding='utf-8')
    assert 'company_id = int(company_context.get("companyId") or requested_company_id or 1)' not in main,         'Found implicit fallback to company_id=1 in backend/main.py'
