from pathlib import Path

from backend.core.artifact_manager import ArtifactManager


def test_artifact_manager_uses_existing_default(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("LOCAL_AI_OFFICE_ARTIFACTS_DIR", raising=False)

    manager = ArtifactManager()

    assert manager.base_directory == Path("data/generated")
    assert (tmp_path / "data" / "generated").is_dir()


def test_artifact_manager_uses_configured_directory(
    monkeypatch, tmp_path
):
    configured = tmp_path / "configured-artifacts"
    monkeypatch.setenv(
        "LOCAL_AI_OFFICE_ARTIFACTS_DIR",
        str(configured),
    )

    manager = ArtifactManager()

    assert manager.base_directory == configured
    assert configured.is_dir()


def test_explicit_artifact_directory_overrides_environment(
    monkeypatch, tmp_path
):
    configured = tmp_path / "environment-artifacts"
    explicit = tmp_path / "explicit-artifacts"
    monkeypatch.setenv(
        "LOCAL_AI_OFFICE_ARTIFACTS_DIR",
        str(configured),
    )

    manager = ArtifactManager(base_directory=str(explicit))

    assert manager.base_directory == explicit
    assert explicit.is_dir()
    assert not configured.exists()
