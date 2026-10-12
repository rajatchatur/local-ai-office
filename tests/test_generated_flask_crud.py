import importlib.util
import sys
from pathlib import Path

import pytest
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.pool import StaticPool


PROJECT_DIR = (
    Path(__file__).resolve().parents[1]
    / "workspace"
    / "TaskManager"
)


@pytest.fixture
def task_app():
    # Load TaskManager with a separate module name.
    module_name = "task_manager_functional_test"
    spec = importlib.util.spec_from_file_location(
        module_name, PROJECT_DIR / "main.py"
    )
    module = importlib.util.module_from_spec(spec)

    # Patch SQLAlchemy before main.py creates its database tables.
    isolated_db = SQLAlchemy()
    module.SQLAlchemy = lambda app: isolated_db
    module.__dict__["__name__"] = module_name

    # Flask-SQLAlchemy reads the database configuration during init.
    module.app = None
    sys.modules[module_name] = module

    # Execute the app module in an isolated namespace, replacing the
    # database URL in the source before execution.
    source = (PROJECT_DIR / "main.py").read_text()
    source = source.replace(
        '"sqlite:///" + str(Path(__file__).resolve().parent / "tasks.db")',
        '"sqlite://"',
    )
    exec(compile(source, str(PROJECT_DIR / "main.py"), "exec"), module.__dict__)

    module.app.config.update(
        TESTING=True,
        SQLALCHEMY_ENGINE_OPTIONS={
            "poolclass": StaticPool,
            "connect_args": {"check_same_thread": False},
        },
    )

    with module.app.test_client() as client:
        yield module, client

    with module.app.app_context():
        module.db.session.remove()
        module.db.engine.dispose()
    sys.modules.pop(module_name, None)


def test_task_manager_crud(task_app):
    module, client = task_app

    response = client.get("/")
    assert response.status_code == 200
    assert b"Task Manager" in response.data

    response = client.post(
        "/add",
        data={"description": "Functional test task"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Functional test task" in response.data

    with module.app.app_context():
        task = module.Task.query.filter_by(
            description="Functional test task"
        ).one()
        task_id = task.id
        assert task.completed is False

    response = client.post(
        f"/complete/{task_id}", follow_redirects=True
    )
    assert response.status_code == 200

    with module.app.app_context():
        task = module.db.session.get(module.Task, task_id)
        assert task.completed is True

    response = client.get("/")
    assert b"Functional test task" in response.data
    assert b"Mark Incomplete" in response.data

    response = client.post(
        f"/delete/{task_id}", follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Functional test task" not in response.data

    with module.app.app_context():
        assert module.db.session.get(module.Task, task_id) is None
