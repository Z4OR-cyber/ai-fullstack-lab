"""
轨道A·阶段十：工程进阶 — 系统设计练习（Q6-Q10）
Q6: HLD基础 | Q7: HLD实战 | Q8: LLD与SOLID | Q9: 分布式系统核心 | Q10: 容量规划与性能工程
"""
from __future__ import annotations

import hashlib
import math
import random
import threading
import time
import bisect
from abc import ABC, abstractmethod
from collections import defaultdict, deque, OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
import statistics


# ============================================================
# Q6: HLD基础 — 负载均衡/缓存/CDN/分片/消息队列
# ============================================================

class Q6HLDBasics:
    """HLD基础：用Python模拟每种机制运行"""

    # ---------- 1. 负载均衡 ----------
    class RoundRobinBalancer:
        def __init__(self, servers: list[str]):
            self.servers = servers
            self._index = 0
            self._lock = threading.Lock()

        def get_server(self) -> str:
            with self._lock:
                server = self.servers[self._index % len(self.servers)]
                self._index += 1
                return server

    class LeastConnectionsBalancer:
        def __init__(self, servers: list[str]):
            self.connections = {s: 0 for s in servers}

        def get_server(self) -> str:
            return min(self.connections, key=self.connections.get)

        def connect(self, server: str): self.connections[server] += 1
        def disconnect(self, server: str): self.connections[server] = max(0, self.connections[server] - 1)

    class ConsistentHashBalancer:
        def __init__(self, servers: list[str], replicas: int = 150):
            self.ring: dict[int, str] = {}
            self.sorted_keys: list[int] = []
            for server in servers:
                for i in range(replicas):
                    key = self._hash(f"{server}:{i}")
                    self.ring[key] = server
                    bisect.insort(self.sorted_keys, key)

        @staticmethod
        def _hash(s: str) -> int:
            return int(hashlib.md5(s.encode()).hexdigest(), 16)

        def get_server(self, key: str) -> str:
            if not self.sorted_keys:
                raise RuntimeError("No servers")
            h = self._hash(key)
            idx = bisect.bisect_right(self.sorted_keys, h)
            if idx >= len(self.sorted_keys):
                idx = 0
            return self.ring[self.sorted_keys[idx]]

    def test_load_balancing(self):
        servers = ["s1", "s2", "s3"]
        # Round Robin
        rr = self.RoundRobinBalancer(servers)
        results = [rr.get_server() for _ in range(6)]
        assert results == ["s1", "s2", "s3", "s1", "s2", "s3"]

        # Least Connections
        lc = self.LeastConnectionsBalancer(servers)
        lc.connect("s1")
        assert lc.get_server() == "s2"
        lc.connect("s2")
        assert lc.get_server() == "s3"

        # Consistent Hash
        ch = self.ConsistentHashBalancer(servers, replicas=100)
        s1 = ch.get_server("user:1001")
        s2 = ch.get_server("user:1001")  # 相同key应映射到相同server
        assert s1 == s2
        # 不同key分布到不同server
        distribution = defaultdict(int)
        for i in range(1000):
            distribution[ch.get_server(f"user:{i}")] += 1
        assert len(distribution) >= 2  # 至少分布到2个server
        print("  ✅ 负载均衡 —— Round Robin / 最少连接 / 一致性哈希")

    # ---------- 2. 缓存策略 ----------
    class CacheAside:
        """Cache Aside: 读时先查缓存，未命中查DB再写入缓存"""
        def __init__(self):
            self.cache: dict[str, Any] = {}
            self.db: dict[str, Any] = {"user:1": "Alice", "user:2": "Bob"}
            self.cache_hits = 0
            self.cache_misses = 0

        def get(self, key: str) -> Any:
            if key in self.cache:
                self.cache_hits += 1
                return self.cache[key]
            self.cache_misses += 1
            val = self.db.get(key)
            if val is not None:
                self.cache[key] = val
            return val

        def set(self, key: str, value: Any):
            self.db[key] = value
            self.cache[key] = value

    class WriteThrough:
        """Write Through: 写时同时更新缓存和DB"""
        def __init__(self):
            self.cache: dict[str, Any] = {}
            self.db: dict[str, Any] = {}
            self.writes = 0

        def write(self, key: str, value: Any):
            self.cache[key] = value
            self.db[key] = value
            self.writes += 1

        def read(self, key: str) -> Any:
            return self.cache.get(key)  # 缓存总有最新值

    class WriteBehind:
        """Write Behind: 写缓存，异步刷入DB"""
        def __init__(self):
            self.cache: dict[str, Any] = {}
            self.db: dict[str, Any] = {}
            self.write_buffer: list[tuple[str, Any]] = []

        def write(self, key: str, value: Any):
            self.cache[key] = value
            self.write_buffer.append((key, value))

        def flush(self):
            for key, value in self.write_buffer:
                self.db[key] = value
            self.write_buffer.clear()

        def read(self, key: str) -> Any:
            return self.cache.get(key)

    def test_cache_strategies(self):
        # Cache Aside
        ca = self.CacheAside()
        assert ca.get("user:1") == "Alice"  # miss
        assert ca.get("user:1") == "Alice"  # hit
        assert ca.cache_misses == 1
        assert ca.cache_hits == 1

        # Write Through
        wt = self.WriteThrough()
        wt.write("key1", "value1")
        assert wt.read("key1") == "value1"
        assert wt.db["key1"] == "value1"

        # Write Behind
        wb = self.WriteBehind()
        wb.write("key1", "value1")
        assert wb.read("key1") == "value1"
        assert "key1" not in wb.db  # DB还未更新
        wb.flush()
        assert wb.db["key1"] == "value1"  # flush后更新
        print("  ✅ 缓存策略 —— Cache Aside / Write Through / Write Behind")

    # ---------- 3. CDN原理模拟 ----------
    class CDNNode:
        def __init__(self, name: str, location: str):
            self.name = name
            self.location = location
            self.cache: dict[str, bytes] = {}

    class CDNSimulator:
        """CDN: 就近节点缓存 + 源站回源"""
        def __init__(self, origin_content: dict[str, bytes]):
            self.origin = origin_content
            self.nodes: list[Q6HLDBasics.CDNNode] = []

        def add_node(self, node: Q6HLDBasics.CDNNode):
            self.nodes.append(node)
            return self

        def get_nearest_node(self, user_location: str) -> Q6HLDBasics.CDNNode:
            # 简化：按location匹配
            for node in self.nodes:
                if node.location == user_location:
                    return node
            return self.nodes[0]

        def fetch(self, url: str, user_location: str) -> bytes:
            node = self.get_nearest_node(user_location)
            if url in node.cache:
                return node.cache[url]
            # 回源
            content = self.origin.get(url, b"Not Found")
            node.cache[url] = content  # 缓存到边缘节点
            return content

    def test_cdn(self):
        cdn = self.CDNSimulator({"img/logo.png": b"PNG_DATA", "js/app.js": b"JS_DATA"})
        cdn.add_node(self.CDNNode("edge-us", "US"))
        cdn.add_node(self.CDNNode("edge-cn", "CN"))
        # CN用户访问，首次回源
        content1 = cdn.fetch("img/logo.png", "CN")
        assert content1 == b"PNG_DATA"
        # 再次访问，命中CN节点缓存
        content2 = cdn.fetch("img/logo.png", "CN")
        assert content2 == b"PNG_DATA"
        assert "img/logo.png" in cdn.nodes[1].cache  # CN节点已缓存
        print("  ✅ CDN原理模拟 —— 边缘节点缓存 + 源站回源")

    # ---------- 4. 数据分片 ----------
    class RangeSharding:
        """范围分片：按ID范围分配到不同分片"""
        def __init__(self, ranges: list[tuple[int, int, str]]):
            self.ranges = ranges  # [(start, end, shard_name)]

        def get_shard(self, key: int) -> str:
            for start, end, name in self.ranges:
                if start <= key < end:
                    return name
            raise ValueError(f"No shard for key {key}")

    class HashSharding:
        """哈希分片：按hash取模分配"""
        def __init__(self, num_shards: int):
            self.num_shards = num_shards

        def get_shard(self, key: str) -> int:
            return int(hashlib.md5(key.encode()).hexdigest(), 16) % self.num_shards

    def test_sharding(self):
        # 范围分片
        range_shard = self.RangeSharding([(0, 1000, "shard-0"), (1000, 2000, "shard-1"), (2000, 3000, "shard-2")])
        assert range_shard.get_shard(500) == "shard-0"
        assert range_shard.get_shard(1500) == "shard-1"
        assert range_shard.get_shard(2500) == "shard-2"

        # 哈希分片
        hash_shard = self.HashSharding(num_shards=4)
        distribution = defaultdict(int)
        for i in range(1000):
            shard = hash_shard.get_shard(f"user:{i}")
            distribution[shard] += 1
            assert 0 <= shard < 4
        # 验证数据分布相对均匀
        counts = list(distribution.values())
        assert max(counts) / min(counts) < 2.0  # 分布不均率小于2倍
        print("  ✅ 数据分片 —— 范围分片 / 哈希分片")

    # ---------- 5. 消息队列 ----------
    class MessageQueue:
        """生产者-消费者模型"""
        def __init__(self, max_size: int = 100):
            self._queue: deque = deque()
            self._max_size = max_size
            self._lock = threading.Lock()
            self._not_empty = threading.Condition(self._lock)
            self._consumed: list[Any] = []
            self._closed = False

        def produce(self, message: Any):
            with self._lock:
                if self._closed:
                    raise RuntimeError("Queue closed")
                self._queue.append(message)
                self._not_empty.notify()

        def consume(self, timeout: float = 1.0) -> Optional[Any]:
            with self._lock:
                if not self._queue and not self._closed:
                    self._not_empty.wait(timeout=timeout)
                if self._queue:
                    msg = self._queue.popleft()
                    self._consumed.append(msg)
                    return msg
                return None

        def close(self):
            with self._lock:
                self._closed = True
                self._not_empty.notify_all()

        @property
        def consumed_count(self): return len(self._consumed)

    def test_message_queue(self):
        mq = self.MessageQueue(max_size=10)
        consumed_results: list[Any] = []

        def producer():
            for i in range(5):
                mq.produce(f"msg-{i}")
            mq.close()

        def consumer():
            while True:
                msg = mq.consume(timeout=0.5)
                if msg is None:
                    break
                consumed_results.append(msg)

        p = threading.Thread(target=producer)
        c = threading.Thread(target=consumer)
        p.start()
        time.sleep(0.1)
        c.start()
        p.join()
        c.join()

        assert len(consumed_results) == 5
        assert consumed_results[0] == "msg-0"
        assert consumed_results[4] == "msg-4"
        print("  ✅ 消息队列 —— 生产者-消费者模型")

    def run(self):
        print("=" * 60)
        print("Q6: HLD基础（负载均衡 / 缓存 / CDN / 分片 / 消息队列）")
        print("=" * 60)
        self.test_load_balancing()
        self.test_cache_strategies()
        self.test_cdn()
        self.test_sharding()
        self.test_message_queue()
        print()


