"""Package init for company_context.

Avoid importing route registration at import time to keep unit tests lightweight
and to prevent hard dependency on psycopg2 when only service logic is needed.
"""
try:
    # Importing routes may pull heavy optional deps; keep optional.
    from .routes import register_company_context_module  # type: ignore
except Exception:
    register_company_context_module = None
