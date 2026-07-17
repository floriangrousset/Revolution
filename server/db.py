"""File-DB access layer.

The persona JSON files on disk match the `Agent` dataclass shape verbatim,
so this layer is a thin wrapper around `Agent.from_json` + atomic writes.

Layout (rooted at `Settings.data_dir`):

    data/
    ├── parties.json
    ├── index.json
    ├── personas/<party>/<id>.json
    └── debates/<id>/{debate.json, transcript.jsonl, votes.json, amendments.json}
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.agents.base import Agent, validate_relationships

from .settings import REPO_ROOT, get_settings

log = logging.getLogger(__name__)

# Default seed parties (both the two ground-truth caucuses the engine knows
# about and any common custom parties the user has spun up). Metadata is
# retro-filled on startup if a party row is missing fields.
_DEFAULT_PARTIES: list[dict[str, Any]] = [
    {
        "id": "democrat",
        "label": "Democratic Caucus",
        "color": "#2E5AA8",
        "ideology": "Modern American liberalism",
        "founded_year": 1828,
        "motto": "Working for a stronger middle class",
        "description": (
            "The Democratic Party is one of the two major contemporary U.S. political "
            "parties. Its modern coalition centers on social-safety-net expansion, civil "
            "rights, labor protections, climate action, and a regulated mixed economy."
        ),
        "history": (
            "Founded in the late 1820s around Andrew Jackson's coalition, the "
            "Democratic Party has reinvented itself several times — from the Solid "
            "South of the late 19th century, to FDR's New Deal coalition of organized "
            "labor and Northern liberals, to the post-1964 civil-rights realignment "
            "that drove Southern conservatives to the GOP. The modern party fuses "
            "professional-class liberals, organized labor, Black and Latino voters, "
            "and a growing democratic-socialist left flank."
        ),
        "key_policies": [
            "Affordable Care Act expansion and a public option",
            "Progressive taxation and IRS enforcement against tax evasion",
            "Federal climate investment via the Inflation Reduction Act framework",
            "Voting rights legislation (e.g. John Lewis VRAA)",
            "Codification of Roe and broader reproductive-rights protections",
        ],
        "notable_members": [
            "President Joe Biden",
            "Senate Majority Leader Chuck Schumer",
            "Speaker Emerita Nancy Pelosi",
            "Senator Elizabeth Warren",
            "Representative Alexandria Ocasio-Cortez",
        ],
        "national_committee_chair": "Jaime Harrison (DNC)",
        "electoral_strength": (
            "Minority caucus in both chambers of the 119th Congress: 45 senators "
            "plus 2 caucusing independents, and 212 House members as of July 2026."
        ),
        "voting_seats": 212,
        "created_at": "2026-06-15T00:00:00+00:00",
    },
    {
        "id": "republican",
        "label": "Republican Conference",
        "color": "#C0392B",
        "ideology": "Modern American conservatism",
        "founded_year": 1854,
        "motto": "Limited government, individual liberty, strong defense",
        "description": (
            "The Republican Party is one of the two major contemporary U.S. political "
            "parties. Its modern coalition centers on constitutional originalism, "
            "lower taxation, free-enterprise economics, religious-liberty protections, "
            "and a strong national defense."
        ),
        "history": (
            "Founded in 1854 by anti-slavery activists from the dying Whig Party, the "
            "GOP elected Abraham Lincoln in 1860 and shepherded Reconstruction. After "
            "decades as a pro-business, urban-industrial party, it remade itself "
            "around Goldwater conservatism, the Reagan coalition of fiscal "
            "conservatives plus social conservatives plus defense hawks, and most "
            "recently the Trump-era populist nationalist realignment that brought in "
            "working-class voters of all races."
        ),
        "key_policies": [
            "2017 Tax Cuts and Jobs Act and making its provisions permanent",
            "Border security, completion of the southern border wall, and Title 42",
            "School-choice expansion and parental rights in education",
            "Originalist judicial appointments at every federal level",
            "Repeal of EPA emissions rules constraining domestic oil and gas",
        ],
        "notable_members": [
            "Former President Donald Trump",
            "Senate Minority Leader Mitch McConnell",
            "Speaker Mike Johnson",
            "Senator Ted Cruz",
            "Governor Ron DeSantis",
        ],
        "national_committee_chair": "Michael Whatley (RNC)",
        "electoral_strength": (
            "Majority caucus in both chambers of the 119th Congress: 53 senators "
            "and 218 House members as of July 2026."
        ),
        "voting_seats": 218,
        "created_at": "2026-06-15T00:00:00+00:00",
    },
]

# Additional bundled parties seeded on first boot. Same shape as
# `_DEFAULT_PARTIES` — these are appended onto a fresh parties.json and
# auto-added to an existing one during `_backfill_party_metadata` if not
# already present, so a fresh install or a post-R2-D upgrade ends up with
# the full default set available in the Party Manager.
_BUNDLED_PARTIES: dict[str, dict[str, Any]] = {
    "libertarian": {
        "label": "Libertarian Caucus",
        "color": "#C2A14D",
        "ideology": "Classical liberalism / civil-libertarian populism",
        "founded_year": 1971,
        "motto": "Maximum freedom, minimum government",
        "description": (
            "The Libertarian Party advocates for free markets, civil liberties, "
            "non-interventionism, and a sharply limited federal government. It is the "
            "largest U.S. third party by registered membership."
        ),
        "history": (
            "Founded in Colorado in 1971 by activists frustrated with Nixon-era wage "
            "controls and the Vietnam War, the Libertarian Party has run a "
            "presidential candidate every cycle since 1972. Its 1980 ticket of Ed "
            "Clark and David Koch broke 1% of the popular vote; Gary Johnson's 2016 "
            "campaign crossed 3.3% — the LP's best modern showing. The party has "
            "since fractured between a pragmatic Classical-Liberal wing and the "
            "paleo-libertarian Mises Caucus."
        ),
        "key_policies": [
            "Repeal the federal income tax and abolish the IRS",
            "End the federal War on Drugs; full decriminalization and expungement",
            "Withdraw from foreign military entanglements; close overseas bases",
            "Abolish the Federal Reserve and return to a competing-currencies regime",
            "Repeal occupational licensing and most federal economic regulation",
        ],
        "notable_members": [
            "Former Governor Gary Johnson (2016 nominee)",
            "Spike Cohen (2020 VP nominee)",
            "Chase Oliver (2024 presidential nominee)",
            "Former Representative Justin Amash",
        ],
        "national_committee_chair": "Angela McArdle (LNC)",
        "electoral_strength": (
            "No federal officeholders. Largest U.S. third party by registration with "
            "ballot access in roughly 35 states for federal races."
        ),
    },
    "green": {
        "label": "Green Caucus",
        "color": "#2E8B57",
        "ideology": "Green politics / eco-socialism",
        "founded_year": 2001,
        "motto": "Ecology, social justice, grassroots democracy, peace",
        "description": (
            "The Green Party of the United States organizes around four pillars: "
            "ecological wisdom, social justice, grassroots democracy, and "
            "non-violence. Its policy agenda emphasizes climate action, economic "
            "redistribution, and demilitarization."
        ),
        "history": (
            "U.S. Greens grew out of state-level parties in the 1980s; the national "
            "Green Party formed in 2001 from the merger of the Association of State "
            "Green Parties. Ralph Nader's 2000 presidential run carried 2.7% of the "
            "vote and became a defining and controversial moment. Jill Stein has "
            "twice been the Green nominee, drawing the party further into a "
            "left-of-Democratic-Party identity."
        ),
        "key_policies": [
            "Green New Deal — 100% renewable electricity by 2030",
            "Single-payer Medicare-for-All",
            "Reparations and a Truth and Reconciliation Commission on race",
            "End all foreign military aid; close all overseas U.S. military bases",
            "Ranked-choice voting and public financing of all elections",
        ],
        "notable_members": [
            "Dr. Jill Stein (2012, 2016, 2024 presidential nominee)",
            "Howie Hawkins (2020 presidential nominee)",
            "Cornel West (independent run; long Green ally)",
        ],
        "national_committee_chair": "Anita Rios (GPUS co-chair)",
        "electoral_strength": (
            "Holds roughly 130 local elected offices nationwide. No federal "
            "officeholders since 2001. Strongest grass-roots presence in California, "
            "Maine, and the Pacific Northwest."
        ),
    },
    "constitution": {
        "label": "Constitution Caucus",
        "color": "#8B0000",
        "ideology": "Constitutional originalism, paleoconservatism, social conservatism",
        "founded_year": 1992,
        "motto": "Honor God, family, and the Constitution",
        "description": (
            "The Constitution Party (originally U.S. Taxpayers Party) advocates a "
            "strict constructionist reading of the U.S. Constitution, a sharply "
            "smaller federal government, traditional Christian social values, and "
            "non-interventionist foreign policy."
        ),
        "history": (
            "Founded by Howard Phillips in 1992 as the U.S. Taxpayers Party, it "
            "renamed itself the Constitution Party in 1999. Its high-water mark was "
            "Chuck Baldwin's 2008 presidential campaign, which polled 0.15% of the "
            "popular vote. The party draws heavily from former Republicans alienated "
            "by what they see as the GOP's drift on abortion, federalism, and "
            "interventionist foreign policy."
        ),
        "key_policies": [
            "Constitutional ban on abortion; defund Planned Parenthood",
            "Eliminate the Department of Education and return schooling to states",
            "Withdraw from the UN, NATO, and most international treaties",
            "End birthright citizenship for children of undocumented parents",
            "Restore the gold standard and abolish the Federal Reserve",
        ],
        "notable_members": [
            "Howard Phillips (founder)",
            "Pastor Chuck Baldwin (2008 nominee)",
            "Darrell Castle (2016 nominee)",
            "Don Blankenship (2020 nominee)",
        ],
        "national_committee_chair": "Jim Clymer",
        "electoral_strength": (
            "No federal officeholders. Ballot access in roughly 14 states; relies on "
            "write-in eligibility elsewhere."
        ),
    },
    "reform": {
        "label": "Reform Caucus",
        "color": "#9932CC",
        "ideology": "Fiscal moderation, anti-corruption, electoral reform",
        "founded_year": 1995,
        "motto": "Reform politics — fiscal responsibility, government accountability",
        "description": (
            "The Reform Party was founded around Ross Perot's anti-deficit, "
            "anti-corruption populism. It seeks balanced budgets, campaign-finance "
            "reform, term limits, and a foreign policy guided by U.S. interests "
            "narrowly defined."
        ),
        "history": (
            "Born from Ross Perot's 1992 independent run, which carried 18.9% of the "
            "popular vote — the strongest third-party performance since Theodore "
            "Roosevelt in 1912. Perot ran again under the Reform banner in 1996, "
            "winning 8.4%. Jesse Ventura's 1998 Minnesota gubernatorial victory was "
            "the party's only governorship. The party fractured after 2000 between "
            "Pat Buchanan's paleoconservative wing and remaining centrists."
        ),
        "key_policies": [
            "Constitutional balanced-budget amendment with caps on federal debt",
            "Congressional term limits — 12 years lifetime maximum",
            "Public financing of federal elections; ban on corporate PACs",
            "Renegotiate trade agreements to favor U.S. manufacturers",
            "No new wars without an explicit congressional declaration",
        ],
        "notable_members": [
            "Ross Perot (founder; 1996 nominee)",
            "Governor Jesse Ventura (Minnesota, 1999–2003)",
            "Pat Buchanan (2000 nominee)",
        ],
        "national_committee_chair": "Nicholas Hensley",
        "electoral_strength": (
            "No current federal or gubernatorial officeholders. Maintains state-level "
            "ballot lines in Mississippi, Kansas, and Florida."
        ),
    },
    "forward": {
        "label": "Forward Caucus",
        "color": "#E67E22",
        "ideology": "Centrism, anti-polarization, structural electoral reform",
        "founded_year": 2021,
        "motto": "Not left. Not right. Forward.",
        "description": (
            "The Forward Party advocates a centrist coalition between disaffected "
            "Democrats and Republicans, with a platform focused on structural "
            "electoral reforms — ranked-choice voting, open primaries, "
            "independent redistricting — rather than ideological positions."
        ),
        "history": (
            "Founded in 2021 by former Democratic presidential candidate Andrew Yang "
            "after the launch of his Humanity Forward super-PAC. Merged in 2022 with "
            "Christine Todd Whitman's Renew America Movement and David Jolly's "
            "Serve America Movement to form the current Forward Party. Has secured "
            "ballot access in over a dozen states and run a handful of state "
            "legislative candidates."
        ),
        "key_policies": [
            "Nonpartisan primaries open to all voters",
            "Ranked-choice voting for all federal elections",
            "Independent redistricting commissions in every state",
            "Universal basic income — $1,000/month for every American adult",
            "Modernize the federal regulatory apparatus with sunset clauses",
        ],
        "notable_members": [
            "Andrew Yang (co-chair, founder)",
            "Former Governor Christine Todd Whitman (co-chair)",
            "Former Representative David Jolly (co-chair)",
        ],
        "national_committee_chair": "Lindsey Williams Drath (CEO)",
        "electoral_strength": (
            "No federal officeholders. Secured ballot access in roughly 15 states; "
            "has elected a handful of municipal officials in Texas and Utah."
        ),
    },
    "dsa": {
        "label": "Democratic Socialists Caucus",
        "color": "#C71585",
        "ideology": "Democratic socialism",
        "founded_year": 1982,
        "motto": "We are socialists because we share a vision of a humane social order",
        "description": (
            "Note: DSA is not a ballot-line party but a national membership "
            "organization that operates as a caucus within the broader U.S. left, "
            "primarily by endorsing and supporting candidates running on Democratic "
            "Party ballot lines. Included here because it functions as a distinct "
            "voting bloc in deliberations."
        ),
        "history": (
            "Founded in 1982 from the merger of Michael Harrington's Democratic "
            "Socialist Organizing Committee and the New American Movement. Membership "
            "remained around 5,000 for three decades until Bernie Sanders' 2016 "
            "presidential run; DSA grew to over 90,000 members by 2021. Its members "
            "now hold a handful of seats in Congress and dozens in state legislatures, "
            "all running on Democratic Party ballot lines."
        ),
        "key_policies": [
            "Medicare for All — abolish private health insurance",
            "Green New Deal with a federal jobs guarantee",
            "Free public college and student-debt cancellation",
            "Federal protection of the right to organize and sectoral bargaining",
            "Defund and demilitarize police; community-controlled public safety",
        ],
        "notable_members": [
            "Senator Bernie Sanders (longtime ally; not a formal member)",
            "Representative Alexandria Ocasio-Cortez (DSA member)",
            "Representative Rashida Tlaib (DSA member)",
            "Representative Cori Bush (DSA member)",
            "Representative Jamaal Bowman (DSA member)",
        ],
        "national_committee_chair": "Ashik Siddique (NPC co-chair)",
        "electoral_strength": (
            "Operates as a caucus — DSA-endorsed candidates hold 5+ U.S. House seats "
            "and 80+ state legislative seats, all on Democratic Party ballot lines."
        ),
    },
    "wfp": {
        "label": "Working Families Caucus",
        "color": "#FF6600",
        "ideology": "Progressive labor populism",
        "founded_year": 1998,
        "motto": "An economy that works for everyone, a politics that includes everyone",
        "description": (
            "The Working Families Party is a progressive labor-aligned party. In "
            "fusion-voting states like New York and Connecticut it runs on its own "
            "ballot line alongside the Democratic Party; elsewhere it operates as an "
            "endorsing organization for progressive Democratic primary candidates."
        ),
        "history": (
            "Founded in 1998 in New York by ACORN, the Communications Workers of "
            "America, and several smaller unions. Took advantage of New York's "
            "fusion-voting laws to pressure the Democratic Party from the left on "
            "labor, housing, and criminal-justice issues. Has expanded to roughly 14 "
            "states and routinely endorses in major U.S. Senate and gubernatorial "
            "races."
        ),
        "key_policies": [
            "$25/hr federal minimum wage indexed to inflation",
            "PRO Act and full restoration of collective-bargaining rights",
            "Universal childcare and paid family leave",
            "Bold housing investment — social housing and rent stabilization",
            "End cash bail and over-policing of low-income communities",
        ],
        "notable_members": [
            "Maurice Mitchell (National Director)",
            "Public Advocate Jumaane Williams (NYC)",
            "Lieutenant Governor Antonio Delgado (NY)",
            "Representative Bowman, Bush, Lee (all WFP-endorsed)",
        ],
        "national_committee_chair": "Maurice Mitchell (National Director)",
        "electoral_strength": (
            "Major fusion-line presence in NY and CT, electing dozens of city "
            "council members and state legislators. Active endorsement operation in "
            "12+ other states."
        ),
    },
}

# Required party fields and the per-field defaults applied when a row is read
# from disk and missing them.
_PARTY_FIELD_DEFAULTS: dict[str, Any] = {
    "ideology": "",
    "founded_year": None,
    "motto": "",
    "description": "",
    "history": "",
    "key_policies": [],
    "notable_members": [],
    "national_committee_chair": "",
    "electoral_strength": "",
    "color": "#C2A14D",
    # Configured seat count used for seat-weighted voting (real-chamber
    # weight). None = party votes unweighted. Distinct from the derived
    # `seats` API field, which counts persona files.
    "voting_seats": None,
    "created_at": None,
}

# One lock per debate id, lazily created. Protects per-debate file writes.
_debate_locks: dict[str, asyncio.Lock] = {}


def _data_dir() -> Path:
    return get_settings().data_dir


def _personas_dir() -> Path:
    return _data_dir() / "personas"


def _parties_file() -> Path:
    return _data_dir() / "parties.json"


def _debate_lock(debate_id: str) -> asyncio.Lock:
    lock = _debate_locks.get(debate_id)
    if lock is None:
        lock = asyncio.Lock()
        _debate_locks[debate_id] = lock
    return lock


# ---------------------------------------------------------------------------
# Bootstrap: seed personas + parties on first run
# ---------------------------------------------------------------------------

def ensure_seeded() -> None:
    """If `data/personas/` is empty, copy from `src/agents/data/`."""
    data_dir = _data_dir()
    personas_dir = _personas_dir()
    parties_file = _parties_file()

    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "debates").mkdir(parents=True, exist_ok=True)

    if not parties_file.exists():
        _atomic_write_json(parties_file, {"parties": _DEFAULT_PARTIES})
        log.info("seeded parties.json")
    # Always run the backfill — it tops up existing entries with newly added
    # schema fields and appends any bundled party (Green, DSA, …) that the
    # parties.json doesn't yet carry.
    _backfill_party_metadata()
    _backfill_persona_images()

    source = REPO_ROOT / "src" / "agents" / "data"
    if not source.is_dir():
        log.warning("seed source missing: %s", source)
        return

    personas_dir.mkdir(parents=True, exist_ok=True)
    seeded_parties: list[str] = []
    for party_dir in source.iterdir():
        if not party_dir.is_dir():
            continue
        dst = personas_dir / party_dir.name
        # Only seed a party folder the first time we see it. If the user has
        # an existing `data/personas/<party>/` directory (even empty after a
        # deliberate cleanup) we leave it alone — they can re-seed by
        # deleting the folder. This lets R2-D's new bundled caucuses
        # (green, constitution, …) appear on upgrade without trampling any
        # persona the user has edited or removed.
        if dst.exists():
            continue
        dst.mkdir(parents=True, exist_ok=True)
        for json_file in party_dir.glob("*.json"):
            shutil.copy2(json_file, dst / json_file.name)
        seeded_parties.append(party_dir.name)
    if seeded_parties:
        log.info("seeded personas/ for parties: %s", ", ".join(sorted(seeded_parties)))


def _backfill_party_metadata() -> None:
    """Bring an older parties.json up to the current schema in place.

    Performs two passes:
      1. For each existing party row, apply bundled metadata for that id
         (rich fields from `_DEFAULT_PARTIES` or `_BUNDLED_PARTIES`) and fill
         any missing scalar with `_PARTY_FIELD_DEFAULTS`.
      2. Append any bundled party (libertarian, green, dsa, …) that the
         parties.json doesn't already carry. This is how R2-D's new caucuses
         show up on an existing install without the user having to add them
         manually.
    The file is only rewritten if anything actually changed.
    """
    parties_file = _parties_file()
    if not parties_file.exists():
        return
    with parties_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    entries = data.get("parties", [])
    by_default_id = {e["id"]: e for e in _DEFAULT_PARTIES}
    existing_ids = {e["id"] for e in entries}
    changed = False

    from datetime import datetime, timezone
    now_ts = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for entry in entries:
        before = dict(entry)
        pid = entry["id"]
        canonical = by_default_id.get(pid) or _BUNDLED_PARTIES.get(pid)
        if canonical:
            for k, v in canonical.items():
                if not entry.get(k):
                    entry[k] = v
        for k, default in _PARTY_FIELD_DEFAULTS.items():
            if k not in entry:
                entry[k] = default
        if entry.get("created_at") is None:
            entry["created_at"] = now_ts
        if entry != before:
            changed = True

    # Pass 2: append any bundled-but-missing party.
    bundled_pool: list[tuple[str, dict[str, Any]]] = [
        (pid, dict(payload)) for pid, payload in _BUNDLED_PARTIES.items()
        if pid not in existing_ids
    ]
    for pid, payload in bundled_pool:
        payload.setdefault("id", pid)
        for k, default in _PARTY_FIELD_DEFAULTS.items():
            payload.setdefault(k, default)
        payload.setdefault("created_at", now_ts)
        entries.append(payload)
        changed = True

    if changed:
        _atomic_write_json(parties_file, {"parties": entries})
        log.info("backfilled parties.json metadata")


def _backfill_persona_images() -> None:
    """Bring older persona files up to the current image schema in place.

    Walks `data/personas/<party>/*.json`; any file missing the `image_url`
    key gets `image_url` + `image_attribution` copied from the matching
    bundled persona in `src/agents/data/<party>/<id>.json` (empty strings
    when there is no bundled match). Each file is only rewritten when it
    actually changed.
    """
    personas_root = _personas_dir()
    if not personas_root.is_dir():
        return
    bundled_root = REPO_ROOT / "src" / "agents" / "data"
    backfilled = 0
    for party_dir in sorted(personas_root.iterdir()):
        if not party_dir.is_dir():
            continue
        for json_file in sorted(party_dir.glob("*.json")):
            try:
                with json_file.open("r", encoding="utf-8") as f:
                    record = json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                log.warning("skipping unreadable persona %s: %s", json_file, e)
                continue
            if "image_url" in record:
                continue
            image_url, image_attribution = "", ""
            bundled_file = bundled_root / party_dir.name / json_file.name
            if bundled_file.is_file():
                try:
                    with bundled_file.open("r", encoding="utf-8") as f:
                        bundled = json.load(f)
                    image_url = bundled.get("image_url", "")
                    image_attribution = bundled.get("image_attribution", "")
                except (OSError, json.JSONDecodeError) as e:
                    log.warning("unreadable bundled persona %s: %s", bundled_file, e)
            record["image_url"] = image_url
            record["image_attribution"] = image_attribution
            _atomic_write_json(json_file, record)
            backfilled += 1
    if backfilled:
        log.info("backfilled image fields on %d persona files", backfilled)


# ---------------------------------------------------------------------------
# Atomic write helpers
# ---------------------------------------------------------------------------

def _atomic_write_json(path: Path, payload: Any) -> None:
    """Write JSON atomically — temp file + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
        f.write("\n")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Personas
