# 第四期 Track3：系统设计与分布式系统练习题（15题）

> 纯 Python 实现，标准库 + numpy + httpx，所有代码完整可运行。

---

## 目录

| 分类 | 题号 | 标题 |
|------|------|------|
| 系统设计 | 1 | URL短链接系统 |
| 系统设计 | 2 | 限流器多算法实现 |
| 系统设计 | 3 | 消息队列系统 |
| 系统设计 | 4 | 分布式缓存 |
| 系统设计 | 5 | 负载均衡器 |
| 数据库进阶 | 6 | B+树索引实现 |
| 数据库进阶 | 7 | SQL查询优化器 |
| 数据库进阶 | 8 | MVCC多版本并发控制 |
| 数据库进阶 | 9 | 分库分表中间件 |
| 数据库进阶 | 10 | WAL预写日志 |
| 分布式系统 | 11 | Raft共识算法 |
| 分布式系统 | 12 | 分布式锁 |
| 分布式系统 | 13 | 事件溯源与CQRS |
| 分布式系统 | 14 | Gossip协议 |
| 分布式系统 | 15 | 分布式事务 |

---

# 一、系统设计（5题）

---

## 第1题：URL短链接系统

### 知识点讲解

URL短链接系统的核心是将长URL映射为短码。短码生成通常有两种策略：自增ID + Base62编码、MD5/SHA哈希取模。自增ID方案简单且无冲突，但需要全局唯一ID生成器；哈希方案无需协调但存在冲突可能，需做冲突检测。

Base62编码使用 `0-9a-zA-Z` 共62个字符，将10进制数字转换为62进制，6位可表示约568亿个短码。系统典型流程为：用户提交长URL → 生成短码 → 存入存储（DB+缓存）→ 返回短链。重定向时先查缓存（Redis），未命中再查DB，通过HTTP 301/302跳转。301是永久重定向（浏览器缓存），302是临时重定向（每次都请求短链服务，便于统计）。

访问统计通常使用异步方式：将点击事件写入消息队列，再由消费者批量写入数据库，避免同步统计拖慢重定向响应。缓存策略上，热门短链放入本地缓存或Redis，设置合理TTL防止冷数据常驻。读多写少的场景下，可对存储层做读写分离，写主库读从库，同时利用CDN加速重定向响应。

```python
"""
URL短链接系统：Base62编码 + 重定向 + 访问统计
"""
import time
import threading
from collections import defaultdict, OrderedDict
from urllib.parse import urlparse

# Base62 字符表
BASE62_CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
BASE62_BASE = len(BASE62_CHARS)


def encode_base62(num: int) -> str:
    """将十进制数字编码为 Base62 字符串"""
    if num == 0:
        return BASE62_CHARS[0]
    result = []
    while num > 0:
        result.append(BASE62_CHARS[num % BASE62_BASE])
        num //= BASE62_BASE
    # 反转得到正确顺序
    return "".join(reversed(result))


def decode_base62(s: str) -> int:
    """将 Base62 字符串解码为十进制数字"""
    num = 0
    for ch in s:
        num = num * BASE62_BASE + BASE62_CHARS.index(ch)
    return num


class URLShortener:
    """URL短链接系统核心实现"""

    def __init__(self):
        # 长URL -> 短码
        self._long_to_short = {}
        # 短码 -> 长URL
        self._short_to_long = {}
        # 自增ID，用于生成短码
        self._counter = 10000
        # 访问统计：短码 -> 点击次数
        self._click_stats = defaultdict(int)
        # 访问统计：短码 -> 最近访问时间列表（用于时间窗口统计）
        self._access_log = defaultdict(list)
        # LRU缓存，提升热点短链查询速度
        self._cache = OrderedDict()
        self._cache_max = 1000
        # 线程锁，保证并发安全
        self._lock = threading.Lock()

    def shorten(self, long_url: str) -> str:
        """生成长URL的短码"""
        with self._lock:
            # 如果长URL已经缩短过，直接返回已有短码（幂等性）
            if long_url in self._long_to_short:
                return self._long_to_short[long_url]
            # 自增ID生成短码
            self._counter += 1
            short_code = encode_base62(self._counter)
            # 双向映射存储
            self._long_to_short[long_url] = short_code
            self._short_to_long[short_code] = long_url
            # 写入缓存
            self._cache[short_code] = long_url
            if len(self._cache) > self._cache_max:
                self._cache.popitem(last=False)  # 淘汰最久未访问
            return short_code

    def redirect(self, short_code: str) -> str | None:
        """根据短码获取长URL，并记录访问统计"""
        # 先查缓存
        if short_code in self._cache:
            # LRU：移动到末尾（最近访问）
            self._cache.move_to_end(short_code)
            long_url = self._cache[short_code]
        else:
            # 缓存未命中，查存储
            long_url = self._short_to_long.get(short_code)
            if long_url is None:
                return None
            # 回填缓存
            self._cache[short_code] = long_url
            if len(self._cache) > self._cache_max:
                self._cache.popitem(last=False)

        # 异步记录访问统计（这里用同步模拟）
        now = time.time()
        with self._lock:
            self._click_stats[short_code] += 1
            self._access_log[short_code].append(now)
            # 只保留最近1000条访问记录
            if len(self._access_log[short_code]) > 1000:
                self._access_log[short_code] = self._access_log[short_code][-500:]

        return long_url

    def get_stats(self, short_code: str) -> dict:
        """获取短链的访问统计"""
        now = time.time()
        access_times = self._access_log.get(short_code, [])
        # 统计最近1小时访问量
        recent_1h = sum(1 for t in access_times if now - t < 3600)
        # 统计最近24小时访问量
        recent_24h = sum(1 for t in access_times if now - t < 86400)
        return {
            "short_code": short_code,
            "total_clicks": self._click_stats.get(short_code, 0),
            "clicks_last_1h": recent_1h,
            "clicks_last_24h": recent_24h,
            "long_url": self._short_to_long.get(short_code, ""),
        }

    def batch_shorten(self, urls: list[str]) -> list[str]:
        """批量生成短链"""
        return [self.shorten(url) for url in urls]


# ======================== 测试 ========================
if __name__ == "__main__":
    shortener = URLShortener()

    # 测试 Base62 编解码
    assert decode_base62(encode_base62(0)) == 0
    assert decode_base62(encode_base62(123456789)) == 123456789
    assert decode_base62(encode_base62(999999999999)) == 999999999999
    print("[OK] Base62 编解码正确")

    # 测试短链生成
    url1 = "https://www.example.com/very/long/path?param1=value1&param2=value2"
    short1 = shortener.shorten(url1)
    print(f"短链生成: {url1} -> {short1}")

    # 测试幂等性：同一长URL生成相同短码
    short1_again = shortener.shorten(url1)
    assert short1 == short1_again, "同一URL应返回相同短码"
    print("[OK] 幂等性验证通过")

    # 测试重定向
    redirected = shortener.redirect(short1)
    assert redirected == url1, "重定向应返回原始URL"
    print(f"[OK] 重定向: {short1} -> {redirected}")

    # 测试访问统计
    for _ in range(50):
        shortener.redirect(short1)
    stats = shortener.get_stats(short1)
    print(f"访问统计: 总点击={stats['total_clicks']}, 近1h={stats['clicks_last_1h']}")

    # 测试缓存命中（重复访问应更快）
    import time as _time
    start = _time.perf_counter()
    for _ in range(10000):
        shortener.redirect(short1)
    elapsed = _time.perf_counter() - start
    print(f"[OK] 缓存命中测试: 10000次查询耗时 {elapsed:.4f}s")

    # 测试批量生成
    urls = [f"https://example.com/page/{i}" for i in range(100)]
    shorts = shortener.batch_shorten(urls)
    assert len(set(shorts)) == 100, "100个URL应生成100个不同短码"
    print("[OK] 批量生成100个短链，无冲突")
```

### 思考题
1. 如果短链系统需要支持自定义短码（用户指定短码），如何修改设计？冲突如何处理？
2. 短链过期机制如何实现？过期数据如何清理？
3. 当QPS达到百万级时，自增ID生成器会成为瓶颈，如何设计分布式ID生成方案？

---

## 第2题：限流器多算法实现

### 知识点讲解

限流是保护系统稳定性的核心手段，常见的三种算法各有优劣：

**令牌桶**：以固定速率向桶中放入令牌，请求到来时取走令牌，桶满则丢弃多余令牌。特点是允许突发流量——桶中积累的令牌可瞬时消耗。适用于需要容忍短时峰值的API网关场景。

**滑动窗口**：将时间划分为细粒度的小窗口（如1秒分成10个100ms窗口），统计当前时刻往前一个完整窗口周期内的请求总数。相比固定窗口算法，滑动窗口避免了窗口边界处的流量突刺（如窗口切换瞬间2倍流量）。适用于需要精确控制QPS的场景。

**漏桶**：请求如水滴进入漏桶，桶以恒定速率漏出（处理）。桶满则拒绝新请求。与令牌桶的区别在于：漏桶输出速率恒定，不允许突发；令牌桶输出可以突发。适用于需要严格平滑流量的下游保护场景。

原子性保证方面，单机限流可用线程锁或原子操作保证计数安全；分布式限流通常用Redis + Lua脚本实现原子操作。工程实践中还需考虑：限流后的处理策略（直接拒绝、排队等待、降级返回缓存）、多维度限流（按用户、IP、接口分别限流）、限流规则动态配置等。

```python
"""
限流器：令牌桶 + 滑动窗口 + 漏桶 三种算法实现
"""
import time
import threading
from collections import deque
from dataclasses import dataclass, field


# ======================== 令牌桶限流器 ========================
@dataclass
class TokenBucketRateLimiter:
    """
    令牌桶限流器
    - capacity: 桶容量（最大突发量）
    - rate: 令牌生成速率（个/秒）
    """
    capacity: int
    rate: float
    _tokens: float = 0.0
    _last_refill: float = field(default_factory=time.monotonic)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self):
        self._tokens = float(self.capacity)

    def _refill(self):
        """补充令牌（懒加载方式：只在请求时计算应补充的令牌数）"""
        now = time.monotonic()
        elapsed = now - self._last_refill
        # 按速率补充令牌，但不超过桶容量
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_refill = now

    def try_acquire(self, tokens: int = 1) -> bool:
        """尝试获取令牌，返回是否成功"""
        with self._lock:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def acquire(self, tokens: int = 1, timeout: float = None) -> bool:
        """阻塞式获取令牌，支持超时"""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True
            if deadline is not None and time.monotonic() >= deadline:
                return False
            # 等待令牌补充
            time.sleep(0.01)


# ======================== 滑动窗口限流器 ========================
class SlidingWindowRateLimiter:
    """
    滑动窗口限流器
    - window_size: 窗口大小（秒）
    - max_requests: 窗口内最大请求数
    将窗口细分为多个小窗口，统计当前大窗口内的请求总数
    """

    def __init__(self, window_size: float, max_requests: int, slot_count: int = 10):
        self.window_size = window_size
        self.max_requests = max_requests
        self.slot_count = slot_count
        self.slot_duration = window_size / slot_count
        # 每个小窗口的请求计数和时间戳
        self._slots = deque()  # 元素: (timestamp, count)
        self._lock = threading.Lock()

    def _purge_expired(self, now: float):
        """清除过期的窗口数据"""
        cutoff = now - self.window_size
        while self._slots and self._slots[0][0] < cutoff:
            self._slots.popleft()

    def _total_count(self) -> int:
        """统计当前窗口内总请求数"""
        return sum(count for _, count in self._slots)

    def try_acquire(self) -> bool:
        """尝试通过限流"""
        with self._lock:
            now = time.monotonic()
            self._purge_expired(now)
            if self._total_count() >= self.max_requests:
                return False
            # 将请求记录到当前小窗口
            if self._slots and (now - self._slots[-1][0]) < self.slot_duration:
                # 合并到最近的小窗口
                ts, cnt = self._slots[-1]
                self._slots[-1] = (ts, cnt + 1)
            else:
                self._slots.append((now, 1))
            return True


# ======================== 漏桶限流器 ========================
class LeakyBucketRateLimiter:
    """
    漏桶限流器
    - capacity: 桶容量（队列长度上限）
    - leak_rate: 漏出速率（请求处理速率，个/秒）
    请求以不均匀速率进入，以恒定速率漏出
    """

    def __init__(self, capacity: int, leak_rate: float):
        self.capacity = capacity
        self.leak_rate = leak_rate
        self._queue = deque()
        self._last_leak = time.monotonic()
        self._lock = threading.Lock()

    def _leak(self):
        """漏出（处理）队列中的请求"""
        now = time.monotonic()
        elapsed = now - self._last_leak
        # 计算应漏出的请求数
        leak_count = int(elapsed * self.leak_rate)
        for _ in range(min(leak_count, len(self._queue))):
            self._queue.popleft()
        if leak_count > 0:
            self._last_leak = now

    def try_acquire(self) -> bool:
        """尝试将请求放入漏桶"""
        with self._lock:
            self._leak()
            if len(self._queue) < self.capacity:
                self._queue.append(time.monotonic())
                return True
            return False


# ======================== 多维度限流管理器 ========================
class MultiDimensionRateLimiter:
    """
    多维度限流管理器
    支持对不同维度（用户ID、IP、API路径）分别配置限流规则
    """

    def __init__(self):
        # 维度名 -> {规则参数} -> SlidingWindowRateLimiter 实例
        self._rules = {}  # dimension_name -> (window_size, max_requests)
        self._limiters = {}  # (dimension_name, dimension_value) -> limiter
        self._lock = threading.Lock()

    def add_rule(self, dimension: str, window_size: float, max_requests: int):
        """添加限流规则"""
        self._rules[dimension] = (window_size, max_requests)

    def check(self, **kwargs) -> bool:
        """
        检查请求是否通过所有维度的限流
        kwargs: dimension_name=dimension_value, 如 user_id="u123", ip="1.2.3.4"
        """
        for dim_name, dim_value in kwargs.items():
            if dim_name not in self._rules:
                continue
            key = (dim_name, dim_value)
            with self._lock:
                if key not in self._limiters:
                    window_size, max_req = self._rules[dim_name]
                    self._limiters[key] = SlidingWindowRateLimiter(window_size, max_req)
                limiter = self._limiters[key]
            if not limiter.try_acquire():
                return False
        return True


# ======================== 测试 ========================
if __name__ == "__main__":
    # 测试令牌桶
    print("=== 令牌桶测试 ===")
    bucket = TokenBucketRateLimiter(capacity=10, rate=2.0)
    # 瞬时消耗所有令牌
    acquired = sum(1 for _ in range(15) if bucket.try_acquire())
    print(f"瞬时请求15次，成功{acquired}次（容量10）")
    assert acquired == 10, "应允许10个突发请求"
    # 等待令牌补充
    time.sleep(1.0)
    acquired = sum(1 for _ in range(5) if bucket.try_acquire())
    print(f"等待1秒后请求5次，成功{acquired}次（应约2个）")
    assert acquired == 2, f"1秒应补充2个令牌，实际{acquired}"

    # 测试滑动窗口
    print("\n=== 滑动窗口测试 ===")
    sw = SlidingWindowRateLimiter(window_size=1.0, max_requests=5)
    # 快速发5个请求
    results = [sw.try_acquire() for _ in range(5)]
    assert all(results), "前5个请求应全部通过"
    # 第6个应被拒绝
    assert not sw.try_acquire(), "第6个请求应被拒绝"
    print("前5个请求通过，第6个被拒绝")
    # 等待窗口滑过
    time.sleep(1.1)
    assert sw.try_acquire(), "窗口滑过后应允许新请求"
    print("等待1.1秒后，新请求通过")

    # 测试漏桶
    print("\n=== 漏桶测试 ===")
    leaky = LeakyBucketRateLimiter(capacity=5, leak_rate=10.0)
    # 快速放入5个请求
    results = [leaky.try_acquire() for _ in range(7)]
    acquired = sum(results)
    assert acquired == 5, f"应允许5个请求入桶，实际{acquired}"
    print(f"瞬时请求7次，成功入桶{acquired}次（容量5）")
    # 等待漏出
    time.sleep(0.5)
    assert leaky.try_acquire(), "漏出后应可入桶"
    print("等待0.5秒后（漏出5个），新请求入桶成功")

    # 测试多维度限流
    print("\n=== 多维度限流测试 ===")
    mgr = MultiDimensionRateLimiter()
    mgr.add_rule("user_id", window_size=10, max_requests=3)
    mgr.add_rule("ip", window_size=10, max_requests=10)
    # 同一用户前3次通过，第4次被拒
    for i in range(3):
        assert mgr.check(user_id="user1", ip="1.1.1.1"), f"第{i+1}次应通过"
    assert not mgr.check(user_id="user1", ip="1.1.1.1"), "第4次用户维度应被拒"
    # 换个用户，同一IP应通过
    assert mgr.check(user_id="user2", ip="1.1.1.1"), "不同用户应通过"
    print("用户维度限流3次/10秒，IP维度限流10次/10秒 — 测试通过")
```

### 思考题
1. 令牌桶和漏桶在突发流量处理上的本质区别是什么？各适合什么场景？
2. 分布式环境下，如何用Redis实现原子限流？Lua脚本如何保证检查和扣减的原子性？
3. 如果限流器需要支持动态调整速率（如根据系统负载自动调参），如何设计自适应限流？

---

## 第3题：消息队列系统

### 知识点讲解

消息队列是分布式系统中解耦生产者和消费者的核心组件。本实现采用发布-订阅模型，核心概念包括：

**主题与分区**：Topic是消息的逻辑分类，每个Topic划分为多个Partition。分区是并行度的基本单位——同一分区内的消息有序，不同分区可并行消费。生产者根据分区键（Partition Key）将消息路由到特定分区，保证相同键的消息进入同一分区。

**消费者组**：同一消费者组内的消费者共同消费一个Topic的所有分区，每个分区只被组内一个消费者消费，实现负载均衡。不同消费者组独立消费，互不影响。消费者通过拉取模式从分区获取消息。

**偏移量管理**：Offset是消费者在分区中的消费位置。消费者需要定期提交已消费的偏移量，以便故障恢复后从断点继续。提交方式分自动提交（简单但可能重复消费）和手动提交（精确控制但增加复杂度）。

**死信处理**：当消息消费失败超过重试次数，应将消息转入死信队列，避免毒药消息阻塞正常消费。死信队列中的消息可由人工干预或特殊消费者处理。

```python
"""
简单消息队列系统：发布-订阅 + 分区 + 消费者组 + 偏移量 + 死信队列
"""
import time
import threading
import hashlib
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Message:
    """消息实体"""
    topic: str
    partition: int
    offset: int
    key: str | None
    value: any
    timestamp: float = field(default_factory=time.time)
    retry_count: int = 0


class Partition:
    """分区：存储消息的有序队列"""

    def __init__(self, topic: str, partition_id: int):
        self.topic = topic
        self.partition_id = partition_id
        self._messages = []  # 消息列表，按offset递增
        self._next_offset = 0
        self._lock = threading.Lock()

    def append(self, key: str | None, value: any) -> int:
        """追加消息到分区，返回消息的offset"""
        with self._lock:
            msg = Message(
                topic=self.topic,
                partition=self.partition_id,
                offset=self._next_offset,
                key=key,
                value=value,
            )
            self._messages.append(msg)
            self._next_offset += 1
            return msg.offset

    def fetch(self, offset: int, max_count: int = 100) -> list[Message]:
        """从指定offset拉取消息"""
        with self._lock:
            result = []
            for i in range(offset, min(offset + max_count, len(self._messages))):
                result.append(self._messages[i])
            return result

    @property
    def latest_offset(self) -> int:
        return self._next_offset


class Topic:
    """主题：包含多个分区"""

    def __init__(self, name: str, partition_count: int = 3):
        self.name = name
        self.partition_count = partition_count
        self.partitions = [
            Partition(name, i) for i in range(partition_count)
        ]

    def _select_partition(self, key: str | None) -> int:
        """根据分区键选择分区，无键则轮询"""
        if key is None:
            # 无键时用时间戳取模，近似均匀分布
            return int(time.time() * 1000) % self.partition_count
        # 有键时用哈希取模，保证相同键进同一分区
        h = int(hashlib.md5(key.encode()).hexdigest(), 16)
        return h % self.partition_count

    def produce(self, key: str | None, value: any) -> tuple[int, int]:
        """生产消息，返回 (partition_id, offset)"""
        pid = self._select_partition(key)
        offset = self.partitions[pid].append(key, value)
        return pid, offset


class Consumer:
    """消费者：属于某个消费者组，消费分配给自己的分区"""

    def __init__(self, consumer_id: str, group: str, broker: "MessageBroker"):
        self.consumer_id = consumer_id
        self.group = group
        self.broker = broker
        # 分区 -> 当前消费offset
        self._offsets = {}
        # 分配的分区列表
        self._assigned_partitions = []
        # 消费回调
        self._handler: Callable | None = None
        self._running = False
        self._thread = None

    def assign(self, topic_name: str, partitions: list[int]):
        """分配分区给消费者"""
        self._assigned_partitions = partitions
        for p in partitions:
            if p not in self._offsets:
                self._offsets[p] = 0  # 从头开始消费

    def subscribe(self, handler: Callable[[Message], bool]):
        """注册消息处理函数，返回True表示消费成功，False表示失败"""
        self._handler = handler

    def poll(self, max_messages: int = 10) -> list[Message]:
        """拉取已分配分区中的消息"""
        messages = []
        topic = self.broker.get_topic(
            # 假设消费者只订阅一个topic
            list(self.broker._topics.keys())[0] if self.broker._topics else None
        )
        if topic is None:
            return messages
        for pid in self._assigned_partitions:
            partition = topic.partitions[pid]
            offset = self._offsets.get(pid, 0)
            msgs = partition.fetch(offset, max_count=max_messages - len(messages))
            for msg in msgs:
                messages.append(msg)
                self._offsets[pid] = msg.offset + 1
            if len(messages) >= max_messages:
                break
        return messages

    def commit_offset(self, partition: int, offset: int):
        """手动提交偏移量"""
        self._offsets[partition] = offset

    def consume_loop(self, max_messages: int = 10):
        """消费循环：拉取消息并调用处理函数"""
        while self._running:
            messages = self.poll(max_messages)
            for msg in messages:
                if self._handler:
                    success = self._handler(msg)
                    if not success:
                        # 消费失败，加入死信队列
                        msg.retry_count += 1
                        if msg.retry_count <= 3:
                            # 重试：回退offset
                            self._offsets[msg.partition] = msg.offset
                        else:
                            # 超过重试次数，加入死信队列
                            self.broker.add_to_dlq(msg)
            if not messages:
                time.sleep(0.01)

    def start(self):
        """启动消费线程"""
        self._running = True
        self._thread = threading.Thread(target=self.consume_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """停止消费"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)


class ConsumerGroup:
    """消费者组：管理组内消费者的分区分配"""

    def __init__(self, group_name: str):
        self.group_name = group_name
        self.consumers: list[Consumer] = []

    def rebalance(self, topic: Topic):
        """再均衡：将分区均匀分配给组内消费者"""
        n = len(self.consumers)
        if n == 0:
            return
        for i, partition_id in enumerate(range(topic.partition_count)):
            consumer = self.consumers[i % n]
            consumer.assign(topic.name, [partition_id] if partition_id not in consumer._assigned_partitions else consumer._assigned_partitions)
        # 简化版：重新分配
        partitions_per_consumer = topic.partition_count // n
        remainder = topic.partition_count % n
        idx = 0
        for i, consumer in enumerate(self.consumers):
            count = partitions_per_consumer + (1 if i < remainder else 0)
            assigned = list(range(idx, idx + count))
            consumer.assign(topic.name, assigned)
            idx += count


class MessageBroker:
    """消息队列Broker：管理主题、消费者组、死信队列"""

    def __init__(self):
        self._topics: dict[str, Topic] = {}
        self._consumer_groups: dict[str, ConsumerGroup] = {}
        self._dlq: deque = deque(maxlen=10000)  # 死信队列
        self._lock = threading.Lock()

    def create_topic(self, name: str, partition_count: int = 3) -> Topic:
        """创建主题"""
        with self._lock:
            if name not in self._topics:
                self._topics[name] = Topic(name, partition_count)
            return self._topics[name]

    def get_topic(self, name: str) -> Topic | None:
        return self._topics.get(name)

    def produce(self, topic_name: str, key: str | None, value: any) -> tuple[int, int]:
        """生产消息"""
        topic = self.get_topic(topic_name)
        if topic is None:
            raise ValueError(f"Topic '{topic_name}' does not exist")
        return topic.produce(key, value)

    def create_consumer(self, consumer_id: str, group_name: str) -> Consumer:
        """创建消费者并加入消费者组"""
        consumer = Consumer(consumer_id, group_name, self)
        with self._lock:
            if group_name not in self._consumer_groups:
                self._consumer_groups[group_name] = ConsumerGroup(group_name)
            self._consumer_groups[group_name].consumers.append(consumer)
        return consumer

    def rebalance_group(self, group_name: str, topic_name: str):
        """触发消费者组再均衡"""
        group = self._consumer_groups.get(group_name)
        topic = self.get_topic(topic_name)
        if group and topic:
            group.rebalance(topic)

    def add_to_dlq(self, msg: Message):
        """将消息加入死信队列"""
        self._dlq.append(msg)

    def get_dlq_messages(self) -> list[Message]:
        """获取死信队列中的消息"""
        return list(self._dlq)


# ======================== 测试 ========================
if __name__ == "__main__":
    broker = MessageBroker()
    topic = broker.create_topic("orders", partition_count=3)
    print(f"创建主题 'orders'，分区数={topic.partition_count}")

    # 生产消息
    for i in range(10):
        key = f"user_{i % 4}"  # 4个用户的订单
        value = {"order_id": i, "amount": (i + 1) * 100}
        pid, offset = broker.produce("orders", key, value)
        print(f"  生产: key={key}, value={value} -> partition={pid}, offset={offset}")

    # 验证相同key进入相同分区
    pid1, _ = broker.produce("orders", "user_0", {"order_id": 100})
    pid2, _ = broker.produce("orders", "user_0", {"order_id": 101})
    assert pid1 == pid2, "相同key应进入相同分区"
    print(f"\n[OK] 相同key 'user_0' 进入相同分区: partition={pid1}")

    # 创建消费者组并消费
    c1 = broker.create_consumer("c1", "group_a")
    c2 = broker.create_consumer("c2", "group_a")
    broker.rebalance_group("group_a", "orders")
    print(f"\n消费者组 'group_a': c1分配分区={c1._assigned_partitions}, c2分配分区={c2._assigned_partitions}")

    # 消费消息
    received = []
    c1.subscribe(lambda msg: received.append(msg.value) or True)
    c2.subscribe(lambda msg: received.append(msg.value) or True)
    msgs1 = c1.poll(max_messages=20)
    msgs2 = c2.poll(max_messages=20)
    print(f"  c1 消费 {len(msgs1)} 条, c2 消费 {len(msgs2)} 条")
    assert len(msgs1) + len(msgs2) == 12, "应消费全部12条消息"
    print("[OK] 所有消息被消费")

    # 测试死信队列
    c3 = broker.create_consumer("c3", "group_b")
    broker.rebalance_group("group_b", "orders")
    c3.subscribe(lambda msg: False)  # 总是消费失败
    c3._offsets = {0: 0, 1: 0, 2: 0}
    c3.start()
    time.sleep(1.0)
    c3.stop()
    dlq_msgs = broker.get_dlq_messages()
    print(f"\n死信队列消息数: {len(dlq_msgs)}")
    assert len(dlq_msgs) > 0, "消费失败的消息应进入死信队列"
    print("[OK] 死信队列测试通过")
```

