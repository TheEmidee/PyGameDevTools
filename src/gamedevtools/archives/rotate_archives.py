#!/usr/bin/env python3
"""
Directory move and cleanup script.

This script creates a new directory (named using the current date format,
yyyyMMdd) inside a destination directory, handles name conflicts by adding
incremental suffixes, moves the contents of a source directory into it, and
cleans up old directories in the destination directory, keeping only the
specified number of most recent ones.
"""

import argparse
import shutil
import sys
from pathlib import Path

from ..helpers import get_date_formatted_name


def find_available_name(parent_dir: Path, base_name: str) -> str:
    """
    Find an available directory name by adding incremental suffix if needed.

    Args:
        parent_dir (Path): Parent directory path
        base_name (str): Base name (e.g., "20240729")

    Returns:
        str: Available directory name
    """
    target_path = parent_dir / base_name

    if not target_path.exists():
        return base_name

    # Find the next available suffix
    counter = 1
    while True:
        suffixed_name = f"{base_name}_{counter:02d}"
        target_path = parent_dir / suffixed_name
        if not target_path.exists():
            return suffixed_name
        counter += 1


def cleanup_old_directories(parent_dir: Path, keep_count: int) -> None:
    """
    Keep only the most recent X directories in the parent directory.

    Args:
        parent_dir (Path): Parent directory path
        keep_count (int): Number of directories to keep
    """

    print(f"\nCleaning up directories (keeping {keep_count} most recent)...")

    if keep_count <= 0:
        print("Warning: keep_count must be positive. No cleanup performed.")
        return

    # Get all directories in parent directory
    directories = [d for d in parent_dir.iterdir() if d.is_dir()]

    if len(directories) <= keep_count:
        print(f"Found {len(directories)} directories. Nothing to clean up.")
        return

    directories.sort(key=lambda x: x.name, reverse=True)

    # Keep the most recent ones, remove the rest
    dirs_to_keep = directories[:keep_count]
    dirs_to_remove = directories[keep_count:]

    print(f"Keeping {len(dirs_to_keep)} most recent directories:")
    for d in dirs_to_keep:
        print(f"  - {d.name}")

    print(f"\nRemoving {len(dirs_to_remove)} old directories:")
    for d in dirs_to_remove:
        try:
            shutil.rmtree(d)
            print(f"  - Removed: {d.name}")
        except Exception as e:
            print(f"  - Failed to remove {d.name}: {e}")


def move_directory_contents(source_dir: Path, target_dir: Path) -> None:
    """
    Move all files and subdirectories from source_dir into target_dir.

    Args:
        source_dir (Path): Directory whose contents will be moved
        target_dir (Path): Directory the contents will be moved into
    """
    for item in source_dir.iterdir():
        destination_item = target_dir / item.name
        shutil.move(str(item), str(destination_item))
        print(f"  - Moved: {item.name}")


def write_output_file(output_path: Path, renamed_folder_path: Path) -> None:
    """
    Writes the path of the last folder in the output path.

    Args:
        output_path (Path): Path to the output file
        content (str): Content to write
    """
    # Write directory name to output file if specified
    try:
        output_file_path = Path(output_path)
        # Create parent directories if they don't exist
        output_file_path.parent.mkdir(parents=True, exist_ok=True)
        # Write the directory name to the file
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write(str(renamed_folder_path))
        print(f"Directory name written to: {output_file_path}")
    except Exception as e:
        print(f"Warning: Failed to write to output file '{output_path}': {e}")


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""

    parser = argparse.ArgumentParser(description="Move contents of a source directory into a new date-named directory and cleanup old directories")
    parser.add_argument("--source_directory", help="Path to the directory whose contents should be moved")
    parser.add_argument("--destination_directory", help="Path to the directory where the new date-named directory will be created")
    parser.add_argument(
        "--keep_count",
        type=int,
        default=10,
        help="Number of directories to keep in the destination folder",
    )
    parser.add_argument(
        "--folder_output_file_name",
        "-o",
        help="Optional path to text file where the new directory name will be written",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    # Convert to Path objects
    source_path = Path(args.source_directory).resolve()
    destination_path = Path(args.destination_directory).resolve()

    # Check if the source directory exists
    if not source_path.exists():
        print(f"Error: Directory '{source_path}' does not exist.")
        sys.exit(1)

    if not source_path.is_dir():
        print(f"Error: '{source_path}' is not a directory.")
        sys.exit(1)

    print(f"Source directory : {source_path.name}")

    if not any(source_path.iterdir()):
        print(f"Source directory '{source_path.name}' is empty. Nothing to move.")
        sys.exit(1)

    # Make sure the destination directory exists
    destination_path.mkdir(parents=True, exist_ok=True)

    # Get current date name
    date_name = get_date_formatted_name()

    # Find available name (handle conflicts) inside the destination directory
    new_name = find_available_name(destination_path, date_name)
    new_path = destination_path / new_name

    # Create the new directory and move the source directory's contents into it
    try:
        new_path.mkdir(parents=True, exist_ok=False)
        print(f"Created new directory: '{new_path}'")

        print(f"Moving contents of '{source_path.name}' into '{new_name}'...")
        move_directory_contents(source_path, new_path)

        print(f"Successfully moved contents of '{source_path.name}' to '{new_name}'")

        if args.folder_output_file_name:
            write_output_file(args.folder_output_file_name, new_path)
    except Exception as e:
        print(f"Error moving directory contents: {e}")
        sys.exit(1)

    cleanup_old_directories(destination_path, args.keep_count)

    print("\nOperation completed successfully!")


if __name__ == "__main__":
    main()