# ============================================================
# Q7: HLD实战 — AI推理服务 + Bug Bounty平台
# ============================================================

class Q7HLDPractice:
    """HLD实战：设计AI推理服务和Bug Bounty平台"""

    def print_architecture_ai(self):
        arch = """
        ┌─────────────────────────────────────────────────────────────┐
        │                      AI 推理服务架构                          │
        ├─────────────────────────────────────────────────────────────┤
        │                                                             │
        │   Client ──→ [API Gateway] ──→ [Load Balancer]             │
        │                                       │                     │
        │                    ┌──────────────────┼──────────────────┐  │
        │                    ▼                  ▼                  ▼  │
        │              [Infer Node 1]   [Infer Node 2]   [Infer Node 3]│
        │                    │                  │                  │  │
        │                    ▼                  ▼                  ▼  │
        │              [Model Cache]    [Model Cache]    [Model Cache]│
        │                    │                  │                  │  │
        │                    └──────────────────┼──────────────────┘  │
        │                                       ▼                     │
        │                              [Result Queue]                  │
        │                                       │                     │
        │                                       ▼                     │
        │                              [Response]                      │
        └─────────────────────────────────────────────────────────────┘
        """
        print(arch)

    def simulate_ai_inference(self):
        """模拟AI推理服务核心流程"""
        class APIGateway:
            def handle_request(self, request: dict) -> dict:
                if not request.get("api_key"):
                    return {"error": "Unauthorized"}
                request["gateway_ts"] = time.time()
                return request

        class LoadBalancer:
            def __init__(self, nodes: list[str]):
                self.nodes = nodes
                self._idx = 0

            def route(self, request: dict) -> str:
                node = self.nodes[self._idx % len(self.nodes)]
                self._idx += 1
                return node

        class ModelCache:
            def __init__(self):
                self._cache: dict[str, str] = {}

            def get(self, model_name: str) -> Optional[str]:
                return self._cache.get(model_name)

            def load(self, model_name: str) -> str:
                if model_name not in self._cache:
                    self._cache[model_name] = f"loaded:{model_name}"
                return self._cache[model_name]

        class InferenceNode:
            def __init__(self, name: str, cache: ModelCache):
                self.name = name
                self.cache = cache

            def infer(self, request: dict) -> dict:
                model = self.cache.load(request.get("model", "gpt-4"))
                return {
                    "node": self.name,
                    "model": model,
                    "result": f"inference for: {request.get('prompt', '')}",
                    "latency_ms": random.randint(50, 200),
                }

        class ResultQueue:
            def __init__(self):
                self._results: list[dict] = []

            def enqueue(self, result: dict):
                self._results.append(result)

            def dequeue(self) -> Optional[dict]:
                return self._results.pop(0) if self._results else None

        # 组装并运行
        gateway = APIGateway()
        lb = LoadBalancer(["node-1", "node-2", "node-3"])
        cache = ModelCache()
        nodes = {n: InferenceNode(n, cache) for n in ["node-1", "node-2", "node-3"]}
        result_queue = ResultQueue()

        # 模拟5个请求
        for i in range(5):
            req = gateway.handle_request({"api_key": "key123", "model": "gpt-4", "prompt": f"query-{i}"})
            assert "error" not in req
            node_name = lb.route(req)
            result = nodes[node_name].infer(req)
            result_queue.enqueue(result)

        # 验证结果
        results = []
        while result_queue._results:
            results.append(result_queue.dequeue())

        assert len(results) == 5
        assert all("inference for:" in r["result"] for r in results)
        # 模型缓存只加载一次
        assert cache.get("gpt-4") == "loaded:gpt-4"

    def test_ai_inference(self):
        self.print_architecture_ai()
        self.simulate_ai_inference()
        print("  ✅ AI推理服务 —— 网关→负载均衡→推理集群→模型缓存→结果队列")

    def print_architecture_bugbounty(self):
        arch = """
        ┌─────────────────────────────────────────────────────────────┐
        │                   Bug Bounty 平台架构                        │
        ├─────────────────────────────────────────────────────────────┤
        │                                                             │
        │  [Hacker]          [Program Owner]        [Reviewer]       │
        │      │                   │                    │             │
        │      ▼                   ▼                    ▼             │
        │  ┌──────────────────────────────────────────────────┐      │
        │  │              User Management Service              │      │
        │  └──────────────────────┬───────────────────────────┘      │
        │                         │                                   │
        │  ┌──────────────────────▼───────────────────────────┐      │
        │  │          Vulnerability Submission Service         │      │
        │  └──────────────────────┬───────────────────────────┘      │
        │                         │                                   │
        │  ┌──────────────────────▼───────────────────────────┐      │
        │  │         Review Workflow (Triager→Analyst→Owner)   │      │
        │  └──────────────────────┬───────────────────────────┘      │
        │                         │                                   │
        │  ┌──────────┬───────────▼──────────┬─────────────┐         │
        │  │ Rewards  │   Notification Hub   │  Analytics  │         │
        │  │ Service  │ (Email/Push/Webhook) │   Service   │         │
        │  └──────────┴──────────────────────┴─────────────┘         │
        └─────────────────────────────────────────────────────────────┘
        """
        print(arch)

    def simulate_bug_bounty(self):
        """模拟Bug Bounty平台核心流程"""
        class User:
            def __init__(self, uid: str, name: str, role: str):
                self.uid = uid
                self.name = name
                self.role = role  # hacker / owner / reviewer

        class VulnerabilityReport:
            def __init__(self, vid: str, title: str, severity: str, hacker: User):
                self.vid = vid
                self.title = title
                self.severity = severity
                self.hacker = hacker
                self.status = "submitted"
                self.reward = 0

        SEVERITY_REWARDS = {"critical": 5000, "high": 2000, "medium": 500, "low": 100}

        class ReviewWorkflow:
            def __init__(self):
                self.transitions = {
                    "submitted": "triaging",
                    "triaging": "analyzing",
                    "analyzing": "resolved",
                    "resolved": "closed",
                }

            def advance(self, report: VulnerabilityReport) -> str:
                next_status = self.transitions.get(report.status)
                if next_status:
                    report.status = next_status
                return report.status

        class NotificationSystem:
            def __init__(self):
                self.sent: list[str] = []

            def notify(self, user: User, message: str):
                self.sent.append(f"[{user.name}] {message}")

        class RewardSystem:
            def __init__(self, notifier: NotificationSystem):
                self.notifier = notifier

            def grant(self, report: VulnerabilityReport):
                report.reward = SEVERITY_REWARDS.get(report.severity, 0)
                self.notifier.notify(report.hacker, f"Reward granted: ${report.reward}")
                return report.reward

        # 运行流程
        hacker = User("u1", "Alice", "hacker")
        owner = User("u2", "Bob", "owner")
        reviewer = User("u3", "Carol", "reviewer")

        report = VulnerabilityReport("vuln-001", "SQL Injection in login", "critical", hacker)
        workflow = ReviewWorkflow()
        notifier = NotificationSystem()
        rewards = RewardSystem(notifier)

        # 提交 → 审核
        notifier.notify(hacker, "Report submitted successfully")
        assert workflow.advance(report) == "triaging"
        notifier.notify(reviewer, "New report to triage")
        assert workflow.advance(report) == "analyzing"
        assert workflow.advance(report) == "resolved"

        # 奖励
        reward = rewards.grant(report)
        assert reward == 5000
        assert report.status == "resolved"

        # 通知验证
        assert len(notifier.sent) == 3
        assert "Reward granted" in notifier.sent[-1]

    def test_bug_bounty(self):
        self.print_architecture_bugbounty()
        self.simulate_bug_bounty()
        print("  ✅ Bug Bounty平台 —— 提交→审核→奖励→通知 全流程")

    def run(self):
        print("=" * 60)
        print("Q7: HLD实战（AI推理服务 + Bug Bounty平台）")
        print("=" * 60)
        self.test_ai_inference()
        self.test_bug_bounty()
        print()


