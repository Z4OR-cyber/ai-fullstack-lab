"""AML Add/Search HTTP 服务 — 基于标准库 http.server。

本模块实现 :class:`AMLMemoryServer`，为 AML（Agent Memory Leaderboard）
评测提供符合规范的两个 HTTP 端点：

- **POST /add**：存储对话消息到记忆系统。
- **POST /search**：根据查询检索相关记忆。
- **GET /health**：健康检查。

技术约束：

- 仅使用 Python 标准库（``http.server``、``json``、``socketserver``、
  ``asyncio``、``signal``、``logging``、``threading``），不引入 Flask /
  FastAPI / aiohttp 等第三方 Web 框架。
- 支持 API Key 鉴权（通过 ``X-API-Key`` Header）。
- 支持 asyncio 事件循环集成，请求处理可以运行协程。
- 支持优雅关闭（SIGTERM / SIGINT / Ctrl+C）。
- 完整的请求校验和错误处理，返回结构化 JSON 错误。

AML 接口规范
------------

POST /add 请求体::

    {
        "user_id": "string",
        "session_id": "string",
        "messages": [
            {"role": "user|assistant", "content": "string",
             "timestamp": "ISO8601", "metadata": {}}
        ],
        "metadata": {}
    }

POST /add 响应：``{"status": "ok"}`` 或 HTTP 204。

POST /search 请求体::

    {
        "user_id": "string",
        "session_id": "string",
        "query": "string",
        "top_k": int
    }

POST /search 响应::

    {
        "results": [
            {"content": "string", "score": float, "metadata": {}}
        ]
    }

典型用法（编程方式）::

    from suyi.memory.aml_adapter import AMLMemoryServer

    server = AMLMemoryServer(host="0.0.0.0", port=8090, api_key="secret")
    server.start()  # 阻塞运行
    # 或在后台线程中运行:
    # server.start_in_thread()

也可以通过命令行直接启动::

    python -m suyi.memory.aml_adapter --port 8090 --api-key mysecret
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import socket
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .aml_memory import AMLMemoryStore

__all__ = ["AMLMemoryServer", "AMLRequestHandler", "create_server"]

logger = logging.getLogger("suyi.memory.aml_adapter")


# ----------------------------------------------------------------------
#  请求校验
# ----------------------------------------------------------------------

def _validate_add_body(body: Dict[str, Any]) -> Optional[str]:
    """校验 /add 请求体。

    Args:
        body: 解析后的 JSON 请求体。

    Returns:
        错误信息字符串；若校验通过返回 None。
    """
    if not isinstance(body, dict):
        return "Request body must be a JSON object"

    if not body.get("user_id"):
        return "Missing or empty 'user_id'"
    if not isinstance(body["user_id"], str):
        return "'user_id' must be a string"

    if not body.get("session_id"):
        return "Missing or empty 'session_id'"
    if not isinstance(body["session_id"], str):
        return "'session_id' must be a string"

    messages = body.get("messages")
    if not isinstance(messages, list):
        return "'messages' must be an array"
    if len(messages) == 0:
        return "'messages' array must not be empty"

    for idx, msg in enumerate(messages):
        if not isinstance(msg, dict):
            return f"messages[{idx}] must be an object"
        role = msg.get("role")
        if role not in ("user", "assistant", "system", "tool"):
            return (
                f"messages[{idx}].role must be one of "
                f"'user', 'assistant', 'system', 'tool'"
            )
        content = msg.get("content")
        if not isinstance(content, str):
            return f"messages[{idx}].content must be a string"

    return None


def _validate_search_body(body: Dict[str, Any]) -> Optional[str]:
    """校验 /search 请求体。

    Args:
        body: 解析后的 JSON 请求体。

    Returns:
        错误信息字符串；校验通过返回 None。
    """
    if not isinstance(body, dict):
        return "Request body must be a JSON object"

    if not body.get("user_id"):
        return "Missing or empty 'user_id'"
    if not isinstance(body["user_id"], str):
        return "'user_id' must be a string"

    if not body.get("session_id"):
        return "Missing or empty 'session_id'"
    if not isinstance(body["session_id"], str):
        return "'session_id' must be a string"

    query = body.get("query")
    if not isinstance(query, str) or not query.strip():
        return "'query' must be a non-empty string"

    top_k = body.get("top_k", 5)
    if not isinstance(top_k, int) or top_k < 1:
        return "'top_k' must be a positive integer"
    if top_k > 100:
        return "'top_k' must not exceed 100"

    return None


# ----------------------------------------------------------------------
#  HTTP 请求处理器
# ----------------------------------------------------------------------

class AMLRequestHandler(BaseHTTPRequestHandler):
    """AML HTTP 请求处理器。

    由 :class:`AMLMemoryServer` 创建并传入 :class:`AMLMemoryStore` 实例
    和配置。每个请求在独立线程中处理（``ThreadingHTTPServer``）。

    注意：此类的实例由 HTTP 服务器自动创建，不应直接实例化。
    通过 ``server_context`` 类属性访问共享的存储和配置。
    """

    # 由 AMLMemoryServer 在启动前设置的类级上下文
    server_context: Dict[str, Any] = {}

    # 静默默认日志，使用我们自己的 logger
    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        """重写默认日志方法，使用 logging 模块。"""
        client = self.client_address[0] if self.client_address else "?"
        logger.info("%s - %s", client, format % args)

    # ------------------------------------------------------------------
    #  CORS / 通用响应
    # ------------------------------------------------------------------

    def _set_cors_headers(self) -> None:
        """设置 CORS 头（AML 评测可能从浏览器端调用）。"""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Methods", "GET, POST, OPTIONS"
        )
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-API-Key, Authorization",
        )

    def _send_json(
        self,
        status: int,
        data: Any,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """发送 JSON 响应。

        Args:
            status: HTTP 状态码。
            data: 可序列化为 JSON 的数据。
            extra_headers: 额外的 HTTP 头。
        """
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._set_cors_headers()
        if extra_headers:
            for key, value in extra_headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_empty(self, status: int = HTTPStatus.NO_CONTENT) -> None:
        """发送空响应（204 No Content）。"""
        self.send_response(status)
        self._set_cors_headers()
        self.end_headers()

    def _send_error_json(
        self, status: int, message: str, detail: Optional[str] = None
    ) -> None:
        """发送结构化 JSON 错误响应。

        Args:
            status: HTTP 状态码。
            message: 简短错误描述。
            detail: 可选的详细信息。
        """
        error: Dict[str, Any] = {"error": message}
        if detail:
            error["detail"] = detail
        self._send_json(status, error)

    def _read_body(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """读取并解析请求体 JSON。

        Returns:
            (parsed_body, error_message) 元组。成功时 error_message 为 None，
            失败时 parsed_body 为 None。
        """
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length <= 0:
            return None, "Request body is empty"
        if content_length > 10 * 1024 * 1024:  # 10MB 限制
            return None, "Request body too large (max 10MB)"

        try:
            raw = self.rfile.read(content_length)
            body = json.loads(raw.decode("utf-8"))
            return body, None
        except json.JSONDecodeError as e:
            return None, f"Invalid JSON: {e.msg}"
        except UnicodeDecodeError:
            return None, "Request body must be UTF-8 encoded"

    # ------------------------------------------------------------------
    #  鉴权
    # ------------------------------------------------------------------

    def _check_auth(self) -> bool:
        """检查 API Key 鉴权。

        若服务器未配置 api_key，则始终放行。

        Returns:
            鉴权通过返回 True，否则 False。
        """
        expected_key = self.server_context.get("api_key")
        if not expected_key:
            return True

        provided = self.headers.get("X-API-Key", "")
        # 也支持 Authorization: Bearer <key>
        if not provided:
            auth = self.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                provided = auth[7:]

        # 常量时间比较，防止时序攻击
        import hmac
        return hmac.compare_digest(provided, expected_key)

    # ------------------------------------------------------------------
    #  路由
    # ------------------------------------------------------------------

    def do_OPTIONS(self) -> None:  # noqa: N802
        """处理 CORS 预检请求。"""
        self.send_response(HTTPStatus.NO_CONTENT)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        """处理 GET 请求 — 目前仅 /health。"""
        if self.path.rstrip("/") == "/health":
            self._handle_health()
        else:
            self._send_error_json(
                HTTPStatus.NOT_FOUND,
                f"Path not found: {self.path}",
            )

    def do_POST(self) -> None:  # noqa: N802
        """处理 POST 请求 — /add 和 /search。"""
        # 鉴权检查
        if not self._check_auth():
            self._send_error_json(
                HTTPStatus.UNAUTHORIZED,
                "Invalid or missing API key",
            )
            return

        path = self.path.rstrip("/")

        if path == "/add":
            self._handle_add()
        elif path == "/search":
            self._handle_search()
        else:
            self._send_error_json(
                HTTPStatus.NOT_FOUND,
                f"Path not found: {self.path}",
            )

    # ------------------------------------------------------------------
    #  端点处理
    # ------------------------------------------------------------------

    def _handle_health(self) -> None:
        """GET /health — 返回服务状态和记忆统计。"""
        store: AMLMemoryStore = self.server_context["store"]
        try:
            stats = store.get_stats()
            self._send_json(HTTPStatus.OK, {
                "status": "ok",
                "service": "suyi-aml-memory",
                "version": self.server_context.get("version", "unknown"),
                "timestamp": time.time(),
                "stats": stats,
            })
        except Exception as e:
            logger.exception("Health check failed")
            self._send_error_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "Health check failed",
                str(e),
            )

    def _handle_add(self) -> None:
        """POST /add — 存储对话消息。"""
        body, err = self._read_body()
        if err:
            self._send_error_json(HTTPStatus.BAD_REQUEST, err)
            return

        err = _validate_add_body(body)
        if err:
            self._send_error_json(HTTPStatus.BAD_REQUEST, err)
            return

        store: AMLMemoryStore = self.server_context["store"]
        user_id = body["user_id"]
        session_id = body["session_id"]
        messages = body["messages"]
        request_metadata = body.get("metadata", {}) or {}

        try:
            # 在事件循环中运行（如果可用）
            count = self._run_in_event_loop(
                store.add_messages_batch, user_id, session_id, messages
            )
            logger.info(
                "ADD user=%s session=%s messages=%d records=%d",
                user_id, session_id, len(messages), count,
            )

            # AML 规范允许 {"status": "ok"} 或 204
            # 返回 200 + JSON 更通用
            self._send_json(HTTPStatus.OK, {
                "status": "ok",
                "added": count,
            })
        except Exception as e:
            logger.exception("Failed to add messages")
            self._send_error_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "Failed to store messages",
                str(e),
            )

    def _handle_search(self) -> None:
        """POST /search — 检索相关记忆。"""
        body, err = self._read_body()
        if err:
            self._send_error_json(HTTPStatus.BAD_REQUEST, err)
            return

        err = _validate_search_body(body)
        if err:
            self._send_error_json(HTTPStatus.BAD_REQUEST, err)
            return

        store: AMLMemoryStore = self.server_context["store"]
        user_id = body["user_id"]
        session_id = body["session_id"]
        query = body["query"]
        top_k = body.get("top_k", 5)
        layers = body.get("layers")  # 可选层过滤
        metadata_filter = body.get("metadata_filter")  # 可选元数据过滤

        try:
            start_time = time.time()
            results = self._run_in_event_loop(
                store.search,
                user_id=user_id,
                session_id=session_id,
                query=query,
                top_k=top_k,
                layers=layers,
                metadata_filter=metadata_filter,
            )
            elapsed_ms = (time.time() - start_time) * 1000

            # 转换为 AML 规范的响应格式
            aml_results = []
            for r in results:
                aml_results.append({
                    "content": r["content"],
                    "score": r["score"],
                    "metadata": r["metadata"],
                })

            logger.info(
                "SEARCH user=%s session=%s query=%r top_k=%d "
                "results=%d elapsed=%.1fms",
                user_id, session_id, query[:50], top_k,
                len(aml_results), elapsed_ms,
            )

            self._send_json(HTTPStatus.OK, {
                "results": aml_results,
                "count": len(aml_results),
                "elapsed_ms": round(elapsed_ms, 2),
            })
        except Exception as e:
            logger.exception("Search failed")
            self._send_error_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "Search failed",
                str(e),
            )

    # ------------------------------------------------------------------
    #  asyncio 集成
    # ------------------------------------------------------------------

    def _run_in_event_loop(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """在事件循环中运行同步函数。

        如果服务器上下文配置了 asyncio 事件循环，则在该循环中通过
        ``run_in_executor`` 运行；否则直接同步调用。

        Args:
            func: 要运行的函数。
            *args: 位置参数。
            **kwargs: 关键字参数。

        Returns:
            函数返回值。
        """
        loop = self.server_context.get("event_loop")
        if loop is not None and loop.is_running():
            # 如果事件循环正在运行，使用 executor
            future = asyncio.run_coroutine_threadsafe(
                self._async_wrapper(func, *args, **kwargs), loop
            )
            return future.result(timeout=30)
        # 没有事件循环或未运行，直接调用
        return func(*args, **kwargs)

    @staticmethod
    async def _async_wrapper(
        func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """在线程池中运行同步函数的异步包装器。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: func(*args, **kwargs)
        )


