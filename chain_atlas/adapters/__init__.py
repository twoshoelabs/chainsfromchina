"""
Adapter registry. Add a module per chain and list it in REGISTRY.

Scope, and it is a judgement this project makes explicitly: mainland-China-origin chains,
collected market by market. The archive began with the United States and the map still reads
only US rows, but one adapter covers one market — MINISO's US and UAE estates are published by
different sites in different shapes, so they are two adapters and two chain_ids, never one.

A chain earns a place on this roster by TRADING in a market the project covers — never by being
convenient to collect. Chains with no usable locator stay here as disabled adapters carrying the
reason, so `status` shows the shape of the category rather than the shape of what happened to be
scrapable. Yang's Braised Chicken has been in America since 2017 and is the clearest case: eight
years of trading, no locator, and it would have been invisible under any other rule. Taiwanese and Hong Kong brands (Tiger Sugar, The Alley,
Gong Cha) are a different and earlier wave and are not in scope; Asian grocers such as
99 Ranch and H Mart sell Chinese products but are not Chinese chains, and including them
would answer a question nobody asked.
"""
from .base import Adapter, StoreRecord
from .mixue import MixueAdapter
from .chagee import ChageeAdapter
from .luckin import LuckinAdapter
from .miniso import MinisoAdapter
from .miniso_ae import MinisoUAEAdapter
from .haidilao_us import HaidilaoUSAdapter
from .stubs import (PopMartAdapter, HeyteaAdapter, CottiAdapter, YangsAdapter,
                    TaiErAdapter, ChaPandaAdapter, NaixueAdapter, JueweiAdapter)

REGISTRY: list[Adapter] = [
    MixueAdapter(),     # validated live 21 Sep 2026; 27 stores (10 open, 17 coming soon), 1 request
    ChageeAdapter(),    # validated live 21 Sep 2026; 11 stores with published coordinates, 1 request
    LuckinAdapter(),    # validated live 21 Sep 2026; 22 stores, no coordinates, 1 request
    MinisoAdapter(),    # validated live 21 Sep 2026; 462 CMS rows -> ~425 stores, 2 requests
    MinisoUAEAdapter(), # validated live 21 Sep 2026; first non-US market, 7 emirate pages
    HaidilaoUSAdapter(),# validated live 21 Sep 2026; 15 US restaurants with coordinates
    PopMartAdapter(),   # blocked — see stubs.py
    HeyteaAdapter(),    # blocked — see stubs.py
    CottiAdapter(),     # blocked — see stubs.py
    YangsAdapter(),     # in the US since 2017, no locator found — see stubs.py
    TaiErAdapter(),     # in the US, parent discloses counts — see stubs.py
    ChaPandaAdapter(),  # entered the US Aug 2025 — see stubs.py
    NaixueAdapter(),    # US entry reported — see stubs.py
    JueweiAdapter(),    # trades as Juewei Yabo in the US — see stubs.py
]


def by_id(chain_id: str) -> Adapter | None:
    """
    name:      by_id
    purpose:   Look an adapter up by its chain_id.
    arguments: chain_id
    returns:   Adapter or None
    effects:   None
    other:     —
    """
    return next((a for a in REGISTRY if a.chain_id == chain_id), None)
