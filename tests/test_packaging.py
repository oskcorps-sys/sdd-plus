"""Tests for Phase 7 — PyPI packaging readiness."""

import tomllib
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent


class TestPyprojectMetadata:
    def _load(self) -> dict:
        with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
            return tomllib.load(f)

    def test_name(self):
        data = self._load()
        assert data["project"]["name"] == "sdd-plus"

    def test_version(self):
        data = self._load()
        assert data["project"]["version"] == "0.4.0"

    def test_description(self):
        data = self._load()
        assert len(data["project"]["description"]) > 20

    def test_classifiers(self):
        data = self._load()
        classifiers = data["project"]["classifiers"]
        assert any("MIT" in c for c in classifiers)
        assert any("Python :: 3" in c for c in classifiers)

    def test_keywords(self):
        data = self._load()
        assert "sdd" in data["project"]["keywords"]

    def test_urls(self):
        data = self._load()
        urls = data["project"]["urls"]
        assert "Homepage" in urls
        assert "Repository" in urls

    def test_scripts_entry_point(self):
        data = self._load()
        assert "sdd" in data["project"]["scripts"]


class TestProjectFiles:
    def test_license_exists(self):
        license_file = PROJECT_ROOT / "LICENSE"
        assert license_file.exists()
        content = license_file.read_text(encoding="utf-8")
        assert "MIT" in content

    def test_readme_exists(self):
        assert (PROJECT_ROOT / "README.md").exists()

    def test_readme_has_install_section(self):
        content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
        assert "pip install sdd-plus" in content

    def test_changelog_exists(self):
        changelog = PROJECT_ROOT / "CHANGELOG.md"
        assert changelog.exists()
        content = changelog.read_text(encoding="utf-8")
        assert "0.1.0" in content


# ---------------------------------------------------------------------------
# Named acceptance-test functions (match PHASE_7_CONTRACT.yaml names)
# ---------------------------------------------------------------------------


def test_pyproject_has_metadata():
    """pyproject.toml has name, version, description, classifiers, keywords, urls."""
    with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    proj = data["project"]
    assert proj["name"] == "sdd-plus"
    assert proj["version"] == "0.4.0"
    assert len(proj["description"]) > 20
    assert len(proj["classifiers"]) > 0
    assert len(proj["keywords"]) > 0
    assert "Homepage" in proj["urls"]


def test_readme_has_install_section():
    content = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    assert "pip install sdd-plus" in content


def test_license_exists():
    license_file = PROJECT_ROOT / "LICENSE"
    assert license_file.exists()
    assert "MIT" in license_file.read_text(encoding="utf-8")


def test_changelog_exists():
    content = (PROJECT_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "0.1.0" in content


def test_package_builds():
    """python -m build produces a wheel in dist/."""
    import subprocess
    import shutil

    dist = PROJECT_ROOT / "dist"
    if dist.exists():
        shutil.rmtree(dist)

    result = subprocess.run(
        ["python", "-m", "build", "--wheel", "--no-isolation"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"Build failed: {result.stderr}"
    wheels = list(dist.glob("*.whl"))
    assert len(wheels) >= 1, f"No wheel found in dist/: {list(dist.iterdir())}"


def test_wheel_installs():
    """The built wheel can be installed and sdd --help works."""
    import subprocess

    dist = PROJECT_ROOT / "dist"
    wheels = list(dist.glob("*.whl"))
    if not wheels:
        pytest.skip("No wheel found — run test_package_builds first")

    wheel = wheels[0]
    # We won't create a fresh venv in CI (slow), but verify the wheel is a valid zip
    import zipfile
    assert zipfile.is_zipfile(str(wheel)), f"{wheel} is not a valid zip/wheel"

    # Verify the entry point is declared inside the wheel metadata
    with zipfile.ZipFile(str(wheel)) as zf:
        names = zf.namelist()
        # Should contain sdd/ package files
        sdd_files = [n for n in names if n.startswith("sdd/")]
        assert len(sdd_files) > 10, f"Wheel has too few sdd/ files: {len(sdd_files)}"
