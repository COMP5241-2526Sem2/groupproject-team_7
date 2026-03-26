"""
AWS S3 Storage Service for managing file uploads, downloads, and access.

This service provides a wrapper around the boto3 S3 client for uploading
slide PDFs, videos, thumbnails, and other media files to AWS S3.
"""

import os
import logging
import tempfile
from typing import Optional, Tuple
from io import BytesIO
import boto3
from botocore.exceptions import ClientError
from flask import current_app

logger = logging.getLogger(__name__)


class S3StorageService:
    """Service for managing file storage in AWS S3."""

    def __init__(self):
        """Initialize S3 client with credentials from app config."""
        self.s3_client = None
        self.bucket_name = None

    def _get_client(self):
        """Lazy-load and return S3 client."""
        if self.s3_client is None:
            self.s3_client = boto3.client(
                "s3",
                region_name=current_app.config.get("AWS_S3_REGION", "us-east-1"),
                aws_access_key_id=current_app.config.get("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=current_app.config.get("AWS_SECRET_ACCESS_KEY"),
                endpoint_url=current_app.config.get("AWS_S3_ENDPOINT_URL"),
            )
            self.bucket_name = current_app.config.get("AWS_S3_BUCKET")
        return self.s3_client

    def upload_file(self, file_obj, s3_key: str, content_type: str = "application/octet-stream") -> str:
        """
        Upload a file to S3.

        Args:
            file_obj: File-like object or bytes to upload
            s3_key: S3 object key (path within bucket)
            content_type: MIME type of the file

        Returns:
            S3 object key if successful

        Raises:
            Exception: If upload fails
        """
        try:
            client = self._get_client()
            client.upload_fileobj(
                file_obj,
                self.bucket_name,
                s3_key,
                ExtraArgs={"ContentType": content_type},
            )
            logger.info(f"Uploaded file to S3: s3://{self.bucket_name}/{s3_key}")
            return s3_key
        except ClientError as e:
            logger.error(f"Failed to upload file to S3: {e}")
            raise

    def download_file(self, s3_key: str) -> BytesIO:
        """
        Download a file from S3 to memory.

        Args:
            s3_key: S3 object key

        Returns:
            BytesIO object containing file content

        Raises:
            Exception: If download fails
        """
        try:
            client = self._get_client()
            file_obj = BytesIO()
            client.download_fileobj(self.bucket_name, s3_key, file_obj)
            file_obj.seek(0)
            logger.info(f"Downloaded file from S3: s3://{self.bucket_name}/{s3_key}")
            return file_obj
        except ClientError as e:
            logger.error(f"Failed to download file from S3: {e}")
            raise

    def download_to_temp_file(self, s3_key: str) -> str:
        """
        Download a file from S3 to a temporary local file.

        Useful for processing files that require local file paths (e.g., fitz.open()).

        Args:
            s3_key: S3 object key

        Returns:
            Path to temporary file

        Raises:
            Exception: If download fails
        """
        try:
            temp_dir = current_app.config.get("TEMP_UPLOAD_DIR", "/tmp/synclearn_uploads")
            os.makedirs(temp_dir, exist_ok=True)

            # Create temp file with matching extension
            _, ext = os.path.splitext(s3_key)
            temp_file = tempfile.NamedTemporaryFile(suffix=ext, dir=temp_dir, delete=False)
            temp_path = temp_file.name

            client = self._get_client()
            client.download_file(self.bucket_name, s3_key, temp_path)
            logger.info(f"Downloaded S3 file to temp: {temp_path}")
            return temp_path
        except ClientError as e:
            logger.error(f"Failed to download file to temp: {e}")
            raise

    def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> str:
        """
        Generate a presigned URL for accessing a file in S3.

        Args:
            s3_key: S3 object key
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            Presigned URL that can be used to access the file

        Raises:
            Exception: If URL generation fails
        """
        try:
            client = self._get_client()
            url = client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": s3_key},
                ExpiresIn=expiration,
            )
            logger.info(f"Generated presigned URL for: {s3_key}")
            return url
        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise

    def delete_file(self, s3_key: str) -> bool:
        """
        Delete a file from S3.

        Args:
            s3_key: S3 object key

        Returns:
            True if successful

        Raises:
            Exception: If deletion fails
        """
        try:
            client = self._get_client()
            client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"Deleted file from S3: {s3_key}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete file from S3: {e}")
            raise

    def delete_directory(self, s3_prefix: str) -> bool:
        """
        Delete all files under a prefix in S3 (simulating directory deletion).

        Args:
            s3_prefix: S3 prefix (path) to delete

        Returns:
            True if successful

        Raises:
            Exception: If deletion fails
        """
        try:
            client = self._get_client()
            paginator = client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=s3_prefix)

            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        client.delete_object(Bucket=self.bucket_name, Key=obj["Key"])

            logger.info(f"Deleted directory prefix from S3: {s3_prefix}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete directory from S3: {e}")
            raise

    def list_files(self, s3_prefix: str) -> list:
        """
        List all files under a prefix in S3.

        Args:
            s3_prefix: S3 prefix (path) to list

        Returns:
            List of S3 object keys

        Raises:
            Exception: If listing fails
        """
        try:
            client = self._get_client()
            files = []
            paginator = client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=s3_prefix)

            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        files.append(obj["Key"])

            logger.info(f"Listed {len(files)} files under prefix: {s3_prefix}")
            return files
        except ClientError as e:
            logger.error(f"Failed to list files from S3: {e}")
            raise


# Global instance
_s3_service = None


def get_s3_service() -> S3StorageService:
    """Get or create the S3 storage service singleton."""
    global _s3_service
    if _s3_service is None:
        _s3_service = S3StorageService()
    return _s3_service
