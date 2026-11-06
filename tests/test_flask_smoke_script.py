import subprocess
import sys

import pytest

from backend.agents.coder import FLASK_SMOKE_SCRIPT


def _run_smoke(project_dir):
    script = FLASK_SMOKE_SCRIPT.replace("__ENTRY__", repr("main.py")).replace(
        "__NOAPP__", repr("main.py must expose a Flask app named app")
    )
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_smoke_passes_for_healthy_flask_app(tmp_path):
    pytest.importorskip("flask")
    (tmp_path / "main.py").write_text(
        "from flask import Flask\n"
        "app = Flask(__name__)\n"
        "@app.route('/')\n"
        "def index():\n"
        "    return 'ok'\n"
        "@app.route('/item/<int:item_id>')\n"
        "def item(item_id):\n"
        "    return 1 / 0\n"  # parameterised routes are skipped
    )

    result = _run_smoke(tmp_path)

    assert result.returncode == 0, result.stderr
    assert "STARTUP_OK" in result.stdout


def test_smoke_fails_when_a_route_raises(tmp_path):
    pytest.importorskip("flask")
    (tmp_path / "main.py").write_text(
        "from flask import Flask\n"
        "app = Flask(__name__)\n"
        "@app.route('/boom')\n"
        "def boom():\n"
        "    return 1 / 0\n"
    )

    result = _run_smoke(tmp_path)

    assert result.returncode != 0
    assert "GET /boom" in result.stderr
    assert "ZeroDivisionError" in result.stderr


def test_smoke_fails_when_model_relationship_has_no_foreign_key(tmp_path):
    pytest.importorskip("flask_sqlalchemy")
    (tmp_path / "main.py").write_text(
        "from flask import Flask\n"
        "from flask_sqlalchemy import SQLAlchemy\n"
        "app = Flask(__name__)\n"
        "app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'\n"
        "db = SQLAlchemy(app)\n"
        "class User(db.Model):\n"
        "    id = db.Column(db.Integer, primary_key=True)\n"
        "    expenses = db.relationship('Expense', backref='user')\n"
        "class Expense(db.Model):\n"
        "    id = db.Column(db.Integer, primary_key=True)\n"
        "    user_id = db.Column(db.Integer)\n"
    )

    result = _run_smoke(tmp_path)

    assert result.returncode != 0
    assert "foreign key" in result.stderr.lower()
