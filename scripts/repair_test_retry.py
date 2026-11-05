#!/usr/bin/env python3
"""Safely propose, apply, test, and retry local-LLM repairs."""

import argparse
import hashlib
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(root: Path, *args: str, input_text: str | None = None):
    return subprocess.run(
        ["git", *args],
        cwd=root,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )


def run_tests(root: Path, python: str) -> int:
    print("\n=== Running full test suite ===", flush=True)
    return subprocess.run(
        [python, "-m", "pytest", "-q"], cwd=root, check=False
    ).returncode



def validate_patch_preserves_symbols(patch: str, task: str) -> None:
    """Reject patches that unexpectedly delete Python imports or definitions."""
    files = {}
    current = None

    for line in patch.splitlines():
        if line.startswith("diff --git "):
            match = re.fullmatch(r"diff --git a/(.+) b/(.+)", line)
            current = match.group(1) if match else None
            if current is not None:
                files.setdefault(current, {"removed": [], "added": []})
            continue

        if current is None or current not in files:
            continue
        if line.startswith(("--- ", "+++ ", "@@")):
            continue

        if line.startswith("-"):
            content = line[1:].strip()
            if re.match(r"^(?:async\s+)?def\s+\w+|^class\s+\w+|^import\s+|^from\s+\S+\s+import\s+", content):
                files[current]["removed"].append(content)
        elif line.startswith("+"):
            content = line[1:].strip()
            if re.match(r"^(?:async\s+)?def\s+\w+|^class\s+\w+|^import\s+|^from\s+\S+\s+import\s+", content):
                files[current]["added"].append(content)

    explicit_removal = bool(re.search(
        r"\b(remove|delete|drop|rename)\b.{0,50}\b(function|class|import|module|definition)\b",
        task,
        re.IGNORECASE,
    ))

    for filename, changes in files.items():
        added = changes["added"]
        added_names = set()
        for content in added:
            definition = re.match(r"^(?:async\s+)?def\s+(\w+)|^class\s+(\w+)", content)
            if definition:
                added_names.add(definition.group(1) or definition.group(2))

        for content in changes["removed"]:
            definition = re.match(r"^(?:async\s+)?def\s+(\w+)|^class\s+(\w+)", content)
            if definition:
                name = definition.group(1) or definition.group(2)
                if name not in added_names and not explicit_removal:
                    raise ValueError(
                        f"Safety guard rejected patch: it removes {name!r} "
                        f"from {filename} without an explicit removal request."
                    )

        removed_imports = [
            item for item in changes["removed"]
            if item.startswith(("import ", "from "))
        ]
        added_imports = [
            item for item in added
            if item.startswith(("import ", "from "))
        ]
        if removed_imports and not added_imports and not explicit_removal:
            raise ValueError(
                f"Safety guard rejected patch: it removes existing imports "
                f"from {filename} without adding replacements."
            )

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bounded local-LLM repair, test, and retry workflow."
    )
    parser.add_argument("--files", nargs="+", required=True,
                        help="Existing repository files the model may change.")
    parser.add_argument("--task", required=True,
                        help="Specific repair request.")
    parser.add_argument("--max-attempts", type=int, default=2, choices=(1, 2))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--apply", action="store_true",
                        help="Authorize applying patches to the listed files.")
    args = parser.parse_args()

    root_result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        text=True, capture_output=True, check=False,
    )
    if root_result.returncode:
        print("Error: run this inside the repository.", file=sys.stderr)
        return 2
    root = Path(root_result.stdout.strip()).resolve()

    # Resolve and snapshot only explicitly authorized existing files.
    selected: dict[str, Path] = {}
    original: dict[str, bytes] = {}
    for name in args.files:
        candidate = Path(name)
        if candidate.is_absolute() or ".." in candidate.parts:
            parser.error(f"Unsafe file path: {name}")
        path = (root / candidate).resolve()
        if root not in path.parents or not path.is_file():
            parser.error(f"Not an existing repository file: {name}")
        relative = path.relative_to(root).as_posix()
        if relative in selected:
            parser.error(f"Duplicate file: {relative}")
        if path.stat().st_size > 100_000:
            parser.error(f"File exceeds 100 KB limit: {relative}")
        selected[relative] = path
        original[relative] = path.read_bytes()

    if not args.apply:
        print("Safety stop: no changes made.")
        print("Review the selected files and rerun with --apply to authorize")
        print("the bounded patch → test → retry workflow.")
        return 2

    print("=== Checking baseline before any repair ===", flush=True)
    baseline = run_tests(root, args.python)
    if baseline:
        print("Baseline failed; no patch was requested or applied.",
              file=sys.stderr)
        return baseline

    repair_script = root / "scripts" / "vscode_repair.py"
    if not repair_script.is_file():
        print(f"Missing proposal tool: {repair_script}", file=sys.stderr)
        return 2

    run_dir = Path(tempfile.mkdtemp(prefix="local-ai-office-repair-"))
    print(f"Repair logs and patches: {run_dir}", flush=True)

    # Hashes represent the last contents written by this runner.
    owned_hashes = {name: digest(data) for name, data in original.items()}
    failure_context = ""
    success = False

    for attempt in range(1, args.max_attempts + 1):
        print(f"\n=== Repair attempt {attempt}/{args.max_attempts} ===",
              flush=True)

        # Never overwrite edits made outside this runner after a patch.
        for name, path in selected.items():
            if digest(path.read_bytes()) != owned_hashes[name]:
                print(f"Safety stop: {name} changed unexpectedly; not applying "
                      "another patch.", file=sys.stderr)
                return 2

        patch_path = run_dir / f"attempt-{attempt}.patch"
        task = args.task
        if failure_context:
            task += (
                "\nThe previous proposed repair did not pass tests. "
                "Correct the remaining issue without undoing the original "
                "task. Latest test output:\n" + failure_context[-8000:]
            )

        command = [
            sys.executable, str(repair_script),
            "--files", *selected.keys(),
            "--task", task,
            "--output", str(patch_path),
        ]
        proposal = subprocess.run(
            command, cwd=root, text=True, capture_output=True, check=False
        )
        print(proposal.stdout, end="")
        if proposal.stderr:
            print(proposal.stderr, file=sys.stderr, end="")
        (run_dir / f"attempt-{attempt}-proposal.log").write_text(
            proposal.stdout + "\n" + proposal.stderr, encoding="utf-8"
        )
        if proposal.returncode or not patch_path.is_file():
            failure_context = (
                proposal.stdout + "\n" + proposal.stderr
                + "\nProposal generation failed. Return valid JSON in the "
                "required schema and make the smallest justified change."
            )
            if attempt < args.max_attempts:
                print(
                    "Proposal failed validation; retrying with the error "
                    "included in the next request.",
                    file=sys.stderr,
                    flush=True,
                )
                continue
            print("No valid patch produced after all attempts.", file=sys.stderr)
            break

        patch = patch_path.read_text(encoding="utf-8")
        if not patch.strip():
            print("Empty patch; nothing to apply.", file=sys.stderr)
            break

        # Ensure the patch only names files explicitly selected above.
        patch_names = set()
        for line in patch.splitlines():
            if line.startswith("diff --git "):
                match = re.fullmatch(r"diff --git a/(.+) b/(.+)", line)
                if not match or match.group(1) != match.group(2):
                    print("Safety stop: unsupported patch path format.",
                          file=sys.stderr)
                    return 2
                patch_names.add(match.group(1))
        if not patch_names or not patch_names.issubset(selected):
            print(f"Safety stop: patch touches unauthorized paths: "
                  f"{sorted(patch_names - set(selected))}", file=sys.stderr)
            return 2

        # Check selected files have not changed while the model was running.
        for name, path in selected.items():
            if digest(path.read_bytes()) != owned_hashes[name]:
                print(f"Safety stop: {name} changed during proposal generation.",
                      file=sys.stderr)
                return 2

        try:
            validate_patch_preserves_symbols(patch, args.task)
        except ValueError as exc:
            failure_context = str(exc)
            print(f"{failure_context}; patch was not applied.", file=sys.stderr)
            if attempt < args.max_attempts:
                print("Retrying once with the safety error as context.",
                      file=sys.stderr, flush=True)
                continue
            break

        check = git(root, "apply", "--check", "--", input_text=patch)
        if check.returncode:
            failure_context = check.stderr or check.stdout
            print("Patch failed git apply --check; not applied.",
                  file=sys.stderr)
            break

        applied = git(root, "apply", "--", input_text=patch)
        if applied.returncode:
            failure_context = applied.stderr or applied.stdout
            print("Patch application failed.", file=sys.stderr)
            break

        owned_hashes = {
            name: digest(path.read_bytes()) for name, path in selected.items()
        }
        test_result = subprocess.run(
            [args.python, "-m", "pytest", "-q"],
            cwd=root, text=True, capture_output=True, check=False,
        )
        output = test_result.stdout + "\n" + test_result.stderr
        (run_dir / f"attempt-{attempt}-tests.log").write_text(
            output, encoding="utf-8"
        )
        print(output, end="")
        if test_result.returncode == 0:
            success = True
            print(f"\nRepair passed the full test suite on attempt {attempt}.")
            break

        failure_context = output
        print("Tests failed after this patch.", file=sys.stderr)

    if success:
        print("\nReview your changes with: git diff --")
        print("No Docker containers were stopped or restarted.")
        return 0

    # Restore only runner-owned files, and only if nobody changed them
    # since the last successful application by this runner.
    print("\n=== Safe rollback of runner-owned file changes ===")
    conflicts = []
    for name, path in selected.items():
        if digest(path.read_bytes()) != owned_hashes[name]:
            conflicts.append(name)
    if conflicts:
        print("Rollback skipped for safety: files changed unexpectedly: "
              + ", ".join(conflicts), file=sys.stderr)
        print(f"Inspect the saved patches and logs in {run_dir}.")
        return 1

    for name, path in selected.items():
        path.write_bytes(original[name])
    print("Restored selected files to their exact pre-run contents.")
    print(f"Saved patches and logs: {run_dir}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
