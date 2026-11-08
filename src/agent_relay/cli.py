from __future__ import annotations

import json
import math
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from http.client import HTTPException
from typing import Any, NoReturn, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import click


class HttpResponse(Protocol):
    status: int
    headers: Mapping[str, str]

    def read(self) -> bytes: ...
    def close(self) -> None: ...


class RequestOpener(Protocol):
    def __call__(self, request: Request, *, timeout: float) -> HttpResponse: ...


@dataclass(frozen=True)
class ApiResult:
    data: object
    request_id: str | None


class CliFailure(Exception):
    def __init__(
        self,
        exit_code: int,
        code: str,
        message: str,
        *,
        request_id: str | None = None,
        http_status: int | None = None,
        outcome: str | None = None,
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.request_id = request_id
        self.error: dict[str, object] = {"code": code, "message": message}
        if http_status is not None:
            self.error["httpStatus"] = http_status
        if outcome is not None:
            self.error["outcome"] = outcome


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


class RelayHttpClient:
    def __init__(
        self,
        base_url: str,
        timeout: float,
        *,
        opener: RequestOpener | None = None,
    ) -> None:
        try:
            parsed = urlsplit(base_url)
            host = parsed.hostname
            _ = parsed.port
            has_credentials = parsed.username is not None or parsed.password is not None
        except ValueError as exc:
            raise CliFailure(2, "invalid_base_url", "服务地址格式无效") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not host
            or has_credentials
            or parsed.query
            or parsed.fragment
        ):
            raise CliFailure(2, "invalid_base_url", "服务地址只能包含 HTTP(S) scheme、主机和路径")
        if not math.isfinite(timeout) or timeout <= 0:
            raise CliFailure(2, "invalid_timeout", "HTTP 超时必须为大于 0 的有限数值")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.opener = opener or cast(RequestOpener, build_opener(NoRedirectHandler()).open)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int | None] | None = None,
        body: Mapping[str, object] | None = None,
    ) -> ApiResult:
        query = urlencode(
            [(key, value) for key, value in (params or {}).items() if value is not None]
        )
        url = f"{self.base_url}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{query}"
        encoded_body = (
            json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
        )
        headers = {"Accept": "application/json"}
        if encoded_body is not None:
            headers["Content-Type"] = "application/json"
        request = Request(url, data=encoded_body, headers=headers, method=method)
        is_write = method.upper() not in {"GET", "HEAD", "OPTIONS"}
        request_id = None

        try:
            try:
                response = self.opener(request, timeout=self.timeout)
            except HTTPError as exc:
                response = cast(HttpResponse, exc)
            try:
                status = response.status
                request_id = _header(response.headers, "X-Request-Id")
                response_body = response.read()
            finally:
                response.close()
        except KeyboardInterrupt as exc:
            raise CliFailure(
                130,
                "interrupted",
                "请求已中断；写入结果请先查询服务记录" if is_write else "请求已中断",
                request_id=request_id,
                outcome="unknown" if is_write else None,
            ) from exc
        except (URLError, OSError, HTTPException) as exc:
            raise CliFailure(
                5,
                "transport_error",
                "无法取得 Relay HTTP 响应；写入结果请先查询服务记录"
                if is_write
                else "无法取得 Relay HTTP 响应，请检查服务地址和运行状态",
                request_id=request_id,
                outcome="unknown" if is_write else None,
            ) from exc

        if not 200 <= status < 300:
            self._raise_http_error(status, response_body, request_id, is_write)
        try:
            data = _decode_json(response_body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CliFailure(
                4,
                "invalid_response",
                "Relay 返回的响应不是有效 JSON",
                request_id=request_id,
                http_status=status,
                outcome="unknown" if is_write else None,
            ) from exc
        return ApiResult(data, request_id)

    @staticmethod
    def _raise_http_error(
        status: int,
        response_body: bytes,
        header_request_id: str | None,
        is_write: bool,
    ) -> NoReturn:
        try:
            payload = _decode_json(response_body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        error = payload if isinstance(payload, dict) else {}
        request_id = header_request_id
        api_code = _string(error.get("code"))
        message = _string(error.get("error"))
        body_request_id = _string(error.get("requestId"))
        if not (api_code and message and body_request_id):
            api_code = "invalid_response"
            message = f"Relay 返回 HTTP {status}，错误响应不符合约定"
        else:
            request_id = body_request_id
        rejected = 400 <= status < 500
        raise CliFailure(
            3 if rejected else 4,
            api_code,
            message,
            request_id=request_id,
            http_status=status,
            outcome=("rejected" if rejected else "unknown") if is_write else None,
        )


def _segment(value: str) -> str:
    return quote(value, safe="")


def _room_path(room_id: str) -> str:
    return f"/api/room/{_segment(room_id)}"


def _result_from_field(result: ApiResult, field: str) -> ApiResult:
    return ApiResult(_rows(result, field), result.request_id)


@click.group(context_settings={"help_option_names": ["-h", "--help"]}, no_args_is_help=False)
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
def cli(context: click.Context, base_url: str, timeout: float) -> None:
    """通过 HTTP 管理本机 Relay 聊天室。"""
    context.obj = RelayHttpClient(base_url, timeout, opener=cast(RequestOpener | None, context.obj))


@cli.result_callback()
def emit_result(result: ApiResult, **_options: object) -> None:
    _emit_success(result)


@cli.group("room", no_args_is_help=False)
def room_commands() -> None:
    """聊天室。"""


@room_commands.command("list", help="列出聊天室")
@click.pass_obj
def room_list(client: RelayHttpClient) -> ApiResult:
    return client.request("GET", "/api/room")


@room_commands.command("create", help="创建聊天室")
@click.option("--name", required=True)
@click.option("--project-path", required=True)
@click.pass_obj
def room_create(client: RelayHttpClient, name: str, project_path: str) -> ApiResult:
    return client.request("POST", "/api/room", body={"name": name, "projectPath": project_path})


@room_commands.command("get", help="读取聊天室及最新消息页")
@click.argument("room_id")
@click.option("--topic-id")
@click.option("--member-id", help="按发言成员筛选")
@click.option("--before-seq", type=int)
@click.option("--limit", type=click.IntRange(1, 200), default=50, show_default=True)
@click.pass_obj
def room_get(
    client: RelayHttpClient,
    room_id: str,
    topic_id: str | None,
    member_id: str | None,
    before_seq: int | None,
    limit: int,
) -> ApiResult:
    return client.request(
        "GET",
        _room_path(room_id),
        params={
            "topic_id": topic_id,
            "member_id": member_id,
            "before_seq": before_seq,
            "limit": limit,
        },
    )


@room_commands.command("metadata", help="读取聊天室资源和统计")
@click.argument("room_id")
@click.pass_obj
def room_metadata(client: RelayHttpClient, room_id: str) -> ApiResult:
    return client.request("GET", f"{_room_path(room_id)}/metadata")


@room_commands.command("events", help="补取聊天室事件")
@click.argument("room_id")
@click.option("--after-event-id", type=int, default=0, show_default=True)
@click.option("--limit", type=click.IntRange(1, 200), default=200, show_default=True)
@click.pass_obj
def room_events(
    client: RelayHttpClient, room_id: str, after_event_id: int, limit: int
) -> ApiResult:
    return client.request(
        "GET",
        f"{_room_path(room_id)}/event",
        params={"after_event_id": after_event_id, "limit": limit},
    )


@cli.group("topic", no_args_is_help=False)
def topic_commands() -> None:
    """话题。"""


@topic_commands.command("list", help="列出聊天室话题")
@click.argument("room_id")
@click.pass_obj
def topic_list(client: RelayHttpClient, room_id: str) -> ApiResult:
    return _result_from_field(client.request("GET", f"{_room_path(room_id)}/metadata"), "topics")


@topic_commands.command("create", help="创建话题")
@click.argument("room_id")
@click.option("--name", required=True)
@click.option("--description", default="")
@click.pass_obj
def topic_create(client: RelayHttpClient, room_id: str, name: str, description: str) -> ApiResult:
    return client.request(
        "POST",
        f"{_room_path(room_id)}/topic",
        body={"name": name, "description": description},
    )


@topic_commands.command("update", help="更新话题")
@click.argument("room_id")
@click.argument("topic_id")
@click.option("--name", required=True)
@click.option("--description", required=True)
@click.pass_obj
def topic_update(
    client: RelayHttpClient, room_id: str, topic_id: str, name: str, description: str
) -> ApiResult:
    return client.request(
        "PATCH",
        f"{_room_path(room_id)}/topic/{_segment(topic_id)}",
        body={"name": name, "description": description},
    )


@topic_commands.command("delete", help="删除话题")
@click.argument("room_id")
@click.argument("topic_id")
@click.pass_obj
def topic_delete(client: RelayHttpClient, room_id: str, topic_id: str) -> ApiResult:
    return client.request("DELETE", f"{_room_path(room_id)}/topic/{_segment(topic_id)}")


@cli.group("member", no_args_is_help=False)
def member_commands() -> None:
    """成员和会话。"""


@member_commands.command("list", help="列出聊天室成员")
@click.argument("room_id")
@click.pass_obj
def member_list(client: RelayHttpClient, room_id: str) -> ApiResult:
    return _result_from_field(client.request("GET", f"{_room_path(room_id)}/metadata"), "members")


@member_commands.command("sessions", help="列出项目目录内的 Codex 会话")
@click.argument("room_id")
@click.pass_obj
def member_sessions(client: RelayHttpClient, room_id: str) -> ApiResult:
    return client.request("GET", f"{_room_path(room_id)}/session")


@member_commands.command("add", help="添加已存在的会话为成员")
@click.argument("room_id")
@click.option("--session-id", required=True)
@click.option("--name", required=True)
@click.option("--topic-id", multiple=True, help="订阅话题，可重复；省略时不订阅话题")
@click.pass_obj
def member_add(
    client: RelayHttpClient, room_id: str, session_id: str, name: str, topic_id: tuple[str, ...]
) -> ApiResult:
    return client.request(
        "POST",
        f"{_room_path(room_id)}/member",
        body={"sessionId": session_id, "name": name, "topicIds": list(topic_id)},
    )


@member_commands.command("update", help="更新成员")
@click.argument("room_id")
@click.argument("member_id")
@click.option("--name", required=True)
@click.option("--topic-id", multiple=True, help="订阅话题，可重复；省略时清空订阅")
@click.pass_obj
def member_update(
    client: RelayHttpClient, room_id: str, member_id: str, name: str, topic_id: tuple[str, ...]
) -> ApiResult:
    return client.request(
        "PATCH",
        f"{_room_path(room_id)}/member/{_segment(member_id)}",
        body={"name": name, "topicIds": list(topic_id)},
    )


@member_commands.command("delete", help="删除成员")
@click.argument("room_id")
@click.argument("member_id")
@click.pass_obj
def member_delete(client: RelayHttpClient, room_id: str, member_id: str) -> ApiResult:
    return client.request("DELETE", f"{_room_path(room_id)}/member/{_segment(member_id)}")


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
    client: RelayHttpClient,
    room_id: str,
    topic_id: str | None,
    member_id: str | None,
    before_seq: int | None,
    limit: int,
) -> ApiResult:
    return client.request(
        "GET",
        f"{_room_path(room_id)}/message",
        params={
            "topic_id": topic_id,
            "member_id": member_id,
            "before_seq": before_seq,
            "limit": limit,
        },
    )


def _message_result(client: RelayHttpClient, room_id: str, message_id: str) -> ApiResult:
    return client.request("GET", f"{_room_path(room_id)}/message/{_segment(message_id)}")


@message_commands.command("get", help="查询单条消息")
@click.argument("room_id")
@click.argument("message_id")
@click.pass_obj
def message_get(client: RelayHttpClient, room_id: str, message_id: str) -> ApiResult:
    return _message_result(client, room_id, message_id)


@message_commands.command("publish", help="显式发布消息")
@click.argument("room_id")
@click.option("--publication-id", required=True)
@click.option("--content", required=True)
@click.option("--topic-id", multiple=True)
@click.option("--mention", multiple=True)
@click.option("--reply-to")
@click.pass_obj
def message_publish(
    client: RelayHttpClient,
    room_id: str,
    publication_id: str,
    content: str,
    topic_id: tuple[str, ...],
    mention: tuple[str, ...],
    reply_to: str | None,
) -> ApiResult:
    return client.request(
        "POST",
        f"{_room_path(room_id)}/message",
        body={
            "publicationId": publication_id,
            "content": content,
            "topicIds": list(topic_id),
            "mentionedMemberIds": list(mention),
            "replyToMessageId": reply_to,
        },
    )


@message_commands.command("publication", help="按稳定编号找回发布")
@click.argument("room_id")
@click.argument("publication_id")
@click.pass_obj
def publication_get(client: RelayHttpClient, room_id: str, publication_id: str) -> ApiResult:
    return client.request("GET", f"{_room_path(room_id)}/publication/{_segment(publication_id)}")


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
    client: RelayHttpClient,
    room_id: str,
    message_id: str,
    status: str | None,
    member_id: str | None,
) -> ApiResult:
    result = _message_result(client, room_id, message_id)
    message = _object(result)
    filtered = [
        delivery
        for delivery in _rows(result, "deliveries")
        if (status is None or delivery.get("status") == status)
        and (member_id is None or delivery.get("targetMemberId") == member_id)
    ]
    return ApiResult({"messageId": message.get("id"), "deliveries": filtered}, result.request_id)


