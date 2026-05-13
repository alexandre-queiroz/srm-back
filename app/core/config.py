from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    EXCHANGE_RATE_PRIMARY_URL: str
    EXCHANGE_RATE_SECONDARY_URL: str

    OTEL_SERVICE_NAME: str = "srm-credit-engine"
    AXIOM_TOKEN: str
    AXIOM_DATASET: str

    R2_ENDPOINT_URL: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_BUCKET_NAME: str

    WORKER_POLL_INTERVAL: int = 60

    model_config = {"env_file": ".env"}


settings = Settings()
