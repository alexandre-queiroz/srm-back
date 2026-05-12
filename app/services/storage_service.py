import boto3
from botocore.config import Config

from app.core.config import settings

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=settings.R2_ENDPOINT_URL,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
            region_name="auto",
        )
    return _client


def upload_xml(key: str, content: bytes) -> str:
    """Upload XML to R2 and return the storage key."""
    _get_client().put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=key,
        Body=content,
        ContentType="application/xml",
    )
    return f"r2://{settings.R2_BUCKET_NAME}/{key}"


def download_xml(key: str) -> bytes:
    """Download XML from R2 by key. Key format: r2://bucket/path or plain path."""
    if key.startswith("r2://"):
        key = key.split("/", 3)[-1]
    response = _get_client().get_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
    return response["Body"].read()
