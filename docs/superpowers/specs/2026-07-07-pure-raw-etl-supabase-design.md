# Pure raw CCTNS ETL + Supabase migration — design

## Goal
Strip all AI/derived-analytics code from the repo. Keep/build only ETLs that fetch raw data from the CCTNS API (per `http://10.20.2.211:3001/doc`, OpenAPI at `/doc/openapi`) and store it as-is in Postgres. Move DB and file storage to Supabase.

## Source of truth
Live OpenAPI spec at `10.20.2.211:3001/doc/openapi`. 30 paths across these endpoint groups:
`ping`, `crimes` (+ `disposal`), `master-data/hierarchy`, `accused`, `arrests`, `mo-seizures`, `person-details`, `property-details`, `interrogation-reports/v1`, `chargesheets`, `update-chargesheets`, `case-property`, `files`, `reports/missing-udb-persons/v1`, `reports/arrest/arrest-particulars/v1`, `reports/stolen-automobiles`, `fpb/accused` (+ `pcn`).

## Keep as-is (internals untouched, DB config → Supabase only)
13 folders already do pure fetch-from-API → upsert-into-Postgres, one per endpoint group:

`etl-hierarchy`, `etl-crimes`, `etl-accused`, `etl-persons`, `etl-properties`, `etl-ir`, `etl-disposal`, `etl_arrests`, `etl_mo_seizures`, `etl_chargesheets`, `etl_updated_chargesheet`, `etl_fsl_case_property`, `etl-files`.

Change per folder: `config.py` `DB_CONFIG` → Supabase connection string/env vars. Strip any dead `ENABLE_EMBEDDINGS`/`EMBEDDING_MODEL` keys. No other logic changes.

## Remove entirely
AI-based:
- `brief_facts_ai/` (LLM extraction of accused/drug facts)
- `core/llm_service.py`, `core/geo_resolver.py`, `etl-address/`, `etl-address-solution-plan.md` (LLM address resolution)
- `chatbot/` (NL2SQL agent stack)

Rule-based derived (not raw API data):
- `drug_standardization/`, `domicile_classification/`, `section-wise-case-clarification/`, `fix_fullname/`
- `etl_case_status/` (derived SQL on stored crimes)
- `etl_refresh_views/` and the `*_mv.sql` materialized views (`firs_mv.sql`, `accuseds_mv.sql`, `criminal_profiles_mv.sql`, `advanced_search_accuseds_mv.sql`, `advanced_search_firs_mv.sql`)

Legacy/unrelated:
- `etl-mongo-to-postgresql/` (one-off Mongo→Postgres migration, not CCTNS API, not in master schedule)

## Build new — 4 endpoint groups with zero existing code

### `etl-missing-udb-persons` → `GET /reports/missing-udb-persons/v1/`
No path params; likely date-range query like other list endpoints. Fields: `ACTS_SECTIONS, BRIEF_FACTS, COMPLAINANT_NAME, CRIME_ID, DISTRICT, FIR_NUM, GENDER, IO_NAME, IO_PAO_CODE, IO_RANK, PERSON, PERSON_AGE, PERSON_DATE, PERSON_MEDIA[], PERSON_NAME, PHYSICAL_FEATURES{}, PRESENT_ADDRESS{}, PS_NAME`.

### `etl-arrest-particulars` → `GET /reports/arrest/arrest-particulars/v1/`
Response nests one extra level (`data.data[]`, not `data[]` — confirmed different shape from the rest). Fields: `ACCUSED_AGE, ACCUSED_MEDIA[], ACCUSED_NAME, ACTS_SECTIONS, ARREST_TYPE, BRIEF_FACTS, CRIME_ID, DATE_OF_ARREST, DISTRICT, FIR_DATE, FIR_NUM, GENDER, IO_NAME, IO_PAO_CODE, IO_RANK, PERSON, PLACE_OF_ARREST, PRESENT_ADDRESS{}, PS_NAME`.

