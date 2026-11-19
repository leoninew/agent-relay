"""Convert a closed member_roles_20261118 snapshot into a new asset bundle."""

import argparse
import hashlib
import json
import re
import shutil
import sqlite3
import sys
from collections import Counter
from collections.abc import Iterator
from contextlib import closing
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any

from conflua.domain.identifiers import TsidSource
from conflua.domain.rooms.inline_images import inline_images
from conflua.domain.rooms.markdown import inline_matches
from conflua.infrastructure.persistence.migrations import MIGRATION_HEAD, run_migrations

SOURCE_REVISION = "member_roles_20261118"
TARGET_REVISION = "schema_governance_20261119"
ROOT = Path(__file__).resolve().parents[1]
TABLES = (
    "rooms",
    "channels",
    "sessions",
    "topics",
    "members",
    "member_topics",
    "messages",
    "message_topics",
    "message_mentions",
    "message_recipients",
    "deliveries",
    "room_events",
    "member_context_queries",
    "member_context_messages",
    "member_topic_positions",
    "member_roles",
)
ID_SCOPES = {
    "rooms": (),
    "channels": ("room_id",),
    "topics": ("room_id", "channel_id"),
    "members": ("room_id", "channel_id"),
    "messages": ("room_id", "channel_id"),
    "deliveries": ("room_id", "channel_id"),
    "member_context_queries": ("room_id", "channel_id"),
    "member_roles": (),
}
REFERENCES = {
    "room_id": "rooms",
    "channel_id": "channels",
    "topic_id": "topics",
    "member_id": "members",
    "publisher_id": "members",
    "target_member_id": "members",
    "message_id": "messages",
    "reply_to_message_id": "messages",
    "query_id": "member_context_queries",
}
EVENT_ENTITIES = {
    "topic": "topics",
    "member": "members",
    "position": "members",
    "message": "messages",
    "delivery": "deliveries",
    "clear": "rooms",
}
TIMESTAMPS = (
    "created_at",
    "updated_at",
    "deleted_at",
    "archived_at",
    "observed_at",
    "provided_at",
    "queued_at",
    "received_at",
    "activation_attempted_at",
    "next_attempt_at",
)
LEGACY_ROLES = {
    "role-51e2d9a525cc4363b8660e64db6df0e1": "0S9A3WPM7ZZ3Y",
    "role-fdb01844f6e0422b8126737dcd156480": "0S9A3WPM7ZZ3Z",
    "role-bfaf04ac7f07427591abb0f4e2c3a32c": "0S9A3WPM7ZZ40",
}
OLD_ROOM = re.compile(r"room-[A-Za-z0-9_-]+")
OLD_CHANNEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
IMAGE_FILE = re.compile(r"(img-[a-f0-9]{32})\.(png|jpg|webp)")
OLD_LINK = re.compile(
    r"!\[(?:\\[^\r\n]|[^\]\\\r\n])*\]"
    rf"\((/api/room/({OLD_ROOM.pattern})/channel/({OLD_CHANNEL.pattern})/image/(img-[a-f0-9]{{32}}))\)"
)
ISO_TIME = re.compile(
    r"(?P<local>[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:[.,][0-9]{1,6})?)(?:Z|(?P<sign>[+-])(?P<offset>[0-9]{2}:[0-9]{2}"
    r"(?::[0-9]{2}(?:[.,][0-9]{1,6})?)?))"
)

type SqlValue = str | int | float | bytes | None
type Row = dict[str, SqlValue]
type Key = tuple[SqlValue, ...]


class MigrationError(ValueError):
    pass


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def require_revision(db: sqlite3.Connection, expected: str, label: str) -> None:
    exists = db.execute("SELECT 1 FROM sqlite_schema WHERE name = 'alembic_version'").fetchone()
    versions = (
        [row[0] for row in db.execute("SELECT version_num FROM alembic_version")] if exists else []
    )
    if versions != [expected]:
        raise MigrationError(f"{label} revision {versions!r}; expected {expected!r}")


