import click


def validate_keyword(
    _context: click.Context, _parameter: click.Parameter, value: str | None
) -> str | None:
    if value is not None and len(value) > 200:
        raise click.BadParameter("最多 200 字符")
    return value
