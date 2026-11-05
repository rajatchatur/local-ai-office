#!/usr/bin/env python3
"""Interactive VS Code launcher for the local AI repair workflow."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNNER = ROOT / "scripts" / "repair_test_retry.py"


def main() -> int:
    print("\n=== Local AI Office: Automated Repair ===")
    task = input("Describe the repair you want: ").strip()
    if not task:
        print("Cancelled: a repair task is required.")
        return 2

    raw_files = input(
        "Repository-relative files to give the model "
        "(comma-separated): "
    ).strip()
    files = [item.strip() for item in raw_files.split(",") if item.strip()]
    if not files:
        print("Cancelled: specify at least one file.")
        return 2

    print("\nSelected files:")
    for name in files:
        print(f"  - {name}")
    print("\nThe runner will check the existing test baseline first.")
    answer = input(
        "Allow a validated patch to be applied and tested? Type APPLY: "
    ).strip()

    command = [
        sys.executable, str(RUNNER),
        "--files", *files,
        "--task", task,
        "--max-attempts", "2",
    ]
    if answer == "APPLY":
        command.append("--apply")
    else:
        print("Proposal-only mode: source files will not be modified.")

    print("\nStarting repair runner...\n", flush=True)
    result = subprocess.run(command, cwd=ROOT)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
