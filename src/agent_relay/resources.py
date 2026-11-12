import sys
from pathlib import Path


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        extraction_root = Path(getattr(sys, "_MEIPASS", None) or Path(sys.executable).parent)
        return (extraction_root / "resources").resolve()
    return Path(__file__).resolve().parents[2]
