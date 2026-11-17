import platform
import tomllib
from pathlib import Path

from PyInstaller.compat import is_darwin, is_win
from PyInstaller.utils.hooks import copy_metadata

machine = platform.machine().lower()
if not (is_win and machine in {"amd64", "x86_64"}) and not (
    is_darwin and machine in {"x86_64", "arm64"}
):
    raise SystemExit("Build on Windows x64 or macOS with an x86_64/arm64 Python interpreter")

root = Path(SPECPATH).parent
app_icon = root / "assets" / ("conflua.png" if is_darwin else "conflua.ico")
target_arch = machine if is_darwin else None
runtime_imports = [
    "uvicorn.loops.asyncio",
    "conflua.infrastructure.persistence.migration_sql",
]
resources = [
    (str(app_icon), "resources/assets"),
    (str(root / "config" / "config.yaml"), "resources/config"),
    (str(root / "config" / "conflua.yaml"), "resources/config"),
    (str(root / "alembic.ini"), "resources"),
    (str(root / "migrations" / "sqlite"), "resources/migrations/sqlite"),
    (str(root / "web" / "dist"), "resources/web/dist"),
    (str(root / "src" / "conflua" / "logging.yaml"), "conflua"),
    *copy_metadata("conflua"),
]

desktop = Analysis(
    [str(root / "src" / "conflua" / "desktop.py")],
    pathex=[str(root / "src")],
    datas=resources,
    hiddenimports=[
        "webview",
        "webview.platforms.cocoa" if is_darwin else "webview.platforms.edgechromium",
        *runtime_imports,
    ],
    excludes=["tkinter", "PyQt5", "PyQt6", "PySide2", "PySide6"],
)
console = Analysis(
    [str(root / "src" / "conflua" / "cli.py")],
    pathex=[str(root / "src")],
    datas=resources,
)

desktop_exe = EXE(
    PYZ(desktop.pure),
    desktop.scripts,
    [],
    exclude_binaries=True,
    name="conflua-gui",
    console=False,
    icon=str(app_icon),
    target_arch=target_arch,
)
console_exe = EXE(
    PYZ(console.pure),
    console.scripts,
    [],
    exclude_binaries=True,
    name="conflua",
    console=True,
    icon=str(app_icon),
    target_arch=target_arch,
)
contents = (
    desktop_exe, console_exe, desktop.binaries, desktop.datas, console.binaries, console.datas
)
if is_darwin:
    version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    BUNDLE(
        *contents,
        name="Conflua.app",
        icon=str(app_icon),
        bundle_identifier="io.github.leoninew.conflua",
        version=version,
        info_plist={
            "CFBundleVersion": version,
            "LSBackgroundOnly": False,
            "NSHighResolutionCapable": True,
            "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
        },
    )
else:
    COLLECT(*contents, name="conflua")
