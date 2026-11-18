from __future__ import annotations

import json
import os
import sys
from collections.abc import Sequence
from typing import cast

import click

from conflua.interfaces.client import ConfluaClient, ConfluaClientError, RequestOpener
from conflua.interfaces.cmds.channel import channel_commands
from conflua.interfaces.cmds.codex import codex_commands
from conflua.interfaces.cmds.delivery import delivery_commands
from conflua.interfaces.cmds.mcp import mcp_server
from conflua.interfaces.cmds.member import member_commands
from conflua.interfaces.cmds.message import message_commands
from conflua.interfaces.cmds.queue import queue_commands
from conflua.interfaces.cmds.room import room_commands
from conflua.interfaces.cmds.topic import topic_commands
from conflua.interfaces.dto import ApiResult


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    commands=[
        mcp_server,
        codex_commands,
        room_commands,
        channel_commands,
        topic_commands,
        member_commands,
        message_commands,
        queue_commands,
        delivery_commands,
    ],
)
@click.option(
    "--channel-id",
    envvar="CONFLUA_CHANNEL_ID",
    help="频道 ID；频道资源操作必须指定",
)
@click.option(
    "--session-id",
    envvar="CONFLUA_SESSION_ID",
    show_envvar=True,
    help="绑定 Codex 会话；CLI 默认读取执行环境的 CODEX_THREAD_ID",
)
@click.option(
    "--base-url",
    default="http://127.0.0.1:9081",
    envvar="CONFLUA_URL",
    show_default=True,
    show_envvar=True,
    help="Conflua 服务地址",
)
@click.option(
    "--timeout",
    type=click.FloatRange(min=0, min_open=True),
    default=10.0,
    envvar="CONFLUA_HTTP_TIMEOUT",
    show_default=True,
    show_envvar=True,
    help="单次 HTTP 请求超时秒数",
)
@click.pass_context
def cli(
    context: click.Context,
    base_url: str,
    timeout: float,
    session_id: str | None,
    channel_id: str | None,
) -> None:
    """管理 Conflua 聊天室和查询本机 Codex 会话。"""
    if context.invoked_subcommand == "codex":
        return
    if session_id is None and context.invoked_subcommand != "mcp":
        session_id = os.environ.get("CODEX_THREAD_ID")
    context.obj = ConfluaClient(
        base_url,
        timeout,
        opener=cast(RequestOpener | None, context.obj),
        session_id=session_id,
        channel_id=channel_id,
    )


@cli.result_callback()
def emit_result(result: ApiResult | None, **_options: object) -> None:
    if result is not None:
        _emit_success(result)


def _emit_success(result: ApiResult) -> None:
    print(
        json.dumps(
            {"requestId": result.request_id, "data": result.data},
            ensure_ascii=False,
            indent=2,
        )
    )


def _emit_failure(failure: ConfluaClientError) -> None:
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
    arguments = list(argv) if argv is not None else None
    try:
        result = cli.main(
            args=arguments,
            prog_name="conflua",
            standalone_mode=False,
            obj=opener,
        )
        return result if isinstance(result, int) else 0
    except click.UsageError as failure:
        if not (sys.argv[1:] if arguments is None else arguments):
            failure.show()
            return failure.exit_code
        _emit_failure(ConfluaClientError(2, "invalid_arguments", failure.format_message()))
        return 2
    except click.Abort:
        _emit_failure(ConfluaClientError(130, "interrupted", "请求已中断"))
        return 130
    except ConfluaClientError as failure:
        _emit_failure(failure)
        return failure.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