def check_db(db: sqlite3.Connection, label: str) -> dict[str, Any]:
    integrity = [row[0] for row in db.execute("PRAGMA integrity_check")]
    violations = [tuple(row) for row in db.execute("PRAGMA foreign_key_check")]
    if integrity != ["ok"] or violations:
        raise MigrationError(
            f"{label}: integrity_check={integrity}; foreign_key_check={violations}"
        )
    return {"integrity_check": integrity, "foreign_key_check": violations}


def rows(db: sqlite3.Connection, table: str) -> Iterator[tuple[int, Row]]:
    for record in db.execute(f'SELECT rowid AS "_old_rowid", * FROM "{table}" ORDER BY rowid'):
        data = dict(record)
        yield int(data.pop("_old_rowid")), data


def key_for(table: str, data: Row, identifier: SqlValue) -> Key:
    return (*(data[column] for column in ID_SCOPES[table]), identifier)


def utc_time(value: SqlValue, location: str) -> str:
    match = ISO_TIME.fullmatch(value) if isinstance(value, str) else None
    if not match:
        raise MigrationError(f"{location}: expected ISO time with explicit offset, got {value!r}")
    try:
        local = datetime.fromisoformat(match["local"])
        if match["offset"] is not None:
            offset = time.fromisoformat(match["offset"])
            delta = timedelta(
                hours=offset.hour,
                minutes=offset.minute,
                seconds=offset.second,
                microseconds=offset.microsecond,
            )
            local += delta if match["sign"] == "-" else -delta
        return local.replace(tzinfo=UTC).isoformat(timespec="microseconds")
    except (ValueError, OverflowError) as error:
        raise MigrationError(f"{location}: invalid historical time {value!r}") from error


