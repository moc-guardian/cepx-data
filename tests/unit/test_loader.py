from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_LOADER = Path(__file__).resolve().parents[2] / "tools" / "load_cepaberto.py"

# Real CEP Aberto CEP-dump shape: headerless, positional columns
# cep, logradouro, complemento, bairro, cidade_id, estado_id.
_CEP_DUMP = (
    "69900001,Beco Estado do Acre,,Base,7735,1\n"
    '69902992,"Ramal Benfica, s/n",,,7735,1\n'  # quoted comma, empty bairro
    "69900010,Rua Estado do Acre,,Centro,7735,1\n"
)
_CITIES = "7735,Rio Branco,1\n"  # cidade_id, nome, estado_id
_STATES = "1,Acre,AC\n"  # estado_id, nome, sigla

_LOOKUP = (
    "SELECT r.end, n.name FROM ranges r JOIN names n ON n.id = r.name_id "
    "WHERE r.start <= ? ORDER BY r.start DESC LIMIT 1"
)


def _build(tmp_path) -> Path:
    cep = tmp_path / "ac.cepaberto_parte_1.csv"
    cep.write_text(_CEP_DUMP, encoding="utf-8")
    (tmp_path / "cities.csv").write_text(_CITIES, encoding="utf-8")
    (tmp_path / "states.csv").write_text(_STATES, encoding="utf-8")
    db = tmp_path / "cepx.sqlite"
    subprocess.run(
        [
            sys.executable,
            str(_LOADER),
            str(cep),
            "--cities",
            str(tmp_path / "cities.csv"),
            "--states",
            str(tmp_path / "states.csv"),
            "--out",
            str(db),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return db


def test_loader_builds_queryable_db_with_resolved_names(tmp_path):
    con = sqlite3.connect(_build(tmp_path))
    try:
        row = con.execute(_LOOKUP, (69900001,)).fetchone()
    finally:
        con.close()
    assert row is not None
    assert row[1] == "AC|Rio Branco|Base|Beco Estado do Acre"


def test_loader_preserves_quoted_embedded_comma(tmp_path):
    con = sqlite3.connect(_build(tmp_path))
    try:
        row = con.execute(_LOOKUP, (69902992,)).fetchone()
    finally:
        con.close()
    assert row[1].endswith("Ramal Benfica, s/n")


def test_absent_cep_is_a_miss(tmp_path):
    con = sqlite3.connect(_build(tmp_path))
    try:
        row = con.execute(_LOOKUP, (69900002,)).fetchone()
    finally:
        con.close()
    # nearest lower range is 69900001, whose end is 69900001 < 69900002
    assert row is None or row[0] < 69900002
