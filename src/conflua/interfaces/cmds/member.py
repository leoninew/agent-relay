import click

from conflua.interfaces.client import ConfluaClient
from conflua.interfaces.dto import ApiResult


@click.group("member", no_args_is_help=False)
def member_commands() -> None:
    """成员和会话。"""


@member_commands.command("list", help="列出聊天室成员")
@click.argument("room_id")
@click.pass_obj
def member_list(client: ConfluaClient, room_id: str) -> ApiResult:
    return client.member_list(room_id)


@member_commands.command("sessions", help="列出项目目录内的 Codex 会话")
@click.argument("room_id")
@click.pass_obj
def member_sessions(client: ConfluaClient, room_id: str) -> ApiResult:
    return client.member_sessions(room_id)


@member_commands.command("add", help="添加已存在的会话为成员")
@click.argument("room_id")
@click.option("--session-id", required=True)
@click.option("--name", required=True)
@click.option("--topic-id", multiple=True, help="订阅话题，可重复；省略时不订阅话题")
@click.pass_obj
def member_add(
    client: ConfluaClient, room_id: str, session_id: str, name: str, topic_id: tuple[str, ...]
) -> ApiResult:
    return client.member_add(room_id, session_id, name, list(topic_id))


@member_commands.command("update", help="更新成员")
@click.argument("room_id")
@click.argument("member_id")
@click.option("--name", required=True)
@click.option("--topic-id", multiple=True, help="订阅话题，可重复；省略时清空订阅")
@click.pass_obj
def member_update(
    client: ConfluaClient, room_id: str, member_id: str, name: str, topic_id: tuple[str, ...]
) -> ApiResult:
    return client.member_update(room_id, member_id, name, list(topic_id))


@member_commands.command("delete", help="删除成员")
@click.argument("room_id")
@click.argument("member_id")
@click.pass_obj
def member_delete(client: ConfluaClient, room_id: str, member_id: str) -> ApiResult:
    return client.member_delete(room_id, member_id)


@member_commands.command("catalog", help="查看聊天室、同伴、话题及自身订阅")
@click.argument("room_id")
@click.argument("member_id", required=False)
@click.pass_obj
def member_catalog(client: ConfluaClient, room_id: str, member_id: str | None) -> ApiResult:
    return client.member_catalog(room_id, member_id)


@member_commands.command("context", help="查阅成员最近可见消息，可筛选；记录提供位置，不代表已读")
@click.argument("room_id")
@click.argument("member_id", required=False)
@click.option("--message-id", help="查单条消息，与其他筛选和游标互斥")
@click.option("--topic-id")
@click.option("--keyword", help="正文中的字面子串")
@click.option("--before-seq", type=click.IntRange(min=1))
@click.option("--after-seq", type=click.IntRange(min=0))
@click.option("--limit", type=click.IntRange(1, 200), default=50, show_default=True)
@click.pass_obj
def member_context(
    client: ConfluaClient,
    room_id: str,
    member_id: str | None,
    message_id: str | None,
    topic_id: str | None,
    keyword: str | None,
    before_seq: int | None,
    after_seq: int | None,
    limit: int,
) -> ApiResult:
    return client.member_context(
        room_id, member_id, message_id, topic_id, keyword, before_seq, after_seq, limit
    )


@member_commands.command("positions", help="查看成员话题查阅位置，不推进位置")
@click.argument("room_id")
@click.argument("member_id", required=False)
@click.pass_obj
def member_positions(client: ConfluaClient, room_id: str, member_id: str | None) -> ApiResult:
    return client.member_positions(room_id, member_id)
