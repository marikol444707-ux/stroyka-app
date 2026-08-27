import importlib.util
import sys
import types
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_ENV_PATH = PROJECT_ROOT / "migrations" / "env.py"


def _load_alembic_env(db_config, *, offline=True):
    configured = {}
    created_engine = {}
    fake_context = types.SimpleNamespace(
        config=types.SimpleNamespace(config_file_name=None),
        is_offline_mode=lambda: offline,
        configure=lambda **kwargs: configured.update(kwargs),
        begin_transaction=nullcontext,
        run_migrations=lambda: None,
    )
    fake_alembic = types.ModuleType("alembic")
    fake_alembic.context = fake_context
    fake_backend_db = types.ModuleType("backend.db")
    fake_backend_db.DB_CONFIG = db_config
    fake_sqlalchemy = types.ModuleType("sqlalchemy")

    class FakeConnectable:
        def connect(self):
            return nullcontext(object())

    def create_engine(url, **kwargs):
        created_engine.update(url=url, kwargs=kwargs)
        return FakeConnectable()

    fake_sqlalchemy.create_engine = create_engine
    fake_sqlalchemy.pool = types.SimpleNamespace(NullPool=object())
    fake_sqlalchemy_engine = types.ModuleType("sqlalchemy.engine")

    class FakeUrl:
        def __init__(self, **values):
            for key, value in values.items():
                setattr(self, key, value)

        def __str__(self):
            return (
                f"{self.drivername}://{self.username}:***"
                f"@{self.host}:{self.port}/{self.database}"
            )

    fake_sqlalchemy_engine.URL = types.SimpleNamespace(
        create=lambda drivername, **kwargs: FakeUrl(
            drivername=drivername,
            **kwargs,
        ),
    )

    spec = importlib.util.spec_from_file_location(
        "test_accounting_alembic_env",
        ALEMBIC_ENV_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(
        sys.modules,
        {
            "alembic": fake_alembic,
            "backend.db": fake_backend_db,
            "sqlalchemy": fake_sqlalchemy,
            "sqlalchemy.engine": fake_sqlalchemy_engine,
        },
    ):
        spec.loader.exec_module(module)
    return module, configured, created_engine


class AlembicEnvironmentTests(unittest.TestCase):
    def test_database_url_keeps_the_password_without_exposing_it_as_text(self):
        module, configured, _created_engine = _load_alembic_env({
            "dbname": "stroyka",
            "user": "stroyka",
            "password": "pa:ss/@word",
            "host": "localhost",
            "port": "5432",
        })

        database_url = module._database_url()

        self.assertEqual(database_url.password, "pa:ss/@word")
        self.assertIn("***", str(database_url))
        self.assertEqual(configured["url"].password, "pa:ss/@word")

    def test_online_migrations_connect_with_the_database_url_object(self):
        module, configured, created_engine = _load_alembic_env({
            "dbname": "stroyka",
            "user": "stroyka",
            "password": "pa:ss/@word",
            "host": "localhost",
            "port": "5432",
        }, offline=False)

        self.assertEqual(created_engine["url"].password, "pa:ss/@word")
        self.assertIn("connection", configured)


if __name__ == "__main__":
    unittest.main()