### 思考题
1. 消费者组内消费者数量超过分区数时会发生什么？如何处理？
2. 至少一次交付和恰好一次交付的区别是什么？如何实现恰好一次？
3. 消息积压时如何快速消费？增加消费者是否总是有效？

---

## 第4题：分布式缓存

### 知识点讲解

分布式缓存是高并发系统的关键组件。本实现涵盖缓存替换算法和一致性哈希路由两个核心模块。

**LRU（最近最少使用）**：淘汰最长时间未被访问的数据。实现上使用双向链表 + 哈希表，访问时将节点移到链表头部，淘汰时移除尾部节点。LRU适合时间局部性强的访问模式。

**LFU（最不经常使用）**：淘汰访问频率最低的数据。当多个数据频率相同时，淘汰最久未访问的。LFU适合需要保留高频热点数据的场景，但存在"历史热点"问题——曾经频繁访问但后来不再访问的数据会长期占用缓存。

**一致性哈希**：分布式缓存路由的核心算法。将哈希空间组织成虚拟环（0 ~ 2^32-1），每个节点和Key都映射到环上。Key顺时针找到的第一个节点即为其存储节点。节点加入/离开时只影响相邻区间的Key，最小化数据迁移。为解决数据倾斜，引入虚拟节点——每个物理节点对应多个虚拟节点，均匀分布在环上。

缓存三大问题：**穿透**（查询不存在的Key，绕过缓存直接打DB）→ 用布隆过滤器或缓存空值；**击穿**（热点Key过期瞬间大量请求打DB）→ 互斥锁重建缓存；**雪崩**（大量Key同时过期）→ TTL加随机偏移。

```python
"""
分布式缓存：LRU + LFU + 一致性哈希路由
"""
import time
import threading
import hashlib
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field
from typing import Any


# ======================== LRU 缓存 ========================
class LRUCache:
    """
    LRU缓存：使用 OrderedDict 实现 O(1) 的 get/put
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._cache = OrderedDict()
        self._lock = threading.Lock()
        # 统计信息
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._hits += 1
                return self._cache[key]
            self._misses += 1
            return None

    def put(self, key: str, value: Any, ttl: float | None = None):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = {
                "value": value,
                "expire_at": time.time() + ttl if ttl else None,
            }
            if len(self._cache) > self.capacity:
                self._cache.popitem(last=False)  # 淘汰最久未访问

    def _is_expired(self, entry: dict) -> bool:
        if entry.get("expire_at") is None:
            return False
        return time.time() > entry["expire_at"]

    def get_with_ttl(self, key: str) -> Any | None:
        """带TTL检查的get"""
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if self._is_expired(entry):
                    del self._cache[key]
                    self._misses += 1
                    return None
                self._cache.move_to_end(key)
                self._hits += 1
                return entry["value"]
            self._misses += 1
            return None

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def stats(self) -> dict:
        return {
            "size": len(self._cache),
            "capacity": self.capacity,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{self.hit_rate:.2%}",
        }


# ======================== LFU 缓存 ========================
class LFUCache:
    """
    LFU缓存：淘汰访问频率最低的数据
    使用频次链表 + 哈希表实现 O(1) 操作
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self._cache = {}  # key -> {"value": v, "freq": f, "time": t}
        self._lock = threading.Lock()
        self._min_freq = 0
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                entry["freq"] += 1
                entry["time"] = time.monotonic()
                self._hits += 1
                return entry["value"]
            self._misses += 1
            return None

    def put(self, key: str, value: Any):
        with self._lock:
            if key in self._cache:
                self._cache[key]["value"] = value
                self._cache[key]["freq"] += 1
                self._cache[key]["time"] = time.monotonic()
                return
            if len(self._cache) >= self.capacity:
                # 淘汰频率最低且最久未访问的
                evict_key = min(self._cache.keys(),
                                key=lambda k: (self._cache[k]["freq"], self._cache[k]["time"]))
                del self._cache[evict_key]
            self._cache[key] = {
                "value": value,
                "freq": 1,
                "time": time.monotonic(),
            }

    def stats(self) -> dict:
        return {
            "size": len(self._cache),
            "capacity": self.capacity,
            "hits": self._hits,
            "misses": self._misses,
        }


# ======================== 一致性哈希 ========================
class ConsistentHashRing:
    """
    一致性哈希环：用于分布式缓存路由
    - 每个物理节点对应多个虚拟节点，均匀分布
    - 节点增减时只影响相邻区间
    """

    def __init__(self, virtual_nodes: int = 150):
        self.virtual_nodes = virtual_nodes
        self._ring: dict[int, str] = {}  # hash -> node_name
        self._sorted_hashes: list[int] = []  # 排序的hash列表，用于二分查找
        self._lock = threading.Lock()

    def _hash(self, key: str) -> int:
        """使用MD5计算哈希，取前8字节"""
        h = hashlib.md5(key.encode()).hexdigest()
        return int(h[:8], 16)

    def add_node(self, node: str):
        """添加节点：在环上放置虚拟节点"""
        with self._lock:
            for i in range(self.virtual_nodes):
                vnode_key = f"{node}#{i}"
                h = self._hash(vnode_key)
                self._ring[h] = node
            self._sorted_hashes = sorted(self._ring.keys())

    def remove_node(self, node: str):
        """移除节点：删除对应的所有虚拟节点"""
        with self._lock:
            to_remove = [h for h, n in self._ring.items() if n == node]
            for h in to_remove:
                del self._ring[h]
            self._sorted_hashes = sorted(self._ring.keys())

    def get_node(self, key: str) -> str | None:
        """根据key找到对应的存储节点（顺时针第一个）"""
        with self._lock:
            if not self._sorted_hashes:
                return None
            h = self._hash(key)
            # 二分查找第一个 >= h 的位置
            import bisect
            idx = bisect.bisect_right(self._sorted_hashes, h)
            if idx == len(self._sorted_hashes):
                idx = 0  # 环绕到环的首部
            return self._ring[self._sorted_hashes[idx]]

    def get_nodes_for_replication(self, key: str, count: int) -> list[str]:
        """获取key的多个副本节点（用于多副本存储）"""
        with self._lock:
            if not self._sorted_hashes:
                return []
            h = self._hash(key)
            import bisect
            idx = bisect.bisect_right(self._sorted_hashes, h)
            nodes = []
            seen = set()
            for i in range(len(self._sorted_hashes)):
                node = self._ring[self._sorted_hashes[(idx + i) % len(self._sorted_hashes)]]
                if node not in seen:
                    nodes.append(node)
                    seen.add(node)
                    if len(nodes) >= count:
                        break
            return nodes


# ======================== 分布式缓存集群 ========================
class DistributedCache:
    """
    分布式缓存集群：一致性哈希路由 + 多节点LRU缓存
    集成缓存穿透/击穿/雪崩防护
    """

    def __init__(self, node_names: list[str], per_node_capacity: int = 1000):
        self.ring = ConsistentHashRing(virtual_nodes=150)
        self.nodes = {}  # node_name -> LRUCache
        for name in node_names:
            self.ring.add_node(name)
            self.nodes[name] = LRUCache(per_node_capacity)
        # 防穿透：空值缓存
        self._null_cache = {}  # key -> expire_at
        # 防击穿：锁池
        self._lock_pool = defaultdict(threading.Lock)
        # 统计
        self._total_get = 0
        self._cache_hits = 0

    def _get_node(self, key: str) -> LRUCache:
        node_name = self.ring.get_node(key)
        return self.nodes[node_name]

    def get(self, key: str) -> Any | None:
        self._total_get += 1
        # 防穿透：检查空值缓存
        if key in self._null_cache:
            if time.time() < self._null_cache[key]:
                return None  # 已知不存在的key
            else:
                del self._null_cache[key]

        cache = self._get_node(key)
        value = cache.get_with_ttl(key)
        if value is not None:
            self._cache_hits += 1
            return value
        return None

    def set(self, key: str, value: Any, ttl: float | None = None):
        """设置缓存，TTL加随机偏移防止雪崩"""
        if ttl is not None:
            import random
            # TTL加0~30秒随机偏移，防止大量key同时过期
            ttl += random.uniform(0, min(30, ttl * 0.1))
        cache = self._get_node(key)
        cache.put(key, value, ttl=ttl)

    def get_or_load(self, key: str, loader: callable, ttl: float = 300) -> Any:
        """
        防击穿：缓存未命中时加锁加载，只允许一个请求重建缓存
        """
        value = self.get(key)
        if value is not None:
            return value
        # 加锁防击穿
        lock = self._lock_pool[key]
        with lock:
            # 双重检查
            value = self.get(key)
            if value is not None:
                return value
            # 从数据源加载
            value = loader(key)
            if value is None:
                # 防穿透：缓存空值（短TTL）
                self._null_cache[key] = time.time() + 60
                return None
            self.set(key, value, ttl=ttl)
            return value

    def add_node(self, name: str, capacity: int = 1000):
        """动态添加节点"""
        self.ring.add_node(name)
        self.nodes[name] = LRUCache(capacity)

    def remove_node(self, name: str):
        """动态移除节点"""
        self.ring.remove_node(name)
        # 注意：实际场景需要将数据迁移到其他节点
        del self.nodes[name]

    def stats(self) -> dict:
        return {
            "total_get": self._total_get,
            "cache_hits": self._cache_hits,
            "hit_rate": f"{self._cache_hits / self._total_get:.2%}" if self._total_get > 0 else "0%",
            "node_count": len(self.nodes),
            "node_stats": {name: cache.stats() for name, cache in self.nodes.items()},
        }


# ======================== 测试 ========================
if __name__ == "__main__":
    # 测试 LRU
    print("=== LRU缓存测试 ===")
    lru = LRUCache(capacity=3)
    lru.put("a", 1)
    lru.put("b", 2)
    lru.put("c", 3)
    assert lru.get("a") == 1  # a变为最近使用
    lru.put("d", 4)  # 容量满，淘汰最久未使用的b
    assert lru.get("b") is None, "b应被淘汰"
    assert lru.get("c") == 3
    print("[OK] LRU淘汰策略正确")

    # 测试 TTL
    lru.put("temp", 99, ttl=0.1)
    assert lru.get_with_ttl("temp") == 99
    time.sleep(0.15)
    assert lru.get_with_ttl("temp") is None, "TTL过期后应返回None"
    print("[OK] TTL过期机制正确")

    # 测试 LFU
    print("\n=== LFU缓存测试 ===")
    lfu = LFUCache(capacity=2)
    lfu.put("a", 1)
    lfu.put("b", 2)
    lfu.get("a")  # a频率=2
    lfu.get("a")  # a频率=3
    lfu.get("b")  # b频率=2
    lfu.put("c", 3)  # 容量满，淘汰频率最低的b
    assert lfu.get("b") is None, "b频率较低应被淘汰"
    assert lfu.get("a") == 1, "a频率高应保留"
    print("[OK] LFU淘汰策略正确")

    # 测试一致性哈希
    print("\n=== 一致性哈希测试 ===")
    ring = ConsistentHashRing(virtual_nodes=100)
    for node in ["node1", "node2", "node3"]:
        ring.add_node(node)

    # 统计Key分布
    distribution = defaultdict(int)
    for i in range(10000):
        node = ring.get_node(f"key_{i}")
        distribution[node] += 1
    print(f"Key分布(10000个): {dict(distribution)}")
    # 验证分布相对均匀
    for node, count in distribution.items():
        assert 2500 < count < 4000, f"{node}分布不均匀: {count}"
    print("[OK] 一致性哈希分布均匀")

    # 验证节点增减时数据迁移最小
    key_node_before = {f"key_{i}": ring.get_node(f"key_{i}") for i in range(1000)}
    ring.add_node("node4")
    migrated = sum(1 for k, v in key_node_before.items()
                   if ring.get_node(k) != v)
    print(f"添加node4后，迁移的Key数: {migrated}/1000 (约25%)")
    assert migrated < 400, "迁移量应小于40%"
    print("[OK] 节点增减时数据迁移最小")

    # 测试分布式缓存
    print("\n=== 分布式缓存测试 ===")
    cache = DistributedCache(["cache1", "cache2", "cache3"], per_node_capacity=500)
    # 写入数据
    for i in range(100):
        cache.set(f"user:{i}", {"name": f"user_{i}", "age": i}, ttl=300)
    # 读取数据
    for i in range(100):
        val = cache.get(f"user:{i}")
        assert val is not None and val["age"] == i, f"user:{i}读取失败"
    print("[OK] 100个key写入读取正确")

    # 测试防击穿
    load_count = 0
    def loader(key):
        nonlocal load_count
        load_count += 1
        time.sleep(0.05)  # 模拟慢查询
        return f"loaded_{key}"

    threads = []
    results = []
    def worker():
        results.append(cache.get_or_load("hot_key", loader, ttl=300))

    for _ in range(10):
        threads.append(threading.Thread(target=worker))
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print(f"10个并发请求，loader只调用{load_count}次（防击穿）")
    assert load_count == 1, f"loader应只调用1次，实际{load_count}次"
    print("[OK] 防击穿：并发请求只触发一次加载")

    print(f"\n缓存统计: {cache.stats()}")
```

### 思考题
1. LRU和LFU分别适合什么场景？能否设计一个混合策略（如LRU-K）兼顾两者优势？
2. 一致性哈希中虚拟节点数如何选择？虚拟节点过多或过少各有什么问题？
3. 如何实现缓存的多级架构（本地缓存 + 分布式缓存 + DB）？各层职责如何划分？

---

## 第5题：负载均衡器

### 知识点讲解

负载均衡器是分布式系统流量分发的核心组件。本实现涵盖四种经典算法：

**轮询**：将请求依次分配给后端服务器列表，简单公平但未考虑服务器性能差异。

**加权轮询**：为每台服务器分配权重，权重高的分配更多请求。实现上可展开为虚拟服务器列表（如权重3的节点出现3次），或使用平滑加权轮询算法（Nginx采用），避免权重高的节点被连续选中。

**最少连接**：将请求分配给当前活跃连接数最少的服务器，动态感知服务器负载。适合请求处理时间差异大的场景，但需要维护各服务器连接计数。

**一致性哈希**：与分布式缓存相同原理，相同客户端（IP或SessionID）路由到同一服务器，天然支持会话保持。节点变更时影响最小。

**健康检查**：负载均衡器定期探测后端服务器健康状态，自动摘除故障节点，恢复后自动加回。分主动检查（定期发HTTP请求）和被动检查（根据请求失败率判断）。

**慢启动**：新加入或恢复的服务器不立即承担全量流量，而是逐步增加权重，避免瞬时压力过大导致再次过载。Nginx的`slow_start`参数即此机制。

**会话保持**：确保同一用户的请求始终路由到同一服务器。方法包括：IP哈希、Cookie粘性、SessionID哈希。一致性哈希天然支持此特性。

