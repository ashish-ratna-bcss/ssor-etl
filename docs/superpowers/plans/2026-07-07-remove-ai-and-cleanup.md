# Remove AI/Derived Code + Repo Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strip every AI/derived-analytics module from CCTNS-ETL, sever the one hidden runtime coupling a kept ETL has to a removed module, rewrite the master orchestrator schedule, and trim `requirements.txt` to only what the surviving raw-fetch ETLs use.

**Architecture:** No code rewrite of surviving ETLs beyond one targeted edit (`etl-accused/etl_accused.py`). Everything else is file moves (`mv` into `archive/`) plus two text-file edits (`etl_master/input.txt`, `requirements.txt`). This is Phase 1 of 3 — see the design doc for Phase 2 (Supabase config swap) and Phase 3 (4 new raw ETLs).

**Tech Stack:** Bash (`mv`, `grep`), Python 3 (`py_compile` for syntax verification).

## Global Constraints
- Git repo initialized at `/home/ashish-ratna/CCTNS-ETL` with baseline commit `4d23564`. Every task ends with a real `git commit`.
- Do not touch `node_modules/` — third-party, unrelated to this migration.
- Do not delete anything — every removal is a `mv` into `archive/`, reversible.
- Reference design doc: `docs/superpowers/specs/2026-07-07-pure-raw-etl-supabase-design.md`.

---

### Task 1: Archive every AI/derived/legacy module and all root-level clutter

**Files:**
- Create: `archive/` (new top-level directory, receives everything below)
- Move (AI): `brief_facts_ai/`, `core/` (contains only `llm_service.py` + `geo_resolver.py`), `chatbot/`
- Move (derived logic, not raw API data): `drug_standardization/`, `domicile_classification/`, `section-wise-case-clarification/`, `fix_fullname/`, `etl_case_status/`, `etl_refresh_views/`, `etl-address/`, `etl-address-solution-plan.md`
- Move (materialized views, byproducts of removed derived tables): `firs_mv.sql`, `accuseds_mv.sql`, `criminal_profiles_mv.sql`, `advanced_search_accuseds_mv.sql`, `advanced_search_firs_mv.sql`, `unified_brief_facts_etl.sql`
- Move (legacy, unrelated to CCTNS API): `etl-mongo-to-postgresql/`
- Move (everything else at repo root not in the keep-list below — reports, scratch scripts, CSV/log dumps, one-off SQL/shell fixes, `diagnostics/`, `tests/`, root-level `migrations/`)
- Test: none (this is a file-move task) — verified via Step 3 below

**Keep-list (must survive at repo root, untouched by this task):**
`etl-hierarchy/`, `etl-crimes/`, `etl-accused/`, `etl-persons/`, `etl-properties/`, `etl-ir/`, `etl-disposal/`, `etl_arrests/`, `etl_mo_seizures/`, `etl_chargesheets/`, `etl_updated_chargesheet/`, `etl_fsl_case_property/`, `etl-files/`, `etl_master/`, `CCTNSV2_data/`, `docs/`, `node_modules/`, `archive/` (itself), `db_pooling.py`, `env_utils.py`, `etl_run_config.py`, `requirements.txt`, `DB-schema.sql`, `README.md`, `skills-lock.json`

- [ ] **Step 1: Create the archive directory and move every non-keep-list item into it**

```bash
cd /home/ashish-ratna/CCTNS-ETL

mkdir -p archive

KEEP=(
  "etl-hierarchy" "etl-crimes" "etl-accused" "etl-persons" "etl-properties"
  "etl-ir" "etl-disposal" "etl_arrests" "etl_mo_seizures" "etl_chargesheets"
  "etl_updated_chargesheet" "etl_fsl_case_property" "etl-files" "etl_master"
  "CCTNSV2_data" "docs" "node_modules" "archive"
  "db_pooling.py" "env_utils.py" "etl_run_config.py" "requirements.txt"
  "DB-schema.sql" "README.md" "skills-lock.json"
)

is_kept() {
  local item="$1"
  for k in "${KEEP[@]}"; do
    [[ "$item" == "$k" ]] && return 0
  done
  return 1
}

for item in * .[!.]*; do
  [[ "$item" == "*" || "$item" == ".[!.]*" ]] && continue   # no-match glob guard
  if is_kept "$item"; then
    continue
  fi
  echo "archiving: $item"
  mv -- "$item" archive/
done
```

- [ ] **Step 2: Confirm the keep-list directories/files are still present at root**

Run: `ls /home/ashish-ratna/CCTNS-ETL`
Expected output: exactly the 24 keep-list entries (order may vary), nothing else.

- [ ] **Step 3: Confirm nothing removed is still reachable from root**

