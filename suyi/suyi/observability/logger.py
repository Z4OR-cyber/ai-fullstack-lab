"""结构化日志 — JSON 格式日志，支持上下文追踪和日志轮转.

特性:
    - JSON 格式输出，便于日志聚合工具解析
    - 上下文追踪：session_id, request_id, agent_name
    - 日志级别：DEBUG / INFO / WARN / ERROR
    - 日志输出：文件 + 控制台
    - 日志轮转：按大小（RotatingFileHandler）和按时间（TimedRotatingFileHandler）

设计原则:
    - 纯 Python 标准库 logging，不依赖第三方库
    - 每条日志是一个 JSON 对象，包含 timestamp, level, message 和上下文字段
    - 支持通过 with_context() 创建带固定上下文的子 logger
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional


# ── 日志级别常量 ──────────────────────────────────────────────

class LogLevel:
    """日志级别常量.

    使用字符串常量而非直接引用 logging 常量，
    以便在不导入 logging 的情况下也能使用.
    """

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"

    @classmethod
    def to_numeric(cls, level: str) -> int:
        """将字符串日志级别转为 logging 数字常量.

        Args:
            level: 字符串日志级别（DEBUG/INFO/WARN/ERROR）.

        Returns:
            logging 模块的数字常量.
        """
        mapping: Dict[str, int] = {
            cls.DEBUG: logging.DEBUG,
            cls.INFO: logging.INFO,
            cls.WARN: logging.WARNING,
            cls.ERROR: logging.ERROR,
        }
        return mapping.get(level.upper(), logging.INFO)


class JsonFormatter(logging.Formatter):
    """JSON 日志格式化器.

    将 LogRecord 格式化为 JSON 字符串，
    包含 timestamp, level, message 和所有 extra 字段.
    """

    # LogRecord 自带属性，不作为 extra 输出
    _BUILTIN_ATTRS: frozenset = frozenset({
        "name", "msg", "args", "levelname", "levelno", "pathname",
        "filename", "module", "exc_info", "exc_text", "stack_info",
        "lineno", "funcName", "created", "msecs", "relativeCreated",
        "thread", "threadName", "processName", "process", "message",
        "asctime", "taskName",
    })

    def format(self, record: logging.LogRecord) -> str:
        """将 LogRecord 格式化为 JSON 字符串.

        Args:
            record: 日志记录.

        Returns:
            JSON 格式的日志字符串.
        """
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # 添加 extra 字段
        for key, value in record.__dict__.items():
            if key not in self._BUILTIN_ATTRS and not key.startswith("_"):
                log_entry[key] = value

        # 异常信息
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class StructuredLogger:
    """结构化日志记录器.

    输出 JSON 格式日志，支持上下文追踪（session_id, request_id, agent_name）
    和日志轮转（按大小 / 按时间）.

    Args:
        name:        logger 名称（默认 'suyi'）.
        session_id:  会话 ID（自动生成如未提供）.
        agent_name:  Agent 名称.
        log_file:    日志文件路径（None 则仅输出到控制台）.
        level:       日志级别字符串（DEBUG/INFO/WARN/ERROR）.
        max_bytes:   日志文件最大字节数（按大小轮转，0 表示不轮转）.
        backup_count: 保留的备份文件数.
        when:        按时间轮转的单位（'S'/'M'/'H'/'D'/'midnight'）.
                     设置后优先使用按时间轮转.
        console:     是否同时输出到控制台（默认 True）.

    使用示例::

        logger = StructuredLogger(
            session_id="abc123",
            log_file="logs/agent.json",
            level="DEBUG",
        )
        logger.info("User message received", extra={"user_input": "hello"})
        logger.error("Tool failed", extra={"tool": "bash", "error": "timeout"})

        # 创建带固定上下文的子 logger
        child = logger.with_context(request_id="req-001")
        child.info("Processing request")
    """

    def __init__(
        self,
        name: str = "suyi",
        session_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        log_file: Optional[str] = None,
        level: str = LogLevel.INFO,
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB
        backup_count: int = 5,
        when: Optional[str] = None,
        console: bool = True,
    ) -> None:
        self.name: str = name
        self.session_id: str = session_id or str(uuid.uuid4())
        self.agent_name: Optional[str] = agent_name
        self.log_file: Optional[str] = log_file
        self.level: str = level

        self._logger: logging.Logger = logging.getLogger(name)
        self._logger.setLevel(LogLevel.to_numeric(level))
        # 避免重复添加 handler
        self._logger.handlers.clear()
        self._logger.propagate = False

        formatter: JsonFormatter = JsonFormatter()

        # 文件 handler
        if log_file:
            os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
            if when:
                file_handler: logging.Handler = (
                    logging.handlers.TimedRotatingFileHandler(
                        log_file, when=when, backupCount=backup_count,
                    )
                )
            else:
                file_handler = logging.handlers.RotatingFileHandler(
                    log_file,
                    maxBytes=max_bytes,
                    backupCount=backup_count,
                )
            file_handler.setFormatter(formatter)
            self._logger.addHandler(file_handler)

        # 控制台 handler
        if console:
            console_handler: logging.Handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            self._logger.addHandler(console_handler)

    # ── 核心日志方法 ──────────────────────────────────────────

    def _log(
        self,
        level: str,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        """内部日志方法，附加上下文字段.

        Args:
            level:   日志级别字符串.
            message: 日志消息.
            extra:   额外字段字典.
        """
        merged: Dict[str, Any] = {
            "session_id": self.session_id,
        }
        if self.agent_name:
            merged["agent_name"] = self.agent_name
        if extra:
            merged.update(extra)

        self._logger.log(
            LogLevel.to_numeric(level),
            message,
            extra=merged,
        )

    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录 DEBUG 级别日志."""
        self._log(LogLevel.DEBUG, message, extra)

    def info(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录 INFO 级别日志."""
        self._log(LogLevel.INFO, message, extra)

    def warn(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录 WARN 级别日志."""
        self._log(LogLevel.WARN, message, extra)

    warning = warn  # 别名

    def error(self, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
        """记录 ERROR 级别日志."""
        self._log(LogLevel.ERROR, message, extra)

    # ── 上下文管理 ────────────────────────────────────────────

    def with_context(
        self,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> "StructuredLogger":
        """创建带固定上下文的子 logger.

        子 logger 共享底层 logging.Logger（同一 handler），
        但携带额外的上下文字段.

        Args:
            session_id:  覆盖会话 ID（不传则继承）.
            request_id:  请求 ID.
            agent_name:  覆盖 Agent 名称（不传则继承）.

        Returns:
            新的 StructuredLogger 实例.
        """
        child: StructuredLogger = StructuredLogger.__new__(StructuredLogger)
        child.name = self.name
        child.session_id = session_id or self.session_id
        child.agent_name = agent_name or self.agent_name
        child.log_file = self.log_file
        child.level = self.level
        child._logger = self._logger  # 共享底层 logger
        child._fixed_extra: Dict[str, Any] = {}
        if request_id:
            child._fixed_extra["request_id"] = request_id
        if agent_name:
            child._fixed_extra["agent_name"] = agent_name
        return child

    def set_level(self, level: str) -> None:
        """动态修改日志级别.

        Args:
            level: 日志级别字符串（DEBUG/INFO/WARN/ERROR）.
        """
        self.level = level
        self._logger.setLevel(LogLevel.to_numeric(level))

    def get_context(self) -> Dict[str, Any]:
        """返回当前 logger 的上下文信息.

        Returns:
            包含 session_id 和 agent_name 的字典.
        """
        ctx: Dict[str, Any] = {"session_id": self.session_id}
        if self.agent_name:
            ctx["agent_name"] = self.agent_name
        return ctx