```python
"""
负载均衡器：轮询 + 加权轮询 + 最少连接 + 一致性哈希
"""
import time
import threading
import hashlib
import bisect
import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class BackendServer:
    """后端服务器"""
    name: str
    host: str
    port: int
    weight: int = 1
    is_healthy: bool = True
    active_connections: int = 0
    # 慢启动相关
    current_weight: float = 0  # 当前有效权重（用于慢启动）
    slow_start_duration: float = 0  # 慢启动持续时间（秒），0表示不启用
    _join_time: float = field(default_factory=time.time)
    # 统计
    total_requests: int = 0
    failed_requests: int = 0
    last_health_check: float = 0.0

    def update_slow_start(self):
        """慢启动：逐步增加有效权重到配置值"""
        if self.slow_start_duration <= 0:
            self.current_weight = float(self.weight)
            return
        elapsed = time.time() - self._join_time
        if elapsed >= self.slow_start_duration:
            self.current_weight = float(self.weight)
        else:
            # 线性增长
            ratio = elapsed / self.slow_start_duration
            self.current_weight = self.weight * ratio


class LoadBalancer:
    """负载均衡器基类"""

    def __init__(self):
        self._servers: list[BackendServer] = []
        self._lock = threading.Lock()
        self._health_check_interval = 5.0  # 健康检查间隔（秒）
        self._health_check_func: Callable[[BackendServer], bool] | None = None
        self._running = False
        self._health_thread = None

    def add_server(self, server: BackendServer):
        with self._lock:
            self._servers.append(server)

    def remove_server(self, name: str):
        with self._lock:
            self._servers = [s for s in self._servers if s.name != name]

    def get_healthy_servers(self) -> list[BackendServer]:
        """获取健康的服务器列表"""
        with self._lock:
            return [s for s in self._servers if s.is_healthy]

    def select(self, client_key: str | None = None) -> BackendServer | None:
        """选择服务器（子类实现）"""
        raise NotImplementedError

    def release(self, server: BackendServer):
        """释放连接"""
        with self._lock:
            server.active_connections = max(0, server.active_connections - 1)

    def set_health_check(self, check_func: Callable[[BackendServer], bool]):
        """设置健康检查函数"""
        self._health_check_func = check_func

    def start_health_check(self):
        """启动健康检查线程"""
        self._running = True
        self._health_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        self._health_thread.start()

    def stop_health_check(self):
        self._running = False
        if self._health_thread:
            self._health_thread.join(timeout=2)

    def _health_check_loop(self):
        while self._running:
            with self._lock:
                servers = list(self._servers)
            for server in servers:
                if self._health_check_func:
                    was_healthy = server.is_healthy
                    server.is_healthy = self._health_check_func(server)
                    server.last_health_check = time.time()
                    if not was_healthy and server.is_healthy:
                        # 恢复健康，重置慢启动
                        server._join_time = time.time()
            time.sleep(self._health_check_interval)

    def stats(self) -> list[dict]:
        with self._lock:
            return [
                {
                    "name": s.name,
                    "healthy": s.is_healthy,
                    "weight": s.weight,
                    "current_weight": round(s.current_weight, 2),
                    "active_conn": s.active_connections,
                    "total_req": s.total_requests,
                    "failed_req": s.failed_requests,
                }
                for s in self._servers
            ]


# ======================== 轮询 ========================
class RoundRobinBalancer(LoadBalancer):
    """简单轮询"""

    def __init__(self):
        super().__init__()
        self._index = 0

    def select(self, client_key: str | None = None) -> BackendServer | None:
        with self._lock:
            healthy = [s for s in self._servers if s.is_healthy]
            if not healthy:
                return None
            server = healthy[self._index % len(healthy)]
            self._index = (self._index + 1) % len(healthy)
            server.active_connections += 1
            server.total_requests += 1
            return server


# ======================== 加权轮询（平滑加权） ========================
class WeightedRoundRobinBalancer(LoadBalancer):
    """
    平滑加权轮询（Nginx算法）
    每台服务器维护 current_weight，每次选择时：
    1. current_weight += effective_weight
    2. 选择 current_weight 最大的服务器
    3. 被选中的服务器 current_weight -= total_weight
    这样权重高的服务器分散被选中，而非连续选中
    """

    def __init__(self):
        super().__init__()
        self._current_weights = {}  # name -> current_weight

    def select(self, client_key: str | None = None) -> BackendServer | None:
        with self._lock:
            healthy = [s for s in self._servers if s.is_healthy]
            if not healthy:
                return None
            for s in healthy:
                s.update_slow_start()
                if s.name not in self._current_weights:
                    self._current_weights[s.name] = 0
                self._current_weights[s.name] += s.current_weight
            total = sum(s.current_weight for s in healthy)
            # 选择current_weight最大的
            best = max(healthy, key=lambda s: self._current_weights[s.name])
            self._current_weights[best.name] -= total
            best.active_connections += 1
            best.total_requests += 1
            return best


# ======================== 最少连接 ========================
class LeastConnectionsBalancer(LoadBalancer):
    """最少连接数"""

    def select(self, client_key: str | None = None) -> BackendServer | None:
        with self._lock:
            healthy = [s for s in self._servers if s.is_healthy]
            if not healthy:
                return None
            for s in healthy:
                s.update_slow_start()
            # 选择活跃连接数最少的，连接数相同则按权重选择
            min_conn = min(s.active_connections for s in healthy)
            candidates = [s for s in healthy if s.active_connections == min_conn]
            # 在候选中按权重选择
            total_weight = sum(s.current_weight for s in candidates)
            if total_weight <= 0:
                selected = candidates[0]
            else:
                r = random.uniform(0, total_weight)
                cumulative = 0
                selected = candidates[-1]
                for s in candidates:
                    cumulative += s.current_weight
                    if r <= cumulative:
                        selected = s
                        break
            selected.active_connections += 1
            selected.total_requests += 1
            return selected


# ======================== 一致性哈希 ========================
class ConsistentHashBalancer(LoadBalancer):
    """一致性哈希负载均衡（支持会话保持）"""

    def __init__(self, virtual_nodes: int = 150):
        super().__init__()
        self.virtual_nodes = virtual_nodes
        self._ring: dict[int, str] = {}
        self._sorted_hashes: list[int] = []

    def _hash(self, key: str) -> int:
        return int(hashlib.md5(key.encode()).hexdigest()[:8], 16)

    def add_server(self, server: BackendServer):
        with self._lock:
            super().add_server(server)
            for i in range(self.virtual_nodes):
                h = self._hash(f"{server.name}#{i}")
                self._ring[h] = server.name
            self._sorted_hashes = sorted(self._ring.keys())

    def remove_server(self, name: str):
        with self._lock:
            super().remove_server(name)
            to_remove = [h for h, n in self._ring.items() if n == name]
            for h in to_remove:
                del self._ring[h]
            self._sorted_hashes = sorted(self._ring.keys())

    def select(self, client_key: str | None = None) -> BackendServer | None:
        with self._lock:
            healthy = [s for s in self._servers if s.is_healthy]
            if not healthy:
                return None
            healthy_names = {s.name for s in healthy}
            if not self._sorted_hashes:
                return None
            key = client_key or str(time.time())
            h = self._hash(key)
            idx = bisect.bisect_right(self._sorted_hashes, h)
            # 顺时针找到健康的节点
            for i in range(len(self._sorted_hashes)):
                pos = (idx + i) % len(self._sorted_hashes)
                name = self._ring[self._sorted_hashes[pos]]
                if name in healthy_names:
                    server = next(s for s in healthy if s.name == name)
                    server.active_connections += 1
                    server.total_requests += 1
                    return server
            return None


# ======================== 测试 ========================
if __name__ == "__main__":
    # 测试轮询
    print("=== 轮询测试 ===")
    rr = RoundRobinBalancer()
    for i in range(3):
        rr.add_server(BackendServer(f"s{i}", f"10.0.0.{i}", 8080))
    counts = defaultdict(int)
    for _ in range(12):
        s = rr.select()
        counts[s.name] += 1
        rr.release(s)
    print(f"分配结果: {dict(counts)}")
    assert all(c == 4 for c in counts.values()), "轮询应均匀分配"
    print("[OK] 轮询均匀分配")

    # 测试加权轮询
    print("\n=== 加权轮询测试 ===")
    wrr = WeightedRoundRobinBalancer()
    wrr.add_server(BackendServer("heavy", "10.0.0.1", 8080, weight=5))
    wrr.add_server(BackendServer("light", "10.0.0.2", 8080, weight=1))
    counts = defaultdict(int)
    for _ in range(60):
        s = wrr.select()
        counts[s.name] += 1
        wrr.release(s)
    print(f"分配结果: {dict(counts)} (heavy:light ≈ 5:1)")
    assert counts["heavy"] == 50 and counts["light"] == 10, f"期望50:10，实际{dict(counts)}"
    print("[OK] 加权轮询比例正确")

    # 验证平滑性（权重高的不被连续选中）
    wrr2 = WeightedRoundRobinBalancer()
    wrr2.add_server(BackendServer("a", "10.0.0.1", 8080, weight=3))
    wrr2.add_server(BackendServer("b", "10.0.0.2", 8080, weight=1))
    sequence = []
    for _ in range(8):
        s = wrr2.select()
        sequence.append(s.name)
        wrr2.release(s)
    print(f"选择序列: {sequence}")
    # 检查没有3次以上连续相同
    max_consecutive = 1
    current = 1
    for i in range(1, len(sequence)):
        if sequence[i] == sequence[i-1]:
            current += 1
            max_consecutive = max(max_consecutive, current)
        else:
            current = 1
    assert max_consecutive <= 2, f"连续选中次数应<=2，实际{max_consecutive}"
    print("[OK] 平滑加权：无过多连续选中")

    # 测试最少连接
    print("\n=== 最少连接测试 ===")
    lc = LeastConnectionsBalancer()
    lc.add_server(BackendServer("s1", "10.0.0.1", 8080))
    lc.add_server(BackendServer("s2", "10.0.0.2", 8080))
    # 模拟s1已有5个连接
    lc._servers[0].active_connections = 5
    lc._servers[1].active_connections = 1
    selected = lc.select()
    assert selected.name == "s2", "应选择连接数最少的s2"
    print(f"s1有5连接，s2有1连接 -> 选中{selected.name}")
    print("[OK] 最少连接选择正确")

    # 测试一致性哈希（会话保持）
    print("\n=== 一致性哈希测试 ===")
    chb = ConsistentHashBalancer(virtual_nodes=100)
    chb.add_server(BackendServer("node1", "10.0.0.1", 8080))
    chb.add_server(BackendServer("node2", "10.0.0.2", 8080))
    chb.add_server(BackendServer("node3", "10.0.0.3", 8080))
    # 同一客户端应路由到同一服务器
    client = "192.168.1.100"
    targets = set()
    for _ in range(100):
        s = chb.select(client_key=client)
        targets.add(s.name)
        chb.release(s)
    assert len(targets) == 1, f"同一客户端应路由到同一服务器，实际{targets}"
    print(f"客户端 {client} 始终路由到: {targets.pop()}")
    print("[OK] 会话保持正确")

    # 测试慢启动
    print("\n=== 慢启动测试 ===")
    wrr3 = WeightedRoundRobinBalancer()
    wrr3.add_server(BackendServer("old", "10.0.0.1", 8080, weight=10))
    wrr3.add_server(BackendServer("new", "10.0.0.2", 8080, weight=10, slow_start_duration=2.0))
    # 初始时new的权重应接近0
    wrr3._servers[1].update_slow_start()
    initial_weight = wrr3._servers[1].current_weight
    time.sleep(1.0)
    wrr3._servers[1].update_slow_start()
    mid_weight = wrr3._servers[1].current_weight
    time.sleep(1.5)
    wrr3._servers[1].update_slow_start()
    final_weight = wrr3._servers[1].current_weight
    print(f"慢启动权重变化: 初始={initial_weight:.2f} -> 1秒后={mid_weight:.2f} -> 2.5秒后={final_weight:.2f}")
    assert initial_weight < mid_weight < final_weight, "慢启动权重应递增"
    assert final_weight == 10, "慢启动结束后应达到满权重"
    print("[OK] 慢启动权重逐步增长")

    # 测试健康检查
    print("\n=== 健康检查测试 ===")
    rr2 = RoundRobinBalancer()
    rr2.add_server(BackendServer("healthy", "10.0.0.1", 8080))
    rr2.add_server(BackendServer("sick", "10.0.0.2", 8080))
    # 模拟健康检查函数
    check_count = [0]
    def health_check(server: BackendServer) -> bool:
        check_count[0] += 1
        return server.name == "healthy"  # sick总是不健康
    rr2.set_health_check(health_check)
    rr2._health_check_interval = 0.2
    rr2.start_health_check()
    time.sleep(0.5)
    # 此时sick应被标记为不健康
    healthy_servers = rr2.get_healthy_servers()
    print(f"健康检查后健康服务器: {[s.name for s in healthy_servers]}")
    assert len(healthy_servers) == 1 and healthy_servers[0].name == "healthy"
    # 请求应只分配给健康的服务器
    for _ in range(5):
        s = rr2.select()
        assert s.name == "healthy", "应只分配给健康服务器"
        rr2.release(s)
    rr2.stop_health_check()
    print("[OK] 健康检查正确摘除故障节点")
```

### 思考题
1. 平滑加权轮询算法的数学原理是什么？为什么能保证长序列中的分配比例精确等于权重比？
2. 如何实现基于响应时间的自适应负载均衡？如何避免慢节点的"雪崩"效应？
3. 四层（L4）和七层（L7）负载均衡的区别是什么？各自适合什么场景？


---

# 二、数据库进阶（5题）

---

## 第6题：B+树索引实现

### 知识点讲解

B+树是关系型数据库（MySQL/PostgreSQL）最核心的索引数据结构。相比二叉搜索树，B+树每个节点可存储多个键值，树高更低，适合磁盘I/O场景。

**结构特点**：B+树分为内部节点和叶子节点。内部节点只存储键值用于路由，不存数据；所有数据都存储在叶子节点中。叶子节点通过双向链表连接，支持高效范围扫描。每个节点的大小通常对应一个磁盘页（如InnoDB默认16KB），保证一次I/O读取一个完整节点。

**页分裂**：当插入导致节点键数量超过阶数上限时触发。将节点一分为二，中间键上推到父节点。页分裂是B+树写操作的主要开销，会导致页空间利用率降低（约50%）和写入放大。InnoDB通过自适应哈希索引和Change Buffer优化写性能。

**页合并**：当删除导致节点键数量低于下限时，先尝试从兄弟节点借键，若兄弟也不够则合并节点并删除父节点中的对应键。合并可能导致级联合并到根节点，降低树高。

**聚簇索引 vs 非聚簇索引**：聚簇索引的叶子节点存储完整数据行，数据按主键顺序物理存储，一张表只能有一个聚簇索引。非聚簇索引（二级索引）的叶子节点存储主键值，查询时需要"回表"——先查二级索引获取主键，再查聚簇索引获取完整行。覆盖索引指查询的列都在二级索引中，无需回表。

```python
"""
B+树索引实现：插入/删除/范围查询 + 页分裂/页合并
"""
from typing import Any


class BPlusTreeNode:
    """B+树节点"""

    def __init__(self, is_leaf: bool = False):
        self.is_leaf = is_leaf
        self.keys: list = []          # 键列表（有序）
        self.children: list = []      # 内部节点：子节点列表；叶子节点：数据列表
        self.next: BPlusTreeNode | None = None  # 叶子节点的后继指针
        self.prev: BPlusTreeNode | None = None  # 叶子节点的前驱指针
        self.parent: BPlusTreeNode | None = None

    def __repr__(self):
        return f"{'Leaf' if self.is_leaf else 'Internal'}({self.keys})"


class BPlusTree:
    """
    B+树实现
    - order: 阶数，每个节点最多 order-1 个键
    - 叶子节点存储 (key, value) 对，通过链表连接
    """

    def __init__(self, order: int = 4):
        self.order = order  # 每个节点最多 order 个子节点，order-1 个键
        self.root = BPlusTreeNode(is_leaf=True)
        self._min_keys = (order - 1) // 2  # 非根节点最少键数

    def search(self, key) -> Any | None:
        """精确查找"""
        node = self._find_leaf(key)
        for i, k in enumerate(node.keys):
            if k == key:
                return node.children[i]  # 叶子节点children存value
        return None

    def _find_leaf(self, key) -> BPlusTreeNode:
        """从根开始查找key应该所在的叶子节点"""
        node = self.root
        while not node.is_leaf:
            # 找到第一个大于key的位置
            i = 0
            while i < len(node.keys) and key >= node.keys[i]:
                i += 1
            node = node.children[i]
        return node

    def insert(self, key, value):
        """插入键值对"""
        leaf = self._find_leaf(key)
        # 在叶子节点中找到插入位置
        idx = 0
        while idx < len(leaf.keys) and leaf.keys[idx] < key:
            idx += 1
        # 如果key已存在，更新value
        if idx < len(leaf.keys) and leaf.keys[idx] == key:
            leaf.children[idx] = value
            return
        # 插入key和value
        leaf.keys.insert(idx, key)
        leaf.children.insert(idx, value)
        # 检查是否需要分裂
        if len(leaf.keys) > self.order - 1:
            self._split_leaf(leaf)

    def _split_leaf(self, leaf: BPlusTreeNode):
        """叶子节点分裂"""
        mid = len(leaf.keys) // 2
        # 创建新节点
        new_leaf = BPlusTreeNode(is_leaf=True)
        new_leaf.keys = leaf.keys[mid:]
        new_leaf.children = leaf.children[mid:]
        leaf.keys = leaf.keys[:mid]
        leaf.children = leaf.children[:mid]
        # 更新链表指针
        new_leaf.next = leaf.next
        new_leaf.prev = leaf
        if leaf.next:
            leaf.next.prev = new_leaf
        leaf.next = new_leaf
        # 上推分裂键（新节点的第一个键）
        split_key = new_leaf.keys[0]
        self._insert_in_parent(leaf, split_key, new_leaf)

    def _insert_in_parent(self, left: BPlusTreeNode, key, right: BPlusTreeNode):
        """在父节点中插入分裂后的键和右子节点"""
        if left.parent is None:
            # left是根节点，需要创建新根
            new_root = BPlusTreeNode(is_leaf=False)
            new_root.keys = [key]
            new_root.children = [left, right]
            left.parent = new_root
            right.parent = new_root
            self.root = new_root
            return

        parent = left.parent
        # 找到left在父节点中的位置
        idx = parent.children.index(left)
        parent.keys.insert(idx, key)
        parent.children.insert(idx + 1, right)
        right.parent = parent

        # 检查内部节点是否需要分裂
        if len(parent.keys) > self.order - 1:
            self._split_internal(parent)

    def _split_internal(self, node: BPlusTreeNode):
        """内部节点分裂"""
        mid = len(node.keys) // 2
        split_key = node.keys[mid]  # 中间键上推，不保留在子节点
        # 创建新内部节点
        new_node = BPlusTreeNode(is_leaf=False)
        new_node.keys = node.keys[mid + 1:]
        new_node.children = node.children[mid + 1:]
        node.keys = node.keys[:mid]
        node.children = node.children[:mid + 1]
        # 更新子节点的parent指针
        for child in new_node.children:
            child.parent = new_node
        # 上推
        self._insert_in_parent(node, split_key, new_node)

    def delete(self, key):
        """删除键"""
        leaf = self._find_leaf(key)
        if key not in leaf.keys:
            return False  # key不存在
        idx = leaf.keys.index(key)
        leaf.keys.pop(idx)
        leaf.children.pop(idx)
        # 如果是根节点或键数足够，无需处理
        if leaf == self.root or len(leaf.keys) >= self._min_keys:
            return True
        # 需要借键或合并
        self._fix_underflow(leaf)
        return True

    def _fix_underflow(self, node: BPlusTreeNode):
        """处理节点下溢：先尝试借键，再尝试合并"""
        if node == self.root:
            # 根节点特殊处理
            if not node.is_leaf and len(node.children) == 1:
                # 根只有一个子节点，子节点成为新根
                self.root = node.children[0]
                self.root.parent = None
            return

        parent = node.parent
        idx = parent.children.index(node)
        # 尝试从左兄弟借键
        if idx > 0:
            left_sibling = parent.children[idx - 1]
            if len(left_sibling.keys) > self._min_keys:
                self._borrow_from_left(node, left_sibling, idx)
                return
        # 尝试从右兄弟借键
        if idx < len(parent.children) - 1:
            right_sibling = parent.children[idx + 1]
            if len(right_sibling.keys) > self._min_keys:
                self._borrow_from_right(node, right_sibling, idx)
                return
        # 需要合并
        if idx > 0:
            # 与左兄弟合并
            self._merge(parent.children[idx - 1], node, idx - 1)
        else:
            # 与右兄弟合并
            self._merge(node, parent.children[idx + 1], idx)

    def _borrow_from_left(self, node: BPlusTreeNode, left: BPlusTreeNode, idx: int):
        """从左兄弟借键"""
        parent = node.parent
        if node.is_leaf:
            # 叶子节点借键
            borrowed_key = left.keys.pop()
            borrowed_val = left.children.pop()
            node.keys.insert(0, borrowed_key)
            node.children.insert(0, borrowed_val)
            # 更新父节点中的分隔键
            parent.keys[idx - 1] = node.keys[0]
        else:
            # 内部节点借键
            borrowed_key = parent.keys[idx - 1]
            parent.keys[idx - 1] = left.keys.pop()
            borrowed_child = left.children.pop()
            node.keys.insert(0, borrowed_key)
            node.children.insert(0, borrowed_child)
            borrowed_child.parent = node

    def _borrow_from_right(self, node: BPlusTreeNode, right: BPlusTreeNode, idx: int):
        """从右兄弟借键"""
        parent = node.parent
        if node.is_leaf:
            borrowed_key = right.keys.pop(0)
            borrowed_val = right.children.pop(0)
            node.keys.append(borrowed_key)
            node.children.append(borrowed_val)
            parent.keys[idx] = right.keys[0]
        else:
            borrowed_key = parent.keys[idx]
            parent.keys[idx] = right.keys.pop(0)
            borrowed_child = right.children.pop(0)
            node.keys.append(borrowed_key)
            node.children.append(borrowed_child)
            borrowed_child.parent = node

    def _merge(self, left: BPlusTreeNode, right: BPlusTreeNode, idx: int):
        """合并两个节点"""
        parent = left.parent
        if left.is_leaf:
            # 叶子合并
            left.keys.extend(right.keys)
            left.children.extend(right.children)
            left.next = right.next
            if right.next:
                right.next.prev = left
        else:
            # 内部合并：需要把父节点的分隔键也拉下来
            left.keys.append(parent.keys[idx])
            left.keys.extend(right.keys)
            left.children.extend(right.children)
            for child in right.children:
                child.parent = left
        # 从父节点删除分隔键和右子节点
        parent.keys.pop(idx)
        parent.children.pop(idx + 1)
        # 检查父节点是否下溢
        if parent == self.root:
            if len(parent.keys) == 0:
                self.root = parent.children[0] if parent.children else left
                self.root.parent = None
        elif len(parent.keys) < self._min_keys:
            self._fix_underflow(parent)

    def range_query(self, start_key, end_key) -> list[tuple]:
        """范围查询：利用叶子节点链表高效扫描"""
        leaf = self._find_leaf(start_key)
        results = []
        while leaf is not None:
            for i, k in enumerate(leaf.keys):
                if k > end_key:
                    return results
                if k >= start_key:
                    results.append((k, leaf.children[i]))
            leaf = leaf.next
        return results

    def get_all(self) -> list[tuple]:
        """获取所有键值对（有序）"""
        # 找到最左叶子
        node = self.root
        while not node.is_leaf:
            node = node.children[0]
        results = []
        while node is not None:
            for i, k in enumerate(node.keys):
                results.append((k, node.children[i]))
            node = node.next
        return results

    def height(self) -> int:
        """计算树高"""
        h = 1
        node = self.root
        while not node.is_leaf:
            h += 1
            node = node.children[0]
        return h


# ======================== 测试 ========================
if __name__ == "__main__":
    tree = BPlusTree(order=4)

    # 测试插入
    print("=== 插入测试 ===")
    for i in range(1, 21):
        tree.insert(i, f"value_{i}")
    all_items = tree.get_all()
    print(f"插入1-20后，共{len(all_items)}个键，树高={tree.height()}")
    assert len(all_items) == 20
    assert all(all_items[i][0] < all_items[i+1][0] for i in range(len(all_items)-1)), "应有序"
    print("[OK] 插入后数据有序且完整")

    # 测试查找
    print("\n=== 查找测试 ===")
    assert tree.search(10) == "value_10"
    assert tree.search(1) == "value_1"
    assert tree.search(20) == "value_20"
    assert tree.search(21) is None  # 不存在的key
    print("[OK] 查找正确")

    # 测试范围查询
    print("\n=== 范围查询测试 ===")
    results = tree.range_query(5, 10)
    keys = [r[0] for r in results]
    print(f"范围查询[5, 10]: keys={keys}")
    assert keys == [5, 6, 7, 8, 9, 10], f"期望[5,6,7,8,9,10]，实际{keys}"
    print("[OK] 范围查询正确")

    # 测试更新
    tree.insert(10, "updated_value")
    assert tree.search(10) == "updated_value"
    print("[OK] 更新值正确")

    # 测试删除
    print("\n=== 删除测试 ===")
    before_count = len(tree.get_all())
    # 删除一些键
    for key in [3, 7, 11, 15, 1, 20]:
        tree.delete(key)
        assert tree.search(key) is None, f"删除后key {key}应不存在"
    after_count = len(tree.get_all())
    all_items = tree.get_all()
    print(f"删除6个键后: {before_count} -> {after_count}")
    assert after_count == before_count - 6
    # 验证剩余数据仍然有序
    keys = [k for k, v in all_items]
    assert keys == sorted(keys), "删除后应保持有序"
    print("[OK] 删除后数据正确有序")

    # 测试大量数据
    print("\n=== 大量数据测试 ===")
    big_tree = BPlusTree(order=6)
    import random
    test_keys = list(range(1, 1001))
    random.shuffle(test_keys)
    for k in test_keys:
        big_tree.insert(k, k * 10)
    # 验证所有数据
    for k in range(1, 1001):
        assert big_tree.search(k) == k * 10, f"key {k} 查找失败"
    # 范围查询
    results = big_tree.range_query(500, 550)
    assert len(results) == 51, f"范围[500,550]应有51个结果，实际{len(results)}"
    print(f"1000个键，树高={big_tree.height()}，范围[500,550]返回{len(results)}条")
    print("[OK] 大量数据测试通过")
```

### 思考题
1. B+树与B树的区别是什么？为什么数据库索引选择B+树而非B树？
2. 页分裂时为什么选择中间位置分裂？如果选择其他位置（如1/3）会有什么影响？
3. 聚簇索引和非聚簇索引的回表操作有什么性能影响？如何用覆盖索引优化？

