"""Offline CEP database for cepx's local provider, built from CEP Aberto.

This package ships a prebuilt SQLite database (``cepx.sqlite``) derived from
CEP Aberto (https://www.cepaberto.com/) under the Open Database License (ODbL).
cepx's LocalProvider locates it via :func:`db_path`. See the NOTICE file for
the attribution the ODbL requires.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files

DB_SUBDIR = "data"
DB_FILENAME = "cepx.sqlite"

try:
    __version__ = version("cepx-data")
except PackageNotFoundError:  # pragma: no cover - source tree, not installed
    __version__ = "0.0.0"


def db_path() -> str:
    """Absolute path to the bundled CEP SQLite database.

    The file only exists in a built/released distribution (it is produced by
    the data pipeline in ``tools/``); use :func:`has_db` to check first.
    """
    return str(files("cepx_data") / DB_SUBDIR / DB_FILENAME)


def has_db() -> bool:
    """Whether the bundled database is present in this installation."""
    return (files("cepx_data") / DB_SUBDIR / DB_FILENAME).is_file()


__all__ = ("DB_FILENAME", "DB_SUBDIR", "__version__", "db_path", "has_db")
