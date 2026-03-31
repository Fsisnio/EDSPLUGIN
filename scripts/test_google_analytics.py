#!/usr/bin/env python3
"""
Test that Google Analytics (gtag.js) is correctly installed in the Streamlit app.
"""
import sys
from pathlib import Path

# Path to streamlit app
APP_PATH = Path(__file__).resolve().parent.parent / "web_dashboard" / "streamlit_app.py"

REQUIRED_STRINGS = [
    "googletagmanager.com/gtag/js",
    "G-B9F48TD21L",
    "gtag('config', 'G-B9F48TD21L')",
]


def main() -> int:
    if not APP_PATH.exists():
        print(f"❌ App not found: {APP_PATH}")
        return 1

    content = APP_PATH.read_text()
    all_ok = True

    for s in REQUIRED_STRINGS:
        if s in content:
            print(f"✓ Found: {s[:50]}...")
        else:
            print(f"❌ Missing: {s}")
            all_ok = False

    if all_ok:
        print("\n✅ Google Analytics tag is present in the app.")
        print("\nTo verify it loads in the browser:")
        print("  1. Run: streamlit run web_dashboard/streamlit_app.py")
        print("  2. Open http://localhost:8501")
        print("  3. Open DevTools (F12) → Network tab")
        print("  4. Filter by 'gtag' or 'googletagmanager'")
        print("  5. You should see requests to googletagmanager.com")
        print("\nOr use Google Tag Assistant: https://tagassistant.google.com/")
        return 0
    else:
        print("\n❌ Google Analytics tag is incomplete.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
