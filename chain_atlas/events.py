"""
Turning two days of observations into dated facts.

The rules, and why each one is conservative:

  opening      A store seen trading that was never seen trading before. If we had seen it
               announced first, the opening is dated to the day it started trading, which is
               the most precise opening date this project can produce.
  announced    A store first seen NOT trading (Mixue's `coming_soon`). It is not an opening
               and is never added to a store count; it is the pipeline, reported separately.
  closure      A store absent from the locator for N consecutive COLLECTED days. Absence on a
               day the collector failed is not absence: gaps are recorded, never inferred as
               closures, so a network outage cannot manufacture a wave of shutdowns.
  withdrawn    An announced store that disappeared without ever trading. A cancelled plan is
               not a closure and must not be counted as one.
  reopen       A closed store seen trading again.
  relocation   A closure and an opening by the same chain within R metres and D days. Emitted
               in addition to the pair, never instead of it: the pair is the evidence.
"""
import json
from datetime import date, timedelta

from .geo import haversine_m

RELOC_RADIUS_M = 400
RELOC_WINDOW_D = 45


def _collected_days(con, chain_id: str, upto: str, n: int) -> list[str]:
    """
    name:      _collected_days
    purpose:   The last n dates on which this chain was collected successfully, newest first.
    arguments: con, chain_id, upto (YYYY-MM-DD, inclusive), n
    returns:   list[str]
    effects:   None
    other:     This is what makes the closure rule immune to collector downtime.
    """
    rows = con.execute(
        "SELECT DISTINCT obs_date FROM runs WHERE chain_id=? AND status='ok' AND obs_date<=?"
        " ORDER BY obs_date DESC LIMIT ?", (chain_id, upto, n)).fetchall()
    return [r["obs_date"] for r in rows]


def _emit(con, detected, event_date, chain_id, store_id, kind, details=None):
    con.execute(
        "INSERT INTO events (detected_date,event_date,chain_id,store_id,event_type,details)"
        " VALUES (?,?,?,?,?,?)",
        (detected, event_date, chain_id, store_id, kind,
         json.dumps(details, ensure_ascii=False) if details else None))