# ----------------------------------------------------------------------
#  AMLMemoryServer
# ----------------------------------------------------------------------

class AMLMemoryServer:
    """AML Add/Search HTTP 服务器。

    基于 ``ThreadingHTTPServer`` 实现，支持多线程并发请求处理。
    提供同步和异步（后台线程）两种启动方式，以及优雅关闭。

    Attributes:
        host: 监听地址。
        port: 监听端口。
        store: 后端 :class:`AMLMemoryStore` 实例。
        api_key: API Key 鉴权密钥，None 表示不鉴权。
        httpd: 底层 ``ThreadingHTTPServer`` 实例。
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8090,
        store: Optional[AMLMemoryStore] = None,
        storage_dir: Optional[str] = None,
        api_key: Optional[str] = None,
        version: str = "1.10.0",
        max_workers: int = 32,
        reranker: Any = None,
        **store_kwargs: Any,
    ) -> None:
        """初始化 AML HTTP 服务器。

        Args:
            host: 监听地址，默认 ``0.0.0.0``。
            port: 监听端口，默认 8090。
            store: 可选的已存在 :class:`AMLMemoryStore` 实例。若为 None
                则自动创建一个。
            storage_dir: 记忆持久化目录（仅在 store 为 None 时使用）。
            api_key: API Key 鉴权密钥。若为 None 则从环境变量
                ``AML_API_KEY`` 读取；若环境变量也未设置，则不鉴权。
            version: 服务版本号，在 /health 中返回。
            max_workers: 最大并发工作线程数。
            reranker: v1.10.0 新增，传递给 :class:`AMLMemoryStore` 的
                utility 重排器配置；仅在 ``store`` 为 None 时生效。
                支持 ``None``（按环境变量 ``AML_RERANK_ENABLED`` 决定，
                默认开启）、``False``（关闭）或已有的
                :class:`~suyi.memory.utility_reranker.UtilityReranker`
                实例。
            **store_kwargs: 传递给 :class:`AMLMemoryStore` 的额外参数。
        """
        self.host = host
        self.port = port
        self.version = version
        self.max_workers = max_workers

        # API Key: 参数优先，其次环境变量
        if api_key is None:
            api_key = os.environ.get("AML_API_KEY")
        self.api_key = api_key

        # 创建或使用记忆存储
        if store is not None:
            self.store = store
        else:
            self.store = AMLMemoryStore(
                storage_dir=storage_dir,
                reranker=reranker,
                **store_kwargs,
            )

        # HTTP 服务器实例
        self.httpd: Optional[ThreadingHTTPServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

    # ------------------------------------------------------------------
    #  启动
    # ------------------------------------------------------------------

    def _setup_handler_context(self) -> None:
        """配置请求处理器的类级上下文。"""
        AMLRequestHandler.server_context = {
            "store": self.store,
            "api_key": self.api_key,
            "version": self.version,
            "event_loop": self._event_loop,
        }

    def _start_event_loop(self) -> None:
        """在后台线程中启动 asyncio 事件循环。"""
        def _loop_runner() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._event_loop = loop
            # 更新 handler 上下文中的事件循环引用
            AMLRequestHandler.server_context["event_loop"] = loop
            loop.run_forever()

        self._loop_thread = threading.Thread(
            target=_loop_runner,
            name="aml-asyncio-loop",
            daemon=True,
        )
        self._loop_thread.start()

        # 等待事件循环就绪
        for _ in range(50):
            if self._event_loop is not None:
                break
            time.sleep(0.05)

    def start(self) -> None:
        """启动 HTTP 服务器（阻塞当前线程）。

        注册 SIGTERM/SIGINT 信号处理以支持优雅关闭。
        此方法会阻塞直到服务器关闭。
        """
        self._start_event_loop()
        self._setup_handler_context()

        # 创建 HTTP 服务器
        self.httpd = ThreadingHTTPServer(
            (self.host, self.port), AMLRequestHandler
        )
        # 允许端口复用，避免重启时 TIME_WAIT
        self.httpd.allow_reuse_address = True

        actual_port = self.httpd.server_address[1]
        logger.info(
            "AML Memory Server starting on %s:%d (version %s)",
            self.host, actual_port, self.version,
        )
        if self.api_key:
            logger.info("API Key authentication enabled")
        else:
            logger.warning("API Key authentication DISABLED")

        # 注册信号处理（仅主线程）
        if threading.current_thread() is threading.main_thread():
            self._register_signals()

        # 阻塞服务循环。serve_forever 会定期轮询 timeout（默认 0.5s），
        # 因此 shutdown_event 可快速响应。
        try:
            self.httpd.serve_forever(poll_interval=0.5)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        finally:
            self.stop()

    def start_in_thread(self) -> threading.Thread:
        """在后台线程中启动 HTTP 服务器。

        Returns:
            运行服务器的线程对象。
        """
        self._server_thread = threading.Thread(
            target=self.start,
            name="aml-http-server",
            daemon=True,
        )
        self._server_thread.start()

        # 等待服务器就绪
        for _ in range(50):
            if self.httpd is not None:
                break
            time.sleep(0.05)

        return self._server_thread

    def _register_signals(self) -> None:
        """注册 SIGTERM/SIGINT 信号处理器。"""
        def _signal_handler(signum: int, frame: Any) -> None:
            sig_name = signal.Signals(signum).name
            logger.info("Received %s, shutting down...", sig_name)
            self._shutdown_event.set()

        try:
            signal.signal(signal.SIGTERM, _signal_handler)
            signal.signal(signal.SIGINT, _signal_handler)
        except (ValueError, OSError):
            # 非主线程或不支持信号的平台
            pass

    # ------------------------------------------------------------------
    #  关闭
    # ------------------------------------------------------------------

    def stop(self, timeout: float = 10.0) -> None:
        """优雅关闭服务器。

        - 停止接受新连接。
        - 关闭事件循环。
        - 持久化记忆数据。

        Args:
            timeout: 等待后台线程结束的超时时间（秒）。
        """
        logger.info("Shutting down AML Memory Server...")
        self._shutdown_event.set()

        if self.httpd is not None:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception as e:
                logger.warning("Error closing HTTP server: %s", e)
            self.httpd = None

        # 停止事件循环
        if self._event_loop is not None:
            try:
                self._event_loop.call_soon_threadsafe(
                    self._event_loop.stop
                )
            except Exception:
                pass
            self._event_loop = None

        if self._loop_thread is not None:
            # v1.10.0: 若 stop() 恰好从 loop 线程内调用（例如 daemon
            # 线程的 finally 路径），join 当前线程会抛 RuntimeError，
            # 此时跳过 join 即可。
            if self._loop_thread is not threading.current_thread():
                self._loop_thread.join(timeout=timeout)
            self._loop_thread = None

        if self._server_thread is not None:
            if self._server_thread is not threading.current_thread():
                self._server_thread.join(timeout=timeout)
            self._server_thread = None

        logger.info("AML Memory Server stopped")

    # ------------------------------------------------------------------
    #  上下文管理器
    # ------------------------------------------------------------------

    def __enter__(self) -> "AMLMemoryServer":
        self.start_in_thread()
        return self

    def __exit__(self, *args: Any) -> None:
        self.stop()

    def __repr__(self) -> str:
        return (
            f"AMLMemoryServer(host={self.host!r}, port={self.port}, "
            f"version={self.version!r})"
        )


# ----------------------------------------------------------------------
#  工厂函数
# ----------------------------------------------------------------------

def create_server(
    host: str = "0.0.0.0",
    port: int = 8090,
    api_key: Optional[str] = None,
    storage_dir: Optional[str] = None,
    **kwargs: Any,
) -> AMLMemoryServer:
    """创建 :class:`AMLMemoryServer` 实例的工厂函数。

    Args:
        host: 监听地址。
        port: 监听端口。
        api_key: API Key 密钥。
        storage_dir: 持久化目录。
        **kwargs: 其他参数。

    Returns:
        配置好的 AMLMemoryServer 实例（未启动）。
    """
    return AMLMemoryServer(
        host=host,
        port=port,
        api_key=api_key,
        storage_dir=storage_dir,
        **kwargs,
    )


# ----------------------------------------------------------------------
#  命令行入口
# ----------------------------------------------------------------------

def _main() -> None:
    """命令行启动入口。

    用法::

        python -m suyi.memory.aml_adapter [--host HOST] [--port PORT]
                                          [--api-key KEY]
                                          [--storage-dir DIR]
                                          [--log-level LEVEL]
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Suyi AML Memory HTTP Server"
    )
    parser.add_argument(
        "--host", default="0.0.0.0",
        help="Bind address (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port", type=int, default=8090,
        help="Bind port (default: 8090)",
    )
    parser.add_argument(
        "--api-key", default=None,
        help="API key for X-API-Key auth (default: AML_API_KEY env var)",
    )
    parser.add_argument(
        "--storage-dir", default=None,
        help="Directory for memory persistence "
             "(default: ~/.suyi/aml_memory/)",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    server = AMLMemoryServer(
        host=args.host,
        port=args.port,
        api_key=args.api_key,
        storage_dir=args.storage_dir,
    )

    try:
        server.start()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    _main()
