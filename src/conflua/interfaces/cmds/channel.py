import click

from conflua.interfaces.client import ConfluaClient
from conflua.interfaces.dto import ApiResult


@click.group("channel", no_args_is_help=False)
def channel_commands() -> None:
    """频道与工作目录。"""


@channel_commands.command("list")
@click.argument("room_id")
@click.pass_obj
def channel_list(client: ConfluaClient, room_id: str) -> ApiResult:
    return client.channel_list(room_id)


@channel_commands.command("create")
@click.argument("room_id")
@click.option("--name", required=True)
@click.option("--description", default="")
@click.option("--worktree/--no-worktree", default=False)
@click.pass_obj
def channel_create(
    client: ConfluaClient, room_id: str, name: str, description: str, worktree: bool
) -> ApiResult:
    return client.channel_create(room_id, name, worktree, description)


@channel_commands.command("get")
@click.argument("room_id")
@click.argument("channel_id")
@click.pass_obj
def channel_get(client: ConfluaClient, room_id: str, channel_id: str) -> ApiResult:
    return client.channel_get(room_id, channel_id)


@channel_commands.command("archive")
@click.argument("room_id")
@click.argument("channel_id")
@click.pass_obj
def channel_archive(client: ConfluaClient, room_id: str, channel_id: str) -> ApiResult:
    return client.channel_archive(room_id, channel_id)
