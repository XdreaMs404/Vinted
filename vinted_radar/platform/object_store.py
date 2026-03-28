from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import json
from typing import Any

from vinted_radar.domain.events import canonical_json, normalize_prefix, sha256_hex
from vinted_radar.domain.manifests import EvidenceManifestEntry
from vinted_radar.platform.config import ObjectStorageConfig, PlatformConfig

_SHA256_METADATA_KEY = "sha256"
_DEFAULT_CONTENT_TYPE = "application/octet-stream"


@dataclass(frozen=True, slots=True)
class ObjectStoreObject:
    bucket: str
    key: str
    content_type: str
    content_length: int
    checksum: str
    etag: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name, value in (
            ("bucket", self.bucket),
            ("key", self.key),
            ("content_type", self.content_type),
            ("checksum", self.checksum),
        ):
            if not str(value).strip():
                raise ValueError(f"{field_name} cannot be empty")
        if self.content_length < 0:
            raise ValueError("content_length must be >= 0")
        object.__setattr__(self, "metadata", _normalize_metadata(self.metadata))

    def as_dict(self) -> dict[str, object]:
        return {
            "bucket": self.bucket,
            "key": self.key,
            "content_type": self.content_type,
            "content_length": self.content_length,
            "checksum": self.checksum,
            "etag": self.etag,
            "metadata": dict(self.metadata),
        }

    def as_manifest_entry(self, *, logical_name: str) -> EvidenceManifestEntry:
        return EvidenceManifestEntry(
            logical_name=logical_name,
            object_key=self.key,
            content_type=self.content_type,
            content_length=self.content_length,
            checksum=self.checksum,
        )


@dataclass(frozen=True, slots=True)
class ObjectStoreReadResult(ObjectStoreObject):
    data: bytes = b""
    checksum_verified: bool = False

    def as_dict(self) -> dict[str, object]:
        payload = super().as_dict()
        payload.update(
            {
                "data_length": len(self.data),
                "checksum_verified": self.checksum_verified,
            }
        )
        return payload


