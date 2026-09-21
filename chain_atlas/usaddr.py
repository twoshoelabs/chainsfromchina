"""
Pulling city / state / ZIP off the end of a one-line US address.

This is small and dull and the state map rests entirely on it. Chains write the same corner
four different ways, and every variant this fails to read is a store that silently vanishes
from a state total:

    "1065 Brea Mall, Brea, CA 92821"                            comma-separated, textbook
    "20 City Boulevard West Suite 916, Orange CA 92868"         no comma before the state
    "14006 Riverside Dr Space 249A  San Fernando Valley, CA 91423"   two spaces where a comma belongs
    "10250 Santa Monica Blvd, Los Angeles, CA-90067, USA"       hyphen before the ZIP, trailing country
    "555 6th Ave, New York, NY 10011, United States"            trailing country, spelled out

So: strip the country, accept a hyphen or spaces between state and ZIP, and let the city be
preceded by either a comma or whitespace. A line it still cannot read yields Nones rather than
a guess — the raw address is always kept, and `export` counts the unparsed rather than hiding
them.
"""
import re

STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA",
    "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT",
    "VA", "WA", "WV", "WI", "WY", "DC", "PR", "GU", "VI", "AS", "MP",
}
# Chains write the state out in full about as often as they abbreviate it, and POP MART does
# both within one feed: "Rosemont, Illinois 60018" beside "Costa Mesa, CA 92626".
FULL_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA",
    "colorado": "CO", "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA",
    "hawaii": "HI", "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA",
    "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT", "vermont": "VT",
    "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI",
    "wyoming": "WY", "district of columbia": "DC", "puerto rico": "PR",
}
# A suite or space number written AFTER the postcode, which POP MART does often enough to
# matter: "East Rutherford, NJ 07073, Space D230".
_TRAILING_UNIT = re.compile(
    r"[,\s]+(?:space|ste|suite|unit|shop|#)\s*[A-Za-z0-9-]+\s*$", re.I)
_COUNTRY = re.compile(r"[,\s]+(?:USA|U\.S\.A\.|US|U\.S\.|UNITED STATES(?: OF AMERICA)?)\s*$", re.I)
# city, then state, then ZIP. The separator before the city may be a comma or just spaces;
# the separator before the ZIP may be a comma, a hyphen or spaces.
_FULL_ALT = "|".join(sorted((re.escape(k) for k in FULL_NAMES), key=len, reverse=True))
_TAIL = re.compile(
    r"(?:,|\s\s|,\s)\s*(?P<city>[A-Za-z][A-Za-z .'\-]{1,40}?)\s*[,\s]\s*"
    rf"(?P<state>[A-Za-z]{{2}}|{_FULL_ALT})\.?\s*[-,\s]\s*(?P<zip>\d{{5}})(?:-\d{{4}})?\s*$",
    re.I)
# Fallback: no readable city, but a state and ZIP are still there — a store with a state is
# worth more to this project than a store with nothing.
_STATE_ZIP = re.compile(
    rf"\b(?P<state>[A-Za-z]{{2}}|{_FULL_ALT})\.?\s*[-,\s]\s*(?P<zip>\d{{5}})(?:-\d{{4}})?\s*$",
    re.I)


def split_tail(addr: str | None) -> tuple[str | None, str | None, str | None]:
    """
    name:      split_tail
    purpose:   Read city, state and ZIP off the end of a US address line.
    arguments: addr — the chain's own string, or None
    returns:   (city, state, zip); any element may be None
    effects:   None
    other:     The state is validated against the USPS list, so a street named "1 Mall Dr"
               cannot contribute "MA" as a state. A two-letter token that is not a state
               fails the whole match rather than being passed through.
    """
    if not addr:
        return None, None, None
    s = _COUNTRY.sub("", addr.strip())
    s = _TRAILING_UNIT.sub("", s)
    m = _TAIL.search(s)
    if m:
        st = _abbr(m.group("state"))
        if st:
            city = m.group("city").strip(" ,")
            return (city or None), st, m.group("zip")
    m = _STATE_ZIP.search(s)
    if m:
        st = _abbr(m.group("state"))
        if st:
            return None, st, m.group("zip")
    return None, None, None


def _abbr(token: str) -> str | None:
    """A USPS code, or a full state name resolved to one; None if it is neither."""
    t = (token or "").strip().rstrip(".")
    if t.upper() in STATES:
        return t.upper()
    return FULL_NAMES.get(t.lower())
