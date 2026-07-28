# multi-file-edit

Command-line utility for changing the created, modified, and accessed dates for
files in a folder.

## Usage

```bash
python3 change_file_dates.py "/path/to/folder" "2024-01-31 09:30:00"
```

By default, the script updates all files inside the folder recursively.

Useful options:

```bash
# Preview changes without editing timestamps
python3 change_file_dates.py "/path/to/folder" "2024-01-31" --dry-run

# Only update files directly inside the folder
python3 change_file_dates.py "/path/to/folder" "2024-01-31" --no-recursive

# Also update folder timestamps
python3 change_file_dates.py "/path/to/folder" "2024-01-31" --include-dirs
```

Supported date formats:

- `YYYY-MM-DD`
- `YYYY-MM-DD HH:MM`
- `YYYY-MM-DD HH:MM:SS`
- `YYYY-MM-DDTHH:MM`
- `YYYY-MM-DDTHH:MM:SS`

Creation date changes are supported on macOS and Windows. Modified and accessed
dates are handled with Python's standard library.
