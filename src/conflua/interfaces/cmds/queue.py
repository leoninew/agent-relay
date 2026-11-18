import click

from conflua.interfaces.client import ConfluaClient
from conflua.interfaces.dto import ApiResult


@click.group("queue", no_args_is_help=False)
def queue_commands() -> None:
    """查询和清空当前有效消息队列。"""


@queue_commands.command("list", help="查询尚未完成投递的消息")
@click.argument("room_id")
@click.option("--topic-id")
@click.option("--member-id", help="筛选发送者或实际接收成员")
@click.option("--before-seq", type=click.IntRange(min=1))
@click.option("--limit", type=click.IntRange(1, 200), default=50, show_default=True)
@click.pass_obj
def queue_list(
    client: ConfluaClient,
    room_id: str,
    topic_id: str | None,
    member_id: str | None,
    before_seq: int | None,
    limit: int,
) -> ApiResult:
    return client.queue_list(room_id, topic_id, member_id, before_seq, limit)


@queue_commands.command("clear", help="清空范围内的 Conflua 队列，可选删除 Codex 等待项")
@click.argument("room_id")
@click.option("--topic-id")
@click.option("--member-id", help="筛选发送者或实际接收成员")
@click.option(
    "--clear-codex", is_flag=True, help="按 Conflua 回执删除 Codex 等待项，不中断当前轮次"
)
@click.pass_obj
def queue_clear(
    client: ConfluaClient,
    room_id: str,
    topic_id: str | None,
    member_id: str | None,
    clear_codex: bool,
) -> ApiResult:
    return client.queue_clear(room_id, topic_id, member_id, clear_codex=clear_codex)
