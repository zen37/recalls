import pytest

from recalls.config import Config
from recalls.store import SqliteAlertStore, open_store


def test_open_store_defaults_to_sqlite(tmp_path):
    config = Config.from_env({"RECALLS_DB_PATH": str(tmp_path / "r.db")})
    store = open_store(config)
    assert isinstance(store, SqliteAlertStore)


def test_open_store_rejects_unknown_backend(tmp_path):
    config = Config.from_env(
        {"RECALLS_STORE": "mystery", "RECALLS_DB_PATH": str(tmp_path / "r.db")}
    )
    with pytest.raises(ValueError, match="unknown store backend"):
        open_store(config)
