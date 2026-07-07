#!/usr/bin/env python3
"""Download CEP Aberto per-state CEP dumps using an authenticated session.

CEP Aberto gates dumps behind a login, so this reuses logged-in browser session.
Copy the session cookie and the form authenticity_token from a browser
download request (DevTools -> Network -> "Copy as cURL") and export them:

    export CEPABERTO_COOKIE='_cepaberto_session=...; remember_user_token=...'
    export CEPABERTO_TOKEN='Dr4ov/qoZTN...=='   # raw or URL-encoded, either ok
    python tools/fetch_cepaberto.py --out dumps/

Each state (UF) is split into 5 parts; this fetches all 27 x 5 = 135 files as
dumps/<UF>.cepaberto_parte_<n>.csv, plus the two reference tables
dumps/cities.csv and dumps/states.csv (endpoint name=cities / name=states, no
part), all ready for load_cepaberto.py.
"""

from __future__ import annotations

import argparse
import io
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed

_URL = "https://www.cepaberto.com/downloads.csv"

UFS = [
    "AC",
    "AL",
    "AM",
    "AP",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MG",
    "MS",
    "MT",
    "PA",
    "PB",
    "PE",
    "PI",
    "PR",
    "RJ",
    "RN",
    "RO",
    "RR",
    "RS",
    "SC",
    "SE",
    "SP",
    "TO",
]


def _normalize_token(token: str) -> str:
    return urllib.parse.quote(urllib.parse.unquote(token), safe="")


def _looks_like_login_page(body: bytes) -> bool:
    head = body[:512].lstrip().lower()

    return head.startswith(b"<") or b"sign_in" in head or b"<html" in head


def _extract_csv(body: bytes) -> bytes:
    """The endpoint returns a ZIP wrapping one .csv; return the CSV bytes.

    Falls back to the body as-is if it is already plain CSV.
    """
    if body[:4] != b"PK\x03\x04":
        return body

    with zipfile.ZipFile(io.BytesIO(body)) as zf:
        names = [n for n in zf.namelist() if n.lower().endswith(".csv")]

        if not names:
            raise ValueError("ZIP contained no .csv member")

        return zf.read(names[0])


def fetch(
    name: str,
    part: int | None,
    cookie: str,
    token_enc: str,
    timeout: float,
) -> bytes:
    params = {
        "name": name,
    }

    if part is not None:
        params["part"] = part

    headers = {
        "User-Agent": "cepx-data (github.com/moc-guardian/cepx-data)",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "identity",
        "Origin": "https://www.cepaberto.com",
        "Referer": "https://www.cepaberto.com/downloads/new",
        "Cookie": cookie,
    }

    query = urllib.parse.urlencode(params)
    data = f"_method=post&authenticity_token={token_enc}".encode()

    request = urllib.request.Request(
        f"{_URL}?{query}",
        data=data,
        method="POST",
        headers=headers,
    )

    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, urllib.error.HTTPError):
        return error.code >= 500

    return isinstance(error, (urllib.error.URLError, OSError, ValueError))


def _download_one(
    name: str,
    part: int | None,
    filename: str,
    cookie: str,
    token_enc: str,
    out: str,
    delay: float,
    timeout: float,
    retries: int,
    abort: threading.Event,
) -> tuple[str, int | None, str | None]:
    last_error = "unknown error"

    for attempt in range(retries + 1):
        if abort.is_set():
            return (filename, None, "skipped (aborted)")

        try:
            body = fetch(name, part, cookie, token_enc, timeout)

            if _looks_like_login_page(body):
                abort.set()  # session dead: stop the rest of the run

                return (filename, None, "login page (session expired)")

            csv_bytes = _extract_csv(body)
            dest = os.path.join(out, filename)

            with open(dest, "wb") as fh:
                fh.write(csv_bytes)

            if delay:
                time.sleep(delay)  # optional per-request throttle

            return (filename, len(csv_bytes), None)
        except Exception as err:
            if isinstance(err, urllib.error.HTTPError):
                last_error = f"HTTP {err.code}"
            else:
                last_error = str(err) or type(err).__name__

            if not _is_retryable(err) or attempt == retries:
                return (filename, None, last_error)

            time.sleep(2 * (attempt + 1))  # linear backoff before retry

    return (filename, None, last_error)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--out",
        default="dumps",
        help="output directory",
    )

    parser.add_argument(
        "--uf",
        action="append",
        metavar="UF",
        help="limit to specific UF(s); repeatable (default: all 27)",
    )

    parser.add_argument(
        "--parts",
        type=int,
        default=5,
        help="parts per state (default 5)",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="concurrent downloads (default 8)",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help=(
            "per-request timeout in seconds"
            "(default 180 for large states, like SP)"
        ),
    )

    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="retries on transient errors (5xx/timeout) (default 3)",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="optional per-request throttle in seconds (default 0)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the requests without downloading",
    )

    args = parser.parse_args()

    ufs = [u.upper() for u in args.uf] if args.uf else UFS
    parts = range(1, args.parts + 1)

    # (name, part, filename): the two reference tables (no part) + the per-state
    # CEP dumps. cities.csv/states.csv are needed by load_cepaberto.py.
    tasks: list[tuple[str, int | None, str]] = [
        ("cities", None, "cities.csv"),
        ("states", None, "states.csv"),
    ]

    tasks += [
        (uf, part, f"{uf}.cepaberto_parte_{part}.csv")
        for uf in ufs
        for part in parts
    ]

    if args.dry_run:
        for name, part, filename in tasks:
            params = (
                {"name": name, "part": part}
                if part is not None
                else {"name": name}
            )

            query = urllib.parse.urlencode(params)

            print(f"POST {_URL}?{query} -> {filename}")

        print(f"\n{len(tasks)} requests (dry run)")

        return

    cookie = os.environ.get("CEPABERTO_COOKIE")
    token = os.environ.get("CEPABERTO_TOKEN")

    if not cookie or not token:
        raise SystemExit("set CEPABERTO_COOKIE and CEPABERTO_TOKEN env vars")

    token_enc = _normalize_token(token)

    os.makedirs(args.out, exist_ok=True)

    abort = threading.Event()
    total = len(tasks)
    ok = 0
    failures: list[str] = []

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = [
            pool.submit(
                _download_one,
                name,
                part,
                filename,
                cookie,
                token_enc,
                args.out,
                args.delay,
                args.timeout,
                args.retries,
                abort,
            )
            for name, part, filename in tasks
        ]

        for future in as_completed(futures):
            label, size, error = future.result()

            if error:
                failures.append(f"{label}: {error}")
                print(f"  ! {label}: {error}")
                continue

            ok += 1

            print(f"  {ok}/{total} {label} ({size:,} bytes csv)")

    print(f"\ndone: {ok}/{total} files saved to {args.out}/")

    if abort.is_set():
        print(
            "session expired mid-run (got a login page). "
            "Refresh CEPABERTO_COOKIE/CEPABERTO_TOKEN and rerun."
        )

    if failures:
        print(f"{len(failures)} failed:")

        for f in failures:
            print(f"  - {f}")

        raise SystemExit(1)


if __name__ == "__main__":
    main()
