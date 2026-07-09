# SSOR (State Sexual Offender Register) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a read-only classifier that scans already-loaded CCTNS data for convicted sexual-offence cases, tags each with the colour tier from the SSOR concept note (RED/ORANGE/BLUE/BLACK/PINK/GREEN, SILVER as internal-only), and produces a minimal offender-register profile — nothing beyond what the concept note requires.

**Architecture:** New standalone module `ssor-register/` (same shape as `etl-fpb-accused/`: `config.py` + main script + `migrations/`). No external API calls — it is a SQL-only aggregation layer over tables already populated by the existing 17-step master pipeline (`crimes`, `accused`, `persons`, `chargesheet_acts_sections`, `ir_conviction_acquittal`, `disposal`, `interrogation_reports`, `files`, `hierarchy`). Two new tables hold the output: `ssor_offense_records` (one row per convicted case) and `ssor_offenders` (one row per person — the actual register entry). A static seed table `ssor_section_tier_map` holds the doc's section→tier mapping so tier logic lives in data, not scattered code.

**Tech Stack:** Python 3, psycopg2 (via existing `db_pooling.PostgreSQLConnectionPool`), PostgreSQL. No new dependencies.

## Global Constraints

- Only sections listed in the SSOR concept note §5 table are in scope: BNS 63,64,65(1),65(2),66,70,70(2),71,74,75,76,77,78,79,111,143,144; POCSO 5,6,11,12,13,14; IT Act 66E,67,67A,67B; ITPA 3,4,5,6,7. No IPC-era (pre-BNS, pre-2024-07-01) section crosswalk in this pass — flag unmapped rows, don't guess.
- Entry gate is conviction only: `ir_conviction_acquittal.verdict` must indicate a conviction (fall back to `disposal.case_status` only if no IR verdict row exists for that crime). Never register an accused/under-trial.
- Juveniles (`accused.is_ccl = true` on the matched case) are still classified internally but marked `disclosable = false` — never surfaced in any external/disclosable query.
- Keep the profile minimal: only the columns listed in Task 4 below. Do not pull family history, financial history, gang/associate details, drug details, or property/vehicle specifics — none of that belongs in this register.
- No new Python dependency. Reuse `db_pooling.PostgreSQLConnectionPool`, `env_utils.resolve_db_config`/`resolve_table_name`, `colorlog` — same as every other ETL module in this repo.
- This repo has no pytest convention (`requirements.txt` doesn't include it) — tests here are stdlib-`assert` self-checks run via `python3 test_x.py`, matching the rest of the repo.

---

### Task 1: Section→tier lookup table + register schema (migration)

**Files:**
- Create: `ssor-register/migrations/001_create_ssor_tables.sql`

**Interfaces:**
- Produces: tables `public.ssor_section_tier_map(act_name, section_code, tier, severity_rank, description)`, `public.ssor_offense_records(...)`, `public.ssor_offenders(...)` — exact columns below, consumed by Task 4's script.

- [ ] **Step 1: Write the migration SQL**

```sql
-- =============================================================================
-- ssor-register: section->tier lookup + register tables for the State Sexual
-- Offender Register concept note. Scope is deliberately narrow: only the
-- BNS/POCSO/IT Act/ITPA sections named in the note's classification table.
-- IPC-era (pre-2024-07-01) sections are NOT mapped here -- see note in
-- section_matcher.py bucket_act_name().
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.ssor_section_tier_map (
    id SERIAL PRIMARY KEY,
    act_name TEXT NOT NULL,       -- 'BNS' | 'POCSO' | 'IT_ACT' | 'ITPA'
    section_code TEXT NOT NULL,   -- normalized, e.g. '65(1)', '66E'
    tier TEXT NOT NULL,           -- 'RED' | 'ORANGE' | 'BLUE' | 'BLACK' | 'PINK'
    severity_rank INT NOT NULL,   -- higher = graver; used to pick highest tier per person
    description TEXT,
    CONSTRAINT uq_ssor_section_tier UNIQUE (act_name, section_code)
);

INSERT INTO public.ssor_section_tier_map (act_name, section_code, tier, severity_rank, description) VALUES
    ('BNS', '63', 'RED', 100, 'Rape - definition'),
    ('BNS', '64', 'RED', 100, 'Rape - punishment'),
    ('BNS', '65(1)', 'RED', 100, 'Rape of girl under 16'),
    ('BNS', '65(2)', 'RED', 100, 'Rape of girl under 12'),
    ('BNS', '66', 'RED', 100, 'Rape causing death or persistent vegetative state'),
    ('BNS', '70', 'RED', 100, 'Gang rape'),
    ('BNS', '70(2)', 'RED', 100, 'Gang rape - victim under 18'),
    ('POCSO', '5', 'RED', 100, 'Aggravated penetrative sexual assault'),
    ('POCSO', '6', 'RED', 100, 'Aggravated penetrative sexual assault - punishment'),
    ('BNS', '71', 'ORANGE', 80, 'Repeat/habitual sexual offender'),
    ('BNS', '111', 'BLACK', 90, 'Organised crime'),
    ('BNS', '143', 'BLACK', 90, 'Trafficking of persons'),
    ('BNS', '144', 'BLACK', 90, 'Exploitation of a trafficked person'),
    ('ITPA', '3', 'BLACK', 90, 'Keeping a brothel'),
    ('ITPA', '4', 'BLACK', 90, 'Living on earnings of prostitution'),
    ('ITPA', '5', 'BLACK', 90, 'Procuring / inducing person for prostitution'),
    ('ITPA', '6', 'BLACK', 90, 'Detention of a person in premises where prostitution is carried on'),
    ('ITPA', '7', 'BLACK', 90, 'Prostitution in or near public places'),
    ('IT_ACT', '66E', 'BLUE', 60, 'Capturing/transmitting image of private area without consent'),
    ('IT_ACT', '67', 'BLUE', 60, 'Publishing obscene material in electronic form'),
    ('IT_ACT', '67A', 'BLUE', 60, 'Publishing sexually explicit material'),
    ('IT_ACT', '67B', 'BLUE', 60, 'Child sexual abuse material'),
    ('BNS', '77', 'BLUE', 60, 'Voyeurism'),
    ('POCSO', '11', 'BLUE', 60, 'Sexual harassment of a child'),
    ('POCSO', '12', 'BLUE', 60, 'Punishment for sexual harassment of a child'),
    ('POCSO', '13', 'BLUE', 60, 'Use of child for pornographic purposes'),
    ('POCSO', '14', 'BLUE', 60, 'Punishment for pornographic purposes involving a child'),
    ('BNS', '74', 'PINK', 40, 'Assault/criminal force to woman with intent to outrage modesty'),
    ('BNS', '75', 'PINK', 40, 'Sexual harassment'),
    ('BNS', '76', 'PINK', 40, 'Assault with intent to disrobe'),
    ('BNS', '78', 'PINK', 40, 'Stalking'),
    ('BNS', '79', 'PINK', 40, 'Insult to modesty of a woman')
ON CONFLICT (act_name, section_code) DO NOTHING;

-- One row per (person, crime) convicted match -- keeps every applicable
-- section on record per doc S5.8, before cross-case rollup.
CREATE TABLE IF NOT EXISTS public.ssor_offense_records (
    id BIGSERIAL PRIMARY KEY,
    person_id character varying(50) NOT NULL,
    crime_id character varying(50) NOT NULL,
    fir_num character varying(50),
    ps_code character varying(20),
    matched_sections JSONB NOT NULL,   -- [{"act_name":"BNS","section_code":"64","tier":"RED"}, ...]
    record_tier TEXT NOT NULL,         -- highest tier among matched_sections for this case
    is_juvenile_at_offence BOOLEAN NOT NULL DEFAULT false,
    conviction_date DATE,
    sentence_if_convicted TEXT,
    fine_amount_in_inr NUMERIC,
    court_name TEXT,
    appeal_status TEXT,
    date_created TIMESTAMP WITH TIME ZONE DEFAULT now(),
    CONSTRAINT uq_ssor_offense_person_crime UNIQUE (person_id, crime_id)
);

CREATE INDEX IF NOT EXISTS idx_ssor_offense_records_person ON public.ssor_offense_records (person_id);

-- One row per offender -- the actual register entry, rolled up across all
-- of that person's matched convictions.
CREATE TABLE IF NOT EXISTS public.ssor_offenders (
    person_id character varying(50) PRIMARY KEY,
    full_name TEXT,
    alias TEXT,
    date_of_birth DATE,
    age INTEGER,
    gender TEXT,
    photo_file_url TEXT,
    present_address TEXT,
    present_district TEXT,
    jurisdiction_ps_code character varying(20),
    phone_number TEXT,
    highest_tier TEXT NOT NULL,        -- RED|ORANGE|BLUE|BLACK|PINK|GREEN
    disclosable BOOLEAN NOT NULL DEFAULT true,  -- false if any matched offence was as a juvenile
    retention_years INTEGER,           -- NULL = life (subject to periodic review)
    review_date DATE,
    is_in_jail BOOLEAN,
    is_on_bail BOOLEAN,
    is_absconding BOOLEAN,
    is_dead BOOLEAN,
    is_rehabilitated BOOLEAN,
    date_created TIMESTAMP WITH TIME ZONE DEFAULT now(),
    date_modified TIMESTAMP WITH TIME ZONE DEFAULT now()
);

COMMIT;
```

- [ ] **Step 2: Run the migration**

Run: `psql "$DATABASE_URL" -f ssor-register/migrations/001_create_ssor_tables.sql`
Expected: `BEGIN` ... `INSERT 0 32` ... `COMMIT` (32 = number of seed rows above)

- [ ] **Step 3: Verify seed data landed**

Run: `psql "$DATABASE_URL" -c "SELECT tier, count(*) FROM public.ssor_section_tier_map GROUP BY tier ORDER BY tier;"`
Expected: `BLACK|8`, `BLUE|9`, `ORANGE|1`, `PINK|5`, `RED|9` (32 total)

- [ ] **Step 4: Commit**

```bash
git add ssor-register/migrations/001_create_ssor_tables.sql
git commit -m "feat(ssor): add section-tier lookup and register schema"
```

---

### Task 2: Section-code and act-name parsing (pure functions + self-check)

**Files:**
- Create: `ssor-register/section_matcher.py`
- Create: `ssor-register/test_section_matcher.py`

**Interfaces:**
- Produces: `normalize_section_code(raw: str) -> str`, `bucket_act_name(act_description: str) -> str | None` — both consumed by Task 4's script.

- [ ] **Step 1: Write `section_matcher.py`**

```python
"""Pure text-normalization helpers for matching free-text chargesheet
section/act data against ssor_section_tier_map. No DB access here --
keeps the parsing logic isolated and testable without a database.
"""
from __future__ import annotations

import re

_SECTION_PREFIX_RE = re.compile(r'^(sec(tion)?\.?|s\.)\s*', re.IGNORECASE)
_SECTION_CODE_RE = re.compile(r'^(\d+)\s*(\(\s*(\d+)\s*\))?\s*([a-zA-Z])?$')


def normalize_section_code(raw: str) -> str:
    """'Section 65 (1)' -> '65(1)'; 's.67a' -> '67A'; '376' -> '376'."""
    if not raw:
        return ''
    text = _SECTION_PREFIX_RE.sub('', raw.strip())
    match = _SECTION_CODE_RE.match(text.strip())
    if not match:
        return text.strip()
    number, _, sub, letter = match.groups()
    result = number
    if sub:
        result += f'({sub})'
    if letter:
        result += letter.upper()
    return result


# Ordered so a more specific act name (e.g. POCSO) is checked before a
# generic one; first keyword match wins.
_ACT_KEYWORDS = [
    ('POCSO', ('pocso', 'protection of children from sexual offences')),
    ('IT_ACT', ('information technology act', 'it act', 'i.t. act')),
    ('ITPA', ('immoral traffic', 'itpa')),
    ('BNS', ('bharatiya nyaya sanhita', 'bns')),
]


def bucket_act_name(act_description: str) -> str | None:
    """Map free-text act_description to one of BNS/POCSO/IT_ACT/ITPA.

    Returns None for anything else (including legacy IPC text) -- IPC-era
    convictions are out of scope for this pass; see plan doc.
    """
    if not act_description:
        return None
    text = act_description.strip().lower()
    for act_name, keywords in _ACT_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return act_name
    return None
```

- [ ] **Step 2: Write the self-check**

```python
#!/usr/bin/env python3
"""Stdlib self-check for section_matcher -- run directly, no pytest.

Run: python3 test_section_matcher.py
Expected: prints OK and exits 0.
"""
from section_matcher import bucket_act_name, normalize_section_code


def test_normalize_section_code():
    assert normalize_section_code('65') == '65'
    assert normalize_section_code('Section 65 (1)') == '65(1)'
    assert normalize_section_code('s.67a') == '67A'
    assert normalize_section_code('SEC. 70(2)') == '70(2)'
    assert normalize_section_code('376') == '376'
    assert normalize_section_code('') == ''


def test_bucket_act_name():
    assert bucket_act_name('Bharatiya Nyaya Sanhita, 2023') == 'BNS'
    assert bucket_act_name('Protection of Children from Sexual Offences Act, 2012 (POCSO)') == 'POCSO'
    assert bucket_act_name('Information Technology Act, 2000') == 'IT_ACT'
    assert bucket_act_name('Immoral Traffic (Prevention) Act, 1956') == 'ITPA'
    assert bucket_act_name('Indian Penal Code, 1860') is None
    assert bucket_act_name('') is None


if __name__ == '__main__':
    test_normalize_section_code()
    test_bucket_act_name()
    print('OK')
```

- [ ] **Step 3: Run the self-check**

Run: `cd ssor-register && python3 test_section_matcher.py`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add ssor-register/section_matcher.py ssor-register/test_section_matcher.py
git commit -m "feat(ssor): add section/act text-normalization helpers"
```

---

### Task 3: Module config

**Files:**
- Create: `ssor-register/config.py`

**Interfaces:**
- Consumes: `env_utils.resolve_db_config`, `env_utils.resolve_table_name`, `env_utils.load_repo_environment` (existing repo helpers, see `etl-fpb-accused/config.py`)
- Produces: `DB_CONFIG: dict`, `TABLE_CONFIG: dict`, `LOG_CONFIG: dict` — consumed by Task 4.

- [ ] **Step 1: Write `config.py`**

```python
"""Configuration for ssor-register. No API_CONFIG -- this module reads
only from local Postgres tables already populated by the master pipeline."""

from env_utils import load_repo_environment, resolve_db_config, resolve_table_name

load_repo_environment()

DB_CONFIG = resolve_db_config()

TABLE_CONFIG = {
    'crimes': resolve_table_name('CRIMES_TABLE', 'crimes'),
    'accused': resolve_table_name('ACCUSED_TABLE', 'accused'),
    'persons': resolve_table_name('PERSONS_TABLE', 'persons'),
    'hierarchy': resolve_table_name('HIERARCHY_TABLE', 'hierarchy'),
    'files': resolve_table_name('FILES_TABLE', 'files'),
    'disposal': resolve_table_name('DISPOSAL_TABLE', 'disposal'),
    'interrogation_reports': resolve_table_name('INTERROGATION_REPORTS_TABLE', 'interrogation_reports'),
    'ir_conviction_acquittal': resolve_table_name('IR_CONVICTION_ACQUITTAL_TABLE', 'ir_conviction_acquittal'),
    'chargesheet_acts_sections': resolve_table_name('CHARGESHEET_ACTS_SECTIONS_TABLE', 'chargesheet_acts_sections'),
    'chargesheets': resolve_table_name('CHARGESHEETS_TABLE', 'chargesheets'),
    'chargesheet_accused': resolve_table_name('CHARGESHEET_ACCUSED_TABLE', 'chargesheet_accused'),
    'ssor_section_tier_map': resolve_table_name('SSOR_SECTION_TIER_MAP_TABLE', 'ssor_section_tier_map'),
    'ssor_offense_records': resolve_table_name('SSOR_OFFENSE_RECORDS_TABLE', 'ssor_offense_records'),
    'ssor_offenders': resolve_table_name('SSOR_OFFENDERS_TABLE', 'ssor_offenders'),
}

LOG_CONFIG = {
    'level': 'INFO',
    'format': '%(log_color)s%(asctime)s - %(levelname)s - %(message)s',
    'date_format': '%Y-%m-%d %H:%M:%S',
}
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `cd ssor-register && python3 -c "import config; print(sorted(config.TABLE_CONFIG))"`
Expected: prints the sorted list of table-config keys with no traceback

- [ ] **Step 3: Commit**

```bash
git add ssor-register/config.py
git commit -m "feat(ssor): add module config"
```

---

### Task 4: Build script — classify, gate on conviction, roll up, upsert

**Files:**
- Create: `ssor-register/build_ssor_register.py`

**Interfaces:**
- Consumes: `config.DB_CONFIG`, `config.TABLE_CONFIG` (Task 3); `section_matcher.normalize_section_code`, `section_matcher.bucket_act_name` (Task 2); `db_pooling.PostgreSQLConnectionPool` (existing, `db_pooling.py` at repo root)
- Produces: rows in `ssor_offense_records` and `ssor_offenders` (Task 1 schema) — nothing else consumes this in-repo; it is the pipeline's terminal output for this feature.

- [ ] **Step 1: Write the candidate-row query + classification + rollup**

```python
#!/usr/bin/env python3
"""ssor-register: classify convicted sexual-offence cases into SSOR colour
tiers and build the minimal offender-register profile.

Scope is deliberately narrow (see plan doc): only BNS/POCSO/IT Act/ITPA
sections named in the concept note. Entry requires a conviction verdict --
under-trials are never written to ssor_offenders. Juveniles (is_ccl) are
still classified for internal record-keeping but marked non-disclosable.
"""
from __future__ import annotations

import logging
import os
import sys
from collections import defaultdict
from datetime import date

import colorlog

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
for p in (PROJECT_ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from config import DB_CONFIG, LOG_CONFIG, TABLE_CONFIG  # noqa: E402
from db_pooling import PostgreSQLConnectionPool  # noqa: E402
from section_matcher import bucket_act_name, normalize_section_code  # noqa: E402

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    LOG_CONFIG['format'], LOG_CONFIG['date_format'],
    log_colors={'DEBUG': 'cyan', 'INFO': 'green', 'WARNING': 'yellow', 'ERROR': 'red', 'CRITICAL': 'red,bg_white'},
))
logger = logging.getLogger('ssor_register')
logger.setLevel(LOG_CONFIG['level'])
logger.addHandler(handler)
logger.propagate = False

# Retention per tier, per concept note S7. None == life (subject to periodic review).
RETENTION_YEARS = {'RED': None, 'BLACK': None, 'ORANGE': 25, 'BLUE': 25, 'PINK': 15, 'GREEN': 15}
TIER_RANK = {'BLACK': 90, 'RED': 100, 'ORANGE': 80, 'BLUE': 60, 'PINK': 40, 'GREEN': 20}
# Sections where Green (isolated, first offence) vs Pink (general harassment
# tier) is not decidable from the statute alone -- concept note S5.7 ties it
# to prior-record instead. Restricted to the two sections the note lists for
# Green; 76/78/79 always stay Pink.
GREEN_ELIGIBLE_SECTIONS = {'74', '75'}


class SsorRegisterBuilder:
    def __init__(self):
        self.db_pool = PostgreSQLConnectionPool(minconn=1, maxconn=3, **DB_CONFIG)
        self.stats = {'cases_matched': 0, 'cases_skipped_unmapped': 0, 'offenders_written': 0}

    def load_section_tier_map(self, cursor) -> dict[tuple[str, str], tuple[str, int]]:
        cursor.execute(f"SELECT act_name, section_code, tier, severity_rank FROM {TABLE_CONFIG['ssor_section_tier_map']}")
        return {(act, section): (tier, rank) for act, section, tier, rank in cursor.fetchall()}

    def fetch_candidate_sections(self, cursor) -> list[tuple]:
        """Chargesheet-filed sections joined to the specific accused person
        charged on that chargesheet (via chargesheet_accused -- not a blanket
        crime-level join, which would cross-multiply every accused on a crime
        against every section), and the conviction outcome (IR verdict,
        falling back to disposal).

        Two different chargesheet keys are in play: chargesheet_acts_sections
        keys off the API chargeSheetId (chargesheets.charge_sheet_id, text),
        while chargesheet_accused keys off the internal uuid PK
        (chargesheets.id). Both hops are needed to get from a section row to
        the accused person it was actually filed against.
        """
        cursor.execute(f"""
            SELECT
                ca.accused_person_id,
                cs.crime_id,
                c.fir_num,
                c.ps_code,
                cas.act_description,
                cas.section,
                acc.is_ccl,
                COALESCE(ica.verdict, d.case_status) AS outcome,
                ica.verdict_date AS conviction_date,
                ica.sentence_if_convicted,
                ica.fine_amount_in_inr,
                ica.court_name,
                ica.appeal_status
            FROM {TABLE_CONFIG['chargesheet_acts_sections']} cas
            JOIN {TABLE_CONFIG['chargesheets']} cs ON cs.charge_sheet_id = cas.chargesheet_id
            JOIN {TABLE_CONFIG['chargesheet_accused']} ca ON ca.chargesheet_id = cs.id
            JOIN {TABLE_CONFIG['crimes']} c ON c.crime_id = cs.crime_id
            JOIN {TABLE_CONFIG['accused']} acc
                ON acc.crime_id = cs.crime_id AND acc.person_id = ca.accused_person_id
            LEFT JOIN {TABLE_CONFIG['ir_conviction_acquittal']} ica
                ON ica.crime_num = c.fir_num
            LEFT JOIN {TABLE_CONFIG['disposal']} d ON d.crime_id = cs.crime_id
            WHERE ca.accused_person_id IS NOT NULL
              AND COALESCE(ica.verdict, d.case_status) ILIKE 'convict%%'
        """)
        return cursor.fetchall()

    def classify(self, section_map: dict, rows: list[tuple]) -> dict[str, dict]:
        """Group matched sections per (person_id, crime_id), then per person_id."""
        by_case: dict[tuple[str, str], dict] = {}
        for (person_id, crime_id, fir_num, ps_code, act_description, section_raw, is_ccl,
             outcome, conviction_date, sentence, fine_amount, court_name, appeal_status) in rows:
            act_name = bucket_act_name(act_description)
            section_code = normalize_section_code(section_raw)
            if not act_name or (act_name, section_code) not in section_map:
                self.stats['cases_skipped_unmapped'] += 1
                continue
            tier, rank = section_map[(act_name, section_code)]
            key = (person_id, crime_id)
            case = by_case.setdefault(key, {
                'person_id': person_id, 'crime_id': crime_id, 'fir_num': fir_num, 'ps_code': ps_code,
                'is_juvenile_at_offence': bool(is_ccl), 'conviction_date': conviction_date,
                'sentence_if_convicted': sentence, 'fine_amount_in_inr': fine_amount,
                'court_name': court_name, 'appeal_status': appeal_status,
                'matched_sections': [], 'record_tier': None, 'record_rank': -1,
            })
            case['matched_sections'].append({'act_name': act_name, 'section_code': section_code, 'tier': tier})
            if rank > case['record_rank']:
                case['record_rank'] = rank
                case['record_tier'] = tier
            self.stats['cases_matched'] += 1

        by_person: dict[str, list[dict]] = defaultdict(list)
        for case in by_case.values():
            by_person[case['person_id']].append(case)
        return {'by_case': by_case, 'by_person': by_person}

    def resolve_person_tier(self, cases: list[dict]) -> tuple[str, bool]:
        """Highest tier across all of a person's matched cases; downgrade a
        lone PINK case built only from ss.74/75 to GREEN per S5.7."""
        best_tier, best_rank = 'PINK', -1
        for case in cases:
            if case['record_rank'] > best_rank:
                best_rank, best_tier = case['record_rank'], case['record_tier']
        if best_tier == 'PINK' and len(cases) == 1:
            only_case = cases[0]
            sections = {s['section_code'] for s in only_case['matched_sections']}
            if sections and sections.issubset(GREEN_ELIGIBLE_SECTIONS):
                return 'GREEN', TIER_RANK['GREEN']
        return best_tier, best_rank

    def fetch_person_profile(self, cursor, person_id: str) -> dict:
        cursor.execute(f"""
            SELECT p.full_name, p.alias, p.date_of_birth, p.age, p.gender,
                   p.present_house_no, p.present_street_road_no, p.present_ward_colony,
                   p.present_locality_village, p.present_district, p.present_state_ut,
                   p.present_pin_code, p.present_jurisdiction_ps, p.phone_number
            FROM {TABLE_CONFIG['persons']} p WHERE p.person_id = %s
        """, (person_id,))
        row = cursor.fetchone()
        if not row:
            return {}
        (full_name, alias, dob, age, gender, house_no, street, ward, locality,
         district, state_ut, pin_code, jurisdiction_ps, phone) = row
        address_parts = [house_no, street, ward, locality, district, state_ut, pin_code]
        present_address = ', '.join(part for part in address_parts if part)

        cursor.execute(f"""
            SELECT file_url FROM {TABLE_CONFIG['files']}
            WHERE source_type = 'person' AND source_field = 'IDENTITY_DETAILS' AND parent_id = %s
            ORDER BY file_id LIMIT 1
        """, (person_id,))
        photo_row = cursor.fetchone()

        cursor.execute(f"""
            SELECT is_in_jail, is_on_bail, is_absconding, is_dead, is_rehabilitated
            FROM {TABLE_CONFIG['interrogation_reports']}
            WHERE person_id = %s ORDER BY date_modified DESC NULLS LAST LIMIT 1
        """, (person_id,))
        status_row = cursor.fetchone()

        return {
            'full_name': full_name, 'alias': alias, 'date_of_birth': dob, 'age': age, 'gender': gender,
            'present_address': present_address, 'present_district': district,
            'jurisdiction_ps_code': jurisdiction_ps, 'phone_number': phone,
            'photo_file_url': photo_row[0] if photo_row else None,
            'is_in_jail': status_row[0] if status_row else None,
            'is_on_bail': status_row[1] if status_row else None,
            'is_absconding': status_row[2] if status_row else None,
            'is_dead': status_row[3] if status_row else None,
            'is_rehabilitated': status_row[4] if status_row else None,
        }

    def upsert_offense_record(self, cursor, case: dict) -> None:
        import json
        cursor.execute(f"""
            INSERT INTO {TABLE_CONFIG['ssor_offense_records']}
                (person_id, crime_id, fir_num, ps_code, matched_sections, record_tier,
                 is_juvenile_at_offence, conviction_date, sentence_if_convicted,
                 fine_amount_in_inr, court_name, appeal_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (person_id, crime_id) DO UPDATE SET
                matched_sections = EXCLUDED.matched_sections,
                record_tier = EXCLUDED.record_tier,
                conviction_date = EXCLUDED.conviction_date,
                sentence_if_convicted = EXCLUDED.sentence_if_convicted,
                fine_amount_in_inr = EXCLUDED.fine_amount_in_inr,
                court_name = EXCLUDED.court_name,
                appeal_status = EXCLUDED.appeal_status
        """, (
            case['person_id'], case['crime_id'], case['fir_num'], case['ps_code'],
            json.dumps(case['matched_sections']), case['record_tier'], case['is_juvenile_at_offence'],
            case['conviction_date'], case['sentence_if_convicted'], case['fine_amount_in_inr'],
            case['court_name'], case['appeal_status'],
        ))

    def upsert_offender(self, cursor, person_id: str, cases: list[dict]) -> None:
        highest_tier, _ = self.resolve_person_tier(cases)
        disclosable = not any(case['is_juvenile_at_offence'] for case in cases)
        retention_years = RETENTION_YEARS[highest_tier]
        earliest_conviction = min((c['conviction_date'] for c in cases if c['conviction_date']), default=None)
        review_date = None
        if retention_years is not None and earliest_conviction:
            review_date = date(earliest_conviction.year + retention_years, earliest_conviction.month, earliest_conviction.day)

        profile = self.fetch_person_profile(cursor, person_id)
        if not profile:
            logger.warning(f"No persons row for person_id={person_id}; skipping offender profile")
            return

        cursor.execute(f"""
            INSERT INTO {TABLE_CONFIG['ssor_offenders']}
                (person_id, full_name, alias, date_of_birth, age, gender, photo_file_url,
                 present_address, present_district, jurisdiction_ps_code, phone_number,
                 highest_tier, disclosable, retention_years, review_date,
                 is_in_jail, is_on_bail, is_absconding, is_dead, is_rehabilitated, date_modified)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (person_id) DO UPDATE SET
                full_name = EXCLUDED.full_name, alias = EXCLUDED.alias,
                date_of_birth = EXCLUDED.date_of_birth, age = EXCLUDED.age, gender = EXCLUDED.gender,
                photo_file_url = EXCLUDED.photo_file_url, present_address = EXCLUDED.present_address,
                present_district = EXCLUDED.present_district, jurisdiction_ps_code = EXCLUDED.jurisdiction_ps_code,
                phone_number = EXCLUDED.phone_number, highest_tier = EXCLUDED.highest_tier,
                disclosable = EXCLUDED.disclosable, retention_years = EXCLUDED.retention_years,
                review_date = EXCLUDED.review_date, is_in_jail = EXCLUDED.is_in_jail,
                is_on_bail = EXCLUDED.is_on_bail, is_absconding = EXCLUDED.is_absconding,
                is_dead = EXCLUDED.is_dead, is_rehabilitated = EXCLUDED.is_rehabilitated,
                date_modified = now()
        """, (
            person_id, profile['full_name'], profile['alias'], profile['date_of_birth'], profile['age'],
            profile['gender'], profile['photo_file_url'], profile['present_address'], profile['present_district'],
            profile['jurisdiction_ps_code'], profile['phone_number'], highest_tier, disclosable,
            retention_years, review_date, profile['is_in_jail'], profile['is_on_bail'],
            profile['is_absconding'], profile['is_dead'], profile['is_rehabilitated'],
        ))
        self.stats['offenders_written'] += 1

    def run(self) -> None:
        with self.db_pool.get_connection_context() as conn:
            with conn.cursor() as cursor:
                section_map = self.load_section_tier_map(cursor)
                rows = self.fetch_candidate_sections(cursor)

        logger.info(f"Fetched {len(rows)} candidate chargesheet-section rows from convicted cases")
        grouped = self.classify(section_map, rows)

        with self.db_pool.get_connection_context() as conn:
            with conn.cursor() as cursor:
                try:
                    for case in grouped['by_case'].values():
                        self.upsert_offense_record(cursor, case)
                    for person_id, cases in grouped['by_person'].items():
                        self.upsert_offender(cursor, person_id, cases)
                    conn.commit()
                except Exception as e:
                    logger.error(f"Failed building SSOR register: {e}")
                    conn.rollback()
                    raise

        logger.info(f"Done. Stats: {self.stats}")


if __name__ == '__main__':
    SsorRegisterBuilder().run()
```

- [ ] **Step 2: Dry-run against the loaded database**

Run: `cd ssor-register && python3 build_ssor_register.py`
Expected: log line `Done. Stats: {'cases_matched': N, 'cases_skipped_unmapped': M, 'offenders_written': K}` with no traceback (N/M/K depend on what's actually in the DB — first run tells you real numbers)

- [ ] **Step 3: Spot-check the output**

Run: `psql "$DATABASE_URL" -c "SELECT highest_tier, disclosable, count(*) FROM public.ssor_offenders GROUP BY 1, 2 ORDER BY 1;"`
Expected: rows grouped by tier, with `disclosable = false` only appearing where a juvenile case was involved

- [ ] **Step 4: Commit**

```bash
git add ssor-register/build_ssor_register.py
git commit -m "feat(ssor): build offense-record and offender-register tables from convicted cases"
```

---

### Task 5: Wire into master pipeline as the final step

**Files:**
- Modify: `etl_master/input.txt`

**Interfaces:**
- Consumes: nothing new — this is a config-only change appending a step that runs after everything the query in Task 4 depends on (`chargesheets`/`accused`/`persons`/`IR` all already run earlier in the file).

- [ ] **Step 1: Append Order 18 to `etl_master/input.txt`**

Add this block after the existing `[Order 17]` block, and update the ordering-rationale comment block at the top of the file with one line:

```
#  18  ssor_register : reads convicted chargesheet sections + IR verdicts
#                      already loaded by every step above; purely a
#                      classification/rollup, no new source data.
```

```
[Order 18]
ssor_register
cd /data-drive/etl-process-dev/ssor-register
source /data-drive/etl-process-dev/venv/bin/activate
python3 build_ssor_register.py
```

- [ ] **Step 2: Verify the master orchestrator picks it up**

Run: `cd etl_master && python3 -c "from preflight_check import parse_input_file; procs = parse_input_file('input.txt'); print(len(procs), procs[-1]['name'])"`
Expected: `18 ssor_register`

- [ ] **Step 3: Commit**

```bash
git add etl_master/input.txt
git commit -m "feat(ssor): wire ssor_register as final master pipeline step"
```

---

## Known limitations (flagged, not solved here)

- **IPC-era convictions** (FIRs before 2024-07-01, or any chargesheet still citing IPC 375/376/354 etc.) are not mapped — `bucket_act_name` returns `None` for them and they're counted in `cases_skipped_unmapped`, not silently dropped. Add an IPC→BNS crosswalk to `ssor_section_tier_map` if historical backfill is needed later.
- **No biometric store.** `photo_file_url` is the only identity artifact available from CCTNS data; fingerprint/DNA per the concept note §6.2 needs a separate integration (AFIS/state FSL), out of scope here.
- **No NCRB interoperability.** The concept note requires the State register to work alongside the national database (§1); nothing here talks to NCRB — flagged for a later, separate integration.
