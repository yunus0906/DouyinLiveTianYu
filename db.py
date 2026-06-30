#!/usr/bin/python
# coding:utf-8

"""直播数据 SQLite 持久化封装。"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional


class LiveDatabase:
    """抖音直播数据 SQLite 数据库封装。"""

    def __init__(self, db_path: str | Path) -> None:
        """
        初始化数据库连接并自动建表。

        :param db_path: 当前直播场次的 SQLite 数据库文件路径。
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._enable_pragmas()
        self.create_tables()

    def _enable_pragmas(self) -> None:
        """启用适合实时写入和统计查询的 SQLite 配置。"""
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("PRAGMA foreign_keys=ON")

    def close(self) -> None:
        """关闭数据库连接。"""
        self.conn.close()

    def create_tables(self) -> None:
        """创建直播分析所需的业务表和索引。"""
        schema = """
        CREATE TABLE IF NOT EXISTS event (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time INTEGER NOT NULL,
            room_id TEXT,
            event_type TEXT NOT NULL,
            user_id TEXT,
            username TEXT,
            ref_table TEXT,
            ref_id INTEGER,
            payload TEXT,
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time INTEGER NOT NULL,
            room_id TEXT,
            msg_id TEXT,
            user_id TEXT,
            username TEXT,
            content TEXT NOT NULL,
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS gift (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time INTEGER NOT NULL,
            room_id TEXT,
            msg_id TEXT,
            user_id TEXT,
            username TEXT,
            gift_id TEXT,
            gift_name TEXT,
            gift_count INTEGER NOT NULL DEFAULT 0,
            diamond_count INTEGER NOT NULL DEFAULT 0,
            fan_ticket_count INTEGER NOT NULL DEFAULT 0,
            total_value INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS like (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time INTEGER NOT NULL,
            room_id TEXT,
            msg_id TEXT,
            user_id TEXT,
            username TEXT,
            like_count INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS member (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time INTEGER NOT NULL,
            room_id TEXT,
            msg_id TEXT,
            user_id TEXT,
            username TEXT,
            gender INTEGER,
            enter_type INTEGER,
            action INTEGER,
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS follow (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time INTEGER NOT NULL,
            room_id TEXT,
            msg_id TEXT,
            user_id TEXT,
            username TEXT,
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS fansclub (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time INTEGER NOT NULL,
            room_id TEXT,
            msg_id TEXT,
            user_id TEXT,
            username TEXT,
            fansclub_type INTEGER,
            content TEXT,
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS room_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time INTEGER NOT NULL,
            room_id TEXT,
            msg_id TEXT,
            current_user INTEGER,
            total_user TEXT,
            total_pv TEXT,
            display_short TEXT,
            display_middle TEXT,
            display_long TEXT,
            display_value INTEGER,
            total INTEGER,
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS room_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time INTEGER NOT NULL,
            room_id TEXT,
            msg_id TEXT,
            content TEXT,
            room_message_type INTEGER,
            biz_scene TEXT,
            created_at INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS rank (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time INTEGER NOT NULL,
            room_id TEXT,
            msg_id TEXT,
            rank_type TEXT NOT NULL,
            rank_no INTEGER,
            user_id TEXT,
            username TEXT,
            score TEXT,
            created_at INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_event_time ON event(event_time);
        CREATE INDEX IF NOT EXISTS idx_event_type_time ON event(event_type, event_time);
        CREATE INDEX IF NOT EXISTS idx_event_user_time ON event(user_id, event_time);
        CREATE INDEX IF NOT EXISTS idx_chat_time ON chat(event_time);
        CREATE INDEX IF NOT EXISTS idx_chat_user_time ON chat(user_id, event_time);
        CREATE INDEX IF NOT EXISTS idx_gift_time ON gift(event_time);
        CREATE INDEX IF NOT EXISTS idx_gift_rank ON gift(gift_name, total_value);
        CREATE INDEX IF NOT EXISTS idx_gift_user_value ON gift(user_id, total_value);
        CREATE INDEX IF NOT EXISTS idx_like_user_time ON like(user_id, event_time);
        CREATE INDEX IF NOT EXISTS idx_member_time ON member(event_time);
        CREATE INDEX IF NOT EXISTS idx_follow_user_time ON follow(user_id, event_time);
        CREATE INDEX IF NOT EXISTS idx_fansclub_user_time ON fansclub(user_id, event_time);
        CREATE INDEX IF NOT EXISTS idx_room_stats_time ON room_stats(event_time);
        CREATE INDEX IF NOT EXISTS idx_room_info_time ON room_info(event_time);
        CREATE INDEX IF NOT EXISTS idx_rank_type_time ON rank(rank_type, event_time);
        CREATE INDEX IF NOT EXISTS idx_rank_user_time ON rank(user_id, event_time);
        """
        self.conn.executescript(schema)
        self.conn.commit()

    def execute(self, sql: str, params: tuple[Any, ...]) -> Optional[int]:
        """
        执行单条写入 SQL，并自动提交。

        :param sql: 参数化 SQL 语句。
        :param params: SQL 参数。
        :return: 新增记录 ID；失败时返回 None。
        """
        try:
            cursor = self.conn.execute(sql, params)
            self.conn.commit()
            return int(cursor.lastrowid)
        except sqlite3.Error as exc:
            print(f"【X】数据库写入失败: {exc}")
            return None

    def insert_event(
        self,
        event_type: str,
        event_time: Optional[int] = None,
        room_id: Any = None,
        user_id: Any = None,
        username: str = "",
        ref_table: str = "",
        ref_id: Optional[int] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        写入统一事件流，便于后续做跨类型时间线统计。

        :param event_type: 事件类型，如 chat、gift、pk。
        :param event_time: 事件毫秒时间戳，缺省使用当前时间。
        :param room_id: 直播间 ID。
        :param user_id: 用户 ID。
        :param username: 用户昵称。
        :param ref_table: 关联明细表名。
        :param ref_id: 关联明细表主键。
        :param payload: 扩展 JSON 数据。
        :return: 事件表主键 ID。
        """
        now = self._now_ms()
        return self.execute(
            """
            INSERT INTO event (
                event_time, room_id, event_type, user_id, username,
                ref_table, ref_id, payload, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_time or now,
                self._to_text(room_id),
                event_type,
                self._to_text(user_id),
                username,
                ref_table,
                ref_id,
                self._json(payload),
                now,
            ),
        )

    def insert_chat(
        self,
        event_time: Optional[int],
        room_id: Any,
        msg_id: Any,
        user_id: Any,
        username: str,
        content: str,
    ) -> Optional[int]:
        """写入聊天消息。"""
        now = self._now_ms()
        row_id = self.execute(
            """
            INSERT INTO chat (
                event_time, room_id, msg_id, user_id, username, content, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (event_time or now, self._to_text(room_id), self._to_text(msg_id),
             self._to_text(user_id), username, content, now),
        )
        self._insert_ref_event("chat", event_time, room_id, user_id, username, row_id)
        return row_id

    def insert_gift(
        self,
        event_time: Optional[int],
        room_id: Any,
        msg_id: Any,
        user_id: Any,
        username: str,
        gift_id: Any,
        gift_name: str,
        gift_count: int,
        diamond_count: int = 0,
        fan_ticket_count: int = 0,
    ) -> Optional[int]:
        """写入礼物消息。"""
        now = self._now_ms()
        total_value = int(gift_count or 0) * int(diamond_count or 0)
        row_id = self.execute(
            """
            INSERT INTO gift (
                event_time, room_id, msg_id, user_id, username, gift_id,
                gift_name, gift_count, diamond_count, fan_ticket_count,
                total_value, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_time or now, self._to_text(room_id), self._to_text(msg_id),
             self._to_text(user_id), username, self._to_text(gift_id), gift_name,
             gift_count or 0, diamond_count or 0, fan_ticket_count or 0,
             total_value, now),
        )
        self._insert_ref_event(
            "gift", event_time, room_id, user_id, username, row_id,
            {"gift_name": gift_name, "gift_count": gift_count, "total_value": total_value},
        )
        return row_id

    def insert_like(
        self,
        event_time: Optional[int],
        room_id: Any,
        msg_id: Any,
        user_id: Any,
        username: str,
        like_count: int,
    ) -> Optional[int]:
        """写入点赞消息。"""
        return self._insert_simple_user_event(
            "like", event_time, room_id, msg_id, user_id, username,
            "like_count", like_count or 0,
        )

    def insert_member(
        self,
        event_time: Optional[int],
        room_id: Any,
        msg_id: Any,
        user_id: Any,
        username: str,
        gender: Optional[int],
        enter_type: Optional[int],
        action: Optional[int],
    ) -> Optional[int]:
        """写入用户进入直播间消息。"""
        now = self._now_ms()
        row_id = self.execute(
            """
            INSERT INTO member (
                event_time, room_id, msg_id, user_id, username,
                gender, enter_type, action, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_time or now, self._to_text(room_id), self._to_text(msg_id),
             self._to_text(user_id), username, gender, enter_type, action, now),
        )
        self._insert_ref_event("member", event_time, room_id, user_id, username, row_id)
        return row_id

    def insert_follow(
        self,
        event_time: Optional[int],
        room_id: Any,
        msg_id: Any,
        user_id: Any,
        username: str,
    ) -> Optional[int]:
        """写入关注消息。"""
        now = self._now_ms()
        row_id = self.execute(
            """
            INSERT INTO follow (
                event_time, room_id, msg_id, user_id, username, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_time or now, self._to_text(room_id), self._to_text(msg_id),
             self._to_text(user_id), username, now),
        )
        self._insert_ref_event("follow", event_time, room_id, user_id, username, row_id)
        return row_id

    def insert_fansclub(
        self,
        event_time: Optional[int],
        room_id: Any,
        msg_id: Any,
        user_id: Any,
        username: str,
        fansclub_type: Optional[int],
        content: str,
    ) -> Optional[int]:
        """写入粉丝团消息。"""
        now = self._now_ms()
        row_id = self.execute(
            """
            INSERT INTO fansclub (
                event_time, room_id, msg_id, user_id, username,
                fansclub_type, content, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_time or now, self._to_text(room_id), self._to_text(msg_id),
             self._to_text(user_id), username, fansclub_type, content, now),
        )
        self._insert_ref_event("fansclub", event_time, room_id, user_id, username, row_id)
        return row_id

    def insert_room_stats(
        self,
        event_time: Optional[int],
        room_id: Any,
        msg_id: Any,
        current_user: Optional[int] = None,
        total_user: Any = None,
        total_pv: Any = None,
        display_short: str = "",
        display_middle: str = "",
        display_long: str = "",
        display_value: Optional[int] = None,
        total: Optional[int] = None,
    ) -> Optional[int]:
        """写入直播间统计快照。"""
        now = self._now_ms()
        row_id = self.execute(
            """
            INSERT INTO room_stats (
                event_time, room_id, msg_id, current_user, total_user, total_pv,
                display_short, display_middle, display_long, display_value,
                total, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_time or now, self._to_text(room_id), self._to_text(msg_id),
             current_user, self._to_text(total_user), self._to_text(total_pv),
             display_short, display_middle, display_long, display_value, total, now),
        )
        self._insert_ref_event("room_stats", event_time, room_id, None, "", row_id)
        return row_id

    def insert_room_info(
        self,
        event_time: Optional[int],
        room_id: Any,
        msg_id: Any,
        content: str = "",
        room_message_type: Optional[int] = None,
        biz_scene: str = "",
    ) -> Optional[int]:
        """写入直播间信息消息。"""
        now = self._now_ms()
        row_id = self.execute(
            """
            INSERT INTO room_info (
                event_time, room_id, msg_id, content,
                room_message_type, biz_scene, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (event_time or now, self._to_text(room_id), self._to_text(msg_id),
             content, room_message_type, biz_scene, now),
        )
        self._insert_ref_event("room_info", event_time, room_id, None, "", row_id)
        return row_id

    def insert_rank(
        self,
        event_time: Optional[int],
        room_id: Any,
        msg_id: Any,
        rank_type: str,
        rank_no: Optional[int],
        user_id: Any,
        username: str,
        score: Any,
    ) -> Optional[int]:
        """写入排行榜单项。"""
        now = self._now_ms()
        row_id = self.execute(
            """
            INSERT INTO rank (
                event_time, room_id, msg_id, rank_type, rank_no,
                user_id, username, score, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (event_time or now, self._to_text(room_id), self._to_text(msg_id),
             rank_type, rank_no, self._to_text(user_id), username,
             self._to_text(score), now),
        )
        self._insert_ref_event("rank", event_time, room_id, user_id, username, row_id)
        return row_id

    def insert_control(
        self,
        event_time: Optional[int],
        room_id: Any,
        msg_id: Any,
        status: int,
    ) -> Optional[int]:
        """写入直播控制事件，例如直播结束。"""
        return self.insert_event(
            event_type="control",
            event_time=event_time,
            room_id=room_id,
            ref_table="event",
            payload={"msg_id": self._to_text(msg_id), "status": status},
        )

    def _insert_simple_user_event(
        self,
        table: str,
        event_time: Optional[int],
        room_id: Any,
        msg_id: Any,
        user_id: Any,
        username: str,
        count_column: str,
        count_value: int,
    ) -> Optional[int]:
        """写入只包含用户和计数字段的简单事件。"""
        now = self._now_ms()
        row_id = self.execute(
            f"""
            INSERT INTO {table} (
                event_time, room_id, msg_id, user_id, username,
                {count_column}, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (event_time or now, self._to_text(room_id), self._to_text(msg_id),
             self._to_text(user_id), username, count_value, now),
        )
        self._insert_ref_event(table, event_time, room_id, user_id, username, row_id)
        return row_id

    def _insert_ref_event(
        self,
        event_type: str,
        event_time: Optional[int],
        room_id: Any,
        user_id: Any,
        username: str,
        row_id: Optional[int],
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        """为明细表写入对应的统一事件流。"""
        if row_id is None:
            return
        self.insert_event(
            event_type=event_type,
            event_time=event_time,
            room_id=room_id,
            user_id=user_id,
            username=username,
            ref_table=event_type,
            ref_id=row_id,
            payload=payload,
        )

    @staticmethod
    def _now_ms() -> int:
        """返回当前毫秒级时间戳。"""
        return int(time.time() * 1000)

    @staticmethod
    def _to_text(value: Any) -> Optional[str]:
        """将 ID 等字段统一转换为文本，避免大整数精度和类型差异。"""
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _json(payload: Optional[dict[str, Any]]) -> Optional[str]:
        """将扩展数据编码为 JSON 文本。"""
        if payload is None:
            return None
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