@delivery_commands.command("get", help="查询单条投递")
@click.argument("room_id")
@click.argument("message_id")
@click.argument("delivery_id")
@click.pass_obj
def delivery_get(
    client: RelayHttpClient, room_id: str, message_id: str, delivery_id: str
) -> ApiResult:
    result = _message_result(client, room_id, message_id)
    delivery = next(
        (row for row in _rows(result, "deliveries") if row.get("id") == delivery_id),
        None,
    )
    if delivery is None:
        raise CliFailure(
            3,
            "delivery_not_found",
            "消息中不存在该投递记录",
            request_id=result.request_id,
        )
    return ApiResult(delivery, result.request_id)


def _object(result: ApiResult) -> dict[str, Any]:
    if not isinstance(result.data, dict):
        raise CliFailure(
            4, "invalid_response", "Relay 返回的 JSON 结构无效", request_id=result.request_id
        )
    return result.data


def _rows(result: ApiResult, field: str) -> list[dict[str, Any]]:
    value = _object(result).get(field)
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise CliFailure(
            4, "invalid_response", "Relay 返回的 JSON 列表无效", request_id=result.request_id
        )
    return value


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _header(headers: Mapping[str, str], name: str) -> str | None:
    lowered = name.casefold()
    return next((value for key, value in headers.items() if key.casefold() == lowered), None)


def _decode_json(response_body: bytes) -> object:
    if not response_body:
        return None
    return json.loads(response_body.decode("utf-8"))


def _emit_success(result: ApiResult) -> None:
    print(
        json.dumps(
            {"requestId": result.request_id, "data": result.data},
            ensure_ascii=False,
            indent=2,
        )
    )


def _emit_failure(failure: CliFailure) -> None:
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
        _emit_failure(CliFailure(2, "invalid_arguments", failure.format_message()))
        return 2
    except click.Abort:
        _emit_failure(CliFailure(130, "interrupted", "请求已中断"))
        return 130
    except CliFailure as failure:
        _emit_failure(failure)
        return failure.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
