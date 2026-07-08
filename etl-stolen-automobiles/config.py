"""Configuration for etl-stolen-automobiles."""

from env_utils import (
    get_int_env,
    load_repo_environment,
    resolve_api_base_url,
    resolve_db_config,
    resolve_table_name,
)

load_repo_environment()

import os as _os
from datetime import datetime as _dt, timedelta as _td, timezone as _tz
_IST = _tz(_td(hours=5, minutes=30))
_from_date = _os.environ.get('ETL_FROM_DATE', '2022-06-01')
_to_date = _os.environ.get('ETL_TO_DATE', (_dt.now(_IST) - _td(days=1)).strftime('%Y-%m-%d'))

DB_CONFIG = resolve_db_config()


def get_api_endpoint(endpoint_key: str, default_path: str) -> str:
    base_url_override = resolve_api_base_url(f'{endpoint_key.upper()}_API_BASE_URL', default='') or ''
    base_url = base_url_override or resolve_api_base_url('DOPAMAS_API_URL2', default='') or resolve_api_base_url('DOPAMAS_API_URL') or ''
    endpoint_path = (resolve_api_base_url(f'{endpoint_key.upper()}_API_ENDPOINT', default='') or '').strip() or default_path
    if endpoint_path and not endpoint_path.startswith('/'):
        endpoint_path = '/' + endpoint_path
    return f"{base_url.rstrip('/')}{endpoint_path}"


API_CONFIG = {
    'base_url': resolve_api_base_url('DOPAMAS_API_URL'),
    'api_key': resolve_api_base_url('DOPAMAS_API_KEY'),
    'timeout': get_int_env('API_TIMEOUT', 180),
    'max_retries': get_int_env('API_MAX_RETRIES', 5),
    'stolen_automobiles_url': get_api_endpoint('stolen_automobiles', '/reports/stolen-automobiles'),
}

ETL_CONFIG = {
    'start_date': f"{_from_date}T00:00:00+05:30",
    'end_date': f"{_to_date}T23:59:59+05:30",
    'chunk_days': 5,
    'chunk_overlap_days': get_int_env('CHUNK_OVERLAP_DAYS', 1),
}

LOG_CONFIG = {
    'level': resolve_api_base_url('LOG_LEVEL', default='INFO'),
    'format': '%(log_color)s%(asctime)s - %(levelname)s - %(message)s',
    'date_format': '%Y-%m-%d %H:%M:%S',
}

TABLE_CONFIG = {
    'crimes': resolve_table_name('CRIMES_TABLE', 'crimes'),
    'stolen_automobiles': resolve_table_name('STOLEN_AUTOMOBILES_TABLE', 'stolen_automobiles'),
    'stolen_automobile_media': resolve_table_name('STOLEN_AUTOMOBILE_MEDIA_TABLE', 'stolen_automobile_media'),
}
