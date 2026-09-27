import os
import shutil
import subprocess
import sys
from datetime import datetime


# Only these locations are considered application-owned log locations.
# The code does NOT recursively search all of Application Support or
# all of Containers for an application-name substring.
BASE_LOG_SOURCES = [
    os.path.expanduser("~/Library/Logs"),
    "/Library/Logs",
]


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


def run_command(command):
    """Run a macOS command and return stdout, or an empty string on failure."""
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass

    return ""


def find_application(app_name):
    """
    Resolve the actual .app bundle instead of searching the filesystem
    for the application name.
    """
    query = (
        f'kMDItemCFBundleDisplayName == "{app_name}"cd '
        f'&& kMDItemContentType == "com.apple.application-bundle"'
    )

    output = run_command(["mdfind", query])

    if output:
        candidates = [
            line.strip()
            for line in output.splitlines()
            if line.strip().endswith(".app")
        ]

        if candidates:
            # Prefer the normal Applications directories.
            candidates.sort(
                key=lambda p: (
                    0 if p.startswith("/Applications/") else
                    1 if p.startswith(os.path.expanduser("~/Applications/")) else
                    2,
                    len(p),
                )
            )
            return candidates[0]

    # Fallback for applications whose display name is not indexed as expected.
    common_paths = [
        f"/Applications/{app_name}.app",
        os.path.expanduser(f"~/Applications/{app_name}.app"),
    ]

    for path in common_paths:
        if os.path.exists(path):
            return path

    return None


def get_bundle_id(app_path):
    """Read the application's real bundle identifier from its .app bundle."""
    bundle_id = run_command(
        ["mdls", "-raw", "-name", "kMDItemCFBundleIdentifier", app_path]
    )

    if bundle_id and bundle_id != "(null)":
        return bundle_id.strip()

    # Fallback to Info.plist if mdls does not return the identifier.
    info_plist = os.path.join(app_path, "Contents", "Info.plist")

    if os.path.exists(info_plist):
        bundle_id = run_command(
            [
                "/usr/libexec/PlistBuddy",
                "-c",
                "Print :CFBundleIdentifier",
                info_plist,
            ]
        )

        if bundle_id:
            return bundle_id.strip()

    return None


def get_app_specific_sources(app_name, app_path, bundle_id):
    """
    Build a list of locations that belong to this application.

    The important rule is that broad directories such as
    ~/Library/Application Support and ~/Library/Containers are NEVER
    recursively searched as a whole.
    """
    home = os.path.expanduser("~")
    sources = []

    app_dir_name = os.path.splitext(os.path.basename(app_path))[0]

    # Conventional per-user/system log directories.
    for base in BASE_LOG_SOURCES:
        candidates = [
            os.path.join(base, app_dir_name),
            os.path.join(base, app_name),
        ]

        if bundle_id:
            candidates.extend(
                [
                    os.path.join(base, bundle_id),
                    os.path.join(base, bundle_id.split(".")[-1]),
                ]
            )

        sources.extend(candidates)

    # Application Support: inspect ONLY an exact application directory.
    application_support = os.path.join(
        home,
        "Library",
        "Application Support",
    )

    sources.extend(
        [
            os.path.join(application_support, app_dir_name),
            os.path.join(application_support, app_name),
        ]
    )

    if bundle_id:
        sources.append(
            os.path.join(application_support, bundle_id)
        )

    # Sandboxed application container.
    containers_root = os.path.join(
        home,
        "Library",
        "Containers",
    )

    if bundle_id:
        # Current sandbox convention.
        sources.append(
            os.path.join(containers_root, bundle_id, "Data", "Library", "Logs")
        )

        # Only inspect containers whose directory name is the exact bundle ID
        # or a recognized WhatsApp-style bundle prefix.
        if bundle_id.startswith("net.whatsapp."):
            sources.append(
                os.path.join(
                    containers_root,
                    bundle_id,
                    "Data",
                    "Library",
                    "Application Support",
                    "WhatsApp",
                )
            )

    # Group Containers used by modern applications such as WhatsApp.
    group_containers_root = os.path.join(
        home,
        "Library",
        "Group Containers",
    )

    if os.path.isdir(group_containers_root) and bundle_id:
        bundle_parts = bundle_id.split(".")

        for entry in os.listdir(group_containers_root):
            entry_path = os.path.join(group_containers_root, entry)

            if not os.path.isdir(entry_path):
                continue

            # A group container is accepted only when its name contains the
            # complete application bundle ID as a component.
            if bundle_id.lower() in entry.lower():
                sources.append(entry_path)

            # WhatsApp currently uses group.net.whatsapp.WhatsApp.shared.
            elif (
                bundle_id == "net.whatsapp.WhatsApp"
                and entry.lower().startswith("group.net.whatsapp.whatsapp")
            ):
                sources.append(entry_path)

    # Remove duplicates while preserving order.
    unique_sources = []
    seen = set()

    for source in sources:
        normalized = os.path.normpath(source)

        if normalized not in seen:
            seen.add(normalized)
            unique_sources.append(normalized)

    return unique_sources


