#!/usr/bin/env python3
"""Report what the bundled CEP database actually covers.

Analogous to geoip2fast's --coverage, adapted to CEP data. geoip2fast can
report "% of all IPv4" because IP space is fully allocatable; CEPs are sparse
in the 0-99,999,999 numeric space (only ~1.1M of 100M are real addresses), so
that ratio is meaningless here. Instead we report absolute counts and
geographic breadth: states, municipalities, and the 10 CEP macro-regions
(the leading digit of the CEP).

Usage:
    python tools/coverage.py [--db src/cepx_data/data/cepx.sqlite]
"""

from __future__ import annotations

import argparse
import os
import sqlite3

DEFAULT_DB = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "src",
        "cepx_data",
        "data",
        "cepx.sqlite",
    )
)

# Brazil has 27 federative units and (IBGE, 2024) 5,570 municipalities. CEP
# Aberto's "cidades" are finer-grained than municipalities (they include
# districts/localities), so city coverage is a loose lower bound.
TOTAL_UFS = 27
TOTAL_MUNICIPALITIES = 5570

# CEP macro-regions by leading digit (Correios postal regions).
REGIONS = {
    0: "SP (Grande São Paulo)",
    1: "SP (interior/litoral)",
    2: "RJ, ES",
    3: "MG",
    4: "BA, SE",
    5: "PE, AL, PB, RN",
    6: "CE, PI, MA, PA, AM, AC, AP, RR",
    7: "DF, GO, TO, MT, MS, RO",
    8: "PR, SC",
    9: "RS",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--db",
        default=DEFAULT_DB,
        help="path to cepx.sqlite",
    )

    args = parser.parse_args()

    if not os.path.exists(args.db):
        raise SystemExit(f"database not found: {args.db}")

    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)

    def scalar(sql):
        return con.execute(sql).fetchone()[0]

    ceps = scalar("SELECT COUNT(*) FROM ceps")
    states = scalar("SELECT COUNT(*) FROM states")
    cities = scalar("SELECT COUNT(*) FROM cities")
    neighs = scalar("SELECT COUNT(*) FROM neighborhoods")
    streets = scalar("SELECT COUNT(*) FROM streets")
    size = os.path.getsize(args.db) / 1048576

    print(
        f"\nCoverage report  ({os.path.basename(args.db)}, "
        f"{size:.1f} MiB)\n" + "=" * 52
    )

    print(f"  {ceps:>10,}  CEPs")
    print(f"  {cities:>10,}  cities/localities")
    print(f"  {neighs:>10,}  neighborhoods")
    print(f"  {streets:>10,}  streets")

    print("\nGeographic breadth")
    print("-" * 52)

    print(
        f"  states ........... {states:>2}/{TOTAL_UFS}  "
        f"({100 * states / TOTAL_UFS:.0f}%)"
    )

    print(
        f"  municipalities ... {cities:>5,} present vs "
        f"{TOTAL_MUNICIPALITIES:,} IBGE"
    )

    print("\nCEPs per state")
    print("-" * 52)

    rows = con.execute(
        "SELECT s.sigla, COUNT(*) c FROM ceps "
        "JOIN states s ON s.id = ceps.uf_id GROUP BY uf_id ORDER BY c DESC"
    ).fetchall()

    for i in range(0, len(rows), 3):
        cells = rows[i : i + 3]
        print("  " + "   ".join(f"{uf} {n:>8,}" for uf, n in cells))

    print("\nCEPs per macro-region (leading digit)")
    print("-" * 52)

    region_rows = dict(
        con.execute(
            "SELECT cep / 10000000, COUNT(*) FROM ceps GROUP BY cep / 10000000"
        ).fetchall()
    )

    top = max(region_rows.values(), default=1) or 1

    for digit in range(10):
        n = region_rows.get(digit, 0)
        bar = "#" * round(30 * n / top)

        print(f"  {digit}xxxxxxx  {REGIONS[digit]:<31}{n:>9,}  {bar}")

    con.close()

    print()


if __name__ == "__main__":
    main()
