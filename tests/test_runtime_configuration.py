from pathlib import Path

from backend.agents.coder import CoderAgent
from backend.core.workspace import Workspace
from backend.llm.llama_cpp_client import LlamaCppClient


def test_llm_client_uses_default_configuration(monkeypatch):
    monkeypatch.delenv("LOCAL_AI_OFFICE_LLM_BASE_URL", raising=False)

    client = LlamaCppClient()

    assert client.model == "qwen3.5-4b"
    assert client.base_url == "http://127.0.0.1:8000"


def test_llm_client_uses_configured_base_url(monkeypatch):
    monkeypatch.setenv(
        "LOCAL_AI_OFFICE_LLM_BASE_URL",
        "http://127.0.0.1:9000/",
    )

    client = LlamaCppClient()

    assert client.base_url == "http://127.0.0.1:9000"


def test_llm_client_explicit_base_url_overrides_environment(monkeypatch):
    monkeypatch.setenv(
        "LOCAL_AI_OFFICE_LLM_BASE_URL",
        "http://127.0.0.1:9000",
    )

    client = LlamaCppClient(base_url="http://127.0.0.1:8000")

    assert client.base_url == "http://127.0.0.1:8000"


def test_coder_uses_configured_workspace(monkeypatch, tmp_path):
    workspace_path = tmp_path / "configured-workspace"
    monkeypatch.setenv(
        "LOCAL_AI_OFFICE_WORKSPACE",
        str(workspace_path),
    )

    agent = CoderAgent()

    assert isinstance(agent.workspace, Workspace)
    assert agent.workspace.root == workspace_path.resolve()


def test_coder_uses_repository_workspace_by_default(monkeypatch):
    monkeypatch.delenv("LOCAL_AI_OFFICE_WORKSPACE", raising=False)

    agent = CoderAgent()

    expected = Path(__file__).resolve().parents[1] / "workspace"

    assert agent.workspace.root == expected.resolve()


def test_frontend_static_directory_is_absolute():
    from backend.main import app

    office_route = next(
        route for route in app.routes
        if getattr(route, "name", None) == "office"
    )

    static_directory = Path(office_route.app.directory)

    assert static_directory.is_absolute()
    assert static_directory.is_dir()
    assert static_directory.name == "office"
    assert static_directory.parent.name == "frontend"


def test_artifact_manager_uses_configured_directory(monkeypatch, tmp_path):
    from backend.core.artifact_manager import ArtifactManager

    artifact_path = tmp_path / "configured-artifacts"
    monkeypatch.setenv(
        "LOCAL_AI_OFFICE_ARTIFACTS_DIR",
        str(artifact_path),
    )

    manager = ArtifactManager()

    assert manager.base_directory == artifact_path
    assert artifact_path.is_dir()


def test_artifact_manager_preserves_default_directory(monkeypatch, tmp_path):
    from backend.core.artifact_manager import ArtifactManager

    monkeypatch.delenv("LOCAL_AI_OFFICE_ARTIFACTS_DIR", raising=False)
    monkeypatch.chdir(tmp_path)

    manager = ArtifactManager()

    assert manager.base_directory == Path("data/generated")
    assert (tmp_path / "data" / "generated").is_dir()