class S3ObjectStore:
    def __init__(
        self,
        client: object,
        *,
        bucket: str,
        region: str = "us-east-1",
    ) -> None:
        if not str(bucket).strip():
            raise ValueError("bucket cannot be empty")
        self.client = client
        self.bucket = str(bucket).strip()
        self.region = str(region).strip() or "us-east-1"

    @classmethod
    def from_config(
        cls,
        config: PlatformConfig | ObjectStorageConfig,
        *,
        client: object | None = None,
    ) -> S3ObjectStore:
        object_storage = config.object_storage if isinstance(config, PlatformConfig) else config
        resolved_client = create_s3_client(object_storage) if client is None else client
        return cls(
            resolved_client,
            bucket=object_storage.bucket,
            region=object_storage.region,
        )

    def bucket_exists(self) -> bool:
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return True
        except Exception as exc:  # noqa: BLE001
            code = _error_code(exc)
            if code in {"404", "NoSuchBucket", "NotFound"}:
                return False
            raise

    def ensure_bucket(self, *, create_if_missing: bool = True) -> bool:
        if self.bucket_exists():
            return False
        if not create_if_missing:
            raise ValueError(f"Bucket '{self.bucket}' does not exist")
        if self.region == "us-east-1":
            self.client.create_bucket(Bucket=self.bucket)
        else:
            self.client.create_bucket(
                Bucket=self.bucket,
                CreateBucketConfiguration={"LocationConstraint": self.region},
            )
        return True

    def exists(self, key: str) -> bool:
        return self.try_head(key) is not None

    def try_head(self, key: str) -> ObjectStoreObject | None:
        normalized_key = normalize_prefix(key)
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=normalized_key)
        except Exception as exc:  # noqa: BLE001
            code = _error_code(exc)
            if code in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise
        return _object_from_response(
            bucket=self.bucket,
            key=normalized_key,
            response=response,
        )

    def head(self, key: str) -> ObjectStoreObject:
        result = self.try_head(key)
        if result is None:
            raise FileNotFoundError(f"Object '{key}' was not found in bucket '{self.bucket}'")
        return result

    def put_bytes(
        self,
        *,
        key: str,
        data: bytes,
        content_type: str = _DEFAULT_CONTENT_TYPE,
        metadata: Mapping[str, object] | None = None,
        overwrite: bool = False,
    ) -> ObjectStoreObject:
        normalized_key = normalize_prefix(key)
        checksum = sha256_hex(data)
        normalized_metadata = _normalize_metadata(metadata)
        existing = self.try_head(normalized_key)
        if existing is not None:
            if existing.checksum == checksum:
                return existing
            if not overwrite:
                raise ValueError(
                    f"Object '{normalized_key}' already exists with checksum {existing.checksum}; expected {checksum}"
                )

        payload_metadata = dict(normalized_metadata)
        payload_metadata[_SHA256_METADATA_KEY] = checksum
        response = self.client.put_object(
            Bucket=self.bucket,
            Key=normalized_key,
            Body=data,
            ContentType=content_type,
            Metadata=payload_metadata,
        )
        return ObjectStoreObject(
            bucket=self.bucket,
            key=normalized_key,
            content_type=content_type,
            content_length=len(data),
            checksum=checksum,
            etag=_etag(response),
            metadata=payload_metadata,
        )

    def put_text(
        self,
        *,
        key: str,
        text: str,
        content_type: str = "text/plain; charset=utf-8",
        metadata: Mapping[str, object] | None = None,
        overwrite: bool = False,
    ) -> ObjectStoreObject:
        return self.put_bytes(
            key=key,
            data=text.encode("utf-8"),
            content_type=content_type,
            metadata=metadata,
            overwrite=overwrite,
        )

    def put_json(
        self,
        *,
        key: str,
        payload: Any,
        metadata: Mapping[str, object] | None = None,
        overwrite: bool = False,
    ) -> ObjectStoreObject:
        return self.put_text(
            key=key,
            text=canonical_json(payload),
            content_type="application/json",
            metadata=metadata,
            overwrite=overwrite,
        )

    def get_bytes(self, key: str, *, verify_checksum: bool = True) -> ObjectStoreReadResult:
        normalized_key = normalize_prefix(key)
        response = self.client.get_object(Bucket=self.bucket, Key=normalized_key)
        body = response.get("Body")
        if body is None or not hasattr(body, "read"):
            raise ValueError("Object-store response body is missing a readable stream")
        try:
            data = body.read()
        finally:
            close = getattr(body, "close", None)
            if callable(close):
                close()

        metadata = _normalize_metadata(response.get("Metadata"))
        checksum = sha256_hex(data)
        recorded_checksum = metadata.get(_SHA256_METADATA_KEY, checksum)
        if verify_checksum and recorded_checksum != checksum:
            raise ValueError(
                f"Checksum mismatch for object '{normalized_key}': recorded {recorded_checksum}, actual {checksum}"
            )
        content_length = int(response.get("ContentLength") or len(data))
        if content_length != len(data):
            raise ValueError(
                f"Content-length mismatch for object '{normalized_key}': header {content_length}, actual {len(data)}"
            )
        return ObjectStoreReadResult(
            bucket=self.bucket,
            key=normalized_key,
            content_type=str(response.get("ContentType") or _DEFAULT_CONTENT_TYPE),
            content_length=content_length,
            checksum=recorded_checksum,
            etag=_etag(response),
            metadata=metadata,
            data=data,
            checksum_verified=recorded_checksum == checksum,
        )

    def get_text(self, key: str, *, verify_checksum: bool = True) -> str:
        result = self.get_bytes(key, verify_checksum=verify_checksum)
        return result.data.decode("utf-8")

    def get_json(self, key: str, *, verify_checksum: bool = True) -> Any:
        return json.loads(self.get_text(key, verify_checksum=verify_checksum))

    def list_keys(self, prefix: str, *, limit: int | None = None) -> list[str]:
        normalized_prefix = normalize_prefix(prefix)
        keys: list[str] = []
        continuation_token: str | None = None

        while True:
            request: dict[str, object] = {
                "Bucket": self.bucket,
                "Prefix": normalized_prefix,
            }
            if continuation_token is not None:
                request["ContinuationToken"] = continuation_token
            response = self.client.list_objects_v2(**request)
            contents = response.get("Contents") if isinstance(response, Mapping) else None
            if isinstance(contents, list):
                for item in contents:
                    if not isinstance(item, Mapping):
                        continue
                    key = item.get("Key")
                    if key is None:
                        continue
                    keys.append(str(key))
                    if limit is not None and len(keys) >= limit:
                        return keys[:limit]

            if not isinstance(response, Mapping) or not response.get("IsTruncated"):
                break
            next_token = response.get("NextContinuationToken")
            if next_token is None:
                break
            continuation_token = str(next_token)

        return keys

    def delete(self, key: str) -> None:
        normalized_key = normalize_prefix(key)
        self.client.delete_object(Bucket=self.bucket, Key=normalized_key)


def create_s3_client(config: ObjectStorageConfig):
    import boto3
    from botocore.config import Config as BotoConfig

    return boto3.client(
        "s3",
        endpoint_url=config.endpoint_url,
        aws_access_key_id=config.access_key_id,
        aws_secret_access_key=config.secret_access_key,
        region_name=config.region,
        config=BotoConfig(s3={"addressing_style": "path"}),
    )


def _object_from_response(*, bucket: str, key: str, response: Mapping[str, Any]) -> ObjectStoreObject:
    metadata = _normalize_metadata(response.get("Metadata"))
    checksum = metadata.get(_SHA256_METADATA_KEY)
    if checksum is None:
        raise ValueError(f"Object '{key}' is missing recorded sha256 metadata")
    return ObjectStoreObject(
        bucket=bucket,
        key=key,
        content_type=str(response.get("ContentType") or _DEFAULT_CONTENT_TYPE),
        content_length=int(response.get("ContentLength") or 0),
        checksum=checksum,
        etag=_etag(response),
        metadata=metadata,
    )


def _normalize_metadata(metadata: Mapping[str, object] | None) -> dict[str, str]:
    if metadata is None:
        return {}
    return {
        str(key).strip().lower(): str(value).strip()
        for key, value in metadata.items()
        if str(key).strip() and str(value).strip()
    }


def _etag(response: object) -> str | None:
    if not isinstance(response, Mapping):
        return None
    value = response.get("ETag")
    if value is None:
        return None
    return str(value).strip().strip('"') or None


def _error_code(exc: Exception) -> str | None:
    response = getattr(exc, "response", None)
    if not isinstance(response, Mapping):
        return None
    error = response.get("Error")
    if not isinstance(error, Mapping):
        return None
    code = error.get("Code")
    return None if code is None else str(code)


__all__ = [
    "ObjectStoreObject",
    "ObjectStoreReadResult",
    "S3ObjectStore",
    "create_s3_client",
]