class Conversion:
    def __init__(self, source: sqlite3.Connection, merged_channel: list[str] | None) -> None:
        self.source = source
        self.merged_channel = merged_channel
        self.merged_events: Counter[str] = Counter()
        self.started_at = datetime.now(UTC).isoformat(timespec="microseconds")
        self.maps: dict[str, dict[Key, str]] = {}
        self.backfills: Counter[str] = Counter()
        self.lifecycle: Counter[str] = Counter()
        self.time_columns: Counter[str] = Counter()
        self.rewritten_images = 0
        generator = TsidSource(node=1023)
        used = set(LEGACY_ROLES.values())
        for table in ID_SCOPES:
            mapping: dict[Key, str] = {}
            for _, row in rows(source, table):
                identifier = LEGACY_ROLES.get(str(row["id"])) if table == "member_roles" else None
                if identifier is None:
                    identifier = generator.next()
                    if identifier in used:
                        raise MigrationError(f"Duplicate generated TSID: {identifier}")
                used.add(identifier)
                mapping[key_for(table, row, row["id"])] = identifier
            self.maps[table] = mapping
        if merged_channel:
            room, destination, origin = merged_channel
            channels = self.maps["channels"]
            if destination == origin or any(
                (room, item) not in channels for item in (destination, origin)
            ):
                raise MigrationError("Merged event channels must be distinct channels in one room")

    def lookup(self, table: str, row: Row, value: SqlValue, location: str) -> str:
        key = key_for(table, row, value)
        try:
            return self.maps[table][key]
        except KeyError as error:
            raise MigrationError(f"{location}: missing {table} reference {key!r}") from error

    def event_entity(self, row: Row, location: str) -> SqlValue:
        entity = row["entity_id"]
        kind = row["kind"]
        merged = self.merged_channel
        origin = merged[2] if merged and [row["room_id"], row["channel_id"]] == merged[:2] else None
        if kind == "room":
            if entity == row["room_id"] and entity != row["channel_id"]:
                return self.lookup("rooms", row, entity, location)
            if entity == row["channel_id"] and entity != row["room_id"]:
                return self.lookup("channels", row, entity, location)
            if origin is not None and entity == origin:
                self.merged_events["room"] += 1
                return self.lookup("channels", row, origin, location)
        elif kind == "session":
            exists = self.source.execute(
                "SELECT 1 FROM sessions WHERE room_id = ? AND id = ?", (row["room_id"], entity)
            ).fetchone()
            if exists:
                return entity
        elif isinstance(kind, str) and kind in EVENT_ENTITIES:
            table = EVENT_ENTITIES[kind]
            if (
                origin
                and kind in {"topic", "member", "position"}
                and key_for(table, row, entity) not in self.maps[table]
            ):
                self.merged_events[kind] += 1
                return self.lookup(table, {**row, "channel_id": origin}, entity, location)
            return self.lookup(table, row, entity, location)
        raise MigrationError(f"{location}: unrecognized event entity {kind!r} / {entity!r}")

    def copy_assets(self, source: Path, output: Path) -> dict[tuple[str, str, str], str]:
        assets: dict[tuple[str, str, str], str] = {}
        output.mkdir()
        for (room, channel), new_channel in self.maps["channels"].items():
            if not OLD_ROOM.fullmatch(str(room)) or not OLD_CHANNEL.fullmatch(str(channel)):
                raise MigrationError(f"Invalid legacy image scope: {(room, channel)!r}")
            source_dir = source / str(room) / "channels" / str(channel) / "images"
            if source_dir.resolve() != source_dir:
                raise MigrationError(f"Redirected image directory: {source_dir}")
            if not source_dir.exists():
                continue
            target_dir = output / self.maps["rooms"][(room,)] / "channels" / new_channel / "images"
            for path in sorted(source_dir.iterdir()):
                match = IMAGE_FILE.fullmatch(path.name)
                if not match:
                    continue
                if not path.is_file() or path.resolve() != path:
                    raise MigrationError(f"Invalid managed image file: {path}")
                asset = (str(room), str(channel), match[1])
                if asset in assets:
                    raise MigrationError(f"Ambiguous managed image file: {asset!r}")
                target_dir.mkdir(parents=True, exist_ok=True)
                target_file = target_dir / path.name
                digest = sha256(path)
                with path.open("rb") as original, target_file.open("xb") as copy:
                    shutil.copyfileobj(original, copy)
                if sha256(target_file) != digest or sha256(path) != digest:
                    raise MigrationError(f"Image changed during copy: {path}")
                assets[asset] = digest
        return assets

    def rewrite_images(
        self, old: Row, new: Row, assets: dict[tuple[str, str, str], str], location: str
    ) -> str:
        content = str(old["content"])
        room, channel = str(old["room_id"]), str(old["channel_id"])
        new_room, new_channel = str(new["room_id"]), str(new["channel_id"])
        pieces: list[str] = []
        start = 0
        expected = []
        for match in inline_matches(content, OLD_LINK):
            if (match[2], match[3]) != (room, channel):
                continue
            asset = (room, channel, match[4])
            if asset not in assets:
                raise MigrationError(f"{location}: missing managed image {asset!r}")
            pieces.extend(
                (
                    content[start : match.start(1)],
                    f"/api/room/{new_room}/channel/{new_channel}/image/{match[4]}",
                )
            )
            start = match.end(1)
            expected.append(match[4])
        if not expected:
            return content
        pieces.append(content[start:])
        result = "".join(pieces)
        rewritten = [image.id for image in inline_images(result, new_room, new_channel)]
        if rewritten != expected:
            raise MigrationError(f"{location}: rewritten managed image links did not round-trip")
        self.rewritten_images += len(expected)
        return result

    def transform(
        self, table: str, row: Row, assets: dict[tuple[str, str, str], str], location: str
    ) -> Row:
        result = row.copy()
        for column in TIMESTAMPS:
            value = row.get(column)
            if value is not None:
                result[column] = utc_time(value, f"{location}.{column}")
                self.time_columns[f"{table}.{column}"] += 1
        if table == "deliveries" and result.get("updated_at") is None:
            raise MigrationError(f"{location}.updated_at: required historical time is NULL")
        if result.get("created_at") is None:
            result["created_at"] = self.started_at
            self.backfills[table] += 1
        result.setdefault("updated_at", None)
        if table == "rooms":
            result["deleted_at"] = result.pop("archived_at")
        elif table == "channels":
            status, archived_at = result["status"], result["archived_at"]
            if status == "active":
                result["deleted_at"], result["archived_at"] = archived_at, None
            elif status == "archived" and archived_at is not None:
                result["deleted_at"] = None
                self.lifecycle["channels.archived"] += 1
            else:
                raise MigrationError(f"{location}: invalid historical channel status {status!r}")
        if "deleted_at" in result:
            result["is_deleted"] = int(result["deleted_at"] is not None)
            self.lifecycle[f"{table}.deleted"] += int(result["is_deleted"] or 0)
        if table in ID_SCOPES:
            result["id"] = self.lookup(table, row, row["id"], location)
        for column, referenced in REFERENCES.items():
            value = row.get(column)
            if value is not None:
                result[column] = self.lookup(referenced, row, value, f"{location}.{column}")
        if table == "room_events":
            result["entity_id"] = self.event_entity(row, location)
        if table == "messages":
            result["content"] = self.rewrite_images(row, result, assets, location)
        return result

    def copy_tables(
        self, target: sqlite3.Connection, assets: dict[tuple[str, str, str], str]
    ) -> dict[str, dict[str, int]]:
        target.execute("PRAGMA defer_foreign_keys = ON")
        target.execute("DELETE FROM member_roles")
        counts: dict[str, dict[str, int]] = {}
        for table in TABLES:
            columns = [str(column[1]) for column in target.execute(f'PRAGMA table_info("{table}")')]
            insert_columns = columns if table == "room_events" else ["rowid", *columns]
            names = ", ".join(f'"{name}"' for name in insert_columns)
            parameters = ", ".join("?" for _ in insert_columns)
            insert = f'INSERT INTO "{table}" ({names}) VALUES ({parameters})'
            source_count = 0
            for rowid, row in rows(self.source, table):
                location = f"{table}[rowid={rowid}]"
                converted = self.transform(table, row, assets, location)
                difference = converted.keys() ^ columns
                if difference:
                    raise MigrationError(f"{location}: unexpected column difference {difference}")
                values = tuple(converted[column] for column in columns)
                try:
                    target.execute(insert, values if table == "room_events" else (rowid, *values))
                except sqlite3.IntegrityError as error:
                    raise MigrationError(f"{location}: {error}") from error
                source_count += 1
            target_count = target.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
            if source_count != target_count:
                raise MigrationError(
                    f"{table}: row counts differ: {source_count} != {target_count}"
                )
            counts[table] = {"source": source_count, "target": target_count}
        return counts


