# US-entry / expansion models (Pro / intelligence)

How each tracked China-origin chain actually **enters and scales in the US**. Data lives in
[`manual/us_entry_models.json`](../manual/us_entry_models.json) (keyed by `chain_id`, so it covers
every US-present chain, including the many that have no `register.chains` entry). Report:
`python -m chain_atlas entry-models`. **Pro tier** — not surfaced on the public map/register yet.

## The six models

| model | meaning | examples |
|---|---|---|
| **direct_subsidiary** | the brand's own US entity runs company-owned stores; no US franchising | Pop Mart, Chagee, Luckin, Haidilao, Nayuki, Pop Mart, Urban Revivo |
| **us_franchise** | an open US franchise program (FDD or first-party application) | Mixue, Cotti, Möge, Miniso, Zhang Liang, HeyTea, R&B Tea, YGF* |
| **regional_operators** | several independent US operators each run a cluster; no single national entity | YGF Malatang, Zhengxin |
| **importer_group** | a US multi-brand venture that *imports* the brand | Chubby Skewers, Hi Bake, Mama Xita (all **Chubby Group**) |
| **authorized_partner** | a single authorized flagship/licensee via a local partner | JNBY, Little Sheep (Yum China), Zhoumapo, Dusu |
| **distribution** | not branded retail (wholesale / gray-market); usually out of the outlet count | Xiaomi, Huawei (both 0 counted US storefronts) |
| **unknown** | US-present but the mechanism isn't established yet | ~20 small restaurant chains — research backlog |

\* YGF has a national franchise *application* but its stores actually run through independent regional
operators, so it's filed under `regional_operators` — the operative reality, not the paperwork.

## Operators / importer groups

`operators` in the JSON lists US ventures that run one or more China brands. The headline is the
**importer_group**: a US company whose business is bringing China chains over.

- **Chubby Group** (David Zhao; ~70+ locations / 25+ brands) — the clearest importer group: **three**
  China-origin brands in the US — **Chubby Skewers (幸福小串), Hi Bake (嗨呗可), Mama Xita BBQ (西塔老太太)** —
  plus a Japanese import (Chubby Tan) and its own US-created concepts (out of scope). Watch for more.
- **Brand-parent operators** (the Chinese parent running its own brand's US stores, *not* third-party
  importers): Jiumaojiu → Tai Er; Super Hi International → Haidilao; Yum China → Little Sheep.

## Method & caveats

- `confidence`: **high** = explicit first-party / FDD / press evidence; **medium** = strong inference
  from the operating model + footprint; **low** = inferred, thin evidence.
- Only chains with **US outlets** are classified. Global-register-only chains with no US presence
  (Tianlala, Xtep, Li-Ning, Bosideng, …) have no entry model — they're watch targets until they move.
- The ~20 `unknown` rows are the research backlog: mostly single/few-store restaurant chains where we
  haven't established whether the US outlet is a direct flagship, a local franchisee, or a partner.
- Fill unknowns and upgrade `medium`/`low` tags as first-party evidence surfaces (FDDs, franchise
  pages, press). This layer feeds a potential public chain-page datum and a press/Pro angle:
  *"the US ventures quietly importing Chinese chains."*