# ============================================================
# Q8: LLD与SOLID — 插件系统
# ============================================================

class Q8LLDPractice:
    """LLD与SOLID：UML类图、接口隔离、依赖注入、可扩展插件系统"""

    def print_plugin_system_uml(self):
        uml = """
        ┌─────────────────────────────────────────────────────────┐
        │              Plugin System UML (文本表示)                │
        ├─────────────────────────────────────────────────────────┤
        │                                                         │
        │  <<interface>>                                          │
        │   IPlugin                                               │
        │   + name: str                                           │
        │   + version: str                                        │
        │   + initialize(config: dict): void                      │
        │   + execute(input: Any): Any                            │
        │   + shutdown(): void                                    │
        │         ▲                                               │
        │         │ implements                                    │
        │    ┌────┴────┬──────────┬────────────┐                  │
        │    │         │          │            │                  │
        │  Logger    Filter    Transformer   Exporter             │
        │  Plugin    Plugin    Plugin        Plugin               │
        │                                                         │
        │  <<interface>>               <<interface>>              │
        │   IPluginConfig               IPluginRegistry           │
        │   + schema: dict              + register(p: IPlugin)    │
        │   + validate(c: dict): bool   + get(name): IPlugin      │
        │                                + list(): list[str]      │
        │         ▲                          ▲                    │
        │         │ implements                │ implements         │
        │    BaseConfig                  PluginRegistry           │
        │                                                         │
        │  PluginManager ──depends on──→ IPluginRegistry          │
        │               ──depends on──→ IPluginConfig             │
        └─────────────────────────────────────────────────────────┘
        """
        print(uml)

    # ---- 接口定义（ISP：接口隔离）----
    class IPlugin(ABC):
        """插件核心接口"""
        @property
        @abstractmethod
        def name(self) -> str: ...
        @property
        @abstractmethod
        def version(self) -> str: ...
        @abstractmethod
        def initialize(self, config: dict) -> None: ...
        @abstractmethod
        def execute(self, input_data: Any) -> Any: ...
        @abstractmethod
        def shutdown(self) -> None: ...

    class IPluginConfig(ABC):
        """插件配置接口（与插件执行接口隔离）"""
        @property
        @abstractmethod
        def schema(self) -> dict: ...
        @abstractmethod
        def validate(self, config: dict) -> bool: ...

    class IPluginRegistry(ABC):
        """插件注册接口（与插件执行隔离）"""
        @abstractmethod
        def register(self, plugin: "Q8LLDPractice.IPlugin") -> None: ...
        @abstractmethod
        def get(self, name: str) -> "Q8LLDPractice.IPlugin": ...
        @abstractmethod
        def list_plugins(self) -> list[str]: ...

    # ---- 基础实现 ----
    class BaseConfig(IPluginConfig):
        """配置基类，子类提供schema"""
        def __init__(self):
            self._schema: dict = {}

        @property
        def schema(self): return self._schema

        def validate(self, config: dict) -> bool:
            for key, expected_type in self._schema.items():
                if key not in config:
                    return False
            return True

    class PluginRegistry(IPluginRegistry):
        """插件注册器"""
        def __init__(self):
            self._plugins: dict[str, Q8LLDPractice.IPlugin] = {}

        def register(self, plugin: Q8LLDPractice.IPlugin):
            self._plugins[plugin.name] = plugin
            return self

        def get(self, name: str) -> Q8LLDPractice.IPlugin:
            if name not in self._plugins:
                raise KeyError(f"Plugin '{name}' not found")
            return self._plugins[name]

        def list_plugins(self) -> list[str]:
            return list(self._plugins.keys())

    # ---- 依赖注入管理器 ----
    class PluginManager:
        """通过构造函数注入Registry和Config（DIP：依赖抽象）"""
        def __init__(self, registry: "Q8LLDPractice.IPluginRegistry"):
            self._registry = registry
            self._initialized: list[str] = []

        def load_plugin(self, plugin: "Q8LLDPractice.IPlugin", config: dict):
            self._registry.register(plugin)
            plugin.initialize(config)
            self._initialized.append(plugin.name)
            return self

        def execute(self, plugin_name: str, input_data: Any) -> Any:
            plugin = self._registry.get(plugin_name)
            return plugin.execute(input_data)

        def shutdown_all(self):
            for name in self._initialized:
                self._registry.get(name).shutdown()
            self._initialized.clear()

    # ---- 具体插件实现 ----
    class LoggerPlugin(IPlugin):
        @property
        def name(self): return "logger"
        @property
        def version(self): return "1.0.0"

        def initialize(self, config):
            self._level = config.get("level", "INFO")

        def execute(self, input_data):
            return f"[{self._level}] {input_data}"

        def shutdown(self): pass

    class FilterPlugin(IPlugin):
        @property
        def name(self): return "filter"
        @property
        def version(self): return "1.0.0"

        def initialize(self, config):
            self._keywords = config.get("keywords", [])

        def execute(self, input_data):
            if isinstance(input_data, str):
                for kw in self._keywords:
                    input_data = input_data.replace(kw, "***")
            return input_data

        def shutdown(self): pass

    class TransformerPlugin(IPlugin):
        @property
        def name(self): return "transformer"
        @property
        def version(self): return "1.0.0"

        def initialize(self, config):
            self._mode = config.get("mode", "upper")

        def execute(self, input_data):
            if self._mode == "upper":
                return input_data.upper() if isinstance(input_data, str) else input_data
            elif self._mode == "lower":
                return input_data.lower() if isinstance(input_data, str) else input_data
            return input_data

        def shutdown(self): pass

    def test_plugin_system(self):
        self.print_plugin_system_uml()

        # DIP: PluginManager 依赖 IPluginRegistry 抽象
        registry = self.PluginRegistry()
        manager = self.PluginManager(registry)

        # 注册并初始化插件
        manager.load_plugin(self.LoggerPlugin(), {"level": "DEBUG"})
        manager.load_plugin(self.FilterPlugin(), {"keywords": ["secret", "password"]})
        manager.load_plugin(self.TransformerPlugin(), {"mode": "upper"})

        # 列出插件
        assert sorted(registry.list_plugins()) == ["filter", "logger", "transformer"]

        # 执行插件链
        log_result = manager.execute("logger", "System started")
        assert "[DEBUG]" in log_result

        filter_result = manager.execute("filter", "my secret password is here")
        assert "secret" not in filter_result
        assert "password" not in filter_result
        assert "***" in filter_result

        transform_result = manager.execute("transformer", "hello world")
        assert transform_result == "HELLO WORLD"

        # 关闭
        manager.shutdown_all()
        assert len(manager._initialized) == 0

        # ISP验证：配置接口独立于执行接口
        config = self.BaseConfig()
        config._schema = {"level": str}
        assert config.validate({"level": "INFO"}) is True
        assert config.validate({}) is False

        print("  ✅ 插件系统 —— 接口隔离(ISP) + 依赖注入(DIP) + 可扩展")

    def run(self):
        print("=" * 60)
        print("Q8: LLD与SOLID（UML类图 / 接口隔离 / 依赖注入 / 插件系统）")
        print("=" * 60)
        self.test_plugin_system()
        print()


