from __future__ import annotations

import json
import os
import sys
from collections.abc import Sequence
from typing import cast

import click

from agent_relay.client import ApiResult, RelayClient, RelayClientError, RequestOpener


@click.group(context_settings={"help_option_names": ["-h", "--help"]}, no_args_is_help=False)
@click.option(
    "--session-id",
    envvar="AGENT_RELAY_SESSION_ID",
    show_envvar=True,
    help="绑定 Codex 会话；CLI 默认读取执行环境的 CODEX_THREAD_ID",
)
@click.option(
    "--base-url",
    default="http://127.0.0.1:9080",
    envvar="AGENT_RELAY_URL",
    show_default=True,
    show_envvar=True,
    help="Relay 服务地址",
)
@click.option(
    "--timeout",
    type=click.FloatRange(min=0, min_open=True),
    default=10.0,
    envvar="AGENT_RELAY_HTTP_TIMEOUT",
    show_default=True,
    show_envvar=True,
    help="单次 HTTP 请求超时秒数",
)
@click.pass_context
def cli(context: click.Context, base_url: str, timeout: float, session_id: str | None) -> None:
    """通过 HTTP 管理本机 Relay 聊天室。"""
    if session_id is None and context.invoked_subcommand != "mcp":
        session_id = os.environ.get("CODEX_THREAD_ID")
    context.obj = RelayClient(
        base_url, timeout, opener=cast(RequestOpener | None, context.obj), session_id=session_id
    )


@cli.result_callback()
def emit_result(result: ApiResult | None, **_options: object) -> None:
    if result is not None:
        _emit_success(result)


@cli.command("mcp", help="启动 stdio MCP 服务，连接同一 Relay HTTP 服务")
@click.pass_obj
def mcp_server(client: RelayClient) -> None:
    from agent_relay.mcp_server import create_mcp_server

    create_mcp_server(client).run(transport="stdio")


@cli.group("room", no_args_is_help=False)
def room_commands() -> None:
    """聊天室。"""


@room_commands.command("list", help="列出聊天室")
@click.pass_obj
def room_list(client: RelayClient) -> ApiResult:
    return client.room_list()


@room_commands.command("create", help="创建聊天室")
@click.option("--name", required=True)
@click.option("--project-path", required=True)
@click.pass_obj
def room_create(client: RelayClient, name: str, project_path: str) -> ApiResult:
    return client.room_create(name, project_path)


@room_commands.command("get", help="读取聊天室及最新消息页")
@click.argument("room_id")
@click.option("--topic-id")
@click.option("--member-id", help="按发言成员筛选")
@click.option("--before-seq", type=int)
@click.option("--limit", type=click.IntRange(1, 200), default=50, show_default=True)
@click.pass_obj
def room_get(
    client: RelayClient,
    room_id: str,
    topic_id: str | None,
    member_id: str | None,
    before_seq: int | None,
    limit: int,
) -> ApiResult:
    return client.room_get(room_id, topic_id, member_id, before_seq, limit)


@room_commands.command("metadata", help="读取聊天室资源和统计")
@click.argument("room_id")
@click.pass_obj
def room_metadata(client: RelayClient, room_id: str) -> ApiResult:
    return client.room_metadata(room_id)


@room_commands.command("events", help="补取聊天室事件")
@click.argument("room_id")
@click.option("--after-event-id", type=int, default=0, show_default=True)
@click.option("--limit", type=click.IntRange(1, 200), default=200, show_default=True)
@click.pass_obj
def room_events(client: RelayClient, room_id: str, after_event_id: int, limit: int) -> ApiResult:
    return client.room_events(room_id, after_event_id, limit)


@cli.group("topic", no_args_is_help=False)
def topic_commands() -> None:
    """话题。"""


@topic_commands.command("list", help="列出聊天室话题")
@click.argument("room_id")
@click.pass_obj
def topic_list(client: RelayClient, room_id: str) -> ApiResult:
    return client.topic_list(room_id)


@topic_commands.command("create", help="创建话题")
@click.argument("room_id")
@click.option("--name", required=True)
@click.option("--description", default="")
@click.pass_obj
def topic_create(client: RelayClient, room_id: str, name: str, description: str) -> ApiResult:
    return client.topic_create(room_id, name, description)


@topic_commands.command("update", help="更新话题")
@click.argument("room_id")
@click.argument("topic_id")
@click.option("--name", required=True)
@click.option("--description", required=True)
@click.pass_obj
def topic_update(
    client: RelayClient, room_id: str, topic_id: str, name: str, description: str
) -> ApiResult:
    return client.topic_update(room_id, topic_id, name, description)


@topic_commands.command("delete", help="删除话题")
@click.argument("room_id")
@click.argument("topic_id")
@click.pass_obj
def topic_delete(client: RelayClient, room_id: str, topic_id: str) -> ApiResult:
    return client.topic_delete(room_id, topic_id)


@cli.group("member", no_args_is_help=False)
def member_commands() -> None:
    """成员和会话。"""


@member_commands.command("list", help="列出聊天室成员")
@click.argument("room_id")
@click.pass_obj
def member_list(client: RelayClient, room_id: str) -> ApiResult:
    return client.member_list(room_id)


@member_commands.command("sessions", help="列出项目目录内的 Codex 会话")
@click.argument("room_id")
@click.pass_obj
def member_sessions(client: RelayClient, room_id: str) -> ApiResult:
    return client.member_sessions(room_id)


