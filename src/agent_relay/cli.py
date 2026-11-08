from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from http.client import HTTPException
from typing import Any, NoReturn, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


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


class CliArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise CliFailure(2, "invalid_arguments", message)


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


CommandHandler = Callable[[RelayHttpClient, argparse.Namespace], ApiResult]


def _segment(value: str) -> str:
    return quote(value, safe="")


def _room_path(room_id: str) -> str:
    return f"/api/room/{_segment(room_id)}"


def _result_from_field(result: ApiResult, field: str) -> ApiResult:
    return ApiResult(_rows(result, field), result.request_id)


def _room_list(client: RelayHttpClient, _args: argparse.Namespace) -> ApiResult:
    return client.request("GET", "/api/room")


def _room_create(client: RelayHttpClient, args: argparse.Namespace) -> ApiResult:
    return client.request(
        "POST",
        "/api/room",
        body={"name": args.name, "projectPath": args.project_path},
    )


def _room_get(client: RelayHttpClient, args: argparse.Namespace) -> ApiResult:
    return client.request(
        "GET",
        _room_path(args.room_id),
        params={
            "topic_id": args.topic_id,
            "member_id": args.member_id,
            "before_seq": args.before_seq,
            "limit": args.limit,
        },
    )


def _room_metadata(client: RelayHttpClient, args: argparse.Namespace) -> ApiResult:
    return client.request("GET", f"{_room_path(args.room_id)}/metadata")


def _room_events(client: RelayHttpClient, args: argparse.Namespace) -> ApiResult:
    return client.request(
        "GET",
        f"{_room_path(args.room_id)}/event",
        params={"after_event_id": args.after_event_id, "limit": args.limit},
    )


def _topic_list(client: RelayHttpClient, args: argparse.Namespace) -> ApiResult:
    return _result_from_field(_room_metadata(client, args), "topics")


def _topic_create(client: RelayHttpClient, args: argparse.Namespace) -> ApiResult:
    return client.request(
        "POST",
        f"{_room_path(args.room_id)}/topic",
        body={"name": args.name, "description": args.description},
    )


def _topic_update(client: RelayHttpClient, args: argparse.Namespace) -> ApiResult:
    return client.request(
        "PATCH",
        f"{_room_path(args.room_id)}/topic/{_segment(args.topic_id)}",
        body={"name": args.name, "description": args.description},
    )


def _topic_delete(client: RelayHttpClient, args: argparse.Namespace) -> ApiResult:
    return client.request("DELETE", f"{_room_path(args.room_id)}/topic/{_segment(args.topic_id)}")


def _member_list(client: RelayHttpClient, args: argparse.Namespace) -> ApiResult:
    return _result_from_field(_room_metadata(client, args), "members")


def _member_sessions(client: RelayHttpClient, args: argparse.Namespace) -> ApiResult:
    return client.request("GET", f"{_room_path(args.room_id)}/session")


def _member_add(client: RelayHttpClient, args: argparse.Namespace) -> ApiResult:
    return client.request(
        "POST",
        f"{_room_path(args.room_id)}/member",
        body={"sessionId": args.session_id, "name": args.name, "topicIds": args.topic_id},
    )


def _member_update(client: RelayHttpClient, args: argparse.Namespace) -> ApiResult:
    return client.request(
        "PATCH",
        f"{_room_path(args.room_id)}/member/{_segment(args.member_id)}",
        body={"name": args.name, "topicIds": args.topic_id},
    )


def _member_delete(client: RelayHttpClient, args: argparse.Namespace) -> ApiResult:
    return client.request("DELETE", f"{_room_path(args.room_id)}/member/{_segment(args.member_id)}")


def _message_list(client: RelayHttpClient, args: argparse.Namespace) -> ApiResult:
    return client.request(
        "GET",
        f"{_room_path(args.room_id)}/message",
        params={
            "topic_id": args.topic_id,
            "member_id": args.member_id,
            "before_seq": args.before_seq,
            "limit": args.limit,
        },
    )