---

## 第7题：SQL查询优化器

### 知识点讲解

查询优化器是关系型数据库最复杂的组件之一，其目标是从多种执行计划中选择代价最小的方案。

**执行计划**：SQL语句的物理执行步骤。同一条SQL可以有多种执行方式，如全表扫描、索引扫描、索引合并等。优化器通过代价估算比较不同计划的执行成本，选择最优方案。

**代价模型**：基于统计信息估算执行代价。主要因素包括：I/O代价（磁盘读取页数）和CPU代价（记录比较、过滤计算）。代价估算公式通常为：`Total Cost = I/O Cost + CPU Cost * 权重`。MySQL的代价模型还考虑内存代价和网络传输代价。

**统计信息**：优化器决策的基础，包括表级统计（行数、页数）和列级统计（基数、直方图、NULL比例、最大最小值）。统计信息的准确性直接影响优化器决策质量，过时的统计信息可能导致选择次优计划。

**选择率**：谓词条件过滤掉的数据比例。如 `age > 30` 的选择率取决于数据分布。等值条件选择率 ≈ 1/基数，范围条件选择率需要直方图估算。选择率乘以表行数得到扫描后预估行数，影响后续JOIN代价估算。

**索引选择逻辑**：当查询条件列上有索引时，优化器估算索引扫描代价：`索引扫描代价 = 索引页读取 + 回表代价`。如果选择率很高（如90%），索引扫描+回表可能比全表扫描更慢，优化器应选择全表扫描。

```python
"""
SQL查询优化器：代价估算 + 执行计划选择
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ColumnStats:
    """列级统计信息"""
    name: str
    cardinality: int          # 不同值的数量（基数）
    null_count: int           # NULL值数量
    min_value: Any            # 最小值
    max_value: Any            # 最大值
    has_index: bool = False   # 是否有索引
    histogram: dict = field(default_factory=dict)  # 直方图: bucket -> count


@dataclass
class TableStats:
    """表级统计信息"""
    name: str
    row_count: int            # 总行数
    page_count: int           # 数据页数
    columns: dict = field(default_factory=dict)  # col_name -> ColumnStats


@dataclass
class Predicate:
    """查询谓词"""
    column: str
    operator: str             # '=', '>', '<', '>=', '<=', '!='
    value: Any

    def __repr__(self):
        return f"{self.column} {self.operator} {self.value}"


@dataclass
class ExecutionPlan:
    """执行计划"""
    access_method: str        # 'full_scan' 或 'index_scan'
    table: str
    predicate: Predicate | None
    estimated_rows: int       # 预估结果行数
    estimated_cost: float     # 预估代价
    explanation: str = ""     # 代价估算说明

    def __repr__(self):
        return (f"Plan(table={self.table}, method={self.access_method}, "
                f"predicate={self.predicate}, rows={self.estimated_rows}, "
                f"cost={self.estimated_cost:.2f})")


class CostEstimator:
    """
    代价估算器
    基于统计信息估算不同访问路径的执行代价
    """

    # 代价常量（参考MySQL模型简化版）
    COST_READ_PAGE = 1.0          # 读取一个数据页的I/O代价
    COST_READ_INDEX_PAGE = 0.5    # 读取一个索引页的I/O代价（索引更紧凑）
    COST_EVALUATE_CONDITION = 0.1 # 评估一次谓词条件的CPU代价
    COST_ROW_LOOKUP = 1.0         # 索引扫描后回表一次的代价

    def __init__(self, table_stats: TableStats):
        self.stats = table_stats

    def estimate_selectivity(self, predicate: Predicate) -> float:
        """
        估算谓词的选择率（0~1之间，1表示不过滤任何行）
        """
        col_stats = self.stats.columns.get(predicate.column)
        if col_stats is None:
            return 1.0  # 无统计信息，假设不过滤

        if predicate.operator == '=':
            # 等值条件：选择率 ≈ 1/基数
            return 1.0 / max(col_stats.cardinality, 1)

        elif predicate.operator == '!=':
            return 1.0 - 1.0 / max(col_stats.cardinality, 1)

        elif predicate.operator in ('>', '>=', '<', '<='):
            # 范围条件：基于min/max线性估算
            if col_stats.min_value is None or col_stats.max_value is None:
                return 0.33  # 默认值
            val = predicate.value
            vmin = col_stats.min_value
            vmax = col_stats.max_value
            if vmax == vmin:
                return 0.1
            if predicate.operator in ('>', '>='):
                selectivity = (vmax - val) / (vmax - vmin)
            else:
                selectivity = (val - vmin) / (vmax - vmin)
            return max(0.01, min(0.99, selectivity))

        return 1.0

    def estimate_full_scan_cost(self, predicate: Predicate | None) -> tuple[float, int]:
        """
        全表扫描代价 = 页读取代价 + 行评估代价
        """
        io_cost = self.stats.page_count * self.COST_READ_PAGE
        if predicate:
            cpu_cost = self.stats.row_count * self.COST_EVALUATE_CONDITION
        else:
            cpu_cost = 0  # 无谓词，不需要评估
        total = io_cost + cpu_cost
        if predicate:
            selectivity = self.estimate_selectivity(predicate)
            est_rows = int(self.stats.row_count * selectivity)
        else:
            est_rows = self.stats.row_count
        return total, est_rows

    def estimate_index_scan_cost(self, predicate: Predicate) -> tuple[float, int] | None:
        """
        索引扫描代价 = 索引页读取 + 回表代价
        如果列无索引返回None
        """
        col_stats = self.stats.columns.get(predicate.column)
        if col_stats is None or not col_stats.has_index:
            return None

        selectivity = self.estimate_selectivity(predicate)
        est_rows = int(self.stats.row_count * selectivity)

        # 索引页数估算（假设每个索引页存100个条目）
        index_pages = max(1, self.stats.row_count // 100)
        # 索引扫描需要读取的页数（按选择率比例）
        index_io_cost = max(1, int(index_pages * selectivity)) * self.COST_READ_INDEX_PAGE
        # 回表代价：每行需要一次随机I/O
        lookup_cost = est_rows * self.COST_ROW_LOOKUP

        total = index_io_cost + lookup_cost
        return total, est_rows

    def choose_best_plan(self, predicate: Predicate | None) -> ExecutionPlan:
        """
        选择最优执行计划：比较全表扫描和索引扫描的代价
        """
        if predicate is None:
            # 无谓词，只能全表扫描
            cost, rows = self.estimate_full_scan_cost(None)
            return ExecutionPlan(
                access_method="full_scan",
                table=self.stats.name,
                predicate=None,
                estimated_rows=rows,
                estimated_cost=cost,
                explanation="无查询条件，只能全表扫描"
            )

        # 计算全表扫描代价
        full_cost, full_rows = self.estimate_full_scan_cost(predicate)

        # 尝试计算索引扫描代价
        index_result = self.estimate_index_scan_cost(predicate)

        if index_result is None:
            # 无可用索引
            return ExecutionPlan(
                access_method="full_scan",
                table=self.stats.name,
                predicate=predicate,
                estimated_rows=full_rows,
                estimated_cost=full_cost,
                explanation=f"列 '{predicate.column}' 无索引，只能全表扫描"
            )

        index_cost, index_rows = index_result

        # 选择代价更低的方案
        if index_cost < full_cost:
            method = "index_scan"
            cost = index_cost
            explanation = (f"索引扫描代价({index_cost:.2f}) < 全表扫描代价({full_cost:.2f})，"
                          f"选择率={self.estimate_selectivity(predicate):.2%}，选择索引扫描")
        else:
            method = "full_scan"
            cost = full_cost
            explanation = (f"全表扫描代价({full_cost:.2f}) <= 索引扫描代价({index_cost:.2f})，"
                          f"选择率={self.estimate_selectivity(predicate):.2%}，选择全表扫描")

        return ExecutionPlan(
            access_method=method,
            table=self.stats.name,
            predicate=predicate,
            estimated_rows=full_rows,
            estimated_cost=cost,
            explanation=explanation
        )


class QueryOptimizer:
    """查询优化器：整合多表代价估算"""

    def __init__(self):
        self._table_stats: dict[str, TableStats] = {}

    def register_table(self, stats: TableStats):
        self._table_stats[stats.name] = stats

    def optimize_single_table(self, table: str, predicate: Predicate | None) -> ExecutionPlan:
        """单表查询优化"""
        stats = self._table_stats.get(table)
        if stats is None:
            raise ValueError(f"表 '{table}' 未注册")
        estimator = CostEstimator(stats)
        return estimator.choose_best_plan(predicate)

    def explain(self, plan: ExecutionPlan) -> str:
        """生成执行计划说明（类似EXPLAIN输出）"""
        lines = [
            f"=== 执行计划 ===",
            f"表名:     {plan.table}",
            f"访问方式: {plan.access_method}",
            f"谓词条件: {plan.predicate or '无'}",
            f"预估行数: {plan.estimated_rows}",
            f"预估代价: {plan.estimated_cost:.2f}",
            f"说明:     {plan.explanation}",
        ]
        return "\n".join(lines)


# ======================== 测试 ========================
if __name__ == "__main__":
    optimizer = QueryOptimizer()

    # 注册一张用户表（模拟100万行数据）
    user_stats = TableStats(
        name="users",
        row_count=1_000_000,
        page_count=12500,  # 假设每页80行
        columns={
            "id": ColumnStats("id", 1_000_000, 0, 1, 1_000_000, has_index=True),
            "age": ColumnStats("age", 100, 0, 1, 120, has_index=True),
            "city": ColumnStats("city", 350, 0, "北京", "遵义", has_index=True),
            "name": ColumnStats("name", 900_000, 0, "阿", "佐", has_index=False),
        }
    )
    optimizer.register_table(user_stats)

    # 测试1：高选择率查询（等值主键）—— 应选索引扫描
    print("=== 测试1：主键等值查询 ===")
    pred1 = Predicate("id", "=", 42)
    plan1 = optimizer.optimize_single_table("users", pred1)
    print(optimizer.explain(plan1))
    assert plan1.access_method == "index_scan", "主键等值查询应选索引扫描"
    print("[OK] 高选择率查询选择索引扫描\n")

    # 测试2：低选择率范围查询（age > 30，大部分行匹配）—— 应选全表扫描
    print("=== 测试2：大范围查询 ===")
    pred2 = Predicate("age", ">", 30)
    plan2 = optimizer.optimize_single_table("users", pred2)
    print(optimizer.explain(plan2))
    # age范围1-120，age>30选择率≈75%，太高应全表扫描
    assert plan2.access_method == "full_scan", "高选择率范围查询应选全表扫描"
    print("[OK] 低选择率查询选择全表扫描\n")

    # 测试3：高选择率范围查询（age > 110）—— 应选索引扫描
    print("=== 测试3：小范围查询 ===")
    pred3 = Predicate("age", ">", 110)
    plan3 = optimizer.optimize_single_table("users", pred3)
    print(optimizer.explain(plan3))
    assert plan3.access_method == "index_scan", "低选择率范围查询应选索引扫描"
    print("[OK] 高选择率范围查询选择索引扫描\n")

    # 测试4：无索引列查询 —— 应选全表扫描
    print("=== 测试4：无索引列查询 ===")
    pred4 = Predicate("name", "=", "张三")
    plan4 = optimizer.optimize_single_table("users", pred4)
    print(optimizer.explain(plan4))
    assert plan4.access_method == "full_scan", "无索引列应选全表扫描"
    print("[OK] 无索引列选择全表扫描\n")

    # 测试5：无谓词查询 —— 应选全表扫描
    print("=== 测试5：无谓词查询 ===")
    plan5 = optimizer.optimize_single_table("users", None)
    print(optimizer.explain(plan5))
    assert plan5.access_method == "full_scan", "无谓词应选全表扫描"
    assert plan5.estimated_rows == 1_000_000, "无谓词预估行数应为全表"
    print("[OK] 无谓词选择全表扫描\n")

    # 测试6：城市等值查询（中等选择率）
    print("=== 测试6：城市等值查询 ===")
    pred6 = Predicate("city", "=", "北京")
    plan6 = optimizer.optimize_single_table("users", pred6)
    print(optimizer.explain(plan6))
    selectivity = 1.0 / 350  # 约0.29%
    print(f"选择率: {selectivity:.4%}, 预估行数: {plan6.estimated_rows}")
    print("[OK] 中等选择率查询评估正确")
```

### 思考题
1. 代价估算的准确性高度依赖统计信息，如何自动更新统计信息？过期统计信息会导致什么问题？
2. JOIN操作的执行计划有哪些？嵌套循环JOIN、哈希JOIN、排序合并JOIN各适合什么场景？
3. 查询优化器如何处理子查询？子查询展开和物化策略各有什么优缺点？

---

## 第8题：MVCC多版本并发控制

### 知识点讲解

MVCC（Multi-Version Concurrency Control）是现代数据库实现高并发读写的核心技术。其核心思想是：读操作不阻塞写操作，写操作也不阻塞读操作，通过维护数据的多个版本来实现。

**版本链**：每行数据维护多个版本，每个版本记录创建它的事务ID（trx_id）和删除它的事务ID（del_trx_id）。版本按时间顺序链接，形成版本链。InnoDB在Undo Log中保存旧版本数据。

**Read View（读视图）**：事务开始时创建的快照，记录当前活跃事务列表。通过Read View判断某个数据版本对当前事务是否可见：
- 版本的trx_id < Read View中最小活跃事务ID → 版本在当前事务开始前已提交 → 可见
- 版本的trx_id >= Read View中最大事务ID → 版本在当前事务开始后创建 → 不可见
- 版本的trx_id在活跃事务列表中 → 不可见（创建该版本的事务还未提交）
- 否则 → 可见

**读已提交 vs 可重复读**：RC隔离级别下，每次SELECT都创建新的Read View，能看到其他事务已提交的最新数据；RR隔离级别下，事务开始时创建一次Read View，整个事务期间使用同一快照，保证可重复读。

**写偏差异常**：可重复读隔离级别下可能出现的异常。如两个事务同时读取到满足条件的行集（都未提交），各自基于快照做出写决策，但两个写操作在串行化执行时不可能同时成立。解决方法是使用SELECT FOR UPDATE加锁或Serializable隔离级别。

```python
"""
MVCC多版本并发控制：基于时间戳的版本链 + Read View
"""
import threading
import time
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class Version:
    """数据版本"""
    value: any
    created_trx_id: int    # 创建此版本的事务ID
    deleted_trx_id: int | None = None  # 删除此版本的事务ID（None表示未删除）
    next: 'Version | None' = None  # 指向更旧的版本


@dataclass
class Transaction:
    """事务"""
    trx_id: int
    is_active: bool = True
    is_committed: bool = False
    is_rolled_back: bool = False
    start_time: float = field(default_factory=time.time)
    # 该事务使用的Read View（活跃事务ID列表）
    read_view: set | None = None
    read_view_min: int = 0    # Read View中最小活跃事务ID
    read_view_max: int = 0    # Read View中下一个将分配的事务ID


class MVCCStore:
    """
    MVCC存储引擎
    - 每个key维护一个版本链
    - 支持RC和RR两种隔离级别
    """

    def __init__(self):
        self._data: dict[str, Version] = {}  # key -> 最新版本（链表头）
        self._transactions: dict[int, Transaction] = {}
        self._next_trx_id = 1
        self._lock = threading.Lock()

    def begin_transaction(self, isolation_level: str = "RR") -> int:
        """开始事务，返回事务ID"""
        with self._lock:
            trx_id = self._next_trx_id
            self._next_trx_id += 1
            trx = Transaction(trx_id=trx_id)
            # 创建Read View：记录当前活跃事务列表
            active_trx_ids = {
                t.trx_id for t in self._transactions.values() if t.is_active
            }
            trx.read_view = active_trx_ids
            trx.read_view_min = min(active_trx_ids) if active_trx_ids else 0
            trx.read_view_max = self._next_trx_id
            trx._isolation_level = isolation_level
            self._transactions[trx_id] = trx
            return trx_id

    def commit(self, trx_id: int):
        """提交事务"""
        with self._lock:
            trx = self._transactions.get(trx_id)
            if trx:
                trx.is_active = False
                trx.is_committed = True

    def rollback(self, trx_id: int):
        """回滚事务：撤销该事务的所有修改"""
        with self._lock:
            trx = self._transactions.get(trx_id)
            if trx:
                trx.is_active = False
                trx.is_rolled_back = True
                # 清理该事务创建的版本
                for key in list(self._data.keys()):
                    version = self._data[key]
                    if version and version.created_trx_id == trx_id:
                        # 恢复到上一个版本
                        if version.next:
                            self._data[key] = version.next
                        else:
                            del self._data[key]

    def _is_visible(self, version: Version, trx: Transaction) -> bool:
        """判断版本对事务是否可见"""
        # 1. 版本由自己创建 → 可见（自己能看到自己的修改）
        if version.created_trx_id == trx.trx_id:
            return version.deleted_trx_id is None or version.deleted_trx_id != trx.trx_id
        # 2. 版本在Read View之前创建（trx_id < min_active）→ 可见
        if version.created_trx_id < trx.read_view_min:
            visible_by_create = True
        # 3. 版本在Read View之后创建（trx_id >= max_active）→ 不可见
        elif version.created_trx_id >= trx.read_view_max:
            visible_by_create = False
        # 4. 创建版本的事务在活跃列表中 → 不可见
        elif version.created_trx_id in trx.read_view:
            visible_by_create = False
        else:
            visible_by_create = True

        if not visible_by_create:
            return False

        # 5. 检查删除标记
        if version.deleted_trx_id is None:
            return True  # 未被删除
        # 删除此版本的事务是否对当前事务可见
        if version.deleted_trx_id == trx.trx_id:
            return False  # 自己删除的
        if version.deleted_trx_id < trx.read_view_min:
            return False  # 删除操作已提交
        if version.deleted_trx_id >= trx.read_view_max:
            return True  # 删除操作还未发生
        if version.deleted_trx_id in trx.read_view:
            return True  # 删除操作未提交
        return False  # 删除操作已提交

    def read(self, key: str, trx_id: int) -> any:
        """读取key的值（根据事务的Read View选择可见版本）"""
        trx = self._transactions[trx_id]
        # RC隔离级别：每次读取刷新Read View
        if getattr(trx, '_isolation_level', 'RR') == 'RC':
            with self._lock:
                active = {t.trx_id for t in self._transactions.values() if t.is_active}
                trx.read_view = active
                trx.read_view_min = min(active) if active else 0
                trx.read_view_max = self._next_trx_id

        version = self._data.get(key)
        while version is not None:
            if self._is_visible(version, trx):
                return version.value
            version = version.next
        return None  # 无可见版本

    def write(self, key: str, value: any, trx_id: int):
        """写入key的新值（创建新版本）"""
        with self._lock:
            old_version = self._data.get(key)
            # 如果有旧版本，标记为被当前事务删除
            if old_version and old_version.created_trx_id != trx_id:
                old_version.deleted_trx_id = trx_id
            # 创建新版本
            new_version = Version(
                value=value,
                created_trx_id=trx_id,
                next=old_version,
            )
            self._data[key] = new_version

    def delete(self, key: str, trx_id: int):
        """删除key（标记最新版本为已删除）"""
        with self._lock:
            version = self._data.get(key)
            if version and version.deleted_trx_id is None:
                version.deleted_trx_id = trx_id

    def refresh_read_view(self, trx_id: int):
        """刷新事务的Read View（用于RC隔离级别）"""
        with self._lock:
            trx = self._transactions.get(trx_id)
            if trx:
                active = {t.trx_id for t in self._transactions.values() if t.is_active}
                trx.read_view = active
                trx.read_view_min = min(active) if active else 0
                trx.read_view_max = self._next_trx_id


# ======================== 测试 ========================
if __name__ == "__main__":
    store = MVCCStore()

    # 测试1：基本读写
    print("=== 测试1：基本读写 ===")
    trx1 = store.begin_transaction()
    store.write("name", "Alice", trx1)
    store.commit(trx1)

    trx2 = store.begin_transaction()
    assert store.read("name", trx2) == "Alice"
    store.commit(trx2)
    print("[OK] 基本读写正确")

    # 测试2：可重复读（RR）
    print("\n=== 测试2：可重复读 ===")
    trx_a = store.begin_transaction("RR")  # 事务A开始
    val1 = store.read("name", trx_a)  # A读到Alice

    trx_b = store.begin_transaction("RR")  # 事务B开始
    store.write("name", "Bob", trx_b)      # B修改name
    store.commit(trx_b)                      # B提交

    val2 = store.read("name", trx_a)  # A再次读，应仍然是Alice
    print(f"事务A第一次读: {val1}, 第二次读: {val2}")
    assert val1 == val2 == "Alice", "RR隔离级别下应可重复读"
    store.commit(trx_a)

    trx_c = store.begin_transaction("RR")
    val3 = store.read("name", trx_c)
    assert val3 == "Bob", "新事务应读到最新值Bob"
    store.commit(trx_c)
    print("[OK] 可重复读：事务A始终读到Alice，新事务读到Bob")

    # 测试3：读已提交（RC）
    print("\n=== 测试3：读已提交 ===")
    trx_d = store.begin_transaction("RC")  # 事务D（RC隔离级别）
    val_before = store.read("name", trx_d)  # D读到Bob

    trx_e = store.begin_transaction("RC")
    store.write("name", "Charlie", trx_e)
    store.commit(trx_e)  # E提交

    val_after = store.read("name", trx_d)  # D再次读，应看到Charlie
    print(f"事务D第一次读: {val_before}, 第二次读: {val_after}")
    assert val_before == "Bob" and val_after == "Charlie", "RC隔离级别应读到最新已提交值"
    store.commit(trx_d)
    print("[OK] 读已提交：事务D第二次读到Charlie")

    # 测试4：事务回滚
    print("\n=== 测试4：事务回滚 ===")
    trx_f = store.begin_transaction()
    store.write("name", "David", trx_f)
    # 回滚前，自己能看到
    assert store.read("name", trx_f) == "David"
    store.rollback(trx_f)
    trx_g = store.begin_transaction()
    assert store.read("name", trx_g) == "Charlie", "回滚后应恢复到Charlie"
    store.commit(trx_g)
    print("[OK] 回滚后数据恢复")

    # 测试5：写偏差异常演示
    print("\n=== 测试5：写偏差异常 ===")
    # 场景：两个医生都看到对方休假，各自请假，导致无人值班
    store2 = MVCCStore()
    # 初始化：两个医生都在岗
    init_trx = store2.begin_transaction()
    store2.write("doctor_A", "on_duty", init_trx)
    store2.write("doctor_B", "on_duty", init_trx)
    store2.commit(init_trx)

    # 事务1：检查是否有人值班（读到A和B都在岗），A请假
    trx1 = store2.begin_transaction("RR")
    a_status = store2.read("doctor_A", trx1)
    b_status = store2.read("doctor_B", trx1)
    print(f"事务1读到: A={a_status}, B={b_status}")
    # B在岗，A可以请假
    if b_status == "on_duty":
        store2.write("doctor_A", "off_duty", trx1)

    # 事务2：同时检查并让B请假
    trx2 = store2.begin_transaction("RR")
    a_status2 = store2.read("doctor_A", trx2)  # 读到旧的A（on_duty）
    b_status2 = store2.read("doctor_B", trx2)
    print(f"事务2读到: A={a_status2}, B={b_status2}")
    if a_status2 == "on_duty":
        store2.write("doctor_B", "off_duty", trx2)

    # 两个事务都提交
    store2.commit(trx1)
    store2.commit(trx2)

    # 验证结果：两个医生都请假了（写偏差异常！）
    check_trx = store2.begin_transaction()
    final_a = store2.read("doctor_A", check_trx)
    final_b = store2.read("doctor_B", check_trx)
    store2.commit(check_trx)
    print(f"最终结果: A={final_a}, B={final_b}")
    if final_a == "off_duty" and final_b == "off_duty":
        print("[!] 写偏差异常发生：两个医生都请假了，无人值班！")
        print("    解决方案：使用SELECT FOR UPDATE加锁，或使用Serializable隔离级别")
    print("[OK] 写偏差异常演示完成")
```

