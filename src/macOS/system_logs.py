import os
import shutil
from datetime import datetime
import sys


LOG_SOURCES = {
    "var_log": "/var/log",
    "system_library_logs": "/Library/Logs",
    "user_library_logs": os.path.expanduser("~/Library/Logs"),
    "system_diagnostic_reports": "/Library/Logs/DiagnosticReports",
    "user_diagnostic_reports": os.path.expanduser("~/Library/Logs/DiagnosticReports"),
}


def get_project_root():
    return os.path.dirname(
        os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )
    )


def show_progress(current, total, width=40):
    """Display a single-line terminal progress bar."""
    if total <= 0:
        total = 1

    percent = current / total
    filled = int(width * percent)
    bar = "#" * filled + "-" * (width - filled)

    sys.stdout.write(
        f"\rProgress: [{bar}] {percent * 100:6.2f}% "
        f"({current}/{total})"
    )
    sys.stdout.flush()

    if current >= total:
        sys.stdout.write("\n")


def collect_files(source_dir):
    """Collect all regular files from a log source."""
    files_to_copy = []

    if not os.path.exists(source_dir):
        return files_to_copy

    for root, dirs, files in os.walk(source_dir):
        for file_name in files:
            files_to_copy.append(
                os.path.join(root, file_name)
            )

    return files_to_copy


def copy_directory(source_dir, destination_dir):
    """Copy all files from a system log source while showing progress."""
    if not os.path.exists(source_dir):
        print(f"Not found: {source_dir}")
        return

    files_to_copy = collect_files(source_dir)
    total_files = len(files_to_copy)

    if total_files == 0:
        print(f"No files found: {source_dir}")
        return

    copied = 0

    for source_path in files_to_copy:
        relative_path = os.path.relpath(source_path, source_dir)
        destination_path = os.path.join(
            destination_dir,
            relative_path
        )

        try:
            os.makedirs(
                os.path.dirname(destination_path),
                exist_ok=True
            )
            shutil.copy2(source_path, destination_path)
        except (PermissionError, OSError):
            pass

        copied += 1
        show_progress(copied, total_files)


def extract_mac_logs():
    """Extract file-based macOS system logs."""
    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M")
    project_root = get_project_root()

    output_root = os.path.join(project_root, "output_logs")
    output_dir = os.path.join(
        output_root,
        f"{timestamp}_logs"
    )
    os.makedirs(output_dir, exist_ok=True)

    for source_name, source_path in LOG_SOURCES.items():
        print(f"\nExtracting {source_name}...")

        destination_dir = os.path.join(
            output_dir,
            source_name
        )
        os.makedirs(destination_dir, exist_ok=True)

        copy_directory(
            source_path,
            destination_dir
        )

    print(f"\nLogs saved in: {output_dir}")


def main():
    """Run macOS system-log extraction."""
    extract_mac_logs()


if __name__ == "__main__":
    main()
