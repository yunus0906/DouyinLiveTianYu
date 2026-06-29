#!/usr/bin/python
# coding:utf-8

"""直播 SQLite 数据统计报表示例。"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

from db import LiveDatabase


class LiveReport:
    """基于 SQLite 的直播数据统计报表。"""

    def __init__(self, db_path: str = "data/live.db") -> None:
        """
        初始化报表读取器。

        :param db_path: SQLite 数据库文件路径。
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            LiveDatabase(str(self.db_path)).close()
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        """关闭数据库连接。"""
        self.conn.close()

    def scalar(self, sql: str) -> int:
        """
        查询单个整数统计值。

        :param sql: 统计 SQL。
        :return: 查询结果，空值按 0 处理。
        """
        row = self.conn.execute(sql).fetchone()
        return int(row[0] or 0)

    def rows(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        """
        查询多行统计结果。

        :param sql: 查询 SQL。
        :param params: SQL 参数。
        :return: 行对象列表。
        """
        return list(self.conn.execute(sql, params).fetchall())

    def chat_count(self) -> int:
        """统计聊天消息数量。"""
        return self.scalar("SELECT COUNT(*) FROM chat")

    def gift_count(self) -> int:
        """统计礼物消息数量。"""
        return self.scalar("SELECT COUNT(*) FROM gift")

    def gift_rank(self, limit: int = 10) -> list[sqlite3.Row]:
        """统计礼物排行榜。"""
        return self.rows(
            """
            SELECT gift_name,
                   SUM(gift_count) AS gift_count,
                   SUM(total_value) AS total_value
            FROM gift
            GROUP BY gift_name
            ORDER BY total_value DESC, gift_count DESC
            LIMIT ?
            """,
            (limit,),
        )

    def user_contribution_rank(self, limit: int = 10) -> list[sqlite3.Row]:
        """统计用户贡献榜，按礼物总价值排序。"""
        return self.rows(
            """
            SELECT user_id,
                   username,
                   SUM(gift_count) AS gift_count,
                   SUM(total_value) AS total_value
            FROM gift
            GROUP BY user_id, username
            ORDER BY total_value DESC, gift_count DESC
            LIMIT ?
            """,
            (limit,),
        )

    def online_timeline(self, limit: int = 20) -> list[sqlite3.Row]:
        """读取在线人数变化时间线。"""
        return self.rows(
            """
            SELECT event_time, current_user, total_user, total_pv, display_long
            FROM room_stats
            WHERE current_user IS NOT NULL OR display_long != ''
            ORDER BY event_time ASC
            LIMIT ?
            """,
            (limit,),
        )

    def pk_timeline(self, limit: int = 20) -> list[sqlite3.Row]:
        """读取 PK 事件时间线，未来接入 PK 解析后自动可用。"""
        return self.rows(
            """
            SELECT event_time, event_type, username, payload
            FROM event
            WHERE event_type LIKE 'pk%'
            ORDER BY event_time ASC
            LIMIT ?
            """,
            (limit,),
        )

    def generate_markdown(self, output_path: str = "report.md") -> None:
        """
        生成 Markdown 统计报告。

        :param output_path: 输出 Markdown 文件路径。
        """
        lines = [
            "# 直播数据统计报告",
            "",
            f"生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## 核心指标",
            "",
            f"- 聊天数量：{self.chat_count()}",
            f"- 礼物数量：{self.gift_count()}",
            "",
            "## 礼物排行榜",
            "",
            self._table(
                ["礼物", "数量", "价值"],
                ([row["gift_name"], row["gift_count"], row["total_value"]]
                 for row in self.gift_rank()),
            ),
            "",
            "## 用户贡献榜",
            "",
            self._table(
                ["用户ID", "昵称", "礼物数", "价值"],
                ([row["user_id"], row["username"], row["gift_count"], row["total_value"]]
                 for row in self.user_contribution_rank()),
            ),
            "",
            "## 在线人数变化",
            "",
            self._table(
                ["时间", "当前在线", "累计用户", "累计 PV", "展示文本"],
                ([self._format_ms(row["event_time"]), row["current_user"], row["total_user"],
                  row["total_pv"], row["display_long"]]
                 for row in self.online_timeline()),
            ),
            "",
            "## PK 时间轴",
            "",
            self._table(
                ["时间", "事件", "用户", "扩展数据"],
                ([self._format_ms(row["event_time"]), row["event_type"], row["username"],
                  row["payload"]]
                 for row in self.pk_timeline()),
            ),
            "",
        ]
        Path(output_path).write_text("\n".join(lines), encoding="utf-8")

    @staticmethod
    def _table(headers: list[str], rows: Iterable[list[object]]) -> str:
        """将行数据转换为 Markdown 表格。"""
        body = [["" if item is None else str(item) for item in row] for row in rows]
        if not body:
            body = [["暂无数据" for _ in headers]]
        lines = [
            "| " + " | ".join(headers) + " |",
            "| " + " | ".join(["---"] * len(headers)) + " |",
        ]
        lines.extend("| " + " | ".join(row) + " |" for row in body)
        return "\n".join(lines)

    @staticmethod
    def _format_ms(value: int) -> str:
        """格式化毫秒时间戳。"""
        if not value:
            return ""
        return datetime.fromtimestamp(value / 1000).strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    """生成默认直播统计报告。"""
    report = LiveReport()
    try:
        report.generate_markdown()
    finally:
        report.close()


if __name__ == "__main__":
    main()
