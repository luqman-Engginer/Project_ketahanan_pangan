"""Build the production CSS with the Tailwind standalone CLI.

Downloads the pinned Tailwind standalone binary into ``.bin/`` on first run,
then compiles ``app/static/css/input.css`` to ``app/static/css/app.css``.

Usage: python scripts/build_css.py [--watch]
"""
from __future__ import annotations

import argparse
import os
import platform
import subprocess
import sys
import urllib.request
from pathlib import Path

TAILWIND_VERSION = "3.4.17"
ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = ROOT / ".bin"
INPUT_CSS = ROOT / "app" / "static" / "css" / "input.css"
OUTPUT_CSS = ROOT / "app" / "static" / "css" / "app.css"


def _asset_name() -> str:
    """Return the release asset filename for the current platform."""
    system = platform.system()
    machine = platform.machine().lower()
    arm64 = machine in {"arm64", "aarch64"}
    if system == "Windows":
        return "tailwindcss-windows-arm64.exe" if arm64 else "tailwindcss-windows-x64.exe"
    if system == "Darwin":
        return "tailwindcss-macos-aarch64" if arm64 else "tailwindcss-macos-x64"
    return "tailwindcss-linux-arm64" if arm64 else "tailwindcss-linux-x64"


def ensure_binary() -> Path:
    """Download the Tailwind standalone CLI if it is not present yet."""
    BIN_DIR.mkdir(exist_ok=True)
    target = BIN_DIR / ("tailwindcss.exe" if platform.system() == "Windows" else "tailwindcss")
    if target.exists():
        return target
    url = f"https://github.com/tailwindlabs/tailwindcss/releases/download/v{TAILWIND_VERSION}/{_asset_name()}"
    print(f"Downloading Tailwind CLI v{TAILWIND_VERSION} from {url}")
    urllib.request.urlretrieve(url, target)
    if platform.system() != "Windows":
        os.chmod(target, 0o755)
    return target


def main() -> int:
    """Compile (or watch) the CSS bundle."""
    parser = argparse.ArgumentParser(description="Build Tailwind CSS bundle.")
    parser.add_argument("--watch", action="store_true", help="Rebuild on file changes.")
    args = parser.parse_args()

    binary = ensure_binary()
    command = [str(binary), "-i", str(INPUT_CSS), "-o", str(OUTPUT_CSS)]
    command.append("--watch" if args.watch else "--minify")
    result = subprocess.run(command, cwd=ROOT, check=False)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
