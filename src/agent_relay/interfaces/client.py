from __future__ import annotations

import json
import math
from collections.abc import Mapping
from http.client import HTTPException
from typing import Annotated, Any, NoReturn, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pydantic import Field

from agent_relay.interfaces.dto import ApiResult


class HttpResponse(Protocol):
    status: int
    headers: Mapping[str, str]

    def read(self) -> bytes: ...
    def close(self) -> None: ...


class RequestOpener(Protocol):
    def __call__(self, request: Request, *, timeout: float) -> HttpResponse: ...


class RelayClientError(Exception):
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


class RelayClient:
    def __init__(
        self,
        base_url: str,
        timeout: float,
        *,
        opener: RequestOpener | None = None,
        session_id: str | None = None,
    ) -> None:
        try:
            parsed = urlsplit(base_url)
            host = parsed.hostname
            _ = parsed.port
            has_credentials = parsed.username is not None or parsed.password is not None
        except ValueError as exc:
            raise RelayClientError(2, "invalid_base_url", "服务地址格式无效") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not host
            or has_credentials
            or parsed.query
            or parsed.fragment
        ):
            raise RelayClientError(
                2, "invalid_base_url", "服务地址只能包含 HTTP(S) scheme、主机和路径"
            )
        if not math.isfinite(timeout) or timeout <= 0:
            raise RelayClientError(2, "invalid_timeout", "HTTP 超时必须为大于 0 的有限数值")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session_id = session_id
        self.opener = opener or cast(RequestOpener, build_opener(NoRedirectHandler()).open)

    def for_session(self, session_id: str) -> RelayClient:
        return RelayClient(self.base_url, self.timeout, opener=self.opener, session_id=session_id)

    def _member_id(self, room_id: str, member_id: str | None = None) -> str:
        if member_id is not None:
            return member_id
        if not self.session_id:
            raise RelayClientError(2, "session_required", "当前调用没有 Codex 会话上下文")
        result = self.request(
            "GET", f"{_room_path(room_id)}/session/{_segment(self.session_id)}/member"
        )
        if not isinstance(result.data, dict) or not isinstance(result.data.get("id"), str):
            raise RelayClientError(
                4, "invalid_response", "Relay 未返回成员身份", request_id=result.request_id
            )
        return str(result.data["id"])

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
        headers = {"Accept": "application/json", "X-Agent-Relay-Image-Paths": "local"}
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
            raise RelayClientError(
                130,
                "interrupted",
                "请求已中断；写入结果请先查询服务记录" if is_write else "请求已中断",
                request_id=request_id,
                outcome="unknown" if is_write else None,
            ) from exc
        except (URLError, OSError, HTTPException) as exc:
            raise RelayClientError(
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
            raise RelayClientError(
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
        raise RelayClientError(
            3 if rejected else 4,
            api_code,
            message,
            request_id=request_id,
            http_status=status,
            outcome=("rejected" if rejected else "unknown") if is_write else None,
        )

    def room_list(self) -> ApiResult:
        """List the available project chatrooms."""
        return self.request("GET", "/api/room")

    def room_create(self, name: str, project_path: str) -> ApiResult:
        """Create a chatroom for an absolute project directory."""
        return self.request("POST", "/api/room", body={"name": name, "projectPath": project_path})

    def room_get(
        self,
        room_id: str,
        topic_id: str | None = None,
        member_id: str | None = None,
        before_seq: Annotated[int | None, Field(ge=1)] = None,
        limit: Annotated[int, Field(ge=1, le=200)] = 50,
        keyword: Annotated[str | None, Field(max_length=200)] = None,
    ) -> ApiResult:
        """Read room resources and messages; member_id matches sender or actual recipients.

        topic_id and member_id are intersected. keyword is a literal content substring;
        before_seq is exclusive and limit is 1..200.
        """
        return self.request(
            "GET",
            _room_path(room_id),
            params={
                "topic_id": topic_id,
                "member_id": member_id,
                "keyword": keyword,
                "before_seq": before_seq,
                "limit": limit,
            },
        )

    def room_metadata(self, room_id: str) -> ApiResult:
        """Read room resources, delivery counts, query positions and the event cursor."""
        return self.request("GET", f"{_room_path(room_id)}/metadata")

    def room_events(self, room_id: str, after_event_id: int = 0, limit: int = 200) -> ApiResult:
        """Read one bounded page of persisted events after the supplied cursor."""
        return self.request(
            "GET",
            f"{_room_path(room_id)}/event",
            params={"after_event_id": after_event_id, "limit": limit},
        )

    def topic_list(self, room_id: str) -> ApiResult:
        """List room topics, including records marked deleted_at."""
        result = self.room_metadata(room_id)
        return ApiResult(self._rows(result, "topics"), result.request_id)

    def topic_create(self, room_id: str, name: str, description: str = "") -> ApiResult:
        """Create a topic; its creation is independent of member forms."""
        return self.request(
            "POST",
            f"{_room_path(room_id)}/topic",
            body={"name": name, "description": description},
        )

    def topic_update(self, room_id: str, topic_id: str, name: str, description: str) -> ApiResult:
        """Update a topic's name and description; an empty description clears it."""
        return self.request(
            "PATCH",
            f"{_room_path(room_id)}/topic/{_segment(topic_id)}",
            body={"name": name, "description": description},
        )

    def topic_delete(self, room_id: str, topic_id: str) -> ApiResult:
        """Delete a topic and clear its subscriptions without changing saved deliveries."""
        return self.request("DELETE", f"{_room_path(room_id)}/topic/{_segment(topic_id)}")

    def member_list(self, room_id: str) -> ApiResult:
        """List members and their subscriptions, including records marked deleted_at."""
        result = self.room_metadata(room_id)
        return ApiResult(self._rows(result, "members"), result.request_id)

    def member_sessions(self, room_id: str) -> ApiResult:
        """Refresh Codex session candidates for the room's directory and their usability."""
        return self.request("GET", f"{_room_path(room_id)}/session")

    def member_add(
        self, room_id: str, session_id: str, name: str, topic_ids: list[str] | None = None
    ) -> ApiResult:
        """Join a usable existing Codex session; subscriptions can be empty."""
        return self.request(
            "POST",
            f"{_room_path(room_id)}/member",
            body={"sessionId": session_id, "name": name, "topicIds": topic_ids or []},
        )

    def member_update(
        self, room_id: str, member_id: str, name: str, topic_ids: list[str] | None = None
    ) -> ApiResult:
        """Update a member's name and subscriptions; omitted topic_ids clears subscriptions."""
        return self.request(
            "PATCH",
            _member_path(room_id, member_id),
            body={"name": name, "topicIds": topic_ids or []},
        )

    def member_delete(self, room_id: str, member_id: str) -> ApiResult:
        """Remove a member from new routing without modifying its original Codex session."""
        return self.request("DELETE", _member_path(room_id, member_id))

    def member_catalog(self, room_id: str, member_id: str | None = None) -> ApiResult:
        """Read room/project context, active topic/member IDs and this member's subscriptions."""
        return self.request(
            "GET", f"{_member_path(room_id, self._member_id(room_id, member_id))}/catalog"
        )

    def member_context(
        self,
        room_id: str,
        member_id: str | None = None,
        message_id: str | None = None,
        topic_id: str | None = None,
        keyword: str | None = None,
        before_seq: int | None = None,
        after_seq: int | None = None,
        limit: int = 50,
    ) -> ApiResult:
        """Read recent messages visible to this member, optionally selecting a subscribed topic,
        literal keyword or single message. Own publications are also visible. A message ID
        excludes other filters. Choose at most one cursor direction; limit is 1..200.
        Records returned are persisted as provided and advance query positions, not read receipts.
        """
        values = {
            "messageId": message_id,
            "topicId": topic_id,
            "keyword": keyword,
            "beforeSeq": before_seq,
            "afterSeq": after_seq,
            "limit": limit,
        }
        return self.request(
            "POST",
            f"{_member_path(room_id, self._member_id(room_id, member_id))}/context",
            body={key: value for key, value in values.items() if value is not None},
        )

    def member_positions(self, room_id: str, member_id: str | None = None) -> ApiResult:
        """Read this member's topic query positions and later message counts, without advancing."""
        return self.request(
            "GET", f"{_member_path(room_id, self._member_id(room_id, member_id))}/position"
        )

    def message_list(
        self,
        room_id: str,
        topic_id: str | None = None,
        member_id: str | None = None,
        before_seq: Annotated[int | None, Field(ge=1)] = None,
        limit: Annotated[int, Field(ge=1, le=200)] = 50,
        keyword: Annotated[str | None, Field(max_length=200)] = None,
    ) -> ApiResult:
        """Read messages; member_id matches sender or actual recipients.

        topic_id and member_id are intersected. keyword is a literal content substring;
        before_seq is exclusive and limit is 1..200.
        """
        return self.request(
            "GET",
            f"{_room_path(room_id)}/message",
            params={
                "topic_id": topic_id,
                "member_id": member_id,
                "keyword": keyword,
                "before_seq": before_seq,
                "limit": limit,
            },
        )

    def queue_list(
        self,
        room_id: str,
        topic_id: str | None = None,
        member_id: str | None = None,
        before_seq: Annotated[int | None, Field(ge=1)] = None,
        limit: Annotated[int, Field(ge=1, le=200)] = 50,
    ) -> ApiResult:
        """Read current active queue messages, newest first, paging toward older seq values.

        A message is active when it has an undeleted pending, submitting or queued delivery.
        member_id matches sender or saved recipient; topic_id and member_id are intersected.
        """
        return self.request(
            "GET",
            f"{_room_path(room_id)}/queue",
            params={
                "topic_id": topic_id,
                "member_id": member_id,
                "before_seq": before_seq,
                "limit": limit,
            },
        )

    def queue_clear(
        self,
        room_id: str,
        topic_id: str | None = None,
        member_id: str | None = None,
        clear_codex: bool = False,
    ) -> ApiResult:
        """Remove unfinished deliveries from every matching message, preserving history.

        member_id matches sender or saved recipient and affects all unfinished Agent deliveries
        on matching messages. Defaults to Relay only. Set clear_codex=true to also delete waiting
        Codex items identified by Relay receipts in scope, including previously cleared records.
        Does not interrupt running turns. An unknown outcome must not be retried blindly.
        """
        result = self.request(
            "DELETE",
            f"{_room_path(room_id)}/queue",
            params={
                "topic_id": topic_id,
                "member_id": member_id,
                "clear_codex": "true" if clear_codex else None,
            },
        )
        if clear_codex and (
            not isinstance(result.data, dict) or not isinstance(result.data.get("codexQueue"), dict)
        ):
            raise RelayClientError(
                4,
                "invalid_response",
                "服务未返回 Codex 队列清理结果；Relay 记录可能已清空，请核对服务版本",
                request_id=result.request_id,
                outcome="unknown",
            )
        return result

    def message_get(self, room_id: str, message_id: str) -> ApiResult:
        """Read one saved message and its persisted per-member delivery history."""
        return self.request("GET", f"{_room_path(room_id)}/message/{_segment(message_id)}")

    def message_publish(
        self,
        room_id: str,
        publication_id: str,
        content: str,
        topic_ids: list[str] | None = None,
        mentioned_member_ids: list[str] | None = None,
        reply_to_message_id: str | None = None,
        as_member: str | None = None,
    ) -> ApiResult:
        """Publish with explicit topics and/or member mentions, including the human user.
        as_member selects an active member publisher (excluded from recipients); otherwise
        publish as the room user. Retain publication_id for lookup if the outcome is unknown.
        References do not inherit targets. A saved message does not confirm queue reception.
        """
        publisher = self._member_id(room_id, as_member) if self.session_id else as_member
        path = _member_path(room_id, publisher) if publisher is not None else _room_path(room_id)
        return self.request(
            "POST",
            f"{path}/message",
            body={
                "publicationId": publication_id,
                "content": content,
                "topicIds": topic_ids or [],
                "mentionedMemberIds": mentioned_member_ids or [],
                "replyToMessageId": reply_to_message_id,
            },
        )

    def publication_get(
        self, room_id: str, publication_id: str, as_member: str | None = None
    ) -> ApiResult:
        """Find the original saved publication without sending again; use the same as_member."""
        publisher = self._member_id(room_id, as_member) if self.session_id else as_member
        path = _member_path(room_id, publisher) if publisher is not None else _room_path(room_id)
        return self.request("GET", f"{path}/publication/{_segment(publication_id)}")

    def delivery_list(
        self,
        room_id: str,
        message_id: str,
        status: str | None = None,
        member_id: str | None = None,
    ) -> ApiResult:
        """Read persisted delivery history, optionally filtering status and recipient.

        Original status and deleted_at are preserved; use queue_list for the active queue.
        """
        result = self.message_get(room_id, message_id)
        deliveries = [
            row
            for row in self._rows(result, "deliveries")
            if (status is None or row.get("status") == status)
            and (member_id is None or row.get("targetMemberId") == member_id)
        ]
        return ApiResult({"messageId": message_id, "deliveries": deliveries}, result.request_id)

    def delivery_get(self, room_id: str, message_id: str, delivery_id: str) -> ApiResult:
        """Read one delivery's persisted queue/reception evidence."""
        result = self.message_get(room_id, message_id)
        for delivery in self._rows(result, "deliveries"):
            if delivery.get("id") == delivery_id:
                return ApiResult(delivery, result.request_id)
        raise RelayClientError(
            3, "delivery_not_found", "消息中不存在该投递记录", request_id=result.request_id
        )

    @staticmethod
    def _rows(result: ApiResult, field: str) -> list[dict[str, Any]]:
        if not isinstance(result.data, dict):
            raise RelayClientError(
                4, "invalid_response", "Relay 返回的 JSON 结构无效", request_id=result.request_id
            )
        value = result.data.get(field)
        if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
            raise RelayClientError(
                4, "invalid_response", "Relay 返回的 JSON 列表无效", request_id=result.request_id
            )
        return value


def _segment(value: str) -> str:
    return quote(value, safe="")


def _room_path(room_id: str) -> str:
    return f"/api/room/{_segment(room_id)}"


def _member_path(room_id: str, member_id: str) -> str:
    return f"{_room_path(room_id)}/member/{_segment(member_id)}"


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _header(headers: Mapping[str, str], name: str) -> str | None:
    lowered = name.casefold()
    return next((value for key, value in headers.items() if key.casefold() == lowered), None)


def _decode_json(response_body: bytes) -> object:
    if not response_body:
        return None
    return json.loads(response_body.decode("utf-8"))
