import click

from conflua.interfaces.client import ConfluaClient
from conflua.interfaces.cmds._options import validate_keyword
from conflua.interfaces.dto import ApiResult


@click.group("room", no_args_is_help=False)
def room_commands() -> None:
    """聊天室。"""


@room_commands.command("list", help="列出聊天室")
@click.pass_obj
def room_list(client: ConfluaClient) -> ApiResult:
    return client.room_list()


@room_commands.command("create", help="创建聊天室")
@click.option("--name", required=True)
@click.option("--workspace-path", required=True)
@click.pass_obj
def room_create(client: ConfluaClient, name: str, workspace_path: str) -> ApiResult:
    return client.room_create(name, workspace_path)


@room_commands.command("get", help="读取聊天室和消息页")
@click.argument("room_id")
@click.option("--topic-id")
@click.option("--member-id", help="筛选发送者或实际接收成员")
@click.option("--keyword", callback=validate_keyword, help="正文中的字面子串，最多 200 字符")
@click.option("--before-seq", type=click.IntRange(min=1))
@click.option("--limit", type=click.IntRange(1, 200), default=50, show_default=True)
@click.pass_obj
def room_get(
    client: ConfluaClient,
    room_id: str,
    topic_id: str | None,
    member_id: str | None,
    keyword: str | None,
    before_seq: int | None,
    limit: int,
) -> ApiResult:
    return client.room_get(room_id, topic_id, member_id, before_seq, limit, keyword=keyword)


@room_commands.command("metadata", help="读取聊天室资源和统计")
@click.argument("room_id")
@click.pass_obj
def room_metadata(client: ConfluaClient, room_id: str) -> ApiResult:
    return client.room_metadata(room_id)


@room_commands.command("events", help="补取聊天室事件")
@click.argument("room_id")
@click.option("--after-event-id", type=int, default=0, show_default=True)
@click.option("--limit", type=click.IntRange(1, 200), default=200, show_default=True)
@click.pass_obj
def room_events(client: ConfluaClient, room_id: str, after_event_id: int, limit: int) -> ApiResult:
    return client.room_events(room_id, after_event_id, limit)
