"""
Fetch and store raw locator responses. Raw files are the primary evidence; every parsed
table can be rebuilt from them, so they are written before anything is interpreted.
"""
import gzip, hashlib, json, random, time
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlparse

import requests

from .config import RAW_DIR, USER_AGENT, REQUEST_TIMEOUT, DELAY_MIN_S, DELAY_MAX_S, MAX_RETRIES

_session = requests.Session()
_session.headers["User-Agent"] = USER_AGENT
session = _session          # exported so adapters can share cookies
_robots: dict[str, robotparser.RobotFileParser] = {}
_delay = [DELAY_MIN_S, DELAY_MAX_S]


def set_delay(lo: float, hi: float):
    """
    name:      set_delay
    purpose:   Override the politeness delay for this process (probes use ~1 s).
    arguments: lo, hi — seconds
    returns:   None
    effects:   Changes the module-level delay used by fetch().
    other:     The nightly run keeps the configured default.
    """
    _delay[0], _delay[1] = lo, hi


def allowed(url: str) -> bool:
    """
    name:      allowed
    purpose:   Ask the origin's robots.txt whether our User-Agent may fetch this URL.
    arguments: url (str)
    returns:   bool — True also when robots.txt is absent or unreadable, which is the
               standard reading of "no robots.txt means no restriction".
    effects:   Fetches and caches robots.txt once per origin.
    other:     A 404 robots.txt is an allowance, not a failure. A site that answers robots.txt
               with an HTML error page (several here do) parses as empty, i.e. allowed.
    """
    p = urlparse(url)
    origin = f"{p.scheme}://{p.netloc}"
    rp = _robots.get(origin)
    if rp is None:
        rp = robotparser.RobotFileParser()
        try:
            r = _session.get(origin + "/robots.txt", timeout=REQUEST_TIMEOUT)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except Exception:
            rp.parse([])
        _robots[origin] = rp
    return rp.can_fetch(USER_AGENT, url)


def fetch(url: str, method: str = "GET", **kw) -> requests.Response:
    """
    name:      fetch
    purpose:   One polite, robots-checked HTTP request with retries.
    arguments: url, method, plus anything requests accepts (json=, headers=, ...)
    returns:   requests.Response
    effects:   Sleeps the politeness delay BEFORE the request; network I/O.
    other:     Raises RuntimeError if robots.txt disallows the URL — a refusal is a result,
               never something to work around.
    """
    if not allowed(url):
        raise RuntimeError(f"robots.txt disallows {url} for this User-Agent")
    last = None
    for attempt in range(MAX_RETRIES):
        time.sleep(random.uniform(*_delay))
        try:
            r = _session.request(method, url, timeout=REQUEST_TIMEOUT, **kw)
            if r.status_code < 400:
                return r
            last = RuntimeError(f"{r.status_code} from {url}")
        except Exception as e:                      # noqa: BLE001 — retried below
            last = e
    raise last


def save_raw(chain_id: str, obs_date: str, payload, ext: str = "json") -> tuple[str, str]:
    """
    name:      save_raw
    purpose:   Write today's untouched locator payload to the archive.
    arguments: chain_id, obs_date (YYYY-MM-DD), payload (str/bytes/JSON-able), ext
    returns:   (path_str, sha256_hex)
    effects:   Writes raw/<chain>/<date>.<ext>.gz, creating directories.
    other:     Never overwrites: a second run the same day writes .2, .3 ... so a bad
               re-run can never destroy the capture that a number was already derived from.
    """
    d = RAW_DIR / chain_id
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{obs_date}.{ext}.gz"
    n = 2
    while path.exists():
        path = d / f"{obs_date}.{n}.{ext}.gz"
        n += 1
    if isinstance(payload, bytes):
        blob = payload
    elif isinstance(payload, str):
        blob = payload.encode("utf-8")
    else:
        blob = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    with gzip.open(path, "wb") as f:
        f.write(blob)
    return str(path), hashlib.sha256(blob).hexdigest()


def read_raw(path: str | Path):
    """
    name:      read_raw
    purpose:   Re-read an archived capture so a parser can be re-run over old evidence.
    arguments: path
    returns:   str (decoded utf-8)
    effects:   None
    other:     Parsers take whatever fetch_raw returned, so they must accept this too.
    """
    with gzip.open(path, "rb") as f:
        return f.read().decode("utf-8")