# ============================================================
# Q9: 分布式系统核心 — CAP/BASE/一致性哈希/Raft/分布式锁
# ============================================================

class Q9DistributedSystems:
    """分布式系统核心：CAP演示、BASE vs ACID、一致性哈希、Raft简化版、分布式锁"""

    # ---------- 1. CAP定理演示 ----------
    class CAPSimulator:
        """模拟网络分区场景下的CAP选择"""
        def __init__(self, nodes: list[str]):
            self.nodes = {n: {"data": {}, "available": True} for n in nodes}
            self.partition: set[tuple[str, str]] = set()  # 被分区的节点对

        def write(self, node: str, key: str, value: str) -> str:
            if not self.nodes[node]["available"]:
                return f"❌ {node} unavailable"
            self.nodes[node]["data"][key] = value
            # 同步到其他可达节点
            for other in self.nodes:
                if other != node and (node, other) not in self.partition and (other, node) not in self.partition:
                    if self.nodes[other]["available"]:
                        self.nodes[other]["data"][key] = value
            return f"✅ Written to {node}"

        def read(self, node: str, key: str) -> str:
            if not self.nodes[node]["available"]:
                return f"❌ {node} unavailable"
            return self.nodes[node]["data"].get(key, "null")

        def create_partition(self, n1: str, n2: str):
            self.partition.add((n1, n2))
            self.partition.add((n2, n1))

        def heal_partition(self, n1: str, n2: str):
            self.partition.discard((n1, n2))
            self.partition.discard((n2, n1))

    def test_cap(self):
        sim = self.CAPSimulator(["A", "B", "C"])
        # 正常写入，三节点一致
        sim.write("A", "x", "1")
        assert sim.read("B", "x") == "1"
        assert sim.read("C", "x") == "1"

        # 网络分区：A <-> B 断开
        sim.create_partition("A", "B")
        sim.write("A", "x", "2")  # A写，C可见，B不可见
        assert sim.read("A", "x") == "2"
        assert sim.read("C", "x") == "2"
        assert sim.read("B", "x") == "1"  # B仍然是旧值 → 不一致

        # 恢复分区
        sim.heal_partition("A", "B")
        sim.write("A", "x", "3")
        assert sim.read("B", "x") == "3"  # 恢复一致性
        print("  ✅ CAP定理演示 —— 网络分区下一致性 vs 可用性")

    # ---------- 2. BASE vs ACID ----------
    def test_base_vs_acid(self):
        acid_props = {
            "A(Atomicity)": "事务要么全部成功，要么全部回滚",
            "C(Consistency)": "事务前后数据保持一致状态",
            "I(Isolation)": "并发事务互不干扰",
            "D(Durability)": "事务提交后永久保存",
        }
        base_props = {
            "BA(Basically Available)": "基本可用，允许损失部分可用性",
            "S(Soft State)": "软状态，允许中间状态存在",
            "E(Eventual Consistency)": "最终一致性，数据最终达到一致",
        }
        assert len(acid_props) == 4
        assert len(base_props) == 3

        # 模拟ACID事务
        class ACIDTransaction:
            def __init__(self):
                self.db = {"balance_A": 100, "balance_B": 50}
                self._backup = None

            def execute(self, from_acc: str, to_acc: str, amount: int) -> bool:
                self._backup = self.db.copy()
                try:
                    if self.db[from_acc] < amount:
                        raise ValueError("Insufficient balance")
                    self.db[from_acc] -= amount  # Atomicity: all or nothing
                    self.db[to_acc] += amount
                    # Consistency: total unchanged
                    assert self.db["balance_A"] + self.db["balance_B"] == 150
                    return True
                except Exception:
                    self.db = self._backup  # Rollback
                    return False

        tx = ACIDTransaction()
        assert tx.execute("balance_A", "balance_B", 30) is True
        assert tx.db["balance_A"] == 70
        assert tx.db["balance_B"] == 80
        assert tx.execute("balance_A", "balance_B", 200) is False  # 余额不足，回滚
        assert tx.db["balance_A"] == 70  # 未变

        # 模拟BASE：最终一致性
        class BASESystem:
            def __init__(self):
                self.primary = {"count": 0}
                self.replicas = [{"count": 0}, {"count": 0}]
                self._pending: list[tuple[int, int]] = []

            def write(self, value: int):
                self.primary["count"] = value  # 立即写主节点
                self._pending.append(value)  # 异步同步

            def sync(self):
                for v in self._pending:
                    for r in self.replicas:
                        r["count"] = v  # 最终一致
                self._pending.clear()

        base_sys = BASESystem()
        base_sys.write(10)
        assert base_sys.replicas[0]["count"] == 0  # 软状态：副本暂不一致
        base_sys.sync()
        assert base_sys.replicas[0]["count"] == 10  # 最终一致
        print("  ✅ BASE vs ACID —— 强一致性事务 vs 最终一致性")

    # ---------- 3. 一致性哈希（含虚拟节点） ----------
    class ConsistentHashRing:
        def __init__(self, nodes: list[str], vnodes: int = 150):
            self.ring: dict[int, str] = {}
            self.sorted_keys: list[int] = []
            for node in nodes:
                for v in range(vnodes):
                    h = self._hash(f"{node}#{v}")
                    self.ring[h] = node
                    bisect.insort(self.sorted_keys, h)

        @staticmethod
        def _hash(s: str) -> int:
            return int(hashlib.md5(s.encode()).hexdigest(), 16)

        def get_node(self, key: str) -> str:
            h = self._hash(key)
            idx = bisect.bisect_right(self.sorted_keys, h)
            if idx >= len(self.sorted_keys):
                idx = 0
            return self.ring[self.sorted_keys[idx]]

        def add_node(self, node: str, vnodes: int = 150):
            for v in range(vnodes):
                h = self._hash(f"{node}#{v}")
                self.ring[h] = node
                bisect.insort(self.sorted_keys, h)

        def remove_node(self, node: str, vnodes: int = 150):
            to_remove = []
            for v in range(vnodes):
                h = self._hash(f"{node}#{v}")
                if h in self.ring:
                    to_remove.append(h)
            for h in to_remove:
                del self.ring[h]
                idx = bisect.bisect_left(self.sorted_keys, h)
                if idx < len(self.sorted_keys) and self.sorted_keys[idx] == h:
                    self.sorted_keys.pop(idx)

    def test_consistent_hash(self):
        ring = self.ConsistentHashRing(["node-A", "node-B", "node-C"], vnodes=100)
        # 一致性：同一key总映射到同一节点
        assert ring.get_node("user:1") == ring.get_node("user:1")
        # 分布均匀
        dist = defaultdict(int)
        for i in range(3000):
            dist[ring.get_node(f"key:{i}")] += 1
        counts = list(dist.values())
        assert max(counts) / min(counts) < 1.5  # 虚拟节点使分布均匀

        # 迁移率测试：加一个节点，大部分key不变
        before = {f"key:{i}": ring.get_node(f"key:{i}") for i in range(1000)}
        ring.add_node("node-D", vnodes=100)
        after = {f"key:{i}": ring.get_node(f"key:{i}") for i in range(1000)}
        migrated = sum(1 for k in before if before[k] != after[k])
        migration_rate = migrated / 1000
        assert migration_rate < 0.35  # 理论约1/4，迁移率应低
        print(f"  ✅ 一致性哈希 —— 虚拟节点分布均匀，加节点迁移率={migration_rate:.1%}")

    # ---------- 4. Raft共识算法简化版 ----------
    class RaftNode:
        """Raft简化版：Leader选举 + 日志复制"""
        def __init__(self, node_id: str, peers: list[str]):
            self.node_id = node_id
            self.peers = peers
            self.state = "follower"  # follower / candidate / leader
            self.term = 0
            self.voted_for: Optional[str] = None
            self.log: list[dict] = []
            self.commit_index = -1
            self.leader: Optional[str] = None
            self.votes_received: set[str] = set()

        def start_election(self, all_nodes: dict[str, "Q9DistributedSystems.RaftNode"]):
            self.state = "candidate"
            self.term += 1
            self.voted_for = self.node_id
            self.votes_received = {self.node_id}
            # 请求其他节点投票
            for peer_id in self.peers:
                if peer_id in all_nodes:
                    peer = all_nodes[peer_id]
                    if peer.state != "leader" and (peer.voted_for is None or peer.voted_for == self.node_id):
                        if peer.term <= self.term:
                            peer.voted_for = self.node_id
                            peer.term = self.term
                            self.votes_received.add(peer_id)
            # 多数票则成为Leader
            if len(self.votes_received) > len(self.peers) // 2:
                self.state = "leader"
                self.leader = self.node_id
                for peer_id in self.peers:
                    if peer_id != self.node_id and peer_id in all_nodes:
                        all_nodes[peer_id].leader = self.node_id
                        all_nodes[peer_id].state = "follower"
                return True
            return False

        def append_log(self, entry: dict, all_nodes: dict[str, "Q9DistributedSystems.RaftNode"]):
            """Leader将日志复制到所有Follower"""
            if self.state != "leader":
                return False
            self.log.append(entry)
            replicated = 1  # Leader自己
            for peer_id in self.peers:
                if peer_id != self.node_id and peer_id in all_nodes:
                    all_nodes[peer_id].log.append(entry.copy())
                    replicated += 1
            # 多数复制则提交
            if replicated > len(self.peers) // 2:
                self.commit_index = len(self.log) - 1
                for peer_id in self.peers:
                    if peer_id != self.node_id and peer_id in all_nodes:
                        all_nodes[peer_id].commit_index = self.commit_index
                return True
            return False

    def test_raft(self):
        nodes = {nid: self.RaftNode(nid, ["n1", "n2", "n3"]) for nid in ["n1", "n2", "n3"]}
        # n1发起选举
        elected = nodes["n1"].start_election(nodes)
        assert elected is True
        assert nodes["n1"].state == "leader"
        assert nodes["n1"].leader == "n1"
        assert nodes["n2"].leader == "n1"
        assert nodes["n3"].leader == "n1"

        # Leader复制日志
        entry1 = {"term": 1, "command": "SET x=1"}
        committed = nodes["n1"].append_log(entry1, nodes)
        assert committed is True
        assert len(nodes["n1"].log) == 1
        assert len(nodes["n2"].log) == 1
        assert len(nodes["n3"].log) == 1
        assert nodes["n1"].commit_index == 0
        assert nodes["n2"].commit_index == 0

        # 再写一条
        entry2 = {"term": 1, "command": "SET y=2"}
        nodes["n1"].append_log(entry2, nodes)
        assert len(nodes["n1"].log) == 2
        assert nodes["n1"].commit_index == 1
        print("  ✅ Raft简化版 —— Leader选举 + 日志复制 + 多数提交")

    # ---------- 5. 分布式锁（基于Redis模拟） ----------
    class RedisSimulator:
        """模拟Redis的SET NX语义"""
        def __init__(self):
            self._store: dict[str, str] = {}
            self._lock = threading.Lock()

        def set_nx(self, key: str, value: str, ttl: float = 10.0) -> bool:
            with self._lock:
                if key in self._store:
                    return False
                self._store[key] = value
                return True

        def get(self, key: str) -> Optional[str]:
            return self._store.get(key)

        def delete(self, key: str, expected_value: str) -> bool:
            with self._lock:
                if self._store.get(key) == expected_value:
                    del self._store[key]
                    return True
                return False

    class DistributedLock:
        """基于Redis模拟的分布式锁"""
        def __init__(self, redis: "Q9DistributedSystems.RedisSimulator", lock_key: str, ttl: float = 10.0):
            self.redis = redis
            self.lock_key = lock_key
            self.ttl = ttl
            self.lock_value: Optional[str] = None

        def acquire(self, timeout: float = 5.0) -> bool:
            start = time.time()
            self.lock_value = f"{threading.current_thread().name}:{time.time()}"
            while time.time() - start < timeout:
                if self.redis.set_nx(self.lock_key, self.lock_value, self.ttl):
                    return True
                time.sleep(0.05)
            return False

        def release(self) -> bool:
            if self.lock_value:
                return self.redis.delete(self.lock_key, self.lock_value)
            return False

    def test_distributed_lock(self):
        redis = self.RedisSimulator()
        lock = self.DistributedLock(redis, "resource:1", ttl=5.0)
        # 加锁
        assert lock.acquire(timeout=1.0) is True
        # 另一个线程无法加锁
        lock2 = self.DistributedLock(redis, "resource:1", ttl=5.0)
        assert lock2.acquire(timeout=0.2) is False  # 被占用
        # 释放锁
        assert lock.release() is True
        # 现在可以加锁
        assert lock2.acquire(timeout=1.0) is True
        assert lock2.release() is True

        # 多线程竞争测试
        results: list[bool] = []
        lock_holder = self.DistributedLock(redis, "shared:1", ttl=5.0)

        def try_lock():
            l = self.DistributedLock(redis, "shared:1", ttl=5.0)
            results.append(l.acquire(timeout=0.1))

        threads = [threading.Thread(target=try_lock) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # 最多一个成功
        assert sum(results) <= 1
        print("  ✅ 分布式锁 —— Redis SET NX + 唯一值释放 + 多线程竞争")

    def run(self):
        print("=" * 60)
        print("Q9: 分布式系统核心（CAP / BASE / 一致性哈希 / Raft / 分布式锁）")
        print("=" * 60)
        self.test_cap()
        self.test_base_vs_acid()
        self.test_consistent_hash()
        self.test_raft()
        self.test_distributed_lock()
        print()


# ============================================================
# Q10: 容量规划与性能工程
# ============================================================

class Q10CapacityPlanning:
    """容量规划与性能工程：Little's Law / 排队论 / 容量计算器 / 压测模拟 / 监控指标"""

    # ---------- 1. QPS估算 (Little's Law) ----------
    def test_littles_law(self):
        """
        Little's Law: L = λ × W
        L = 系统中平均请求数 (并发数)
        λ = 到达率 (QPS)
        W = 平均响应时间 (秒)
        """
        # 场景：平均响应时间200ms，并发用户数1000
        W = 0.2  # 200ms
        L = 1000  # 并发请求数
        QPS = L / W  # Little's Law
        assert QPS == 5000.0

        # 反推：已知QPS和响应时间，求并发数
        qps = 10000
        response_time = 0.05  # 50ms
        concurrency = qps * response_time
        assert concurrency == 500.0

        # 反推：已知QPS和并发数，求最大响应时间
        qps = 2000
        concurrency = 400
        max_rt = concurrency / qps
        assert max_rt == 0.2
        print(f"  ✅ Little's Law —— L={L}, W={W}s → QPS={QPS:.0f}")

    # ---------- 2. 性能瓶颈分析（排队论基础） ----------
    def test_queueing_theory(self):
        """
        M/M/1队列模型:
        ρ = λ/μ (利用率)
        Lq = ρ²/(1-ρ) (队列中平均等待数)
        Wq = Lq/λ (平均等待时间)
        """
        # 服务率: 每秒处理500请求
        mu = 500  # req/s
        # 到达率: 每秒400请求
        lam = 400  # req/s

        rho = lam / mu  # 利用率
        assert abs(rho - 0.8) < 0.001

        # 队列平均等待数
        Lq = (rho ** 2) / (1 - rho)
        assert abs(Lq - 3.2) < 0.001

        # 平均等待时间
        Wq = Lq / lam
        assert abs(Wq - 0.008) < 0.001  # 8ms

        # 利用率越高，等待时间增长越快（非线性）
        wait_times = []
        for utilization in [0.5, 0.7, 0.8, 0.9, 0.95, 0.99]:
            if utilization < 1:
                w = utilization / (mu * (1 - utilization))
                wait_times.append((utilization, w))
        # 利用率0.9的等待时间远大于0.5
        w_50 = next(w for u, w in wait_times if u == 0.5)
        w_90 = next(w for u, w in wait_times if u == 0.9)
        assert w_90 > w_50 * 5
        print(f"  ✅ 排队论 —— ρ={rho}, Lq={Lq}, Wq={Wq*1000:.0f}ms (利用率越高延迟非线性增长)")

    # ---------- 3. 容量规划计算器 ----------
    class CapacityCalculator:
        def __init__(self):
            self.metrics: dict[str, Any] = {}

        def plan(self, daily_users: int, avg_requests_per_user: int,
                 peak_multiplier: float = 3.0, target_p99_ms: float = 200,
                 single_node_qps: float = 500, safety_margin: float = 1.5) -> dict:
            daily_requests = daily_users * avg_requests_per_user
            avg_qps = daily_requests / 86400  # 24小时
            peak_qps = avg_qps * peak_multiplier
            required_qps = peak_qps * safety_margin
            min_nodes = math.ceil(required_qps / single_node_qps)

            result = {
                "daily_requests": daily_requests,
                "avg_qps": round(avg_qps, 1),
                "peak_qps": round(peak_qps, 1),
                "required_qps": round(required_qps, 1),
                "single_node_qps": single_node_qps,
                "min_nodes": min_nodes,
                "target_p99_ms": target_p99_ms,
            }
            self.metrics = result
            return result

    def test_capacity_calculator(self):
        calc = self.CapacityCalculator()
        result = calc.plan(
            daily_users=1_000_000,
            avg_requests_per_user=20,
            peak_multiplier=3.0,
            target_p99_ms=200,
            single_node_qps=500,
            safety_margin=1.5
        )
        assert result["daily_requests"] == 20_000_000
        assert result["avg_qps"] > 230  # 20M / 86400 ≈ 231.5
        assert result["peak_qps"] > 690
        assert result["required_qps"] > 1000
        assert result["min_nodes"] >= 3
        assert isinstance(result["min_nodes"], int)
        print(f"  ✅ 容量规划计算器 —— 日请求{result['daily_requests']:,} → 需{result['min_nodes']}节点")

    # ---------- 4. 压测模拟 ----------
    def test_stress_test(self):
        """用Python并发模拟压测"""
        results: list[dict] = []
        lock = threading.Lock()

        def mock_api_call(request_id: int) -> dict:
            start = time.time()
            # 模拟处理时间：50-150ms
            processing_time = random.uniform(0.05, 0.15)
            time.sleep(processing_time)
            # 模拟5%错误率
            is_error = random.random() < 0.05
            elapsed = (time.time() - start) * 1000  # ms
            return {
                "request_id": request_id,
                "latency_ms": round(elapsed, 1),
                "success": not is_error,
            }

        total_requests = 100
        concurrency = 20

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = {executor.submit(mock_api_call, i): i for i in range(total_requests)}
            for future in as_completed(futures):
                with lock:
                    results.append(future.result())

        assert len(results) == total_requests
        latencies = sorted([r["latency_ms"] for r in results])
        success_count = sum(1 for r in results if r["success"])
        error_rate = (total_requests - success_count) / total_requests

        # 验证统计
        assert 0 <= error_rate <= 1.0
        assert all(l > 0 for l in latencies)
        assert len(latencies) == total_requests
        print(f"  ✅ 压测模拟 —— {total_requests}请求/{concurrency}并发 → 错误率={error_rate:.1%}")

    # ---------- 5. 性能监控指标计算 ----------
    def test_perf_metrics(self):
        """计算P50/P90/P99/错误率等监控指标"""
        # 模拟1000个请求的延迟数据
        random.seed(42)
        latencies = []
        for _ in range(950):
            latencies.append(random.uniform(20, 100))  # 正常请求
        for _ in range(45):
            latencies.append(random.uniform(100, 300))  # 慢请求
        for _ in range(5):
            latencies.append(random.uniform(300, 1000))  # 超时请求
        latencies.sort()

        n = len(latencies)
        assert n == 1000

        def percentile(data: list[float], p: float) -> float:
            """计算百分位数"""
            k = (len(data) - 1) * p / 100
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return data[int(k)]
            return data[f] + (data[c] - data[f]) * (k - f)

        p50 = percentile(latencies, 50)
        p90 = percentile(latencies, 90)
        p99 = percentile(latencies, 99)
        avg = statistics.mean(latencies)
        error_count = sum(1 for l in latencies if l > 500)  # >500ms视为错误
        error_rate = error_count / n

        # 验证
        assert 20 <= p50 <= 100  # 中位数在正常范围
        assert p90 > p50  # P90 > P50
        assert p99 > p90  # P99 > P90
        assert p99 > 200  # P99包含慢请求
        assert 0 <= error_rate <= 0.01  # 约0.5%
        assert avg > p50  # 均值受长尾影响大于中位数

        # SLA检查
        sla_p99 = 500  # ms
        sla_pass = p99 < sla_p99
        metrics_summary = {
            "total_requests": n,
            "p50_ms": round(p50, 1),
            "p90_ms": round(p90, 1),
            "p99_ms": round(p99, 1),
            "avg_ms": round(avg, 1),
            "error_rate": f"{error_rate:.2%}",
            "sla_target_p99": sla_p99,
            "sla_passed": sla_pass,
        }
        print(f"  ✅ 性能监控指标 —— P50={metrics_summary['p50_ms']}ms, "
              f"P90={metrics_summary['p90_ms']}ms, P99={metrics_summary['p99_ms']}ms, "
              f"错误率={metrics_summary['error_rate']}")

    def run(self):
        print("=" * 60)
        print("Q10: 容量规划与性能工程（Little's Law / 排队论 / 容量计算 / 压测 / 监控）")
        print("=" * 60)
        self.test_littles_law()
        self.test_queueing_theory()
        self.test_capacity_calculator()
        self.test_stress_test()
        self.test_perf_metrics()
        print()


# ============================================================
# 主函数
# ============================================================

def main():
    print("\n" + "🔥" * 30)
    print("  阶段十·工程进阶 — 系统设计练习（Q6-Q10）")
    print("🔥" * 30 + "\n")

    Q6HLDBasics().run()
    Q7HLDPractice().run()
    Q8LLDPractice().run()
    Q9DistributedSystems().run()
    Q10CapacityPlanning().run()

    print("=" * 60)
    print("  🎉 Q6-Q10 全部通过！")
    print("=" * 60)


if __name__ == "__main__":
    main()