@member_commands.command("add", help="添加已存在的会话为成员")
@click.argument("room_id")
@click.option("--session-id", required=True)
@click.option("--name", required=True)
@click.option("--topic-id", multiple=True, help="订阅话题，可重复；省略时不订阅话题")
@click.pass_obj
def member_add(
    client: RelayClient, room_id: str, session_id: str, name: str, topic_id: tuple[str, ...]
) -> ApiResult:
    return client.member_add(room_id, session_id, name, list(topic_id))


@member_commands.command("update", help="更新成员")
@click.argument("room_id")
@click.argument("member_id")
@click.option("--name", required=True)
@click.option("--topic-id", multiple=True, help="订阅话题，可重复；省略时清空订阅")
@click.pass_obj
def member_update(
    client: RelayClient, room_id: str, member_id: str, name: str, topic_id: tuple[str, ...]
) -> ApiResult:
    return client.member_update(room_id, member_id, name, list(topic_id))


@member_commands.command("delete", help="删除成员")
@click.argument("room_id")
@click.argument("member_id")
@click.pass_obj
def member_delete(client: RelayClient, room_id: str, member_id: str) -> ApiResult:
    return client.member_delete(room_id, member_id)


@member_commands.command("catalog", help="查看聊天室/项目、同伴、话题及自身订阅")
@click.argument("room_id")
@click.argument("member_id", required=False)
@click.pass_obj
def member_catalog(client: RelayClient, room_id: str, member_id: str | None) -> ApiResult:
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
    client: RelayClient,
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
def member_positions(client: RelayClient, room_id: str, member_id: str | None) -> ApiResult:
    return client.member_positions(room_id, member_id)


@cli.group("message", no_args_is_help=False)
def message_commands() -> None:
    """消息和发布。"""


@message_commands.command("list", help="查询消息页")
@click.argument("room_id")
@click.option("--topic-id")
@click.option("--member-id", help="按发言成员筛选")
@click.option("--before-seq", type=int)
@click.option("--limit", type=click.IntRange(1, 200), default=50, show_default=True)
@click.pass_obj
def message_list(
    client: RelayClient,
    room_id: str,
    topic_id: str | None,
    member_id: str | None,
    before_seq: int | None,
    limit: int,
) -> ApiResult:
    return client.message_list(room_id, topic_id, member_id, before_seq, limit)


@message_commands.command("get", help="查询单条消息")
@click.argument("room_id")
@click.argument("message_id")
@click.pass_obj
def message_get(client: RelayClient, room_id: str, message_id: str) -> ApiResult:
    return client.message_get(room_id, message_id)


@message_commands.command("publish", help="显式发布消息")
@click.argument("room_id")
@click.option("--publication-id", required=True)
@click.option("--content", required=True)
@click.option("--topic-id", multiple=True)
@click.option("--mention", multiple=True)
@click.option("--reply-to")
@click.option("--as-member", help="以此成员发布；省略时使用房间用户身份")
@click.pass_obj
def message_publish(
    client: RelayClient,
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
@click.option("--as-member", help="使用发布时的成员身份找回；省略时查询房间用户发布")
@click.pass_obj
def publication_get(
    client: RelayClient, room_id: str, publication_id: str, as_member: str | None
) -> ApiResult:
    return client.publication_get(room_id, publication_id, as_member)


@cli.group("delivery", no_args_is_help=False)
def delivery_commands() -> None:
    """查询持久投递。"""


@delivery_commands.command("list", help="列出消息的投递")
@click.argument("room_id")
@click.argument("message_id")
@click.option(
    "--status",
    type=click.Choice(("pending", "submitting", "queued", "received", "rejected", "unknown")),
)
@click.option("--member-id")
@click.pass_obj
def delivery_list(
    client: RelayClient,
    room_id: str,
    message_id: str,
    status: str | None,
    member_id: str | None,
) -> ApiResult:
    return client.delivery_list(room_id, message_id, status, member_id)


@delivery_commands.command("get", help="查询单条投递")
@click.argument("room_id")
@click.argument("message_id")
@click.argument("delivery_id")
@click.pass_obj
def delivery_get(client: RelayClient, room_id: str, message_id: str, delivery_id: str) -> ApiResult:
    return client.delivery_get(room_id, message_id, delivery_id)


def _emit_success(result: ApiResult) -> None:
    print(
        json.dumps(
            {"requestId": result.request_id, "data": result.data},
            ensure_ascii=False,
            indent=2,
        )
    )


def _emit_failure(failure: RelayClientError) -> None:
    print(
        json.dumps(
            {"requestId": failure.request_id, "error": failure.error},
            ensure_ascii=False,
            indent=2,
        ),
        file=sys.stderr,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    opener: RequestOpener | None = None,
) -> int:
    try:
        result = cli.main(
            args=list(argv) if argv is not None else None,
            prog_name="agent-relay",
            standalone_mode=False,
            obj=opener,
        )
        return result if isinstance(result, int) else 0
    except click.UsageError as failure:
        _emit_failure(RelayClientError(2, "invalid_arguments", failure.format_message()))
        return 2
    except click.Abort:
        _emit_failure(RelayClientError(130, "interrupted", "请求已中断"))
        return 130
    except RelayClientError as failure:
        _emit_failure(failure)
        return failure.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
