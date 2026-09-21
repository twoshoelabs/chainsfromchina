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
_COUNTRY = re.compile(r"[,\s]+(?:USA|U\.S\.A\.|US|U\.S\.|UNITED STATES(?: OF AMERICA)?)\s*$", re.I)
# city, then state, then ZIP. The separator before the city may be a comma or just spaces;
# the separator before the ZIP may be a comma, a hyphen or spaces.
_TAIL = re.compile(
    r"(?:,|\s\s|,\s)\s*(?P<city>[A-Za-z][A-Za-z .'\-]{1,40}?)\s*[,\s]\s*"
    r"(?P<state>[A-Z]{2})\s*[-,\s]\s*(?P<zip>\d{5})(?:-\d{4})?\s*$")
# Fallback: no readable city, but a state and ZIP are still there — a store with a state is
# worth more to this project than a store with nothing.
_STATE_ZIP = re.compile(r"\b(?P<state>[A-Z]{2})\s*[-,\s]\s*(?P<zip>\d{5})(?:-\d{4})?\s*$")


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
    m = _TAIL.search(s)
    if m and m.group("state") in STATES:
        city = m.group("city").strip(" ,")
        return (city or None), m.group("state"), m.group("zip")
    m = _STATE_ZIP.search(s)
    if m and m.group("state") in STATES:
        return None, m.group("state"), m.group("zip")
    return None, None, None
