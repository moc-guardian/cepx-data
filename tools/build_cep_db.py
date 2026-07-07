#!/usr/bin/env python3
"""Build the offline CEP database consumed by cepx's LocalProvider.

This is a build-time ETL tool, not part of the shipped runtime. CEP Aberto is
point data (one row per CEP), so the schema is normalized to keep it compact:

  - ceps(cep PK, uf_id, city_id, neigh_id, street_id)   -- cep is the rowid
  - states(id, sigla) / cities(id, nome)
  - neighborhoods(id, nome) / streets(id, nome)         -- deduplicated

The `--demo` mode fabricates a small synthetic dataset so the pipeline is
runnable end-to-end without any licensed data.

Usage:
    python tools/build_cep_db.py --demo [--out src/cepx_data/data/cepx.sqlite]
"""

from __future__ import annotations

import argparse
import os
import random
import sqlite3
from collections.abc import Callable, Iterable

# A row of source data: (cep, uf, city, neighborhood, street)
Row = tuple[int, str, str, str, str]

DEFAULT_OUT = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "src",
        "cepx_data",
        "data",
        "cepx.sqlite",
    )
)

_DDL = """
CREATE TABLE states (
    id INTEGER PRIMARY KEY,
    sigla TEXT NOT NULL
);

CREATE TABLE cities (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL
);

CREATE TABLE neighborhoods (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL
);

CREATE TABLE streets (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL
);

CREATE TABLE ceps (
    cep INTEGER PRIMARY KEY,
    uf_id INTEGER NOT NULL REFERENCES states(id),
    city_id INTEGER NOT NULL REFERENCES cities(id),
    neigh_id INTEGER NOT NULL REFERENCES neighborhoods(id),
    street_id INTEGER NOT NULL REFERENCES streets(id)
);
"""


def _interner() -> tuple[dict[str, int], Callable[[str], int]]:
    """Return (mapping, intern_fn) that assigns a stable id to each value."""
    mapping: dict[str, int] = {}

    def intern(value: str) -> int:
        i = mapping.get(value)
        if i is None:
            i = len(mapping)
            mapping[value] = i
        return i

    return mapping, intern


def build(rows: Iterable[Row], out_path: str) -> dict[str, int]:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if os.path.exists(out_path):
        os.remove(out_path)

    con = sqlite3.connect(out_path)
    con.execute("PRAGMA journal_mode=OFF")
    con.execute("PRAGMA synchronous=OFF")
    con.executescript(_DDL)

    states, uf_id = _interner()
    cities, city_id = _interner()
    neighs, neigh_id = _interner()
    streets, street_id = _interner()

    cep_rows = [
        (
            cep,
            uf_id(uf),
            city_id(city),
            neigh_id(neigh),
            street_id(street),
        )
        for cep, uf, city, neigh, street in rows
    ]

    for table, mapping in (
        ("states", states),
        ("cities", cities),
        ("neighborhoods", neighs),
        ("streets", streets),
    ):
        con.executemany(
            f"INSERT INTO {table} VALUES (?, ?)",
            ((i, value) for value, i in mapping.items()),
        )

    con.executemany(
        "INSERT INTO ceps (cep, uf_id, city_id, neigh_id, street_id) "
        "VALUES (?, ?, ?, ?, ?)",
        cep_rows,
    )

    con.commit()
    con.execute("VACUUM")
    con.close()

    return {
        "ceps": len(cep_rows),
        "states": len(states),
        "cities": len(cities),
        "neighborhoods": len(neighs),
        "streets": len(streets),
    }


def _demo_rows(n: int, seed: int = 42) -> list[Row]:
    """Fabricate `n` CEPs with realistic repetition across the dimensions."""
    rng = random.Random(seed)

    ufs = [
        "SP",
        "RJ",
        "MG",
        "BA",
        "PR",
        "RS",
        "PE",
        "CE",
        "SC",
        "GO",
    ]

    cities = [
        "São Paulo",
        "Rio de Janeiro",
        "Belo Horizonte",
        "Salvador",
        "Curitiba",
        "Porto Alegre",
        "Recife",
        "Fortaleza",
    ]

    neighs = [
        "Centro",
        "Jardim",
        "Vila Nova",
        "Perdizes",
        "Boa Vista",
    ]

    streets = [
        "Rua Caiubi",
        "Avenida Brasil",
        "Rua das Flores",
        "Travessa São João",
        "Alameda Santos",
    ]

    rows: list[Row] = []
    cep = 1_000_000
    stride = max(1, (99_000_000 - cep) // n)

    for _ in range(n):
        cep += rng.randint(1, stride)

        if cep >= 99_999_999:
            break

        rows.append(
            (
                cep,
                rng.choice(ufs),
                rng.choice(cities),
                rng.choice(neighs),
                rng.choice(streets),
            )
        )

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help="output .sqlite path",
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="build from synthetic data (no source dataset)",
    )

    parser.add_argument(
        "--demo-size",
        type=int,
        default=50_000,
        help="number of synthetic CEPs for --demo",
    )

    args = parser.parse_args()

    if not args.demo:
        parser.error("no source dataset wired up; use --demo for now")

    rows = _demo_rows(args.demo_size)
    counts = build(rows, args.out)
    size_mb = os.path.getsize(args.out) / (1024 * 1024)

    print(f"wrote {args.out}")
    print(
        f"  {counts['ceps']:,} CEPs, {counts['cities']:,} cities, "
        f"{counts['neighborhoods']:,} neighborhoods, "
        f"{counts['streets']:,} streets, {size_mb:.2f} MiB"
    )


if __name__ == "__main__":
    main()
