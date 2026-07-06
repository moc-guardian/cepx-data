#!/usr/bin/env python3
"""Build the offline CEP database consumed by cepx's LocalProvider.

This is a build-time ETL tool, not part of the shipped runtime. It turns a
source dataset of CEP ranges into a compact SQLite file:

  - ranges(start, end, name_id)  with start as the primary key (indexed)
  - names(id, name)              deduplicated "UF|city|neighborhood|street"

A lookup then becomes a single indexed range query. Point it at a real source
(e.g. the Correios DNE, if you are licensed to use it) by feeding rows to
`build`. The `--demo` mode fabricates a small synthetic dataset so the
offline path is runnable end-to-end without any licensed data.

Usage:
    python tools/build_cep_db.py --demo [--out src/cepx/data/cepx.sqlite]
"""

from __future__ import annotations

import argparse
import os
import random
import sqlite3
from collections.abc import Iterable

# A row of source data: (start_cep, end_cep, uf, city, neighborhood, street)
Row = tuple[int, int, str, str, str, str]

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


def build(rows: Iterable[Row], out_path: str) -> tuple[int, int]:
    """Write `rows` into a fresh SQLite database at `out_path`.

    Returns (n_ranges, n_unique_names).
    """
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    if os.path.exists(out_path):
        os.remove(out_path)

    con = sqlite3.connect(out_path)
    con.execute("PRAGMA journal_mode=OFF")
    con.execute("PRAGMA synchronous=OFF")

    con.execute(
        "CREATE TABLE names (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
    )

    con.execute(
        "CREATE TABLE ranges ("
        "  start INTEGER PRIMARY KEY,"
        "  end INTEGER NOT NULL,"
        "  name_id INTEGER NOT NULL REFERENCES names(id)"
        ")"
    )

    name_ids: dict[str, int] = {}

    def name_id(name: str) -> int:
        i = name_ids.get(name)
        if i is None:
            i = len(name_ids)
            name_ids[name] = i
        return i

    range_rows = []

    for start, end, uf, city, neighborhood, street in rows:
        name = f"{uf}|{city}|{neighborhood}|{street}"
        range_rows.append((start, end, name_id(name)))

    con.executemany(
        "INSERT INTO names (id, name) VALUES (?, ?)",
        ((i, name) for name, i in name_ids.items()),
    )

    con.executemany(
        "INSERT INTO ranges (start, end, name_id) VALUES (?, ?, ?)",
        range_rows,
    )

    con.commit()
    con.execute("VACUUM")
    con.close()

    return len(range_rows), len(name_ids)


def _demo_rows(n: int, seed: int = 42) -> list[Row]:
    """Fabricate `n` non-overlapping CEP ranges with realistic repetition."""
    rng = random.Random(seed)

    ufs = ["SP", "RJ", "MG", "BA", "PR", "RS", "PE", "CE", "SC", "GO"]

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
    cursor = 1_000_000
    stride = max(2, (99_000_000 - cursor) // n)

    for _ in range(n):
        start = cursor + rng.randint(0, stride)
        end = start + rng.randint(0, min(500, stride))

        if end >= 99_999_999:
            break

        rows.append(
            (
                start,
                end,
                rng.choice(ufs),
                rng.choice(cities),
                rng.choice(neighs),
                rng.choice(streets),
            )
        )

        cursor = end + 1

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
        help="number of synthetic ranges for --demo",
    )

    args = parser.parse_args()

    if not args.demo:
        parser.error("no source dataset wired up; use --demo for now")

    rows = _demo_rows(args.demo_size)
    n_ranges, n_names = build(rows, args.out)
    size_mb = os.path.getsize(args.out) / (1024 * 1024)

    print(f"wrote {args.out}")
    print(f"  {n_ranges:,} ranges, {n_names:,} unique names, {size_mb:.2f} MiB")

    if rows:
        sample = rows[len(rows) // 2]

        print(
            f"  sample lookup key inside DB: {sample[0]:08d} .. {sample[1]:08d}"
        )


if __name__ == "__main__":
    main()
