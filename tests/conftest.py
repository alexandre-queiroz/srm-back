import os

# Set dummy env vars before any app module is imported.
# Unit tests are fully mocked — these values are never used in real calls.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests")
os.environ.setdefault("EXCHANGE_RATE_PRIMARY_URL", "http://localhost/primary")
os.environ.setdefault("EXCHANGE_RATE_SECONDARY_URL", "http://localhost/secondary")
os.environ.setdefault("AXIOM_TOKEN", "test-axiom-token")
os.environ.setdefault("AXIOM_DATASET", "test-dataset")
os.environ.setdefault("R2_ENDPOINT_URL", "http://localhost/r2")
os.environ.setdefault("R2_ACCESS_KEY_ID", "test-key-id")
os.environ.setdefault("R2_SECRET_ACCESS_KEY", "test-secret")
os.environ.setdefault("R2_BUCKET_NAME", "test-bucket")
os.environ.setdefault("CRON_SECRET", "test-cron-secret")
