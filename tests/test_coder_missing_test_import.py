from backend.agents.coder import CoderAgent


def make_agent(files):
    agent = object.__new__(CoderAgent)
    agent.inspect_project = lambda project_name: files
    return agent


def test_repairs_unambiguous_missing_import_in_test():
    files = {
        "RepairProject/main.py": (
            "def add(a, b):\n"
            "    return a + b\n"
        ),
        "RepairProject/test_main.py": (
            "import pytest\n"
            "\n"
            "def test_add():\n"
            "    assert add(2, 3) == 5\n"
        ),
    }
    agent = make_agent(files)

    result = agent._repair_missing_test_import(
        "RepairProject",
        {
            "return_code": 1,
            "test_result": {
                "stderr": (
                    "test_main.py:4: NameError: "
                    "name 'add' is not defined"
                ),
            },
        },
    )

    assert result is not None
    path, content = result
    assert path == "test_main.py"
    assert "from main import add" in content
    assert content.index("import pytest") < content.index("from main import add")
    assert content.index("from main import add") < content.index("def test_add")
    compile(content, path, "exec")


def test_does_not_repair_unrelated_assertion_failure():
    files = {
        "RepairProject/main.py": "def add(a, b):\n    return a + b\n",
        "RepairProject/test_main.py": "def test_add():\n    assert 1 == 2\n",
    }
    agent = make_agent(files)

    result = agent._repair_missing_test_import(
        "RepairProject",
        {
            "return_code": 1,
            "test_result": {
                "stderr": "test_main.py:2: AssertionError",
            },
        },
    )

    assert result is None


def test_does_not_repair_ambiguous_symbol():
    files = {
        "RepairProject/main.py": "def add(a, b):\n    return a + b\n",
        "RepairProject/helpers.py": "def add(a, b):\n    return a + b\n",
        "RepairProject/test_main.py": "def test_add():\n    assert add(2, 3) == 5\n",
    }
    agent = make_agent(files)

    result = agent._repair_missing_test_import(
        "RepairProject",
        {
            "return_code": 1,
            "test_result": {
                "stderr": (
                    "test_main.py:2: NameError: "
                    "name 'add' is not defined"
                ),
            },
        },
    )

    assert result is None


def test_preserves_docstring_and_future_import():
    files = {
        "RepairProject/main.py": "def add(a, b):\n    return a + b\n",
        "RepairProject/test_main.py": (
            '"""Test module."""\n'
            "from __future__ import annotations\n"
            "import pytest\n"
            "\n"
            "def test_add():\n"
            "    assert add(2, 3) == 5\n"
        ),
    }
    agent = make_agent(files)

    result = agent._repair_missing_test_import(
        "RepairProject",
        {
            "return_code": 1,
            "test_result": {
                "stderr": (
                    "test_main.py:6: NameError: "
                    "name 'add' is not defined"
                ),
            },
        },
    )

    assert result is not None
    _, content = result
    assert content.index('"""Test module."""') < content.index(
        "from __future__ import annotations"
    )
    assert content.index("from __future__ import annotations") < content.index(
        "from main import add"
    )
    assert content.index("import pytest") < content.index("from main import add")
    compile(content, "test_main.py", "exec")


def test_does_not_repair_non_test_file():
    files = {
        "RepairProject/main.py": (
            "def run():\n"
            "    return add(2, 3)\n"
        ),
        "RepairProject/helpers.py": "def add(a, b):\n    return a + b\n",
    }
    agent = make_agent(files)

    result = agent._repair_missing_test_import(
        "RepairProject",
        {
            "return_code": 1,
            "stderr": "main.py:2: NameError: name 'add' is not defined",
        },
    )

    assert result is None

def test_repairs_missing_import_in_nested_tests_directory():
    files = {
        "RepairProject/main.py": "def add(a, b):\n    return a + b\n",
        "RepairProject/tests/test_main.py": (
            "def test_add():\n"
            "    assert add(2, 3) == 5\n"
        ),
    }
    agent = make_agent(files)

    result = agent._repair_missing_test_import(
        "RepairProject",
        {
            "return_code": 1,
            "test_result": {
                "stderr": (
                    "tests/test_main.py:2: NameError: "
                    "name 'add' is not defined"
                ),
            },
        },
    )

    assert result is not None
    repaired_path, content = result
    assert repaired_path == "tests/test_main.py"
    assert "from main import add" in content
    compile(content, repaired_path, "exec")


def test_does_not_repair_ambiguous_nested_test_import():
    files = {
        "RepairProject/main.py": "def add(a, b):\n    return a + b\n",
        "RepairProject/helpers.py": "def add(a, b):\n    return a + b\n",
        "RepairProject/tests/test_main.py": (
            "def test_add():\n"
            "    assert add(2, 3) == 5\n"
        ),
    }
    agent = make_agent(files)

    result = agent._repair_missing_test_import(
        "RepairProject",
        {
            "return_code": 1,
            "test_result": {
                "stderr": (
                    "tests/test_main.py:2: NameError: "
                    "name 'add' is not defined"
                ),
            },
        },
    )

    assert result is None


def test_inspect_project_skips_cache_and_environment_directories():
    files = {
        "CacheProject/main.py": "print('hello')\n",
        "CacheProject/tests/test_main.py": "def test_main(): pass\n",
        "CacheProject/.pytest_cache/README.md": "cache data",
        "CacheProject/.pytest_cache/v/cache/nodeids": "[]",
        "CacheProject/tests/__pycache__/test_main.cpython-311.pyc": "binary",
        "CacheProject/.venv/lib/python3.11/site-packages/example.py": "package",
        "CacheProject/node_modules/example/index.js": "package",
    }

    class FakeWorkspace:
        def list_files(self):
            return list(files)

        def read_file(self, relative_path):
            return files[relative_path]

    agent = object.__new__(CoderAgent)
    agent.workspace = FakeWorkspace()

    result = agent.inspect_project("CacheProject")

    assert set(result) == {
        "CacheProject/main.py",
        "CacheProject/tests/test_main.py",
    }