Run:
```bash
cd /home/ashish-ratna/CCTNS-ETL
for name in brief_facts_ai core chatbot drug_standardization domicile_classification \
            section-wise-case-clarification fix_fullname etl_case_status \
            etl_refresh_views etl-address etl-mongo-to-postgresql; do
  [[ -e "$name" ]] && echo "STILL AT ROOT: $name"
done
echo "done"
```
Expected: only `done` printed — no `STILL AT ROOT` lines.

---

### Task 2: Sever `etl-accused`'s runtime coupling to the now-archived `brief_facts_ai`

`etl-accused/etl_accused.py` is a **keep-as-is** ETL, but it currently imports from and writes into `brief_facts_ai` at three spots. Once Task 1 moves `brief_facts_ai/` into `archive/`, the import at line ~1918 would raise `ModuleNotFoundError` (caught by a broad `except Exception`, so it wouldn't crash the ETL — but it's dead AI-coupled logic that must go per the "pure API fetch and store" goal).

**Files:**
- Modify: `etl-accused/etl_accused.py:81` (table-name constant)
- Modify: `etl-accused/etl_accused.py:221-245` (`route_accused_status` method)
- Modify: `etl-accused/etl_accused.py:1913-1926` (Branch-C invalidation block)
- Test: manual verification via `grep` + `py_compile` (no existing unit test suite for this file)

- [ ] **Step 1: Confirm current coupling before editing**

Run: `grep -n "brief_facts_ai\|BRIEF_FACTS_ACCUSED_TABLE" /home/ashish-ratna/CCTNS-ETL/etl-accused/etl_accused.py`
Expected: 8 matching lines (this is the pre-edit baseline — compare against Step 4).

- [ ] **Step 2: Remove the table constant and the brief_facts_ai status-update block**

In `etl-accused/etl_accused.py`, delete line 81:
```python
BRIEF_FACTS_ACCUSED_TABLE = TABLE_CONFIG.get('brief_facts_ai', 'brief_facts_ai')  # Updated to unified table
```

In `route_accused_status` (around line 221), replace:
```python
    def route_accused_status(self, accused: Dict, cursor):
        """
        Route ACCUSED_STATUS field to arrests and brief_facts_ai tables.
        """
        accused_status = accused.get('accused_status')
        if not accused_status:
            return

        accused_id = accused.get('accused_id')
        crime_id = accused.get('crime_id')
        seq_num = accused.get('seq_num')
        person_id = accused.get('person_id')

        # 1. Update brief_facts_ai status
        if accused_id:
            try:
                cursor.execute(f"""
                    UPDATE {BRIEF_FACTS_ACCUSED_TABLE}
                    SET status = %s
                    WHERE accused_id = %s
                """, (accused_status, accused_id))
                logger.trace(f"Updated status in brief_facts_ai for accused_id {accused_id}")
            except Exception as e:
                logger.error(f"Error updating {BRIEF_FACTS_ACCUSED_TABLE} status: {e}")

        # 2. Update arrests table with parsed 41A info
```
with:
```python
    def route_accused_status(self, accused: Dict, cursor):
        """
        Route ACCUSED_STATUS field to the arrests table.
        """
        accused_status = accused.get('accused_status')
        if not accused_status:
            return

        accused_id = accused.get('accused_id')
        crime_id = accused.get('crime_id')
        seq_num = accused.get('seq_num')
        person_id = accused.get('person_id')

        # Update arrests table with parsed 41A info
```

- [ ] **Step 3: Remove the Branch-C invalidation block**

Around line 1913, replace:
```python
        # Invalidate Branch C processing-log entries for crimes that now have real
        # accused records.  Brief_facts_ai will re-run those crimes on its next batch,
        # promoting the LLM-only rows to proper Branch A/B rows with relational identity.
        if inserted_crime_ids:
            try:
                from brief_facts_ai.db import invalidate_branch_c_log_for_crimes
                with self.db_pool.get_connection_context() as _inv_conn:
                    invalidate_branch_c_log_for_crimes(_inv_conn, list(inserted_crime_ids))
                    _inv_conn.commit()
            except Exception as _inv_err:
                logger.warning(
                    f"Branch C invalidation skipped for chunk {chunk_range}: {_inv_err} "
                    "(non-fatal — brief_facts_ai will re-detect via date_modified)"
                )

```
with nothing (delete the block entirely). `inserted_crime_ids` is assigned at line 1782 and populated at line 1867 — both stay untouched; this was its only consumer, so no other code references it after this deletion.

- [ ] **Step 4: Verify the coupling is gone and the file still compiles**

Run:
```bash
grep -n "brief_facts_ai\|BRIEF_FACTS_ACCUSED_TABLE" /home/ashish-ratna/CCTNS-ETL/etl-accused/etl_accused.py
python3 -m py_compile /home/ashish-ratna/CCTNS-ETL/etl-accused/etl_accused.py && echo "COMPILES OK"
```
Expected: no grep output, then `COMPILES OK`.

