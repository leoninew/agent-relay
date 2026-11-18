import click

from conflua.interfaces.client import ConfluaClient
from conflua.interfaces.dto import ApiResult


@click.group("topic", no_args_is_help=False)
def topic_commands() -> None:
    """话题。"""


@topic_commands.command("list", help="列出聊天室话题")
@click.argument("room_id")
@click.pass_obj
def topic_list(client: ConfluaClient, room_id: str) -> ApiResult:
    return client.topic_list(room_id)


@topic_commands.command("create", help="创建话题")
@click.argument("room_id")
@click.option("--name", required=True)
@click.option("--description", default="")
@click.pass_obj
def topic_create(client: ConfluaClient, room_id: str, name: str, description: str) -> ApiResult:
    return client.topic_create(room_id, name, description)


@topic_commands.command("update", help="更新话题")
@click.argument("room_id")
@click.argument("topic_id")
@click.option("--name", required=True)
@click.option("--description", required=True)
@click.pass_obj
def topic_update(
    client: ConfluaClient, room_id: str, topic_id: str, name: str, description: str
) -> ApiResult:
    return client.topic_update(room_id, topic_id, name, description)


@topic_commands.command("delete", help="删除话题")
@click.argument("room_id")
@click.argument("topic_id")
@click.pass_obj
def topic_delete(client: ConfluaClient, room_id: str, topic_id: str) -> ApiResult:
    return client.topic_delete(room_id, topic_id)
