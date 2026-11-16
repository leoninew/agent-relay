from pathlib import Path

from PyInstaller.compat import is_win
from PyInstaller.utils.hooks import copy_metadata

if not is_win:
    raise SystemExit("The desktop package must be built on Windows")

root = Path(SPECPATH).parent
app_icon = root / "assets" / "conflua.ico"
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
    hiddenimports=["webview", "webview.platforms.edgechromium", *runtime_imports],
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
)
console_exe = EXE(
    PYZ(console.pure),
    console.scripts,
    [],
    exclude_binaries=True,
    name="conflua",
    console=True,
    icon=str(app_icon),
)
COLLECT(
    desktop_exe,
    console_exe,
    desktop.binaries,
    desktop.datas,
    console.binaries,
    console.datas,
    name="conflua",
)
