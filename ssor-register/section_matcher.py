"""Parses CCTNS's free-text ACTS_SECTIONS field into (act_name, section_code)
pairs for matching against ssor_kb.

Real samples pulled from the live API (2022-2026, ~132k crimes) show this
field mixes 100+ act abbreviations in one comma-separated string, e.g.:

    "354B IPC, 354C IPC, 506 IPC, 509 IPC, 67A ITA-2000-2008"
    "64(2)(m) BNS, 78 BNS, 137(2) BNS"
    "5 POCSO ACT 2012, r/w 6 POCSO ACT 2012, 3(2)(v) SC ST POA ACT 2015"
    "332,196 BNS"   -- one act suffix shared by multiple bare section numbers

Rather than parse every act in that mess, this only extracts sections
immediately attached to one of our four in-scope act markers (BNS, POCSO,
IT Act, ITPA) and ignores everything else -- IPC, Arms Act, MV Act, SC/ST
Act, etc. are not in the concept note's scope and are silently skipped.

ITPA's marker pattern is unverified against real data -- 0 hits across the
132k-crime sample -- so section_code extraction for it works the same way
as BNS/POCSO but hasn't been seen live yet.
"""
from __future__ import annotations

import re

_RW_RE = re.compile(r'\br/w\b', re.IGNORECASE)

# One comma-joined run of section tokens (bare digits, optional letter
# suffix, optional hyphenated suffix, optional parenthesized sub-clauses)
# immediately followed by one of our four act markers.
_SECTION_TOKEN = r'\d+[\w\-]*(?:\([^,()]*\))*'
_SECTIONS_RUN = rf'(?P<sections>{_SECTION_TOKEN}(?:\s*,\s*{_SECTION_TOKEN})*)'
# Trailing year(s) must be consumed as part of the act marker itself --
# otherwise a bare "2012" left dangling after "POCSO ACT 2012" gets
# swallowed as a bogus section number by the next match's greedy run.
_ACT_ALTERNATION = r'(?P<act>BNS|POCSO\s+ACT(?:\s+\d{4})?|ITA[-\s]?2000(?:[-\s]?2008)?|ITPA)'
_SECTION_ACT_RE = re.compile(rf'{_SECTIONS_RUN}\s+{_ACT_ALTERNATION}\b', re.IGNORECASE)

_ACT_NAME_BY_MARKER = {
    'BNS': 'BNS',
    'POCSO ACT': 'POCSO',
    'ITPA': 'ITPA',
}


def _bucket_act_marker(raw_marker: str) -> str:
    upper = raw_marker.upper()
    if upper.startswith('ITA'):
        return 'IT_ACT'
    for prefix, act_name in _ACT_NAME_BY_MARKER.items():
        if upper.startswith(prefix):
            return act_name
    return upper  # unreachable given _ACT_ALTERNATION, kept defensive


def normalize_section_code(raw: str) -> str:
    """'64(2)(m)' -> '64'; '66-D' -> '66D'; '67A' -> '67A'."""
    base = raw.split('(', 1)[0]
    return base.replace('-', '').strip().upper()


def extract_sections(acts_sections: str) -> list[tuple[str, str]]:
    """Return every (act_name, section_code) pair found for our four
    in-scope acts. Everything else in the free-text field is ignored."""
    if not acts_sections:
        return []
    cleaned = _RW_RE.sub('', acts_sections)

    pairs: list[tuple[str, str]] = []
    for match in _SECTION_ACT_RE.finditer(cleaned):
        act_name = _bucket_act_marker(match.group('act'))
        for raw_section in match.group('sections').split(','):
            section_code = normalize_section_code(raw_section)
            if section_code:
                pairs.append((act_name, section_code))
    return pairs
