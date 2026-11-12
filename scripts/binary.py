import argparse
import os
import tomllib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def project_version() -> str:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    version = str(project["version"])
    if os.environ.get("GITHUB_REF_TYPE") == "tag":
        tag = os.environ.get("GITHUB_REF_NAME")
        if tag != f"v{version}":
            raise ValueError(f"Tag {tag!r} does not match project version v{version}")
    return version


def main() -> None:
    parser = argparse.ArgumentParser(description="Package the complete Windows binaries as a ZIP")
    parser.add_argument("--check-version", action="store_true")
    arguments = parser.parse_args()
    version = project_version()
    if arguments.check_version:
        print(version)
        return

    package = ROOT / "dist" / "AgentRelay"
    for relative in (
        "agent-relay-gui.exe",
        "agent-relay.exe",
        "_internal/resources/config/app.yaml",
        "_internal/resources/config/config.yaml",
        "_internal/resources/web/dist/index.html",
        "_internal/resources/alembic.ini",
        "_internal/resources/migrations/sqlite/env.py",
        "_internal/agent_relay/logging.yaml",
    ):
        if not (package / relative).is_file():
            raise FileNotFoundError(f"Incomplete desktop package: {relative}")
    artifact_name = f"agent-relay-{version}-windows-x64"
    archive = package.parent / f"{artifact_name}.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as output:
        for source in sorted(package.rglob("*")):
            if source.is_file():
                output.write(source, source.relative_to(package.parent))
    if output_path := os.environ.get("GITHUB_OUTPUT"):
        with Path(output_path).open("a", encoding="utf-8") as outputs:
            outputs.write(f"artifact_name={artifact_name}\narchive={archive.as_posix()}\n")
    print(archive)


if __name__ == "__main__":
    main()
