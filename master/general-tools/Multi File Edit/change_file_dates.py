#!/usr/bin/env python3
"""Set created, modified, and accessed timestamps for files in a folder."""

from __future__ import annotations

import argparse
import ctypes
import os
import platform
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%dT%H:%M:%S",
)


@dataclass
class Result:
    changed: int = 0
    skipped: int = 0
    failed: int = 0


def parse_date(value: str) -> datetime:
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(value, date_format)
        except ValueError:
            pass

    expected = ", ".join(DATE_FORMATS)
    raise argparse.ArgumentTypeError(
        f"invalid date {value!r}; expected one of: {expected}"
    )


def iter_targets(
    folder: Path,
    recursive: bool,
    include_dirs: bool,
    follow_symlinks: bool,
) -> Iterable[Path]:
    if recursive:
        for root, dirs, files in os.walk(folder, followlinks=follow_symlinks):
            root_path = Path(root)

            if include_dirs:
                for name in dirs:
                    path = root_path / name
                    if follow_symlinks or not path.is_symlink():
                        yield path

            for name in files:
                path = root_path / name
                if follow_symlinks or not path.is_symlink():
                    yield path
    else:
        for path in folder.iterdir():
            if path.is_symlink() and not follow_symlinks:
                continue
            if path.is_file() or (include_dirs and path.is_dir()):
                yield path


class MacTimespec(ctypes.Structure):
    _fields_ = [
        ("tv_sec", ctypes.c_long),
        ("tv_nsec", ctypes.c_long),
    ]


class MacAttrList(ctypes.Structure):
    _fields_ = [
        ("bitmapcount", ctypes.c_ushort),
        ("reserved", ctypes.c_ushort),
        ("commonattr", ctypes.c_uint),
        ("volattr", ctypes.c_uint),
        ("dirattr", ctypes.c_uint),
        ("fileattr", ctypes.c_uint),
        ("forkattr", ctypes.c_uint),
    ]


def set_creation_time_macos(path: Path, timestamp: float) -> None:
    attr_bit_map_count = 5
    attr_cmn_crtime = 0x00000200

    attr_list = MacAttrList()
    attr_list.bitmapcount = attr_bit_map_count
    attr_list.commonattr = attr_cmn_crtime

    seconds = int(timestamp)
    nanoseconds = int((timestamp - seconds) * 1_000_000_000)
    timespec = MacTimespec(seconds, nanoseconds)

    libc = ctypes.CDLL("libc.dylib", use_errno=True)
    result = libc.setattrlist(
        os.fsencode(path),
        ctypes.byref(attr_list),
        ctypes.byref(timespec),
        ctypes.sizeof(timespec),
        0,
    )
    if result != 0:
        errno = ctypes.get_errno()
        raise OSError(errno, os.strerror(errno), str(path))


class WindowsFileTime(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", ctypes.c_ulong),
        ("dwHighDateTime", ctypes.c_ulong),
    ]


def set_creation_time_windows(path: Path, timestamp: float) -> None:
    kernel32 = ctypes.windll.kernel32

    file_write_attributes = 0x0100
    file_share_all = 0x00000001 | 0x00000002 | 0x00000004
    open_existing = 3
    file_flag_backup_semantics = 0x02000000
    invalid_handle_value = ctypes.c_void_p(-1).value

    handle = kernel32.CreateFileW(
        str(path),
        file_write_attributes,
        file_share_all,
        None,
        open_existing,
        file_flag_backup_semantics,
        None,
    )
    if handle == invalid_handle_value:
        raise ctypes.WinError()

    try:
        intervals = int((timestamp + 11_644_473_600) * 10_000_000)
        filetime = WindowsFileTime(
            intervals & 0xFFFFFFFF,
            intervals >> 32,
        )
        if not kernel32.SetFileTime(handle, ctypes.byref(filetime), None, None):
            raise ctypes.WinError()
    finally:
        kernel32.CloseHandle(handle)


def set_creation_time(path: Path, timestamp: float) -> None:
    system = platform.system()
    if system == "Darwin":
        set_creation_time_macos(path, timestamp)
    elif system == "Windows":
        set_creation_time_windows(path, timestamp)
    else:
        raise RuntimeError(
            "setting file creation time is only supported by this script on "
            "macOS and Windows"
        )


def change_dates(
    folder: Path,
    when: datetime,
    recursive: bool,
    include_dirs: bool,
    follow_symlinks: bool,
    dry_run: bool,
) -> Result:
    result = Result()
    timestamp = when.timestamp()

    for path in iter_targets(folder, recursive, include_dirs, follow_symlinks):
        if dry_run:
            print(f"Would update: {path}")
            result.skipped += 1
            continue

        try:
            set_creation_time(path, timestamp)
            os.utime(path, (timestamp, timestamp), follow_symlinks=follow_symlinks)
            print(f"Updated: {path}")
            result.changed += 1
        except Exception as exc:
            print(f"Failed: {path} ({exc})", file=sys.stderr)
            result.failed += 1

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Change created, modified, and accessed dates for files in a folder."
        )
    )
    parser.add_argument("folder", type=Path, help="Folder containing files to update.")
    parser.add_argument(
        "date",
        type=parse_date,
        help=(
            "Date to apply. Examples: 2024-01-31, "
            "'2024-01-31 09:30:00', 2024-01-31T09:30:00."
        ),
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Only update files directly inside the folder.",
    )
    parser.add_argument(
        "--include-dirs",
        action="store_true",
        help="Also update dates on directories inside the target folder.",
    )
    parser.add_argument(
        "--follow-symlinks",
        action="store_true",
        help="Update symbolic link targets instead of skipping symlinks.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without modifying timestamps.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    folder = args.folder.expanduser().resolve()
    if not folder.exists():
        parser.error(f"folder does not exist: {folder}")
    if not folder.is_dir():
        parser.error(f"path is not a folder: {folder}")

    result = change_dates(
        folder=folder,
        when=args.date,
        recursive=not args.no_recursive,
        include_dirs=args.include_dirs,
        follow_symlinks=args.follow_symlinks,
        dry_run=args.dry_run,
    )

    print(
        f"Done. Changed: {result.changed}, skipped: {result.skipped}, "
        f"failed: {result.failed}."
    )
    return 1 if result.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
