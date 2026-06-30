#!/usr/bin/python
# coding:utf-8

"""单场直播会话目录、配置和日志管理。"""

import json
import logging
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TextIO


class _TeeStream:
    """同时写入控制台和日志文件，兼容项目中已有的 print 输出。"""

    def __init__(self, console: TextIO, log_file: TextIO) -> None:
        self.console = console
        self.log_file = log_file

    def write(self, message: str) -> int:
        self.console.write(message)
        self.log_file.write(message)
        self.flush()
        return len(message)

    def flush(self) -> None:
        self.console.flush()
        self.log_file.flush()


@dataclass
class LiveSession:
    """封装单场直播的工作目录、数据库路径、配置文件和日志。"""

    room_id: str | None = None
    anchor_name: str = ""
    title: str = ""
    data_root: Path = Path("data")
    start_time: datetime = field(default_factory=datetime.now)

    workspace: Path = field(init=False)
    db_path: Path = field(init=False)
    report_path: Path = field(init=False)
    summary_path: Path = field(init=False)
    ai_analysis_path: Path = field(init=False)
    config_path: Path = field(init=False)
    screenshots_path: Path = field(init=False)
    clips_path: Path = field(init=False)
    logs_path: Path = field(init=False)
    log_path: Path = field(init=False)

    _stdout: TextIO | None = field(default=None, init=False, repr=False)
    _stderr: TextIO | None = field(default=None, init=False, repr=False)
    _log_file: TextIO | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        """初始化目录结构，并写入 recording 状态的 config.json。"""
        room_name = self._safe_room_id(self.room_id)
        day_name = self.start_time.strftime("%Y-%m-%d")
        start_name = self.start_time.strftime("%Y%m%d_%H%M%S")

        self.workspace = self.data_root / day_name / f"{room_name}_{start_name}"
        self.db_path = self.workspace / "live.db"
        self.report_path = self.workspace / "report.md"
        self.summary_path = self.workspace / "summary.json"
        self.ai_analysis_path = self.workspace / "ai_analysis.md"
        self.config_path = self.workspace / "config.json"
        self.screenshots_path = self.workspace / "screenshots"
        self.clips_path = self.workspace / "clips"
        self.logs_path = self.workspace / "logs"
        self.log_path = self.logs_path / "record.log"

        self.create_workspace()
        self.write_config(status="recording")

    def create_workspace(self) -> None:
        """创建单场直播所需的全部目录和占位文件。"""
        self.screenshots_path.mkdir(parents=True, exist_ok=True)
        self.clips_path.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)
        self.report_path.touch(exist_ok=True)
        self.ai_analysis_path.touch(exist_ok=True)

        if not self.summary_path.exists():
            self.summary_path.write_text("{}\n", encoding="utf-8")

    def setup_logging(self) -> None:
        """把运行日志写入当前场次 logs/record.log，同时保留控制台输出。"""
        if self._log_file is not None:
            return

        self._stdout = sys.stdout
        self._stderr = sys.stderr
        self._log_file = self.log_path.open("a", encoding="utf-8")
        sys.stdout = _TeeStream(self._stdout, self._log_file)  # type: ignore[assignment]
        sys.stderr = _TeeStream(self._stderr, self._log_file)  # type: ignore[assignment]

        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.FileHandler(self.log_path, encoding="utf-8")],
            force=True,
        )

    def write_config(self, status: str, end_time: datetime | None = None) -> None:
        """写入或更新当前场次 config.json。"""
        config = self._read_config()
        config.update(
            {
                "room_id": self.room_id or "unknown",
                "anchor_name": self.anchor_name,
                "title": self.title,
                "start_time": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": "" if end_time is None else end_time.strftime("%Y-%m-%d %H:%M:%S"),
                "status": status,
            }
        )
        self.config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=4) + "\n",
            encoding="utf-8",
        )

    def update_room_info(
        self,
        room_id: str | None = None,
        anchor_name: str | None = None,
        title: str | None = None,
    ) -> None:
        """运行中补充真实房间 ID、主播名或标题，不移动已创建的目录。"""
        if room_id:
            self.room_id = str(room_id)
        if anchor_name is not None:
            self.anchor_name = anchor_name
        if title is not None:
            self.title = title
        self.write_config(status=self._read_config().get("status", "recording"))

    def finish(self) -> None:
        """直播结束时标记完成，并恢复标准输出。"""
        self.write_config(status="finished", end_time=datetime.now())
        self.close_logging()

    def close_logging(self) -> None:
        """关闭日志文件并恢复原始 stdout/stderr。"""
        if self._log_file is None:
            return

        if self._stdout is not None:
            sys.stdout = self._stdout
        if self._stderr is not None:
            sys.stderr = self._stderr
        self._log_file.close()
        self._log_file = None

    def _read_config(self) -> dict[str, str]:
        """读取已有配置，文件不存在或损坏时返回空配置。"""
        if not self.config_path.exists():
            return {}
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _safe_room_id(room_id: str | None) -> str:
        """清理目录名中的非法字符；房间号缺失时使用 unknown。"""
        if not room_id:
            return "unknown"
        safe = "".join(char for char in str(room_id) if char.isalnum() or char in "_-")
        return safe or "unknown"