def _message_get(client: RelayHttpClient, args: argparse.Namespace) -> ApiResult:
    return client.request(
        "GET",
        f"{_room_path(args.room_id)}/message/{_segment(args.message_id)}",
    )


def _message_publish(client: RelayHttpClient, args: argparse.Namespace) -> ApiResult:
    return client.request(
        "POST",
        f"{_room_path(args.room_id)}/message",
        body={
            "publicationId": args.publication_id,
            "content": args.content,
            "topicIds": args.topic_id,
            "mentionedMemberIds": args.mention,
            "replyToMessageId": args.reply_to,
        },
    )


def _publication_get(client: RelayHttpClient, args: argparse.Namespace) -> ApiResult:
    return client.request(
        "GET",
        f"{_room_path(args.room_id)}/publication/{_segment(args.publication_id)}",
    )


def _delivery_list(client: RelayHttpClient, args: argparse.Namespace) -> ApiResult:
    result = _message_get(client, args)
    message = _object(result)
    filtered = [
        delivery
        for delivery in _rows(result, "deliveries")
        if (args.status is None or delivery.get("status") == args.status)
        and (args.member_id is None or delivery.get("targetMemberId") == args.member_id)
    ]
    return ApiResult({"messageId": message.get("id"), "deliveries": filtered}, result.request_id)


def _delivery_get(client: RelayHttpClient, args: argparse.Namespace) -> ApiResult:
    result = _message_get(client, args)
    delivery = next(
        (row for row in _rows(result, "deliveries") if row.get("id") == args.delivery_id),
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


def _positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive number") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be finite and greater than zero")
    return parsed


