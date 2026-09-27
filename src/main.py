import platform


def get_os():
    """Detect and normalize the current operating system."""
    system = platform.system().strip().lower()

    if system == "darwin":
        return "macos"
    if system == "windows":
        return "windows"
    if system == "linux":
        return "linux"
    if system == "android":
        return "android"
    if system == "ios":
        return "ios"

    return "unknown"


def main():
    """Detect the OS and redirect execution to the appropriate OS manager."""
    os_type = get_os()

    print("=" * 50)
    print("Cross-Platform Log Extractor")
    print("=" * 50)
    print(f"Detected OS: {os_type.capitalize()}")

    if os_type == "macos":
        try:
            from macOS.MAC_manager import main as os_main
        except (ImportError, ModuleNotFoundError) as e:
            print(f"macOS module could not be loaded: {e}")
            return

        os_main()
        return

    if os_type == "windows":
        print("Windows log extraction is coming soon.")
        return

    if os_type == "linux":
        print("Linux log extraction is coming soon.")
        return

    if os_type == "android":
        print("Android log extraction is coming soon.")
        return

    if os_type == "ios":
        print("iOS log extraction is coming soon.")
        return

    print("Unsupported operating system. Exiting.")


if __name__ == "__main__":
    main()
