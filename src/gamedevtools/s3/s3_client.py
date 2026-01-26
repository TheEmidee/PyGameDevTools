import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional
from urllib.parse import quote

import boto3
from botocore.exceptions import ClientError  # type: ignore[import-untyped]
from mypy_boto3_s3.type_defs import ObjectIdentifierTypeDef, ObjectTypeDef
from tqdm import tqdm


@dataclass
class S3UploadedObject:
    file_path: Path
    s3_key: str
    download_url: str
    file_size: int


class S3ProgressCallback:
    """Thread-safe callback for tracking upload progress across multiple files."""

    def __init__(self, pbar: tqdm) -> None:
        self._pbar = pbar
        self._lock = threading.Lock()

    def __call__(self, bytes_amount: int) -> None:
        with self._lock:
            self._pbar.update(bytes_amount)


class S3Client:
    def __init__(self, access_key: str, secret_key: str, region: str) -> None:
        self.s3 = boto3.client("s3", aws_access_key_id=access_key, aws_secret_access_key=secret_key, region_name=region)

    def get_bucket_files(self, bucket_name: str, prefix: str, filter_func: Optional[Callable[[ObjectTypeDef], bool]] = None) -> List[str]:
        """
        Retrieve a list of files from an S3 bucket with optional filtering.
        Args:
            bucket_name (str): The name of the S3 bucket to query.
            prefix (str): The prefix (directory path) within the bucket to search under.
            filter_func: A callable that takes an S3 object and returns True if the object should be included.
        Returns:
            List[str]: A list of S3 object keys (file paths) that match the filter criteria.
        """
        paginator = self.s3.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

        files = []
        for page in pages:
            if "Contents" in page:
                files.extend([obj["Key"] for obj in page["Contents"] if filter_func is None or filter_func(obj)])

        return files

    def folder_exists_in_bucket(self, bucket_name: str, folder_name: str) -> bool:
        """Check if a folder exists in the S3 bucket."""
        response = self.s3.list_objects_v2(Bucket=bucket_name, Prefix=f"{folder_name}/", MaxKeys=1)
        return "Contents" in response

    def find_available_folder_name(self, bucket_name: str, base_folder_name: str) -> str:
        """Find an available folder name by auto-incrementing if needed."""
        if not self.folder_exists_in_bucket(bucket_name, base_folder_name):
            return base_folder_name

        # Find the next available increment
        counter = 1
        while True:
            candidate_name = f"{base_folder_name}_{counter:02d}"
            if not self.folder_exists_in_bucket(bucket_name, candidate_name):
                return candidate_name
            counter += 1

            # Safety check to prevent infinite loop
            if counter > 999:
                raise RuntimeError(f"Too many folders with base name '{base_folder_name}' (reached limit of 999)")

    def download_file(self, bucket_name: str, key: str, local_folder: Path, show_progress_bar: bool = False) -> bool:
        """
        Download a file from an S3 bucket to a local folder.
        Args:
            bucket_name (str): The name of the S3 bucket.
            key (str): The S3 object key (path) of the file to download.
            local_folder (Path): The local folder path where the file will be saved.
            show_progress_bar (bool, optional): Whether to display a progress bar during download. Defaults to False.
        Returns:
            bool: True if the download was successful.
        """
        filename = os.path.basename(key)
        local_path = local_folder.joinpath(filename)

        response = self.s3.head_object(Bucket=bucket_name, Key=key)
        file_size = response["ContentLength"]

        pbar = None

        if show_progress_bar:
            pbar = tqdm(total=file_size, unit="B", unit_scale=True, desc=filename)

        self.s3.download_file(bucket_name, key, str(local_path), Callback=lambda bytes_transferred: pbar.update(bytes_transferred) if pbar else None)

        if pbar:
            pbar.close()

        return True

    def upload_folder_to_s3(
        self, local_folder: str, bucket_name: str, destination_folder: str, region: str = "", show_progress: bool = True
    ) -> tuple[bool, list[S3UploadedObject]]:
        """Upload all files in a local folder to S3 and return list of uploaded files."""
        local_path = Path(local_folder)

        if not local_path.is_dir():
            print(f"Error: '{local_folder}' is not a valid directory.")
            return False, []

        # 1. Gather file info
        all_files = []
        total_size = 0
        for file_path in local_path.rglob("*"):
            if file_path.is_file():
                size = file_path.stat().st_size
                all_files.append((file_path, size))
                total_size += size

        if not all_files:
            return False, []

        uploaded_objects: list[S3UploadedObject] = []

        # 2. Setup Progress Bars
        # position=0 is the bottom bar, position=1 is the one above it
        overall_pbar = None
        if show_progress:
            overall_pbar = tqdm(total=total_size, unit="B", unit_scale=True, desc="Total Progress", position=0)

        callback = S3ProgressCallback(overall_pbar) if overall_pbar else None

        # 3. Upload Loop
        for file_path, file_size in all_files:
            relative_path = file_path.relative_to(local_path)
            s3_key = f"{destination_folder}/{relative_path}".replace("\\", "/")

            file_pbar = None
            if show_progress:
                # Individual file progress (clears when done due to leave=False)
                file_pbar = tqdm(total=file_size, unit="B", unit_scale=True, desc=f"Uploading {file_path.name}", position=1, leave=False)

            try:
                # Wrap the callback to update both the overall pbar AND the file pbar
                def combined_callback(bytes_amount: int) -> None:
                    if callback:
                        callback(bytes_amount)
                    if file_pbar:
                        file_pbar.update(bytes_amount)

                self.s3.upload_file(str(file_path), bucket_name, s3_key, Callback=combined_callback)

                # Store metadata
                url = self.generate_download_url(bucket_name, s3_key, region)
                uploaded_objects.append(S3UploadedObject(file_path, s3_key, url, file_size))

            except ClientError as e:
                print(f"\nError uploading {file_path.name}: {e}")
            finally:
                if file_pbar:
                    file_pbar.close()

        if overall_pbar:
            overall_pbar.close()

        return len(uploaded_objects) > 0, uploaded_objects

    def generate_download_url(self, bucket_name: str, s3_key: str, region: str = "") -> str:
        """Generate a direct download URL for an S3 object."""
        if region != "us-east-1":
            base_url = f"https://{bucket_name}.s3.{region}.amazonaws.com"
        else:
            base_url = f"https://{bucket_name}.s3.amazonaws.com"

        # URL encode the key to handle special characters
        encoded_key = quote(s3_key, safe="/")
        return f"{base_url}/{encoded_key}"

    def cleanup_old_folders(self, bucket_name: str, keep_count: int) -> None:
        """Remove old folders, keeping only the specified number of most recent ones."""
        folders = self.get_folders_in_bucket(bucket_name)

        if keep_count <= 0:
            print("Warning: keep_count must be positive. No cleanup performed.")
            return

        if len(folders) <= keep_count:
            print(f"Found {len(folders)} folders, keeping all (limit: {keep_count})")
            return

        # Sort folders by name in descending order (assuming names are sortable)
        folders.sort(reverse=True)

        folders_to_keep = folders[:keep_count]
        folders_to_delete = folders[keep_count:]

        print(f"Keeping {len(folders_to_keep)} folders: {folders_to_keep}")
        print(f"Deleting {len(folders_to_delete)} old folders: {folders_to_delete}")

        for folder in folders_to_delete:
            self.delete_folder_from_s3(bucket_name, folder)

    def get_folders_in_bucket(self, bucket_name: str) -> List[str]:
        """Get all top-level folders in the S3 bucket."""
        folders = set()

        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=bucket_name, Delimiter="/")

            for page in pages:
                if "CommonPrefixes" in page:
                    for prefix in page["CommonPrefixes"]:
                        folder_name = prefix["Prefix"].rstrip("/")
                        folders.add(folder_name)

        except ClientError as e:
            print(f"Error listing folders: {e}")
            return []

        return list(folders)

    def delete_folder_from_s3(self, bucket_name: str, folder_name: str) -> None:
        """Delete all objects in a folder from S3."""
        try:
            keys_to_delete = self.get_bucket_files(bucket_name, f"{folder_name}/")

            if keys_to_delete:
                # Transform List[str] -> List[dict] for S3 API compatibility
                # Format: [{'Key': 'file1.txt'}, {'Key': 'file2.txt'}]
                delete_list: list[ObjectIdentifierTypeDef] = [{"Key": key} for key in keys_to_delete]

                for i in range(0, len(delete_list), 1000):
                    batch = delete_list[i : i + 1000]
                    self.s3.delete_objects(Bucket=bucket_name, Delete={"Objects": batch})

                print(f"Deleted folder '{folder_name}' ({len(keys_to_delete)} objects)")
            else:
                print(f"Folder '{folder_name}' was already empty")

        except ClientError as e:
            print(f"Error deleting folder '{folder_name}': {e}")