def diff(con, chain_id: str, obs_date: str, closure_n_days: int, baseline: bool) -> dict:
    """
    name:      diff
    purpose:   Derive today's events for one chain and update the store roster.
    arguments: con, chain_id, obs_date, closure_n_days, baseline (True on a chain's first
               ever run, when every store is pre-existing and nothing is an opening)
    returns:   dict of counts by event type
    effects:   Inserts into events; updates stores.
    other:     Idempotent per (chain, day): re-running over the same observations re-derives
               the same roster, and events already written for that day are cleared first.
    """
    con.execute("DELETE FROM events WHERE chain_id=? AND detected_date=?", (chain_id, obs_date))
    row = con.execute("SELECT country FROM chains WHERE chain_id=?", (chain_id,)).fetchone()
    country = row["country"] if row else "US"
    counts: dict[str, int] = {}

    def bump(k):
        counts[k] = counts.get(k, 0) + 1

    today = {r["store_key"]: r for r in con.execute(
        "SELECT * FROM observations WHERE chain_id=? AND obs_date=?", (chain_id, obs_date))}
    known = {r["store_key"]: r for r in con.execute(
        "SELECT * FROM stores WHERE chain_id=?", (chain_id,))}

    opened_today, closed_today = [], []

    for key, o in today.items():
        trading = bool(o["trading"]) and not o["temp_closed"]
        prev = known.get(key)
        if prev is None:
            status = "active" if trading else "pre_opening"
            cur = con.execute(
                "INSERT INTO stores (chain_id,country,store_key,store_code,name,addr_raw,addr_norm,"
                "city,state,zip,lat,lon,coord_src,cell100,first_seen,last_seen,opened_on,status)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (chain_id, country, key, o["store_code"], o["name"], o["addr_raw"], o["addr_norm"],
                 o["city"], o["state"], o["zip"], o["lat"], o["lon"],
                 "published" if o["lat"] is not None else None,
                 _cell(o["lat"], o["lon"], country), obs_date, obs_date,
                 obs_date if trading else None, status))
            sid = cur.lastrowid
            if baseline:
                bump("baseline")
            elif trading:
                _emit(con, obs_date, obs_date, chain_id, sid, "opening", {"first_seen_trading": True})
                opened_today.append((sid, o))
                bump("opening")
            else:
                _emit(con, obs_date, obs_date, chain_id, sid, "announced", {"status": "coming_soon"})
                bump("announced")
            continue

        sid = prev["store_id"]
        was_trading = prev["status"] == "active"
        moved = haversine_m(prev["lat"], prev["lon"], o["lat"], o["lon"])
        con.execute(
            "UPDATE stores SET store_code=?,name=?,addr_raw=?,addr_norm=?,city=?,state=?,zip=?,"
            "lat=COALESCE(?,lat),lon=COALESCE(?,lon),cell100=COALESCE(?,cell100),last_seen=? WHERE store_id=?",
            (o["store_code"], o["name"], o["addr_raw"], o["addr_norm"], o["city"], o["state"],
             o["zip"], o["lat"], o["lon"], _cell(o["lat"], o["lon"], country), obs_date, sid))

        if trading and prev["status"] == "pre_opening":
            # The precise case: announced, then seen trading. This is a real opening date.
            con.execute("UPDATE stores SET status='active', opened_on=? WHERE store_id=?", (obs_date, sid))
            _emit(con, obs_date, obs_date, chain_id, sid, "opening",
                  {"announced_on": prev["first_seen"], "from": "pre_opening"})
            opened_today.append((sid, o))
            bump("opening")
        elif trading and prev["status"] == "closed":
            con.execute("UPDATE stores SET status='active' WHERE store_id=?", (sid,))
            _emit(con, obs_date, obs_date, chain_id, sid, "reopen", {"closed_since": prev["last_seen"]})
            bump("reopen")
        elif not trading and was_trading:
            con.execute("UPDATE stores SET status='temp_closed' WHERE store_id=?", (sid,))
            _emit(con, obs_date, obs_date, chain_id, sid, "temp_closed", None)
            bump("temp_closed")
        elif trading and prev["status"] == "temp_closed":
            con.execute("UPDATE stores SET status='active' WHERE store_id=?", (sid,))
            _emit(con, obs_date, obs_date, chain_id, sid, "reopen", {"from": "temp_closed"})
            bump("reopen")

        if moved is not None and moved > RELOC_RADIUS_M:
            _emit(con, obs_date, obs_date, chain_id, sid, "relocation",
                  {"metres": round(moved), "same_key": True})
            bump("relocation")

    # Absence. Only days we actually collected count toward the run of absences.
    recent = _collected_days(con, chain_id, obs_date, closure_n_days)
    if len(recent) >= closure_n_days:
        placeholders = ",".join("?" * len(recent))
        gone = con.execute(
            f"SELECT s.* FROM stores s WHERE s.chain_id=? AND s.status IN ('active','pre_opening')"
            f" AND s.store_key NOT IN (SELECT store_key FROM observations WHERE chain_id=s.chain_id"
            f" AND obs_date IN ({placeholders}))", (chain_id, *recent)).fetchall()
        for s in gone:
            if s["status"] == "pre_opening":
                con.execute("UPDATE stores SET status='withdrawn' WHERE store_id=?", (s["store_id"],))
                _emit(con, obs_date, s["last_seen"], chain_id, s["store_id"], "withdrawn",
                      {"announced_on": s["first_seen"], "never_traded": True})
                bump("withdrawn")
            else:
                con.execute("UPDATE stores SET status='closed' WHERE store_id=?", (s["store_id"],))
                # Dated to the day after it was last seen: the last day we have evidence it traded.
                gone_on = (date.fromisoformat(s["last_seen"]) + timedelta(days=1)).isoformat()
                _emit(con, obs_date, gone_on, chain_id, s["store_id"], "closure",
                      {"last_seen": s["last_seen"], "absent_days_collected": len(recent)})
                closed_today.append((s["store_id"], s))
                bump("closure")

    _pair_relocations(con, chain_id, obs_date, opened_today, closed_today, bump)
    return counts


def _pair_relocations(con, chain_id, obs_date, opened, closed, bump):
    """
    name:      _pair_relocations
    purpose:   Flag an opening and a nearby recent closure as one move.
    arguments: con, chain_id, obs_date, opened/closed lists from this run, bump callback
    returns:   None
    effects:   Emits 'relocation' events.
    other:     Advisory only. The opening and the closure both stand; this says they look like
               one store moving, and a reader can disagree because both halves are still there.
    """
    if not opened:
        return
    window = (date.fromisoformat(obs_date) - timedelta(days=RELOC_WINDOW_D)).isoformat()
    recent_closures = con.execute(
        "SELECT e.event_id, s.store_id, s.lat, s.lon, s.addr_raw FROM events e"
        " JOIN stores s ON s.store_id=e.store_id"
        " WHERE e.chain_id=? AND e.event_type='closure' AND e.event_date>=?",
        (chain_id, window)).fetchall()
    for sid, o in opened:
        for c in recent_closures:
            d = haversine_m(c["lat"], c["lon"], o["lat"], o["lon"])
            if d is not None and d <= RELOC_RADIUS_M:
                _emit(con, obs_date, obs_date, chain_id, sid, "relocation",
                      {"metres": round(d), "from_store_id": c["store_id"],
                       "from_addr": c["addr_raw"], "advisory": True})
                bump("relocation")
                break


def _cell(lat, lon, country="US"):
    from .geo import cell100
    return cell100(lat, lon, country)