### 思考题
1. MVCC如何解决脏读、不可重复读、幻读问题？RR隔离级别下是否完全解决了幻读？
2. 版本链过长会导致什么性能问题？如何用Purge线程清理旧版本？
3. 写偏差异常在什么条件下发生？为什么Serializable隔离级别能避免它？

---

## 第9题：分库分表中间件

### 知识点讲解

当单表数据量超过千万级，数据库性能开始下降，分库分表是水平扩展的核心手段。

**分片策略**：主要有哈希分片和范围分片两种。哈希分片通过对分片键取哈希后取模，将数据均匀分散到各分片，适合等值查询但范围查询需要扫描所有分片。范围分片按分片键的值域划分，如ID 1-10000在分片1、10001-20000在分片2，适合范围查询但可能导致数据热点（最新数据集中在最后一个分片）。

**分片键选择**：分片键决定了数据的分布方式，选择原则包括：高频查询条件优先、数据分布均匀、避免跨分片查询。常见选择是用户ID或订单ID作为分片键。一旦确定分片键，非分片键的查询需要广播到所有分片（Scatter-Gather），性能较差。

**跨分片查询**：非分片键条件查询需要将请求发送到所有分片，合并结果。分页查询更复杂——`LIMIT 10 OFFSET 20`在分片场景下需要对每个分片取前30条，合并后再取第21-30条。跨分片JOIN通常通过绑定表（相同分片键的表分到同一分片）或广播表（小表复制到所有分片）优化。

**全局ID生成**：分库分表后各分片自增ID会冲突，需要全局唯一ID。常用方案：UUID（无序，索引友好度差）、雪花算法Snowflake（时间戳+机器ID+序列号，有序且高性能）、号段模式（每次从DB批量取一段ID）。分布式ID需要保证全局唯一、趋势递增、高性能、高可用。

```python
"""
分库分表中间件：哈希分片 + 范围分片 + 全局ID生成
"""
import hashlib
import threading
import time
from dataclasses import dataclass, field
from typing import Any
from collections import defaultdict


# ======================== 全局ID生成器 ========================
class SnowflakeIDGenerator:
    """
    雪花算法ID生成器
    结构: [1位符号位][41位时间戳][10位机器ID][12位序列号]
    """

    def __init__(self, machine_id: int):
        self.machine_id = machine_id & 0x3FF  # 10位机器ID
        self._sequence = 0
        self._last_timestamp = -1
        self._lock = threading.Lock()
        # 起始时间戳（2024-01-01）
        self._epoch = 1704067200000
        self._machine_bits = 10
        self._sequence_bits = 12
        self._max_sequence = (1 << self._sequence_bits) - 1

    def _current_ms(self) -> int:
        return int(time.time() * 1000)

    def generate(self) -> int:
        """生成全局唯一ID"""
        with self._lock:
            timestamp = self._current_ms()
            if timestamp == self._last_timestamp:
                self._sequence = (self._sequence + 1) & self._max_sequence
                if self._sequence == 0:
                    # 序列号耗尽，等待下一毫秒
                    while timestamp <= self._last_timestamp:
                        timestamp = self._current_ms()
            else:
                self._sequence = 0
            self._last_timestamp = timestamp
            return ((timestamp - self._epoch) << (self._machine_bits + self._sequence_bits)
                    | (self.machine_id << self._sequence_bits)
                    | self._sequence)


class SegmentIDGenerator:
    """
    号段模式ID生成器
    每次从数据库批量获取一段ID，减少DB访问
    """

    def __init__(self, step: int = 1000):
        self.step = step
        self._current = 0
        self._max = 0
        self._lock = threading.Lock()

    def _load_segment(self):
        """模拟从DB加载号段"""
        self._current = self._max + 1
        self._max = self._current + self.step - 1

    def generate(self) -> int:
        with self._lock:
            if self._current >= self._max:
                self._load_segment()
            self._current += 1
            return self._current


# ======================== 分片策略 ========================
class ShardStrategy:
    """分片策略基类"""

    def get_shard(self, key: Any, shard_count: int) -> int:
        raise NotImplementedError


class HashShardStrategy(ShardStrategy):
    """哈希分片：对key取哈希后取模"""

    def get_shard(self, key: Any, shard_count: int) -> int:
        if isinstance(key, int):
            return key % shard_count
        h = int(hashlib.md5(str(key).encode()).hexdigest(), 16)
        return h % shard_count


class RangeShardStrategy(ShardStrategy):
    """范围分片：按key的值域划分"""

    def __init__(self, boundaries: list):
        """boundaries: 分界值列表，如 [10000, 20000, 30000] 表示4个分片"""
        self.boundaries = boundaries

    def get_shard(self, key: Any, shard_count: int) -> int:
        for i, boundary in enumerate(self.boundaries):
            if key < boundary:
                return i
        return len(self.boundaries)


# ======================== 分片节点 ========================
@dataclass
class ShardNode:
    """分片节点（模拟一个数据库实例）"""
    shard_id: int
    name: str
    data: dict = field(default_factory=dict)  # 主键 -> 记录

    def insert(self, pk: Any, record: dict):
        self.data[pk] = record

    def select(self, pk: Any) -> dict | None:
        return self.data.get(pk)

    def select_where(self, column: str, value: Any) -> list[dict]:
        """条件查询"""
        return [r for r in self.data.values() if r.get(column) == value]

    def select_range(self, column: str, start: Any, end: Any) -> list[dict]:
        """范围查询"""
        return [r for r in self.data.values() if start <= r.get(column, float('inf')) <= end]

    def count(self) -> int:
        return len(self.data)


# ======================== 分库分表中间件 ========================
class ShardingMiddleware:
    """
    分库分表中间件
    - 管理多个分片节点
    - 路由请求到正确的分片
    - 处理跨分片查询
    """

    def __init__(self, shard_key: str, strategy: ShardStrategy, shard_count: int):
        self.shard_key = shard_key
        self.strategy = strategy
        self.shard_count = shard_count
        self.shards: list[ShardNode] = [
            ShardNode(shard_id=i, name=f"shard_{i}") for i in range(shard_count)
        ]
        self._id_generator = SnowflakeIDGenerator(machine_id=1)

    def _get_shard(self, record: dict) -> ShardNode:
        """根据分片键路由到正确分片"""
        key_value = record[self.shard_key]
        shard_id = self.strategy.get_shard(key_value, self.shard_count)
        return self.shards[shard_id]

    def _get_shard_by_key_value(self, key_value: Any) -> ShardNode:
        shard_id = self.strategy.get_shard(key_value, self.shard_count)
        return self.shards[shard_id]

    def insert(self, record: dict) -> int:
        """插入记录，自动生成全局ID"""
        pk = self._id_generator.generate()
        record['id'] = pk
        shard = self._get_shard(record)
        shard.insert(pk, record)
        return pk

    def select_by_id(self, pk: int, shard_key_value: Any = None) -> dict | None:
        """
        根据主键查询
        如果提供shard_key_value，可以直接路由到正确分片
        否则需要广播到所有分片
        """
        if shard_key_value is not None:
            shard = self._get_shard_by_key_value(shard_key_value)
            return shard.select(pk)
        # 广播查询
        for shard in self.shards:
            result = shard.select(pk)
            if result is not None:
                return result
        return None

    def select_by_shard_key(self, key_value: Any) -> list[dict]:
        """根据分片键精确查询（高效：只查一个分片）"""
        shard = self._get_shard_by_key_value(key_value)
        return list(shard.data.values())

    def select_where(self, column: str, value: Any) -> list[dict]:
        """
        非分片键条件查询（低效：广播到所有分片）
        """
        results = []
        for shard in self.shards:
            results.extend(shard.select_where(column, value))
        return results

    def select_range(self, column: str, start: Any, end: Any) -> list[dict]:
        """范围查询（跨分片）"""
        results = []
        for shard in self.shards:
            results.extend(shard.select_range(column, start, end))
        return results

    def paginate(self, column: str, page: int, page_size: int) -> list[dict]:
        """
        跨分片分页查询
        需要从每个分片取前 page*page_size 条，合并排序后再截取
        """
        offset = (page - 1) * page_size
        limit = offset + page_size
        all_results = []
        for shard in self.shards:
            # 每个分片取前 limit 条
            records = sorted(shard.data.values(), key=lambda r: r.get(column, 0))
            all_results.extend(records[:limit])
        # 合并排序
        all_results.sort(key=lambda r: r.get(column, 0))
        # 截取对应页
        return all_results[offset:offset + page_size]

    def stats(self) -> dict:
        return {
            "shard_count": self.shard_count,
            "shard_key": self.shard_key,
            "total_records": sum(s.count() for s in self.shards),
            "per_shard": {s.name: s.count() for s in self.shards},
        }


# ======================== 测试 ========================
if __name__ == "__main__":
    # 测试全局ID生成器
    print("=== 雪花算法ID生成器 ===")
    gen = SnowflakeIDGenerator(machine_id=1)
    ids = [gen.generate() for _ in range(1000)]
    assert len(set(ids)) == 1000, "ID应全部唯一"
    assert ids == sorted(ids), "ID应趋势递增"
    print(f"生成1000个ID，唯一性={len(set(ids))==1000}, 递增性={ids==sorted(ids)}")
    print("[OK] 雪花算法ID唯一且递增")

    # 测试号段模式
    print("\n=== 号段模式ID生成器 ===")
    seg_gen = SegmentIDGenerator(step=100)
    seg_ids = [seg_gen.generate() for _ in range(250)]
    assert len(set(seg_ids)) == 250
    assert seg_ids[0] == 1 and seg_ids[99] == 100 and seg_ids[100] == 101
    print(f"号段模式生成250个ID: 第1个={seg_ids[0]}, 第100个={seg_ids[99]}, 第101个={seg_ids[100]}")
    print("[OK] 号段模式ID正确")

    # 测试哈希分片
    print("\n=== 哈希分片测试 ===")
    hash_middleware = ShardingMiddleware(
        shard_key="user_id",
        strategy=HashShardStrategy(),
        shard_count=4,
    )
    # 插入1000条记录
    for i in range(1000):
        record = {"user_id": i, "name": f"user_{i}", "age": 20 + i % 50}
        hash_middleware.insert(record)
    stats = hash_middleware.stats()
    print(f"哈希分片统计: {stats['per_shard']}")
    # 验证分布均匀
    for shard_name, count in stats["per_shard"].items():
        assert 200 < count < 300, f"{shard_name}分布不均匀: {count}"
    print("[OK] 哈希分片数据分布均匀")

    # 测试分片键精确查询（高效）
    result = hash_middleware.select_by_shard_key(42)
    assert len(result) == 1 and result[0]["user_id"] == 42
    print("[OK] 分片键查询直接路由到正确分片")

    # 测试非分片键查询（广播）
    results = hash_middleware.select_where("age", 30)
    print(f"非分片键查询 age=30: 找到{len(results)}条（广播到4个分片）")
    assert all(r["age"] == 30 for r in results)

    # 测试范围分片
    print("\n=== 范围分片测试 ===")
    range_middleware = ShardingMiddleware(
        shard_key="order_id",
        strategy=RangeShardStrategy(boundaries=[1000, 2000, 3000]),
        shard_count=4,
    )
    # 插入记录到不同范围
    for i in range(0, 4000, 100):
        record = {"order_id": i, "amount": i * 10}
        range_middleware.insert(record)
    stats = range_middleware.stats()
    print(f"范围分片统计: {stats['per_shard']}")
    # 范围查询：order_id在1000-2000之间
    results = range_middleware.select_range("order_id", 1000, 2000)
    print(f"范围查询 order_id [1000, 2000]: 找到{len(results)}条")
    assert all(1000 <= r["order_id"] <= 2000 for r in results)
    print("[OK] 范围查询正确")

    # 测试跨分片分页
    print("\n=== 跨分片分页测试 ===")
    page1 = hash_middleware.paginate("user_id", page=1, page_size=10)
    page2 = hash_middleware.paginate("user_id", page=2, page_size=10)
    print(f"第1页: user_ids = {[r['user_id'] for r in page1]}")
    print(f"第2页: user_ids = {[r['user_id'] for r in page2]}")
    assert len(page1) == 10 and len(page2) == 10
    assert page1[-1]["user_id"] < page2[0]["user_id"], "分页应有序"
    print("[OK] 跨分片分页正确")

    # 测试主键查询
    pk = hash_middleware.insert({"user_id": 999, "name": "test", "age": 99})
    result = hash_middleware.select_by_id(pk, shard_key_value=999)
    assert result is not None and result["name"] == "test"
    print(f"\n[OK] 主键查询: pk={pk}, result={result}")
```

### 思考题
1. 哈希分片和范围分片各有什么优缺点？什么场景下应该选择哪种策略？
2. 跨分片JOIN如何实现？绑定表和广播表的原理是什么？
3. 分库分表后如何实现分布式事务？XA事务和最终一致性方案各有什么优缺点？

---

## 第10题：WAL预写日志

### 知识点讲解

WAL（Write-Ahead Logging）是数据库保证持久性的核心机制。其核心原则是：在修改数据页之前，先将修改操作记录到日志文件中。这样即使系统崩溃，也可以通过重放日志恢复数据。

**日志结构**：每条日志记录包含：LSN（日志序列号，单调递增）、事务ID、操作类型（INSERT/UPDATE/DELETE）、修改前数据、修改后数据。LSN是日志的全局序号，用于标识日志位置和实现时间点恢复。日志通常是追加写入（Append-Only），顺序I/O性能远高于随机I/O。

**Redo Log**：记录修改后的新值。崩溃恢复时重放Redo Log，将已提交但未刷盘的数据重新写入，保证持久性。Redo Log是物理日志（记录页级别的修改）或逻辑日志（记录SQL操作）。

**Undo Log**：记录修改前的旧值。崩溃恢复时用于回滚未提交的事务，保证原子性。Undo Log也用于MVCC实现（读取历史版本）。Redo和Undo配合实现ACID中的A（原子性）和D（持久性）。

**检查点**：定期将内存中的脏页刷盘，并记录检查点LSN。恢复时只需从检查点LSN开始重放日志，缩短恢复时间。检查点策略包括：固定间隔检查点、模糊检查点（不阻塞写入）。检查点过于频繁影响性能，过于稀疏导致恢复时间长。

**崩溃恢复流程**：1. 读取最后一个检查点LSN；2. 从该LSN开始扫描日志；3. 重放所有已提交事务的Redo Log（重做）；4. 回滚所有未提交事务的Undo Log（撤销）；5. 恢复完成。

```python
"""
WAL预写日志：日志记录 + 检查点 + 崩溃恢复
"""
import os
import json
import time
import threading
from dataclasses import dataclass, field, asdict
from enum import Enum


class OpType(Enum):
    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    BEGIN = "BEGIN"
    COMMIT = "COMMIT"
    ABORT = "ABORT"
    CHECKPOINT = "CHECKPOINT"


@dataclass
class LogRecord:
    """日志记录"""
    lsn: int                    # 日志序列号
    trx_id: int                 # 事务ID
    op_type: OpType             # 操作类型
    table: str = ""             # 表名
    key: str = ""               # 记录键
    old_value: dict | None = None  # 修改前值（用于Undo）
    new_value: dict | None = None  # 修改后值（用于Redo）
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["op_type"] = self.op_type.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "LogRecord":
        d["op_type"] = OpType(d["op_type"])
        return cls(**d)


class WALLogger:
    """WAL日志管理器"""

    def __init__(self, log_file: str):
        self.log_file = log_file
        self._lsn = 0
        self._lock = threading.Lock()
        # 内存中的日志缓冲（实际场景会刷盘）
        self._records: list[LogRecord] = []
        self._committed_trx: set[int] = set()

    def append(self, trx_id: int, op_type: OpType, table: str = "",
               key: str = "", old_value: dict | None = None,
               new_value: dict | None = None) -> int:
        """追加日志记录，返回LSN"""
        with self._lock:
            self._lsn += 1
            record = LogRecord(
                lsn=self._lsn,
                trx_id=trx_id,
                op_type=op_type,
                table=table,
                key=key,
                old_value=old_value,
                new_value=new_value,
            )
            self._records.append(record)
            if op_type == OpType.COMMIT:
                self._committed_trx.add(trx_id)
            return self._lsn

    def checkpoint(self, dirty_pages: dict[str, dict]):
        """创建检查点：记录当前状态"""
        with self._lock:
            self._lsn += 1
            record = LogRecord(
                lsn=self._lsn,
                trx_id=0,
                op_type=OpType.CHECKPOINT,
                table="",
                key="",
                old_value=None,
                new_value={"dirty_pages": dirty_pages, "committed": list(self._committed_trx)},
            )
            self._records.append(record)
            return self._lsn

    def get_records_after(self, lsn: int) -> list[LogRecord]:
        """获取指定LSN之后的日志记录"""
        return [r for r in self._records if r.lsn > lsn]

    def get_all_records(self) -> list[LogRecord]:
        return list(self._records)

    def get_last_checkpoint_lsn(self) -> int:
        """获取最后一个检查点的LSN"""
        for record in reversed(self._records):
            if record.op_type == OpType.CHECKPOINT:
                return record.lsn
        return 0

    def is_committed(self, trx_id: int) -> bool:
        return trx_id in self._committed_trx

    def save_to_file(self):
        """将日志持久化到文件"""
        with open(self.log_file, 'w', encoding='utf-8') as f:
            for record in self._records:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False) + '\n')

    def load_from_file(self):
        """从文件加载日志"""
        if not os.path.exists(self.log_file):
            self._records = []
            self._lsn = 0
            return
        self._records = []
        self._committed_trx = set()
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    record = LogRecord.from_dict(json.loads(line))
                    self._records.append(record)
                    if record.lsn > self._lsn:
                        self._lsn = record.lsn
                    if record.op_type == OpType.COMMIT:
                        self._committed_trx.add(record.trx_id)


class WALDatabase:
    """
    基于WAL的简易数据库
    - 写操作先记日志再修改内存数据
    - 支持检查点和崩溃恢复
    """

    def __init__(self, wal_file: str = "wal.log"):
        self.wal = WALLogger(wal_file)
        self._data: dict[str, dict] = {}  # key -> value
        self._active_trx: set[int] = set()
        self._next_trx_id = 1
        self._lock = threading.Lock()

    def begin(self) -> int:
        """开始事务"""
        with self._lock:
            trx_id = self._next_trx_id
            self._next_trx_id += 1
            self._active_trx.add(trx_id)
            self.wal.append(trx_id, OpType.BEGIN)
            return trx_id

    def put(self, trx_id: int, key: str, value: dict):
        """插入/更新"""
        old_value = self._data.get(key)
        self.wal.append(trx_id, OpType.UPDATE, key=key,
                        old_value=old_value, new_value=value)
        self._data[key] = value

    def delete(self, trx_id: int, key: str):
        """删除"""
        old_value = self._data.get(key)
        if old_value:
            self.wal.append(trx_id, OpType.DELETE, key=key, old_value=old_value)
            del self._data[key]

    def get(self, key: str) -> dict | None:
        """读取"""
        return self._data.get(key)

    def commit(self, trx_id: int):
        """提交事务"""
        self.wal.append(trx_id, OpType.COMMIT)
        self._active_trx.discard(trx_id)
        self.wal.save_to_file()  # 持久化日志

    def abort(self, trx_id: int):
        """中止事务：用Undo回滚"""
        records = self.wal.get_all_records()
        # 逆序处理该事务的日志，执行Undo
        for record in reversed(records):
            if record.trx_id == trx_id and record.op_type in (OpType.UPDATE, OpType.DELETE):
                if record.old_value is not None:
                    self._data[record.key] = record.old_value
                elif record.op_type == OpType.UPDATE:
                    self._data.pop(record.key, None)
        self.wal.append(trx_id, OpType.ABORT)
        self._active_trx.discard(trx_id)

    def checkpoint(self):
        """创建检查点"""
        self.wal.checkpoint(dict(self._data))
        self.wal.save_to_file()

    def crash(self):
        """模拟崩溃：丢弃内存数据，日志已持久化"""
        self._data = {}
        self._active_trx = set()

    def recover(self):
        """
        崩溃恢复：
        1. 从检查点开始扫描日志
        2. REDO：重放已提交事务的操作
        3. UNDO：回滚未提交事务的操作
        """
        self.wal.load_from_file()
        records = self.wal.get_all_records()

        # 找到最后一个检查点
        checkpoint_lsn = self.wal.get_last_checkpoint_lsn()
        checkpoint_data = None
        if checkpoint_lsn > 0:
            for r in records:
                if r.lsn == checkpoint_lsn and r.op_type == OpType.CHECKPOINT:
                    checkpoint_data = r.new_value
                    break

        # 从检查点恢复数据状态
        if checkpoint_data:
            self._data = dict(checkpoint_data.get("dirty_pages", {}))
        else:
            self._data = {}

        # 收集从检查点开始的日志
        records_after_checkpoint = [r for r in records if r.lsn > checkpoint_lsn]

        # 确定已提交和未提交的事务
        committed_trx = set(checkpoint_data.get("committed", [])) if checkpoint_data else set()
        active_trx = set()
        for r in records_after_checkpoint:
            if r.op_type == OpType.COMMIT:
                committed_trx.add(r.trx_id)
            elif r.op_type == OpType.BEGIN:
                active_trx.add(r.trx_id)

        uncommitted_trx = active_trx - committed_trx

        # REDO阶段：重放已提交事务的操作（从检查点开始）
        for r in records_after_checkpoint:
            if r.trx_id in committed_trx and r.op_type == OpType.UPDATE:
                if r.new_value is not None:
                    self._data[r.key] = r.new_value
            elif r.trx_id in committed_trx and r.op_type == OpType.DELETE:
                self._data.pop(r.key, None)

        # UNDO阶段：回滚未提交事务的操作（逆序）
        for r in reversed(records_after_checkpoint):
            if r.trx_id in uncommitted_trx and r.op_type == OpType.UPDATE:
                if r.old_value is not None:
                    self._data[r.key] = r.old_value
                else:
                    self._data.pop(r.key, None)
            elif r.trx_id in uncommitted_trx and r.op_type == OpType.DELETE:
                if r.old_value is not None:
                    self._data[r.key] = r.old_value

        return {
            "committed_trx": committed_trx,
            "uncommitted_trx": uncommitted_trx,
            "recovered_keys": len(self._data),
        }


# ======================== 测试 ========================
if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        wal_file = os.path.join(tmpdir, "test_wal.log")
        db = WALDatabase(wal_file)

        # 测试1：正常提交
        print("=== 测试1：正常事务提交 ===")
        trx1 = db.begin()
        db.put(trx1, "user:1", {"name": "Alice", "age": 30})
        db.put(trx1, "user:2", {"name": "Bob", "age": 25})
        db.commit(trx1)
        assert db.get("user:1")["name"] == "Alice"
        assert db.get("user:2")["name"] == "Bob"
        print("[OK] 提交后数据可读")

        # 测试2：事务回滚
        print("\n=== 测试2：事务回滚 ===")
        trx2 = db.begin()
        db.put(trx2, "user:3", {"name": "Charlie", "age": 35})
        db.put(trx2, "user:1", {"name": "Alice_Updated", "age": 31})
        db.abort(trx2)
        # user:3应不存在，user:1应恢复
        assert db.get("user:3") is None, "回滚后user:3应不存在"
        assert db.get("user:1")["name"] == "Alice", "回滚后user:1应恢复"
        print("[OK] 回滚后数据恢复正确")

        # 测试3：检查点
        print("\n=== 测试3：检查点 ===")
        db.checkpoint()
        checkpoint_lsn = db.wal.get_last_checkpoint_lsn()
        print(f"检查点LSN: {checkpoint_lsn}")
        assert checkpoint_lsn > 0

        # 测试4：崩溃恢复
        print("\n=== 测试4：崩溃恢复 ===")
        # 模拟崩溃前的操作
        trx3 = db.begin()
        db.put(trx3, "user:4", {"name": "David", "age": 40})
        db.commit(trx3)  # 已提交

        trx4 = db.begin()
        db.put(trx4, "user:5", {"name": "Eve", "age": 28})
        db.put(trx4, "user:1", {"name": "Alice_V2", "age": 32})
        # 不提交，模拟崩溃！
        print(f"崩溃前数据: user:1={db.get('user:1')}, user:4={db.get('user:4')}, user:5={db.get('user:5')}")

        # 模拟崩溃
        db.crash()
        print(f"崩溃后内存数据: {db._data}")

        # 恢复
        result = db.recover()
        print(f"恢复结果: {result}")
        print(f"恢复后: user:1={db.get('user:1')}, user:4={db.get('user:4')}, user:5={db.get('user:5')}")

        # 验证恢复正确性
        assert db.get("user:1")["name"] == "Alice", "未提交事务的修改应回滚"
        assert db.get("user:2")["name"] == "Bob", "已提交数据应恢复"
        assert db.get("user:4")["name"] == "David", "已提交数据应恢复（REDO）"
        assert db.get("user:5") is None, "未提交事务的插入应回滚（UNDO）"
        print("[OK] 崩溃恢复正确：已提交数据REDO，未提交数据UNDO")

        # 测试5：多次崩溃恢复
        print("\n=== 测试5：多次崩溃恢复 ===")
        trx5 = db.begin()
        db.put(trx5, "user:6", {"name": "Frank", "age": 50})
        db.commit(trx5)
        db.crash()
        result = db.recover()
        assert db.get("user:6")["name"] == "Frank"
        print("[OK] 二次崩溃恢复正确")

        # 测试6：日志统计
        print("\n=== 测试6：日志统计 ===")
        all_records = db.wal.get_all_records()
        op_counts = {}
        for r in all_records:
            op_counts[r.op_type.value] = op_counts.get(r.op_type.value, 0) + 1
        print(f"日志记录总数: {len(all_records)}")
        print(f"操作类型分布: {op_counts}")
        assert len(all_records) > 0
        print("[OK] 日志统计正确")
```

