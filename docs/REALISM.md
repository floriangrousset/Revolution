# 🏛️ Realism — how close is the simulation to the real thing?

Revolution models US legislative negotiation. This document is an honest audit of
where the simulation matches real congressional procedure, where it deliberately
simplifies, and what a more faithful model would add. It doubles as the design
rationale for the realism features shipped in July 2026 and the roadmap for the
rest.

> **Reminder:** this is a simulation, not a forecast. Personas are AI
> approximations of public figures' documented positions; outcomes depend on
> model choice, temperature, and the motion text.

## ✅ What the engine models faithfully

| Mechanic | Real-world analogue | Where |
|---|---|---|
| Private caucus deliberation → floor debate → roll-call vote | Caucus meetings → floor consideration → recorded vote | `src/graphs/main_graph.py` |
| Party hierarchy (head → advisors → assistants) | Leadership → committee leaders → member offices | `src/agents/base.py` |
| Passage rules: majority / 3⁄5 / 2⁄3 | House majority · Senate cloture (60/100) · veto-override & constitutional thresholds | `src/voting/consensus.py` (`VotingRules`, integer-exact math) |
| Optional quorum | Art. I §5 quorum requirement | `VotingRules.quorum` |
| Seat-weighted voting | Party strength = seats, not headcount. Ships with the July-2026 splits (House 218 R – 212 D) | `voting_seats` in the party registry; per-ballot weight = seats ÷ ballots cast, exact `Fraction` math |
| Amendment markup round | A failed measure amended and reconsidered (motion to recommit with instructions / markup) | `markup` + `markup_debate` nodes; outcome `"amended"` |
| Amendment sponsorship | Sponsors/cosponsors | `amendment_sponsors` state, `by`/`sponsors` in `amendments.json` |
| Abstentions | "Present" votes — excluded from the pass denominator | `determine_final_result` |
| Bipartisanship detection | Cross-party support coalitions | ≥ 2 parties each casting ≥ 1 support vote (raw head-counts, never weighted) |
| Vote changes across the debate | Members persuaded between whip check and final passage | initial vs. final vote, Persuasion Timeline |
| Roster fidelity | The 22 seeded personas are fact-checked against the 119th Congress as of 2026-07-17 (no executive-branch officials seated; a test guards this) | `src/agents/data/`, `tests/test_agents.py` |

## ⚠️ Deliberate simplifications

- **One chamber.** The simulated chamber mixes House and Senate figures. Seat
  weighting defaults to House splits; switch the registry numbers to 53/47 for a
  Senate feel.
- **Time-boxed debate.** Debate ends after `max_rounds` (1–5), not by motions to
  proceed or cloture votes. The 3⁄5 rule models the cloture *threshold*, not the
  cloture *procedure*.
- **Only heads + two advisors speak on the floor.** Assistants deliberate in
  caucus and vote, but never hold the floor — a cost/pacing tradeoff.
- **One amendment per markup cycle.** The clerk incorporates the single
  most-sponsored amendment; real markups process many amendments seriatim.
- **No floor motions.** No points of order, unanimous consent, tabling, or
  recommittal as explicit moves.

## 🗺️ Roadmap to deeper realism

Ordered by leverage; each builds on machinery that now exists:

1. **Whip counts** — feed each head the initial-vote tally as a whip count they
   can act on in later debate rounds (the data already exists).
2. **Filibuster as behavior** — let a `bomb_thrower`/`hardliner` posture force
   the `three_fifths` rule for a debate, modeling the filibuster as an agent
   move rather than a config choice.
3. **Committee stage** — generalize the markup node into a pre-floor committee
   subgraph: a jurisdictional subset of agents amends the motion before floor
   debate.
4. **Bicameralism** — run the negotiation twice with different `seat_config`s
   (House, then Senate), then a conference/reconciliation markup on the
   differences. Proposal versioning already supports it.
5. **Veto & override** — a president actor after passage; on veto, an automatic
   re-vote under `two_thirds`. Nearly free given the passage-rule machinery.

## 📚 Data provenance

- **Seat splits** (July 17, 2026): Senate 53 R / 45 D + 2 I caucusing with the
  Democrats; House 218 R / 212 D / 1 I / 4 vacancies. Sources: House Press
  Gallery party breakdown, Senate Daily Press, 119th Congress membership logs.
- **Personas**: each seeded persona cites two sources (congress.gov member page
  plus an official leadership or encyclopedia page), stamped
  `persona_last_updated: 2026-07-17`.
- **Portraits**: official GPO congressional portraits (public domain, via the
  [unitedstates/images](https://github.com/unitedstates/images) project) and
  license-verified Wikimedia Commons photos — see
  [`web/public/portraits/ATTRIBUTIONS.md`](../web/public/portraits/ATTRIBUTIONS.md).
