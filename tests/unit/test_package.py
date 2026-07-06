from __future__ import annotations

import pytest

import cepx_data

pytestmark = pytest.mark.unit


def test_db_path_points_at_the_bundled_sqlite():
    path = cepx_data.db_path()
    assert path.endswith("cepx.sqlite")
    assert cepx_data.DB_SUBDIR in path


def test_has_db_returns_a_bool():
    # In a source checkout the database is absent; once built/installed it is
    # present. Either way the accessor must return a plain bool.
    assert isinstance(cepx_data.has_db(), bool)


def test_version_is_a_string():
    assert isinstance(cepx_data.__version__, str)
