import re

from tsidpy import TSIDGenerator

TSID_BODY = r"[0-7][0-9A-HJKMNP-TV-Z]{12}"
TSID_PATTERN = re.compile(TSID_BODY)


def is_tsid(value: str) -> bool:
    return TSID_PATTERN.fullmatch(value) is not None


def require_tsid(value: str) -> str:
    if not is_tsid(value):
        raise ValueError("Expected a canonical 13-character TSID")
    return value


class TsidSource:
    def __init__(self, node: int = 0) -> None:
        if not 0 <= node <= 1023:
            raise ValueError("TSID node must be between 0 and 1023")
        self._generator = TSIDGenerator(node=node, node_bits=10)

    def next(self) -> str:
        return require_tsid(str(self._generator.create()))


new_tsid = TsidSource().next
