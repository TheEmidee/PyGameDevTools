# gamedevtools/s3/__init__.py

from .s3_client import S3Client, S3UploadedObject

# Option A: Explicit export (Best for mypy)
__all__ = ["S3Client", "S3UploadedObject"]
