import pytest

from scripts.repair_test_retry import validate_patch_preserves_symbols


def test_rejects_unrequested_function_removal():
    patch = """diff --git a/example.py b/example.py
--- a/example.py
+++ b/example.py
@@ -1,3 +1 @@
-def keep_me():
-    return 1
-
 value = 2
"""
    with pytest.raises(ValueError, match="keep_me"):
        validate_patch_preserves_symbols(
            patch, "Fix the bug with minimal changes."
        )


def test_allows_adding_a_function():
    patch = """diff --git a/example.py b/example.py
--- a/example.py
+++ b/example.py
@@ -1 +1,4 @@
 value = 1
+
+def added_helper():
+    return 2
"""
    validate_patch_preserves_symbols(patch, "Add a helper function.")


def test_rejects_unrequested_import_removal():
    patch = """diff --git a/example.py b/example.py
--- a/example.py
+++ b/example.py
@@ -1,2 +1 @@
-import json
 value = 1
"""
    with pytest.raises(ValueError, match="imports"):
        validate_patch_preserves_symbols(
            patch, "Fix the bug with minimal changes."
        )
