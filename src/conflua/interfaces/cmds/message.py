import click

from conflua.interfaces.client import ConfluaClient
from conflua.interfaces.cmds._options import validate_keyword
from conflua.interfaces.dto import ApiResult


@click.group("message", no_args_is_help=False)
def message_commands() -> None:
    """消息和发布。"""


@message_commands.command("list", help="查询消息页")
@click.argument("room_id")
@click.option("--topic-id")
@click.option("--member-id", help="筛选发送者或实际接收成员")
@click.option("--keyword", callback=validate_keyword, help="正文中的字面子串，最多 200 字符")
@click.option("--before-seq", type=click.IntRange(min=1))
@click.option("--limit", type=click.IntRange(1, 200), default=50, show_default=True)
@click.pass_obj
def message_list(
    client: ConfluaClient,
    room_id: str,
    topic_id: str | None,
    member_id: str | None,
    keyword: str | None,
    before_seq: int | None,
    limit: int,
) -> ApiResult:
    return client.message_list(room_id, topic_id, member_id, before_seq, limit, keyword=keyword)


@message_commands.command("get", help="查询单条消息")
@click.argument("room_id")
@click.argument("message_id")
@click.pass_obj
def message_get(client: ConfluaClient, room_id: str, message_id: str) -> ApiResult:
    return client.message_get(room_id, message_id)


@message_commands.command("publish", help="显式发布消息")
@click.argument("room_id")
@click.option("--publication-id", required=True)
@click.option("--content", required=True)
@click.option("--topic-id", multiple=True)
@click.option("--mention", multiple=True)
@click.option("--reply-to")
@click.option("--as-member", help="以此成员发布；省略时使用固定用户身份")
@click.pass_obj
def message_publish(
    client: ConfluaClient,
    room_id: str,
    publication_id: str,
    content: str,
    topic_id: tuple[str, ...],
    mention: tuple[str, ...],
    reply_to: str | None,
    as_member: str | None,
) -> ApiResult:
    return client.message_publish(
        room_id,
        publication_id,
        content,
        list(topic_id),
        list(mention),
        reply_to,
        as_member,
    )


@message_commands.command("publication", help="按稳定编号找回发布")
@click.argument("room_id")
@click.argument("publication_id")
@click.option("--as-member", help="使用发布时的成员身份找回；省略时查询固定用户发布")
@click.pass_obj
def publication_get(
    client: ConfluaClient, room_id: str, publication_id: str, as_member: str | None
) -> ApiResult:
    return client.publication_get(room_id, publication_id, as_member)
