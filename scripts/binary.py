import argparse
import os
import platform
import plistlib
import subprocess
import sys
import tomllib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from conflua import __version__

ROOT = Path(__file__).resolve().parents[1]


def project_version() -> str:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = str(project["version"])
    if __version__ != version:
        raise ValueError(
            f"Runtime version {__version__!r} does not match project version {version!r}; "
            "run scripts/version-calc.py --no-dry-run"
        )
    tag = os.environ.get("CI_COMMIT_TAG")
    if tag is None and os.environ.get("GITHUB_REF_TYPE") == "tag":
        tag = os.environ.get("GITHUB_REF_NAME")
    if tag is not None and tag != f"v{version}":
        raise ValueError(f"Tag {tag!r} does not match project version v{version}")
    return version


def package_target() -> tuple[str, str]:
    machine = platform.machine().lower()
    if sys.platform == "win32" and machine in {"amd64", "x86_64"}:
        return "windows", "x64"
    if sys.platform == "darwin" and machine in {"x86_64", "arm64"}:
        return "macos", "amd64" if machine == "x86_64" else "arm64"
    raise ValueError(f"Unsupported desktop build platform: {sys.platform}/{machine}")


def validate_package(package: Path, system: str, architecture: str, version: str) -> Path:
    is_macos = system == "macos"
    runtime = package / "Contents" / "Frameworks" if is_macos else package / "_internal"
    executables = package / "Contents" / "MacOS" if is_macos else package
    suffix = "" if is_macos else ".exe"
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
        if not (runtime / relative).is_file():
            raise FileNotFoundError(f"Incomplete desktop package: {relative}")

    for name in ("conflua-gui", "conflua"):
        executable = executables / f"{name}{suffix}"
        if not executable.is_file():
            raise FileNotFoundError(f"Incomplete desktop package: {executable}")
        if is_macos:
            if not os.access(executable, os.X_OK):
                raise ValueError(f"Not executable: {executable}")
            actual_arch = subprocess.check_output(
                ["/usr/bin/lipo", "-archs", str(executable)], text=True
            ).strip()
            expected_arch = "x86_64" if architecture == "amd64" else "arm64"
            if actual_arch != expected_arch:
                raise ValueError(f"Expected {expected_arch}, got {actual_arch}: {executable}")

    if is_macos:
        with (package / "Contents" / "Info.plist").open("rb") as source:
            info = plistlib.load(source)
        if (
            info.get("CFBundleExecutable") != "conflua-gui"
            or info.get("CFBundleShortVersionString") != version
            or info.get("CFBundleVersion") != version
            or info.get("LSBackgroundOnly", False)
        ):
            raise ValueError("Invalid desktop bundle metadata")
        icon_file = package / "Contents" / "Resources" / info["CFBundleIconFile"]
        if not icon_file.is_file():
            raise FileNotFoundError(f"Missing bundle icon: {icon_file}")

    return executables / f"conflua{suffix}"


def archive_package(package: Path, archive: Path, system: str) -> None:
    if system == "macos":
        subprocess.run(
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
        return
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as output:
        for source in sorted(package.rglob("*")):
            if source.is_file():
                output.write(source, source.relative_to(package.parent))


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate and package native desktop binaries")
    parser.add_argument("--check-version", action="store_true")
    arguments = parser.parse_args()
    version = project_version()
    if arguments.check_version:
        print(version)
        return

    system, architecture = package_target()
    package = ROOT / "dist" / ("Conflua.app" if system == "macos" else "conflua")
    executable = validate_package(package, system, architecture, version)
    subprocess.run([str(executable), "--help"], cwd=package.parent, check=True, timeout=30)
    artifact_name = f"conflua-{version}-{system}-{architecture}"
    archive = package.parent / f"{artifact_name}.zip"
    archive_package(package, archive, system)
    if output_path := os.environ.get("GITHUB_OUTPUT"):
        with Path(output_path).open("a", encoding="utf-8") as outputs:
            outputs.write(f"artifact_name={artifact_name}\narchive={archive.as_posix()}\n")
    print(archive)


if __name__ == "__main__":
    main()
