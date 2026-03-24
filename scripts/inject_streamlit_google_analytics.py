#!/usr/bin/env python3
"""
Inject Google Analytics (gtag.js) into Streamlit's static index.html.

Streamlit loads the app in the main document; components.html runs in an iframe,
so Google's tag assistant does not see it. This patch fixes detection on e.g. Render.

Idempotent: safe to run multiple times.
"""
from __future__ import annotations

import pathlib
import re
import sys

MEASUREMENT_ID = "G-X76TEN0BS5"

SNIPPET = f"""    <!-- Google tag (gtag.js) -->
    <script async src="https://www.googletagmanager.com/gtag/js?id={MEASUREMENT_ID}"></script>
    <script>
      window.dataLayer = window.dataLayer || [];
      function gtag(){{dataLayer.push(arguments);}}
      gtag('js', new Date());
      gtag('config', '{MEASUREMENT_ID}');
    </script>
"""


def main() -> int:
    import streamlit

    index_path = pathlib.Path(streamlit.__file__).resolve().parent / "static" / "index.html"
    if not index_path.is_file():
        print(f"ERROR: {index_path} not found", file=sys.stderr)
        return 1

    text = index_path.read_text(encoding="utf-8")
    if MEASUREMENT_ID in text and "googletagmanager.com/gtag" in text:
        print(f"Already present: {index_path}")
        return 0

    if not re.search(r"</head>", text, flags=re.IGNORECASE):
        print("ERROR: </head> not found in index.html", file=sys.stderr)
        return 1

    new_text, n = re.subn(
        r"(</head>)",
        SNIPPET + r"\1",
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    if n != 1:
        print("ERROR: could not inject before </head>", file=sys.stderr)
        return 1

    index_path.write_text(new_text, encoding="utf-8")
    print(f"Injected GA ({MEASUREMENT_ID}) into {index_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
