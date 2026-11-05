import json

import pytest

from scripts.vscode_repair import parse_model_proposal


def test_parse_model_proposal_accepts_empty_changes():
    assert parse_model_proposal('{"changes": []}') == []


def test_parse_model_proposal_accepts_a_change():
    raw = json.dumps({
        "changes": [{"path": "example.py", "content": "print(1)"}]
    })
    assert parse_model_proposal(raw) == [
        {"path": "example.py", "content": "print(1)"}
    ]


def test_parse_model_proposal_accepts_list_of_changes():
    raw = json.dumps([{
        "path": "example.py",
        "content": "print(1)",
    }])
    assert parse_model_proposal(raw) == [{
        "path": "example.py",
        "content": "print(1)",
    }]


def test_parse_model_proposal_rejects_list_with_non_object():
    with pytest.raises(ValueError, match="Every proposed change"):
        parse_model_proposal('["not a change object"]')


def test_parse_model_proposal_rejects_missing_changes():
    with pytest.raises(ValueError, match="changes.*list"):
        parse_model_proposal('{"message": "no proposal"}')


def test_parse_model_proposal_rejects_non_list_changes():
    with pytest.raises(ValueError, match="changes.*list"):
        parse_model_proposal('{"changes": {}}')


def test_parse_model_proposal_rejects_malformed_json():
    with pytest.raises(json.JSONDecodeError):
        parse_model_proposal('{"changes": ')


def test_validate_patch_rejects_empty_patch(tmp_path):
    from scripts.vscode_repair import validate_patch

    with pytest.raises(ValueError, match="empty patch"):
        validate_patch(tmp_path, "")


def test_validate_patch_rejects_corrupt_patch(tmp_path):
    from scripts.vscode_repair import validate_patch

    with pytest.raises(ValueError, match="git apply --check"):
        validate_patch(tmp_path, "this is not a unified diff\n")


def test_validate_patch_accepts_valid_patch(tmp_path):
    import subprocess

    from scripts.vscode_repair import validate_patch

    subprocess.run(
        ["git", "init", "-q", str(tmp_path)],
        check=True,
    )
    target = tmp_path / "example.txt"
    target.write_text("before\n", encoding="utf-8")

    patch = (
        "--- a/example.txt\n"
        "+++ b/example.txt\n"
        "@@ -1 +1 @@\n"
        "-before\n"
        "+after\n"
    )

    validate_patch(tmp_path, patch)

    assert target.read_text(encoding="utf-8") == "before\n"


def test_build_patch_generates_valid_git_patch(tmp_path):
    import subprocess
    from scripts.vscode_repair import build_patch, validate_patch

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    target = tmp_path / "sample.py"
    target.write_text("value = 1\n", encoding="utf-8")

    originals = {"sample.py": "value = 1\n"}
    replacements = {"sample.py": "value = 2\n"}
    patch = build_patch(originals, replacements)

    assert patch.startswith("diff --git a/sample.py b/sample.py\n")
    assert "\n--- a/sample.py\n" in patch
    assert "\n+++ b/sample.py\n" in patch
    validate_patch(tmp_path, patch)

    subprocess.run(
        ["git", "apply", "--"],
        cwd=tmp_path,
        input=patch,
        text=True,
        capture_output=True,
        check=True,
    )
    assert target.read_text(encoding="utf-8") == "value = 2\n"


def test_build_patch_skips_unchanged_files():
    from scripts.vscode_repair import build_patch

    assert build_patch({"sample.py": "value = 1\n"},
                       {"sample.py": "value = 1\n"}) == ""





def test_safety_guard_rejects_unrequested_symbol_removal():
    from scripts.repair_test_retry import validate_patch_preserves_symbols

    patch = """diff --git a/scripts/vscode_repair.py b/scripts/vscode_repair.py
--- a/scripts/vscode_repair.py
+++ b/scripts/vscode_repair.py
@@ -1,2 +1 @@
-def validate_patch():
+def main():
"""
    with pytest.raises(ValueError, match="validate_patch"):
        validate_patch_preserves_symbols(
            patch,
            "Fix the automated repair workflow with minimal changes.",
        )


def test_safety_guard_allows_adding_a_function():
    from scripts.repair_test_retry import validate_patch_preserves_symbols

    patch = """diff --git a/example.py b/example.py
--- a/example.py
+++ b/example.py
@@ -1 +1,4 @@
 value = 1
+
+def new_function():
+    return 2
"""
    validate_patch_preserves_symbols(
        patch,
        "Add a helper function with minimal changes.",
    )


def test_safety_guard_allows_explicit_function_removal():
    from scripts.repair_test_retry import validate_patch_preserves_symbols

    patch = """diff --git a/example.py b/example.py
--- a/example.py
+++ b/example.py
@@ -1,3 +1 @@
-def obsolete_function():
-    return 1
-
 value = 2
"""
    validate_patch_preserves_symbols(
        patch,
        "Remove the obsolete function from example.py.",
    )

@pytest.mark.parametrize(
    ("old_content", "new_content"),
    [
        ("value = 1", "value = 2"),
        ("value = 1", "value = 2\\n"),
        ("value = 1\\n", "value = 2"),
        ("a = 1\\nb = 2\\n", "a = 1\\nb = 3\\n"),
    ],
)
def test_build_patch_handles_missing_final_newlines(
    tmp_path, old_content, new_content
):
    import subprocess
    from scripts.vscode_repair import build_patch, validate_patch

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    target = tmp_path / "sample.py"
    target.write_text(old_content, encoding="utf-8", newline="")

    patch = build_patch(
        {"sample.py": old_content},
        {"sample.py": new_content},
    )

    assert "-value = 1+value = 2" not in patch
    validate_patch(tmp_path, patch)
