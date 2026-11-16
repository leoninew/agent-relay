import re
from collections.abc import Iterator

_FENCE = re.compile(r"^ {0,3}(?:> ?)*(`{3,}|~{3,})([^\r\n]*)")


def inline_matches(content: str, pattern: re.Pattern[str]) -> Iterator[re.Match[str]]:
    """Find inline references without interpreting code or escaped examples."""
    fence: tuple[str, int] | None = None
    index = 0
    while index < len(content):
        if index == 0 or content[index - 1] == "\n":
            end = content.find("\n", index)
            line_end = len(content) if end < 0 else end + 1
            line = content[index:line_end]
            marker = _FENCE.match(line)
            if fence is not None:
                if (
                    marker is not None
                    and marker[1][0] == fence[0]
                    and len(marker[1]) >= fence[1]
                    and not marker[2].strip()
                ):
                    fence = None
                index = line_end
                continue
            if marker is not None and (marker[1][0] != "`" or "`" not in marker[2]):
                fence = (marker[1][0], len(marker[1]))
                index = line_end
                continue
            if line.startswith(("    ", "\t")):
                index = line_end
                continue
        if content[index] == "\\":
            index += 2
            continue
        if content[index] == "`":
            run_end = index + 1
            while run_end < len(content) and content[run_end] == "`":
                run_end += 1
            run = content[index:run_end]
            close = content.find(run, run_end)
            while close >= 0 and (
                content[close - 1] == "`" or content[close + len(run) : close + len(run) + 1] == "`"
            ):
                close = content.find(run, close + len(run))
            index = run_end if close < 0 else close + len(run)
            continue
        match = pattern.match(content, index)
        if match is not None:
            yield match
            index = match.end()
        else:
            index += 1