---

### Task 3: Rewrite `etl_master/input.txt` to drop archived-module blocks

**Files:**
- Modify: `etl_master/input.txt` (full rewrite)
- Test: manual inspection + a parse dry-run against `master_etl.py`'s own block parser

- [ ] **Step 1: Replace the file contents**

Write `etl_master/input.txt` as:
```
# Master ETL Process Configuration File
# This file defines the sequence of ETL processes to run daily.
# The Master ETL script will read this file top-to-bottom and execute each process sequentially.
#
# Format:
# <Working Directory> ; <Command to Execute>
#
# Instructions:
# 1. Add each ETL process on a new line.
# 2. Specify the full path to the directory where the process should run.
# 3. Separate the directory and the command with a semicolon (;).
# 4. Lines starting with # are ignored.
#

# --- User Process Definitions ---

[Order 1]
hierarchy
cd /data-drive/etl-process-dev/etl-hierarchy
source /data-drive/etl-process-dev/venv/bin/activate
python3 etl_hierarchy.py

[Order 2]
crimes
cd /data-drive/etl-process-dev/etl-crimes
source /data-drive/etl-process-dev/venv/bin/activate
python3 etl_crimes.py

[Order 3]
accused
cd /data-drive/etl-process-dev/etl-accused
source /data-drive/etl-process-dev/venv/bin/activate
python3 etl_accused.py

[Order 4]
persons
cd /data-drive/etl-process-dev/etl-persons
source /data-drive/etl-process-dev/venv/bin/activate
python3 etl_persons.py

[Order 5]
properties
cd /data-drive/etl-process-dev/etl-properties
source /data-drive/etl-process-dev/venv/bin/activate
python3 etl_properties.py

[Order 6]
IR
cd /data-drive/etl-process-dev/etl-ir
source /data-drive/etl-process-dev/venv/bin/activate
python3 ir_etl.py

[Order 7]
Disposal
cd /data-drive/etl-process-dev/etl-disposal
source /data-drive/etl-process-dev/venv/bin/activate
python3 etl_disposal.py

[Order 8]
arrests
cd /data-drive/etl-process-dev/etl_arrests
source /data-drive/etl-process-dev/venv/bin/activate
python3 etl_arrests.py

[Order 9]
mo_seizures
cd /data-drive/etl-process-dev/etl_mo_seizures
source /data-drive/etl-process-dev/venv/bin/activate
python3 etl_mo_seizure.py

[Order 10]
chargesheets
cd /data-drive/etl-process-dev/etl_chargesheets
source /data-drive/etl-process-dev/venv/bin/activate
python3 etl_chargesheets.py

[Order 11]
updated_chargesheet
cd /data-drive/etl-process-dev/etl_updated_chargesheet
source /data-drive/etl-process-dev/venv/bin/activate
python3 etl_update_chargesheet.py

[Order 12]
fsl_case_property
cd /data-drive/etl-process-dev/etl_fsl_case_property
source /data-drive/etl-process-dev/venv/bin/activate
python3 etl_fsl_case_property.py

[Order 13]
update_file_id
cd /data-drive/etl-process-dev/etl-files/etl_pipeline_files
source /data-drive/etl-process-dev/venv/bin/activate
python3 main_standalone.py

[Order 14]
files_download_media_server
cd /data-drive/etl-process-dev/etl-files/etl_files_media_server
source /data-drive/etl-process-dev/venv/bin/activate
python3 -m etl_files_media_server.main

[Order 15]
update_file_extentions
cd /data-drive/etl-process-dev/etl-files/update_file_urls_with_extensions
source /data-drive/etl-process-dev/venv/bin/activate
python3 update_file_urls_with_extensions.py
```

Note: Orders 16-19 (the 4 new raw-fetch ETLs — missing-udb-persons, arrest-particulars, stolen-automobiles, fpb-accused) are intentionally **not** added here — they don't exist yet. Phase 3's plan appends them to this same file once built.

- [ ] **Step 2: Dry-run the block parser against the new file**

`master_etl.py:474` calls `parse_input_file(config_path)` to turn the text file into process blocks. Run it directly:

```bash
cd /home/ashish-ratna/CCTNS-ETL/etl_master
python3 -c "
from master_etl import parse_input_file
processes = parse_input_file('input.txt')
print('block count:', len(processes))
for p in processes:
    print(p.get('order'), p.get('name'))
"
```
Expected: `block count: 15`, followed by 15 lines `1 hierarchy` through `15 update_file_extentions` (names matching Task 3 Step 1's `[Order N]` blocks in order).

- [ ] **Step 3: Confirm no references to archived block names remain**

Run: `grep -niE "brief_facts|refresh_views|domicile|fix_person_names|full_name_fix|name_fix|surname_fix|class_classification|case_status" /home/ashish-ratna/CCTNS-ETL/etl_master/input.txt`
Expected: no output.

---

### Task 4: Trim `requirements.txt` to only what surviving ETLs use

Verified by grep across every keep-list ETL: `spacy`, `fuzzywuzzy`, `python-Levenshtein`, `metaphone`, `pymongo`, `openpyxl`, `pydantic`, the LLM stack (`langchain*`, `sentence-transformers`, `torch`, `openai`, `langgraph`), the web stack (`Flask`, `flask-cors`, `flask-limiter`, `SQLAlchemy`, `Werkzeug`, `gunicorn`), and `redis` are used **only** by archived modules. `dedupe` (etl-persons), `psutil`/`filelock` (etl-files), `pandas`/`numpy` (listed in several kept ETLs' own requirements.txt) are genuinely used and stay.

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Replace the file contents**

```
# Consolidated requirements for the raw CCTNS fetch-and-store ETLs
# Core Database
psycopg2-binary>=2.9.10,<3.0

# Environment & Configuration
python-dotenv>=1.0.0
python-dateutil>=2.8.2

# System & Process Management (for parallel ETL execution)
psutil>=6.0.0
filelock>=3.13.0

# Data Processing
pandas>=2.1.0
numpy>=1.26.0

# HTTP & API
requests>=2.31.0

# Person de-duplication (etl-persons)
dedupe>=2.0.0
metaphone>=0.6

# Utilities
tqdm>=4.66.1
colorlog>=6.8.0
```

- [ ] **Step 2: Verify every kept ETL's imports are covered**

Run:
```bash
cd /home/ashish-ratna/CCTNS-ETL
for d in etl-hierarchy etl-crimes etl-accused etl-persons etl-properties etl-ir etl-disposal etl_arrests etl_mo_seizures etl_chargesheets etl_updated_chargesheet etl_fsl_case_property etl-files; do
  echo "=== $d ==="
  grep -hE "^import |^from " "$d"/*.py 2>/dev/null | sed -E 's/^(import|from) ([A-Za-z0-9_]+).*/\2/' | sort -u
done | sort -u
```
Read the combined module list; every third-party name (ignore stdlib: `os`, `sys`, `re`, `json`, `time`, `datetime`, `logging`, `threading`, `collections`, `concurrent`, `typing`, `decimal`, `uuid`, `hashlib`, `functools`, `itertools`) must map to a package in the new `requirements.txt`. If something's missing, add it before moving on.

---

### Task 5: Full-repo sanity pass

**Files:** none created/modified — verification only

- [ ] **Step 1: Every kept ETL script still compiles**

```bash
cd /home/ashish-ratna/CCTNS-ETL
for f in etl-hierarchy/etl_hierarchy.py etl-crimes/etl_crimes.py etl-accused/etl_accused.py \
         etl-persons/etl_persons.py etl-properties/etl_properties.py etl-ir/ir_etl.py \
         etl-disposal/etl_disposal.py etl_arrests/etl_arrests.py etl_mo_seizures/etl_mo_seizure.py \
         etl_chargesheets/etl_chargesheets.py etl_updated_chargesheet/etl_update_chargesheet.py \
         etl_fsl_case_property/etl_fsl_case_property.py etl_master/master_etl.py etl_run_config.py \
         db_pooling.py env_utils.py; do
  python3 -m py_compile "$f" && echo "OK: $f" || echo "FAIL: $f"
done
```
Expected: every line prints `OK: ...`, none print `FAIL: ...`.

- [ ] **Step 2: No remaining reference anywhere in the surviving tree to an archived module**

```bash
cd /home/ashish-ratna/CCTNS-ETL
grep -rnE "brief_facts_ai|llm_service|geo_resolver|drug_standardization|domicile_classification|section-wise-case-clarification|fix_fullname|etl_case_status|etl_refresh_views|etl-address|chatbot" \
  --include=*.py --include=*.txt --include=*.sql \
  etl-hierarchy etl-crimes etl-accused etl-persons etl-properties etl-ir etl-disposal \
  etl_arrests etl_mo_seizures etl_chargesheets etl_updated_chargesheet etl_fsl_case_property \
  etl-files etl_master db_pooling.py env_utils.py etl_run_config.py requirements.txt 2>/dev/null
```
Expected: no output.

- [ ] **Step 3: Record completion**

No git repo to commit to. Note in your working notes / the plan checkboxes above that Phase 1 is complete, and confirm with the user before starting Phase 2 (Supabase config swap) or Phase 3 (4 new ETLs) — both are separate plans per the design doc's phasing.