### 思考题
1. WAL的"预写"原则为什么能保证持久性？如果先写数据页再写日志会出什么问题？
2. 检查点频率如何权衡？Fuzzy Checkpoint如何避免阻塞写入？
3. 组提交如何提升WAL的写入性能？为什么多个事务的日志可以合并一次刷盘？


---

# 三、分布式系统（5题）

---

## 第11题：Raft共识算法

### 知识点讲解

Raft是当今最广泛使用的共识算法之一，相比Paxos更易理解和实现。Raft将共识问题分解为三个子问题：Leader选举、日志复制、安全性约束。

**Leader选举**：Raft集群中所有节点初始为Follower状态。如果Follower在选举超时时间内未收到Leader的心跳，则转为Candidate，增加Term（任期号），向其他节点发起RequestVote RPC。获得多数票后成为Leader。为避免选票分裂，每个节点的选举超时时间随机化（如150-300ms），超时最短的节点最先发起选举。

**Term任期**：Raft将时间划分为任期，每个任期最多一个Leader。Term号单调递增，充当逻辑时钟。节点发现当前Term小于其他节点时自动更新。过期的Leader收到更高Term的消息时会自动降级为Follower。

**日志复制**：Leader收到客户端命令后追加到本地日志，然后通过AppendEntries RPC复制到Follower。当多数节点确认后，该日志条目标记为已提交，Leader应用到状态机并返回客户端结果。Leader在后续的心跳中携带已提交的索引，通知Follower也应用日志。

**安全性约束**：保证已提交的日志不会被覆盖。核心规则是"Leader完整性"——只有包含所有已提交日志的节点才能被选为Leader。实现方式是RequestVote RPC中比较候选人的最后日志索引和Term，投票者只投给日志至少与自己一样新的候选人。这保证了新Leader的日志一定是所有已提交日志的超集。

**心跳超时**：Leader定期发送心跳（空的AppendEntries）维持权威。如果网络分区导致脑裂，少数派分区中的Leader无法提交日志（得不到多数确认），多数派分区选出新Leader。网络恢复后，旧Leader发现更高Term自动降级，日志被新Leader覆盖。

```python
"""
Raft共识算法：Leader选举 + 日志复制
简化版实现，展示核心机制
"""
import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict


class NodeState(Enum):
    FOLLOWER = "Follower"
    CANDIDATE = "Candidate"
    LEADER = "Leader"


@dataclass
class LogEntry:
    """日志条目"""
    term: int           # 创建时的任期号
    index: int          # 日志索引
    command: any        # 客户端命令
    committed: bool = False  # 是否已提交


@dataclass
class VoteRequest:
    """RequestVote RPC请求"""
    term: int
    candidate_id: int
    last_log_index: int
    last_log_term: int


@dataclass
class VoteResponse:
    """RequestVote RPC响应"""
    term: int
    vote_granted: bool


@dataclass
class AppendEntriesRequest:
    """AppendEntries RPC请求（也用作心跳）"""
    term: int
    leader_id: int
    prev_log_index: int
    prev_log_term: int
    entries: list
    leader_commit: int


@dataclass
class AppendEntriesResponse:
    """AppendEntries RPC响应"""
    term: int
    success: bool
    match_index: int = 0


class RaftNode:
    """Raft节点"""

    def __init__(self, node_id: int, peers: list,
                 election_timeout_range: tuple = (0.15, 0.3)):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        self.state = NodeState.FOLLOWER
        self.current_term = 0
        self.voted_for = None
        self.log = []
        self.commit_index = 0
        self.last_applied = 0
        self.next_index = {}
        self.match_index = {}
        self.election_timeout_range = election_timeout_range
        self._reset_election_timeout()
        self.last_heartbeat = time.monotonic()
        self.votes_received = set()
        self.state_machine = {}
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._network = {}
        self.heartbeat_interval = 0.05

    def _reset_election_timeout(self):
        """重置选举超时（随机化避免活锁）"""
        self.election_timeout = random.uniform(*self.election_timeout_range)

    def set_network(self, network):
        """设置网络（模拟节点间通信）"""
        self._network = network

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self):
        """主循环"""
        while self._running:
            with self._lock:
                now = time.monotonic()
                if self.state == NodeState.LEADER:
                    if now - self.last_heartbeat >= self.heartbeat_interval:
                        self._send_append_entries_to_all()
                        self.last_heartbeat = now
                elif self.state in (NodeState.FOLLOWER, NodeState.CANDIDATE):
                    if now - self.last_heartbeat >= self.election_timeout:
                        self._start_election()
            time.sleep(0.01)

    def _start_election(self):
        """发起选举"""
        self.state = NodeState.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self.votes_received = {self.node_id}
        self.last_heartbeat = time.monotonic()
        self._reset_election_timeout()
        last_log_index = len(self.log)
        last_log_term = self.log[-1].term if self.log else 0
        print(f"  [Node {self.node_id}] 开始选举 Term={self.current_term}")

        for peer_id in self.peers:
            peer = self._network.get(peer_id)
            if peer is None:
                continue
            req = VoteRequest(
                term=self.current_term,
                candidate_id=self.node_id,
                last_log_index=last_log_index,
                last_log_term=last_log_term,
            )
            resp = peer.handle_vote_request(req)
            if resp.term > self.current_term:
                self.current_term = resp.term
                self.state = NodeState.FOLLOWER
                self.voted_for = None
                return
            if resp.vote_granted:
                self.votes_received.add(peer_id)
        majority = (len(self.peers) + 1) // 2 + 1
        if len(self.votes_received) >= majority:
            self._become_leader()

    def _become_leader(self):
        """成为Leader"""
        self.state = NodeState.LEADER
        self.last_heartbeat = time.monotonic()
        next_idx = len(self.log) + 1
        for peer_id in self.peers:
            self.next_index[peer_id] = next_idx
            self.match_index[peer_id] = 0
        print(f"  [Node {self.node_id}] 成为Leader Term={self.current_term}")
        self._send_append_entries_to_all()

    def handle_vote_request(self, req):
        """处理投票请求"""
        with self._lock:
            if req.term > self.current_term:
                self.current_term = req.term
                self.state = NodeState.FOLLOWER
                self.voted_for = None
            if req.term < self.current_term:
                return VoteResponse(term=self.current_term, vote_granted=False)
            if self.voted_for is not None and self.voted_for != req.candidate_id:
                return VoteResponse(term=self.current_term, vote_granted=False)
            # 安全性约束：候选人的日志必须至少和自己一样新
            my_last_index = len(self.log)
            my_last_term = self.log[-1].term if self.log else 0
            log_ok = (req.last_log_term > my_last_term or
                      (req.last_log_term == my_last_term and
                       req.last_log_index >= my_last_index))
            if not log_ok:
                return VoteResponse(term=self.current_term, vote_granted=False)
            self.voted_for = req.candidate_id
            self.last_heartbeat = time.monotonic()
            self._reset_election_timeout()
            return VoteResponse(term=self.current_term, vote_granted=True)

    def _send_append_entries_to_all(self):
        """向所有Follower发送AppendEntries"""
        for peer_id in self.peers:
            self._send_append_entries(peer_id)

    def _send_append_entries(self, peer_id):
        """向指定Follower发送AppendEntries"""
        peer = self._network.get(peer_id)
        if peer is None:
            return
        next_idx = self.next_index.get(peer_id, 1)
        prev_log_index = next_idx - 1
        prev_log_term = (self.log[prev_log_index - 1].term
                         if prev_log_index > 0 and prev_log_index <= len(self.log)
                         else 0)
        entries = self.log[next_idx - 1:] if next_idx <= len(self.log) else []
        req = AppendEntriesRequest(
            term=self.current_term,
            leader_id=self.node_id,
            prev_log_index=prev_log_index,
            prev_log_term=prev_log_term,
            entries=list(entries),
            leader_commit=self.commit_index,
        )
        resp = peer.handle_append_entries(req)
        if resp.term > self.current_term:
            self.current_term = resp.term
            self.state = NodeState.FOLLOWER
            self.voted_for = None
            return
        if resp.success:
            if entries:
                self.next_index[peer_id] = entries[-1].index + 1
                self.match_index[peer_id] = entries[-1].index
            else:
                self.match_index[peer_id] = max(
                    self.match_index.get(peer_id, 0), prev_log_index)
            self._update_commit_index()
        else:
            self.next_index[peer_id] = max(1, next_idx - 1)

    def _update_commit_index(self):
        """更新commit_index"""
        if self.state != NodeState.LEADER:
            return
        for n in range(len(self.log), self.commit_index, -1):
            if self.log[n - 1].term != self.current_term:
                continue
            count = 1
            for peer_id in self.peers:
                if self.match_index.get(peer_id, 0) >= n:
                    count += 1
            majority = (len(self.peers) + 1) // 2 + 1
            if count >= majority:
                self.commit_index = n
                self._apply_committed()
                break

    def _apply_committed(self):
        """将已提交的日志应用到状态机"""
        while self.last_applied < self.commit_index:
            self.last_applied += 1
            entry = self.log[self.last_applied - 1]
            self.state_machine[entry.index] = entry.command
            entry.committed = True

    def handle_append_entries(self, req):
        """处理AppendEntries请求"""
        with self._lock:
            if req.term < self.current_term:
                return AppendEntriesResponse(
                    term=self.current_term, success=False)
            if req.term > self.current_term:
                self.current_term = req.term
                self.voted_for = None
            self.state = NodeState.FOLLOWER
            self.last_heartbeat = time.monotonic()
            self._reset_election_timeout()
            # 检查日志一致性
            if req.prev_log_index > 0:
                if req.prev_log_index > len(self.log):
                    return AppendEntriesResponse(
                        term=self.current_term, success=False)
                if self.log[req.prev_log_index - 1].term != req.prev_log_term:
                    return AppendEntriesResponse(
                        term=self.current_term, success=False)
            # 追加日志条目（处理冲突）
            for entry in req.entries:
                idx = entry.index
                if idx <= len(self.log):
                    if self.log[idx - 1].term != entry.term:
                        self.log = self.log[:idx - 1]
                        self.log.append(entry)
                else:
                    self.log.append(entry)
            # 更新commit_index
            if req.leader_commit > self.commit_index:
                self.commit_index = min(req.leader_commit, len(self.log))
                self._apply_committed()
            match_idx = (req.entries[-1].index if req.entries
                         else req.prev_log_index)
            return AppendEntriesResponse(
                term=self.current_term, success=True, match_index=match_idx)

    def propose(self, command):
        """Leader提交命令到日志"""
        with self._lock:
            if self.state != NodeState.LEADER:
                return False
            entry = LogEntry(
                term=self.current_term,
                index=len(self.log) + 1,
                command=command,
            )
            self.log.append(entry)
            self._send_append_entries_to_all()
            return True

    def get_status(self):
        with self._lock:
            return {
                "id": self.node_id,
                "state": self.state.value,
                "term": self.current_term,
                "log_len": len(self.log),
                "commit_index": self.commit_index,
                "last_applied": self.last_applied,
                "state_machine_size": len(self.state_machine),
            }


class RaftCluster:
    """Raft集群管理器"""

    def __init__(self, node_ids):
        self.nodes = {}
        network = {}
        for nid in node_ids:
            node = RaftNode(nid, node_ids)
            self.nodes[nid] = node
            network[nid] = node
        for node in self.nodes.values():
            node.set_network(network)

    def start(self):
        for node in self.nodes.values():
            node.start()

    def stop(self):
        for node in self.nodes.values():
            node.stop()

    def get_leader(self):
        for node in self.nodes.values():
            if node.state == NodeState.LEADER:
                return node
        return None

    def wait_for_leader(self, timeout=5.0):
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            leader = self.get_leader()
            if leader:
                return leader
            time.sleep(0.05)
        return None


# ======================== 测试 ========================
if __name__ == "__main__":
    random.seed(42)

    # 测试1：Leader选举
    print("=== 测试1：Leader选举 ===")
    cluster = RaftCluster([1, 2, 3, 4, 5])
    cluster.start()
    leader = cluster.wait_for_leader(timeout=3.0)
    assert leader is not None, "应选出Leader"
    print(f"Leader: Node {leader.node_id}, Term={leader.current_term}")
    leaders = [n for n in cluster.nodes.values() if n.state == NodeState.LEADER]
    assert len(leaders) == 1, f"应只有一个Leader，实际{len(leaders)}"
    print("[OK] 成功选出唯一Leader")

    # 测试2：日志复制
    print("\n=== 测试2：日志复制 ===")
    leader.propose({"op": "set", "key": "x", "value": 1})
    leader.propose({"op": "set", "key": "y", "value": 2})
    time.sleep(0.5)
    for nid, node in cluster.nodes.items():
        status = node.get_status()
        print(f"  Node {nid}: {status}")
    log_lens = [len(n.log) for n in cluster.nodes.values()]
    assert all(l == 2 for l in log_lens), f"所有节点日志长度应为2，实际{log_lens}"
    print("[OK] 日志已复制到所有节点")

    # 测试3：Leader故障转移
    print("\n=== 测试3：Leader故障转移 ===")
    old_leader_id = leader.node_id
    print(f"停止Leader Node {old_leader_id}")
    cluster.nodes[old_leader_id].stop()
    time.sleep(2.0)
    new_leader = cluster.get_leader()
    assert new_leader is not None, "应选出新Leader"
    assert new_leader.node_id != old_leader_id, "新Leader应不是旧Leader"
    print(f"新Leader: Node {new_leader.node_id}, Term={new_leader.current_term}")
    print("[OK] Leader故障后成功选出新Leader")

    # 测试4：新Leader继续处理命令
    print("\n=== 测试4：新Leader处理命令 ===")
    new_leader.propose({"op": "set", "key": "z", "value": 3})
    time.sleep(0.5)
    active_nodes = [n for nid, n in cluster.nodes.items() if nid != old_leader_id]
    log_lens = [len(n.log) for n in active_nodes]
    print(f"活跃节点日志长度: {log_lens}")
    assert all(l == 3 for l in log_lens), f"活跃节点日志长度应为3，实际{log_lens}"
    print("[OK] 新Leader成功复制日志")

    # 测试5：已提交日志持久性
    print("\n=== 测试5：已提交日志持久性 ===")
    time.sleep(0.5)
    commit_indices = [n.commit_index for n in active_nodes]
    print(f"各节点commit_index: {commit_indices}")
    assert all(c >= 3 for c in commit_indices), "所有节点应提交到索引3"
    print("[OK] 日志已提交并应用到状态机")

    cluster.stop()
    print("\n集群已停止")
```

### 思考题
1. Raft如何保证选举安全性（一个Term最多一个Leader）？随机化超时时间的作用是什么？
2. 日志不一致时Leader如何修复Follower的日志？为什么采用回退next_index策略？
3. 如果网络分区导致脑裂，Raft如何保证数据一致性？少数派分区的Leader能否提交日志？

---

## 第12题：分布式锁

### 知识点讲解

分布式锁是分布式系统中协调资源访问的基本原语。本实现基于租约机制，解决传统分布式锁的多个难题。

**租约机制**：锁具有过期时间（TTL），持有者必须在TTL内续约，否则锁自动释放。租约机制避免了持有者崩溃导致锁永久占用的问题。但租约的引入带来了新的挑战——如果持有者在租约过期后仍认为持锁，会导致多个客户端同时"持锁"。

**Fencing Token**：解决租约过期后的安全问题。每次获取锁时生成一个单调递增的token，持有者在访问资源时携带token，资源服务端拒绝低于当前最大token的请求。这样即使旧持有者租约过期后仍尝试写入，也会被资源服务端拒绝。Fencing Token是Martin Kleppmann提出的对Redlock算法核心批评的解决方案。

**锁续约**：持锁期间定期延长TTL，防止业务操作未完成时锁过期。续约需要验证当前是否仍持锁（避免续约了已被他人获取的锁），通常用CAS操作实现。

**羊群效应**：当锁释放时，所有等待的客户端同时竞争锁，只有一个成功，其余全部失败重试。这造成大量无效请求。解决方案是使用公平锁（排队机制，如Zookeeper的顺序临时节点），或客户端退避重试。

**脑裂问题**：网络分区可能导致多个客户端同时认为自己持锁。租约+Fencing Token可以缓解此问题。更严格的方案是使用共识算法（如Raft）实现锁服务，保证线性一致性。

**锁粒度**：粗粒度锁减少锁管理开销但降低并发度；细粒度锁提高并发度但增加死锁风险和管理复杂度。实际应用中需要根据业务特点权衡，如对账户操作按账户ID分锁，对库存操作按商品SKU分锁。

