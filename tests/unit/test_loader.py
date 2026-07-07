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

# Normalized schema: exact match on the cep primary key, joined to dimensions.
_LOOKUP = (
    "SELECT s.sigla, c.nome, n.nome, st.nome FROM ceps "
    "JOIN states s ON s.id = ceps.uf_id "
    "JOIN cities c ON c.id = ceps.city_id "
    "JOIN neighborhoods n ON n.id = ceps.neigh_id "
    "JOIN streets st ON st.id = ceps.street_id "
    "WHERE ceps.cep = ?"
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
    assert row == ("AC", "Rio Branco", "Base", "Beco Estado do Acre")


def test_loader_preserves_quoted_embedded_comma(tmp_path):
    con = sqlite3.connect(_build(tmp_path))
    try:
        row = con.execute(_LOOKUP, (69902992,)).fetchone()
    finally:
        con.close()
    assert row[3] == "Ramal Benfica, s/n"  # street, with the embedded comma
    assert row[2] == ""  # empty bairro interned as a shared row


def test_absent_cep_is_a_miss(tmp_path):
    con = sqlite3.connect(_build(tmp_path))
    try:
        row = con.execute(_LOOKUP, (69900002,)).fetchone()
    finally:
        con.close()
    assert row is None  # exact-match on cep: an absent CEP simply has no row
