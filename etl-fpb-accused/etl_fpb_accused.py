#!/usr/bin/env python3
"""etl-fpb-accused -- raw fetch-and-store for GET /fpb/accused.

Unlike every other ETL in this repo, this endpoint has no date-range query --
it's keyed by (firNum, psCode), required query params. So instead of chunked
date windows, this ETL walks distinct (fir_num, ps_code) pairs already present
in the crimes table and fetches each one that hasn't been pulled yet.

Deliberately does NOT call POST /fpb/accused/pcn. Its response schema is
byte-identical to GET /fpb/accused, but a POST implies a write/trigger action
on the source system (e.g. issuing a PCN slip) rather than a pure data read --
running that in an unattended sync loop risks side effects on production
CCTNS data that a read-only ETL must not have. If PCN generation needs to be
automated, that's a deliberate, explicitly-triggered action, not a fetch job.
"""
from __future__ import annotations

import logging
import os
import sys
import time

import colorlog
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
for p in (PROJECT_ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from config import API_CONFIG, DB_CONFIG, LOG_CONFIG, TABLE_CONFIG  # noqa: E402
from db_pooling import PostgreSQLConnectionPool  # noqa: E402

CRIMES_TABLE = TABLE_CONFIG['crimes']
FPB_ACCUSED_TABLE = TABLE_CONFIG['fpb_accused']
FPB_ADDITIONAL_CRIMES_TABLE = TABLE_CONFIG['fpb_additional_crimes']

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    LOG_CONFIG['format'], LOG_CONFIG['date_format'],
    log_colors={'DEBUG': 'cyan', 'INFO': 'green', 'WARNING': 'yellow', 'ERROR': 'red', 'CRITICAL': 'red,bg_white'},
))
logger = logging.getLogger('etl_fpb_accused')
logger.setLevel(LOG_CONFIG['level'])
logger.addHandler(handler)
logger.propagate = False

FLAT_COLUMNS = [
    'age', 'alias', 'caste', 'cc_kd_dc_no', 'confession_statement', 'date_fingerprinted',
    'date_of_arrest', 'dob', 'father_husband_name', 'fir_reg_num', 'fp_unit', 'full_name', 'mo',
    'nationality', 'occupation', 'phone_number', 'place_of_birth', 'property_recovered',
    'ps_where_fps_obtained', 'religion', 'remarks', 'sex', 'slip_type', 'surname',
]