### `etl-stolen-automobiles` → `GET /reports/stolen-automobiles` (list) + `GET /reports/stolen-automobiles/{crimeId}` (single, same schema)
Fields: `AUTO_SEQ_NO, AUTO_TYPE, BELONGS_TO_WHOM, CHASSIS_NO, CLASSIFICATION, COLOR, COLOR_TYPE, CRIME_ID, DATE_CREATED, DATE_MODIFIED, DATE_OF_SEIZURE, DISTRICT, DRIVER_SIDE, ENGINE_CAPACITY, ENGINE_NO, ESTIMATE_VALUE, FUEL, FULL_CHASSIS_NO, FULL_ENGINE_NO, INSURANCE_CERTIFICATE_NO, INSURANCE_COMPANY_NAME, LICENSE_CLASS, LIFTING_CAPACITY, LOCATION_TYPE, MADE, MAKE, MANUFACTURED, MANUFACTURER, MEDIA[], MFG_MONTH, MFG_YEAR, MODEL, MV_UTILITY, NATURE_OF_STOLEN, OVER_ALL_LENGTH, OWNER_FATHER_NAME, OWNER_NAME, PARTICULAR_OF_PROPERTY, PERMANENT_ADDRESS, PLACE_OF_RECOVERY, PRESENT_ADDRESS, PROPERTY_CATEGORY, PROPERTY_CATEGORY_NAME, PROPERTY_RECOVERED_FROM, PROPERTY_STATUS, RECOVERED_VALUE, REGISTERED_AT, REGISTERED_MOBILE_NO, REGISTERED_OWNER, REGISTRATION_DATE, REGISTRATION_NO, REGISTRATION_NUMBER, REGISTRATION_PLACE, REGISTRATION_VALID_UPTO, REMARKS, RTA_NAME, RTA_VERIFICATION_DATE, SEAT_CAPACITY, SEQ_NO, SLOGAN_PICTURE, SPECIAL_IDENTIFICATION, STOLEN_PROPERTY_ID, SUB_CLASSIFICATION, TMP_REGISTRATION_NO, TOTAL_ESTIMATED_VALUE, ULW, VARIANT, WHEEL_BASE`. Has `DATE_CREATED`/`DATE_MODIFIED` → supports the same incremental-by-date pattern as the other ETLs.

### `etl-fpb-accused` → `GET /fpb/accused` + `POST /fpb/accused/pcn`
**Different fetch pattern**: both require query params `firNum` + `psCode` (not a date range). No bulk/list mode in the spec — must be driven by iterating FIR_NUM/PS_CODE pairs already present in the `crimes` table (this ETL runs after `etl-crimes`). `pcn` variant is a POST with identical response shape/params — purpose distinction (fingerprint-bureau slip type) unclear from schema alone, store both under one table with a `source_endpoint` discriminator column, or two tables (`fpb_accused`, `fpb_accused_pcn`) if the plan step finds they diverge — decide during planning by hitting both live with a sample FIR/PS pair.
Fields: `AADHAAR_OR_OTHER_ID{}, ADDITIONAL_CRIMES[], AGE, ALIAS, ARREST_DETAILS{}, CASTE, CC_KD_DC_NO, CONFESSION_STATEMENT, CRIME_ID, DATE_FINGERPRINTED, DATE_OF_ARREST, DOB, FATHER_HUSBAND_NAME, FIR_REG_NUM, FP_UNIT, FULL_NAME, MO, NATIONALITY, OCCUPATION, PERMANENT_ADDRESS{}, PERSON_ID, PHONE_NUMBER, PHYSICAL_FEATURES{}, PLACE_OF_BIRTH, PRESENT_ADDRESS{}, PROPERTY_RECOVERED, PS_WHERE_FPS_OBTAINED, RELIGION, REMARKS, SEX, SLIP_TYPE, SURNAME`.

All 4 follow the existing per-folder pattern (own `config.py`, own fetch/upsert script, `db_pooling.py` import) — no shared-package refactor, keeps blast radius isolated to new folders only.

## Supabase migration
- Supabase Postgres = plain Postgres. Keep `db_pooling.py` / psycopg2 unchanged — swap `DB_CONFIG` env vars (host/port/user/password/db) to Supabase's connection string.
- Use Supabase **direct connection or Session-mode pooler**, not the Transaction-mode pooler (port 6543) — ETLs hold long-lived `ThreadedConnectionPool` connections across a run, which transaction-mode pgbouncer doesn't suit.
- `etl-files`: file bytes move from local disk to a Supabase Storage bucket; DB row keeps only the storage path/public URL.
- No Supabase project exists yet. I can write the DDL/config now; actual provisioning needs either the dashboard (you) or the Supabase MCP (currently unauthenticated in this session — you'd need to run `/mcp` to authorize it before I can provision/query via it).

## Master orchestrator
`etl_master/input.txt`: drop blocks for every removed folder, append blocks for the 4 new ones. `master_etl.py` itself needs no code change (it just parses the text file).

## Repo cleanup
Everything not in the keep/new list (loose `*.md` reports, `scratch_*.py`, CSV dumps, one-off `.sql`/`.sh` fix scripts) moves to `archive/` — not deleted, just out of the active tree.

## Out of scope
- No shared-package refactor of the existing 13 ETLs (duplication noted in `project-overview.md` stays; not what was asked).
- Exact Supabase project provisioning (needs your action or MCP auth).
- `fpb/accused` vs `pcn` semantic distinction — resolve empirically during planning, not assumed here.