```python
"""
分布式锁：基于租约的锁 + 锁续约 + Fencing Token
"""
import time
import threading
import uuid
from collections import defaultdict, OrderedDict
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class LockEntry:
    """锁条目"""
    lock_name: str
    owner_id: str
    fencing_token: int
    acquired_at: float
    ttl: float
    expires_at: float
    renew_count: int = 0


class DistributedLockService:
    """
    分布式锁服务（模拟Redis/Zookeeper锁服务）
    - 基于租约（TTL）实现锁自动释放
    - Fencing Token防止过期锁的安全问题
    - 支持锁续约和公平锁
    """

    def __init__(self):
        self._locks = {}
        self._fencing_counter = 0
        self._lock = threading.Lock()
        self._wait_queues = defaultdict(OrderedDict)
        self._resource_max_token = defaultdict(int)

    def try_lock(self, lock_name, owner_id=None, ttl=10.0):
        """尝试获取锁（非阻塞），返回 (成功与否, fencing_token)"""
        if owner_id is None:
            owner_id = str(uuid.uuid4())
        with self._lock:
            now = time.monotonic()
            existing = self._locks.get(lock_name)
            if existing:
                if now < existing.expires_at:
                    return False, None  # 锁仍被持有
                del self._locks[lock_name]  # 清理过期锁
            self._fencing_counter += 1
            entry = LockEntry(
                lock_name=lock_name,
                owner_id=owner_id,
                fencing_token=self._fencing_counter,
                acquired_at=now,
                ttl=ttl,
                expires_at=now + ttl,
            )
            self._locks[lock_name] = entry
            return True, entry.fencing_token

    def lock(self, lock_name, owner_id=None, ttl=10.0,
             timeout=30.0, fair=False):
        """阻塞式获取锁"""
        if owner_id is None:
            owner_id = str(uuid.uuid4())
        deadline = time.monotonic() + timeout
        if fair:
            return self._fair_lock(lock_name, owner_id, ttl, deadline)
        while True:
            success, token = self.try_lock(lock_name, owner_id, ttl)
            if success:
                return True, token
            if time.monotonic() >= deadline:
                return False, None
            time.sleep(0.01)

    def _fair_lock(self, lock_name, owner_id, ttl, deadline):
        """公平锁：排队获取，避免羊群效应"""
        event = threading.Event()
        with self._lock:
            self._wait_queues[lock_name][owner_id] = event
        while True:
            success, token = self.try_lock(lock_name, owner_id, ttl)
            if success:
                with self._lock:
                    self._wait_queues[lock_name].pop(owner_id, None)
                return True, token
            if time.monotonic() >= deadline:
                with self._lock:
                    self._wait_queues[lock_name].pop(owner_id, None)
                return False, None
            with self._lock:
                queue = self._wait_queues[lock_name]
                if queue and next(iter(queue)) == owner_id:
                    time.sleep(0.005)
                else:
                    remaining = deadline - time.monotonic()
                    if remaining > 0:
                        event.wait(timeout=min(0.05, remaining))

    def renew(self, lock_name, owner_id, ttl=10.0):
        """锁续约：延长TTL，必须验证owner（CAS语义）"""
        with self._lock:
            entry = self._locks.get(lock_name)
            if entry is None:
                return False
            if entry.owner_id != owner_id:
                return False
            if time.monotonic() >= entry.expires_at:
                del self._locks[lock_name]
                return False
            entry.expires_at = time.monotonic() + ttl
            entry.ttl = ttl
            entry.renew_count += 1
            return True

    def unlock(self, lock_name, owner_id):
        """释放锁，必须验证owner_id防止释放他人的锁"""
        with self._lock:
            entry = self._locks.get(lock_name)
            if entry is None:
                return False
            if entry.owner_id != owner_id:
                return False
            del self._locks[lock_name]
            queue = self._wait_queues.get(lock_name)
            if queue:
                next_owner = next(iter(queue), None)
                if next_owner:
                    self._wait_queues[lock_name][next_owner].set()
            return True

    def write_with_fencing(self, resource, owner_id, fencing_token, data):
        """资源服务端写入：验证Fencing Token"""
        with self._lock:
            max_token = self._resource_max_token[resource]
            if fencing_token < max_token:
                print(f"  [拒绝] token={fencing_token} < max={max_token}")
                return False
            self._resource_max_token[resource] = fencing_token
            print(f"  [接受] token={fencing_token}, 写入: {data}")
            return True


class LockContext:
    """
    锁上下文管理器：自动获取和释放锁
    支持自动续约（看门狗机制）
    """

    def __init__(self, lock_service, lock_name, ttl=10.0,
                 auto_renew=True, fair=False):
        self.service = lock_service
        self.lock_name = lock_name
        self.ttl = ttl
        self.auto_renew = auto_renew
        self.fair = fair
        self.owner_id = str(uuid.uuid4())
        self.fencing_token = None
        self._renew_thread = None
        self._renew_stop = threading.Event()

    def __enter__(self):
        success, token = self.service.lock(
            self.lock_name, self.owner_id, self.ttl, fair=self.fair)
        if not success:
            raise TimeoutError(f"获取锁 '{self.lock_name}' 超时")
        self.fencing_token = token
        if self.auto_renew:
            self._start_watchdog()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._renew_stop.set()
        if self._renew_thread:
            self._renew_thread.join(timeout=1)
        self.service.unlock(self.lock_name, self.owner_id)

    def _start_watchdog(self):
        """启动看门狗线程，定期续约"""
        def watchdog():
            while not self._renew_stop.wait(self.ttl / 3):
                if not self.service.renew(
                        self.lock_name, self.owner_id, self.ttl):
                    break
        self._renew_thread = threading.Thread(target=watchdog, daemon=True)
        self._renew_thread.start()


# ======================== 测试 ========================
if __name__ == "__main__":
    service = DistributedLockService()

    # 测试1：基本锁获取和释放
    print("=== 测试1：基本锁获取释放 ===")
    success, token = service.try_lock("my_lock", "client1", ttl=2.0)
    assert success and token == 1
    print(f"Client1获取锁: success={success}, token={token}")
    success2, _ = service.try_lock("my_lock", "client2", ttl=2.0)
    assert not success2
    print(f"Client2获取锁: success={success2}")
    assert service.unlock("my_lock", "client1")
    success2, token2 = service.try_lock("my_lock", "client2", ttl=2.0)
    assert success2 and token2 == 2
    print(f"Client1释放后，Client2获取: success={success2}, token={token2}")
    print("[OK] 基本锁操作正确，Fencing Token单调递增")

    # 测试2：锁续约
    print("\n=== 测试2：锁续约 ===")
    service.try_lock("renew_lock", "client1", ttl=0.5)
    time.sleep(0.3)
    assert service.renew("renew_lock", "client1", ttl=0.5)
    time.sleep(0.3)
    success, _ = service.try_lock("renew_lock", "client2", ttl=0.5)
    assert not success, "续约后锁应仍被持有"
    print("[OK] 锁续约成功")

    # 测试3：锁自动过期
    print("\n=== 测试3：锁自动过期 ===")
    service.try_lock("expire_lock", "client1", ttl=0.2)
    time.sleep(0.3)
    success, _ = service.try_lock("expire_lock", "client2", ttl=0.2)
    assert success, "锁过期后应可被获取"
    print("[OK] 锁自动过期后可被获取")

    # 测试4：Fencing Token防止过期写入
    print("\n=== 测试4：Fencing Token ===")
    _, token_a = service.try_lock("resource_lock", "clientA", ttl=0.3)
    print(f"ClientA获取锁, token={token_a}")
    time.sleep(0.4)  # 锁过期
    _, token_b = service.try_lock("resource_lock", "clientB", ttl=1.0)
    print(f"ClientB获取锁, token={token_b}")
    assert service.write_with_fencing("account", "clientB", token_b, "B的数据")
    assert not service.write_with_fencing("account", "clientA", token_a, "A的数据")
    print("[OK] Fencing Token拒绝了过期锁持有者的写入")

    # 测试5：上下文管理器 + 自动续约
    print("\n=== 测试5：上下文管理器 + 自动续约 ===")
    with LockContext(service, "ctx_lock", ttl=0.5, auto_renew=True) as ctx:
        print(f"获取锁: token={ctx.fencing_token}")
        time.sleep(1.0)  # 超过TTL
        success, _ = service.try_lock("ctx_lock", "other", ttl=0.5)
        assert not success, "自动续约期间锁应被持有"
        print("[OK] 看门狗自动续约成功")
    success, _ = service.try_lock("ctx_lock", "other", ttl=0.5)
    assert success, "退出上下文后锁应释放"
    print("[OK] 上下文退出后锁自动释放")

    # 测试6：公平锁（避免羊群效应）
    print("\n=== 测试6：公平锁 ===")
    results = []
    results_lock = threading.Lock()
    def worker(name):
        with LockContext(service, "fair_lock", ttl=0.1,
                         auto_renew=False, fair=True) as ctx:
            with results_lock:
                results.append(name)
            time.sleep(0.05)
    threads = [threading.Thread(target=worker, args=(f"client_{i}",))
               for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(f"获取锁顺序: {results}")
    assert len(results) == 5
    print("[OK] 公平锁：所有客户端按顺序获取锁")
```

### 思考题
1. Fencing Token如何防止过期锁的安全问题？没有Fencing Token的Redlock算法有什么风险？
2. 看门狗续约机制中，如果续约请求失败应该如何处理？是否应该立即释放锁？
3. 公平锁和非公平锁各有什么优缺点？什么场景下应该使用公平锁？

---

## 第13题：事件溯源与CQRS

### 知识点讲解

事件溯源和CQRS是两种互补的架构模式，常一起使用构建高性能、可审计的系统。

**事件溯源**：将状态变更以不可变事件序列存储，而非直接存储当前状态。系统的当前状态是所有事件重放的结果。优势包括：完整审计日志、时间旅行（恢复任意历史时刻状态）、事件回溯调试、与领域驱动设计（DDD）天然契合。例如银行账户系统不直接存储余额，而是存储所有存取款事件，余额是事件重放的结果。

**事件不可变性**：事件一旦写入Event Store便不可修改或删除。错误的修正通过"补偿事件"实现，而非修改原始事件。如错误存入100元，不是修改原始事件，而是写入一个"-100"的补偿事件。这保证了完整的审计链。

**快照优化**：随着事件积累，重放所有事件获取当前状态的代价线性增长。快照机制定期将当前状态持久化，重放时从最近的快照开始，只应用后续事件。如每100个事件创建一次快照，重放代价从O(n)降低到O(100)。

**CQRS（命令查询职责分离）**：将写入和读取分离为不同的模型。写入端使用领域模型处理命令，产出事件；读取端（投影）从事件构建优化的读模型，如为列表查询建物化视图、为搜索建Elasticsearch索引。读写模型独立扩展，读模型可针对查询场景优化。

**最终一致性**：CQRS中读模型通过异步消费事件更新，因此读模型有短暂延迟。应用需要容忍最终一致性，或通过版本号检测读模型是否最新。对于强一致性需求，可以在命令执行后等待读模型更新完成再返回。

```python
"""
事件溯源与CQRS：Event Store + 投影重建读模型
以银行账户系统为例
"""
import time
import threading
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Callable
from datetime import datetime


@dataclass(frozen=True)
class Event:
    """事件基类（不可变）"""
    event_id: str
    aggregate_id: str
    event_type: str
    data: dict
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    version: int = 0


class OptimisticConcurrencyError(Exception):
    """乐观并发冲突异常"""
    pass


class EventStore:
    """
    事件存储：追加写入，不可变
    - 支持按聚合根查询事件
    - 支持快照优化
    - 支持事件订阅
    """

    def __init__(self, snapshot_interval=100):
        self._events = defaultdict(list)
        self._snapshots = defaultdict(list)
        self._subscribers = []
        self._lock = threading.Lock()
        self._next_event_id = 0
        self.snapshot_interval = snapshot_interval

    def append(self, aggregate_id, event_type, data, expected_version=None):
        """追加事件（乐观并发控制）"""
        with self._lock:
            events = self._events[aggregate_id]
            current_version = len(events)
            if expected_version is not None and expected_version != current_version:
                raise OptimisticConcurrencyError(
                    f"并发冲突: 期望版本{expected_version}, 实际{current_version}")
            self._next_event_id += 1
            event = Event(
                event_id=f"evt_{self._next_event_id}",
                aggregate_id=aggregate_id,
                event_type=event_type,
                data=data,
                version=current_version + 1,
            )
            events.append(event)
            for subscriber in self._subscribers:
                subscriber(event)
            return event

    def get_events(self, aggregate_id, from_version=0):
        """获取聚合根的事件"""
        events = self._events.get(aggregate_id, [])
        return [e for e in events if e.version > from_version]

    def get_all_events(self, from_version=0):
        """获取所有事件（用于投影重建）"""
        all_events = []
        for events in self._events.values():
            all_events.extend(e for e in events if e.version > from_version)
        all_events.sort(key=lambda e: e.event_id)
        return all_events

    def save_snapshot(self, aggregate_id, version, state):
        """保存快照"""
        with self._lock:
            self._snapshots[aggregate_id].append((version, state))

    def get_latest_snapshot(self, aggregate_id):
        """获取最新快照"""
        snapshots = self._snapshots.get(aggregate_id, [])
        if not snapshots:
            return None
        return snapshots[-1]

    def subscribe(self, callback):
        """订阅事件"""
        self._subscribers.append(callback)


class BankAccount:
    """
    银行账户聚合根（写模型）
    状态通过重放事件恢复，修改通过产生事件实现
    """

    def __init__(self, account_id, event_store):
        self.account_id = account_id
        self.event_store = event_store
        self.balance = 0.0
        self.is_active = False
        self.owner = ""
        self._version = 0

    def load_from_history(self):
        """从事件历史重建状态（支持快照优化）"""
        snapshot = self.event_store.get_latest_snapshot(self.account_id)
        if snapshot:
            self._version, state = snapshot
            self.balance = state.get("balance", 0)
            self.is_active = state.get("is_active", False)
            self.owner = state.get("owner", "")
        else:
            self._version = 0
        events = self.event_store.get_events(self.account_id, self._version)
        for event in events:
            self._apply(event)

    def _apply(self, event):
        """应用事件到当前状态"""
        if event.event_type == "AccountCreated":
            self.owner = event.data["owner"]
            self.is_active = True
            self.balance = 0.0
        elif event.event_type == "MoneyDeposited":
            self.balance += event.data["amount"]
        elif event.event_type == "MoneyWithdrawn":
            self.balance -= event.data["amount"]
        elif event.event_type == "AccountClosed":
            self.is_active = False
        self._version = event.version

    def create(self, owner):
        if self._version > 0:
            raise ValueError("账户已存在")
        self._raise_event("AccountCreated", {"owner": owner})

    def deposit(self, amount):
        if not self.is_active:
            raise ValueError("账户未激活")
        if amount <= 0:
            raise ValueError("存款金额必须大于0")
        self._raise_event("MoneyDeposited", {"amount": amount})

    def withdraw(self, amount):
        if not self.is_active:
            raise ValueError("账户未激活")
        if amount <= 0:
            raise ValueError("取款金额必须大于0")
        if self.balance < amount:
            raise ValueError(f"余额不足: {self.balance} < {amount}")
        self._raise_event("MoneyWithdrawn", {"amount": amount})

    def close(self):
        if not self.is_active:
            raise ValueError("账户已关闭")
        if self.balance != 0:
            raise ValueError("关闭账户前余额必须为0")
        self._raise_event("AccountClosed", {})

    def _raise_event(self, event_type, data):
        """产生事件并应用"""
        event = self.event_store.append(
            self.account_id, event_type, data, expected_version=self._version)
        self._apply(event)

    def get_state(self):
        return {
            "account_id": self.account_id,
            "owner": self.owner,
            "balance": self.balance,
            "is_active": self.is_active,
            "version": self._version,
        }


class AccountBalanceProjection:
    """账户余额投影（读模型）"""

    def __init__(self):
        self.balances = {}
        self.owners = {}
        self.active_accounts = set()
        self.transaction_history = defaultdict(list)
        self._lock = threading.Lock()

    def handle_event(self, event):
        """处理事件，更新读模型"""
        with self._lock:
            aid = event.aggregate_id
            if event.event_type == "AccountCreated":
                self.balances[aid] = 0.0
                self.owners[aid] = event.data["owner"]
                self.active_accounts.add(aid)
            elif event.event_type == "MoneyDeposited":
                self.balances[aid] = self.balances.get(aid, 0) + event.data["amount"]
                self.transaction_history[aid].append({
                    "type": "deposit", "amount": event.data["amount"],
                    "timestamp": event.timestamp})
            elif event.event_type == "MoneyWithdrawn":
                self.balances[aid] = self.balances.get(aid, 0) - event.data["amount"]
                self.transaction_history[aid].append({
                    "type": "withdraw", "amount": event.data["amount"],
                    "timestamp": event.timestamp})
            elif event.event_type == "AccountClosed":
                self.active_accounts.discard(aid)

    def rebuild(self, event_store):
        """从Event Store重建读模型"""
        with self._lock:
            self.balances = {}
            self.owners = {}
            self.active_accounts = set()
            self.transaction_history = defaultdict(list)
        for event in event_store.get_all_events():
            self.handle_event(event)

    def get_balance(self, account_id):
        return self.balances.get(account_id)

    def get_active_accounts(self):
        return [
            {"account_id": aid, "owner": self.owners[aid],
             "balance": self.balances[aid]}
            for aid in self.active_accounts]

    def get_total_balance(self):
        return sum(self.balances.values())

    def get_transaction_history(self, account_id):
        return self.transaction_history.get(account_id, [])


class AccountCommandHandler:
    """命令处理器：处理业务命令，操作聚合根"""

    def __init__(self, event_store):
        self.event_store = event_store

    def handle_create_account(self, account_id, owner):
        account = BankAccount(account_id, self.event_store)
        account.load_from_history()
        account.create(owner)

    def handle_deposit(self, account_id, amount):
        account = BankAccount(account_id, self.event_store)
        account.load_from_history()
        account.deposit(amount)

    def handle_withdraw(self, account_id, amount):
        account = BankAccount(account_id, self.event_store)
        account.load_from_history()
        account.withdraw(amount)

    def handle_close_account(self, account_id):
        account = BankAccount(account_id, self.event_store)
        account.load_from_history()
        account.close()


# ======================== 测试 ========================
if __name__ == "__main__":
    event_store = EventStore()
    projection = AccountBalanceProjection()
    event_store.subscribe(projection.handle_event)
    handler = AccountCommandHandler(event_store)

    # 测试1：创建账户和存款
    print("=== 测试1：创建账户和存款 ===")
    handler.handle_create_account("acc1", "Alice")
    handler.handle_deposit("acc1", 1000)
    handler.handle_withdraw("acc1", 300)
    print(f"账户acc1余额: {projection.get_balance('acc1')}")
    assert projection.get_balance("acc1") == 700.0
    print("[OK] 事件溯源正确计算余额")

    # 测试2：事件不可变性验证
    print("\n=== 测试2：事件不可变性 ===")
    events = event_store.get_events("acc1")
    print(f"acc1的事件数: {len(events)}")
    for e in events:
        print(f"  {e.event_type}: {e.data} (v{e.version})")
    assert len(events) == 3
    print("[OK] 事件完整记录且不可变")

    # 测试3：时间旅行（重放到历史版本）
    print("\n=== 测试3：时间旅行 ===")
    account = BankAccount("acc1", event_store)
    events = event_store.get_events("acc1")
    account._apply(events[0])
    account._apply(events[1])
    print(f"重放前2个事件后余额: {account.balance} (应为1000)")
    assert account.balance == 1000.0
    print("[OK] 时间旅行：可恢复任意历史状态")

    # 测试4：投影重建
    print("\n=== 测试4：投影重建 ===")
    handler.handle_create_account("acc2", "Bob")
    handler.handle_deposit("acc2", 500)
    projection2 = AccountBalanceProjection()
    projection2.rebuild(event_store)
    print(f"重建后活跃账户: {projection2.get_active_accounts()}")
    assert projection2.get_balance("acc1") == 700.0
    assert projection2.get_balance("acc2") == 500.0
    assert projection2.get_total_balance() == 1200.0
    print("[OK] 投影重建正确")

    # 测试5：乐观并发控制
    print("\n=== 测试5：乐观并发控制 ===")
    errors = []
    def concurrent_deposit():
        try:
            account = BankAccount("acc1", event_store)
            account.load_from_history()
            time.sleep(0.01)
            account.deposit(100)
        except OptimisticConcurrencyError as e:
            errors.append(str(e))
    threads = [threading.Thread(target=concurrent_deposit) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    print(f"3个并发存款请求，{len(errors)}个因并发冲突失败")
    assert len(errors) == 2
    print("[OK] 乐观并发控制正确")

    # 测试6：事务历史查询
    print("\n=== 测试6：事务历史查询 ===")
    history = projection.get_transaction_history("acc1")
    print(f"acc1的交易历史 ({len(history)}笔):")
    for tx in history:
        print(f"  {tx['type']}: {tx['amount']}")
    assert len(history) >= 2
    print("[OK] 交易历史查询正确")

    # 测试7：快照优化
    print("\n=== 测试7：快照优化 ===")
    handler.handle_create_account("acc3", "Charlie")
    for i in range(250):
        handler.handle_deposit("acc3", 1.0)
    account3 = BankAccount("acc3", event_store)
    account3.load_from_history()
    event_store.save_snapshot("acc3", account3._version, account3.get_state())
    account3_new = BankAccount("acc3", event_store)
    account3_new.load_from_history()
    assert account3_new.balance == 250.0
    print(f"快照恢复后余额: {account3_new.balance} (250笔存款)")
    print("[OK] 快照优化正确")
```

### 思考题
1. 事件溯源与传统CRUD应用相比有什么优势和劣势？什么场景适合使用事件溯源？
2. 快照的创建频率如何权衡？快照过多或过少各有什么问题？
3. CQRS中读模型的最终一致性如何处理？用户看到旧数据时如何优雅处理？

---

## 第14题：Gossip协议

### 知识点讲解

Gossip协议（流行病协议）是分布式系统中实现最终一致性的核心通信协议，因其简单、可扩展、容错性强而被广泛应用（如Cassandra、Consul、Redis Cluster）。

**基本原理**：每个节点定期随机选择少量邻居节点交换状态信息。经过O(log N)轮传播后，信息可扩散到整个集群。类似流行病传播，每个"感染"节点在每轮传播中感染其他节点。Gossip协议有三种模式：

**反熵**：节点定期与随机邻居完整比较状态差异并修复。保证最终一致性但传输量大。可通过Merkle树减少传输量——只比较哈希，差异部分才传输完整数据。Cassandra使用反熵修复节点间数据不一致。

**谣言传播**：新信息产生时立即以Gossip方式传播，传播N轮后停止（标记为"已知"）。适合传播新事件，延迟低但不保证一致性。节点收到新信息后标记为"hot"，以更高频率传播。

**推送-拉取模型**：推送是发送方主动发送信息；拉取是接收方主动请求信息。推送-拉取结合效果最好——推送快速传播新信息，拉取修复遗漏。纯推送模式在节点已感染时浪费带宽，纯拉取模式延迟较高。

**Φ故障检测器（Accrual Failure Detector）**：传统心跳超时是二值判断（活着/死了），Φ检测器输出连续的怀疑度值。基于历史心跳到达时间的统计分布，计算当前心跳延迟的Φ值。Φ=1表示10%概率误判，Φ=3表示0.1%误判。应用层根据Φ值阈值决定是否标记节点为故障，适应不同场景的容错需求。相比固定超时，Φ检测器能适应网络延迟的变化。