class FpbAccusedETL:
    def __init__(self):
        self.db_pool = PostgreSQLConnectionPool(minconn=1, maxconn=3, **DB_CONFIG)
        self.stats = {'pairs_processed': 0, 'accused_upserted': 0, 'failed_api_calls': 0}

    def pending_fir_ps_pairs(self, cursor) -> list[tuple[str, str, str]]:
        """(crime_id, fir_num, ps_code) triples not yet present in fpb_accused."""
        cursor.execute(
            f"""
            SELECT c.crime_id, c.fir_num, c.ps_code
            FROM {CRIMES_TABLE} c
            WHERE c.fir_num IS NOT NULL AND c.ps_code IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM {FPB_ACCUSED_TABLE} f
                  WHERE f.fir_num = c.fir_num AND f.ps_code = c.ps_code
              )
            """
        )
        return cursor.fetchall()

    def fetch_fpb_accused_api(self, fir_num: str, ps_code: str) -> list[dict] | None:
        url = API_CONFIG['fpb_accused_url']
        params = {'firNum': fir_num, 'psCode': ps_code}
        headers = {'x-api-key': API_CONFIG['api_key']}
        for attempt in range(API_CONFIG['max_retries']):
            try:
                logger.debug(f"Fetching FPB accused: firNum={fir_num} psCode={ps_code} (attempt {attempt + 1})")
                response = requests.get(url, params=params, headers=headers, timeout=API_CONFIG['timeout'])
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status'):
                        return data.get('data') or []
                    return []
                if response.status_code == 404:
                    return []
                logger.warning(f"API returned status code {response.status_code}, retrying...")
                time.sleep(2 ** attempt)
            except requests.exceptions.Timeout:
                logger.warning(f"API timeout, retrying... (attempt {attempt + 1})")
                time.sleep(2 ** attempt)
            except Exception as e:
                logger.error(f"API error: {e}")
                time.sleep(2 ** attempt)
        self.stats['failed_api_calls'] += 1
        logger.error(f"Failed to fetch FPB accused for firNum={fir_num} psCode={ps_code} after max retries")
        return None

    def insert_accused(self, cursor, crime_id: str, fir_num: str, ps_code: str, record: dict) -> None:
        aadhaar = record.get('AADHAAR_OR_OTHER_ID') or {}
        arrest = record.get('ARREST_DETAILS') or {}
        permanent = record.get('PERMANENT_ADDRESS') or {}
        present = record.get('PRESENT_ADDRESS') or {}
        pf = record.get('PHYSICAL_FEATURES') or {}

        flat_values = [record.get(col.upper()) for col in FLAT_COLUMNS]
        extra_columns = [
            'aadhaar_or_other_id_number', 'aadhaar_or_other_id_type',
            'arrest_details_crime_no', 'arrest_details_crime_year', 'arrest_details_district',
            'arrest_details_ps_name', 'arrest_details_section_of_law', 'arrest_details_state_of_arrest',
            'permanent_address_address', 'permanent_address_district', 'permanent_address_state_ut',
            'present_address_address', 'present_address_district', 'present_address_state_ut',
            'pf_beard', 'pf_chin', 'pf_complexion_of_face', 'pf_ear', 'pf_eyebrows', 'pf_forehead',
            'pf_hair', 'pf_hair_color', 'pf_height', 'pf_jaws', 'pf_lips', 'pf_moustaches',
            'pf_mouth', 'pf_neck', 'pf_nose', 'pf_shape_of_face', 'pf_weight',
        ]
        extra_values = [
            aadhaar.get('NUMBER'), aadhaar.get('TYPE'),
            arrest.get('CRIME_NO'), arrest.get('CRIME_YEAR'), arrest.get('DISTRICT'),
            arrest.get('PS_NAME'), arrest.get('SECTION_OF_LAW'), arrest.get('STATE_OF_ARREST'),
            permanent.get('ADDRESS'), permanent.get('DISTRICT'), permanent.get('STATE_UT'),
            present.get('ADDRESS'), present.get('DISTRICT'), present.get('STATE_UT'),
            pf.get('BEARD'), pf.get('CHIN'), pf.get('COMPLEXION_OF_FACE'), pf.get('EAR'),
            pf.get('EYEBROWS'), pf.get('FOREHEAD'), pf.get('HAIR'), pf.get('HAIR_COLOR'),
            pf.get('HEIGHT'), pf.get('JAWS'), pf.get('LIPS'), pf.get('MOUSTACHES'), pf.get('MOUTH'),
            pf.get('NECK'), pf.get('NOSE'), pf.get('SHAPE_OF_FACE'), pf.get('WEIGHT'),
        ]

        all_columns = ['crime_id', 'person_id', 'fir_num', 'ps_code'] + FLAT_COLUMNS + extra_columns
        all_values = [crime_id, record.get('PERSON_ID'), fir_num, ps_code] + flat_values + extra_values
        placeholders = ', '.join(['%s'] * len(all_columns))

        cursor.execute(
            f"""
            INSERT INTO {FPB_ACCUSED_TABLE} ({', '.join(all_columns)})
            VALUES ({placeholders})
            ON CONFLICT (fir_num, ps_code, full_name) DO NOTHING
            RETURNING fpb_accused_id
            """,
            all_values,
        )
        row = cursor.fetchone()
        if not row:
            return
        fpb_accused_id = row[0]
        self.stats['accused_upserted'] += 1

        for extra_crime in record.get('ADDITIONAL_CRIMES') or []:
            cursor.execute(
                f"""
                INSERT INTO {FPB_ADDITIONAL_CRIMES_TABLE}
                    (fpb_accused_id, crime_no, district, police_station, section_of_law, state, year)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    fpb_accused_id, extra_crime.get('CRIME_NO'), extra_crime.get('DISTRICT'),
                    extra_crime.get('POLICE_STATION'), extra_crime.get('SECTION_OF_LAW'),
                    extra_crime.get('STATE'), extra_crime.get('YEAR'),
                ),
            )

    def run(self) -> None:
        with self.db_pool.get_connection_context() as conn:
            with conn.cursor() as cursor:
                pairs = self.pending_fir_ps_pairs(cursor)
        logger.info(f"Found {len(pairs)} (fir_num, ps_code) pairs pending FPB accused fetch")

        for crime_id, fir_num, ps_code in pairs:
            records = self.fetch_fpb_accused_api(fir_num, ps_code)
            if records is None:
                continue
            with self.db_pool.get_connection_context() as conn:
                with conn.cursor() as cursor:
                    try:
                        for record in records:
                            self.insert_accused(cursor, crime_id, fir_num, ps_code, record)
                        conn.commit()
                    except Exception as e:
                        logger.error(f"Failed processing firNum={fir_num} psCode={ps_code}: {e}")
                        conn.rollback()
            self.stats['pairs_processed'] += 1

        logger.info(f"Done. Stats: {self.stats}")


if __name__ == '__main__':
    FpbAccusedETL().run()
