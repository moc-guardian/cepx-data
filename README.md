# cepx-data

Offline Brazilian CEP database for [cepx](https://github.com/moc-guardian/cepx)'s
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

CEP Aberto is *point* data (one row per CEP). Each CEP is one row in a `ceps`
table keyed on the CEP itself (`cep INTEGER PRIMARY KEY`, i.e. the rowid), and
the repeated UF / city / neighborhood / street values are deduplicated into
`states` / `cities` / `neighborhoods` / `streets` tables referenced by small
integer ids. A lookup is an exact match on the `cep` key joined to the four
dimension tables; a CEP absent from the dataset is a clean miss. Normalizing
the repeated text (rather than storing a `UF|city|...` string per row) keeps
the database ~42 MiB instead of ~82 MiB.

## Coverage

Run `python tools/coverage.py` to report what the bundled database covers.
As of the current dataset:

```
   1,137,150  CEPs
       5,367  cities/localities
      31,285  neighborhoods
     611,241  streets

  states ........... 27/27  (100%)
  municipalities ... 5,367 present vs 5,570 IBGE

CEPs per macro-region (leading digit)
  0xxxxxxx  SP (Grande São Paulo)            114,641  ##################
  1xxxxxxx  SP (interior/litoral)            186,209  ##############################
  2xxxxxxx  RJ, ES                           131,820  #####################
  3xxxxxxx  MG                               116,180  ###################
  4xxxxxxx  BA, SE                            64,380  ##########
  5xxxxxxx  PE, AL, PB, RN                    91,280  ###############
  6xxxxxxx  CE, PI, MA, PA, AM, AC, AP, RR   112,120  ##################
  7xxxxxxx  DF, GO, TO, MT, MS, RO           156,020  #########################
  8xxxxxxx  PR, SC                           106,105  #################
  9xxxxxxx  RS                                58,395  #########
```

(CEP Aberto counts districts finer than IBGE municipalities, so the
municipality figure is a loose lower bound.)

## Building the database

The database is a build artifact, produced during the release pipeline.
No CEP Aberto data is committed to this repo.
To build locally you only need a logged-in CEP Aberto session:

```bash
export CEPABERTO_COOKIE='_cepaberto_session=...; remember_user_token=...'
export CEPABERTO_TOKEN='...'          # from a browser download request
make data                             # fetch dumps + refs, then build
```

- `tools/fetch_cepaberto.py`: parallel authenticated download of the per-state
  dumps AND the `cities.csv` / `states.csv` reference tables (each response is a
  ZIP wrapping a CSV; auto-extracted), with retries, into `dumps/`.
- `tools/load_cepaberto.py`: joins the dumps against the reference tables and
  writes `src/cepx_data/data/cepx.sqlite`.
- `tools/build_cep_db.py`: the SQLite writer (deduped dimension tables +
  `ceps` keyed on the CEP).
- `tools/coverage.py`: reports what the built database covers.

The full dataset is ~1.14M CEPs (~42 MiB).

## Releases

On merge to `main`, release-please opens/tags releases. The publish job runs
`make data` (using the repo secrets `CEPABERTO_COOKIE` / `CEPABERTO_TOKEN`),
builds the wheel, and publishes to PyPI via Trusted Publishing.

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
