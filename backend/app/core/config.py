"""Environment configuration; secrets remain outside application source."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / '.env')
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', 'http://127.0.0.1:3000,http://localhost:3000').split(',')
COOKIE_SECURE = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'


def database_url() -> str:
    value = os.getenv('DATABASE_URL', '')
    if not value.startswith('postgresql+asyncpg://'):
        raise RuntimeError('Set DATABASE_URL to a PostgreSQL asyncpg connection URL in .env.')
    return value
