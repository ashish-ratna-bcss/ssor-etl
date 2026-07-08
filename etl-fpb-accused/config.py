"""Configuration for etl-fpb-accused."""

from env_utils import (
    get_int_env,
    load_repo_environment,
    resolve_api_base_url,
    resolve_db_config,
    resolve_table_name,
)

load_repo_environment()

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
    'fpb_accused_url': get_api_endpoint('fpb_accused', '/fpb/accused'),
}

LOG_CONFIG = {
    'level': resolve_api_base_url('LOG_LEVEL', default='INFO'),
    'format': '%(log_color)s%(asctime)s - %(levelname)s - %(message)s',
    'date_format': '%Y-%m-%d %H:%M:%S',
}

TABLE_CONFIG = {
    'crimes': resolve_table_name('CRIMES_TABLE', 'crimes'),
    'fpb_accused': resolve_table_name('FPB_ACCUSED_TABLE', 'fpb_accused'),
    'fpb_additional_crimes': resolve_table_name('FPB_ADDITIONAL_CRIMES_TABLE', 'fpb_additional_crimes'),
}