def _page_limit(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer from 1 to 200") from exc
    if not 1 <= parsed <= 200:
        raise argparse.ArgumentTypeError("must be an integer from 1 to 200")
    return parsed


def _command_parser(
    parent: argparse._SubParsersAction[CliArgumentParser],
    name: str,
    handler: CommandHandler,
    help_text: str,
) -> argparse.ArgumentParser:
    parser = parent.add_parser(name, help=help_text)
    parser.set_defaults(handler=handler)
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = CliArgumentParser(prog="agent-relay", description="通过 HTTP 管理本机 Relay 聊天室")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("AGENT_RELAY_URL", "http://127.0.0.1:9080"),
        help="Relay 服务地址（默认读取 AGENT_RELAY_URL）",
    )
    parser.add_argument(
        "--timeout",
        type=_positive_float,
        default=os.environ.get("AGENT_RELAY_HTTP_TIMEOUT", "10"),
        help="单次 HTTP 请求超时秒数（默认读取 AGENT_RELAY_HTTP_TIMEOUT）",
    )
    groups = parser.add_subparsers(dest="group", required=True)

    room = groups.add_parser("room", help="聊天室")
    room_commands = room.add_subparsers(dest="action", required=True)
    _command_parser(room_commands, "list", _room_list, "列出聊天室")
    create = _command_parser(room_commands, "create", _room_create, "创建聊天室")
    create.add_argument("--name", required=True)
    create.add_argument("--project-path", required=True)
    get = _command_parser(room_commands, "get", _room_get, "读取聊天室及最新消息页")
    get.add_argument("room_id")
    _add_message_page_args(get)
    metadata = _command_parser(room_commands, "metadata", _room_metadata, "读取聊天室资源和统计")
    metadata.add_argument("room_id")
    events = _command_parser(room_commands, "events", _room_events, "补取聊天室事件")
    events.add_argument("room_id")
    events.add_argument("--after-event-id", type=int, default=0)
    events.add_argument("--limit", type=_page_limit, default=200)

    topic = groups.add_parser("topic", help="话题")
    topic_commands = topic.add_subparsers(dest="action", required=True)
    topic_list = _command_parser(topic_commands, "list", _topic_list, "列出聊天室话题")
    topic_list.add_argument("room_id")
    topic_create = _command_parser(topic_commands, "create", _topic_create, "创建话题")
    topic_create.add_argument("room_id")
    topic_create.add_argument("--name", required=True)
    topic_create.add_argument("--description", default="")
    topic_update = _command_parser(topic_commands, "update", _topic_update, "更新话题")
    topic_update.add_argument("room_id")
    topic_update.add_argument("topic_id")
    topic_update.add_argument("--name", required=True)
    topic_update.add_argument("--description", required=True)
    topic_delete = _command_parser(topic_commands, "delete", _topic_delete, "删除话题")
    topic_delete.add_argument("room_id")
    topic_delete.add_argument("topic_id")

    member = groups.add_parser("member", help="成员和会话")
    member_commands = member.add_subparsers(dest="action", required=True)
    member_list = _command_parser(member_commands, "list", _member_list, "列出聊天室成员")
    member_list.add_argument("room_id")
    sessions = _command_parser(
        member_commands, "sessions", _member_sessions, "列出项目目录内的 Codex 会话"
    )
    sessions.add_argument("room_id")
    member_add = _command_parser(member_commands, "add", _member_add, "添加已存在的会话为成员")
    member_add.add_argument("room_id")
    member_add.add_argument("--session-id", required=True)
    member_add.add_argument("--name", required=True)
    member_add.add_argument("--topic-id", action="append", required=True)
    member_update = _command_parser(member_commands, "update", _member_update, "更新成员")
    member_update.add_argument("room_id")
    member_update.add_argument("member_id")
    member_update.add_argument("--name", required=True)
    member_update.add_argument("--topic-id", action="append", required=True)
    member_delete = _command_parser(member_commands, "delete", _member_delete, "删除成员")
    member_delete.add_argument("room_id")
    member_delete.add_argument("member_id")

    message = groups.add_parser("message", help="消息和发布")
    message_commands = message.add_subparsers(dest="action", required=True)
    message_list = _command_parser(message_commands, "list", _message_list, "查询消息页")
    message_list.add_argument("room_id")
    _add_message_page_args(message_list)
    message_get = _command_parser(message_commands, "get", _message_get, "查询单条消息")
    message_get.add_argument("room_id")
    message_get.add_argument("message_id")
    publish = _command_parser(message_commands, "publish", _message_publish, "显式发布消息")
    publish.add_argument("room_id")
    publish.add_argument("--publication-id", required=True)
    publish.add_argument("--content", required=True)
    publish.add_argument("--topic-id", action="append", default=[])
    publish.add_argument("--mention", action="append", default=[])
    publish.add_argument("--reply-to")
    publication = _command_parser(
        message_commands, "publication", _publication_get, "按稳定编号找回发布"
    )
    publication.add_argument("room_id")
    publication.add_argument("publication_id")

    delivery = groups.add_parser("delivery", help="查询持久投递")
    delivery_commands = delivery.add_subparsers(dest="action", required=True)
    delivery_list = _command_parser(delivery_commands, "list", _delivery_list, "列出消息的投递")
    delivery_list.add_argument("room_id")
    delivery_list.add_argument("message_id")
    delivery_list.add_argument(
        "--status", choices=("pending", "submitting", "queued", "received", "rejected", "unknown")
    )
    delivery_list.add_argument("--member-id")
    delivery_get = _command_parser(delivery_commands, "get", _delivery_get, "查询单条投递")
    delivery_get.add_argument("room_id")
    delivery_get.add_argument("message_id")
    delivery_get.add_argument("delivery_id")
    return parser


def _add_message_page_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--topic-id")
    parser.add_argument("--member-id", help="按发言成员筛选")
    parser.add_argument("--before-seq", type=int)
    parser.add_argument("--limit", type=_page_limit, default=50)


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
        parser = build_parser()
        args = parser.parse_args(argv)
        client = RelayHttpClient(args.base_url, args.timeout, opener=opener)
        handler = cast(CommandHandler, args.handler)
        _emit_success(handler(client, args))
        return 0
    except CliFailure as failure:
        _emit_failure(failure)
        return failure.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
