#!/usr/bin/env python3
"""etl-stolen-automobiles -- raw fetch-and-store for GET /reports/stolen-automobiles.

Pure CCTNS raw API data, no derived/AI transformation: fetches records changed
in a date range (DATE_CREATED/DATE_MODIFIED-driven, same chunked-overlap
pattern as the other date-range ETLs), upserts into stolen_automobiles, and
replaces the MEDIA[] child rows per record.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timedelta

import colorlog
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE)
for p in (PROJECT_ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from config import API_CONFIG, DB_CONFIG, ETL_CONFIG, LOG_CONFIG, TABLE_CONFIG  # noqa: E402
from db_pooling import PostgreSQLConnectionPool  # noqa: E402

STOLEN_AUTOMOBILES_TABLE = TABLE_CONFIG['stolen_automobiles']
STOLEN_AUTOMOBILE_MEDIA_TABLE = TABLE_CONFIG['stolen_automobile_media']
CRIMES_TABLE = TABLE_CONFIG['crimes']
API_DATA_START_DATE = '2022-06-01'

handler = colorlog.StreamHandler()
handler.setFormatter(colorlog.ColoredFormatter(
    LOG_CONFIG['format'], LOG_CONFIG['date_format'],
    log_colors={'DEBUG': 'cyan', 'INFO': 'green', 'WARNING': 'yellow', 'ERROR': 'red', 'CRITICAL': 'red,bg_white'},
))
logger = logging.getLogger('etl_stolen_automobiles')
logger.setLevel(LOG_CONFIG['level'])
logger.addHandler(handler)
logger.propagate = False

# Every raw column this ETL writes, in API-field order (used for the upsert's SET clause).
COLUMNS = [
    'auto_seq_no', 'auto_type', 'belongs_to_whom', 'chassis_no', 'classification', 'color',
    'color_type', 'date_created', 'date_modified', 'date_of_seizure', 'district', 'driver_side',
    'engine_capacity', 'engine_no', 'estimate_value', 'fuel', 'full_chassis_no', 'full_engine_no',
    'insurance_certificate_no', 'insurance_company_name', 'license_class', 'lifting_capacity',
    'location_type', 'made', 'make', 'manufactured', 'manufacturer', 'mfg_month', 'mfg_year',
    'model', 'mv_utility', 'nature_of_stolen', 'over_all_length', 'owner_father_name', 'owner_name',
    'particular_of_property', 'permanent_address', 'place_of_recovery', 'present_address',
    'property_category', 'property_category_name', 'property_recovered_from', 'property_status',
    'recovered_value', 'registered_at', 'registered_mobile_no', 'registered_owner',
    'registration_date', 'registration_no', 'registration_number', 'registration_place',
    'registration_valid_upto', 'remarks', 'rta_name', 'rta_verification_date', 'seat_capacity',
    'seq_no', 'slogan_picture', 'special_identification', 'sub_classification',
    'tmp_registration_no', 'total_estimated_value', 'ulw', 'variant', 'wheel_base',
]

# API field -> our column, only where the name actually differs.
FIELD_OVERRIDES = {}


def api_field_to_column(record: dict, column: str) -> object:
    api_field = FIELD_OVERRIDES.get(column, column.upper())
    return record.get(api_field)


class StolenAutomobilesETL:
    def __init__(self):
        self.db_pool = PostgreSQLConnectionPool(minconn=2, maxconn=5, **DB_CONFIG)
        self.stats = {'fetched': 0, 'upserted': 0, 'skipped_no_crime': 0, 'failed_api_calls': 0}

    def get_effective_start_date(self) -> str:
        force_start = os.environ.get('FORCE_START_DATE')
        if force_start:
            logger.info(f"FORCE_START_DATE override: {force_start}")
            return force_start
        with self.db_pool.get_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {STOLEN_AUTOMOBILES_TABLE}")
                if cur.fetchone()[0] == 0:
                    return API_DATA_START_DATE
                cur.execute(
                    f"SELECT GREATEST(MAX(date_created), MAX(date_modified)) FROM {STOLEN_AUTOMOBILES_TABLE}"
                )
                row = cur.fetchone()
                if row and row[0]:
                    return max(row[0].strftime('%Y-%m-%d'), API_DATA_START_DATE)
        return API_DATA_START_DATE

    def generate_date_ranges(self, start_date: str, end_date: str) -> list[tuple[str, str]]:
        chunk_days = ETL_CONFIG['chunk_days']
        overlap_days = ETL_CONFIG['chunk_overlap_days']
        start = datetime.fromisoformat(start_date).date()
        end = datetime.fromisoformat(end_date).date()
        ranges = []
        current = start
        while current <= end:
            chunk_end = min(current + timedelta(days=chunk_days - 1), end)
            ranges.append((current.strftime('%Y-%m-%d'), chunk_end.strftime('%Y-%m-%d')))
            current = chunk_end - timedelta(days=overlap_days - 1) + timedelta(days=1)
        return ranges

    def fetch_stolen_automobiles_api(self, from_date: str, to_date: str) -> list[dict] | None:
        url = API_CONFIG['stolen_automobiles_url']
        params = {'fromDate': from_date, 'toDate': to_date}
        headers = {'x-api-key': API_CONFIG['api_key']}
        for attempt in range(API_CONFIG['max_retries']):
            try:
                logger.debug(f"Fetching stolen automobiles: {from_date} to {to_date} (attempt {attempt + 1})")
                response = requests.get(url, params=params, headers=headers, timeout=API_CONFIG['timeout'])
                if response.status_code == 200:
                    data = response.json()
                    if data.get('status'):
                        records = data.get('data') or []
                        logger.info(f"Fetched {len(records)} stolen automobile records for {from_date} to {to_date}")
                        return records
                    logger.warning(f"API returned status=false for {from_date} to {to_date}")
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
        logger.error(f"Failed to fetch stolen automobiles for {from_date} to {to_date} after max retries")
        return None

    def crime_exists(self, cursor, crime_id: str) -> bool:
        if not crime_id:
            return False
        cursor.execute(f"SELECT 1 FROM {CRIMES_TABLE} WHERE crime_id = %s", (crime_id,))
        return cursor.fetchone() is not None

    def upsert_record(self, cursor, record: dict) -> None:
        stolen_property_id = record.get('STOLEN_PROPERTY_ID')
        crime_id = record.get('CRIME_ID')
        if not stolen_property_id:
            return
        if not self.crime_exists(cursor, crime_id):
            logger.warning(f"Skipping stolen automobile {stolen_property_id}: crime_id {crime_id} not found")
            self.stats['skipped_no_crime'] += 1
            return

        values = {col: api_field_to_column(record, col) for col in COLUMNS}
        set_clause = ', '.join(f"{col} = COALESCE(EXCLUDED.{col}, {STOLEN_AUTOMOBILES_TABLE}.{col})" for col in COLUMNS)
        insert_cols = ['stolen_property_id', 'crime_id'] + COLUMNS
        placeholders = ', '.join(['%s'] * len(insert_cols))
        cursor.execute(
            f"""
            INSERT INTO {STOLEN_AUTOMOBILES_TABLE} ({', '.join(insert_cols)})
            VALUES ({placeholders})
            ON CONFLICT (stolen_property_id) DO UPDATE SET {set_clause}
            """,
            [stolen_property_id, crime_id] + [values[col] for col in COLUMNS],
        )
        self.stats['upserted'] += 1

        cursor.execute(f"DELETE FROM {STOLEN_AUTOMOBILE_MEDIA_TABLE} WHERE stolen_property_id = %s", (stolen_property_id,))
        media_refs = record.get('MEDIA') or []
        if media_refs:
            cursor.executemany(
                f"INSERT INTO {STOLEN_AUTOMOBILE_MEDIA_TABLE} (stolen_property_id, media_ref) VALUES (%s, %s)",
                [(stolen_property_id, ref) for ref in media_refs if ref],
            )

    def process_date_range(self, from_date: str, to_date: str) -> None:
        records = self.fetch_stolen_automobiles_api(from_date, to_date)
        if records is None:
            return
        self.stats['fetched'] += len(records)
        with self.db_pool.get_connection_context() as conn:
            with conn.cursor() as cursor:
                for record in records:
                    try:
                        self.upsert_record(cursor, record)
                    except Exception as e:
                        logger.error(f"Failed to upsert {record.get('STOLEN_PROPERTY_ID')}: {e}")
                        conn.rollback()
                        continue
                conn.commit()

    def run(self) -> None:
        start_date = self.get_effective_start_date()
        end_date = datetime.now().strftime('%Y-%m-%d')
        logger.info(f"Running etl-stolen-automobiles from {start_date} to {end_date}")
        for from_date, to_date in self.generate_date_ranges(start_date, end_date):
            self.process_date_range(from_date, to_date)
        logger.info(f"Done. Stats: {self.stats}")


if __name__ == '__main__':
    StolenAutomobilesETL().run()
