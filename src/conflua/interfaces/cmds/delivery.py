import click

from conflua.interfaces.client import ConfluaClient
from conflua.interfaces.dto import ApiResult


@click.group("delivery", no_args_is_help=False)
def delivery_commands() -> None:
    """查询持久投递。"""


@delivery_commands.command("list", help="列出消息的历史投递（status 不代表当前队列）")
@click.argument("room_id")
@click.argument("message_id")
@click.option(
    "--status",
    type=click.Choice(("pending", "submitting", "queued", "received", "rejected", "unknown")),
)
@click.option("--member-id")
@click.pass_obj
def delivery_list(
    client: ConfluaClient,
    room_id: str,
    message_id: str,
    status: str | None,
    member_id: str | None,
) -> ApiResult:
    return client.delivery_list(room_id, message_id, status, member_id)


@delivery_commands.command("get", help="查询单条历史投递")
@click.argument("room_id")
@click.argument("message_id")
@click.argument("delivery_id")
@click.pass_obj
def delivery_get(
    client: ConfluaClient, room_id: str, message_id: str, delivery_id: str
) -> ApiResult:
    return client.delivery_get(room_id, message_id, delivery_id)
