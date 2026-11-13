#!/usr/bin/env python3
"""Derive Agent Relay's version from Git history; preview changes by default.

Rules (x is fixed at 0):
  * y, z start at 0
  * a commit whose subject starts with "feat"  -> y += 1, z = 0
  * any other commit                           -> z += 1

``--no-dry-run`` updates ``pyproject.toml`` and the static runtime version in
``src/agent_relay/__init__.py``, then refreshes ``uv.lock``. The target defaults
to this script's repository, independently of the current working directory.
The About dialog uses this runtime version in source and packaged applications.

Usage:

    uv run --locked --no-sync python scripts/version-calc.py
    uv run --locked --no-sync python scripts/version-calc.py --no-dry-run
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

DEFAULT_TARGET = Path(__file__).resolve().parents[1]
PROJECT_VERSION_RE = re.compile(rb"^(\s*version\s*=\s*\")([^\"]+)(\")")
PACKAGE_VERSION_RE = re.compile(rb"^(\s*__version__\s*=\s*\")([^\"]+)(\")", re.MULTILINE)
COMMIT_FIELD_COUNT = 3


def write_output(message: str = "") -> None:
    """Write one user-facing line to standard output."""
    sys.stdout.write(f"{message}\n")


def resolve_target_dir(path: Path) -> Path:
    """Resolve a target directory to the root of its Git repository."""
    target = path.expanduser().resolve()
    if not target.is_dir():
        raise RuntimeError(f"target directory does not exist: {path}")

    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=target,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
    )
    repository = Path(completed.stdout.strip()).resolve()
    if not (repository / "pyproject.toml").is_file():
        raise RuntimeError(f"target repository has no pyproject.toml: {repository}")
    return repository


def run_git(repository: Path, *args: str) -> str:
    """Run Git in the target repository and return standard output."""
    completed = subprocess.run(
        ["git", *args],
        cwd=repository,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout


def run_uv(repository: Path, *args: str) -> None:
    """Run uv in the target repository, preserving its output for the caller."""
    subprocess.run(["uv", *args], cwd=repository, check=True)


def is_feature(subject: str) -> bool:
    """Return whether a commit subject advances the minor version."""
    return subject.lstrip().lower().startswith("feat")


def iter_commits(repository: Path) -> Iterator[tuple[str, str, str]]:
    """Yield (full_hash, ISO date, subject) from oldest to newest."""
    log = run_git(repository, "log", "--reverse", "--pretty=format:%H%x1f%aI%x1f%s")
    for line in log.splitlines():
        parts = line.split("\x1f", 2)
        if len(parts) == COMMIT_FIELD_COUNT:
            full_hash, date, subject = parts
            yield full_hash, date, subject


def calculate_version(repository: Path) -> str:
    """Walk Git history and return the calculated x.y.z version."""
    major = 0
    minor = 0
    patch = 0
    saw_commit = False

    for full_hash, date, subject in iter_commits(repository):
        saw_commit = True
        if is_feature(subject):
            minor += 1
            patch = 0
        else:
            patch += 1
        write_output(f"{date}  {full_hash[:8]}  {subject[:50]}  {major}.{minor}.{patch}")

    if not saw_commit:
        raise RuntimeError("no commits found; cannot derive version")

    return f"{major}.{minor}.{patch}"


def prepare_project_version_update(repository: Path, version: str) -> tuple[str, bytes]:
    """Return the current project version and an updated pyproject.toml body."""
    path = repository / "pyproject.toml"
    raw = path.read_bytes()
    in_project_table = False
    offset = 0
    match_offset: int | None = None
    match: re.Match[bytes] | None = None

    for line in raw.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith(b"[") and stripped.endswith(b"]"):
            in_project_table = stripped == b"[project]"
        elif in_project_table:
            candidate = PROJECT_VERSION_RE.match(line)
            if candidate is not None:
                if match is not None:
                    raise RuntimeError("found multiple version fields in [project]")
                match = candidate
                match_offset = offset
        offset += len(line)

    if match is None or match_offset is None:
        raise RuntimeError("could not find a static [project].version in pyproject.toml")

    previous = match.group(2).decode("utf-8")
    value_start = match_offset + match.start(2)
    value_end = match_offset + match.end(2)
    updated = raw[:value_start] + version.encode("utf-8") + raw[value_end:]
    return previous, updated


def package_version_files(repository: Path) -> tuple[Path, ...]:
    """Require the runtime version used by the API and desktop application."""
    path = repository / "src" / "agent_relay" / "__init__.py"
    if not path.is_file():
        raise RuntimeError(f"target repository has no Agent Relay package: {repository}")
    return (path,)


def prepare_package_version_update(
    path: Path, repository: Path, version: str
) -> tuple[str, bytes, bytes]:
    """Return the current package version, original body, and updated body."""
    original = path.read_bytes()
    matches = list(PACKAGE_VERSION_RE.finditer(original))
    if len(matches) != 1:
        relative_path = path.relative_to(repository)
        raise RuntimeError(f"expected one static __version__ in {relative_path}")
    match = matches[0]

    previous = match.group(2).decode("utf-8")
    value_start, value_end = match.span(2)
    updated = original[:value_start] + version.encode("utf-8") + original[value_end:]
    return previous, original, updated


def restore_version_files(
    repository: Path,
    pyproject: bytes,
    package_versions: dict[Path, bytes],
    lock: bytes,
) -> None:
    """Restore version metadata after an unsuccessful uv lock refresh."""
    (repository / "pyproject.toml").write_bytes(pyproject)
    for path, content in package_versions.items():
        path.write_bytes(content)
    (repository / "uv.lock").write_bytes(lock)


def apply_version(repository: Path, version: str) -> None:
    """Update package metadata and refresh uv.lock as one operation."""
    previous, updated_pyproject = prepare_project_version_update(repository, version)
    package_updates = {
        path: prepare_package_version_update(path, repository, version)
        for path in package_version_files(repository)
    }
    project_path = repository / "pyproject.toml"
    lock_path = repository / "uv.lock"
    original_pyproject = project_path.read_bytes()
    try:
        original_lock = lock_path.read_bytes()
    except OSError as error:
        raise RuntimeError("version application requires an existing uv.lock") from error

    try:
        if updated_pyproject != original_pyproject:
            project_path.write_bytes(updated_pyproject)
        for path, (_, original, updated) in package_updates.items():
            if updated != original:
                path.write_bytes(updated)
        run_uv(repository, "lock")
    except (OSError, RuntimeError, subprocess.CalledProcessError):
        original_package_versions = {
            path: original for path, (_, original, _) in package_updates.items()
        }
        restore_version_files(
            repository, original_pyproject, original_package_versions, original_lock
        )
        raise

    if previous == version:
        write_output(f"unchanged pyproject.toml -> project.version = {version!r}")
    else:
        write_output(f"updated pyproject.toml -> project.version {previous!r} -> {version!r}")
    for path, (previous_package, _, _) in package_updates.items():
        relative_path = path.relative_to(repository).as_posix()
        if previous_package == version:
            write_output(f"unchanged {relative_path} -> __version__ = {version!r}")
        else:
            write_output(
                f"updated {relative_path} -> __version__ {previous_package!r} -> {version!r}"
            )
    write_output("refreshed uv.lock")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Calculate Agent Relay's version; apply with --no-dry-run"
    )
    parser.add_argument(
        "target_dir",
        type=Path,
        nargs="?",
        default=DEFAULT_TARGET,
        metavar="TARGET_DIR",
        help="Agent Relay checkout to calculate (default: this script's repository)",
    )
    parser.add_argument(
        "--no-dry-run",
        dest="dry_run",
        action="store_false",
        help="write version metadata and refresh the target uv.lock",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the version calculation command."""
    args = parse_args(argv)
    repository = resolve_target_dir(args.target_dir)
    version = calculate_version(repository)
    write_output()
    write_output(f"version: {version}")
    if not args.dry_run:
        apply_version(repository, version)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except subprocess.CalledProcessError as error:
        sys.stderr.write(f"command failed: {error}\n")
        sys.exit(1)
    except (OSError, RuntimeError, ValueError, re.error) as error:
        sys.stderr.write(f"{error}\n")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
