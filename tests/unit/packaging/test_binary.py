import plistlib
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
from pytest import MonkeyPatch


@pytest.fixture
def binary() -> ModuleType:
    script = Path(__file__).resolve().parents[3] / "scripts" / "binary.py"
    spec = spec_from_file_location("conflua_binary", script)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [
        ("win32", "AMD64", ("windows", "x64")),
        ("win32", "x86_64", ("windows", "x64")),
        ("darwin", "x86_64", ("macos", "amd64")),
        ("darwin", "arm64", ("macos", "arm64")),
    ],
)
def test_package_target(
    binary: ModuleType,
    monkeypatch: MonkeyPatch,
    system: str,
    machine: str,
    expected: tuple[str, str],
) -> None:
    monkeypatch.setattr(binary.sys, "platform", system)
    monkeypatch.setattr(binary.platform, "machine", lambda: machine)

    assert binary.package_target() == expected


@pytest.mark.parametrize(("system", "machine"), [("linux", "x86_64"), ("win32", "ARM64")])
def test_package_target_rejects_unsupported_platforms(
    binary: ModuleType, monkeypatch: MonkeyPatch, system: str, machine: str
) -> None:
    monkeypatch.setattr(binary.sys, "platform", system)
    monkeypatch.setattr(binary.platform, "machine", lambda: machine)

    with pytest.raises(ValueError, match="Unsupported desktop build platform"):
        binary.package_target()


def create_package(root: Path, system: str) -> Path:
    is_macos = system == "macos"
    package = root / ("Conflua.app" if is_macos else "conflua")
    runtime = package / "Contents" / "Frameworks" if is_macos else package / "_internal"
    icon = "conflua.png" if is_macos else "conflua.ico"
    for relative in (
        f"resources/assets/{icon}",
        "resources/config/conflua.yaml",
        "resources/config/config.yaml",
        "resources/web/dist/index.html",
        "resources/web/dist/conflua.png",
        "resources/alembic.ini",
        "resources/migrations/sqlite/env.py",
        "conflua/logging.yaml",
        "webview/js/api.js",
    ):
        target = runtime / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
    executables = package / "Contents" / "MacOS" if is_macos else package
    executables.mkdir(parents=True, exist_ok=True)
    for name in ("conflua-gui", "conflua"):
        executable = executables / (name if is_macos else f"{name}.exe")
        executable.touch()
        executable.chmod(0o755)
    if is_macos:
        resources = package / "Contents" / "Resources"
        resources.mkdir()
        (resources / "conflua.icns").touch()
        with (package / "Contents" / "Info.plist").open("wb") as output:
            plistlib.dump(
                {
                    "CFBundleExecutable": "conflua-gui",
                    "CFBundleShortVersionString": "0.48.2",
                    "CFBundleVersion": "0.48.2",
                    "CFBundleIconFile": "conflua.icns",
                    "LSBackgroundOnly": False,
                },
                output,
            )
    return package


@pytest.mark.parametrize(
    ("system", "architecture", "machine"),
    [("macos", "amd64", "x86_64"), ("macos", "arm64", "arm64"), ("windows", "x64", "")],
)
def test_validate_package(
    binary: ModuleType,
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
    system: str,
    architecture: str,
    machine: str,
) -> None:
    package = create_package(tmp_path, system)
    inspect_arch = Mock(return_value=f"{machine}\n")
    monkeypatch.setattr(binary.subprocess, "check_output", inspect_arch)

    executable = binary.validate_package(package, system, architecture, "0.48.2")

    assert executable.name == ("conflua" if system == "macos" else "conflua.exe")
    assert inspect_arch.call_count == (2 if system == "macos" else 0)


def test_validate_package_rejects_wrong_macos_architecture(
    binary: ModuleType, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    package = create_package(tmp_path, "macos")
    monkeypatch.setattr(binary.subprocess, "check_output", Mock(return_value="arm64\n"))

    with pytest.raises(ValueError, match="Expected x86_64, got arm64"):
        binary.validate_package(package, "macos", "amd64", "0.48.2")


def test_validate_package_rejects_missing_resources(binary: ModuleType, tmp_path: Path) -> None:
    package = create_package(tmp_path, "windows")
    (package / "_internal" / "resources" / "web" / "dist" / "index.html").unlink()

    with pytest.raises(FileNotFoundError, match="resources/web/dist/index.html"):
        binary.validate_package(package, "windows", "x64", "0.48.2")


def test_validate_package_rejects_wrong_bundle_version(
    binary: ModuleType, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    package = create_package(tmp_path, "macos")
    monkeypatch.setattr(binary.subprocess, "check_output", Mock(return_value="arm64\n"))

    with pytest.raises(ValueError, match="Invalid desktop bundle metadata"):
        binary.validate_package(package, "macos", "arm64", "0.48.3")


def test_macos_archive_uses_ditto(
    binary: ModuleType, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    package = tmp_path / "Conflua.app"
    archive = tmp_path / "conflua-macos-arm64.zip"
    run = Mock()
    monkeypatch.setattr(binary.subprocess, "run", run)

    binary.archive_package(package, archive, "macos")

    run.assert_called_once_with(
        [
            "/usr/bin/ditto",
            "-c",
            "-k",
            "--sequesterRsrc",
            "--keepParent",
            str(package),
            str(archive),
        ],
        check=True,
    )


def test_windows_archive_keeps_directory_layout(binary: ModuleType, tmp_path: Path) -> None:
    package = create_package(tmp_path, "windows")
    archive = tmp_path / "conflua-windows-x64.zip"

    binary.archive_package(package, archive, "windows")

    with ZipFile(archive) as output:
        assert "conflua/conflua.exe" in output.namelist()
        assert "conflua/_internal/resources/web/dist/index.html" in output.namelist()