def preserve_event_cursor(source: sqlite3.Connection, target: sqlite3.Connection) -> int:
    statement = "SELECT seq FROM sqlite_sequence WHERE name = 'room_events'"
    old, new = source.execute(statement).fetchone(), target.execute(statement).fetchone()
    if old is None and new is None:
        return 0
    if old is None or (new is not None and old[0] < new[0]):
        raise MigrationError("room_events: invalid source AUTOINCREMENT high-water mark")
    target.execute("DELETE FROM sqlite_sequence WHERE name = 'room_events'")
    target.execute("INSERT INTO sqlite_sequence(name, seq) VALUES ('room_events', ?)", (old[0],))
    return int(old[0])


def convert(
    source_db: Path, source_images: Path, output: Path, merged_channel: list[str] | None = None
) -> Path:
    source_db = source_db.resolve()
    source_images = source_images.resolve()
    output = output.resolve()
    if not source_db.is_file() or not source_images.is_dir():
        raise MigrationError("Explicit source database file and image directory must already exist")
    if output.exists() or source_db.is_relative_to(output) or output.is_relative_to(source_images):
        raise MigrationError("Output must be a new directory separate from the source assets")
    sidecars = (source_db.with_name(source_db.name + ext) for ext in ("-wal", "-shm", "-journal"))
    if any(path.exists() for path in sidecars):
        raise MigrationError("Source has SQLite sidecars; use a closed, consistent SQLite snapshot")
    if MIGRATION_HEAD != TARGET_REVISION:
        raise MigrationError(f"Expected frozen target {TARGET_REVISION}, found {MIGRATION_HEAD}")
    source_digest = sha256(source_db)
    with closing(sqlite3.connect(f"{source_db.as_uri()}?mode=ro&immutable=1", uri=True)) as source:
        source.row_factory = sqlite3.Row
        require_revision(source, SOURCE_REVISION, "Source")
        source_tables = {
            row[0]
            for row in source.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table' AND name NOT GLOB 'sqlite_*'"
            )
        }
        difference = source_tables ^ {*TABLES, "alembic_version"}
        if difference:
            raise MigrationError(f"Unexpected source tables: {difference}")
        source_checks = check_db(source, "Source")
        conversion = Conversion(source, merged_channel)
        output.mkdir(exist_ok=False)
        assets = conversion.copy_assets(source_images, output / "rooms")
        target_db = output / "conflua.db"
        run_migrations(target_db, resources=ROOT)
        with closing(sqlite3.connect(target_db)) as target:
            target.execute("PRAGMA foreign_keys = ON")
            require_revision(target, TARGET_REVISION, "Target")
            with target:
                target.execute("BEGIN")
                counts = conversion.copy_tables(target, assets)
                high_water = preserve_event_cursor(source, target)
                null_times = target.execute(
                    "SELECT count(*) FROM deliveries WHERE updated_at IS NULL"
                ).fetchone()[0]
                if null_times:
                    raise MigrationError(
                        f"Target deliveries.updated_at contains {null_times} NULL rows"
                    )
                target_checks = check_db(target, "Target")
    if sha256(source_db) != source_digest:
        raise MigrationError("Source database changed during conversion; discard the output")
    report = {
        "source_revision": SOURCE_REVISION,
        "target_revision": TARGET_REVISION,
        "source_database_sha256": source_digest,
        "target_database_sha256": sha256(target_db),
        "source_checks": source_checks,
        "target_checks": target_checks,
        "row_counts": counts,
        "old_key_columns": {table: (*scope, "id") for table, scope in ID_SCOPES.items()},
        "id_mappings": {
            table: [{"old_key": key, "new_id": value} for key, value in mapping.items()]
            for table, mapping in conversion.maps.items()
        },
        "created_at_backfill_value": conversion.started_at,
        "created_at_backfills": dict(conversion.backfills),
        "historical_time_counts": dict(conversion.time_columns),
        "lifecycle_counts": dict(conversion.lifecycle),
        "deliveries_updated_at_null": null_times,
        "room_events_high_water": high_water,
        "merged_event_channels": merged_channel,
        "merged_event_entity_counts": dict(conversion.merged_events),
        "images": {
            "copied_files": len(assets),
            "rewritten_links": conversion.rewritten_images,
            "sha256": [
                {"old_scope_and_id": asset, "sha256": digest} for asset, digest in assets.items()
            ],
        },
    }
    temporary_report = output / "report.json.tmp"
    with temporary_report.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return temporary_report.rename(output / "report.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-db", required=True, type=Path)
    parser.add_argument("--source-images", required=True, type=Path)
    parser.add_argument(
        "--merged-event-channel",
        nargs=3,
        metavar=("ROOM", "DESTINATION", "ORIGIN"),
        help="Resolve historical event entities only for a documented channel merge",
    )
    parser.add_argument("--output", required=True, type=Path, help="New directory (must not exist)")
    args = parser.parse_args()
    try:
        report = convert(args.source_db, args.source_images, args.output, args.merged_event_channel)
    except Exception as error:
        print(json.dumps({"error": str(error), "output_usable": False}), file=sys.stderr)
        return 1
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
