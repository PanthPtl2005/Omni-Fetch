from . import system_logs
from . import app_logs


def main():
    """Provide the macOS log-extraction menu."""
    print("=" * 50)
    print("macOS Log Extractor")
    print("=" * 50)
    print("1. System Logs")
    print("2. App Logs")

    choice = input("Enter 1 or 2: ").strip()

    if choice == "1":
        system_logs.main()
    elif choice == "2":
        app_logs.main()
    else:
        print("Invalid choice. Exiting.")


if __name__ == "__main__":
    main()
