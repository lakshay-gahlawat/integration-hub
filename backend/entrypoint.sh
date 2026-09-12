#!/bin/sh
set -e

echo "Waiting for database..."
python - <<'PY'
import time
import sys
from sqlalchemy import create_engine, text
from app.core.config import settings

for attempt in range(30):
    try:
        engine = create_engine(settings.DATABASE_URL)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("Database is ready.")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        print(f"Database not ready yet ({exc.__class__.__name__}), retrying... ({attempt + 1}/30)")
        time.sleep(2)
print("Database never became ready.")
sys.exit(1)
PY

python - <<'PY'
import sys
from app.core.config import settings

if not settings.INTEGRATION_ENCRYPTION_KEY:
    print(
        "FATAL: INTEGRATION_ENCRYPTION_KEY is not set. Generate one with:\n"
        '  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"\n'
        "and set it in your .env file before starting the application."
    )
    sys.exit(1)
PY

echo "Running database migrations..."
alembic upgrade head

echo "Starting: $@"
exec "$@"
