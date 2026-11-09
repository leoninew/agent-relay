import sys
from pathlib import Path
from typing import BinaryIO


class SubmitterLock:
    def __init__(self, path: Path) -> None:
        self.path = path.with_suffix(path.suffix + ".dispatch.lock")
        self.file: BinaryIO | None = None

    def acquire(self) -> bool:
        stream = self.path.open("a+b")
        try:
            if sys.platform == "win32":
                import msvcrt

                if self.path.stat().st_size == 0:
                    stream.write(b"\0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            stream.close()
            return False
        self.file = stream
        return True

    def release(self) -> None:
        if self.file is not None:
            self.file.close()
            self.file = None