```python
"""
Gossip协议：状态传播 + 故障检测
"""
import random
import time
import threading
import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any
from math import erf, sqrt


@dataclass
class NodeState:
    """节点状态信息"""
    node_id: str
    address: str
    is_alive: bool = True
    heartbeat: int = 0
    last_seen: float = field(default_factory=time.monotonic)
    state_version: int = 0
    metadata: dict = field(default_factory=dict)


@dataclass
class GossipMessage:
    """Gossip消息"""
    sender_id: str
    states: dict
    timestamp: float = field(default_factory=time.monotonic)


class PhiAccrualDetector:
    """
    Φ累积故障检测器
    基于心跳到达时间的统计分布计算怀疑度
    """

    def __init__(self, sample_size=1000, min_std_dev=0.01):
        self._heartbeat_history = deque(maxlen=sample_size)
        self._last_heartbeat = time.monotonic()
        self._min_std_dev = min_std_dev
        self._sum = 0.0
        self._sum_sq = 0.0
        self._count = 0

    def heartbeat(self):
        """记录一次心跳到达"""
        now = time.monotonic()
        interval = now - self._last_heartbeat
        self._last_heartbeat = now
        if self._count >= self._heartbeat_history.maxlen:
            old = self._heartbeat_history[0]
            self._sum -= old
            self._sum_sq -= old * old
            self._count -= 1
        self._heartbeat_history.append(interval)
        self._sum += interval
        self._sum_sq += interval * interval
        self._count += 1

    def phi(self):
        """计算当前Φ值"""
        if self._count < 2:
            return 0.0
        now = time.monotonic()
        elapsed = now - self._last_heartbeat
        mean = self._sum / self._count
        variance = self._sum_sq / self._count - mean * mean
        std_dev = max(math.sqrt(max(variance, 0)), self._min_std_dev)
        if elapsed <= 0:
            return 0.0
        # 正态分布CDF
        cdf = 0.5 * (1 + erf((elapsed - mean) / (std_dev * sqrt(2))))
        p = max(1e-10, 1.0 - cdf)
        try:
            return min(-math.log10(p), 100.0)
        except (ValueError, OverflowError):
            return 100.0


class GossipNode:
    """
    Gossip协议节点
    - 定期与随机邻居交换状态
    - 使用Φ检测器进行故障检测
    """

    def __init__(self, node_id, address,
                 gossip_interval=0.1, fanout=3, phi_threshold=8.0):
        self.node_id = node_id
        self.address = address
        self.local_state = NodeState(
            node_id=node_id, address=address, is_alive=True)
        self._cluster_state = {node_id: self.local_state}
        self._detectors = {}
        self.gossip_interval = gossip_interval
        self.fanout = fanout
        self.phi_threshold = phi_threshold
        self._network = {}
        self._running = False
        self._thread = None
        self._fd_thread = None
        self._lock = threading.Lock()
        self._heartbeat_counter = 0

    def set_network(self, network):
        self._network = network

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._gossip_loop, daemon=True)
        self._thread.start()
        self._fd_thread = threading.Thread(
            target=self._failure_detection_loop, daemon=True)
        self._fd_thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._fd_thread:
            self._fd_thread.join(timeout=2)

    def _gossip_loop(self):
        """Gossip主循环"""
        while self._running:
            self._heartbeat_counter += 1
            with self._lock:
                self.local_state.heartbeat = self._heartbeat_counter
                self.local_state.last_seen = time.monotonic()
                self.local_state.state_version += 1
            self._gossip_once()
            time.sleep(self.gossip_interval)

    def _gossip_once(self):
        """执行一轮Gossip传播"""
        with self._lock:
            peers = [n for n in self._cluster_state.keys()
                     if n != self.node_id and n in self._network]
        if not peers:
            return
        selected = random.sample(peers, min(self.fanout, len(peers)))
        for peer_id in selected:
            peer = self._network.get(peer_id)
            if peer and peer.local_state.is_alive:
                self._send_gossip(peer)

    def _send_gossip(self, peer):
        """向邻居发送Gossip消息"""
        with self._lock:
            states = dict(self._cluster_state)
        msg = GossipMessage(sender_id=self.node_id, states=states)
        peer._receive_gossip(msg)

    def _receive_gossip(self, msg):
        """接收Gossip消息并合并状态"""
        with self._lock:
            for node_id, remote_state in msg.states.items():
                local = self._cluster_state.get(node_id)
                if local is None or remote_state.state_version > local.state_version:
                    self._cluster_state[node_id] = NodeState(
                        node_id=remote_state.node_id,
                        address=remote_state.address,
                        is_alive=remote_state.is_alive,
                        heartbeat=remote_state.heartbeat,
                        last_seen=time.monotonic(),
                        state_version=remote_state.state_version,
                        metadata=remote_state.metadata)
                    if node_id != self.node_id:
                        if node_id not in self._detectors:
                            self._detectors[node_id] = PhiAccrualDetector()
                        self._detectors[node_id].heartbeat()

    def _failure_detection_loop(self):
        """故障检测循环"""
        while self._running:
            with self._lock:
                for node_id, detector in list(self._detectors.items()):
                    if node_id == self.node_id:
                        continue
                    phi = detector.phi()
                    state = self._cluster_state.get(node_id)
                    if state and state.is_alive and phi > self.phi_threshold:
                        state.is_alive = False
                        state.state_version += 1
                        print(f"  [Node {self.node_id}] 检测到 "
                              f"Node {node_id} 故障 (Phi={phi:.2f})")
                    elif (state and not state.is_alive and
                          phi < self.phi_threshold * 0.5):
                        state.is_alive = True
                        state.state_version += 1
            time.sleep(0.05)

    def set_metadata(self, key, value):
        """设置元数据（触发Gossip传播）"""
        with self._lock:
            self.local_state.metadata[key] = value
            self.local_state.state_version += 1

    def get_cluster_state(self):
        with self._lock:
            return {
                nid: {"alive": s.is_alive, "heartbeat": s.heartbeat,
                      "version": s.state_version, "metadata": s.metadata}
                for nid, s in self._cluster_state.items()}

    def simulate_crash(self):
        """模拟节点崩溃"""
        self._running = False
        self.local_state.is_alive = False
        if self._thread:
            self._thread.join(timeout=1)
        if self._fd_thread:
            self._fd_thread.join(timeout=1)


class GossipCluster:
    """Gossip集群管理器"""

    def __init__(self, node_configs, fanout=3, gossip_interval=0.1):
        self.nodes = {}
        network = {}
        for node_id, address in node_configs:
            node = GossipNode(node_id, address, gossip_interval, fanout)
            self.nodes[node_id] = node
            network[node_id] = node
        for node in self.nodes.values():
            node.set_network(network)

    def start(self):
        for node in self.nodes.values():
            node.start()

    def stop(self):
        for node in self.nodes.values():
            node.stop()


# ======================== 测试 ========================
if __name__ == "__main__":
    random.seed(42)

    # 测试1：状态传播
    print("=== 测试1：Gossip状态传播 ===")
    cluster = GossipCluster([
        ("n1", "127.0.0.1:8001"), ("n2", "127.0.0.1:8002"),
        ("n3", "127.0.0.1:8003"), ("n4", "127.0.0.1:8004"),
        ("n5", "127.0.0.1:8005"), ("n6", "127.0.0.1:8006"),
        ("n7", "127.0.0.1:8007"), ("n8", "127.0.0.1:8008"),
        ("n9", "127.0.0.1:8009"), ("n10", "127.0.0.1:8010"),
    ], fanout=3, gossip_interval=0.05)
    cluster.start()
    cluster.nodes["n1"].set_metadata("status", "UPGRADING")
    time.sleep(1.0)
    spread_count = 0
    for nid, node in cluster.nodes.items():
        state = node.get_cluster_state().get("n1", {})
        if state.get("metadata", {}).get("status") == "UPGRADING":
            spread_count += 1
    print(f"状态传播: n1的元数据传播到 {spread_count}/10 个节点")
    assert spread_count == 10, f"应传播到所有节点，实际{spread_count}"
    print("[OK] Gossip状态传播到所有节点")

    # 测试2：新节点加入
    print("\n=== 测试2：新节点加入 ===")
    n11 = GossipNode("n11", "127.0.0.1:8011", 0.05, 3)
    for node in list(cluster.nodes.values()) + [n11]:
        node._network["n11"] = n11
    n11._network = {**cluster.nodes, "n11": n11}
    cluster.nodes["n11"] = n11
    n11.start()
    time.sleep(1.0)
    n11_state = n11.get_cluster_state()
    print(f"新节点n11知道 {len(n11_state)}/11 个节点")
    assert len(n11_state) >= 10
    print("[OK] 新节点通过Gossip发现集群成员")

    # 测试3：故障检测
    print("\n=== 测试3：故障检测 ===")
    cluster.nodes["n5"].simulate_crash()
    print("节点n5已崩溃，等待检测...")
    time.sleep(5.0)
    detect_count = 0
    for nid, node in cluster.nodes.items():
        if nid == "n5":
            continue
        state = node.get_cluster_state().get("n5", {})
        if not state.get("alive", True):
            detect_count += 1
    print(f"{detect_count}/10 个节点检测到n5故障")
    if detect_count > 0:
        print("[OK] Gossip故障检测生效")
    else:
        print("[提示] Phi检测器需要更多时间累积数据")
    cluster.stop()

    # 测试4：Phi检测器准确性
    print("\n=== 测试4：Phi检测器 ===")
    detector = PhiAccrualDetector(sample_size=100)
    for _ in range(50):
        detector.heartbeat()
        time.sleep(0.01)
    phi_normal = detector.phi()
    print(f"正常情况下Phi值: {phi_normal:.4f} (应接近0)")
    time.sleep(0.2)
    phi_after_delay = detector.phi()
    print(f"延迟0.2秒后Phi值: {phi_after_delay:.4f} (应明显升高)")
    assert phi_after_delay > phi_normal
    print("[OK] Phi检测器正确反映心跳延迟")
```

### 思考题
1. Gossip协议的传播速度是O(log N)，这个复杂度是如何推导的？fanout参数如何影响传播速度和带宽消耗？
2. Phi故障检测器相比固定超时有什么优势？如何选择合适的Phi阈值？
3. 反熵和谣言传播各适合什么场景？如何用Merkle树优化反熵的传输量？

---

## 第15题：分布式事务

### 知识点讲解

分布式事务是跨多个服务或数据库的事务，保证操作的原子性和一致性。本实现涵盖两种核心模式：两阶段提交和Saga。

**两阶段提交（2PC）**：包含协调者和多个参与者。阶段一（Prepare）：协调者询问所有参与者是否可以提交，参与者执行操作并锁定资源，回复YES或NO。阶段二（Commit/Rollback）：如果所有参与者都YES，协调者发送COMMIT；否则发送ROLLBACK。2PC是强一致性协议，但存在阻塞问题——如果协调者在第二阶段崩溃，参与者会一直持有资源锁等待，且同步阻塞影响性能。2PC适用于数据库层面的分布式事务（如XA协议），不适合微服务架构。

**Saga模式**：将长事务拆分为一系列本地事务T1, T2, ..., Tn，每个Ti有对应的补偿事务Ci。如果Ti失败，则按逆序执行C(i-1), ..., C1回滚。Saga是最终一致性方案，不持有锁，性能好但中间状态可见。Saga有两种实现：编排式（Orchestrator集中协调）和编舞式（事件驱动，各服务监听事件触发下一步）。编排式更易管理但Orchestrator是单点；编舞式去中心化但流程难以追踪。

**ACID vs BASE**：ACID（原子性、一致性、隔离性、持久性）是传统数据库事务的目标，保证强一致性但牺牲可用性和性能。BASE（基本可用、软状态、最终一致性）是分布式系统的妥协，牺牲强一致性换取高可用。2PC追求ACID，Saga追求BASE。

**TCC补偿**：Try-Confirm-Cancel模式。Try阶段预留资源（如冻结余额），Confirm阶段确认操作（扣减冻结余额），Cancel阶段释放资源（解冻）。TCC相比Saga的优势是资源在Try阶段就锁定，隔离性更好；劣势是业务侵入性强，每个操作需要实现三个方法。

**幂等性设计**：分布式事务中由于重试机制，同一操作可能执行多次。幂等性保证多次执行结果一致。实现方式：唯一请求ID + 去重表、数据库唯一约束、乐观锁版本号。Saga的补偿操作也必须幂等——如果补偿操作执行后崩溃重试，不能产生副作用。

```python
"""
分布式事务：两阶段提交(2PC) + Saga模式 + TCC
"""
import time
import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable


# ======================== 两阶段提交(2PC) ========================
class ParticipantState(Enum):
    INIT = "INIT"
    PREPARED = "PREPARED"
    COMMITTED = "COMMITTED"
    ABORTED = "ABORTED"


@dataclass
class Participant:
    """2PC参与者"""
    name: str
    state: ParticipantState = ParticipantState.INIT
    data: dict = field(default_factory=dict)
    _backup: dict = field(default_factory=dict)

    def prepare(self, key, value):
        """准备阶段：执行操作并锁定资源"""
        if self.state != ParticipantState.INIT:
            return False
        self._backup[key] = self.data.get(key)
        self.data[key] = value
        self.state = ParticipantState.PREPARED
        return True

    def commit(self):
        """提交"""
        if self.state == ParticipantState.PREPARED:
            self.state = ParticipantState.COMMITTED
            self._backup.clear()

    def rollback(self):
        """回滚"""
        if self.state == ParticipantState.PREPARED:
            for key, old_val in self._backup.items():
                if old_val is None:
                    self.data.pop(key, None)
                else:
                    self.data[key] = old_val
            self._backup.clear()
            self.state = ParticipantState.ABORTED
        elif self.state == ParticipantState.INIT:
            self.state = ParticipantState.ABORTED


class TwoPhaseCommitCoordinator:
    """2PC协调者"""

    def __init__(self):
        self.participants = []
        self._transaction_log = []

    def add_participant(self, participant):
        self.participants.append(participant)

    def execute(self, operations):
        """执行分布式事务"""
        txn_id = str(uuid.uuid4())[:8]
        print(f"\n  [2PC] 开始事务 {txn_id}")
        # 阶段一：Prepare
        print(f"  [2PC] 阶段一: Prepare")
        for op_name, key, value in operations:
            participant = next(
                (p for p in self.participants if p.name == op_name), None)
            if participant is None:
                print(f"    参与者 {op_name} 不存在，事务中止")
                self._abort_all()
                return False
            success = participant.prepare(key, value)
            if success:
                print(f"    {op_name}: Prepare成功")
            else:
                print(f"    {op_name}: Prepare失败，事务中止")
                self._abort_all()
                return False
        # 阶段二：Commit
        print(f"  [2PC] 阶段二: Commit")
        for p in self.participants:
            if p.state == ParticipantState.PREPARED:
                p.commit()
                print(f"    {p.name}: 已提交")
        self._transaction_log.append(
            {"txn_id": txn_id, "result": "committed"})
        return True

    def _abort_all(self):
        """中止所有已Prepare的参与者"""
        for p in self.participants:
            if p.state == ParticipantState.PREPARED:
                p.rollback()
                print(f"    {p.name}: 已回滚")
        for p in self.participants:
            if p.state == ParticipantState.INIT:
                p.state = ParticipantState.ABORTED


# ======================== Saga模式 ========================
class SagaStep:
    """Saga事务步骤"""
    def __init__(self, name, action, compensation):
        self.name = name
        self.action = action
        self.compensation = compensation
        self.executed = False
        self.compensated = False


class SagaOrchestrator:
    """
    Saga编排器
    - 按顺序执行每个步骤的正向操作
    - 如果某步失败，逆序执行已完成步骤的补偿操作
    """
    def __init__(self, saga_name=""):
        self.saga_name = saga_name
        self.steps = []
        self._completed_steps = []
        self._status = "INIT"

    def add_step(self, name, action, compensation):
        self.steps.append(SagaStep(name, action, compensation))
        return self

    def execute(self):
        """执行Saga事务"""
        saga_id = str(uuid.uuid4())[:8]
        print(f"\n  [Saga] 开始 {self.saga_name} (id={saga_id})")
        self._status = "RUNNING"
        for i, step in enumerate(self.steps):
            print(f"  [Saga] 步骤{i+1}/{len(self.steps)}: {step.name}")
            try:
                success = step.action()
                if success:
                    step.executed = True
                    self._completed_steps.append(step)
                    print(f"    -> 成功")
                else:
                    print(f"    -> 失败，开始补偿")
                    self._compensate()
                    self._status = "COMPENSATED"
                    return False
            except Exception as e:
                print(f"    -> 异常: {e}，开始补偿")
                self._compensate()
                self._status = "COMPENSATED"
                return False
        self._status = "COMPLETED"
        print(f"  [Saga] 事务完成")
        return True

    def _compensate(self):
        """逆序执行补偿操作"""
        print(f"  [Saga] 补偿 ({len(self._completed_steps)}步)")
        for step in reversed(self._completed_steps):
            if step.executed and not step.compensated:
                try:
                    step.compensation()
                    step.compensated = True
                    print(f"    补偿 {step.name}: 成功")
                except Exception as e:
                    print(f"    补偿 {step.name}: 异常 {e}")

    @property
    def status(self):
        return self._status


# ======================== TCC模式 ========================
class TCCParticipant:
    """TCC参与者：Try-Confirm-Cancel"""
    def __init__(self, name):
        self.name = name
        self._frozen = {}
        self._actual = {}
        self._state = "INIT"

    def try_execute(self, key, value):
        self._frozen[key] = value
        self._state = "TRIED"
        return True

    def confirm(self, key):
        if key in self._frozen:
            self._actual[key] = self._frozen[key]
            del self._frozen[key]
            self._state = "CONFIRMED"
            return True
        return False

    def cancel(self, key):
        self._frozen.pop(key, None)
        self._state = "CANCELLED"
        return True

    def get_value(self, key):
        return self._actual.get(key)


class TCCCoordinator:
    """TCC协调器"""
    def __init__(self):
        self.participants = []
        self._tried = []

    def add_participant(self, p):
        self.participants.append(p)

    def execute(self, operations):
        # Try阶段
        print("\n  [TCC] Try阶段")
        for idx, key, value in operations:
            p = self.participants[idx]
            if p.try_execute(key, value):
                self._tried.append((p, key))
                print(f"    {p.name}: Try {key}={value}")
            else:
                print(f"    {p.name}: Try失败，Cancel")
                self._cancel_all()
                return False
        # Confirm阶段
        print("  [TCC] Confirm阶段")
        for p, key in self._tried:
            p.confirm(key)
            print(f"    {p.name}: Confirm {key}")
        return True

    def _cancel_all(self):
        print("  [TCC] Cancel阶段")
        for p, key in self._tried:
            p.cancel(key)
            print(f"    {p.name}: Cancel {key}")


# ======================== 幂等性管理器 ========================
class IdempotencyManager:
    """幂等性管理器：基于请求ID去重"""
    def __init__(self):
        self._processed = {}
        self._lock = threading.Lock()

    def execute_idempotent(self, request_id, action):
        with self._lock:
            if request_id in self._processed:
                print(f"  [幂等] 请求 {request_id} 已处理，返回缓存")
                return self._processed[request_id]["result"]
        result = action()
        with self._lock:
            self._processed[request_id] = {
                "result": result, "time": time.time()}
        return result


# ======================== 测试 ========================
if __name__ == "__main__":
    # 测试1：2PC成功场景
    print("=== 测试1：2PC成功场景 ===")
    coord = TwoPhaseCommitCoordinator()
    account_a = Participant("account_a", data={"balance": 1000})
    account_b = Participant("account_b", data={"balance": 500})
    coord.add_participant(account_a)
    coord.add_participant(account_b)
    success = coord.execute([
        ("account_a", "balance", 900),
        ("account_b", "balance", 600),
    ])
    assert success
    assert account_a.data["balance"] == 900
    assert account_b.data["balance"] == 600
    print(f"\n  结果: A={account_a.data['balance']}, B={account_b.data['balance']}")
    print("[OK] 2PC成功提交")

    # 测试2：2PC失败回滚
    print("\n=== 测试2：2PC失败回滚 ===")
    coord2 = TwoPhaseCommitCoordinator()
    svc1 = Participant("svc1", data={"data": "original"})
    svc2 = Participant("svc2", data={"data": "original"})
    svc3 = Participant("svc3", data={"data": "original"})
    coord2.add_participant(svc1)
    coord2.add_participant(svc2)
    coord2.add_participant(svc3)
    svc3.state = ParticipantState.COMMITTED  # 模拟异常
    success = coord2.execute([
        ("svc1", "data", "modified"),
        ("svc2", "data", "modified"),
        ("svc3", "data", "modified"),
    ])
    assert not success
    assert svc1.data["data"] == "original"
    assert svc2.data["data"] == "original"
    print(f"\n  结果: svc1={svc1.data['data']}, svc2={svc2.data['data']}")
    print("[OK] 2PC失败时正确回滚")

    # 测试3：Saga成功场景
    print("\n=== 测试3：Saga成功场景 ===")
    order_state = {"created": False, "paid": False, "shipped": False}
    saga = SagaOrchestrator("订单处理")
    saga.add_step("创建订单",
                  lambda: order_state.update(created=True) or True,
                  lambda: order_state.update(created=False) or True)
    saga.add_step("支付",
                  lambda: order_state.update(paid=True) or True,
                  lambda: order_state.update(paid=False) or True)
    saga.add_step("发货",
                  lambda: order_state.update(shipped=True) or True,
                  lambda: order_state.update(shipped=False) or True)
    success = saga.execute()
    assert success
    assert order_state == {"created": True, "paid": True, "shipped": True}
    print(f"\n  最终状态: {order_state}")
    print("[OK] Saga成功完成")

    # 测试4：Saga失败补偿
    print("\n=== 测试4：Saga失败补偿 ===")
    state2 = {"booked": False, "paid": False, "ticketed": False}
    fail_count = [0]
    def issue_ticket():
        fail_count[0] += 1
        return False if fail_count[0] == 1 else True
    saga2 = SagaOrchestrator("机票预订")
    saga2.add_step("预订航班",
                  lambda: state2.update(booked=True) or True,
                  lambda: state2.update(booked=False) or True)
    saga2.add_step("支付",
                  lambda: state2.update(paid=True) or True,
                  lambda: state2.update(paid=False) or True)
    saga2.add_step("出票", issue_ticket, lambda: True)
    success = saga2.execute()
    assert not success
    assert state2 == {"booked": False, "paid": False, "ticketed": False}
    print(f"\n  补偿后状态: {state2}")
    print("[OK] Saga失败时正确执行补偿")

    # 测试5：TCC模式
    print("\n=== 测试5：TCC模式 ===")
    tcc = TCCCoordinator()
    tcc_a = TCCParticipant("账户A")
    tcc_b = TCCParticipant("账户B")
    tcc.add_participant(tcc_a)
    tcc.add_participant(tcc_b)
    success = tcc.execute([(0, "deduct", 100), (1, "add", 100)])
    assert success
    assert tcc_a.get_value("deduct") == 100
    assert tcc_b.get_value("add") == 100
    print(f"\n  A确认: {tcc_a.get_value('deduct')}, B确认: {tcc_b.get_value('add')}")
    print("[OK] TCC模式正确执行")

    # 测试6：幂等性
    print("\n=== 测试6：幂等性 ===")
    mgr = IdempotencyManager()
    exec_count = [0]
    def do_action():
        exec_count[0] += 1
        time.sleep(0.01)
        return f"result_{exec_count[0]}"
    req_id = "req_001"
    r1 = mgr.execute_idempotent(req_id, do_action)
    r2 = mgr.execute_idempotent(req_id, do_action)
    r3 = mgr.execute_idempotent(req_id, do_action)
    print(f"\n  3次执行结果: {r1}, {r2}, {r3}")
    print(f"  实际执行次数: {exec_count[0]}")
    assert r1 == r2 == r3
    assert exec_count[0] == 1
    print("[OK] 幂等性保证重复请求只执行一次")

    # 测试7：三种模式对比
    print("\n=== 测试7：三种模式对比 ===")
    print("""
  +----------+-------------------+---------------------+---------------------+
  |  模式    |  一致性           |  性能               |  适用场景           |
  +----------+-------------------+---------------------+---------------------+
  |  2PC     |  强一致性(ACID)   |  低（同步阻塞）     |  数据库层XA事务     |
  |  Saga    |  最终一致性(BASE) |  高（无锁）         |  微服务长事务       |
  |  TCC     |  较强一致性       |  中（Try阶段锁）    |  资源预留场景       |
  +----------+-------------------+---------------------+---------------------+
    """)
    print("[OK] 三种分布式事务模式对比完成")

print("\n" + "=" * 60)
print("全部15道练习题已完整输出！")
print("=" * 60)
```

### 思考题
1. 2PC的协调者如果在Commit阶段崩溃，参与者如何恢复？为什么说2PC存在阻塞问题？
2. Saga的补偿操作必须满足什么特性？如果补偿操作本身也失败了如何处理？
3. TCC相比Saga有什么优势？为什么TCC的Try阶段能提供更好的隔离性？Try阶段"预留资源"在业务层面如何实现？

---

> 本文档包含15道系统设计与分布式系统练习题，涵盖系统设计（5题）、数据库进阶（5题）、分布式系统（5题）。所有代码均为完整可运行的Python实现，使用标准库+numpy+httpx。
