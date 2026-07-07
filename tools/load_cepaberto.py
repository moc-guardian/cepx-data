#!/usr/bin/env python3
"""Load CEP Aberto dumps into the offline cepx SQLite database.

CEP Aberto (https://www.cepaberto.com/) publishes per-state dumps under the
Open Database License (ODbL). The data is *point* data: one row per CEP. Each
CEP becomes one row in the normalized `ceps` table (keyed on the CEP itself);
build_cep_db.py handles the schema.

The dumps are headerless CSV with positional columns:

    CEP file   -> cep, logradouro, complemento, bairro, cidade_id, estado_id
    cities.csv -> cidade_id, nome, estado_id
    states.csv -> estado_id, nome, sigla

City and state are numeric IDs in the CEP file; cepx's Address needs names, so
cidade_id is resolved via cities.csv and estado_id via states.csv.

Usage:
    python tools/load_cepaberto.py "*.cepaberto_*.csv" \\
        --cities cities.csv --states states.csv
"""

from __future__ import annotations

import argparse
import csv
import glob
import os
import re
from collections.abc import Iterator

from build_cep_db import Row, build

_NON_DIGITS = re.compile(r"\D+")

_COL_CEP = 0
_COL_STREET = 1
_COL_COMPLEMENTO = 2
_COL_BAIRRO = 3
_COL_CIDADE_ID = 4
_COL_ESTADO_ID = 5


def _load_id_map(path: str, value_col: int) -> dict[int, str]:
    mapping: dict[int, str] = {}

    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.reader(fh):
            if len(row) <= value_col:
                continue

            id_digits = _NON_DIGITS.sub("", row[0] or "")
            value = row[value_col].strip()

            if id_digits and value:
                mapping[int(id_digits)] = value

    if not mapping:
        raise SystemExit(f"no rows parsed from {path}")

    return mapping


def _iter_rows(
    paths: list[str],
    cities: dict[int, str],
    states: dict[int, str],
) -> Iterator[Row]:
    for path in paths:
        with open(path, encoding="utf-8", newline="") as fh:
            for row in csv.reader(fh):
                if len(row) <= _COL_ESTADO_ID:
                    continue  # malformed / short row

                cep_digits = _NON_DIGITS.sub("", row[_COL_CEP] or "")

                if len(cep_digits) != 8:
                    continue

                cep = int(cep_digits)
                city_digits = _NON_DIGITS.sub("", row[_COL_CIDADE_ID] or "")
                state_digits = _NON_DIGITS.sub("", row[_COL_ESTADO_ID] or "")
                city = cities.get(int(city_digits)) if city_digits else None
                uf = states.get(int(state_digits)) if state_digits else None

                if not uf or not city:
                    continue  # cepx requires both a UF and a city name

                street = (row[_COL_STREET] or "").strip()
                bairro = (row[_COL_BAIRRO] or "").strip()

                yield (cep, uf, city, bairro, street)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "inputs",
        nargs="+",
        help="CEP dump file(s) or globs",
    )

    parser.add_argument(
        "--cities",
        required=True,
        help="CEP Aberto cities reference CSV (cidade_id, nome, estado_id)",
    )

    parser.add_argument(
        "--states",
        required=True,
        help="CEP Aberto states reference CSV (estado_id, nome, sigla)",
    )

    parser.add_argument(
        "--out",
        default=os.path.normpath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "src",
                "cepx_data",
                "data",
                "cepx.sqlite",
            )
        ),
        help="output .sqlite path",
    )

    args = parser.parse_args()

    cities = _load_id_map(args.cities, value_col=1)  # cidade_id -> nome
    states = _load_id_map(args.states, value_col=2)  # estado_id -> sigla

    paths = sorted({
        p for pattern
        in args.inputs
        for p in glob.glob(pattern)
    })  # fmt: skip

    if not paths:
        raise SystemExit(f"no files matched: {args.inputs}")

    counts = build(_iter_rows(paths, cities, states), args.out)
    size_mb = os.path.getsize(args.out) / (1024 * 1024)

    print(f"wrote {args.out}")

    print(
        f"  {counts['ceps']:,} CEPs, {counts['cities']:,} cities, "
        f"{counts['neighborhoods']:,} neighborhoods, "
        f"{counts['streets']:,} streets, {size_mb:.2f} MiB"
    )

    print("  data: CEP Aberto (https://www.cepaberto.com/) - ODbL.")


if __name__ == "__main__":
    main()