# ---------------------------------------------------------------------------

def _agent_to_dict(agent: Agent) -> dict[str, Any]:
    """Serialize an Agent (with nested Source dataclasses) to a plain dict."""
    return asdict(agent)


def _summary(agent: Agent) -> dict[str, Any]:
    """List-view fields per API_SPEC."""
    return {
        "id": agent.id,
        "name": agent.name,
        "title": agent.title,
        "party": agent.party,
        "role": agent.role,
        "specialty": agent.specialty,
        "negotiation_posture": agent.negotiation_posture,
        "persona_last_updated": agent.persona_last_updated,
        "image_url": agent.image_url,
    }


def load_all_personas() -> list[Agent]:
    """Walk `data/personas/*/*.json` and return every Agent, sorted by id."""
    root = _personas_dir()
    if not root.is_dir():
        return []
    agents: list[Agent] = []
    for party_dir in sorted(root.iterdir()):
        if not party_dir.is_dir():
            continue
        for json_file in sorted(party_dir.glob("*.json")):
            try:
                agents.append(Agent.from_json(json_file))
            except ValueError as e:
                log.warning("skipping malformed persona %s: %s", json_file, e)
    agents.sort(key=lambda a: a.id)
    return agents


def list_personas(
    *,
    party: str | None = None,
    role: str | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    """Return summary records for personas, optionally filtered."""
    agents = load_all_personas()
    if party:
        agents = [a for a in agents if a.party == party]
    if role:
        agents = [a for a in agents if a.role == role]
    if query:
        needle = query.lower()
        agents = [
            a for a in agents
            if needle in (a.name + a.title + a.specialty).lower()
        ]
    return [_summary(a) for a in agents]


def get_persona(persona_id: str) -> dict[str, Any] | None:
    """Full persona record or None if not found."""
    for agent in load_all_personas():
        if agent.id == persona_id:
            return _agent_to_dict(agent)
    return None


def _persona_path(party: str, persona_id: str) -> Path:
    return _personas_dir() / party / f"{persona_id}.json"


def save_persona(persona: dict[str, Any], *, expected_id: str | None = None) -> dict[str, Any]:
    """Validate and write a persona to disk. Returns the saved record.

    Raises ValueError on validation failure (unknown enum, ally/rival rules…).
    If the persona's `party` changed since the last save, the previous on-disk
    file is removed so we don't leave an orphan in the old party's directory.
    """
    agent = Agent(**persona)  # raises ValueError on bad enums/sources

    # Detect a party change against the current on-disk file. The lookup walks
    # all party directories rather than trusting the caller's payload, which
    # may already be the new party.
    previous_path: Path | None = None
    for existing in load_all_personas():
        if existing.id == agent.id and existing.party != agent.party:
            previous_path = _persona_path(existing.party, existing.id)
            break

    others = [a for a in load_all_personas() if a.id != agent.id]
    validate_relationships(others + [agent])
    if expected_id is not None and expected_id != agent.id:
        raise ValueError(f"id mismatch: path={expected_id!r} body={agent.id!r}")
    path = _persona_path(agent.party, agent.id)
    _atomic_write_json(path, _agent_to_dict(agent))

    if previous_path is not None and previous_path.exists() and previous_path != path:
        try:
            previous_path.unlink()
        except OSError as e:
            log.warning("orphaned persona file %s left behind: %s", previous_path, e)
    return _agent_to_dict(agent)


def delete_persona(persona_id: str, *, force: bool = False) -> bool:
    """Delete a persona. Returns False if not found.

    Raises ValueError if other personas still reference this id (use force=True
    to strip references and delete anyway).
    """
    target = None
    referenced_by: list[Agent] = []
    for agent in load_all_personas():
        if agent.id == persona_id:
            target = agent
        elif persona_id in agent.allies or persona_id in agent.rivals:
            referenced_by.append(agent)
    if target is None:
        return False
    if referenced_by and not force:
        names = ", ".join(a.id for a in referenced_by)
        raise ValueError(f"persona {persona_id} is referenced by: {names}")
    if force:
        for ref in referenced_by:
            ref.allies = [x for x in ref.allies if x != persona_id]
            ref.rivals = [x for x in ref.rivals if x != persona_id]
            _atomic_write_json(_persona_path(ref.party, ref.id), _agent_to_dict(ref))
    path = _persona_path(target.party, target.id)
    if path.exists():
        path.unlink()
    return True


# ---------------------------------------------------------------------------
# Parties
# ---------------------------------------------------------------------------

def _read_parties_file() -> list[dict[str, Any]]:
    parties_file = _parties_file()
    if parties_file.exists():
        with parties_file.open("r", encoding="utf-8") as f:
            return json.load(f).get("parties", [])
    return list(_DEFAULT_PARTIES)


def list_parties() -> list[dict[str, Any]]:
    """Return party registry, with seat counts derived from persona files."""
    registry = _read_parties_file()
    personas_root = _personas_dir()
    out: list[dict[str, Any]] = []
    for entry in registry:
        seats = 0
        party_dir = personas_root / entry["id"]
        if party_dir.is_dir():
            seats = sum(1 for _ in party_dir.glob("*.json"))
        out.append({**entry, "seats": seats})
    return out


def get_party(party_id: str) -> dict[str, Any] | None:
    """Single party record with derived seat count, or None."""
    for entry in list_parties():
        if entry["id"] == party_id:
            return entry
    return None


def save_party(party: dict[str, Any]) -> dict[str, Any]:
    """Add or replace a party in the registry. Fills in defaults for missing
    metadata fields and stamps `created_at` if unset."""
    required = {"id", "label", "color"}
    if not required.issubset(party):
        missing = required - set(party)
        raise ValueError(f"party missing fields: {sorted(missing)}")
    pid = party["id"].strip()
    if not pid:
        raise ValueError("party id cannot be empty")
    if not pid.replace("_", "").isalnum():
        raise ValueError(
            f"party id {pid!r} must be alphanumeric with underscores only"
        )
    if party.get("voting_seats") is not None:
        seats_value = party["voting_seats"]
        if not isinstance(seats_value, int) or isinstance(seats_value, bool) or seats_value < 0:
            raise ValueError("voting_seats must be a non-negative integer or null")
    parties = _read_parties_file()
    existing = next((p for p in parties if p["id"] == pid), None)
    payload: dict[str, Any] = dict(existing or {})
    for k, default in _PARTY_FIELD_DEFAULTS.items():
        payload.setdefault(k, default)
    payload.update({k: v for k, v in party.items() if v is not None})
    payload["id"] = pid
    if not payload.get("created_at"):
        from datetime import datetime, timezone
        payload["created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    parties = [p for p in parties if p["id"] != pid]
    parties.append(payload)
    _atomic_write_json(_parties_file(), {"parties": parties})
    # Make sure the persona dir exists so new personas can be saved there.
    (_personas_dir() / pid).mkdir(parents=True, exist_ok=True)
    seats = sum(1 for _ in (_personas_dir() / pid).glob("*.json"))
    return {**payload, "seats": seats}


def update_party(party_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    """Partial update — merge new fields into the existing record."""
    parties = _read_parties_file()
    target = next((p for p in parties if p["id"] == party_id), None)
    if target is None:
        raise KeyError(party_id)
    # 'id' is immutable.
    patch = {k: v for k, v in patch.items() if k != "id"}
    merged = {**target, **patch}
    return save_party(merged)


def delete_party(party_id: str, *, force: bool = False) -> bool:
    """Remove a party. Rejects if any persona is still seated there unless
    `force=True` (which also deletes the personas). Returns False if not
    found. The two ground-truth parties cannot be deleted."""
    if party_id in {"democrat", "republican"}:
        raise ValueError(
            f"the {party_id!r} caucus is part of the seeded chamber and cannot be removed"
        )
    parties = _read_parties_file()
    target = next((p for p in parties if p["id"] == party_id), None)
    if target is None:
        return False
    party_dir = _personas_dir() / party_id
    seated = sorted(party_dir.glob("*.json")) if party_dir.is_dir() else []
    if seated and not force:
        ids = ", ".join(p.stem for p in seated)
        raise ValueError(
            f"party {party_id!r} still has seated personas: {ids}"
        )
    if force:
        # Cascade-delete personas in the party. Other-party references to
        # them get stripped too.
        for f in seated:
            try:
                pid = f.stem
            except Exception:
                continue
            try:
                delete_persona(pid, force=True)
            except Exception as e:
                log.warning("failed to delete persona %s during party cascade: %s", pid, e)
    if party_dir.is_dir() and not any(party_dir.iterdir()):
        try:
            party_dir.rmdir()
        except OSError:
            pass
    parties = [p for p in parties if p["id"] != party_id]
    _atomic_write_json(_parties_file(), {"parties": parties})
    return True


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------

def relationships() -> dict[str, list[dict[str, Any]]]:
    """Derive a node/edge graph from current personas (intra-party only)."""
    agents = load_all_personas()
    nodes = [
        {"id": a.id, "name": a.name, "party": a.party, "role": a.role}
        for a in agents
    ]
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for a in agents:
        for ally in a.allies:
            lo, hi = sorted((a.id, ally))
            key = ("ally", lo, hi)
            if key not in seen:
                edges.append({"from": a.id, "to": ally, "type": "ally"})
                seen.add(key)
        for rival in a.rivals:
            lo, hi = sorted((a.id, rival))
            key = ("rival", lo, hi)
            if key not in seen:
                edges.append({"from": a.id, "to": rival, "type": "rival"})
                seen.add(key)
    return {"nodes": nodes, "edges": edges}