def collect_files(source_path):
    """Collect files only from already-identified application-owned sources."""
    files = []

    if not os.path.exists(source_path):
        return files

    if os.path.isfile(source_path):
        return [source_path]

    for root, dirs, file_names in os.walk(source_path):
        for file_name in file_names:
            full_path = os.path.join(root, file_name)

            # Ignore Finder metadata and macOS resource-fork files.
            if file_name == ".DS_Store" or file_name.startswith("._"):
                continue

            files.append(full_path)

    return files


def is_likely_log_file(file_path):
    """
    Keep actual log-oriented files and diagnostic reports.

    Application Support databases/configuration/media are not treated as
    application logs merely because their path contains the app name.
    """
    file_name = os.path.basename(file_path).lower()
    extension = os.path.splitext(file_name)[1].lower()

    log_extensions = {
        ".log",
        ".logarchive",
        ".ips",
        ".crash",
        ".txt",
    }

    if extension in log_extensions:
        return True

    # Some applications use files without a .log extension inside a directory
    # explicitly named Logs.
    normalized = file_path.replace("\\", "/").lower()

    if "/logs/" in normalized:
        return True

    # WhatsApp's current group-container log directory can contain files
    # without conventional extensions.
    if "group.net.whatsapp.whatsapp" in normalized and "/logs/" in normalized:
        return True

    return False


def build_file_list(source_paths):
    """Collect and de-duplicate actual log files from app-owned sources."""
    files = []
    seen = set()

    for source in source_paths:
        for file_path in collect_files(source):
            if not is_likely_log_file(file_path):
                continue

            real_path = os.path.realpath(file_path)

            if real_path in seen:
                continue

            seen.add(real_path)
            files.append((source, file_path))

    return files


def copy_logs(files, output_dir):
    """Copy selected logs while displaying only a progress bar."""
    total = len(files)

    if total == 0:
        return 0

    copied = 0

    for source_path, file_path in files:
        relative_path = os.path.relpath(file_path, source_path)

        source_label = os.path.basename(source_path)

        if source_label in ("", ".", os.sep):
            source_label = "logs"

        destination_file = os.path.join(
            output_dir,
            source_label,
            relative_path,
        )

        try:
            os.makedirs(
                os.path.dirname(destination_file),
                exist_ok=True,
            )
            shutil.copy2(file_path, destination_file)
        except (PermissionError, OSError):
            pass

        copied += 1
        show_progress(copied, total)

    return copied


def extract_app_logs(app_name):
    """Extract file-based logs from locations belonging to the requested app."""
    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M")
    project_root = get_project_root()

    output_root = os.path.join(project_root, "output_logs")

    safe_app_name = "".join(
        character
        for character in app_name
        if character.isalnum() or character in ("_", "-")
    ) or "application"

    output_dir = os.path.join(
        output_root,
        f"{timestamp}_{safe_app_name}_logs",
    )

    print(f"\nFinding application: {app_name}...")

    app_path = find_application(app_name)

    if not app_path:
        print(f"Application '{app_name}' was not found on this Mac.")
        print("Make sure the application is installed in /Applications")
        print("or ~/Applications.")
        return

    bundle_id = get_bundle_id(app_path)

    print(f"Application: {app_path}")

    if bundle_id:
        print(f"Bundle ID: {bundle_id}")
    else:
        print("Bundle ID: could not be determined.")

    source_paths = get_app_specific_sources(
        app_name,
        app_path,
        bundle_id,
    )

    files = build_file_list(source_paths)

    if not files:
        print(f"\nNo file-based logs found for '{app_name}'.")
        print(
            "The application may store its logs in the macOS Unified "
            "Logging System instead of regular files."
        )
        return

    # Create the output folder only after actual log files have been found.
    os.makedirs(output_dir, exist_ok=True)

    print(f"\nFound {len(files)} application log file(s).")
    print("Extracting...")

    copied = copy_logs(files, output_dir)

    print(f"\nCompleted: {copied} file(s) processed.")
    print(f"Logs saved in: {output_dir}")


def main():
    """Prompt for an application name and extract its file-based logs."""
    app_name = input(
        "Enter the application name for which you want to extract logs "
        "(e.g., WhatsApp, Safari, Chrome, VSCode): "
    ).strip()

    if not app_name:
        print("Application name is required. Exiting.")
        return

    extract_app_logs(app_name)


if __name__ == "__main__":
    main()
