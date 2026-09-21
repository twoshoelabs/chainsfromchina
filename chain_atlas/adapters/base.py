"""
One adapter per chain. An adapter knows only how to turn a chain's US locator into a list of
StoreRecord for today; identity, diffing and events live elsewhere.

`trading` is the field that does not exist in the Taiwan sibling. A locator that lists a store
it has not opened yet is telling us something valuable and must not be allowed to inflate a
store count, so the adapter — the only code that understands that chain's vocabulary — decides
what counts as open.
"""
from dataclasses import dataclass, field


@dataclass
class StoreRecord:
    store_code: str | None          # chain's own id if exposed, else None
    name: str | None
    addr_raw: str
    city: str | None = None
    state: str | None = None
    zip: str | None = None
    lat: float | None = None
    lon: float | None = None
    trading: bool = True            # False = listed but not yet open ("coming soon")
    temp_closed: bool = False
    flags: dict = field(default_factory=dict)


class Adapter:
    chain_id: str = ""
    # The market this adapter collects, ISO-3166-1 alpha-2. One adapter covers one market:
    # MINISO's US and UAE estates are published by different sites, in different shapes, and
    # pretending they are one source would make a broken UAE page look like US closures.
    country: str = "US"
    name: str = ""
    name_zh: str | None = None
    origin: str = "CN"
    parent: str | None = None
    format: str = "other"
    # If this adapter collects a market the international register also lists by hand, name the
    # register's chain id here. The collected count then supersedes the typed one, visibly.
    register_chain: str | None = None
    closure_n_days: int = 7
    raw_ext: str = "json"
    ENABLED: bool = False
    # Why a disabled adapter is disabled, shown by `status` so a gap is never silent.
    BLOCKED_REASON: str | None = None
    # URLs to re-probe with `recheck`. A blocker is a fact about a date, not a permanent verdict:
    # ChaPanda has no locator because it has two American shops, and that will change. Without a
    # periodic re-probe the archive would keep quoting a reason from the day someone gave up.
    RECHECK: list[str] = []
    # A count known from a first-party source that publishes NO store list. Haidilao's parent
    # says "13 US restaurants in 8 cities" and names none of them. That is a real number and an
    # unmappable one, so it is kept as data rather than buried in prose, and the map can say
    # "13, location unknown" instead of leaving the chain off entirely.
    KNOWN_COUNT: dict | None = None

    def fetch_raw(self):
        """
        name:      fetch_raw
        purpose:   Retrieve the chain's complete US locator output for today.
        arguments: none
        returns:   Raw payload exactly as received, for save_raw().
        effects:   Network requests via capture.fetch().
        other:     Must return the whole US footprint. A partial result is worse than a failed
                   run, because it looks like closures.
        """
        raise NotImplementedError

    def parse(self, raw) -> list[StoreRecord]:
        """
        name:      parse
        purpose:   Turn fetch_raw() output into StoreRecords.
        arguments: raw — whatever fetch_raw returned, or a re-read raw file
        returns:   list[StoreRecord]
        effects:   None. Must be pure so archived captures can be re-parsed later.
        other:     —
        """
        raise NotImplementedError
