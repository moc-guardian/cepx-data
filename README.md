# cepx-data

Offline Brazilian CEP database for [cepx](https://github.com/araggohnxd/cepx)'s
local provider. It ships a prebuilt SQLite database derived from
[CEP Aberto](https://www.cepaberto.com/), plus the pipeline that builds it.

Install it alongside cepx via the extra:

```bash
pip install "cepx[local]"     # pulls in cepx-data
```

Then cepx resolves CEPs fully offline:

```python
import cepx

cepx.cep("01001000", providers=["local"])
```

`cepx-data` exposes the database location for cepx to discover:

```python
import cepx_data

cepx_data.db_path()   # path to the bundled cepx.sqlite
cepx_data.has_db()    # False in a source checkout, True once built/installed
```

## Data model

CEP Aberto is *point* data (one row per CEP). Each CEP is stored as a
degenerate range `(start == end == cep)` in a table indexed on `start`, and
locality/street names are deduplicated into a `names` table — so a lookup is a
single indexed range query (`WHERE start <= ? ORDER BY start DESC LIMIT 1`), the
SQL equivalent of a binary search. A CEP absent from the dataset is a clean
miss (no range interpolation).

## Building the database

The database is a build artifact (git-ignored); the release pipeline produces
it. No CEP Aberto data is committed to this repo — it is all fetched on demand.
To build locally you only need a logged-in CEP Aberto session:

```bash
export CEPABERTO_COOKIE='_cepaberto_session=...; remember_user_token=...'
export CEPABERTO_TOKEN='...'          # from a browser download request
make data                              # fetch dumps + refs, then build
```

- `tools/fetch_cepaberto.py` — parallel authenticated download of the per-state
  dumps AND the `cities.csv` / `states.csv` reference tables (each response is a
  ZIP wrapping a CSV; auto-extracted), with retries, into `dumps/`.
- `tools/load_cepaberto.py` — joins the dumps against the reference tables and
  writes `src/cepx_data/data/cepx.sqlite`.
- `tools/build_cep_db.py` — the SQLite writer (dedup names + indexed ranges).

The full dataset is ~1.14M CEPs (~82 MiB).

## Releases

On merge to `main`, release-please opens/tags releases. The publish job runs
`make data` (using the repo secrets `CEPABERTO_COOKIE` / `CEPABERTO_TOKEN`),
builds the wheel, and publishes to PyPI via Trusted Publishing.

> **Note:** the CEP Aberto session credentials expire. Refresh the
> `CEPABERTO_COOKIE` / `CEPABERTO_TOKEN` repo secrets before cutting a release,
> or build locally with `make data` and publish manually.

## License & attribution

Code is MIT. The bundled database (and the reference tables it is built from)
are derived from **CEP Aberto** and licensed under the **Open Database License
(ODbL) 1.0** — attribution and share-alike required. No CEP Aberto data is kept
in this repository; it is fetched at build time. See [NOTICE](NOTICE).

## Development

```bash
make setup
make check      # unit tests + coverage + pre-commit
```
