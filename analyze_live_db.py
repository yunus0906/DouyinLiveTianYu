#!/usr/bin/python
# coding:utf-8

"""统计单场抖音直播 SQLite 数据。"""

import argparse
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable, Sequence


USER_TABLES = ("chat", "gift", "like", "member", "follow", "fansclub", "rank")
EVENT_TABLES = ("chat", "gift", "like", "member", "follow", "fansclub", "room_stats", "room_info", "rank")
STOP_WORDS = {
    "的", "了", "是", "我", "你", "他", "她", "它", "们", "啊", "呀", "吧", "吗", "呢", "哈", "哈哈",
    "这个", "那个", "就是", "不是", "可以", "没有", "什么", "怎么", "一下", "一个", "还是", "直播",
}


class LiveDbAnalyzer:
    """读取 live.db 并生成统计结果。"""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = self._resolve_db_path(Path(db_path))
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.tables = self._load_tables()

    def close(self) -> None:
        self.conn.close()

    def analyze(self, limit: int = 30) -> dict[str, object]:
        """返回完整统计数据。"""
        return {
            "database": str(self.db_path),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "overview": self.overview(),
            "gift_by_user": self.gift_by_user(limit),
            "gift_by_name": self.gift_by_name(limit),
            "chat_by_user": self.chat_by_user(limit),
            "most_active_minutes": self.most_active_minutes(limit),
            "gift_curve": self.gift_curve(),
            "online_curve": self.online_curve(),
            "user_stay_duration": self.user_stay_duration(limit),
            "high_frequency_words": self.high_frequency_words(limit),
            "high_frequency_phrases": self.high_frequency_phrases(limit),
        }

    def overview(self) -> dict[str, object]:
        """核心概览。"""
        start_time, end_time = self._recording_time_range()
        current_online_peak = self._scalar("SELECT MAX(current_user) FROM room_stats") if "room_stats" in self.tables else 0
        last_room_stats = self._one(
            """
            SELECT current_user, total_user, total_pv, display_long, display_value, total
            FROM room_stats
            ORDER BY event_time DESC, id DESC
            LIMIT 1
            """
        ) if "room_stats" in self.tables else None

        return {
            "start_time": self._format_time(start_time),
            "end_time": self._format_time(end_time),
            "duration_seconds": max(0, int((end_time - start_time) / 1000)) if start_time and end_time else 0,
            "unique_users": self.unique_user_count(),
            "chat_count": self._count("chat"),
            "gift_message_count": self._count("gift"),
            "gift_count": self._scalar("SELECT SUM(gift_count) FROM gift"),
            "gift_value": self._scalar("SELECT SUM(total_value) FROM gift"),
            "like_count": self._scalar("SELECT SUM(like_count) FROM like"),
            "enter_count": self._count("member"),
            "follow_count": self._count("follow"),
            "fansclub_count": self._count("fansclub"),
            "peak_current_online": current_online_peak,
            "last_current_online": dict(last_room_stats) if last_room_stats else {},
        }

    def unique_user_count(self) -> int:
        """统计所有用户表中出现过的去重用户数。"""
        selects = []
        for table in USER_TABLES:
            if table in self.tables and self._has_columns(table, "user_id"):
                selects.append(f"SELECT user_id FROM {table} WHERE user_id IS NOT NULL AND user_id != ''")
        if not selects:
            return 0
        return self._scalar(f"SELECT COUNT(DISTINCT user_id) FROM ({' UNION ALL '.join(selects)})")

    def gift_by_user(self, limit: int) -> list[dict[str, object]]:
        """谁送了多少礼物。"""
        return self._dict_rows(
            """
            SELECT user_id,
                   COALESCE(NULLIF(username, ''), user_id, '未知用户') AS username,
                   SUM(gift_count) AS gift_count,
                   SUM(total_value) AS total_value,
                   COUNT(*) AS gift_messages,
                   GROUP_CONCAT(DISTINCT gift_name) AS gift_names
            FROM gift
            GROUP BY user_id, username
            ORDER BY total_value DESC, gift_count DESC, gift_messages DESC
            LIMIT ?
            """,
            (limit,),
        )

    def gift_by_name(self, limit: int) -> list[dict[str, object]]:
        """礼物类型统计。"""
        return self._dict_rows(
            """
            SELECT COALESCE(NULLIF(gift_name, ''), gift_id, '未知礼物') AS gift_name,
                   SUM(gift_count) AS gift_count,
                   SUM(total_value) AS total_value,
                   COUNT(*) AS gift_messages
            FROM gift
            GROUP BY COALESCE(NULLIF(gift_name, ''), gift_id, '未知礼物')
            ORDER BY total_value DESC, gift_count DESC, gift_messages DESC
            LIMIT ?
            """,
            (limit,),
        )

    def chat_by_user(self, limit: int) -> list[dict[str, object]]:
        """谁说了多少话。"""
        return self._dict_rows(
            """
            SELECT user_id,
                   COALESCE(NULLIF(username, ''), user_id, '未知用户') AS username,
                   COUNT(*) AS chat_count
            FROM chat
            GROUP BY user_id, username
            ORDER BY chat_count DESC
            LIMIT ?
            """,
            (limit,),
        )

    def most_active_minutes(self, limit: int) -> list[dict[str, object]]:
        """按分钟统计最活跃时间段。"""
        unions = []
        for table in EVENT_TABLES:
            if table in self.tables and self._has_columns(table, "event_time"):
                weight = "COALESCE(like_count, 0)" if table == "like" else "1"
                event_name = "room_stats" if table == "room_stats" else table
                event_time_ms = self._timestamp_ms_sql("event_time")
                unions.append(
                    f"SELECT ({event_time_ms} / 60000) * 60000 AS minute_ts, '{event_name}' AS event_type, {weight} AS weight FROM {table}"
                )
        if not unions:
            return []
        rows = self._rows(
            f"""
            SELECT minute_ts,
                   COUNT(*) AS event_count,
                   SUM(CASE WHEN event_type = 'chat' THEN 1 ELSE 0 END) AS chat_count,
                   SUM(CASE WHEN event_type = 'gift' THEN 1 ELSE 0 END) AS gift_messages,
                   SUM(CASE WHEN event_type = 'like' THEN weight ELSE 0 END) AS like_count,
                   SUM(CASE WHEN event_type = 'member' THEN 1 ELSE 0 END) AS enter_count,
                   SUM(CASE WHEN event_type = 'follow' THEN 1 ELSE 0 END) AS follow_count,
                   SUM(CASE WHEN event_type = 'fansclub' THEN 1 ELSE 0 END) AS fansclub_count
            FROM ({' UNION ALL '.join(unions)})
            GROUP BY minute_ts
            ORDER BY event_count DESC, chat_count DESC, gift_messages DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [self._with_minute(row) for row in rows]

    def gift_curve(self) -> list[dict[str, object]]:
        """礼物曲线，按分钟聚合。"""
        return [
            self._with_minute(row)
            for row in self._rows(
                f"""
                SELECT ({self._timestamp_ms_sql('event_time')} / 60000) * 60000 AS minute_ts,
                       SUM(gift_count) AS gift_count,
                       SUM(total_value) AS total_value,
                       COUNT(*) AS gift_messages
                FROM gift
                GROUP BY minute_ts
                ORDER BY minute_ts ASC
                """
            )
        ]

    def online_curve(self) -> list[dict[str, object]]:
        """在线人数曲线，按分钟聚合。"""
        return [
            self._with_minute(row)
            for row in self._rows(
                f"""
                SELECT ({self._timestamp_ms_sql('event_time')} / 60000) * 60000 AS minute_ts,
                       MAX(current_user) AS max_current_user,
                       CAST(AVG(current_user) AS INTEGER) AS avg_current_user,
                       COUNT(*) AS sample_count
                FROM room_stats
                WHERE current_user IS NOT NULL
                GROUP BY minute_ts
                ORDER BY minute_ts ASC
                """
            )
        ]

    def user_stay_duration(self, limit: int) -> list[dict[str, object]]:
        """用户停留时长估算：用户首次出现到末次出现的时间差。"""
        selects = []
        for table in USER_TABLES:
            if table in self.tables and self._has_columns(table, "event_time", "user_id", "username"):
                event_time_ms = self._timestamp_ms_sql("event_time")
                selects.append(
                    f"""
                    SELECT {event_time_ms} AS event_time, user_id, username, '{table}' AS source
                    FROM {table}
                    WHERE user_id IS NOT NULL AND user_id != ''
                    """
                )
        if not selects:
            return []
        rows = self._rows(
            f"""
            SELECT user_id,
                   COALESCE(NULLIF(MAX(username), ''), user_id) AS username,
                   MIN(event_time) AS first_seen,
                   MAX(event_time) AS last_seen,
                   COUNT(*) AS event_count,
                   SUM(CASE WHEN source = 'chat' THEN 1 ELSE 0 END) AS chat_count,
                   SUM(CASE WHEN source = 'gift' THEN 1 ELSE 0 END) AS gift_messages
            FROM ({' UNION ALL '.join(selects)})
            GROUP BY user_id
            ORDER BY (last_seen - first_seen) DESC, event_count DESC
            LIMIT ?
            """,
            (limit,),
        )
        result = []
        for row in rows:
            item = dict(row)
            seconds = max(0, int((item["last_seen"] - item["first_seen"]) / 1000))
            item["first_seen_text"] = self._format_time(item["first_seen"])
            item["last_seen_text"] = self._format_time(item["last_seen"])
            item["stay_seconds"] = seconds
            item["stay_text"] = self._format_seconds(seconds)
            result.append(item)
        return result

    def high_frequency_words(self, limit: int) -> list[dict[str, object]]:
        """聊天高频词。优先使用 jieba；没有安装时用内置简易分词。"""
        counter: Counter[str] = Counter()
        for content in self._chat_contents():
            counter.update(self._tokenize_words(content))
        return [{"word": word, "count": count} for word, count in counter.most_common(limit)]

    def high_frequency_phrases(self, limit: int) -> list[dict[str, object]]:
        """聊天高频短语，按连续中文 2-4 字片段统计。"""
        counter: Counter[str] = Counter()
        for content in self._chat_contents():
            text = re.sub(r"\s+", "", content)
            for segment in re.findall(r"[\u4e00-\u9fff]{2,}", text):
                max_size = min(4, len(segment))
                for size in range(2, max_size + 1):
                    for index in range(0, len(segment) - size + 1):
                        phrase = segment[index:index + size]
                        if phrase not in STOP_WORDS:
                            counter[phrase] += 1
        return [{"phrase": phrase, "count": count} for phrase, count in counter.most_common(limit)]

    def write_markdown(self, stats: dict[str, object], output_path: str | Path) -> None:
        """输出 Markdown 报告。"""
        output = Path(output_path)
        lines = [
            "# 直播 SQLite 数据统计",
            "",
            f"数据库：`{stats['database']}`",
            f"生成时间：{stats['generated_at']}",
            "",
            "## 核心指标",
            "",
        ]
        overview = stats["overview"]
        assert isinstance(overview, dict)
        lines.extend(
            [
                f"- 开始时间：{overview.get('start_time', '')}",
                f"- 结束时间：{overview.get('end_time', '')}",
                f"- 直播时长：{self._format_seconds(int(overview.get('duration_seconds') or 0))}",
                f"- 出现过的去重用户数：{overview.get('unique_users', 0)}",
                f"- 聊天消息数：{overview.get('chat_count', 0)}",
                f"- 礼物消息数：{overview.get('gift_message_count', 0)}",
                f"- 礼物总数：{overview.get('gift_count', 0)}",
                f"- 礼物总价值：{overview.get('gift_value', 0)}",
                f"- 点赞数：{overview.get('like_count', 0)}",
                f"- 进场消息数：{overview.get('enter_count', 0)}",
                f"- 关注数：{overview.get('follow_count', 0)}",
                f"- 粉丝团消息数：{overview.get('fansclub_count', 0)}",
                f"- 当前在线峰值：{overview.get('peak_current_online', 0)}",
                "",
                "说明：用户停留时长按用户首次出现和末次出现估算，当前表结构没有明确离场事件。",
                "",
            ]
        )
        sections = [
            ("谁送了多少礼物", ["用户ID", "昵称", "礼物数", "价值", "礼物消息", "礼物名"], stats["gift_by_user"], ["user_id", "username", "gift_count", "total_value", "gift_messages", "gift_names"]),
            ("礼物类型统计", ["礼物", "数量", "价值", "消息数"], stats["gift_by_name"], ["gift_name", "gift_count", "total_value", "gift_messages"]),
            ("谁说了多少话", ["用户ID", "昵称", "发言数"], stats["chat_by_user"], ["user_id", "username", "chat_count"]),
            ("哪一分钟最活跃", ["分钟", "事件数", "聊天", "礼物消息", "点赞", "进场", "关注", "粉丝团"], stats["most_active_minutes"], ["minute", "event_count", "chat_count", "gift_messages", "like_count", "enter_count", "follow_count", "fansclub_count"]),
            ("礼物曲线", ["分钟", "礼物数", "价值", "礼物消息"], stats["gift_curve"], ["minute", "gift_count", "total_value", "gift_messages"]),
            ("在线人数曲线", ["分钟", "最高在线", "平均在线", "样本数"], stats["online_curve"], ["minute", "max_current_user", "avg_current_user", "sample_count"]),
            ("用户停留时长", ["用户ID", "昵称", "首次出现", "末次出现", "估算停留", "事件数", "聊天", "礼物消息"], stats["user_stay_duration"], ["user_id", "username", "first_seen_text", "last_seen_text", "stay_text", "event_count", "chat_count", "gift_messages"]),
            ("高频词", ["词", "次数"], stats["high_frequency_words"], ["word", "count"]),
            ("高频短语", ["短语", "次数"], stats["high_frequency_phrases"], ["phrase", "count"]),
        ]
        for title, headers, rows, keys in sections:
            lines.extend([f"## {title}", "", self._markdown_table(headers, rows, keys), ""])
        output.write_text("\n".join(lines), encoding="utf-8")

    def _load_tables(self) -> set[str]:
        rows = self._rows("SELECT name FROM sqlite_master WHERE type = 'table'")
        return {str(row["name"]) for row in rows}

    def _has_columns(self, table: str, *columns: str) -> bool:
        rows = self._rows(f"PRAGMA table_info({table})")
        existing = {str(row["name"]) for row in rows}
        return all(column in existing for column in columns)

    def _time_range(self) -> tuple[int, int]:
        selects = []
        for table in EVENT_TABLES:
            if table in self.tables and self._has_columns(table, "event_time"):
                selects.append(f"SELECT {self._timestamp_ms_sql('event_time')} AS event_time FROM {table}")
        if not selects:
            return 0, 0
        row = self._one(f"SELECT MIN(event_time) AS start_time, MAX(event_time) AS end_time FROM ({' UNION ALL '.join(selects)})")
        if not row:
            return 0, 0
        return int(row["start_time"] or 0), int(row["end_time"] or 0)

    def _recording_time_range(self) -> tuple[int, int]:
        selects = []
        for table in EVENT_TABLES:
            if table in self.tables and self._has_columns(table, "created_at"):
                selects.append(f"SELECT {self._timestamp_ms_sql('created_at')} AS event_time FROM {table}")
        if not selects:
            return self._time_range()
        row = self._one(f"SELECT MIN(event_time) AS start_time, MAX(event_time) AS end_time FROM ({' UNION ALL '.join(selects)})")
        if not row:
            return 0, 0
        return int(row["start_time"] or 0), int(row["end_time"] or 0)

    def _chat_contents(self) -> Iterable[str]:
        if "chat" not in self.tables:
            return []
        return (str(row["content"] or "") for row in self._rows("SELECT content FROM chat WHERE content != ''"))

    def _tokenize_words(self, content: str) -> list[str]:
        try:
            import jieba  # type: ignore

            words = [word.strip() for word in jieba.cut(content) if word.strip()]
        except ImportError:
            words = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z0-9_]{2,}", content)
        return [word for word in words if len(word) >= 2 and word not in STOP_WORDS]

    def _count(self, table: str) -> int:
        if table not in self.tables:
            return 0
        return self._scalar(f"SELECT COUNT(*) FROM {table}")

    def _scalar(self, sql: str, params: Sequence[object] = ()) -> int:
        row = self._one(sql, params)
        if not row:
            return 0
        value = row[0]
        return int(value or 0)

    def _rows(self, sql: str, params: Sequence[object] = ()) -> list[sqlite3.Row]:
        return list(self.conn.execute(sql, tuple(params)).fetchall())

    def _one(self, sql: str, params: Sequence[object] = ()) -> sqlite3.Row | None:
        return self.conn.execute(sql, tuple(params)).fetchone()

    def _dict_rows(self, sql: str, params: Sequence[object] = ()) -> list[dict[str, object]]:
        return [dict(row) for row in self._rows(sql, params)]

    def _with_minute(self, row: sqlite3.Row) -> dict[str, object]:
        item = dict(row)
        item["minute"] = self._format_time(int(item.get("minute_ts") or 0), minute=True)
        return item

    @staticmethod
    def _timestamp_ms_sql(column: str) -> str:
        return f"CASE WHEN {column} > 10000000000 THEN {column} ELSE {column} * 1000 END"

    @staticmethod
    def _markdown_table(headers: list[str], rows: object, keys: list[str]) -> str:
        assert isinstance(rows, list)
        body = []
        for row in rows:
            assert isinstance(row, dict)
            body.append(["" if row.get(key) is None else str(row.get(key)) for key in keys])
        if not body:
            body = [["暂无数据"] + [""] * (len(headers) - 1)]
        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
        ]
        lines.extend("| " + " | ".join(row) + " |" for row in body)
        return "\n".join(lines)

    @staticmethod
    def _format_time(value: int, minute: bool = False) -> str:
        if not value:
            return ""
        timestamp = value / 1000 if value > 10_000_000_000 else value
        pattern = "%Y-%m-%d %H:%M" if minute else "%Y-%m-%d %H:%M:%S"
        return datetime.fromtimestamp(timestamp).strftime(pattern)

    @staticmethod
    def _format_seconds(seconds: int) -> str:
        hours, rest = divmod(max(0, seconds), 3600)
        minutes, secs = divmod(rest, 60)
        if hours:
            return f"{hours}小时{minutes}分{secs}秒"
        if minutes:
            return f"{minutes}分{secs}秒"
        return f"{secs}秒"

    @staticmethod
    def _resolve_db_path(path: Path) -> Path:
        if path.is_dir():
            path = path / "live.db"
        if not path.exists():
            raise FileNotFoundError(f"找不到 SQLite 数据库: {path}")
        return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="统计直播 live.db，生成 Markdown/JSON 报告。")
    parser.add_argument("db", help="live.db 路径，或包含 live.db 的场次目录")
    parser.add_argument("-o", "--output", help="Markdown 输出路径；默认写到数据库同目录 analysis.md")
    parser.add_argument("--json", dest="json_output", help="可选：同时输出 JSON 明细")
    parser.add_argument("--limit", type=int, default=30, help="排行榜/词频输出条数，默认 30")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    analyzer = LiveDbAnalyzer(args.db)
    try:
        stats = analyzer.analyze(limit=args.limit)
        output = Path(args.output) if args.output else analyzer.db_path.with_name("analysis.md")
        analyzer.write_markdown(stats, output)
        if args.json_output:
            Path(args.json_output).write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"已生成统计报告: {output}")
        if args.json_output:
            print(f"已生成 JSON 明细: {args.json_output}")
    finally:
        analyzer.close()


if __name__ == "__main__":
    main()
