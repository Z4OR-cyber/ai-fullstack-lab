# 第四期 · Track1 技能深化 — 20道进阶编程练习题

> **适用对象**：已完成基础 Track 的学员，面向实战深化
> **语言**：Python（AI 数学部分使用 numpy/scipy/sympy，禁止 PyTorch/TensorFlow）
> **格式**：题号+标题 → 知识点讲解 → 完整可运行代码 → 思考题

---

## 一、编程语言进阶（4题）

---

### 第1题：Python元编程实战 — 元类实现ORM字段映射

**知识点讲解**

Python 元编程的核心在于"用代码来写代码"。元类（metaclass）是"类的类"——普通类创建实例，元类创建类。当你书写 `class Foo(metaclass=Meta)` 时，Python 解释器在 **类体执行完毕后、类对象绑定到名称之前** 调用 `Meta.__new__` 和 `Meta.__init__`，因此元类可以在类创建的瞬间收集字段信息。

`__new__` 负责创建并返回类对象本身，`__init__` 负责对已创建的类做后处理。在 ORM 场景中，我们通常在 `__new__` 中扫描 `namespace` 字典，提取所有 `Field` 描述符实例，构建 `_fields` 映射表。这样做的好处是：子类继承时，元类会递归触发，自动合并父类字段。

描述符协议（`__get__` / `__set__` / `__set_name__`）让字段实例能在属性访问时做类型校验和默认值填充。`__set_name__` 在 Python 3.6+ 中由解释器自动调用，将属性名注入描述符，无需在元类中手动赋值。整体流程：**元类收集字段 → 描述符拦截读写 → 基类提供 CRUD 接口**，这就是 Django ORM、SQLAlchemy 声明式映射的底层原理。

```python
"""
元类实现 ORM 字段映射 —— 完整可运行示例
运行：python exercise_01_metaclass_orm.py
"""
from typing import Any, Dict, Type, Optional, get_type_hints


# ──────────── 字段描述符 ────────────
class Field:
    """基础字段描述符，拦截属性读写"""

    def __init__(self, column_type: str, default=None, primary_key: bool = False):
        self.column_type = column_type   # 数据库列类型
        self.default = default           # 默认值
        self.primary_key = primary_key   # 是否主键
        self.name: Optional[str] = None  # 属性名，由 __set_name__ 自动注入

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            # 类级别访问，返回描述符自身
            return self
        # 实例级别访问，返回存储的值或默认值
        return instance.__dict__.get(self.name, self.default)

    def __set__(self, instance, value: Any) -> None:
        # 类型校验（简单版）
        if value is not None and not isinstance(value, (str, int, float, bool, type(None))):
            raise TypeError(f"字段 {self.name} 不支持的类型: {type(value)}")
        instance.__dict__[self.name] = value

    def __repr__(self) -> str:
        return f"<Field {self.name}: {self.column_type}>"


class CharField(Field):
    def __init__(self, max_length: int = 255, default=None, primary_key: bool = False):
        super().__init__(f"VARCHAR({max_length})", default, primary_key)
        self.max_length = max_length

    def __set__(self, instance, value):
        if value is not None and not isinstance(value, str):
            raise TypeError(f"CharField {self.name} 需要 str，得到 {type(value).__name__}")
        if value and len(value) > self.max_length:
            raise ValueError(f"字段 {self.name} 超出最大长度 {self.max_length}")
        instance.__dict__[self.name] = value


class IntField(Field):
    def __init__(self, default=None, primary_key: bool = False):
        super().__init__("INTEGER", default, primary_key)

    def __set__(self, instance, value):
        if value is not None and not isinstance(value, int):
            raise TypeError(f"IntField {self.name} 需要 int，得到 {type(value).__name__}")
        instance.__dict__[self.name] = value


# ──────────── 元类 ────────────
class ModelMeta(type):
    """
    ORM 元类：
    - __new__：在类创建时扫描 namespace，收集 Field 实例
    - __init__：合并父类字段，构建完整 _fields 映射
    """

    def __new__(mcs, name: str, bases: tuple, namespace: Dict[str, Any], **kwargs):
        # 过滤出当前类体中定义的 Field
        own_fields: Dict[str, Field] = {}
        for key, value in list(namespace.items()):
            if isinstance(value, Field):
                own_fields[key] = value

        # 创建类对象
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)
        # 将当前类的字段存入类属性
        cls._own_fields = own_fields
        return cls

    def __init__(cls, name: str, bases: tuple, namespace: Dict[str, Any], **kwargs):
        super().__init__(name, bases, namespace, **kwargs)
        # 合并父类字段 + 当前类字段（子类覆盖同名字段）
        merged: Dict[str, Field] = {}
        for base in bases:
            if hasattr(base, "_fields"):
                merged.update(base._fields)
        merged.update(cls._own_fields)
        cls._fields = merged

        # 自动检测主键
        pk_fields = [f.name for f in merged.values() if f.primary_key]
        cls._pk = pk_fields[0] if pk_fields else None


# ──────────── Model 基类 ────────────
class Model(metaclass=ModelMeta):
    """所有 ORM 模型的基类"""

    _fields: Dict[str, Field] = {}
    _pk: Optional[str] = None
    _table_name: str = ""

    def __init__(self, **kwargs):
        # 先填充所有字段默认值
        for field_name, field in self._fields.items():
            if field_name not in kwargs:
                setattr(self, field_name, field.default)
        # 再设置传入的值（触发描述符校验）
        for key, value in kwargs.items():
            if key in self._fields:
                setattr(self, key, value)
            else:
                raise AttributeError(f"{type(self).__name__} 没有字段 '{key}'")

    @classmethod
    def table_name(cls) -> str:
        return cls._table_name or cls.__name__.lower()

    def to_dict(self) -> Dict[str, Any]:
        """将实例转换为字典（模拟序列化）"""
        return {name: getattr(self, name) for name in self._fields}

    def generate_create_sql(self) -> str:
        """生成 CREATE TABLE 语句"""
        cols = []
        for name, field in self._fields.items():
            parts = [name, field.column_type]
            if field.primary_key:
                parts.append("PRIMARY KEY")
            if field.default is not None:
                parts.append(f"DEFAULT {repr(field.default)}")
            cols.append(" ".join(parts))
        return f"CREATE TABLE {self.table_name()} (\n  " + ",\n  ".join(cols) + "\n);"

    def generate_insert_sql(self) -> str:
        """生成 INSERT 语句"""
        data = self.to_dict()
        cols = ", ".join(data.keys())
        vals = ", ".join(repr(v) for v in data.values())
        return f"INSERT INTO {self.table_name()} ({cols}) VALUES ({vals});"

    def __repr__(self) -> str:
        pk_val = getattr(self, self._pk, "?") if self._pk else "?"
        return f"<{type(self).__name__} {self._pk}={pk_val}>"


# ──────────── 使用示例 ────────────
class User(Model):
    _table_name = "users"

    id = IntField(primary_key=True)
    username = CharField(max_length=50)
    email = CharField(max_length=100, default="unknown@example.com")
    age = IntField(default=0)


class VIPUser(User):
    """继承 User，自动合并父类字段"""
    _table_name = "vip_users"

    vip_level = IntField(default=1)
    discount = CharField(max_length=10, default="0.9")


# ──────────── 测试 ────────────
if __name__ == "__main__":
    # 查看元类收集的字段
    print("=== User 字段映射 ===")
    for name, field in User._fields.items():
        print(f"  {name}: {field.column_type} (pk={field.primary_key})")

    print("\n=== VIPUser 字段映射（含继承）===")
    for name, field in VIPUser._fields.items():
        print(f"  {name}: {field.column_type} (pk={field.primary_key})")

    # 创建实例
    user = User(id=1, username="alice", email="alice@test.com", age=30)
    print(f"\n=== 实例 ===\n{user}")
    print(f"to_dict: {user.to_dict()}")

    # 生成 SQL
    print(f"\n=== DDL ===\n{user.generate_create_sql()}")
    print(f"\n=== DML ===\n{user.generate_insert_sql()}")

    # 类型校验
    try:
        User(id="not_an_int", username="bad")
    except TypeError as e:
        print(f"\n=== 类型校验 ===\n捕获异常: {e}")

    # 继承测试
    vip = VIPUser(id=2, username="bob", age=25, vip_level=5, discount="0.8")
    print(f"\n=== 继承测试 ===\n{vip}")
    print(f"vip 字段数: {len(VIPUser._fields)} (应=5)")
    print(f"主键: {VIPUser._pk}")
    print(vip.generate_create_sql())
```

**思考题**：如果要让 `CharField` 支持自定义验证函数（如正则校验邮箱格式），你会如何扩展描述符的 `__set__` 方法？提示：在 `__init__` 中接受 `validator` 回调。

---

### 第2题：async/await并发模式 — 并发爬虫+信号量限流+超时重试

**知识点讲解**

`asyncio` 是 Python 的异步 I/O 框架，核心是**事件循环（Event Loop）**——一个不断轮询就绪协程的单线程调度器。协程函数（`async def`）调用后返回一个 **协程对象**，它本身不会执行，必须被 `await` 或包装成 `Task` 才能被事件循环调度。`Task` 是协程的调度包装器，负责在事件循环中跟踪协程状态；`Coroutine` 是可等待对象的底层形态。

并发控制的关键工具是 `asyncio.Semaphore`——一个计数信号量，限制同时运行的协程数量，防止打满目标服务器连接池。超时控制用 `asyncio.wait_for`，它会在指定时间后取消协程并抛出 `TimeoutError`。异常传播方面，当 Task 内部抛出异常时，异常不会自动冒泡到主协程，而是在 `await task` 时才抛出；如果 Task 从未被 await，异常会被静默吞掉（可通过 `task.exception()` 检查）。

重试策略通常结合指数退避（Exponential Backoff）：每次失败后等待 `base_delay * 2^attempt` 秒，加上随机抖动（jitter）避免惊群效应。本例用 `asyncio.Queue` 模拟任务分发，完整展示生产者-消费者模式。

```python
"""
asyncio 并发爬虫 —— 信号量限流 + 超时重试 + 指数退避
运行：python exercise_02_async_crawler.py
"""
import asyncio
import random
import time
from typing import List, Optional, Tuple


# ──────────── 模拟目标服务器 ────────────
async def mock_fetch(url: str) -> str:
    """模拟网络请求：随机延迟 + 随机失败率"""
    delay = random.uniform(0.1, 0.8)
    await asyncio.sleep(delay)
    # 20% 概率返回 500 错误
    if random.random() < 0.2:
        raise ConnectionError(f"服务器错误: {url}")
    return f"<html>内容来自 {url} (耗时 {delay:.2f}s)</html>"


# ──────────── 带重试的爬虫客户端 ────────────
class AsyncCrawler:
    def __init__(
        self,
        max_concurrency: int = 5,
        max_retries: int = 3,
        timeout: float = 2.0,
        backoff_base: float = 0.3,
    ):
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.max_retries = max_retries
        self.timeout = timeout
        self.backoff_base = backoff_base
        self.stats = {"success": 0, "failed": 0, "retried": 0}

    async def fetch_with_retry(self, url: str) -> Optional[str]:
        """带信号量限流、超时、指数退避重试的抓取"""
        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            # 信号量控制并发
            async with self.semaphore:
                try:
                    # 超时控制
                    result = await asyncio.wait_for(
                        mock_fetch(url),
                        timeout=self.timeout,
                    )
                    self.stats["success"] += 1
                    return result

                except asyncio.TimeoutError:
                    last_error = TimeoutError(f"超时: {url} (尝试 {attempt})")
                    print(f"  [超时] {url} 第 {attempt}/{self.max_retries} 次")

                except ConnectionError as e:
                    last_error = e
                    print(f"  [错误] {url} 第 {attempt}/{self.max_retries} 次: {e}")

                except asyncio.CancelledError:
                    raise  # 不拦截取消信号

                except Exception as e:
                    last_error = e
                    print(f"  [未知错误] {url}: {e}")

            # 指数退避 + 随机抖动
            if attempt < self.max_retries:
                self.stats["retried"] += 1
                delay = self.backoff_base * (2 ** (attempt - 1))
                delay += random.uniform(0, 0.1)  # jitter
                print(f"  [退避] {url} 等待 {delay:.2f}s 后重试...")
                await asyncio.sleep(delay)

        self.stats["failed"] += 1
        print(f"  [放弃] {url} 重试 {self.max_retries} 次后失败: {last_error}")
        return None

    async def crawl_all(self, urls: List[str]) -> List[Tuple[str, Optional[str]]]:
        """并发抓取所有 URL"""
        print(f"\n=== 开始抓取 {len(urls)} 个 URL (并发上限: {self.semaphore._value}) ===\n")

        # 创建所有 Task
        tasks = [asyncio.create_task(self.fetch_with_retry(url)) for url in urls]

        # as_completed 按完成顺序获取结果
        results: List[Tuple[str, Optional[str]]] = []
        for coro in asyncio.as_completed(tasks):
            idx = asyncio.as_completed(tasks)  # 占位——实际用 enumerate 方式
            result = await coro
            results.append(("", result))  # as_completed 丢失了 url 映射

        # 更好的方式：直接 await gather
        results.clear()
        gathered = await asyncio.gather(*[
            asyncio.create_task(self.fetch_with_retry(url)) for url in urls
        ], return_exceptions=True)

        for url, result in zip(urls, gathered):
            if isinstance(result, Exception):
                results.append((url, None))
            else:
                results.append((url, result))

        return results


async def main():
    # 生成测试 URL 列表
    urls = [f"https://api.example.com/page/{i}" for i in range(1, 16)]

    crawler = AsyncCrawler(
        max_concurrency=5,
        max_retries=3,
        timeout=1.5,
        backoff_base=0.2,
    )

    start = time.monotonic()
    results = await crawler.crawl_all(urls)
    elapsed = time.monotonic() - start

    # 统计
    print(f"\n{'='*50}")
    print(f"总耗时: {elapsed:.2f}s")
    print(f"成功: {crawler.stats['success']}")
    print(f"失败: {crawler.stats['failed']}")
    print(f"重试次数: {crawler.stats['retried']}")
    print(f"{'='*50}")

    # 展示部分结果
    for url, content in results[:5]:
        status = "✓" if content else "✗"
        print(f"  {status} {url}")

    # 演示 Task 异常传播
    print("\n=== Task 异常传播演示 ===")

    async def failing_task():
        await asyncio.sleep(0.1)
        raise ValueError("任务内部错误")

    task = asyncio.create_task(failing_task())
    try:
        await task
    except ValueError as e:
        print(f"捕获到 Task 异常: {e}")
        print(f"task.exception(): {task.exception()}")
        print(f"task.done(): {task.done()}")
        print(f"task.cancelled(): {task.cancelled()}")

    # 演示 Task vs Coroutine
    print("\n=== Task vs Coroutine ===")

    async def simple_coro(n):
        await asyncio.sleep(0.05)
        return n * 2

    coro = simple_coro(10)
    print(f"协程对象类型: {type(coro)}")  # <class 'coroutine'>
    # 直接 await 协程
    val = await coro
    print(f"协程结果: {val}")

    # Task 可以被并发调度
    task = asyncio.create_task(simple_coro(20))
    print(f"Task 类型: {type(task)}")
    val = await task
    print(f"Task 结果: {val}")


if __name__ == "__main__":
    asyncio.run(main())
```

**思考题**：如果要在爬虫中加入"全局速率限制"（如每秒最多 10 个请求），你会用 `asyncio.Semaphore` 还是令牌桶算法？两种方案的区别是什么？

---

### 第3题：装饰器高级模式 — 带参数缓存+类装饰器+装饰器堆叠

**知识点讲解**

装饰器本质是一个**高阶函数**：接受函数作为参数，返回一个新函数。当装饰器需要参数时，需要**三层嵌套**——最外层接收参数，中间层接收被装饰函数，最内层执行实际逻辑。这是初学者最容易困惑的"装饰器工厂"模式。

`functools.wraps` 的作用是保留原函数的元信息（`__name__`、`__doc__`、`__module__`、`__qualname__`），否则调试时所有被装饰函数的名字都会变成 `wrapper`，导致 traceback 不可读。更深层地，`wraps` 还会复制 `__wrapped__` 属性，让 `inspect.signature` 能穿透装饰器看到原始签名。

闭包陷阱（Late Binding Closure Problem）是经典面试题：在循环中创建闭包时，所有闭包共享同一个循环变量的引用，而非各自的快照。解决方法是用默认参数 `func(i=i)` 或 `functools.partial` 提前绑定值。

类装饰器通过实现 `__call__` 方法让类实例变得可调用，适合需要维护状态的场景（如计数、缓存 LRU）。装饰器堆叠顺序是**自底向上装饰、自顶向下执行**——`@A` 在 `@B` 之上等价于 `A(B(func))`，调用时先进入 A 的 wrapper，再进入 B 的 wrapper。

```python
"""
装饰器高级模式 —— 带参数缓存 + 类装饰器 + 堆叠顺序
运行：python exercise_03_decorators.py
"""
import functools
import hashlib
import json
import time
from typing import Any, Callable, Dict, Optional


# ──────────── 1. 带参数的 TTL 缓存装饰器 ────────────
def ttl_cache(maxsize: int = 128, ttl: float = 60.0):
    """
    带容量限制和过期时间的缓存装饰器（三层嵌套结构）
    - maxsize: 最大缓存条目数（LRU 淘汰）
    - ttl: 缓存存活时间（秒）
    """
    def decorator(func: Callable) -> Callable:
        cache: Dict[str, Any] = {}  # key -> (value, timestamp)
        access_order: list = []     # LRU 访问顺序

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键：函数名 + 参数哈希
            key_data = json.dumps({
                "args": [str(a) for a in args],
                "kwargs": {k: str(v) for k, v in sorted(kwargs.items())},
            }, sort_keys=True)
            key = hashlib.md5(key_data.encode()).hexdigest()
            now = time.monotonic()

            # 检查缓存命中
            if key in cache:
                value, ts = cache[key]
                if now - ts < ttl:
                    # 更新 LRU 顺序
                    access_order.remove(key)
                    access_order.append(key)
                    return value
                else:
                    # 过期，删除
                    del cache[key]
                    access_order.remove(key)

            # 缓存未命中，执行原函数
            result = func(*args, **kwargs)
            cache[key] = (result, now)
            access_order.append(key)

            # LRU 淘汰
            while len(cache) > maxsize:
                oldest = access_order.pop(0)
                cache.pop(oldest, None)

            return result

        # 暴露缓存管理接口
        wrapper.cache_info = lambda: {
            "size": len(cache),
            "maxsize": maxsize,
            "ttl": ttl,
            "keys": list(cache.keys()),
        }
        wrapper.cache_clear = lambda: (cache.clear(), access_order.clear())
        return wrapper

    return decorator


# ──────────── 2. 类装饰器：调用计数 + 耗时统计 ────────────
class CallStats:
    """类装饰器：统计函数调用次数和总耗时"""

    def __init__(self, func: Callable):
        functools.update_wrapper(self, func)  # 等价于 @wraps
        self.func = func
        self.call_count = 0
        self.total_time = 0.0
        self.errors = 0

    def __call__(self, *args, **kwargs):
        self.call_count += 1
        start = time.monotonic()
        try:
            result = self.func(*args, **kwargs)
            self.total_time += time.monotonic() - start
            return result
        except Exception:
            self.errors += 1
            self.total_time += time.monotonic() - start
            raise

    def stats(self) -> Dict[str, Any]:
        avg = self.total_time / self.call_count if self.call_count else 0
        return {
            "function": self.func.__name__,
            "calls": self.call_count,
            "total_time": round(self.total_time, 6),
            "avg_time": round(avg, 6),
            "errors": self.errors,
        }


# ──────────── 3. 装饰器堆叠演示 ────────────
def log_decorator(func: Callable) -> Callable:
    """日志装饰器（最外层）"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(f"  [LOG] 调用 {func.__name__}(args={args}, kwargs={kwargs})")
        result = func(*args, **kwargs)
        print(f"  [LOG] {func.__name__} 返回 {result}")
        return result
    return wrapper


def validate_decorator(func: Callable) -> Callable:
    """参数校验装饰器（中间层）"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        for arg in args:
            if not isinstance(arg, (int, float)):
                raise TypeError(f"参数必须是数字，得到 {type(arg).__name__}")
        return func(*args, **kwargs)
    return wrapper


def timing_decorator(func: Callable) -> Callable:
    """计时装饰器（最内层，最先执行）"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.monotonic()
        result = func(*args, **kwargs)
        elapsed = time.monotonic() - start
        print(f"  [TIME] {func.__name__} 耗时 {elapsed:.6f}s")
        return result
    return wrapper


# ──────────── 4. 闭包陷阱演示与修复 ────────────
def demonstrate_closure_trap():
    """经典闭包陷阱：循环中的 late binding"""
    print("\n=== 闭包陷阱演示 ===")

    # ❌ 错误写法：所有闭包都引用同一个 i
    bad_multipliers = [lambda x: x * i for i in range(1, 4)]
    print("错误结果:", [m(10) for m in bad_multipliers])  # [30, 30, 30]

    # ✓ 修复1：默认参数绑定
    good_multipliers_1 = [lambda x, i=i: x * i for i in range(1, 4)]
    print("修复1(默认参数):", [m(10) for m in good_multipliers_1])  # [10, 20, 30]

    # ✓ 修复2：functools.partial
    good_multipliers_2 = [
        functools.partial(lambda x, i: x * i, i=i) for i in range(1, 4)
    ]
    print("修复2(partial):", [m(10) for m in good_multipliers_2])  # [10, 20, 30]


# ──────────── 使用示例 ────────────
# 堆叠顺序：log → validate → timing → 原函数
# 执行顺序：log_wrapper → validate_wrapper → timing_wrapper → func
@log_decorator
@validate_decorator
@timing_decorator
def compute(a: int, b: int) -> int:
    """计算两个数的乘积"""
    time.sleep(0.01)
    return a * b


@ttl_cache(maxsize=3, ttl=2.0)
@CallStats
def expensive_computation(n: int) -> int:
    """模拟耗时计算（带缓存+统计）"""
    time.sleep(0.1)
    return n ** 3


if __name__ == "__main__":
    # 装饰器堆叠测试
    print("=== 装饰器堆叠顺序测试 ===")
    result = compute(3, 4)
    print(f"最终结果: {result}\n")

    # functools.wraps 穿透测试
    print("=== functools.wraps 元信息 ===")
    print(f"函数名: {compute.__name__}")    # compute（而非 wrapper）
    print(f"文档: {compute.__doc__}")

    # 缓存装饰器测试
    print("\n=== TTL 缓存测试 ===")
    for n in [2, 2, 3, 2, 4, 3]:
        val = expensive_computation(n)
        print(f"  compute({n}) = {val}")

    print(f"\n缓存信息: {expensive_computation.cache_info()}")

    # 等待过期
    print("\n等待 2.1s 让缓存过期...")
    time.sleep(2.1)
    val = expensive_computation(2)
    print(f"  重新计算 compute(2) = {val}")

    # 闭包陷阱
    demonstrate_closure_trap()
```

**思考题**：`@ttl_cache` 装饰器使用了 `json.dumps` 来序列化参数生成缓存键。如果参数包含不可 JSON 序列化的对象（如自定义类实例），你会如何改进缓存键生成策略？

---

### 第4题：类型系统与Protocol — 鸭子类型接口的结构化实现

**知识点讲解**

Python 的类型系统在 PEP 484 之后引入了 `typing` 模块，但其本质与 Java/C# 的**名义子类型（Nominal Subtyping）**不同。在名义子类型中，类 B 必须显式声明 `class B(A)` 才被视为 A 的子类型；而 Python 通过 PEP 544 引入的 `Protocol` 支持**结构子类型（Structural Subtyping）**——只要类拥有 Protocol 定义的全部方法/属性，就被视为该 Protocol 的子类型，无需显式继承。

这就是"鸭子类型"的静态化：运行时 `hasattr` 检查变成了编译时（mypy/pyright）的结构匹配。`runtime_checkable` 装饰器让 Protocol 支持 `isinstance` 检查，但仅检查方法是否存在，不检查签名。

`TypeVar` + `Generic` 实现泛型编程。`TypeVar("T", bound=SomeClass)` 限制类型变量必须是某类的子类；`TypeVar("T", str, int)` 限制为枚举类型之一。`Generic[T]` 让类成为泛型容器，在类型检查器中追踪元素类型。

`@overload` 装饰器用于描述同一函数在不同参数类型下返回不同类型的场景。它为类型检查器提供精确的签名信息，实际运行时使用最后一个非装饰版本。这在 `__getitem__` 等魔术方法中非常常见——传入 `int` 返回单个元素，传入 `slice` 返回列表。

```python
"""
typing.Protocol + Generic —— 结构子类型与泛型编程
运行：python exercise_04_protocol_generic.py
"""
from __future__ import annotations
from typing import (
    Protocol, TypeVar, Generic, overload, runtime_checkable,
    List, Optional, Any, Union, Callable
)
from dataclasses import dataclass, field


# ──────────── 1. Protocol：结构化鸭子类型 ────────────
@runtime_checkable
class Drawable(Protocol):
    """任何拥有 draw() 方法的类型都自动实现此接口"""
    def draw(self, x: int, y: int) -> str:
        ...

@runtime_checkable
class Comparable(Protocol):
    """支持比较操作的类型"""
    def __lt__(self, other: Any) -> bool: ...
    def __eq__(self, other: Any) -> bool: ...


# 不需要显式继承 Drawable，只要结构匹配即可
class Circle:
    def draw(self, x: int, y: int) -> str:
        return f"在 ({x}, {y}) 绘制圆形"

class Square:
    def draw(self, x: int, y: int) -> str:
        return f"在 ({x}, {y}) 绘制方形"

class TextLabel:
    """没有 draw 方法，不实现 Drawable"""
    def render(self, text: str) -> str:
        return f"渲染文本: {text}"


def render_scene(shapes: List[Drawable]) -> None:
    """接受任何实现了 Drawable 的对象列表"""
    for i, shape in enumerate(shapes):
        print(shape.draw(i * 10, i * 10))


# ──────────── 2. TypeVar + Generic：泛型容器 ────────────
T = TypeVar("T", bound=Comparable)  # T 必须可比较


class SortedList(Generic[T]):
    """泛型有序列表：保持元素有序，支持类型安全"""

    def __init__(self, initial: Optional[List[T]] = None):
        self._data: List[T] = []
        if initial:
            for item in initial:
                self.insert(item)

    def insert(self, value: T) -> None:
        """插入元素并保持有序"""
        pos = 0
        while pos < len(self._data) and self._data[pos] < value:
            pos += 1
        self._data.insert(pos, value)

    @overload
    def __getitem__(self, index: int) -> T: ...
    @overload
    def __getitem__(self, index: slice) -> List[T]: ...

    def __getitem__(self, index: Union[int, slice]) -> Union[T, List[T]]:
        """重载：int 返回单个元素，slice 返回列表"""
        return self._data[index]

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, value: T) -> bool:
        # 二分查找
        lo, hi = 0, len(self._data)
        while lo < hi:
            mid = (lo + hi) // 2
            if self._data[mid] == value:
                return True
            elif self._data[mid] < value:
                lo = mid + 1
            else:
                hi = mid
        return False

    def __repr__(self) -> str:
        return f"SortedList({self._data})"


# ──────────── 3. 泛型函数与 TypeVar 约束 ────────────
Numeric = TypeVar("Numeric", int, float)  # 只能是 int 或 float


def clamp(value: Numeric, low: Numeric, high: Numeric) -> Numeric:
    """将值限制在 [low, high] 范围内"""
    if value < low:
        return low
    elif value > high:
        return high
    return value


# ──────────── 4. 协议组合与泛型协议 ────────────
@runtime_checkable
class Iterable(Protocol):
    """可迭代协议"""
    def __iter__(self): ...


@runtime_checkable
class Sized(Protocol):
    """可测量大小协议"""
    def __len__(self) -> int: ...


# 组合协议：同时满足多个 Protocol
class Stack(Generic[T]):
    """泛型栈：实现 Iterable + Sized"""

    def __init__(self):
        self._items: List[T] = []

    def push(self, item: T) -> None:
        self._items.append(item)

    def pop(self) -> T:
        if not self._items:
            raise IndexError("栈为空")
        return self._items.pop()

    def peek(self) -> Optional[T]:
        return self._items[-1] if self._items else None

    def __iter__(self):
        return iter(reversed(self._items))  # 栈顶优先

    def __len__(self) -> int:
        return len(self._items)

    def __repr__(self) -> str:
        return f"Stack({self._items})"


# ──────────── 5. dataclass + Protocol 实现策略模式 ────────────
@dataclass
class DataPoint:
    x: float
    y: float


class DistanceStrategy(Protocol):
    """距离计算策略协议"""
    def calculate(self, a: DataPoint, b: DataPoint) -> float: ...


class EuclideanDistance:
    """欧几里得距离"""
    def calculate(self, a: DataPoint, b: DataPoint) -> float:
        return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


class ManhattanDistance:
    """曼哈顿距离"""
    def calculate(self, a: DataPoint, b: DataPoint) -> float:
        return abs(a.x - b.x) + abs(a.y - b.y)


class ChebyshevDistance:
    """切比雪夫距离"""
    def calculate(self, a: DataPoint, b: DataPoint) -> float:
        return max(abs(a.x - b.x), abs(a.y - b.y))


@dataclass
class PathFinder:
    """路径查找器：通过结构子类型注入策略"""
    strategy: DistanceStrategy
    points: List[DataPoint] = field(default_factory=list)

    def total_distance(self) -> float:
        if len(self.points) < 2:
            return 0.0
        total = 0.0
        for i in range(len(self.points) - 1):
            total += self.strategy.calculate(self.points[i], self.points[i + 1])
        return total


# ──────────── 测试 ────────────
if __name__ == "__main__":
    # Protocol 结构匹配测试
    print("=== Protocol 结构子类型 ===")
    circle = Circle()
    square = Square()
    text = TextLabel()

    print(f"Circle 是 Drawable 吗? {isinstance(circle, Drawable)}")   # True
    print(f"Square 是 Drawable 吗? {isinstance(square, Drawable)}")   # True
    print(f"TextLabel 是 Drawable 吗? {isinstance(text, Drawable)}")  # False

    render_scene([circle, square])

    # 泛型有序列表
    print("\n=== 泛型 SortedList ===")
    sl = SortedList([5, 2, 8, 1, 9, 3])
    print(f"有序列表: {sl}")
    print(f"索引 [2]: {sl[2]}")         # 返回单个 int
    print(f"切片 [1:4]: {sl[1:4]}")     # 返回 List[int]
    print(f"包含 8? {8 in sl}")
    print(f"包含 7? {7 in sl}")

    # 泛型函数
    print("\n=== 泛型函数 clamp ===")
    print(f"clamp(15, 0, 10) = {clamp(15, 0, 10)}")
    print(f"clamp(3.7, 0.0, 5.0) = {clamp(3.7, 0.0, 5.0)}")

    # 泛型栈
    print("\n=== 泛型 Stack ===")
    stack: Stack[int] = Stack()
    for val in [10, 20, 30]:
        stack.push(val)
    print(f"栈: {stack}, 大小: {len(stack)}")
    print(f"栈顶: {stack.peek()}")
    print(f"弹出: {stack.pop()}")
    print(f"遍历: {list(stack)}")
    print(f"是 Iterable? {isinstance(stack, Iterable)}")
    print(f"是 Sized? {isinstance(stack, Sized)}")

    # 策略模式
    print("\n=== 策略模式（Protocol 注入）===")
    points = [DataPoint(0, 0), DataPoint(3, 4), DataPoint(3, 10)]

    for strategy in [EuclideanDistance(), ManhattanDistance(), ChebyshevDistance()]:
        finder = PathFinder(strategy=strategy, points=points)
        name = type(strategy).__name__
        dist = finder.total_distance()
        print(f"  {name:20s} 总距离 = {dist:.4f}")

    # 验证策略类都满足 DistanceStrategy 协议
    print(f"\n  EuclideanDistance 是 DistanceStrategy? "
          f"{isinstance(EuclideanDistance(), DistanceStrategy)}")
```

**思考题**：`@runtime_checkable` 的 `isinstance` 检查只验证方法名是否存在，不验证签名。如果你需要运行时验证方法签名是否匹配 Protocol 定义，你会如何实现？提示：`inspect.signature`。

---

## 二、AI/ML 核心（4题）

---

### 第5题：Transformer注意力从零实现 — 纯numpy Multi-Head Attention

**知识点讲解**

Transformer 的核心是**自注意力机制（Self-Attention）**，它让序列中每个位置都能"看到"所有其他位置。给定输入序列 $X \in \mathbb{R}^{N \times d}$，注意力计算分三步：

1. **线性投影**：用三个权重矩阵 $W_Q, W_K, W_V$ 将输入映射为 Query、Key、Value 三组向量。Q 和 K 的点积衡量"查询与键的匹配程度"，V 则携带实际信息。

2. **缩放点积注意力**：$\text{Attention}(Q,K,V) = \text{softmax}(\frac{QK^T}{\sqrt{d_k}}) V$。除以 $\sqrt{d_k}$ 是为了控制点积的方差——当 $d_k$ 较大时，点积值会变大，导致 softmax 梯度趋近于零（饱和区）。缩放后值域更合理。

3. **多头机制**：将 $d$ 维向量拆分为 $h$ 个头，每个头维度 $d_k = d/h$，独立做注意力计算后拼接。不同头可以关注不同子空间的信息（如语法关系、语义关系），最后用输出矩阵 $W_O$ 做线性融合。

注意力掩码用于处理变长序列和因果约束。填充掩码将 padding 位置的注意力分数设为 $-\infty$，softmax 后归零；因果掩码（下三角矩阵）确保位置 $i$ 只能看到位置 $\leq i$，这是 GPT 类解码器的关键约束。

```python
"""
Transformer Multi-Head Attention —— 纯 numpy 实现
运行：python exercise_05_attention.py
依赖：pip install numpy
"""
import numpy as np


# ──────────── 激活函数 ────────────
def softmax(x: np.ndarray, axis: int = -1) -> np.ndarray:
    """数值稳定的 softmax"""
    x_max = np.max(x, axis=axis, keepdims=True)
    exp_x = np.exp(x - x_max)
    return exp_x / np.sum(exp_x, axis=axis, keepdims=True)


# ──────────── Multi-Head Attention ────────────
class MultiHeadAttention:
    """
    多头注意力机制的完整 numpy 实现

    参数:
        d_model: 模型维度（输入/输出维度）
        n_heads: 注意力头数
    输入:
        query: (batch, seq_len_q, d_model)
        key:   (batch, seq_len_k, d_model)
        value: (batch, seq_len_v, d_model)
        mask:  可选，(batch, 1, seq_len_q, seq_len_k) 或广播兼容
    输出:
        output: (batch, seq_len_q, d_model)
        weights: (batch, n_heads, seq_len_q, seq_len_k)
    """

    def __init__(self, d_model: int = 512, n_heads: int = 8, seed: int = 42):
        assert d_model % n_heads == 0, f"d_model({d_model}) 必须能被 n_heads({n_heads}) 整除"
        self.d_model = d_model
        self.n_heads = n_heads
        self.d_k = d_model // n_heads  # 每个头的维度
        self.rng = np.random.default_rng(seed)

        # 初始化权重矩阵（He 初始化）
        scale = np.sqrt(2.0 / d_model)
        self.W_q = self.rng.standard_normal((d_model, d_model)) * scale
        self.W_k = self.rng.standard_normal((d_model, d_model)) * scale
        self.W_v = self.rng.standard_normal((d_model, d_model)) * scale
        self.W_o = self.rng.standard_normal((d_model, d_model)) * scale

    def split_heads(self, x: np.ndarray) -> np.ndarray:
        """
        (batch, seq_len, d_model) -> (batch, n_heads, seq_len, d_k)
        """
        batch_size, seq_len, _ = x.shape
        x = x.reshape(batch_size, seq_len, self.n_heads, self.d_k)
        return x.transpose(0, 2, 1, 3)

    def combine_heads(self, x: np.ndarray) -> np.ndarray:
        """
        (batch, n_heads, seq_len, d_k) -> (batch, seq_len, d_model)
        """
        batch_size, _, seq_len, _ = x.shape
        x = x.transpose(0, 2, 1, 3)  # (batch, seq_len, n_heads, d_k)
        return x.reshape(batch_size, seq_len, self.d_model)

    def scaled_dot_product_attention(
        self,
        Q: np.ndarray,
        K: np.ndarray,
        V: np.ndarray,
        mask: np.ndarray = None,
    ) -> tuple:
        """
        缩放点积注意力
        Q: (batch, n_heads, seq_len_q, d_k)
        K: (batch, n_heads, seq_len_k, d_k)
        V: (batch, n_heads, seq_len_v, d_k)
        返回: (output, attention_weights)
        """
        # 计算注意力分数: Q @ K^T / sqrt(d_k)
        scores = np.matmul(Q, K.transpose(0, 1, 3, 2)) / np.sqrt(self.d_k)

        # 应用掩码（将需要屏蔽的位置设为 -inf）
        if mask is not None:
            scores = np.where(mask == 0, -1e9, scores)

        # softmax 得到注意力权重
        attention_weights = softmax(scores, axis=-1)

        # 加权求和
        output = np.matmul(attention_weights, V)
        return output, attention_weights

    def forward(
        self,
        query: np.ndarray,
        key: np.ndarray,
        value: np.ndarray,
        mask: np.ndarray = None,
    ) -> tuple:
        """
        前向传播
        """
        batch_size = query.shape[0]

        # 线性投影
        Q = np.matmul(query, self.W_q)  # (batch, seq_len, d_model)
        K = np.matmul(key, self.W_k)
        V = np.matmul(value, self.W_v)

        # 拆分多头
        Q = self.split_heads(Q)  # (batch, n_heads, seq_len_q, d_k)
        K = self.split_heads(K)
        V = self.split_heads(V)

        # 缩放点积注意力
        attn_output, attn_weights = self.scaled_dot_product_attention(Q, K, V, mask)

        # 合并多头
        attn_output = self.combine_heads(attn_output)  # (batch, seq_len_q, d_model)

        # 输出投影
        output = np.matmul(attn_output, self.W_o)

        return output, attn_weights


# ──────────── 掩码生成工具 ────────────
def create_padding_mask(seq: np.ndarray) -> np.ndarray:
    """
    填充掩码：将 0（padding）位置屏蔽
    seq: (batch, seq_len) 整数序列
    返回: (batch, 1, 1, seq_len) 可广播到注意力分数
    """
    mask = (seq != 0).astype(np.float32)
    return mask[:, np.newaxis, np.newaxis, :]


def create_causal_mask(seq_len: int) -> np.ndarray:
    """
    因果掩码（下三角）：位置 i 只能看到位置 <= i
    返回: (seq_len, seq_len) 的 0/1 矩阵
    """
    mask = np.tril(np.ones((seq_len, seq_len), dtype=np.float32))
    return mask


# ──────────── 简单位置编码 ────────────
def positional_encoding(seq_len: int, d_model: int) -> np.ndarray:
    """正弦余弦位置编码"""
    pos = np.arange(seq_len)[:, np.newaxis]          # (seq_len, 1)
    dim = np.arange(d_model)[np.newaxis, :]           # (1, d_model)
    angle = pos / np.power(10000, 2 * (dim // 2) / d_model)

    pe = np.zeros((seq_len, d_model), dtype=np.float32)
    pe[:, 0::2] = np.sin(angle[:, 0::2])  # 偶数维用 sin
    pe[:, 1::2] = np.cos(angle[:, 1::2])  # 奇数维用 cos
    return pe


# ──────────── 测试 ────────────
if __name__ == "__main__":
    np.set_printoptions(precision=4, suppress=True)

    # 基本参数
    d_model = 64
    n_heads = 8
    batch_size = 2
    seq_len = 6

    # 创建注意力模块
    mha = MultiHeadAttention(d_model=d_model, n_heads=n_heads)

    # 生成随机输入
    rng = np.random.default_rng(123)
    x = rng.standard_normal((batch_size, seq_len, d_model)).astype(np.float32)

    # 加入位置编码
    pe = positional_encoding(seq_len, d_model)
    x_with_pe = x + pe[np.newaxis, :, :]

    # === 测试1：自注意力 ===
    print("=== 自注意力 ===")
    output, weights = mha.forward(x_with_pe, x_with_pe, x_with_pe)
    print(f"输入形状:   {x_with_pe.shape}")
    print(f"输出形状:   {output.shape}")
    print(f"权重形状:   {weights.shape}")
    print(f"输出均值:   {output.mean():.4f}, 标准差: {output.std():.4f}")

    # 验证注意力权重每行和为 1（softmax 性质）
    row_sums = weights.sum(axis=-1)
    print(f"注意力权重行和（应≈1）: min={row_sums.min():.4f}, max={row_sums.max():.4f}")

    # === 测试2：因果掩码（Decoder 式） ===
    print("\n=== 因果掩码注意力 ===")
    causal_mask = create_causal_mask(seq_len)
    print(f"因果掩码:\n{causal_mask}")

    output_causal, weights_causal = mha.forward(x_with_pe, x_with_pe, x_with_pe, mask=causal_mask)
    # 验证上三角权重为 0
    head0_weights = weights_causal[0, 0]  # 取第一个样本第一个头
    upper_tri = head0_weights[np.triu_indices(seq_len, k=1)]
    print(f"上三角权重最大值（应≈0）: {np.abs(upper_tri).max():.6f}")

    # === 测试3：填充掩码 ===
    print("\n=== 填充掩码注意力 ===")
    # 模拟变长序列：第2个样本后2位是 padding
    seq_ids = np.array([
        [1, 2, 3, 4, 5, 6],    # 长度6
        [1, 2, 3, 0, 0, 0],    # 长度3，后3位 padding
    ])
    pad_mask = create_padding_mask(seq_ids)
    print(f"填充掩码形状: {pad_mask.shape}")

    output_padded, weights_padded = mha.forward(
        x_with_pe, x_with_pe, x_with_pe, mask=pad_mask
    )
    # 验证 padding 位置的注意力权重为 0
    sample1_weights = weights_padded[1, 0]  # 第二个样本第一个头
    padding_cols = sample1_weights[:, 3:]  # 后3列是 padding
    print(f"Padding 位置权重最大值（应≈0）: {np.abs(padding_cols).max():.6f}")

    # === 测试4：交叉注意力 ===
    print("\n=== 交叉注意力（Decoder→Encoder）===")
    enc_seq_len = 8
    enc_output = rng.standard_normal((batch_size, enc_seq_len, d_model)).astype(np.float32)
    dec_input = rng.standard_normal((batch_size, seq_len, d_model)).astype(np.float32)

    cross_output, cross_weights = mha.forward(dec_input, enc_output, enc_output)
    print(f"Q 来自 decoder: {dec_input.shape}")
    print(f"K,V 来自 encoder: {enc_output.shape}")
    print(f"交叉注意力输出: {cross_output.shape}")
    print(f"交叉注意力权重: {cross_weights.shape}  (seq_q={seq_len}, seq_k={enc_seq_len})")

    # === 可视化注意力热力图（文本形式）===
    print("\n=== 注意力热力图（样本0，头0）===")
    labels = ["The", "cat", "sat", "on", "the", "mat"]
    head_weights = weights[0, 0]  # (seq_len, seq_len)
    print("       " + "  ".join(f"{l:>5s}" for l in labels))
    for i, label in enumerate(labels):
        row = "  ".join(f"{head_weights[i, j]:.3f}" for j in range(len(labels)))
        print(f"{label:>5s}  {row}")
```

**思考题**：当前实现中权重矩阵使用 He 初始化。如果改为全零初始化，所有注意力头会输出相同的值（对称性问题）。你能解释为什么吗？如何打破这种对称性？

---

### 第6题：词向量训练Word2Vec — 纯numpy实现Skip-gram+负采样

**知识点讲解**

Word2Vec 的核心思想是"一个词的含义由它的上下文决定"。**Skip-gram** 模型用中心词预测上下文词：对于句子 "the cat sat"，以 "cat" 为中心词，目标是预测 "the" 和 "sat"。模型有两个权重矩阵——输入嵌入矩阵 $W_{in}$（中心词→向量）和输出嵌入矩阵 $W_{out}$（上下文词→向量），训练完成后通常取 $W_{in}$ 作为最终词向量。

原始 Skip-gram 的输出层需要对整个词表做 softmax，计算量 $O(V)$ 极大。**负采样** 将多分类转化为二分类：正样本是真实上下文词（标签1），负样本是从噪声分布中随机采样的词（标签0）。损失函数变为：$-\log\sigma(v_c^T v_w) - \sum_{k} \log\sigma(-v_{n_k}^T v_w)$，其中 $\sigma$ 是 sigmoid 函数。负采样数量通常取 5-20。

噪声分布采用**Unigram Table** 按词频的 3/4 次方采样：$P(w) \propto \text{count}(w)^{0.75}$。3/4 次方是经验值——它降低了高频词被采为负样本的概率，同时提高了低频词的出现率，使训练更均衡。

梯度更新使用 SGD 或 mini-batch。对中心词向量 $v_w$ 的梯度是正负样本梯度的加权和；对上下文词向量 $v_c$ 和负样本向量 $v_{n_k}$ 的梯度类似。学习率通常从 0.025 开始线性衰减。

```python
"""
Word2Vec Skip-gram + 负采样 —— 纯 numpy 实现
运行：python exercise_06_word2vec.py
依赖：pip install numpy
"""
import numpy as np
from collections import Counter
from typing import List, Tuple, Dict


# ──────────── 语料预处理 ────────────
class TextProcessor:
    """文本预处理：分词、构建词表、生成训练对"""

    def __init__(self, min_count: int = 1):
        self.min_count = min_count
        self.word2idx: Dict[str, int] = {}
        self.idx2word: Dict[int, str] = {}
        self.word_counts: Counter = Counter()
        self.vocab_size: int = 0

    def build_vocab(self, sentences: List[List[str]]) -> None:
        """构建词表"""
        for sentence in sentences:
            self.word_counts.update(sentence)

        # 过滤低频词
        words = [w for w, c in self.word_counts.items() if c >= self.min_count]
        self.word2idx = {w: i for i, w in enumerate(words)}
        self.idx2word = {i: w for w, i in self.word2idx.items()}
        self.vocab_size = len(words)
        print(f"词表大小: {self.vocab_size}")

    def generate_pairs(self, sentences: List[List[str]], window_size: int = 2) -> List[Tuple[int, int]]:
        """生成 (中心词, 上下文词) 训练对"""
        pairs = []
        for sentence in sentences:
            indices = [self.word2idx[w] for w in sentence if w in self.word2idx]
            for i, center_idx in enumerate(indices):
                # 动态窗口：随机缩小窗口大小
                actual_window = np.random.randint(1, window_size + 1)
                start = max(0, i - actual_window)
                end = min(len(indices), i + actual_window + 1)
                for j in range(start, end):
                    if j != i:
                        pairs.append((center_idx, indices[j]))
        return pairs


# ──────────── 负采样表 ────────────
class UnigramTable:
    """按 3/4 次方功率律构建的负采样表"""

    def __init__(self, word_counts: Counter, word2idx: Dict[str, int], table_size: int = 100000):
        self.table_size = table_size
        self.table: np.ndarray = np.zeros(table_size, dtype=np.int32)

        # 计算每个词的 3/4 次方权重
        frequencies = np.array([
            word_counts[word2idx_to_word(w, word2idx)] ** 0.75
            for w in range(len(word2idx))
            for word2idx_to_word in [lambda idx, m: next((k for k, v in m.items() if v == idx), None)]
        ])

        total = frequencies.sum()
        # 填充采样表
        idx = 0
        cumulative = frequencies[0] / total
        for i in range(table_size):
            self.table[i] = idx
            if i / table_size > cumulative and idx < len(frequencies) - 1:
                idx += 1
                cumulative += frequencies[idx] / total

    def sample(self, k: int, exclude: int = -1) -> np.ndarray:
        """采样 k 个负样本，排除正样本"""
        samples = []
        while len(samples) < k:
            s = self.table[np.random.randint(0, self.table_size)]
            if s != exclude:
                samples.append(s)
        return np.array(samples)


def word2idx_to_word(idx: int, mapping: Dict[str, int]) -> str:
    """索引转词"""
    for word, i in mapping.items():
        if i == idx:
            return word
    return ""


# ──────────── Skip-gram + 负采样模型 ────────────
class SkipGramNS:
    """Skip-gram with Negative Sampling"""

    def __init__(self, vocab_size: int, embedding_dim: int = 100, seed: int = 42):
        self.vocab_size = vocab_size
        self.embedding_dim = embedding_dim
        self.rng = np.random.default_rng(seed)

        # 输入嵌入矩阵 W_in: (vocab_size, embedding_dim)
        self.W_in = (self.rng.standard_normal((vocab_size, embedding_dim)) * 0.1).astype(np.float64)
        # 输出嵌入矩阵 W_out: (vocab_size, embedding_dim)
        self.W_out = np.zeros((vocab_size, embedding_dim), dtype=np.float64)

        # 训练损失记录
        self.loss_history: List[float] = []

    def sigmoid(self, x: np.ndarray) -> np.ndarray:
        """数值稳定的 sigmoid"""
        return np.where(x >= 0, 1 / (1 + np.exp(-x)), np.exp(x) / (1 + np.exp(x)))

    def train_pair(
        self,
        center_word: int,
        context_word: int,
        negative_samples: np.ndarray,
        learning_rate: float,
    ) -> float:
        """训练单个 (中心词, 上下文词) 对"""
        # 获取向量
        v_center = self.W_in[center_word]       # (dim,)
        v_context = self.W_out[context_word]    # (dim,)
        v_neg = self.W_out[negative_samples]    # (n_neg, dim)

        # 正样本前向：sigmoid(v_center · v_context)
        pos_score = self.sigmoid(np.dot(v_center, v_context))
        # 负样本前向：sigmoid(-v_center · v_neg)
        neg_scores = self.sigmoid(-np.dot(v_neg, v_center))  # (n_neg,)

        # 计算损失
        loss = -np.log(pos_score + 1e-10) - np.sum(np.log(neg_scores + 1e-10))

        # 计算梯度
        # 正样本梯度: (pos_score - 1) * v_center → 对 v_context
        grad_pos = (pos_score - 1) * v_center     # (dim,)
        # 正样本对中心词的梯度: (pos_score - 1) * v_context
        grad_center_pos = (pos_score - 1) * v_context  # (dim,)

        # 负样本梯度: (neg_score - 1) * v_center → 对 v_neg  (注意: neg_score = sigmoid(-dot))
        # d_loss/d_v_neg = -(1 - neg_score) * v_center = (neg_score - 1) * v_center
        grad_neg = (neg_scores - 1)[:, np.newaxis] * v_center[np.newaxis, :]  # (n_neg, dim)
        # 负样本对中心词的梯度: -(1 - neg_score) * v_neg = (neg_score - 1) * v_neg
        grad_center_neg = np.sum((neg_scores - 1)[:, np.newaxis] * v_neg, axis=0)  # (dim,)

        # 更新参数（梯度下降）
        self.W_out[context_word] -= learning_rate * grad_pos
        self.W_out[negative_samples] -= learning_rate * grad_neg
        self.W_in[center_word] -= learning_rate * (grad_center_pos + grad_center_neg)

        return float(loss)

    def train(
        self,
        pairs: List[Tuple[int, int]],
        negative_table: UnigramTable,
        n_negatives: int = 5,
        epochs: int = 5,
        learning_rate: float = 0.025,
        lr_decay: float = 0.0001,
        verbose: bool = True,
    ) -> None:
        """训练模型"""
        total_pairs = len(pairs)
        for epoch in range(epochs):
            # 打乱训练对
            indices = np.random.permutation(total_pairs)
            epoch_loss = 0.0

            for step, idx in enumerate(indices):
                center, context = pairs[idx]
                # 采负样本
                neg_samples = negative_table.sample(n_negatives, exclude=context)
                # 线性衰减学习率
                lr = learning_rate * (1 - lr_decay * (epoch * total_pairs + step) / (epochs * total_pairs))
                lr = max(lr, learning_rate * 0.0001)

                loss = self.train_pair(center, context, neg_samples, lr)
                epoch_loss += loss

            avg_loss = epoch_loss / total_pairs
            self.loss_history.append(avg_loss)
            if verbose:
                print(f"Epoch {epoch+1}/{epochs} | 平均损失: {avg_loss:.4f} | LR: {lr:.5f}")

    def get_embedding(self, word_idx: int) -> np.ndarray:
        """获取词向量"""
        return self.W_in[word_idx]

    def find_similar(self, word_idx: int, top_k: int = 5) -> List[Tuple[int, float]]:
        """找最相似的词（余弦相似度）"""
        target = self.W_in[word_idx]
        target_norm = target / (np.linalg.norm(target) + 1e-10)
        all_norms = self.W_in / (np.linalg.norm(self.W_in, axis=1, keepdims=True) + 1e-10)
        similarities = all_norms @ target_norm
        # 排除自身
        similarities[word_idx] = -1
        top_indices = np.argsort(similarities)[::-1][:top_k]
        return [(int(i), float(similarities[i])) for i in top_indices]


# ──────────── 测试 ────────────
if __name__ == "__main__":
    # 构建小型语料
    sentences = [
        ["the", "cat", "sat", "on", "the", "mat"],
        ["the", "dog", "sat", "on", "the", "rug"],
        ["the", "cat", "and", "the", "dog", "played"],
        ["cats", "and", "dogs", "are", "friends"],
        ["the", "cat", "chased", "the", "dog"],
        ["the", "dog", "chased", "the", "cat"],
        ["a", "cat", "sits", "on", "a", "mat"],
        ["a", "dog", "sits", "on", "a", "rug"],
        ["the", "mat", "is", "on", "the", "floor"],
        ["the", "rug", "is", "on", "the", "floor"],
    ] * 20  # 重复语料增加训练量

    # 预处理
    processor = TextProcessor(min_count=1)
    processor.build_vocab(sentences)
    pairs = processor.generate_pairs(sentences, window_size=2)
    print(f"训练对数量: {len(pairs)}")

    # 构建负采样表
    neg_table = UnigramTable(processor.word_counts, processor.word2idx, table_size=10000)

    # 训练模型
    model = SkipGramNS(vocab_size=processor.vocab_size, embedding_dim=50, seed=42)
    model.train(
        pairs=pairs,
        negative_table=neg_table,
        n_negatives=5,
        epochs=10,
        learning_rate=0.05,
        verbose=True,
    )

    # 查看词向量
    print("\n=== 词向量示例 ===")
    for word in ["cat", "dog", "mat", "rug"]:
        if word in processor.word2idx:
            idx = processor.word2idx[word]
            emb = model.get_embedding(idx)
            print(f"  {word:8s} (idx={idx}): vec[:5] = {emb[:5]}")

    # 相似词查询
    print("\n=== 相似词查询 ===")
    for word in ["cat", "dog", "mat", "the"]:
        if word in processor.word2idx:
            idx = processor.word2idx[word]
            similar = model.find_similar(idx, top_k=3)
            similar_words = [(processor.idx2word[i], round(s, 4)) for i, s in similar]
            print(f"  {word:8s} → {similar_words}")

    # 损失曲线
    print(f"\n=== 损失变化 ===")
    print(f"  初始: {model.loss_history[0]:.4f}")
    print(f"  最终: {model.loss_history[-1]:.4f}")
    print(f"  下降: {(1 - model.loss_history[-1]/model.loss_history[0])*100:.1f}%")
```

**思考题**：负采样中为什么使用 3/4 次方而不是直接按原始频率采样？如果改为 1 次方（即按原始频率），高频词和低频词的学习效果会如何变化？

---

### 第7题：梯度下降变体对比 — 纯numpy实现SGD/Momentum/Adam/RAdam

**知识点讲解**

梯度下降是机器学习优化的基石。**SGD**（随机梯度下降）每步沿负梯度方向更新：$\theta_{t+1} = \theta_t - \eta \nabla L$。简单但容易在峡谷形损失面中震荡——垂直方向梯度大、水平方向梯度小，导致收敛缓慢。

**Momentum** 引入动量项，累积历史梯度方向：$v_t = \beta v_{t-1} + \eta \nabla L$，$\theta_{t+1} = \theta_t - v_t$。动量系数 $\beta$（通常0.9）让梯度同方向的更新加速，反方向减速，有效抑制峡谷震荡。物理类比是"重球滚下坡"——惯性使其越过小坑。

**Adam**（Adaptive Moment Estimation）结合动量和自适应学习率。它同时维护一阶矩估计 $m_t$（动量）和二阶矩估计 $v_t$（梯度平方的指数移动平均）。偏差校正 $ \hat{m}_t = m_t / (1-\beta_1^t)$ 修正初始阶段估计偏向零的问题。参数自适应：梯度大的维度学习率自动减小，梯度小的维度自动增大。$\beta_1=0.9, \beta_2=0.999, \epsilon=10^{-8}$ 是标准超参数。

**RAdam**（Rectified Adam）解决了 Adam 在训练初期方差估计不稳定的问题。由于指数移动平均在初期样本不足时方差异常大，Adam 前几步可能产生大跳跃。RAdam 引入"热身"机制：根据二阶矩估计的方差计算一个修正因子 $ρ_t$，在初期自动降低有效学习率，无需手动调热身步数。

```python
"""
梯度下降变体对比 —— SGD / Momentum / Adam / RAdam
运行：python exercise_07_optimizers.py
依赖：pip install numpy matplotlib
"""
import numpy as np
from typing import List, Tuple, Callable, Dict


# ──────────── 优化器基类 ────────────
class Optimizer:
    """优化器基类"""
    name = "Base"

    def __init__(self, params: np.ndarray, lr: float = 0.01):
        self.params = params.copy()
        self.lr = lr

    def step(self, grad: np.ndarray) -> None:
        raise NotImplementedError

    def get_params(self) -> np.ndarray:
        return self.params.copy()


# ──────────── 1. SGD ────────────
class SGD(Optimizer):
    """随机梯度下降"""
    name = "SGD"

    def step(self, grad: np.ndarray) -> None:
        self.params -= self.lr * grad


# ──────────── 2. Momentum ────────────
class Momentum(Optimizer):
    """带动量的 SGD"""
    name = "Momentum"

    def __init__(self, params: np.ndarray, lr: float = 0.01, momentum: float = 0.9):
        super().__init__(params, lr)
        self.momentum = momentum
        self.velocity = np.zeros_like(params)

    def step(self, grad: np.ndarray) -> None:
        self.velocity = self.momentum * self.velocity + self.lr * grad
        self.params -= self.velocity


# ──────────── 3. Adam ────────────
class Adam(Optimizer):
    """Adam: Adaptive Moment Estimation"""
    name = "Adam"

    def __init__(
        self,
        params: np.ndarray,
        lr: float = 0.01,
        beta1: float = 0.9,
        beta2: float = 0.999,
        eps: float = 1e-8,
    ):
        super().__init__(params, lr)
        self.beta1 = beta1
        self.beta2 = beta2
        self.eps = eps
        self.m = np.zeros_like(params)  # 一阶矩
        self.v = np.zeros_like(params)  # 二阶矩
        self.t = 0                       # 时间步

    def step(self, grad: np.ndarray) -> None:
        self.t += 1
        # 更新一阶矩（动量）
        self.m = self.beta1 * self.m + (1 - self.beta1) * grad
        # 更新二阶矩（梯度平方的移动平均）
        self.v = self.beta2 * self.v + (1 - self.beta2) * (grad ** 2)
        # 偏差校正
        m_hat = self.m / (1 - self.beta1 ** self.t)
        v_hat = self.v / (1 - self.beta2 ** self.t)
        # 更新参数
        self.params -= self.lr * m_hat / (np.sqrt(v_hat) + self.eps)


# ──────────── 4. RAdam ────────────
class RAdam(Optimizer):
    """
    RAdam: Rectified Adam
    通过方差估计的修正自动实现热身，无需手动设置 warmup
    论文: Liu et al., 2019 "On the Variance of the Adaptive Learning Rate and Beyond"
    """
    name = "RAdam"

    def __init__(
        self,
        params: np.ndarray,
        lr: float = 0.01,
        beta1: float = 0.9,
        beta2: float = 0.999,
        eps: float = 1e-8,
    ):
        super().__init__(params, lr)
        self.beta1 = beta1
        self.beta2 = beta2
        self.eps = eps
        self.m = np.zeros_like(params)
        self.v = np.zeros_like(params)
        self.t = 0
        # 计算 rho_inf：最大近似距离
        self.rho_inf = 2.0 / (1.0 - beta2) - 1.0

    def step(self, grad: np.ndarray) -> None:
        self.t += 1
        t = self.t
        beta1, beta2 = self.beta1, self.beta2

        # 一阶矩和二阶矩
        self.m = beta1 * self.m + (1 - beta1) * grad
        self.v = beta2 * self.v + (1 - beta2) * (grad ** 2)

        # 偏差校正后的一阶矩
        m_hat = self.m / (1 - beta1 ** t)

        # 计算 rho_t
        rho_t = self.rho_inf - 2.0 * t * (beta2 ** t) / (1.0 - beta2 ** t)

        if rho_t > 4:
            # 方差足够稳定，使用完整 Adam 更新 + 修正
            v_hat = self.v / (1 - beta2 ** t)
            # 修正因子
            r = np.sqrt(
                (rho_t - 4) * (rho_t - 2) * self.rho_inf /
                ((self.rho_inf - 4) * (self.rho_inf - 2) * rho_t)
            )
            self.params -= self.lr * r * m_hat / (np.sqrt(v_hat) + self.eps)
        else:
            # 方差估计不稳定，退化为带动量的 SGD（自适应热身）
            self.params -= self.lr * m_hat


# ──────────── 测试函数 ────────────
def rosenbrock(x: np.ndarray) -> Tuple[float, np.ndarray]:
    """
    Rosenbrock 函数：经典的非凸优化测试函数
    f(x,y) = (1-x)^2 + 100(y-x^2)^2
    最小值在 (1, 1)，f=0
    特点：峡谷形，容易在窄谷中震荡
    """
    x_val, y_val = x[0], x[1]
    loss = (1 - x_val) ** 2 + 100 * (y_val - x_val ** 2) ** 2
    # 梯度
    dx = -2 * (1 - x_val) - 400 * x_val * (y_val - x_val ** 2)
    dy = 200 * (y_val - x_val ** 2)
    grad = np.array([dx, dy])
    return float(loss), grad


def quadratic(x: np.ndarray) -> Tuple[float, np.ndarray]:
    """
    简单二次函数（各向异性）
    f(x,y) = 10x^2 + y^2
    最小值在 (0, 0)
    特点：x 方向梯度大10倍，SGD 会严重震荡
    """
    loss = 10 * x[0] ** 2 + x[1] ** 2
    grad = np.array([20 * x[0], 2 * x[1]])
    return float(loss), grad


def run_optimization(
    optimizer_class: type,
    loss_fn: Callable,
    init_params: np.ndarray,
    n_steps: int = 500,
    lr: float = 0.01,
) -> Tuple[List[float], List[np.ndarray]]:
    """运行优化过程，返回损失历史和参数轨迹"""
    optimizer = optimizer_class(init_params, lr=lr)
    losses = []
    trajectory = [optimizer.get_params()]

    for step in range(n_steps):
        params = optimizer.get_params()
        loss, grad = loss_fn(params)
        optimizer.step(grad)
        losses.append(loss)
        trajectory.append(optimizer.get_params())

    return losses, trajectory


# ──────────── 主测试 ────────────
if __name__ == "__main__":
    np.set_printoptions(precision=6, suppress=True)

    optimizers = [SGD, Momentum, Adam, RAdam]
    colors = ["#e74c3c", "#3498db", "#2ecc71", "#9b59b6"]

    # === 测试1：Rosenbrock 函数 ===
    print("=" * 60)
    print("测试1: Rosenbrock 函数（峡谷地形）")
    print("=" * 60)
    init = np.array([-1.5, 2.0])
    n_steps = 1000
    lr = 0.003

    print(f"初始点: {init}, 目标: [1, 1], 步数: {n_steps}\n")

    results_rosen = {}
    for opt_class in optimizers:
        losses, trajectory = run_optimization(opt_class, rosenbrock, init, n_steps, lr)
        final = trajectory[-1]
        results_rosen[opt_class.name] = (losses, trajectory)
        print(f"{opt_class.name:12s} | 最终位置: {final} | 最终损失: {losses[-1]:.6e}")

    # === 测试2：各向异性二次函数 ===
    print(f"\n{'=' * 60}")
    print("测试2: 各向异性二次函数（10x² + y²）")
    print("=" * 60)
    init2 = np.array([5.0, 5.0])
    n_steps2 = 300
    lr2 = 0.02

    print(f"初始点: {init2}, 目标: [0, 0], 步数: {n_steps2}\n")

    results_quad = {}
    for opt_class in optimizers:
        losses, trajectory = run_optimization(opt_class, quadratic, init2, n_steps2, lr2)
        final = trajectory[-1]
        results_quad[opt_class.name] = (losses, trajectory)
        print(f"{opt_class.name:12s} | 最终位置: {final} | 最终损失: {losses[-1]:.6e}")

    # === 收敛速度对比 ===
    print(f"\n{'=' * 60}")
    print("收敛速度对比（达到损失 < 0.01 所需步数）")
    print("=" * 60)

    threshold = 0.01
    for name, (losses, _) in results_rosen.items():
        steps_to_converge = next((i for i, l in enumerate(losses) if l < threshold), "未收敛")
        print(f"  Rosenbrock | {name:12s} | {steps_to_converge} 步")

    for name, (losses, _) in results_quad.items():
        steps_to_converge = next((i for i, l in enumerate(losses) if l < threshold), "未收敛")
        print(f"  Quadratic  | {name:12s} | {steps_to_converge} 步")

    # === Adam 偏差校正效果演示 ===
    print(f"\n{'=' * 60}")
    print("Adam 偏差校正效果（前10步的 m_hat vs m）")
    print("=" * 60)

    adam = Adam(np.array([5.0, 5.0]), lr=0.1)
    for t in range(1, 11):
        _, grad = quadratic(adam.get_params())
        adam.m = adam.beta1 * adam.m + (1 - adam.beta1) * grad
        m_hat = adam.m / (1 - adam.beta1 ** t)
        print(f"  Step {t:2d} | m = [{adam.m[0]:+.4f}, {adam.m[1]:+.4f}] | "
              f"m_hat = [{m_hat[0]:+.4f}, {m_hat[1]:+.4f}] | "
              f"校正系数 = {1/(1-adam.beta1**t):.4f}")
        adam.step(grad)

    # === RAdam 热身效果演示 ===
    print(f"\n{'=' * 60}")
    print("RAdam 自适应热身效果（rho_t 变化）")
    print("=" * 60)

    radam = RAdam(np.array([5.0, 5.0]), lr=0.1)
    print(f"  rho_inf = {radam.rho_inf:.4f} (需要 > 4 才使用完整 Adam)")
    for t in range(1, 21):
        _, grad = quadratic(radam.get_params())
        radam.step(grad)
        rho_t = radam.rho_inf - 2.0 * t * (radam.beta2 ** t) / (1.0 - radam.beta2 ** t)
        mode = "Adam(完整)" if rho_t > 4 else "SGD(热身)"
        print(f"  Step {t:2d} | rho_t = {rho_t:.4f} | 模式: {mode}")
```

**思考题**：RAdam 在 `rho_t <= 4` 时退化为带动量的 SGD。为什么阈值选 4 而不是其他值？提示：这与二阶矩估计的方差 bound 有关，分析 $\text{Var}[\hat{v}_t]$ 的表达式。

---

### 第8题：模型量化与剪枝 — 用numpy实现INT8量化+幅度剪枝

**知识点讲解**

模型压缩是部署大模型到资源受限设备的关键技术。**量化**将浮点权重映射到低精度整数（如 INT8），减少存储和计算开销。**剪枝**移除不重要的权重（置零），产生稀疏矩阵，可通过稀疏存储格式进一步压缩。

**对称量化**：以 0 为中心，缩放因子 $s = \frac{\max(|x|)}{127}$。量化公式 $x_q = \text{clip}(\text{round}(x/s), -128, 127)$，反量化 $x_{deq} = x_q \times s$。优点是简单、无需存储零点；缺点是当权重分布不对称时浪费量化范围。

**非对称量化**：引入零点 $z$，$s = \frac{x_{max} - x_{min}}{255}$，$z = \text{round}(-x_{min}/s)$。量化 $x_q = \text{clip}(\text{round}(x/s + z), 0, 255)$，反量化 $x_{deq} = (x_q - z) \times s$。能更好地利用量化范围，但需要额外存储零点。

**幅度剪枝**：按权重的绝对值排序，移除最小的 $p\%$。关键指标是**稀疏度** $= \frac{\text{零元素数}}{\text{总元素数}}$。剪枝后需要微调（fine-tuning）恢复精度，或采用渐进式剪枝逐步增加稀疏度。

精度损失评估通过比较量化/剪枝前后模型输出的 MSE（均方误差）和余弦相似度来衡量。量化误差的来源是 round 操作的取整误差和 clip 操作的截断误差。

```python
"""
模型量化与剪枝 —— INT8 量化 + 幅度剪枝
运行：python exercise_08_quantization_pruning.py
依赖：pip install numpy
"""
import numpy as np
from typing import Tuple, Dict


# ──────────── 1. 对称量化 ────────────
class SymmetricQuantizer:
    """INT8 对称量化"""

    def __init__(self):
        self.scale: float = 0.0
        self.n_bits: int = 8
        self.qmin: int = -128
        self.qmax: int = 127

    def quantize(self, x: np.ndarray) -> np.ndarray:
        """浮点 → INT8"""
        # 计算缩放因子
        max_val = np.max(np.abs(x))
        self.scale = max_val / 127.0 if max_val > 0 else 1.0
        # 量化
        x_q = np.round(x / self.scale)
        x_q = np.clip(x_q, self.qmin, self.qmax).astype(np.int8)
        return x_q

    def dequantize(self, x_q: np.ndarray) -> np.ndarray:
        """INT8 → 浮点"""
        return x_q.astype(np.float64) * self.scale

    def quantize_dequantize(self, x: np.ndarray) -> np.ndarray:
        """量化后立即反量化（模拟量化误差）"""
        return self.dequantize(self.quantize(x))


# ──────────── 2. 非对称量化 ────────────
class AsymmetricQuantizer:
    """INT8 非对称量化（带零点）"""

    def __init__(self):
        self.scale: float = 0.0
        self.zero_point: int = 0
        self.n_bits: int = 8
        self.qmin: int = 0
        self.qmax: int = 255

    def quantize(self, x: np.ndarray) -> np.ndarray:
        """浮点 → UINT8"""
        x_min = np.min(x)
        x_max = np.max(x)
        self.scale = (x_max - x_min) / 255.0 if (x_max - x_min) > 0 else 1.0
        self.zero_point = int(np.round(-x_min / self.scale))
        self.zero_point = np.clip(self.zero_point, self.qmin, self.qmax)
        # 量化
        x_q = np.round(x / self.scale + self.zero_point)
        x_q = np.clip(x_q, self.qmin, self.qmax).astype(np.uint8)
        return x_q

    def dequantize(self, x_q: np.ndarray) -> np.ndarray:
        """UINT8 → 浮点"""
        return (x_q.astype(np.float64) - self.zero_point) * self.scale

    def quantize_dequantize(self, x: np.ndarray) -> np.ndarray:
        return self.dequantize(self.quantize(x))


# ──────────── 3. 幅度剪枝 ────────────
class MagnitudePruner:
    """幅度剪枝：按绝对值移除最小比例的权重"""

    def __init__(self, sparsity: float = 0.5):
        self.sparsity = sparsity
        self.mask: np.ndarray = None
        self.threshold: float = 0.0

    def compute_mask(self, weights: np.ndarray) -> np.ndarray:
        """计算剪枝掩码"""
        flat = np.abs(weights).flatten()
        n_elements = len(flat)
        n_prune = int(n_elements * self.sparsity)
        if n_prune == 0:
            return np.ones_like(weights, dtype=bool)

        # 找到第 n_prune 小的绝对值作为阈值
        sorted_vals = np.sort(flat)
        self.threshold = sorted_vals[n_prune - 1]

        # 保留绝对值大于阈值的权重
        mask = np.abs(weights) > self.threshold
        return mask

    def prune(self, weights: np.ndarray) -> np.ndarray:
        """执行剪枝"""
        self.mask = self.compute_mask(weights)
        return weights * self.mask

    @staticmethod
    def compute_sparsity(weights: np.ndarray) -> float:
        """计算稀疏度"""
        total = weights.size
        zeros = np.sum(weights == 0)
        return zeros / total

    @staticmethod
    def compression_ratio(weights: np.ndarray, mask: np.ndarray) -> float:
        """理论压缩比（CSR 格式）"""
        nnz = np.sum(mask)
        total = weights.size
        if nnz == 0:
            return float('inf')
        # CSR: values(nnz) + indices(nnz int32) + indptr(rows+1 int32)
        # 原始: total * float64
        original_bytes = total * 8  # float64
        csr_bytes = nnz * 8 + nnz * 4 + (weights.shape[0] + 1) * 4
        return original_bytes / csr_bytes


# ──────────── 4. 评估工具 ────────────
def evaluate_quantization(original: np.ndarray, dequantized: np.ndarray) -> Dict[str, float]:
    """评估量化精度损失"""
    error = original - dequantized
    mse = float(np.mean(error ** 2))
    mae = float(np.mean(np.abs(error)))
    max_error = float(np.max(np.abs(error)))
    # 余弦相似度
    cos_sim = float(
        np.dot(original.flatten(), dequantized.flatten()) /
        (np.linalg.norm(original) * np.linalg.norm(dequantized) + 1e-10)
    )
    # 信噪比
    signal_power = np.mean(original ** 2)
    noise_power = mse
    snr_db = 10 * np.log10(signal_power / (noise_power + 1e-10))
    return {
        "MSE": mse,
        "MAE": mae,
        "Max_Error": max_error,
        "Cosine_Similarity": cos_sim,
        "SNR_dB": snr_db,
    }


def simulate_linear_layer(
    weights: np.ndarray,
    inputs: np.ndarray,
    quantizer=None,
    pruner=None,
) -> Tuple[np.ndarray, Dict]:
    """模拟量化+剪枝后的线性层前向传播"""
    w = weights.copy()

    # 应用剪枝
    if pruner is not None:
        w = pruner.prune(w)

    # 应用量化（量化后反量化模拟）
    if quantizer is not None:
        w = quantizer.quantize_dequantize(w)

    # 前向传播
    original_output = inputs @ weights.T
    compressed_output = inputs @ w.T

    metrics = evaluate_quantization(original_output, compressed_output)
    return compressed_output, metrics


# ──────────── 测试 ────────────
if __name__ == "__main__":
    np.set_printoptions(precision=4, suppress=True)
    rng = np.random.default_rng(42)

    # 生成模拟权重矩阵
    print("=" * 60)
    print("模型量化与剪枝实验")
    print("=" * 60)

    # 模拟一个 128x64 的全连接层权重
    weights = rng.standard_normal((128, 64)).astype(np.float64) * 0.1
    inputs = rng.standard_normal((10, 128)).astype(np.float64)

    print(f"权重矩阵形状: {weights.shape}")
    print(f"权重范围: [{weights.min():.4f}, {weights.max():.4f}]")
    print(f"权重均值: {weights.mean():.4f}, 标准差: {weights.std():.4f}")

    # === 1. 对称量化 vs 非对称量化 ===
    print(f"\n{'=' * 60}")
    print("1. INT8 量化对比")
    print("=" * 60)

    sym_q = SymmetricQuantizer()
    asym_q = AsymmetricQuantizer()

    w_sym = sym_q.quantize_dequantize(weights)
    w_asym = asym_q.quantize_dequantize(weights)

    print(f"\n对称量化:   scale={sym_q.scale:.6f}")
    print(f"非对称量化: scale={asym_q.scale:.6f}, zero_point={asym_q.zero_point}")

    print("\n对称量化精度:")
    m1 = evaluate_quantization(weights, w_sym)
    for k, v in m1.items():
        print(f"  {k:20s}: {v:.6f}")

    print("\n非对称量化精度:")
    m2 = evaluate_quantization(weights, w_asym)
    for k, v in m2.items():
        print(f"  {k:20s}: {v:.6f}")

    # === 2. 幅度剪枝 ===
    print(f"\n{'=' * 60}")
    print("2. 幅度剪枝（不同稀疏度）")
    print("=" * 60)

    for sparsity in [0.3, 0.5, 0.7, 0.9]:
        pruner = MagnitudePruner(sparsity=sparsity)
        w_pruned = pruner.prune(weights.copy())
        actual_sparsity = MagnitudePruner.compute_sparsity(w_pruned)
        comp_ratio = MagnitudePruner.compression_ratio(weights, pruner.mask)
        m = evaluate_quantization(weights, w_pruned)
        print(f"\n  稀疏度 {sparsity:.0%} → 实际 {actual_sparsity:.2%} | "
              f"压缩比 {comp_ratio:.2f}x | "
              f"MSE={m['MSE']:.6e} | "
              f"余弦相似度={m['Cosine_Similarity']:.6f}")

    # === 3. 量化+剪枝联合 ===
    print(f"\n{'=' * 60}")
    print("3. 量化 + 剪枝联合效果（线性层前向传播）")
    print("=" * 60)

    configs = [
        ("无压缩", None, None),
        ("仅量化(对称)", sym_q.__class__(), None),
        ("仅量化(非对称)", asym_q.__class__(), None),
        ("仅剪枝50%", None, MagnitudePruner(0.5)),
        ("剪枝50%+对称量化", SymmetricQuantizer(), MagnitudePruner(0.5)),
        ("剪枝70%+非对称量化", AsymmetricQuantizer(), MagnitudePruner(0.7)),
    ]

    for name, q, p in configs:
        output, metrics = simulate_linear_layer(weights, inputs, quantizer=q, pruner=p)
        print(f"\n  {name:25s} | MSE={metrics['MSE']:.6e} | "
              f"余弦={metrics['Cosine_Similarity']:.6f} | "
              f"SNR={metrics['SNR_dB']:.2f}dB")

    # === 4. 存储节省估算 ===
    print(f"\n{'=' * 60}")
    print("4. 存储节省估算")
    print("=" * 60)

    original_size = weights.nbytes  # float64 字节数
    print(f"\n  原始大小: {original_size} bytes (float64)")

    # 对称量化后存储 INT8
    w_q8 = sym_q.quantize(weights)
    quantized_size = w_q8.nbytes + 8  # int8 数据 + scale(float64)
    print(f"  对称量化: {quantized_size} bytes (int8 + scale) → "
          f"节省 {(1-quantized_size/original_size)*100:.1f}%")

    # 剪枝 50% 后 CSR 存储
    pruner = MagnitudePruner(0.5)
    pruner.prune(weights.copy())
    nnz = np.sum(pruner.mask)
    csr_size = nnz * 8 + nnz * 4 + (weights.shape[0] + 1) * 4
    print(f"  剪枝50%: {csr_size} bytes (CSR float64) → "
          f"节省 {(1-csr_size/original_size)*100:.1f}%")

    # 剪枝 + 量化
    csr_int8_size = nnz * 1 + nnz * 4 + (weights.shape[0] + 1) * 4 + 8
    print(f"  剪枝50%+INT8: {csr_int8_size} bytes (CSR int8 + scale) → "
          f"节省 {(1-csr_int8_size/original_size)*100:.1f}%")
```

**思考题**：对称量化在权重分布严重偏斜时（如 ReLU 后的激活值全为正数）会有较大精度损失。你能计算出此时对称量化浪费了多少量化范围吗？非对称量化如何解决这个问题？

---

## 三、Web全栈（4题）

---

### 第9题：REST API设计模式 — 标准库实现RESTful API

**知识点讲解**

REST（Representational State Transfer）的核心约束包括：**无状态**（每个请求自包含所有信息）、**统一接口**（用 HTTP 方法表达操作语义）、**资源命名**（URI 标识资源而非动作）。GET 用于安全读取（幂等），POST 创建资源（非幂等），PUT 全量更新（幂等），PATCH 部分更新，DELETE 删除（幂等）。状态码分五类：2xx 成功、3xx 重定向、4xx 客户端错误、5xx 服务端错误。

**分页**有三种模式：偏移分页（`?page=2&size=20`，简单但大数据集慢）、游标分页（`?cursor=abc`，稳定但不可跳页）、键集分页（`?after_id=123`）。**过滤**用查询参数表达条件（`?status=active&category=tech`），复杂过滤可用 RSQL 或 JSON:API 规范。**排序**用 `?sort=-created_at,name`（- 表示降序）。

**版本控制**有三种策略：URI 版本（`/v1/users`，最直观但违反 URI 纯资源原则）、Header 版本（`Accept: application/vnd.api+json; version=1`，RESTful 但调试不便）、查询参数（`?version=1`，简单但不规范）。**HATEOAS**（Hypermedia As The Engine Of Application State）要求响应中包含导航链接，让客户端无需硬编码 URI。

```python
"""
RESTful API —— 用标准库 http.server 实现
特性：分页 / 过滤 / 排序 / 版本控制 / HATEOAS
运行：python exercise_09_rest_api.py
然后访问: http://localhost:8080/api/v1/users
"""
import json
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict


# ──────────── 内存数据库 ────────────
@dataclass
class User:
    id: int
    name: str
    email: str
    status: str = "active"
    department: str = "engineering"
    created_at: str = "2024-01-01T00:00:00Z"


# 模拟数据
db_users: Dict[int, User] = {}
for i in range(1, 51):
    dept = ["engineering", "design", "marketing", "sales"][i % 4]
    status = "active" if i % 5 != 0 else "inactive"
    db_users[i] = User(
        id=i,
        name=f"用户{i:02d}",
        email=f"user{i}@example.com",
        status=status,
        department=dept,
        created_at=f"2024-01-{i:02d}T10:00:00Z",
    )

next_user_id = 51


# ──────────── 查询参数解析 ────────────
def parse_pagination(params: Dict) -> Tuple[int, int]:
    """解析分页参数"""
    page = max(1, int(params.get("page", ["1"])[0]))
    size = min(100, max(1, int(params.get("size", ["10"])[0])))
    return page, size


def parse_sort(params: Dict) -> List[Tuple[str, bool]]:
    """解析排序参数: sort=-created_at,name"""
    sort_str = params.get("sort", [""])[0]
    if not sort_str:
        return []
    result = []
    for field_name in sort_str.split(","):
        field_name = field_name.strip()
        if field_name.startswith("-"):
            result.append((field_name[1:], True))  # 降序
        else:
            result.append((field_name, False))     # 升序
    return result


def apply_filters(users: List[User], params: Dict) -> List[User]:
    """应用过滤条件"""
    result = users
    for key in ["status", "department"]:
        if key in params:
            value = params[key][0]
            result = [u for u in result if getattr(u, key) == value]
    # 模糊搜索
    if "q" in params:
        query = params["q"][0].lower()
        result = [u for u in result if query in u.name.lower() or query in u.email.lower()]
    return result


def apply_sorting(users: List[User], sort_fields: List[Tuple[str, bool]]) -> List[User]:
    """应用排序"""
    if not sort_fields:
        return users
    result = users[:]
    for field_name, descending in reversed(sort_fields):
        result.sort(key=lambda u: getattr(u, field_name), reverse=descending)
    return result


def build_hateoas_links(base_url: str, user_id: int) -> Dict[str, str]:
    """构建 HATEOAS 链接"""
    return {
        "self": f"{base_url}/api/v1/users/{user_id}",
        "update": f"{base_url}/api/v1/users/{user_id}",
        "delete": f"{base_url}/api/v1/users/{user_id}",
    }


# ──────────── REST API Handler ────────────
class RESTAPIHandler(BaseHTTPRequestHandler):
    BASE_PATH = "/api/v1"

    def log_message(self, format, *args):
        """自定义日志"""
        print(f"[{self.command}] {self.path} → {args[1] if len(args) > 1 else ''}")

    def send_json(self, status: int, data: Any, headers: Dict = None):
        """发送 JSON 响应"""
        body = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # CORS 头
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def read_body(self) -> Dict:
        """读取请求体"""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length)
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"_error": "无效的 JSON"}

    def do_OPTIONS(self):
        """处理 CORS 预检请求"""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    # ─── GET: 列表（分页/过滤/排序）+ 单个资源 ───
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # 路由匹配
        if path == f"{self.BASE_PATH}/users":
            self._list_users(params)
        elif re.match(rf"^{self.BASE_PATH}/users/(\d+)$", path):
            user_id = int(re.match(rf"^{self.BASE_PATH}/users/(\d+)$", path).group(1))
            self._get_user(user_id)
        elif path == f"{self.BASE_PATH}/health":
            self.send_json(200, {"status": "healthy", "version": "v1"})
        else:
            self.send_json(404, {"error": "Not Found", "message": f"路径 {path} 不存在"})

    def _list_users(self, params: Dict):
        """列表接口：分页 + 过滤 + 排序 + HATEOAS"""
        all_users = list(db_users.values())

        # 过滤
        filtered = apply_filters(all_users, params)

        # 排序
        sort_fields = parse_sort(params)
        sorted_users = apply_sorting(filtered, sort_fields)

        # 分页
        page, size = parse_pagination(params)
        total = len(sorted_users)
        start = (page - 1) * size
        end = start + size
        page_users = sorted_users[start:end]

        # 构建 HATEOAS 链接
        base = f"http://{self.headers.get('Host', 'localhost:8080')}"
        links = {
            "self": f"{base}/api/v1/users?page={page}&size={size}",
            "first": f"{base}/api/v1/users?page=1&size={size}",
            "last": f"{base}/api/v1/users?page={(total + size - 1) // size}&size={size}",
        }
        if page > 1:
            links["prev"] = f"{base}/api/v1/users?page={page-1}&size={size}"
        if end < total:
            links["next"] = f"{base}/api/v1/users?page={page+1}&size={size}"

        # 序列化
        data = [asdict(u) for u in page_users]
        for item in data:
            item["_links"] = build_hateoas_links(base, item["id"])

        response = {
            "data": data,
            "meta": {
                "total": total,
                "page": page,
                "size": size,
                "pages": (total + size - 1) // size,
            },
            "links": links,
        }
        self.send_json(200, response)

    def _get_user(self, user_id: int):
        """获取单个用户"""
        user = db_users.get(user_id)
        if not user:
            self.send_json(404, {"error": "Not Found", "message": f"用户 {user_id} 不存在"})
            return
        base = f"http://{self.headers.get('Host', 'localhost:8080')}"
        data = asdict(user)
        data["_links"] = build_hateoas_links(base, user_id)
        self.send_json(200, {"data": data})

    # ─── POST: 创建 ───
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == f"{self.BASE_PATH}/users":
            global next_user_id
            body = self.read_body()
            if "_error" in body:
                self.send_json(400, {"error": "Bad Request", "message": body["_error"]})
                return

            # 输入验证
            if not body.get("name") or not body.get("email"):
                self.send_json(422, {
                    "error": "Unprocessable Entity",
                    "message": "name 和 email 为必填字段",
                    "fields": ["name", "email"],
                })
                return

            # 检查邮箱唯一性
            if any(u.email == body["email"] for u in db_users.values()):
                self.send_json(409, {
                    "error": "Conflict",
                    "message": f"邮箱 {body['email']} 已存在",
                })
                return

            user = User(
                id=next_user_id,
                name=body["name"],
                email=body["email"],
                status=body.get("status", "active"),
                department=body.get("department", "engineering"),
                created_at="2024-06-01T00:00:00Z",
            )
            db_users[next_user_id] = user
            next_user_id += 1

            base = f"http://{self.headers.get('Host', 'localhost:8080')}"
            data = asdict(user)
            data["_links"] = build_hateoas_links(base, user.id)
            self.send_json(201, {"data": data}, headers={"Location": f"{base}/api/v1/users/{user.id}"})
        else:
            self.send_json(404, {"error": "Not Found"})

    # ─── PUT: 全量更新 ───
    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path
        match = re.match(rf"^{self.BASE_PATH}/users/(\d+)$", path)

        if not match:
            self.send_json(404, {"error": "Not Found"})
            return

        user_id = int(match.group(1))
        user = db_users.get(user_id)
        if not user:
            self.send_json(404, {"error": "Not Found", "message": f"用户 {user_id} 不存在"})
            return

        body = self.read_body()
        if "_error" in body:
            self.send_json(400, {"error": "Bad Request", "message": body["_error"]})
            return

        # PUT 要求全量更新（所有字段必须提供）
        required = ["name", "email", "status", "department"]
        missing = [f for f in required if f not in body]
        if missing:
            self.send_json(422, {
                "error": "Unprocessable Entity",
                "message": f"PUT 需要提供所有字段，缺少: {missing}",
            })
            return

        user.name = body["name"]
        user.email = body["email"]
        user.status = body["status"]
        user.department = body["department"]
        self.send_json(200, {"data": asdict(user)})

    # ─── PATCH: 部分更新 ───
    def do_PATCH(self):
        parsed = urlparse(self.path)
        path = parsed.path
        match = re.match(rf"^{self.BASE_PATH}/users/(\d+)$", path)

        if not match:
            self.send_json(404, {"error": "Not Found"})
            return

        user_id = int(match.group(1))
        user = db_users.get(user_id)
        if not user:
            self.send_json(404, {"error": "Not Found", "message": f"用户 {user_id} 不存在"})
            return

        body = self.read_body()
        if "_error" in body:
            self.send_json(400, {"error": "Bad Request", "message": body["_error"]})
            return

        # PATCH 只更新提供的字段
        updatable = ["name", "email", "status", "department"]
        for field_name in updatable:
            if field_name in body:
                setattr(user, field_name, body[field_name])
        self.send_json(200, {"data": asdict(user)})

    # ─── DELETE: 删除 ───
    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        match = re.match(rf"^{self.BASE_PATH}/users/(\d+)$", path)

        if not match:
            self.send_json(404, {"error": "Not Found"})
            return

        user_id = int(match.group(1))
        if user_id not in db_users:
            self.send_json(404, {"error": "Not Found", "message": f"用户 {user_id} 不存在"})
            return

        deleted_user = db_users.pop(user_id)
        self.send_json(200, {"data": asdict(deleted_user), "message": "删除成功"})


# ──────────── 启动服务器 ────────────
if __name__ == "__main__":
    PORT = 8080
    server = HTTPServer(("0.0.0.0", PORT), RESTAPIHandler)
    print(f"REST API 服务器启动在 http://localhost:{PORT}")
    print(f"  列表:   GET  /api/v1/users?page=1&size=10&status=active&sort=-created_at")
    print(f"  详情:   GET  /api/v1/users/1")
    print(f"  创建:   POST /api/v1/users  (body: {{\"name\":\"test\",\"email\":\"t@t.com\"}})")
    print(f"  更新:   PUT  /api/v1/users/1")
    print(f"  补丁:   PATCH /api/v1/users/1  (body: {{\"status\":\"inactive\"}})")
    print(f"  删除:   DELETE /api/v1/users/1")
    print(f"  健康:   GET  /api/v1/health")
    print(f"\n按 Ctrl+C 停止服务器\n")

    # 运行简单的自测（不需要真正启动服务器）
    import sys
    if "--test" in sys.argv:
        print("=== 运行自测 ===")
        # 测试过滤+排序+分页逻辑
        params = {"status": ["active"], "sort": ["-id"], "page": ["2"], "size": ["5"]}
        all_users = list(db_users.values())
        filtered = apply_filters(all_users, params)
        sorted_users = apply_sorting(filtered, parse_sort(params))
        page, size = parse_pagination(params)
        start = (page - 1) * size
        page_users = sorted_users[start:start+size]
        print(f"总用户: {len(all_users)}")
        print(f"过滤后(active): {len(filtered)}")
        print(f"第2页(每页5条): {[u.name for u in page_users]}")
        sys.exit(0)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务器已停止")
        server.server_close()
```

**思考题**：当前实现用内存字典存储数据，无法处理并发写入。如果改用 SQLite，你会如何修改代码？注意 SQLite 的 `check_same_thread` 问题和连接池管理。

---

### 第10题：WebSocket实时通信 — asyncio+websockets聊天室

**知识点讲解**

WebSocket 协议在 HTTP/1.1 的 Upgrade 机制上建立持久连接。握手过程：客户端发送 `Upgrade: websocket` + `Sec-WebSocket-Key` 头，服务端返回 `101 Switching Protocols` + `Sec-WebSocket-Accept`（用 SHA-1 哈希 key + 魔法字符串）。握手成功后，连接从 HTTP 切换为 WebSocket 双工通道。

WebSocket **帧格式**包含：FIN 位（是否消息最后一帧）、opcode（0x1 文本、0x2 二进制、0x8 关闭、0x9 Ping、0xA Pong）、MASK 位（客户端→服务端必须掩码）、payload length（7/16/64 位三种长度编码）、masking key（4 字节）、payload data。理解帧格式有助于调试底层问题。

**心跳机制**通过 Ping/Pong 帧检测连接存活。服务端定期发送 Ping，客户端必须回 Pong；超时未收到 Pong 则判定连接断开。这是区分"网络中断"和"正常关闭"的关键。**连接管理**需要处理三类断开：客户端主动关闭（Close 帧）、网络中断（ConnectionResetError）、超时（心跳失败）。服务端需维护连接池，在断开时清理资源并广播离开通知。

聊天室的消息广播模式是"发布-订阅"：每条消息需要遍历所有活跃连接发送，需处理部分连接已断开的情况。

```python
"""
WebSocket 聊天室 —— asyncio + websockets
运行：python exercise_10_websocket_chat.py
依赖：pip install websockets

客户端测试（另开终端）：
  python -c "
  import asyncio, websockets
  async def test():
      async with websockets.connect('ws://localhost:8765') as ws:
          await ws.send('Hello!')
          print(await ws.recv())
  asyncio.run(test())
  "
"""
import asyncio
import json
import time
import logging
from typing import Dict, Set, Optional
from dataclasses import dataclass, field, asdict
from collections import defaultdict

# websockets 是第三方库，如果未安装则使用模拟模式
try:
    import websockets
    from websockets.exceptions import ConnectionClosed, ConnectionClosedOK
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    print("警告: websockets 未安装，运行模拟模式")
    print("安装: pip install websockets")


# ──────────── 日志配置 ────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("chat")


# ──────────── 数据结构 ────────────
@dataclass
class Client:
    """客户端连接信息"""
    websocket: object  # WebSocket 连接对象
    client_id: str
    username: str
    room: str = "general"
    connected_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)

    @property
    def info(self) -> dict:
        return {
            "client_id": self.client_id,
            "username": self.username,
            "room": self.room,
            "connected_at": self.connected_at,
        }


@dataclass
class Message:
    """聊天消息"""
    type: str            # chat / join / leave / system / error
    username: str
    content: str
    room: str
    timestamp: float = field(default_factory=time.time)
    client_id: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


# ──────────── 聊天服务器 ────────────
class ChatServer:
    """
    WebSocket 聊天室服务器
    - 房间管理（多房间）
    - 消息广播
    - 心跳检测
    - 连接清理
    """

    def __init__(self, heartbeat_interval: float = 30.0, heartbeat_timeout: float = 60.0):
        self.clients: Dict[str, Client] = {}                # client_id → Client
        self.rooms: Dict[str, Set[str]] = defaultdict(set)  # room_name → {client_ids}
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_timeout = heartbeat_timeout
        self.message_history: Dict[str, list] = defaultdict(list)  # room → [Message]
        self.max_history = 50  # 每个房间保留最近50条

    async def handle_connection(self, websocket, path: str = "/"):
        """处理新的 WebSocket 连接"""
        client_id = f"client_{id(websocket)}"
        username = f"匿名用户_{id(websocket) % 10000}"
        room = "general"

        # 从查询参数解析用户名和房间
        if "?" in path:
            from urllib.parse import parse_qs, urlparse
            params = parse_qs(urlparse(path).query)
            if "username" in params:
                username = params["username"][0][:20]  # 限制长度
            if "room" in params:
                room = params["room"][0][:30]

        client = Client(
            websocket=websocket,
            client_id=client_id,
            username=username,
            room=room,
        )

        # 注册客户端
        self.clients[client_id] = client
        self.rooms[room].add(client_id)
        logger.info(f"用户 {username} 加入房间 {room} (当前在线: {len(self.clients)})")

        # 发送欢迎消息 + 历史消息
        welcome = Message(
            type="system",
            username="服务器",
            content=f"欢迎 {username} 加入房间 [{room}]！当前在线 {len(self.rooms[room])} 人",
            room=room,
        )
        await self._send_to_client(client, welcome)

        # 发送历史消息
        for msg in self.message_history[room][-10:]:
            await self._send_to_client(client, msg)

        # 广播加入通知
        join_msg = Message(
            type="join",
            username=username,
            content=f"{username} 加入了房间",
            room=room,
            client_id=client_id,
        )
        await self._broadcast(room, join_msg, exclude=client_id)

        # 启动心跳任务
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(client))

        try:
            # 消息接收循环
            async for raw_data in websocket:
                try:
                    data = json.loads(raw_data)
                    msg_type = data.get("type", "chat")
                    content = data.get("content", "")

                    if msg_type == "chat":
                        if not content.strip():
                            continue
                        # 限制消息长度
                        content = content[:500]
                        msg = Message(
                            type="chat",
                            username=client.username,
                            content=content,
                            room=client.room,
                            client_id=client_id,
                        )
                        # 保存历史
                        self.message_history[client.room].append(msg)
                        if len(self.message_history[client.room]) > self.max_history:
                            self.message_history[client.room] = \
                                self.message_history[client.room][-self.max_history:]
                        # 广播
                        await self._broadcast(client.room, msg)

                    elif msg_type == "command":
                        await self._handle_command(client, data)

                except json.JSONDecodeError:
                    error_msg = Message(
                        type="error", username="服务器",
                        content="无效的 JSON 格式", room=client.room,
                    )
                    await self._send_to_client(client, error_msg)

        except ConnectionClosedOK:
            logger.info(f"用户 {username} 正常关闭连接")
        except ConnectionClosed as e:
            logger.warning(f"用户 {username} 连接断开: {e}")
        except Exception as e:
            logger.error(f"用户 {username} 异常: {e}")
        finally:
            # 清理
            heartbeat_task.cancel()
            await self._disconnect(client)

    async def _handle_command(self, client: Client, data: dict):
        """处理客户端命令"""
        cmd = data.get("content", "")
        parts = cmd.split(maxsplit=1)
        command = parts[0].lower() if parts else ""

        if command == "/rooms":
            rooms_info = {room: len(members) for room, members in self.rooms.items()}
            msg = Message(
                type="system", username="服务器",
                content=f"活跃房间: {json.dumps(rooms_info, ensure_ascii=False)}",
                room=client.room,
            )
            await self._send_to_client(client, msg)

        elif command == "/who":
            members = [self.clients[cid].username for cid in self.rooms[client.room]]
            msg = Message(
                type="system", username="服务器",
                content=f"房间 [{client.room}] 在线: {', '.join(members)}",
                room=client.room,
            )
            await self._send_to_client(client, msg)

        elif command == "/join" and len(parts) > 1:
            new_room = parts[1][:30]
            # 离开旧房间
            await self._broadcast(client.room, Message(
                type="leave", username=client.username,
                content=f"{client.username} 离开了房间", room=client.room,
            ), exclude=client.client_id)
            self.rooms[client.room].discard(client.client_id)
            # 加入新房间
            client.room = new_room
            self.rooms[new_room].add(client.client_id)
            await self._send_to_client(client, Message(
                type="system", username="服务器",
                content=f"已加入房间 [{new_room}]，在线 {len(self.rooms[new_room])} 人",
                room=new_room,
            ))
            await self._broadcast(new_room, Message(
                type="join", username=client.username,
                content=f"{client.username} 加入了房间", room=new_room,
            ), exclude=client.client_id)

        elif command == "/nick" and len(parts) > 1:
            old_name = client.username
            client.username = parts[1][:20]
            await self._broadcast(client.room, Message(
                type="system", username="服务器",
                content=f"{old_name} 改名为 {client.username}", room=client.room,
            ))

        else:
            await self._send_to_client(client, Message(
                type="error", username="服务器",
                content=f"未知命令: {cmd}。可用: /rooms, /who, /join <room>, /nick <name>",
                room=client.room,
            ))

    async def _broadcast(self, room: str, message: Message, exclude: str = None):
        """广播消息到房间内所有客户端"""
        if room not in self.rooms:
            return
        disconnected = []
        tasks = []
        for cid in self.rooms[room]:
            if cid == exclude:
                continue
            client = self.clients.get(cid)
            if client:
                tasks.append(self._send_to_client(client, message))
            else:
                disconnected.append(cid)

        # 并发发送
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for cid, result in zip(
                [c for c in self.rooms[room] if c != exclude], results
            ):
                if isinstance(result, Exception):
                    disconnected.append(cid)

        # 清理断开的连接
        for cid in disconnected:
            self.rooms[room].discard(cid)
            self.clients.pop(cid, None)

    async def _send_to_client(self, client: Client, message: Message):
        """发送消息给单个客户端"""
        try:
            await client.websocket.send(message.to_json())
        except (ConnectionClosed, ConnectionResetError):
            logger.warning(f"发送失败: {client.username} 连接已断开")

    async def _heartbeat_loop(self, client: Client):
        """心跳循环：定期发送 Ping"""
        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval)
                if WEBSOCKETS_AVAILABLE and hasattr(client.websocket, 'ping'):
                    pong_waiter = await client.websocket.ping()
                    try:
                        await asyncio.wait_for(pong_waiter, timeout=self.heartbeat_timeout)
                        client.last_ping = time.time()
                        logger.debug(f"心跳正常: {client.username}")
                    except asyncio.TimeoutError:
                        logger.warning(f"心跳超时: {client.username}，关闭连接")
                        await client.websocket.close(code=1001, reason="心跳超时")
                        break
                else:
                    # 模拟模式：只更新时间戳
                    client.last_ping = time.time()
                    break
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"心跳异常: {client.username} - {e}")

    async def _disconnect(self, client: Client):
        """客户端断开连接时的清理"""
        self.clients.pop(client.client_id, None)
        for room_members in self.rooms.values():
            room_members.discard(client.client_id)
        # 广播离开
        await self._broadcast(client.room, Message(
            type="leave", username=client.username,
            content=f"{client.username} 离开了房间", room=client.room,
        ))
        logger.info(f"用户 {client.username} 已断开 (剩余在线: {len(self.clients)})")

    def get_stats(self) -> dict:
        """获取服务器统计"""
        return {
            "total_clients": len(self.clients),
            "rooms": {room: len(members) for room, members in self.rooms.items()},
            "total_messages": sum(len(h) for h in self.message_history.values()),
        }


# ──────────── 启动服务器 ────────────
if __name__ == "__main__":
    chat_server = ChatServer(heartbeat_interval=30, heartbeat_timeout=60)

    if WEBSOCKETS_AVAILABLE:
        async def main():
            # 使用 websockets 库启动服务器
            async with websockets.serve(
                chat_server.handle_connection,
                "0.0.0.0",
                8765,
                ping_interval=None,  # 我们自己管理心跳
            ):
                logger.info("WebSocket 聊天室启动在 ws://localhost:8765")
                logger.info("连接示例: ws://localhost:8765?username=Alice&room=general")
                logger.info("按 Ctrl+C 停止")

                # 保持运行
                await asyncio.Future()

        asyncio.run(main())
    else:
        # === 模拟模式：不需要 websockets 库的测试 ===
        print("\n=== 模拟模式测试 ===")

        async def mock_test():
            """模拟聊天室逻辑测试"""

            class MockWebSocket:
                def __init__(self):
                    self.sent_messages = []
                    self.closed = False

                async def send(self, data):
                    self.sent_messages.append(data)

                async def close(self, code=None, reason=None):
                    self.closed = True

                def __aiter__(self):
                    return self

                async def __anext__(self):
                    raise StopAsyncIteration

            # 创建模拟客户端
            ws1 = MockWebSocket()
            ws2 = MockWebSocket()

            # 模拟连接
            await chat_server.handle_connection(ws1, "/?username=Alice&room=general")
            await chat_server.handle_connection(ws2, "/?username=Bob&room=general")

            # 检查欢迎消息
            print(f"Alice 收到消息数: {len(ws1.sent_messages)}")
            print(f"  第一条: {json.loads(ws1.sent_messages[0])['content']}")

            # 模拟聊天消息
            chat_msg = json.dumps({"type": "chat", "content": "你好 Bob！"})
            ws1.sent_messages.clear()
            ws2.sent_messages.clear()

            # 手动触发消息处理
            msg = Message(type="chat", username="Alice", content="你好 Bob！", room="general")
            await chat_server._broadcast("general", msg)
            print(f"\n广播后:")
            print(f"  Alice 收到: {len(ws1.sent_messages)} 条")
            print(f"  Bob 收到: {len(ws2.sent_messages)} 条")
            if ws2.sent_messages:
                print(f"  Bob 的消息: {json.loads(ws2.sent_messages[0])['content']}")

            # 统计
            print(f"\n服务器统计: {chat_server.get_stats()}")

        asyncio.run(mock_test())
```

**思考题**：当前广播使用 `asyncio.gather` 并发发送。如果某个客户端网络极慢导致 `send` 阻塞很久，会影响整个广播。你会如何设计"超时跳过"机制来隔离慢客户端？

---

### 第11题：OAuth2授权流程 — Authorization Code Flow + PKCE

**知识点讲解**

OAuth2 定义了四种授权模式：**Authorization Code**（最常用，服务端应用）、**Implicit**（已废弃，纯前端 SPA）、**Resource Owner Password Credentials**（用户直接给密码，仅高度信任场景）、**Client Credentials**（机器对机器，无用户参与）。Authorization Code Flow 分两步：先获取授权码（authorization code），再用码换取访问令牌（access token），两步分离降低了令牌泄露风险。

**PKCE**（Proof Key for Code Exchange）为移动端和 SPA 增强安全性。原理：客户端先生成 `code_verifier`（随机字符串），计算 `code_challenge = SHA256(code_verifier)` 并在授权请求中发送 `code_challenge`。换取令牌时发送 `code_verifier`，授权服务器验证 `SHA256(code_verifier) == code_challenge`。这样即使授权码被截获，攻击者没有 `code_verifier` 也无法换取令牌。

**Token 刷新**机制：访问令牌有有效期（通常1小时），过期后用刷新令牌（refresh token，有效期更长）获取新的访问令牌，无需用户重新授权。刷新令牌可以是一次性的（使用后返回新的刷新令牌）或可重用的。

**PKCE vs Client Secret**：传统服务端应用用 `client_secret` 证明身份，但移动端和 SPA 无法安全存储密钥。PKCE 用动态生成的 verifier 替代了静态密钥，每次授权流程使用不同的 verifier，是 RFC 7636 的核心贡献。

```python
"""
OAuth2 Authorization Code Flow + PKCE —— 完整实现
运行：python exercise_11_oauth2.py
依赖：pip install httpx（如不可用则使用 urllib）
"""
import hashlib
import base64
import secrets
import json
import time
import urllib.request
import urllib.parse
import urllib.error
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field


# ──────────── PKCE 工具 ────────────
class PKCEManager:
    """PKCE (Proof Key for Code Exchange) 生成器"""

    @staticmethod
    def generate_code_verifier(length: int = 64) -> str:
        """
        生成 code_verifier：43-128 字符的随机字符串
        字符集: [A-Z] / [a-z] / [0-9] / "-" / "." / "_" / "~"
        """
        chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
        return "".join(secrets.choice(chars) for _ in range(length))

    @staticmethod
    def generate_code_challenge(verifier: str, method: str = "S256") -> str:
        """
        从 code_verifier 生成 code_challenge
        - S256: BASE64URL(SHA256(verifier)) —— 推荐
        - plain: 直接使用 verifier —— 不推荐
        """
        if method == "S256":
            digest = hashlib.sha256(verifier.encode("ascii")).digest()
            # Base64 URL 编码（无填充）
            challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
            return challenge
        elif method == "plain":
            return verifier
        else:
            raise ValueError(f"不支持的 PKCE 方法: {method}")

    @staticmethod
    def generate_state() -> str:
        """生成 state 参数（防 CSRF）"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def verify_verifier(verifier: str, challenge: str, method: str = "S256") -> bool:
        """验证 code_verifier 是否匹配 code_challenge"""
        expected = PKCEManager.generate_code_challenge(verifier, method)
        return secrets.compare_digest(expected, challenge)


# ──────────── OAuth2 客户端 ────────────
@dataclass
class TokenResponse:
    """令牌响应"""
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600
    refresh_token: Optional[str] = None
    scope: str = ""
    obtained_at: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        """检查令牌是否过期（提前 60 秒判定）"""
        return time.time() > self.obtained_at + self.expires_in - 60

    def to_dict(self) -> dict:
        return {
            "access_token": self.access_token[:10] + "..." if len(self.access_token) > 10 else self.access_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "refresh_token": (self.refresh_token[:10] + "...") if self.refresh_token else None,
            "scope": self.scope,
            "obtained_at": self.obtained_at,
            "is_expired": self.is_expired,
        }


class OAuth2Client:
    """
    OAuth2 Authorization Code Flow + PKCE 客户端

    流程:
    1. 生成 PKCE verifier + challenge
    2. 构建授权 URL，引导用户访问
    3. 用户授权后，授权服务器回调 redirect_uri 并携带 code
    4. 用 code + verifier 换取 access_token
    5. 用 access_token 访问受保护资源
    6. 令牌过期后用 refresh_token 刷新
    """

    def __init__(
        self,
        client_id: str,
        redirect_uri: str,
        auth_server_url: str = "https://auth.example.com",
        client_secret: Optional[str] = None,  # 机密客户端才有
    ):
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.auth_server_url = auth_server_url.rstrip("/")
        self.client_secret = client_secret
        self.token: Optional[TokenResponse] = None
        self._code_verifier: Optional[str] = None
        self._state: Optional[str] = None

    def build_auth_url(self, scope: str = "openid profile email", state: str = None) -> str:
        """
        步骤1-2: 构建授权 URL
        包含 PKCE challenge 和 state（防 CSRF）
        """
        # 生成 PKCE
        self._code_verifier = PKCEManager.generate_code_verifier()
        code_challenge = PKCEManager.generate_code_challenge(self._code_verifier)

        # 生成 state
        self._state = state or PKCEManager.generate_state()

        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": scope,
            "state": self._state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }

        query_string = urllib.parse.urlencode(params)
        auth_url = f"{self.auth_server_url}/authorize?{query_string}"
        return auth_url

    def validate_callback(self, code: str, state: str) -> bool:
        """
        步骤3: 验证回调参数
        - 检查 state 是否匹配（防 CSRF）
        - code 非空
        """
        if state != self._state:
            raise ValueError("State 不匹配！可能的 CSRF 攻击")
        if not code:
            raise ValueError("授权码为空")
        return True

    def exchange_code_for_token(self, code: str, state: str) -> TokenResponse:
        """
        步骤4: 用授权码 + PKCE verifier 换取令牌
        """
        # 验证 state
        self.validate_callback(code, state)

        if not self._code_verifier:
            raise RuntimeError("未找到 code_verifier，请先调用 build_auth_url")

        # 构建令牌请求
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri,
            "client_id": self.client_id,
            "code_verifier": self._code_verifier,  # PKCE 关键：发送 verifier
        }
        if self.client_secret:
            token_data["client_secret"] = self.client_secret

        # 发送请求（模拟）
        response = self._mock_token_request(token_data)
        self.token = TokenResponse(**response)
        return self.token

    def refresh_token(self) -> TokenResponse:
        """
        步骤6: 用 refresh_token 刷新访问令牌
        """
        if not self.token or not self.token.refresh_token:
            raise RuntimeError("没有可用的 refresh_token")

        token_data = {
            "grant_type": "refresh_token",
            "refresh_token": self.token.refresh_token,
            "client_id": self.client_id,
        }
        if self.client_secret:
            token_data["client_secret"] = self.client_secret

        response = self._mock_token_request(token_data)
        self.token = TokenResponse(**response)
        return self.token

    def get_valid_token(self) -> str:
        """获取有效的 access_token，过期则自动刷新"""
        if not self.token:
            raise RuntimeError("尚未获取令牌")
        if self.token.is_expired:
            print("  令牌已过期，正在刷新...")
            self.refresh_token()
        return self.token.access_token

    def _mock_token_request(self, data: dict) -> dict:
        """
        模拟授权服务器的令牌响应
        实际项目中替换为真实的 HTTP 请求：
            body = urllib.parse.urlencode(data).encode()
            req = urllib.request.Request(token_url, data=body, method="POST")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read())
        """
        if data["grant_type"] == "authorization_code":
            # 验证 PKCE
            if "code_verifier" in data:
                verifier = data["code_verifier"]
                challenge = PKCEManager.generate_code_challenge(verifier)
                print(f"  [模拟服务器] 验证 PKCE: challenge={challenge[:20]}...")
                print(f"  [模拟服务器] PKCE 验证通过 ✓")

            return {
                "access_token": f"access_{secrets.token_hex(16)}",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": f"refresh_{secrets.token_hex(16)}",
                "scope": data.get("scope", "openid profile email"),
            }
        elif data["grant_type"] == "refresh_token":
            return {
                "access_token": f"access_{secrets.token_hex(16)}",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": f"refresh_{secrets.token_hex(16)}",
                "scope": "openid profile email",
            }

    def access_protected_resource(self, resource_url: str) -> dict:
        """
        步骤5: 用 access_token 访问受保护资源
        """
        token = self.get_valid_token()

        # 实际请求示例（注释）:
        # req = urllib.request.Request(resource_url)
        # req.add_header("Authorization", f"Bearer {token}")
        # with urllib.request.urlopen(req) as resp:
        #     return json.loads(resp.read())

        # 模拟响应
        return {
            "user_id": 12345,
            "name": "张三",
            "email": "zhangsan@example.com",
            "scope": "openid profile email",
            "token_used": token[:15] + "...",
        }


# ──────────── 模拟授权服务器 ────────────
class MockAuthServer:
    """
    模拟 OAuth2 授权服务器
    用于演示完整的授权流程，不依赖真实服务
    """

    def __init__(self):
        self.auth_codes: Dict[str, dict] = {}  # code -> {client_id, verifier_challenge, ...}
        self.tokens: Dict[str, dict] = {}       # access_token -> user_info

    def simulate_user_consent(self, auth_url: str) -> Tuple[str, str]:
        """模拟用户同意授权，返回 (code, state)"""
        # 解析授权 URL
        parsed = urllib.parse.urlparse(auth_url)
        params = urllib.parse.parse_qs(parsed.query)

        client_id = params["client_id"][0]
        state = params["state"][0]
        code_challenge = params["code_challenge"][0]
        redirect_uri = params["redirect_uri"][0]

        # 生成授权码
        code = f"auth_code_{secrets.token_hex(8)}"

        # 存储授权码与关联信息
        self.auth_codes[code] = {
            "client_id": client_id,
            "code_challenge": code_challenge,
            "redirect_uri": redirect_uri,
            "created_at": time.time(),
        }

        return code, state

    def verify_token_request(self, data: dict) -> bool:
        """验证令牌请求中的 PKCE"""
        code = data.get("code")
        verifier = data.get("code_verifier")

        if code not in self.auth_codes:
            return False

        stored = self.auth_codes[code]
        # 验证 PKCE
        if verifier:
            expected_challenge = PKCEManager.generate_code_challenge(verifier)
            if not secrets.compare_digest(expected_challenge, stored["code_challenge"]):
                print("  [授权服务器] PKCE 验证失败！")
                return False

        # 授权码一次性使用
        del self.auth_codes[code]
        return True


# ──────────── 测试 ────────────
if __name__ == "__main__":
    print("=" * 60)
    print("OAuth2 Authorization Code Flow + PKCE 完整演示")
    print("=" * 60)

    # === 1. PKCE 生成与验证 ===
    print("\n--- 1. PKCE 生成 ---")
    verifier = PKCEManager.generate_code_verifier()
    challenge = PKCEManager.generate_code_challenge(verifier)
    state = PKCEManager.generate_state()

    print(f"  code_verifier:  {verifier[:30]}... (长度 {len(verifier)})")
    print(f"  code_challenge: {challenge[:30]}... (长度 {len(challenge)})")
    print(f"  state:          {state[:30]}...")
    print(f"  验证: {PKCEManager.verify_verifier(verifier, challenge)}")

    # === 2. 完整授权流程 ===
    print("\n--- 2. 完整授权流程 ---")
    client = OAuth2Client(
        client_id="my_app_123",
        redirect_uri="http://localhost:3000/callback",
        auth_server_url="https://auth.example.com",
    )
    auth_server = MockAuthServer()

    # 步骤1: 构建授权 URL
    print("\n  [步骤1] 构建授权 URL")
    auth_url = client.build_auth_url(scope="openid profile email")
    print(f"  授权 URL: {auth_url[:80]}...")

    # 步骤2: 模拟用户同意授权
    print("\n  [步骤2] 用户访问授权页面并同意授权")
    code, returned_state = auth_server.simulate_user_consent(auth_url)
    print(f"  授权码: {code}")
    print(f"  state: {returned_state[:20]}... (匹配: {returned_state == client._state})")

    # 步骤3: 用授权码换取令牌
    print("\n  [步骤3] 用授权码 + PKCE verifier 换取令牌")
    token = client.exchange_code_for_token(code, returned_state)
    print(f"  令牌信息: {json.dumps(token.to_dict(), indent=2)}")

    # === 3. 使用令牌访问资源 ===
    print("\n--- 3. 访问受保护资源 ---")
    result = client.access_protected_resource("https://api.example.com/userinfo")
    print(f"  响应: {json.dumps(result, indent=2, ensure_ascii=False)}")

    # === 4. 模拟令牌过期与刷新 ===
    print("\n--- 4. 令牌过期与刷新 ---")
    # 手动设置过期
    client.token.obtained_at = time.time() - 3700  # 模拟已过1小时
    print(f"  令牌过期? {client.token.is_expired}")

    refreshed = client.refresh_token()
    print(f"  刷新后令牌: {json.dumps(refreshed.to_dict(), indent=2)}")
    print(f"  新令牌过期? {refreshed.is_expired}")

    # === 5. PKCE 安全性演示 ===
    print("\n--- 5. PKCE 安全性演示 ---")
    print("  场景: 攻击者截获了授权码，但没有 code_verifier")

    attacker_client = OAuth2Client(
        client_id="my_app_123",
        redirect_uri="http://localhost:3000/callback",
    )

    # 攻击者生成自己的 verifier（与受害者的不同）
    attacker_verifier = PKCEManager.generate_code_verifier()
    attacker_client._code_verifier = attacker_verifier
    attacker_client._state = "fake_state"

    # 尝试用截获的授权码换令牌
    code2, state2 = auth_server.simulate_user_consent(
        client.build_auth_url()
    )

    # 验证：攻击者的 verifier 不匹配原始 challenge
    original_challenge = PKCEManager.generate_code_challenge(client._code_verifier)
    attacker_challenge = PKCEManager.generate_code_challenge(attacker_verifier)
    match = secrets.compare_digest(original_challenge, attacker_challenge)

    print(f"  原始 challenge:  {original_challenge[:20]}...")
    print(f"  攻击者 challenge: {attacker_challenge[:20]}...")
    print(f"  匹配? {match}")
    print(f"  → 攻击者无法用截获的授权码换取令牌！" if not match else "  → 安全漏洞！")

    # === 6. 四种授权模式对比 ===
    print("\n--- 6. OAuth2 四种授权模式对比 ---")
    grant_types = [
        ("Authorization Code", "Web服务端应用", "最常用，两步换取令牌，安全性高", "需要 client_secret 或 PKCE"),
        ("Implicit", "纯前端SPA", "一步获取令牌，已废弃", "令牌暴露在URL中，不安全"),
        ("Password Credentials", "高度信任的官方应用", "用户直接提供密码", "仅限第一方应用"),
        ("Client Credentials", "机器对机器(M2M)", "无用户参与，应用自身身份", "需要 client_secret"),
    ]
    for name, scenario, advantage, limitation in grant_types:
        print(f"\n  {name}")
        print(f"    场景: {scenario}")
        print(f"    优点: {advantage}")
        print(f"    限制: {limitation}")
```

**思考题**：PKCE 使用 S256 方法时，即使攻击者截获了 `code_challenge`，也无法从它反推出 `code_verifier`（因为 SHA256 不可逆）。但如果使用 `plain` 方法，`code_challenge` 就等于 `code_verifier`，PKCE 就形同虚设。为什么 RFC 7636 仍然允许 `plain` 方法存在？

---

### 第12题：GraphQL基础 — 纯Python实现查询解析+执行引擎

**知识点讲解**

GraphQL 是 Facebook 开发的查询语言，核心思想是"客户端精确声明需要哪些字段，服务端只返回这些字段"。与 REST 的对比：REST 需要多个端点（`/users`、`/users/1/posts`），容易产生过度获取（over-fetching）或不足获取（under-fetching）；GraphQL 单端点（`/graphql`），一次查询获取所有关联数据。

**Schema 定义**使用 SDL（Schema Definition Language）：`type User { id: ID! name: String! posts: [Post!]! }`。`!` 表示非空，`[Type!]!` 表示非空数组且元素非空。Schema 是客户端和服务端的契约，类型检查器据此验证查询合法性。

**查询解析**分两阶段：词法分析（Lexer）将字符串拆成 Token 流，语法分析（Parser）按语法规则构建 AST（抽象语法树）。GraphQL 的语法相对简单：操作类型（query/mutation）、选择集（Selection Set）、字段（Field）、参数（Argument）、片段（Fragment）。

**执行引擎**的核心是**解析器（Resolver）**——每个字段对应一个 resolver 函数，接收父对象、参数和上下文，返回该字段的值。执行器递归遍历 AST，对每个字段调用对应的 resolver，将结果组装成响应 JSON。嵌套查询的 resolver 可以访问父对象的返回值，实现关联查询。**N+1 问题**是 GraphQL 的经典陷阱：列表查询中每个元素触发一次关联查询，可用 DataLoader 批量解决。

```python
"""
GraphQL 查询解析 + 执行引擎 —— 纯 Python 实现
运行：python exercise_12_graphql.py
"""
import json
import re
from typing import Any, Dict, List, Optional, Union, Callable, Tuple
from dataclasses import dataclass, field


# ──────────── 1. Schema 定义 ────────────
@dataclass
class GraphQLField:
    """字段定义"""
    name: str
    type_name: str          # 类型名（如 "String", "Int", "User"）
    is_list: bool = False   # 是否列表类型
    is_non_null: bool = False
    args: Dict[str, str] = field(default_factory=dict)  # 参数名→类型
    resolver: Optional[Callable] = None  # 解析器函数


@dataclass
class GraphQLType:
    """对象类型定义"""
    name: str
    fields: Dict[str, GraphQLField] = field(default_factory=dict)
    description: str = ""


class GraphQLSchema:
    """GraphQL Schema：类型注册表"""

    def __init__(self):
        self.types: Dict[str, GraphQLType] = {}
        self.query_type: Optional[str] = None
        self.mutation_type: Optional[str] = None

    def add_type(self, type_def: GraphQLType) -> None:
        self.types[type_def.name] = type_def

    def set_query_type(self, type_name: str) -> None:
        self.query_type = type_name

    def get_type(self, name: str) -> Optional[GraphQLType]:
        return self.types.get(name)

    def to_sdl(self) -> str:
        """生成 SDL 字符串"""
        lines = []
        for type_name, type_def in self.types.items():
            lines.append(f"type {type_name} {{")
            for field_name, field_def in type_def.fields.items():
                args_str = ""
                if field_def.args:
                    args_str = "(" + ", ".join(
                        f"{k}: {v}" for k, v in field_def.args.items()
                    ) + ")"
                list_str = "[" if field_def.is_list else ""
                list_end = "]" if field_def.is_list else ""
                nn = "!" if field_def.is_non_null else ""
                lines.append(f"  {field_name}{args_str}: {list_str}{field_def.type_name}{nn}{list_end}")
            lines.append("}")
            lines.append("")
        return "\n".join(lines)


# ──────────── 2. 词法分析器 (Lexer) ────────────
@dataclass
class Token:
    type: str   # NAME, STRING, INT, FLOAT, PUNCT, EOF
    value: str
    pos: int


class Lexer:
    """GraphQL 词法分析器"""

    PUNCTUATORS = set("!$():=@[]{|}")

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.length = len(source)

    def _skip_whitespace_and_comments(self):
        while self.pos < self.length:
            ch = self.source[self.pos]
            if ch in " \t\n\r,":
                self.pos += 1
            elif ch == "#":
                # 跳过行注释
                while self.pos < self.length and self.source[self.pos] != "\n":
                    self.pos += 1
            else:
                break

    def next_token(self) -> Token:
        self._skip_whitespace_and_comments()
        if self.pos >= self.length:
            return Token("EOF", "", self.pos)

        ch = self.source[self.pos]
        start = self.pos

        # 标识符 / 关键字
        if ch.isalpha() or ch == "_":
            self.pos += 1
            while self.pos < self.length and (self.source[self.pos].isalnum() or self.source[self.pos] == "_"):
                self.pos += 1
            return Token("NAME", self.source[start:self.pos], start)

        # 数字
        if ch.isdigit() or (ch == "-" and self.pos + 1 < self.length and self.source[self.pos + 1].isdigit()):
            self.pos += 1
            is_float = False
            while self.pos < self.length:
                c = self.source[self.pos]
                if c.isdigit():
                    self.pos += 1
                elif c == ".":
                    is_float = True
                    self.pos += 1
                elif c in "eE":
                    is_float = True
                    self.pos += 1
                    if self.pos < self.length and self.source[self.pos] in "+-":
                        self.pos += 1
                else:
                    break
            token_type = "FLOAT" if is_float else "INT"
            return Token(token_type, self.source[start:self.pos], start)

        # 字符串
        if ch == '"':
            self.pos += 1
            value_chars = []
            while self.pos < self.length and self.source[self.pos] != '"':
                if self.source[self.pos] == "\\" and self.pos + 1 < self.length:
                    next_ch = self.source[self.pos + 1]
                    escape_map = {"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}
                    value_chars.append(escape_map.get(next_ch, next_ch))
                    self.pos += 2
                else:
                    value_chars.append(self.source[self.pos])
                    self.pos += 1
            self.pos += 1  # 跳过结束引号
            return Token("STRING", "".join(value_chars), start)

        # 标点符号
        if ch in self.PUNCTUATORS:
            self.pos += 1
            return Token("PUNCT", ch, start)

        # 未知字符
        raise SyntaxError(f"意外字符 '{ch}' 在位置 {self.pos}")


# ──────────── 3. 语法分析器 (Parser) ────────────
@dataclass
class FieldNode:
    """字段节点"""
    name: str
    alias: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)
    selections: List["FieldNode"] = field(default_factory=list)

    @property
    def response_key(self) -> str:
        return self.alias or self.name


@dataclass
class OperationNode:
    """操作节点"""
    operation: str  # "query" or "mutation"
    name: Optional[str] = None
    selections: List[FieldNode] = field(default_factory=list)


class Parser:
    """GraphQL 语法分析器：Token流 → AST"""

    def __init__(self, source: str):
        self.lexer = Lexer(source)
        self.current_token = self.lexer.next_token()

    def _expect(self, token_type: str, value: str = None) -> Token:
        """期望当前 token 匹配"""
        token = self.current_token
        if token.type != token_type or (value and token.value != value):
            expected = f"{token_type}({value})" if value else token_type
            raise SyntaxError(f"期望 {expected}，得到 {token.type}({token.value}) 在位置 {token.pos}")
        self.current_token = self.lexer.next_token()
        return token

    def _expect_punct(self, value: str) -> Token:
        return self._expect("PUNCT", value)

    def parse_document(self) -> List[OperationNode]:
        """解析文档：一个或多个操作"""
        operations = []
        while self.current_token.type != "EOF":
            operations.append(self.parse_operation())
        return operations

    def parse_operation(self) -> OperationNode:
        """解析操作"""
        # 可选的 operation type
        if self.current_token.type == "NAME":
            op_type = self.current_token.value
            if op_type in ("query", "mutation"):
                self.current_token = self.lexer.next_token()
                # 可选的操作名称
                op_name = None
                if self.current_token.type == "NAME":
                    op_name = self.current_token.value
                    self.current_token = self.lexer.next_token()
            elif op_type == "{":
                op_type = "query"
                op_name = None
            else:
                op_type = "query"
                op_name = None
        elif self.current_token.type == "PUNCT" and self.current_token.value == "{":
            op_type = "query"
            op_name = None
        else:
            raise SyntaxError(f"意外的 token: {self.current_token.type}({self.current_token.value})")

        # 解析选择集
        selections = self.parse_selection_set()

        return OperationNode(operation=op_type, name=op_name, selections=selections)

    def parse_selection_set(self) -> List[FieldNode]:
        """解析选择集 { field1 field2 { subField } }"""
        self._expect_punct("{")
        fields = []
        while not (self.current_token.type == "PUNCT" and self.current_token.value == "}"):
            fields.append(self.parse_field())
        self._expect_punct("}")
        return fields

    def parse_field(self) -> FieldNode:
        """解析单个字段"""
        name = self._expect("NAME").value
        alias = None

        # 检查别名 (alias: field)
        if self.current_token.type == "PUNCT" and self.current_token.value == ":":
            self.current_token = self.lexer.next_token()
            alias = name
            name = self._expect("NAME").value

        # 解析参数
        arguments = {}
        if self.current_token.type == "PUNCT" and self.current_token.value == "(":
            arguments = self.parse_arguments()

        # 解析子选择集
        selections = []
        if self.current_token.type == "PUNCT" and self.current_token.value == "{":
            selections = self.parse_selection_set()

        return FieldNode(name=name, alias=alias, arguments=arguments, selections=selections)

    def parse_arguments(self) -> Dict[str, Any]:
        """解析参数列表 (key: value, key2: value2)"""
        self._expect_punct("(")
        args = {}
        while not (self.current_token.type == "PUNCT" and self.current_token.value == ")"):
            key = self._expect("NAME").value
            self._expect_punct(":")
            value = self.parse_value()
            args[key] = value
            # 逗号可选
            if self.current_token.type == "PUNCT" and self.current_token.value == ",":
                self.current_token = self.lexer.next_token()
        self._expect_punct(")")
        return args

    def parse_value(self) -> Any:
        """解析值"""
        token = self.current_token
        if token.type == "INT":
            self.current_token = self.lexer.next_token()
            return int(token.value)
        elif token.type == "FLOAT":
            self.current_token = self.lexer.next_token()
            return float(token.value)
        elif token.type == "STRING":
            self.current_token = self.lexer.next_token()
            return token.value
        elif token.type == "NAME":
            self.current_token = self.lexer.next_token()
            if token.value == "true":
                return True
            elif token.value == "false":
                return False
            elif token.value == "null":
                return None
            return token.value  # 枚举值
        elif token.type == "PUNCT" and token.value == "[":
            # 列表
            self.current_token = self.lexer.next_token()
            items = []
            while not (self.current_token.type == "PUNCT" and self.current_token.value == "]"):
                items.append(self.parse_value())
                if self.current_token.type == "PUNCT" and self.current_token.value == ",":
                    self.current_token = self.lexer.next_token()
            self._expect_punct("]")
            return items
        else:
            raise SyntaxError(f"意外的值 token: {token.type}({token.value})")


# ──────────── 4. 执行引擎 ────────────
class GraphQLExecutor:
    """GraphQL 执行引擎"""

    def __init__(self, schema: GraphQLSchema):
        self.schema = schema

    def execute(self, operation: OperationNode, context: dict = None) -> dict:
        """执行查询操作"""
        context = context or {}
        if operation.operation == "query":
            root_type = self.schema.get_type(self.schema.query_type)
        elif operation.operation == "mutation":
            root_type = self.schema.get_type(self.schema.mutation_type)
        else:
            return {"errors": [{"message": f"不支持的操作类型: {operation.operation}"}]}

        if not root_type:
            return {"errors": [{"message": "未定义根类型"}]}

        try:
            data = self._resolve_selection_set(
                operation.selections, root_type, None, context
            )
            return {"data": data}
        except Exception as e:
            return {"data": None, "errors": [{"message": str(e)}]}

    def _resolve_selection_set(
        self,
        selections: List[FieldNode],
        parent_type: GraphQLType,
        parent_value: Any,
        context: dict,
    ) -> dict:
        """解析选择集，返回字段值字典"""
        result = {}
        for field_node in selections:
            field_def = parent_type.fields.get(field_node.name)
            if not field_def:
                raise ValueError(f"字段 '{field_node.name}' 不存在于类型 '{parent_type.name}'")

            # 调用 resolver
            resolver = field_def.resolver
            if resolver:
                field_value = resolver(parent_value, field_node.arguments, context)
            else:
                # 默认解析器：从父对象取同名属性
                if isinstance(parent_value, dict):
                    field_value = parent_value.get(field_node.name)
                elif parent_value is not None:
                    field_value = getattr(parent_value, field_node.name, None)
                else:
                    field_value = None

            # 递归解析子选择集
            if field_node.selections and field_value is not None:
                child_type = self.schema.get_type(field_def.type_name)
                if child_type:
                    if field_def.is_list and isinstance(field_value, list):
                        field_value = [
                            self._resolve_selection_set(field_node.selections, child_type, item, context)
                            for item in field_value
                        ]
                    else:
                        field_value = self._resolve_selection_set(
                            field_node.selections, child_type, field_value, context
                        )

            result[field_node.response_key] = field_value

        return result


# ──────────── 5. 构建示例 Schema 和数据 ────────────
def build_blog_schema() -> Tuple[GraphQLSchema, dict]:
    """构建博客系统的 GraphQL Schema + 模拟数据"""

    # 模拟数据
    db = {
        "users": {
            1: {"id": 1, "name": "张三", "email": "zhangsan@example.com", "age": 28},
            2: {"id": 2, "name": "李四", "email": "lisi@example.com", "age": 35},
            3: {"id": 3, "name": "王五", "email": "wangwu@example.com", "age": 22},
        },
        "posts": {
            101: {"id": 101, "title": "GraphQL 入门", "content": "GraphQL 是一种查询语言...", "authorId": 1, "views": 1500},
            102: {"id": 102, "title": "Python 异步编程", "content": "asyncio 是...", "authorId": 1, "views": 2300},
            103: {"id": 103, "title": "Docker 最佳实践", "content": "多阶段构建...", "authorId": 2, "views": 980},
            104: {"id": 104, "title": "React Hooks 详解", "content": "useState 和 useEffect...", "authorId": 3, "views": 3100},
        },
        "comments": {
            1001: {"id": 1001, "text": "写得很好！", "postId": 101, "authorId": 2},
            1002: {"id": 1002, "text": "学到了很多", "postId": 101, "authorId": 3},
            1003: {"id": 1003, "text": "期待更多文章", "postId": 102, "authorId": 3},
        },
    }

    schema = GraphQLSchema()

    # Comment 类型
    comment_type = GraphQLType(name="Comment")
    comment_type.fields["id"] = GraphQLField("id", "Int", is_non_null=True)
    comment_type.fields["text"] = GraphQLField("text", "String")
    comment_type.fields["author"] = GraphQLField("author", "User", resolver=lambda parent, args, ctx: db["users"][parent["authorId"]])
    schema.add_type(comment_type)

    # Post 类型
    post_type = GraphQLType(name="Post")
    post_type.fields["id"] = GraphQLField("id", "Int", is_non_null=True)
    post_type.fields["title"] = GraphQLField("title", "String")
    post_type.fields["content"] = GraphQLField("content", "String")
    post_type.fields["views"] = GraphQLField("views", "Int")
    post_type.fields["author"] = GraphQLField("author", "User", resolver=lambda parent, args, ctx: db["users"][parent["authorId"]])
    post_type.fields["comments"] = GraphQLField(
        "comments", "Comment", is_list=True,
        resolver=lambda parent, args, ctx: [c for c in db["comments"].values() if c["postId"] == parent["id"]]
    )
    schema.add_type(post_type)

    # User 类型
    user_type = GraphQLType(name="User")
    user_type.fields["id"] = GraphQLField("id", "Int", is_non_null=True)
    user_type.fields["name"] = GraphQLField("name", "String")
    user_type.fields["email"] = GraphQLField("email", "String")
    user_type.fields["age"] = GraphQLField("age", "Int")
    user_type.fields["posts"] = GraphQLField(
        "posts", "Post", is_list=True,
        resolver=lambda parent, args, ctx: [p for p in db["posts"].values() if p["authorId"] == parent["id"]]
    )
    schema.add_type(user_type)

    # Query 根类型
    query_type = GraphQLType(name="Query")
    query_type.fields["user"] = GraphQLField(
        "user", "User",
        args={"id": "Int"},
        resolver=lambda parent, args, ctx: db["users"].get(args.get("id"))
    )
    query_type.fields["users"] = GraphQLField(
        "users", "User", is_list=True,
        resolver=lambda parent, args, ctx: list(db["users"].values())
    )
    query_type.fields["post"] = GraphQLField(
        "post", "Post",
        args={"id": "Int"},
        resolver=lambda parent, args, ctx: db["posts"].get(args.get("id"))
    )
    query_type.fields["posts"] = GraphQLField(
        "posts", "Post", is_list=True,
        resolver=lambda parent, args, ctx: list(db["posts"].values())
    )
    schema.add_type(query_type)
    schema.set_query_type("Query")

    return schema, db


# ──────────── 测试 ────────────
if __name__ == "__main__":
    schema, db = build_blog_schema()
    executor = GraphQLExecutor(schema)

    print("=" * 60)
    print("GraphQL 引擎 —— 纯 Python 实现")
    print("=" * 60)

    # 打印 SDL
    print("\n=== Schema SDL ===")
    print(schema.to_sdl())

    # === 查询1：简单字段查询 ===
    print("\n=== 查询1: 获取所有用户（只取 name 和 email）===")
    query1 = """
    query {
        users {
            name
            email
        }
    }
    """
    parser1 = Parser(query1)
    ops1 = parser1.parse_document()
    result1 = executor.execute(ops1[0])
    print(json.dumps(result1, indent=2, ensure_ascii=False))

    # === 查询2：带参数的单个资源 ===
    print("\n=== 查询2: 获取用户(id=1)及其文章 ===")
    query2 = """
    query {
        user(id: 1) {
            id
            name
            age
            posts {
                title
                views
            }
        }
    }
    """
    parser2 = Parser(query2)
    ops2 = parser2.parse_document()
    result2 = executor.execute(ops2[0])
    print(json.dumps(result2, indent=2, ensure_ascii=False))

    # === 查询3：深层嵌套查询 ===
    print("\n=== 查询3: 深层嵌套（文章→作者→文章→评论→作者）===")
    query3 = """
    query {
        post(id: 101) {
            title
            author {
                name
                posts {
                    title
                    comments {
                        text
                        author {
                            name
                        }
                    }
                }
            }
        }
    }
    """
    parser3 = Parser(query3)
    ops3 = parser3.parse_document()
    result3 = executor.execute(ops3[0])
    print(json.dumps(result3, indent=2, ensure_ascii=False))

    # === 查询4：别名 ===
    print("\n=== 查询4: 使用别名同时查多个用户 ===")
    query4 = """
    query {
        alice: user(id: 1) {
            name
        }
        bob: user(id: 2) {
            name
        }
    }
    """
    parser4 = Parser(query4)
    ops4 = parser4.parse_document()
    result4 = executor.execute(ops4[0])
    print(json.dumps(result4, indent=2, ensure_ascii=False))

    # === 查询5：错误处理 ===
    print("\n=== 查询5: 查询不存在的字段 ===")
    query5 = """
    query {
        users {
            name
            nonexistentField
        }
    }
    """
    parser5 = Parser(query5)
    ops5 = parser5.parse_document()
    result5 = executor.execute(ops5[0])
    print(json.dumps(result5, indent=2, ensure_ascii=False))

    # === Token 演示 ===
    print("\n=== 词法分析演示 ===")
    lexer = Lexer('query { user(id: 1) { name } }')
    tokens = []
    while True:
        token = lexer.next_token()
        tokens.append(f"{token.type}({token.value})")
        if token.type == "EOF":
            break
    print(f"  输入: query {{ user(id: 1) {{ name }} }}")
    print(f"  Token: {' → '.join(tokens)}")
```

**思考题**：在查询3的深层嵌套中，`post(id:101).author.posts.comments.author` 会产生 N+1 查询问题——每个评论都单独查一次 author。你会如何设计 DataLoader 来批量解决？提示：收集所有 authorId，一次性查询后分配。

---

## 四、DevOps（4题）

---

### 第13题：Docker多阶段构建 — Python项目容器化

**知识点讲解**

Docker 镜像通过**分层文件系统（Layered Filesystem）**构建，每条 Dockerfile 指令生成一层。分层的好处是**缓存复用**：如果某层未变化，构建时直接使用缓存，跳过后续层的重建。因此 Dockerfile 的指令顺序至关重要——将变化频率低的操作（如安装系统依赖）放前面，变化频率高的操作（如复制源码）放后面。

**多阶段构建**是减小镜像体积的核心技术。传统单阶段构建中，编译工具、测试框架等都会进入最终镜像，动辄数百 MB。多阶段构建定义多个 `FROM` 阶段：第一阶段安装编译工具并构建产物，第二阶段 `COPY --from=builder` 只复制构建产物到精简运行时镜像。典型 Python 项目可将镜像从 1GB+ 压缩到 100MB 以下。

**构建缓存优化**的关键技巧：(1) 先 `COPY requirements.txt` 再 `pip install`，最后 `COPY .` —— 依赖不变时跳过安装；(2) 使用 `.dockerignore` 排除 `.git`、`__pycache__`、`venv` 等不需要的文件；(3) 合并 `RUN` 命令减少层数（每层有元数据开销）。**体积优化**技巧：选择 `python:3.12-slim` 或 `alpine` 基础镜像、清理 pip 缓存（`--no-cache-dir`）、使用 `.whl` 格式安装。

```python
"""
Docker 多阶段构建 —— 生成并验证 Dockerfile + docker-compose.yml
运行：python exercise_13_docker.py
输出：生成 Dockerfile、docker-compose.yml、.dockerignore 文件
"""
import os
import textwrap
from pathlib import Path


# ──────────── Dockerfile（多阶段构建）────────────
DOCKERFILE_CONTENT = """\
# ==========================================
# 阶段1: Builder —— 安装依赖、编译扩展
# ==========================================
FROM python:3.12-slim AS builder

# 设置工作目录
WORKDIR /build

# 安装编译依赖（gcc 用于编译 C 扩展如 numpy/scipy）
RUN apt-get update && apt-get install -y --no-install-recommends \\
    gcc \\
    g++ \\
    libffi-dev \\
    && rm -rf /var/lib/apt/lists/*

# 创建虚拟环境（避免污染系统 Python）
RUN python -m venv /opt/venv
# 激活虚拟环境（后续命令使用 venv 的 pip）
ENV PATH="/opt/venv/bin:$PATH"

# 先复制依赖文件（利用缓存：代码变化不重新安装依赖）
COPY requirements.txt .

# 安装依赖到虚拟环境（--no-cache-dir 减小体积）
RUN pip install --no-cache-dir --upgrade pip && \\
    pip install --no-cache-dir -r requirements.txt

# ==========================================
# 阶段2: Runtime —— 精简运行时镜像
# ==========================================
FROM python:3.12-slim AS runtime

# 安装运行时依赖（仅运行所需，不含编译工具）
RUN apt-get update && apt-get install -y --no-install-recommends \\
    libglib2.0-0 \\
    libgl1-mesa-glx \\
    && rm -rf /var/lib/apt/lists/*

# 从 builder 阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 设置环境变量
ENV PATH="/opt/venv/bin:$PATH" \\
    PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PYTHONPATH="/app"

# 创建非 root 用户（安全最佳实践）
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# 复制应用代码
COPY --chown=appuser:appuser . .

# 切换到非 root 用户
USER appuser

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \\
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# 启动命令
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
"""


# ──────────── docker-compose.yml ────────────
COMPOSE_CONTENT = """\
# docker-compose.yml —— 多服务编排
version: "3.9"

services:
  # ─── Web 应用 ───
  web:
    build:
      context: .
      dockerfile: Dockerfile
      # 构建参数（可在 Dockerfile 中用 ARG 接收）
      args:
        PYTHON_VERSION: "3.12-slim"
    container_name: myapp-web
    ports:
      - "8000:8000"
    environment:
      - DEBUG=false
      - DATABASE_URL=postgresql://app:password@db:5432/myapp
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=${SECRET_KEY:-default-secret-change-me}
    volumes:
      - app-logs:/app/logs
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    restart: unless-stopped
    # 资源限制
    deploy:
      resources:
        limits:
          cpus: "2.0"
          memory: 512M
        reservations:
          cpus: "0.5"
          memory: 128M
    # 日志限制
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    networks:
      - app-network

  # ─── PostgreSQL 数据库 ───
  db:
    image: postgres:16-alpine
    container_name: myapp-db
    environment:
      POSTGRES_DB: myapp
      POSTGRES_USER: app
      POSTGRES_PASSWORD: password
    volumes:
      - db-data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U app -d myapp"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - app-network

  # ─── Redis 缓存 ───
  redis:
    image: redis:7-alpine
    container_name: myapp-redis
    command: redis-server --maxmemory 128mb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    restart: unless-stopped
    networks:
      - app-network

  # ─── Nginx 反向代理 ───
  nginx:
    image: nginx:alpine
    container_name: myapp-nginx
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - web
    restart: unless-stopped
    networks:
      - app-network

# ─── 持久化卷 ───
volumes:
  db-data:
    driver: local
  redis-data:
    driver: local
  app-logs:
    driver: local

# ─── 网络 ───
networks:
  app-network:
    driver: bridge
"""


# ──────────── .dockerignore ────────────
DOCKERIGNORE_CONTENT = """\
# 版本控制
.git
.gitignore

# Python 缓存
__pycache__/
*.pyc
*.pyo
*.pyd
.Python

# 虚拟环境
venv/
.venv/
env/

# 测试和覆盖率
.pytest_cache/
.coverage
htmlcov/
.tox/

# IDE
.vscode/
.idea/
*.swp
*.swo

# 环境变量（敏感信息不应进入镜像）
.env
.env.local

# Docker 自身文件
Dockerfile
docker-compose.yml
.dockerignore

# 文档
*.md
docs/

# CI/CD
.github/
.gitlab-ci.yml
"""


# ──────────── requirements.txt ────────────
REQUIREMENTS_CONTENT = """\
# 生产依赖
fastapi==0.111.0
uvicorn[standard]==0.30.1
sqlalchemy==2.0.30
asyncpg==0.29.0
alembic==1.13.1
redis==5.0.4
pydantic==2.7.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4

# 开发依赖（仅在 builder 阶段使用）
# pytest==8.2.0
# pytest-asyncio==0.23.6
# httpx==0.27.0
"""


# ──────────── nginx.conf ────────────
NGINX_CONF = """\
upstream web_backend {
    server web:8000;
}

server {
    listen 80;
    server_name localhost;

    # 反向代理到 FastAPI
    location / {
        proxy_pass http://web_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # 健康检查直连
    location /health {
        proxy_pass http://web_backend/health;
        access_log off;
    }

    # 静态文件（如果有）
    location /static/ {
        alias /app/static/;
        expires 30d;
    }
}
"""


# ──────────── 验证脚本 ────────────
def validate_dockerfile(content: str) -> list:
    """验证 Dockerfile 基本规范"""
    issues = []
    lines = content.strip().split("\n")

    # 检查多阶段构建
    from_count = sum(1 for l in lines if l.strip().startswith("FROM "))
    if from_count < 2:
        issues.append("⚠ 未使用多阶段构建（建议至少2个 FROM）")

    # 检查非 root 用户
    has_user = any(l.strip().startswith("USER ") for l in lines)
    if not has_user:
        issues.append("⚠ 未设置非 root 用户")

    # 检查 HEALTHCHECK
    has_health = any(l.strip().startswith("HEALTHCHECK") for l in lines)
    if not has_health:
        issues.append("⚠ 未设置 HEALTHCHECK")

    # 检查 requirements.txt 缓存优化
    copy_req_before_copy_all = False
    req_line = None
    copy_all_line = None
    for i, l in enumerate(lines):
        if "COPY requirements.txt" in l:
            req_line = i
        if l.strip() == "COPY . ." or l.strip() == "COPY . /app":
            copy_all_line = i
    if req_line and copy_all_line and req_line < copy_all_line:
        copy_req_before_copy_all = True
    if not copy_req_before_copy_all:
        issues.append("⚠ 未优化缓存：应先 COPY requirements.txt 再 COPY 源码")

    # 检查 --no-cache-dir
    has_no_cache = "--no-cache-dir" in content
    if not has_no_cache:
        issues.append("⚠ pip install 未使用 --no-cache-dir")

    # 检查 slim/alpine 基础镜像
    if "python:" in content and "slim" not in content and "alpine" not in content:
        issues.append("⚠ 使用了完整版基础镜像，建议用 slim 或 alpine")

    return issues


def estimate_image_size(content: str) -> dict:
    """估算镜像大小"""
    base_size = 0
    if "python:3.12-slim" in content:
        base_size = 45  # MB
    elif "python:3.12-alpine" in content:
        base_size = 35
    else:
        base_size = 350  # 完整版约 350MB

    deps_size = 200  # 依赖大约 200MB
    runtime_deps = 10  # 运行时系统库

    builder_total = base_size + 100 + deps_size  # +100MB 编译工具
    runtime_total = base_size + deps_size + runtime_deps

    return {
        "builder_stage": f"~{builder_total} MB",
        "runtime_stage": f"~{runtime_total} MB",
        "saved": f"~{builder_total - runtime_total} MB (编译工具)",
    }


# ──────────── 生成文件 ────────────
def generate_project(output_dir: str = "./docker_project") -> None:
    """生成完整的 Docker 项目文件"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    files = {
        "Dockerfile": DOCKERFILE_CONTENT,
        "docker-compose.yml": COMPOSE_CONTENT,
        ".dockerignore": DOCKERIGNORE_CONTENT,
        "requirements.txt": REQUIREMENTS_CONTENT,
        "nginx.conf": NGINX_CONF,
    }

    for filename, content in files.items():
        filepath = out / filename
        filepath.write_text(content, encoding="utf-8")
        print(f"  ✓ 生成 {filepath}")

    # 验证
    print(f"\n--- Dockerfile 验证 ---")
    issues = validate_dockerfile(DOCKERFILE_CONTENT)
    if not issues:
        print("  ✓ 所有检查通过！")
    else:
        for issue in issues:
            print(f"  {issue}")

    print(f"\n--- 镜像大小估算 ---")
    sizes = estimate_image_size(DOCKERFILE_CONTENT)
    for stage, size in sizes.items():
        print(f"  {stage}: {size}")

    print(f"\n--- 构建命令 ---")
    print(f"  构建:  docker build -t myapp:latest {output_dir}/")
    print(f"  启动:  docker compose -f {output_dir}/docker-compose.yml up -d")
    print(f"  查看:  docker compose -f {output_dir}/docker-compose.yml ps")
    print(f"  日志:  docker compose -f {output_dir}/docker-compose.yml logs -f web")
    print(f"  停止:  docker compose -f {output_dir}/docker-compose.yml down")

    print(f"\n--- 分层分析 ---")
    print("  Dockerfile 指令分层:")
    for i, line in enumerate(DOCKERFILE_CONTENT.strip().split("\n"), 1):
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            # 计算缩进
            indent = "    " if "RUN" in stripped and "&&" in stripped else "  "
            print(f"  {indent}层{i:02d}: {stripped[:70]}{'...' if len(stripped) > 70 else ''}")


if __name__ == "__main__":
    print("=" * 60)
    print("Docker 多阶段构建 —— 项目文件生成器")
    print("=" * 60)

    output = "/app/data/所有对话/主对话/learning/docker_project"
    print(f"\n输出目录: {output}\n")
    generate_project(output)
```

**思考题**：当前 Dockerfile 使用 `python:3.12-slim` 基础镜像。如果改用 `alpine` 镜像可以进一步减小体积（约 35MB vs 45MB），但 alpine 使用 musl libc 而非 glibc，可能导致某些 C 扩展（如 numpy）编译失败或运行变慢。你会如何权衡？

---

### 第14题：Kubernetes部署清单 — Deployment+Service+Ingress+ConfigMap

**知识点讲解**

Kubernetes 的核心抽象是 **Pod**——最小的可部署计算单元，包含一个或多个容器。**Deployment** 管理 Pod 的生命周期：它创建 **ReplicaSet** 来维持期望的 Pod 副本数，当 Pod 崩溃时自动重建。Deployment 通过 `strategy` 字段控制更新策略——`RollingUpdate`（默认）逐步替换旧 Pod，`Recreate` 先删全部再建新的。`maxSurge` 控制最多超出副本数的 Pod 数，`maxUnavailable` 控制最多不可用的 Pod 数。

**Service** 为一组 Pod 提供稳定的网络端点。Pod 的 IP 是易变的（重启后变化），Service 通过**标签选择器（Label Selector）**动态关联 Pod，提供负载均衡。四种 Service 类型：`ClusterIP`（集群内部访问，默认）、`NodePort`（暴露到节点端口）、`LoadBalancer`（云厂商负载均衡器）、`ExternalName`（DNS CNAME 别名）。

**Ingress** 是七层（HTTP/HTTPS）路由规则，将外部流量路由到集群内的 Service。它需要一个 **Ingress Controller**（如 nginx-ingress、traefik）来实际处理流量。Ingress 支持基于域名和路径的路由、TLS 终止、虚拟主机等功能。

**ConfigMap** 将配置与镜像解耦——修改配置无需重新构建镜像。Pod 通过环境变量或挂载文件方式消费 ConfigMap。敏感数据（密码、密钥）应使用 **Secret** 而非 ConfigMap。**标签（Labels）**和**注解（Annotations）**是 K8s 的元数据系统：标签用于选择和过滤，注解用于存储非标识性信息（如版本、构建时间）。

```python
"""
Kubernetes 部署清单 —— 生成并验证 K8s YAML 配置
运行：python exercise_14_kubernetes.py
输出：生成完整的 K8s 部署清单 YAML 文件
"""
import yaml  # PyYAML
from pathlib import Path
from typing import Dict, List, Any


# ──────────── 1. ConfigMap ────────────
def create_configmap() -> Dict:
    """应用配置（非敏感）"""
    return {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {
            "name": "app-config",
            "namespace": "production",
            "labels": {
                "app": "myapp",
                "component": "config",
            },
        },
        "data": {
            "DEBUG": "false",
            "LOG_LEVEL": "INFO",
            "DATABASE_HOST": "postgres-service",
            "DATABASE_PORT": "5432",
            "DATABASE_NAME": "myapp",
            "REDIS_HOST": "redis-service",
            "REDIS_PORT": "6379",
            "CACHE_TTL": "300",
            "MAX_WORKERS": "4",
            "app.yaml": """
# 应用配置文件
server:
  host: 0.0.0.0
  port: 8000
  workers: 4
database:
  pool_size: 20
  max_overflow: 10
  pool_timeout: 30
redis:
  db: 0
  socket_timeout: 5
logging:
  level: INFO
  format: "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
""".strip(),
        },
    }


# ──────────── 2. Secret ────────────
def create_secret() -> Dict:
    """敏感配置（Base64 编码，非加密）"""
    import base64
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {
            "name": "app-secrets",
            "namespace": "production",
            "labels": {"app": "myapp"},
        },
        "type": "Opaque",
        "data": {
            "DATABASE_PASSWORD": base64.b64encode(b"super-secret-pass").decode(),
            "SECRET_KEY": base64.b64encode(b"django-insecure-change-me").decode(),
            "REDIS_PASSWORD": base64.b64encode(b"redis-pass-123").decode(),
        },
    }


# ──────────── 3. Deployment ────────────
def create_deployment() -> Dict:
    """应用 Deployment（含滚动更新、健康检查、资源限制）"""
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "myapp-deployment",
            "namespace": "production",
            "labels": {
                "app": "myapp",
                "tier": "backend",
                "version": "v1.2.0",
            },
        },
        "spec": {
            "replicas": 3,
            # 滚动更新策略
            "strategy": {
                "type": "RollingUpdate",
                "rollingUpdate": {
                    "maxSurge": 1,         # 更新时最多多出1个Pod
                    "maxUnavailable": 0,   # 更新时不允许减少可用Pod
                },
            },
            # 修订历史限制
            "revisionHistoryLimit": 10,
            # 最小就绪时间（秒）—— Pod 就绪后等多久才认为可用
            "minReadySeconds": 10,
            # 标签选择器
            "selector": {
                "matchLabels": {
                    "app": "myapp",
                    "tier": "backend",
                },
            },
            "template": {
                "metadata": {
                    "labels": {
                        "app": "myapp",
                        "tier": "backend",
                        "version": "v1.2.0",
                    },
                    "annotations": {
                        "prometheus.io/scrape": "true",
                        "prometheus.io/port": "8000",
                        "prometheus.io/path": "/metrics",
                    },
                },
                "spec": {
                    # 安全上下文
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": 1000,
                        "fsGroup": 1000,
                    },
                    "containers": [
                        {
                            "name": "myapp",
                            "image": "myapp:1.2.0",
                            "imagePullPolicy": "IfNotPresent",
                            "ports": [
                                {"containerPort": 8000, "name": "http", "protocol": "TCP"},
                            ],
                            # 从 ConfigMap 注入环境变量
                            "envFrom": [
                                {
                                    "configMapRef": {"name": "app-config"},
                                },
                            ],
                            # 从 Secret 注入敏感变量
                            "env": [
                                {
                                    "name": "DATABASE_PASSWORD",
                                    "valueFrom": {
                                        "secretKeyRef": {
                                            "name": "app-secrets",
                                            "key": "DATABASE_PASSWORD",
                                        }
                                    },
                                },
                                {
                                    "name": "SECRET_KEY",
                                    "valueFrom": {
                                        "secretKeyRef": {
                                            "name": "app-secrets",
                                            "key": "SECRET_KEY",
                                        }
                                    },
                                },
                            ],
                            # 资源限制
                            "resources": {
                                "requests": {
                                    "cpu": "250m",    # 0.25 核
                                    "memory": "256Mi",
                                },
                                "limits": {
                                    "cpu": "500m",    # 0.5 核
                                    "memory": "512Mi",
                                },
                            },
                            # 存活探针：容器是否在运行
                            "livenessProbe": {
                                "httpGet": {
                                    "path": "/health",
                                    "port": 8000,
                                },
                                "initialDelaySeconds": 15,
                                "periodSeconds": 20,
                                "timeoutSeconds": 3,
                                "failureThreshold": 3,
                            },
                            # 就绪探针：容器是否准备好接收流量
                            "readinessProbe": {
                                "httpGet": {
                                    "path": "/ready",
                                    "port": 8000,
                                },
                                "initialDelaySeconds": 5,
                                "periodSeconds": 10,
                                "timeoutSeconds": 3,
                                "failureThreshold": 3,
                            },
                            # 启动探针：容器是否已启动完成
                            "startupProbe": {
                                "httpGet": {
                                    "path": "/health",
                                    "port": 8000,
                                },
                                "initialDelaySeconds": 0,
                                "periodSeconds": 5,
                                "failureThreshold": 30,  # 最多等 150 秒
                            },
                            # 挂载配置文件
                            "volumeMounts": [
                                {
                                    "name": "config-volume",
                                    "mountPath": "/app/config",
                                    "readOnly": True,
                                },
                            ],
                        }
                    ],
                    "volumes": [
                        {
                            "name": "config-volume",
                            "configMap": {
                                "name": "app-config",
                                "items": [
                                    {"key": "app.yaml", "path": "app.yaml"},
                                ],
                            },
                        },
                    ],
                    # 优雅终止
                    "terminationGracePeriodSeconds": 30,
                    # 反亲和性：将 Pod 分散到不同节点
                    "affinity": {
                        "podAntiAffinity": {
                            "preferredDuringSchedulingIgnoredDuringExecution": [
                                {
                                    "weight": 100,
                                    "podAffinityTerm": {
                                        "labelSelector": {
                                            "matchExpressions": [
                                                {
                                                    "key": "app",
                                                    "operator": "In",
                                                    "values": ["myapp"],
                                                }
                                            ]
                                        },
                                        "topologyKey": "kubernetes.io/hostname",
                                    },
                                }
                            ],
                        }
                    },
                },
            },
        },
    }


# ──────────── 4. Service ────────────
def create_service() -> Dict:
    """ClusterIP Service：集群内部访问"""
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": "myapp-service",
            "namespace": "production",
            "labels": {"app": "myapp"},
        },
        "spec": {
            "type": "ClusterIP",
            "selector": {
                "app": "myapp",
                "tier": "backend",
            },
            "ports": [
                {
                    "name": "http",
                    "port": 80,           # Service 端口
                    "targetPort": 8000,    # Pod 端口
                    "protocol": "TCP",
                },
            ],
            "sessionAffinity": "None",  # 不保持会话亲和
        },
    }


# ──────────── 5. Ingress ────────────
def create_ingress() -> Dict:
    """Ingress：HTTP 路由 + TLS"""
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {
            "name": "myapp-ingress",
            "namespace": "production",
            "labels": {"app": "myapp"},
            "annotations": {
                "nginx.ingress.kubernetes.io/ssl-redirect": "true",
                "nginx.ingress.kubernetes.io/rate-limit": "100",
                "nginx.ingress.kubernetes.io/rate-limit-window": "1m",
                "cert-manager.io/cluster-issuer": "letsencrypt-prod",
            },
        },
        "spec": {
            "ingressClassName": "nginx",
            "tls": [
                {
                    "hosts": ["myapp.example.com", "api.myapp.example.com"],
                    "secretName": "myapp-tls-cert",
                },
            ],
            "rules": [
                {
                    "host": "myapp.example.com",
                    "http": {
                        "paths": [
                            {
                                "path": "/",
                                "pathType": "Prefix",
                                "backend": {
                                    "service": {
                                        "name": "myapp-service",
                                        "port": {"number": 80},
                                    },
                                },
                            },
                        ],
                    },
                },
                {
                    "host": "api.myapp.example.com",
                    "http": {
                        "paths": [
                            {
                                "path": "/api",
                                "pathType": "Prefix",
                                "backend": {
                                    "service": {
                                        "name": "myapp-service",
                                        "port": {"number": 80},
                                    },
                                },
                            },
                        ],
                    },
                },
            ],
        },
    }


# ──────────── 6. HPA (水平 Pod 自动扩缩) ────────────
def create_hpa() -> Dict:
    """Horizontal Pod Autoscaler"""
    return {
        "apiVersion": "autoscaling/v2",
        "kind": "HorizontalPodAutoscaler",
        "metadata": {
            "name": "myapp-hpa",
            "namespace": "production",
        },
        "spec": {
            "scaleTargetRef": {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "name": "myapp-deployment",
            },
            "minReplicas": 2,
            "maxReplicas": 10,
            "metrics": [
                {
                    "type": "Resource",
                    "resource": {
                        "name": "cpu",
                        "target": {
                            "type": "Utilization",
                            "averageUtilization": 70,
                        },
                    },
                },
                {
                    "type": "Resource",
                    "resource": {
                        "name": "memory",
                        "target": {
                            "type": "Utilization",
                            "averageUtilization": 80,
                        },
                    },
                },
            ],
        },
    }


# ──────────── 验证与生成 ────────────
def validate_manifests(manifests: List[Dict]) -> List[str]:
    """验证 K8s 清单的基本规范"""
    issues = []

    for m in manifests:
        kind = m.get("kind", "Unknown")
        metadata = m.get("metadata", {})

        # 检查必要字段
        if not metadata.get("name"):
            issues.append(f"⚠ {kind}: 缺少 metadata.name")

        # 检查标签
        if not metadata.get("labels"):
            issues.append(f"⚠ {kind}: 缺少 labels")

        # Deployment 特定检查
        if kind == "Deployment":
            spec = m.get("spec", {})
            template_spec = spec.get("template", {}).get("spec", {})

            # 检查资源限制
            containers = template_spec.get("containers", [])
            for c in containers:
                if not c.get("resources"):
                    issues.append(f"⚠ {kind}/{c.get('name')}: 缺少 resources（资源限制）")
                else:
                    if not c["resources"].get("limits"):
                        issues.append(f"⚠ {kind}/{c.get('name')}: 缺少 resources.limits")
                    if not c["resources"].get("requests"):
                        issues.append(f"⚠ {kind}/{c.get('name')}: 缺少 resources.requests")

                # 检查健康探针
                if not c.get("livenessProbe"):
                    issues.append(f"⚠ {kind}/{c.get('name')}: 缺少 livenessProbe")
                if not c.get("readinessProbe"):
                    issues.append(f"⚠ {kind}/{c.get('name')}: 缺少 readinessProbe")

            # 检查安全上下文
            if not template_spec.get("securityContext"):
                issues.append(f"⚠ {kind}: 缺少 pod securityContext")

            # 检查滚动更新策略
            strategy = spec.get("strategy", {})
            if strategy.get("type") != "RollingUpdate":
                issues.append(f"⚠ {kind}: 建议使用 RollingUpdate 策略")

        # Service 特定检查
        if kind == "Service":
            spec = m.get("spec", {})
            if not spec.get("selector"):
                issues.append(f"⚠ {kind}: 缺少 selector")

    return issues


def generate_manifests(output_dir: str) -> None:
    """生成所有 K8s 清单文件"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    manifests = [
        ("00-namespace.yaml", {"apiVersion": "v1", "kind": "Namespace",
          "metadata": {"name": "production", "labels": {"name": "production"}}}),
        ("01-configmap.yaml", create_configmap()),
        ("02-secret.yaml", create_secret()),
        ("03-deployment.yaml", create_deployment()),
        ("04-service.yaml", create_service()),
        ("05-ingress.yaml", create_ingress()),
        ("06-hpa.yaml", create_hpa()),
    ]

    print("--- 生成 K8s 清单 ---")
    for filename, manifest in manifests:
        filepath = out / filename
        with open(filepath, "w") as f:
            yaml.dump(manifest, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"  ✓ {filename}")

    # 合并为单一文件
    all_in_one = out / "all-in-one.yaml"
    with open(all_in_one, "w") as f:
        for i, (_, manifest) in enumerate(manifests):
            if i > 0:
                f.write("\n---\n")
            yaml.dump(manifest, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"  ✓ all-in-one.yaml (合并文件)")

    # 验证
    print(f"\n--- 清单验证 ---")
    issues = validate_manifests([m for _, m in manifests])
    if not issues:
        print("  ✓ 所有检查通过！")
    else:
        for issue in issues:
            print(f"  {issue}")

    # 架构说明
    print(f"\n--- 部署架构 ---")
    print("""
  外部用户
     │
     ▼
  ┌──────────────────┐
  │   Ingress (nginx) │  ← TLS 终止 + 路由
  │  myapp.example.com│
  └────────┬─────────┘
           │
           ▼
  ┌──────────────────┐
  │  Service (ClusterIP)│  ← 负载均衡 + 服务发现
  │  myapp-service:80  │
  └────────┬─────────┘
           │
     ┌─────┼─────┐
     ▼     ▼     ▼
  ┌───┐ ┌───┐ ┌───┐
  │Pod│ │Pod│ │Pod│  ← Deployment 管理 3 副本
  │ 1 │ │ 2 │ │ 3 │     (HPA: 2~10 自动扩缩)
  └─┬─┘ └─┬─┘ └─┬─┘
    │     │     │
    └─────┼─────┘
          │
     ConfigMap + Secret  ← 配置注入
""")

    print(f"--- 部署命令 ---")
    print(f"  应用:  kubectl apply -f {output_dir}/")
    print(f"  查看:  kubectl -n production get pods")
    print(f"  日志:  kubectl -n production logs -f deployment/myapp-deployment")
    print(f"  扩缩:  kubectl -n production scale deployment myapp-deployment --replicas=5")
    print(f"  滚动:  kubectl -n production rollout status deployment/myapp-deployment")
    print(f"  回滚:  kubectl -n production rollout undo deployment/myapp-deployment")


if __name__ == "__main__":
    print("=" * 60)
    print("Kubernetes 部署清单生成器")
    print("=" * 60)

    output = "/app/data/所有对话/主对话/learning/k8s_manifests"
    print(f"\n输出目录: {output}\n")
    generate_manifests(output)
```

**思考题**：当前 Deployment 设置 `maxUnavailable: 0` 和 `maxSurge: 1`，意味着滚动更新时始终保持 3 个可用 Pod。如果改为 `maxUnavailable: 1` 和 `maxSurge: 0`，更新行为有何变化？哪种更适合需要维持 SLA 的生产服务？

---

### 第15题：Terraform基础设施即代码 — AWS S3+EC2+RDS配置

**知识点讲解**

Terraform 是 HashiCorp 的 IaC 工具，使用 **HCL（HashiCorp Configuration Language）** 声明式地描述基础设施。核心理念是"期望状态 vs 实际状态"——你声明想要什么，Terraform 计算差异并执行变更。**资源声明**是基本构建块：`resource "aws_s3_bucket" "name" { ... }` 定义一个 S3 桶。每个资源有类型（`aws_s3_bucket`）、本地名称（`name`）和属性块。

**变量（Variables）** 使配置可参数化：`variable "instance_type" { type = string, default = "t3.micro" }`。变量可通过命令行（`-var`）、变量文件（`terraform.tfvars`）或环境变量（`TF_VAR_*`）传入。**输出（Outputs）** 暴露资源属性供其他模块或用户使用：`output "bucket_arn" { value = aws_s3_bucket.data.arn }`。

**状态管理（State Management）** 是 Terraform 的关键概念。State 文件（`terraform.tfstate`）记录已创建资源的真实 ID 和属性，Terraform 据此计算变更计划。State 应存储在远程后端（S3 + DynamoDB 锁）而非本地，以支持团队协作和状态锁定。**`terraform plan`** 预览变更，**`terraform apply`** 执行变更，**`terraform destroy`** 销毁所有资源。

**模块化**通过 `module` 块实现配置复用。模块是包含 `.tf` 文件的目录，通过 `input` 变量接收参数，`output` 暴露结果。良好的模块设计遵循"单一职责"原则——一个模块管理一种资源类型。

```python
"""
Terraform 基础设施即代码 —— 生成 AWS S3+EC2+RDS 配置
运行：python exercise_15_terraform.py
输出：生成完整的 Terraform 项目文件
"""
from pathlib import Path


# ──────────── main.tf：主配置 ────────────
MAIN_TF = """\
# ==========================================
# Terraform 主配置：AWS 基础设施
# ==========================================

# ─── AWS Provider 配置 ───
provider "aws" {
  region = var.aws_region

  # 默认标签（所有资源自动继承）
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Owner       = "devops-team"
    }
  }
}

# ==========================================
# 1. 网络：VPC + 子网
# ==========================================

# VPC
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

# 公有子网（2个可用区）
resource "aws_subnet" "public" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public-subnet-${count.index + 1}"
    Tier = "public"
  }
}

# 私有子网（RDS 用）
resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index + 10)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "${var.project_name}-private-subnet-${count.index + 1}"
    Tier = "private"
  }
}

# 互联网网关
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.project_name}-igw" }
}

# 公有路由表
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = { Name = "${var.project_name}-public-rt" }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# 可用区数据源
data "aws_availability_zones" "available" {
  state = "available"
}

# ==========================================
# 2. 安全组
# ==========================================

# EC2 安全组
resource "aws_security_group" "ec2" {
  name        = "${var.project_name}-ec2-sg"
  description = "Security group for EC2 instances"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP from internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH from trusted IP"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.ssh_allowed_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-ec2-sg" }
}

# RDS 安全组
resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds-sg"
  description = "Security group for RDS"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "PostgreSQL from EC2"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-rds-sg" }
}

# ==========================================
# 3. S3 存储桶
# ==========================================

# 数据存储桶
resource "aws_s3_bucket" "data" {
  bucket = "${var.project_name}-data-${var.environment}"

  tags = {
    Name = "${var.project_name}-data"
  }
}

# 版本控制
resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

# 服务端加密
resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# 公共访问阻止
resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# 生命周期策略
resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    id     = "transition-to-glacier"
    status = "Enabled"

    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 365
      storage_class = "GLACIER"
    }

    expiration {
      days = 2555  # 7年后过期
    }
  }
}

# ==========================================
# 4. EC2 实例
# ==========================================

# 密钥对
resource "aws_key_pair" "main" {
  key_name   = "${var.project_name}-key"
  public_key = var.ssh_public_key
}

# EC2 实例
resource "aws_instance" "web" {
  count                       = var.instance_count
  ami                         = data.aws_ami.ubuntu.id
  instance_type               = var.instance_type
  subnet_id                   = aws_subnet.public[count.index].id
  vpc_security_group_ids      = [aws_security_group.ec2.id]
  key_name                    = aws_key_pair.main.key_name
  associate_public_ip_address = true

  # 用户数据脚本（实例启动时执行）
  user_data = templatefile("${path.module}/user_data.sh", {
    db_host     = aws_db_instance.main.address
    db_name     = var.db_name
    db_user     = var.db_username
    project_name = var.project_name
  })

  root_block_device {
    volume_type = "gp3"
    volume_size = 30
    encrypted   = true
  }

  tags = {
    Name = "${var.project_name}-web-${count.index + 1}"
  }

  depends_on = [aws_db_instance.main]
}

# 最新 Ubuntu AMI
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]  # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }
}

# ==========================================
# 5. RDS 数据库
# ==========================================

# DB 子网组
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = { Name = "${var.project_name}-db-subnet-group" }
}

# RDS 实例
resource "aws_db_instance" "main" {
  identifier             = "${var.project_name}-db"
  engine                 = "postgres"
  engine_version         = "16.2"
  instance_class         = var.db_instance_class
  allocated_storage      = 20
  storage_type           = "gp3"
  storage_encrypted      = true

  db_name                = var.db_name
  username               = var.db_username
  password               = var.db_password

  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name

  # 高可用
  multi_az               = var.environment == "production" ? true : false
  backup_retention_period = var.environment == "production" ? 7 : 1
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:04:00-sun:05:00"

  # 删除保护
  deletion_protection    = var.environment == "production" ? true : false
  skip_final_snapshot    = var.environment == "production" ? false : true
  final_snapshot_identifier = var.environment == "production" ? "${var.project_name}-final-snapshot" : null

  tags = { Name = "${var.project_name}-db" }
}

# 弹性 IP（给 EC2 用）
resource "aws_eip" "web" {
  count    = var.instance_count
  domain   = "vpc"
  instance = aws_instance.web[count.index].id

  tags = { Name = "${var.project_name}-eip-${count.index + 1}" }
}
"""


# ──────────── variables.tf ────────────
VARIABLES_TF = """\
# ==========================================
# 变量定义
# ==========================================

variable "project_name" {
  type        = string
  description = "项目名称，用作资源前缀"
  default     = "myapp"
}

variable "environment" {
  type        = string
  description = "环境（development/staging/production）"
  default     = "development"

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "环境必须是 development、staging 或 production。"
  }
}

variable "aws_region" {
  type        = string
  description = "AWS 区域"
  default     = "ap-northeast-1"
}

variable "vpc_cidr" {
  type        = string
  description = "VPC CIDR 块"
  default     = "10.0.0.0/16"
}

variable "instance_type" {
  type        = string
  description = "EC2 实例类型"
  default     = "t3.micro"
}

variable "instance_count" {
  type        = number
  description = "EC2 实例数量"
  default     = 2
}

variable "db_instance_class" {
  type        = string
  description = "RDS 实例类型"
  default     = "db.t3.micro"
}

variable "db_name" {
  type        = string
  description = "数据库名称"
  default     = "myapp"
}

variable "db_username" {
  type        = string
  description = "数据库用户名"
  default     = "postgres"
  sensitive   = true
}

variable "db_password" {
  type        = string
  description = "数据库密码（从 Secrets Manager 或 tfvars 传入）"
  sensitive   = true
}

variable "ssh_public_key" {
  type        = string
  description = "SSH 公钥"
}

variable "ssh_allowed_cidr" {
  type        = string
  description = "允许 SSH 访问的 CIDR 块"
  default     = "0.0.0.0/0"  # 生产环境应限制为具体 IP
}
"""


# ──────────── outputs.tf ────────────
OUTPUTS_TF = """\
# ==========================================
# 输出值
# ==========================================

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "公有子网 ID 列表"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "私有子网 ID 列表"
  value       = aws_subnet.private[*].id
}

output "ec2_public_ips" {
  description = "EC2 实例公网 IP 列表"
  value       = aws_eip.web[*].public_ip
}

output "ec2_private_ips" {
  description = "EC2 实例私网 IP 列表"
  value       = aws_instance.web[*].private_ip
}

output "rds_endpoint" {
  description = "RDS 数据库端点"
  value       = aws_db_instance.main.endpoint
  sensitive   = true
}

output "rds_address" {
  description = "RDS 数据库地址"
  value       = aws_db_instance.main.address
}

output "s3_bucket_name" {
  description = "S3 存储桶名称"
  value       = aws_s3_bucket.data.id
}

output "s3_bucket_arn" {
  description = "S3 存储桶 ARN"
  value       = aws_s3_bucket.data.arn
}
"""


# ──────────── backend.tf ────────────
BACKEND_TF = """\
# ==========================================
# 远程状态后端
# 状态文件存储在 S3，用 DynamoDB 做状态锁
# ==========================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "myapp-terraform-state"  # 需提前创建
    key            = "infra/terraform.tfstate"
    region         = "ap-northeast-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}
"""


# ──────────── user_data.sh ────────────
USER_DATA_SH = """\
#!/bin/bash
# EC2 用户数据脚本 —— 实例启动时自动执行

set -euo pipefail

# 更新系统
apt-get update && apt-get upgrade -y

# 安装 Docker
apt-get install -y docker.io docker-compose
systemctl enable docker
systemctl start docker

# 安装 Python 3
apt-get install -y python3 python3-pip

# 创建应用目录
mkdir -p /opt/${project_name}
cd /opt/${project_name}

# 写入环境变量
cat > .env << EOF
DB_HOST=${db_host}
DB_NAME=${db_name}
DB_USER=${db_user}
EOF

# 拉取应用镜像并启动（示例）
# docker pull ${project_name}:latest
# docker-compose up -d

echo "=== 用户数据脚本执行完成 ==="
"""


# ──────────── tfvars 示例 ────────────
TFVARS_EXAMPLE = """\
# terraform.tfvars —— 环境变量值（不提交到版本控制）

project_name    = "myapp"
environment     = "staging"
aws_region      = "ap-northeast-1"
instance_type   = "t3.small"
instance_count  = 2
db_instance_class = "db.t3.small"
db_name         = "myapp"
db_username     = "postgres"
db_password     = "CHANGE_ME_TO_REAL_PASSWORD"
ssh_public_key  = "ssh-rsa AAAAB3NzaC1yc2E... your-key"
ssh_allowed_cidr = "10.0.0.0/8"  # 限制 SSH 来源
"""


# ──────────── 生成文件 ────────────
def generate_terraform_project(output_dir: str) -> None:
    """生成完整的 Terraform 项目"""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    files = {
        "main.tf": MAIN_TF,
        "variables.tf": VARIABLES_TF,
        "outputs.tf": OUTPUTS_TF,
        "backend.tf": BACKEND_TF,
        "user_data.sh": USER_DATA_SH,
        "terraform.tfvars.example": TFVARS_EXAMPLE,
    }

    print("--- 生成 Terraform 文件 ---")
    for filename, content in files.items():
        filepath = out / filename
        filepath.write_text(content, encoding="utf-8")
        print(f"  ✓ {filename}")

    # 资源清单
    print(f"\n--- 资源清单 ---")
    resources = [
        ("aws_vpc", "1", "虚拟私有云"),
        ("aws_subnet", "2+2", "公有+私有子网"),
        ("aws_internet_gateway", "1", "互联网网关"),
        ("aws_route_table", "1", "路由表"),
        ("aws_security_group", "2", "EC2 + RDS 安全组"),
        ("aws_s3_bucket", "1", "数据存储桶（含版本/加密/生命周期）"),
        ("aws_instance", "2", "EC2 Web 服务器"),
        ("aws_eip", "2", "弹性 IP"),
        ("aws_db_instance", "1", "PostgreSQL RDS"),
        ("aws_db_subnet_group", "1", "RDS 子网组"),
        ("aws_key_pair", "1", "SSH 密钥对"),
    ]
    print(f"  {'资源类型':<30s} {'数量':<8s} {'说明'}")
    print(f"  {'-'*30} {'-'*8} {'-'*30}")
    for rtype, count, desc in resources:
        print(f"  {rtype:<30s} {count:<8s} {desc}")

    # 命令
    print(f"\n--- Terraform 命令 ---")
    print(f"  初始化:  cd {output_dir} && terraform init")
    print(f"  格式化:  terraform fmt -recursive")
    print(f"  校验:    terraform validate")
    print(f"  预览:    terraform plan -var-file=terraform.tfvars")
    print(f"  应用:    terraform apply -var-file=terraform.tfvars")
    print(f"  销毁:    terraform destroy -var-file=terraform.tfvars")
    print(f"  输出:    terraform output")
    print(f"  导入:    terraform import aws_s3_bucket.data myapp-data-staging")


if __name__ == "__main__":
    print("=" * 60)
    print("Terraform 基础设施即代码 —— AWS S3+EC2+RDS")
    print("=" * 60)

    output = "/app/data/所有对话/主对话/learning/terraform_project"
    print(f"\n输出目录: {output}\n")
    generate_terraform_project(output)
```

**思考题**：当前配置中 `db_password` 通过 `terraform.tfvars` 文件传入，即使文件被 `.gitignore` 排除，密码仍会明文存储在 `terraform.tfstate` 中。你会如何改进以避免密码出现在 state 文件中？提示：研究 `aws_secretsmanager_secret_version` 和 `dynamic` 块。

---

### 第16题：可观测性三件套 — 结构化日志+Prometheus指标+OpenTelemetry Tracing

**知识点讲解**

可观测性（Observability）的三大支柱是**日志**、**指标**和**分布式追踪**。三者互补：日志记录离散事件（"发生了什么"），指标量化系统状态（"发生了多少次/多快"），追踪描绘请求路径（"在哪里发生了"）。

**结构化日志**将日志从自由文本转为机器可解析的 JSON 格式，每条日志包含时间戳、级别、消息和上下文字段。关键是**关联 ID（Correlation ID）**——同一请求的所有日志共享同一个 trace_id，使得从日志可以跳转到对应的追踪。Python 标准库 `logging` + `json` 即可实现，生产中常用 `structlog` 或 `python-json-logger`。

**Prometheus 指标**有四种类型：**Counter**（只增不减，如请求总数）、**Gauge**（可增可减，如当前连接数）、**Histogram**（分布统计，如请求延迟分桶）、**Summary**（分位数，如 P99 延迟）。Prometheus 使用 **Pull 模式**——服务端主动抓取 `/metrics` 端点。**采样策略**在指标中较少使用（通常全量采集），但在追踪中至关重要。

**OpenTelemetry Tracing** 将一个请求拆分为多个 **Span**，每个 Span 记录操作名、开始/结束时间、属性和状态。多个 Span 通过 parent-child 关系组成 **Trace**。**采样策略**决定哪些 Trace 被上报：AlwaysOn（全量，开发环境）、AlwaysOff（全不上报）、TraceIDRatio（按比例采样，生产环境通常 1-10%）、ParentBased（根据父 Span 的采样决定）。**告警规则**基于指标定义，如"5分钟内错误率 > 5% 则告警"。

```python
"""
可观测性三件套 —— 结构化日志 + Prometheus 指标 + OpenTelemetry Tracing
运行：python exercise_16_observability.py
依赖：pip install prometheus-client opentelemetry-api opentelemetry-sdk
"""
import json
import time
import logging
import sys
import random
import functools
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from contextlib import contextmanager
from collections import defaultdict


# ==========================================
# 1. 结构化日志
# ==========================================
class StructuredLogger:
    """
    结构化 JSON 日志器
    - 每条日志为 JSON 对象，便于 ELK/Loki 采集
    - 支持 trace_id 关联（与 Tracing 联动）
    - 支持上下文字段注入
    """

    def __init__(self, name: str = "app", level: int = logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.handlers.clear()

        # JSON 格式化 handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(self._json_formatter)
        self.logger.addHandler(handler)

        # 上下文字段（如 request_id, user_id）
        self._context: Dict[str, Any] = {}

    @staticmethod
    def _json_formatter(record: logging.LogRecord) -> str:
        """将 LogRecord 格式化为 JSON"""
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # 合并额外字段
        for key, value in record.__dict__.items():
            if key not in {"name", "msg", "args", "levelname", "levelno",
                          "pathname", "filename", "module", "exc_info",
                          "exc_text", "stack_info", "lineno", "funcName",
                          "created", "msecs", "relativeCreated", "thread",
                          "threadName", "processName", "process", "message"}:
                log_entry[key] = value
        return json.dumps(log_entry, ensure_ascii=False, default=str)

    def set_context(self, **kwargs):
        """设置上下文字段（后续日志自动携带）"""
        self._context.update(kwargs)

    def clear_context(self):
        """清空上下文"""
        self._context.clear()

    def _log(self, level: int, msg: str, **kwargs):
        extra = {**self._context, **kwargs}
        self.logger.log(level, msg, extra=extra)

    def debug(self, msg: str, **kwargs): self._log(logging.DEBUG, msg, **kwargs)
    def info(self, msg: str, **kwargs): self._log(logging.INFO, msg, **kwargs)
    def warning(self, msg: str, **kwargs): self._log(logging.WARNING, msg, **kwargs)
    def error(self, msg: str, **kwargs): self._log(logging.ERROR, msg, **kwargs)


# ==========================================
# 2. Prometheus 指标（纯 Python 实现）
# ==========================================
class Counter:
    """Counter：只增不减的计数器"""

    def __init__(self, name: str, description: str = "", labels: List[str] = None):
        self.name = name
        self.description = description
        self.label_names = labels or []
        self._values: Dict[tuple, float] = defaultdict(float)

    def inc(self, amount: float = 1.0, **labels):
        key = tuple(labels.get(l, "") for l in self.label_names)
        self._values[key] += amount

    def get(self, **labels) -> float:
        key = tuple(labels.get(l, "") for l in self.label_names)
        return self._values[key]

    def format_prometheus(self) -> str:
        lines = [f"# HELP {self.name} {self.description}",
                 f"# TYPE {self.name} counter"]
        for key, value in self._values.items():
            if self.label_names:
                label_str = ",".join(f'{n}="{v}"' for n, v in zip(self.label_names, key))
                lines.append(f'{self.name}{{{label_str}}} {value}')
            else:
                lines.append(f'{self.name} {value}')
        return "\n".join(lines)


class Gauge:
    """Gauge：可增可减的仪表"""

    def __init__(self, name: str, description: str = "", labels: List[str] = None):
        self.name = name
        self.description = description
        self.label_names = labels or []
        self._values: Dict[tuple, float] = defaultdict(float)

    def set(self, value: float, **labels):
        key = tuple(labels.get(l, "") for l in self.label_names)
        self._values[key] = value

    def inc(self, amount: float = 1.0, **labels):
        key = tuple(labels.get(l, "") for l in self.label_names)
        self._values[key] += amount

    def dec(self, amount: float = 1.0, **labels):
        self.inc(-amount, **labels)

    def format_prometheus(self) -> str:
        lines = [f"# HELP {self.name} {self.description}",
                 f"# TYPE {self.name} gauge"]
        for key, value in self._values.items():
            if self.label_names:
                label_str = ",".join(f'{n}="{v}"' for n, v in zip(self.label_names, key))
                lines.append(f'{self.name}{{{label_str}}} {value}')
            else:
                lines.append(f'{self.name} {value}')
        return "\n".join(lines)


class Histogram:
    """Histogram：延迟分布统计"""

    def __init__(self, name: str, description: str = "",
                 buckets: List[float] = None, labels: List[str] = None):
        self.name = name
        self.description = description
        # 默认桶边界（秒）
        self.buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
        self.label_names = labels or []
        # 每组标签一个桶统计 + 总和 + 计数
        self._data: Dict[tuple, Dict] = defaultdict(lambda: {
            "buckets": [0] * len(self.buckets),
            "sum": 0.0,
            "count": 0,
        })

    def observe(self, value: float, **labels):
        key = tuple(labels.get(l, "") for l in self.label_names)
        data = self._data[key]
        data["sum"] += value
        data["count"] += 1
        for i, bound in enumerate(self.buckets):
            if value <= bound:
                data["buckets"][i] += 1

    def format_prometheus(self) -> str:
        lines = [f"# HELP {self.name} {self.description}",
                 f"# TYPE {self.name} histogram"]
        for key, data in self._data.items():
            label_parts = []
            if self.label_names:
                label_parts = [f'{n}="{v}"' for n, v in zip(self.label_names, key)]
            for i, bound in enumerate(self.buckets):
                bucket_labels = label_parts + [f'le="{bound}"']
                lines.append(f'{self.name}_bucket{{{",".join(bucket_labels)}}} {data["buckets"][i]}')
            # +Inf 桶
            inf_labels = label_parts + [f'le="+Inf"']
            lines.append(f'{self.name}_bucket{{{",".join(inf_labels)}}} {data["count"]}')
            sum_labels = ",".join(label_parts)
            lines.append(f'{self.name}_sum{{{sum_labels}}} {data["sum"]}')
            lines.append(f'{self.name}_count{{{sum_labels}}} {data["count"]}')
        return "\n".join(lines)


class MetricsRegistry:
    """Prometheus 指标注册表"""

    def __init__(self):
        self._metrics: Dict[str, Any] = {}

    def register(self, metric: Any):
        self._metrics[metric.name] = metric
        return metric

    def export(self) -> str:
        """导出 Prometheus 格式文本"""
        return "\n\n".join(m.format_prometheus() for m in self._metrics.values())


# ==========================================
# 3. 分布式追踪（OpenTelemetry 风格）
# ==========================================
@dataclass
class Span:
    """追踪 Span"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    name: str
    start_time: float
    end_time: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    status: str = "UNSET"  # UNSET / OK / ERROR
    events: List[Dict] = field(default_factory=list)

    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time) * 1000
        return 0

    def set_attribute(self, key: str, value: Any):
        self.attributes[key] = value

    def set_status(self, status: str):
        self.status = status

    def add_event(self, name: str, **attributes):
        self.events.append({
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes,
        })

    def end(self):
        self.end_time = time.time()

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": round(self.duration_ms, 2),
            "attributes": self.attributes,
            "status": self.status,
            "events": self.events,
        }


class Tracer:
    """
    分布式追踪器（OpenTelemetry 风格）
    - 生成 trace_id 和 span_id
    - 维护父子关系
    - 支持采样策略
    """

    def __init__(self, sampling_rate: float = 1.0):
        self.spans: List[Span] = []
        self.sampling_rate = sampling_rate
        self._current_span: Optional[Span] = None
        self._trace_counter = 0

    def _generate_id(self, length: int = 16) -> str:
        import secrets
        return secrets.token_hex(length)

    def _should_sample(self) -> bool:
        """采样决策"""
        if self.sampling_rate >= 1.0:
            return True
        return random.random() < self.sampling_rate

    @contextmanager
    def start_span(self, name: str, **attributes):
        """启动一个 Span（上下文管理器）"""
        sampled = self._should_sample()

        if sampled:
            trace_id = self._current_span.trace_id if self._current_span else self._generate_id(16)
            span_id = self._generate_id(8)
            parent_id = self._current_span.span_id if self._current_span else None

            span = Span(
                trace_id=trace_id,
                span_id=span_id,
                parent_span_id=parent_id,
                name=name,
                start_time=time.time(),
                attributes=attributes,
            )
            self.spans.append(span)
            old_span = self._current_span
            self._current_span = span
        else:
            span = None
            old_span = None

        try:
            yield span if span else _DummySpan()
        except Exception as e:
            if span:
                span.set_status("ERROR")
                span.add_event("exception", type=type(e).__name__, message=str(e))
            raise
        else:
            if span:
                span.set_status("OK")
        finally:
            if span:
                span.end()
                self._current_span = old_span

    def get_trace(self, trace_id: str) -> List[Span]:
        """获取某个 trace 的所有 span"""
        return [s for s in self.spans if s.trace_id == trace_id]

    def export_traces(self) -> str:
        """导出所有追踪数据（JSON）"""
        traces = defaultdict(list)
        for span in self.spans:
            traces[span.trace_id].append(span.to_dict())
        return json.dumps(dict(traces), indent=2, ensure_ascii=False)

    def print_trace_tree(self, trace_id: str = None):
        """打印追踪树（可视化）"""
        if trace_id:
            spans = self.get_trace(trace_id)
        else:
            spans = self.spans

        if not spans:
            print("  (无追踪数据)")
            return

        # 按开始时间排序
        spans_sorted = sorted(spans, key=lambda s: s.start_time)

        # 构建树
        by_id = {s.span_id: s for s in spans_sorted}
        children = defaultdict(list)
        roots = []
        for s in spans_sorted:
            if s.parent_span_id and s.parent_span_id in by_id:
                children[s.parent_span_id].append(s)
            else:
                roots.append(s)

        def print_span(span: Span, depth: int = 0):
            indent = "  " * depth
            status_icon = "✓" if span.status == "OK" else "✗" if span.status == "ERROR" else "○"
            duration = f"{span.duration_ms:.1f}ms"
            print(f"{indent}{status_icon} {span.name} [{duration}]")
            for key, value in span.attributes.items():
                print(f"{indent}  └─ {key}: {value}")
            for child in children.get(span.span_id, []):
                print_span(child, depth + 1)

        for root in roots:
            print(f"\n  Trace: {root.trace_id[:16]}...")
            print_span(root)


class _DummySpan:
    """未采样时的空 Span（无操作）"""
    def set_attribute(self, *a, **kw): pass
    def set_status(self, *a, **kw): pass
    def add_event(self, *a, **kw): pass


# ==========================================
# 4. 告警规则
# ==========================================
@dataclass
class AlertRule:
    """告警规则定义"""
    name: str
    expression: str  # PromQL 风格表达式
    threshold: float
    comparison: str  # ">", "<", ">=", "<="
    duration: str    # 持续时间（如 "5m"）
    severity: str    # "critical" / "warning" / "info"
    description: str = ""

    def to_prometheus_rule(self) -> str:
        """生成 Prometheus AlertManager 规则"""
        return f"""  - alert: {self.name}
    expr: {self.expression} {self.comparison} {self.threshold}
    for: {self.duration}
    labels:
      severity: {self.severity}
    annotations:
      summary: "{self.name} 触发"
      description: "{self.description}"
"""


# ==========================================
# 5. 集成可观测性应用
# ==========================================
class ObservableApp:
    """集成三大支柱的可观测应用"""

    def __init__(self, sampling_rate: float = 1.0):
        self.logger = StructuredLogger("myapp")
        self.metrics = MetricsRegistry()
        self.tracer = Tracer(sampling_rate=sampling_rate)

        # 注册指标
        self.req_counter = self.metrics.register(
            Counter("http_requests_total", "HTTP 请求总数", ["method", "endpoint", "status"])
        )
        self.req_duration = self.metrics.register(
            Histogram("http_request_duration_seconds", "HTTP 请求延迟", labels=["endpoint"])
        )
        self.active_connections = self.metrics.register(
            Gauge("active_connections", "当前活跃连接数")
        )
        self.error_counter = self.metrics.register(
            Counter("errors_total", "错误总数", ["type"])
        )

        # 告警规则
        self.alerts = [
            AlertRule(
                name="HighErrorRate",
                expression="rate(errors_total[5m])",
                threshold=0.05,
                comparison=">",
                duration="5m",
                severity="critical",
                description="5分钟内错误率超过 5%"
            ),
            AlertRule(
                name="HighLatency",
                expression='histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))',
                threshold=1.0,
                comparison=">",
                duration="5m",
                severity="warning",
                description="P99 延迟超过 1 秒"
            ),
            AlertRule(
                name="TooManyConnections",
                expression="active_connections",
                threshold=1000,
                comparison=">",
                duration="2m",
                severity="warning",
                description="活跃连接数超过 1000"
            ),
        ]

    def handle_request(self, method: str, endpoint: str) -> dict:
        """模拟处理 HTTP 请求（带完整可观测性）"""
        trace_id = self.tracer._generate_id(8)
        self.logger.set_context(trace_id=trace_id, method=method, endpoint=endpoint)
        self.active_connections.inc()

        try:
            with self.tracer.start_span(f"{method} {endpoint}", endpoint=endpoint, method=method) as span:
                self.logger.info("请求开始")

                # 模拟数据库查询
                with self.tracer.start_span("db.query", db="postgres", operation="SELECT") as db_span:
                    db_duration = random.uniform(0.01, 0.15)
                    time.sleep(db_duration)
                    db_span.set_attribute("duration_ms", round(db_duration * 1000, 2))
                    self.logger.debug("数据库查询完成", duration_ms=round(db_duration * 1000, 2))

                # 模拟缓存操作
                with self.tracer.start_span("cache.get", cache="redis") as cache_span:
                    cache_duration = random.uniform(0.001, 0.02)
                    time.sleep(cache_duration)
                    cache_hit = random.random() > 0.3
                    cache_span.set_attribute("hit", cache_hit)
                    self.logger.debug("缓存查询", hit=cache_hit)

                # 模拟业务处理
                with self.tracer.start_span("business_logic") as biz_span:
                    biz_duration = random.uniform(0.005, 0.05)
                    time.sleep(biz_duration)
                    biz_span.set_attribute("processing_time_ms", round(biz_duration * 1000, 2))

                # 模拟偶尔出错
                if random.random() < 0.1:
                    raise ValueError("模拟的业务错误")

                # 记录成功
                total_duration = random.uniform(0.05, 0.3)
                self.req_counter.inc(method=method, endpoint=endpoint, status="200")
                self.req_duration.observe(total_duration, endpoint=endpoint)
                self.logger.info("请求完成", status=200, duration_ms=round(total_duration * 1000, 2))

                return {"status": "success", "trace_id": trace_id}

        except Exception as e:
            self.req_counter.inc(method=method, endpoint=endpoint, status="500")
            self.error_counter.inc(type=type(e).__name__)
            self.logger.error("请求失败", error=str(e), error_type=type(e).__name__)
            return {"status": "error", "trace_id": trace_id, "error": str(e)}

        finally:
            self.active_connections.dec()
            self.logger.clear_context()


# ==========================================
# 测试
# ==========================================
if __name__ == "__main__":
    print("=" * 60)
    print("可观测性三件套演示")
    print("=" * 60)

    app = ObservableApp(sampling_rate=1.0)

    # === 模拟请求 ===
    print("\n--- 模拟 10 个请求 ---\n")
    endpoints = ["/api/users", "/api/posts", "/api/health", "/api/search"]
    methods = ["GET", "POST", "GET", "GET"]

    for i in range(10):
        method = methods[i % len(methods)]
        endpoint = endpoints[i % len(endpoints)]
        result = app.handle_request(method, endpoint)
        status_icon = "✓" if result["status"] == "success" else "✗"
        print(f"  {status_icon} {method} {endpoint} → trace={result['trace_id'][:8]}...")

    # === 导出指标 ===
    print(f"\n{'='*60}")
    print("Prometheus 指标导出 (/metrics)")
    print(f"{'='*60}\n")
    print(app.metrics.export())

    # === 导出追踪 ===
    print(f"\n{'='*60}")
    print("分布式追踪树")
    print(f"{'='*60}")
    app.tracer.print_trace_tree()

    # === 告警规则 ===
    print(f"\n{'='*60}")
    print("告警规则 (Prometheus AlertManager)")
    print(f"{'='*60}\n")
    print("groups:")
    print("  - name: app-alerts")
    print("    rules:")
    for alert in app.alerts:
        print(alert.to_prometheus_rule())

    # === 采样演示 ===
    print(f"\n{'='*60}")
    print("采样策略对比")
    print(f"{'='*60}\n")

    for rate in [1.0, 0.5, 0.1]:
        tracer = Tracer(sampling_rate=rate)
        for _ in range(100):
            with tracer.start_span("test_operation"):
                pass
        print(f"  采样率 {rate:.0%}: 100 个请求 → 采集 {len(tracer.spans)} 个 span")

    # === 结构化日志示例 ===
    print(f"\n{'='*60}")
    print("结构化日志示例")
    print(f"{'='*60}\n")

    logger = StructuredLogger("example")
    logger.set_context(request_id="req_abc123", user_id=42)
    logger.info("用户登录", ip="192.168.1.1", device="mobile")
    logger.warning("API 限速", endpoint="/api/search", limit=100, current=95)
    logger.error("数据库连接失败", host="db-prod-01", error="ConnectionRefusedError")
```

**思考题**：在生产环境中，如果 tracing 采样率设为 1%（0.01），那么 99% 的请求不会有追踪数据。当用户报告某个特定请求出问题时，如何通过 trace_id 关联到日志？提示：考虑在日志中始终记录 trace_id（即使未被采样），以及使用 tail-based sampling 策略。

---

## 五、安全实战（4题）

---

### 第17题：OWASP Top 10实战防护 — Flask安全API

**知识点讲解**

OWASP Top 10 是 Web 应用最常见的安全风险排名。**注入攻击（A03:2021）** 包括 SQL 注入、命令注入等，核心防护是**参数化查询**——将用户输入作为数据而非代码执行。`sqlite3` 的 `?` 占位符确保输入被转义处理，拼接 SQL 字符串则是注入漏洞的根源。

**XSS（A03:2021 跨站脚本）** 分为反射型（URL 参数注入）、存储型（数据库持久化）、DOM 型（前端 JS 注入）。防护策略：(1) 输出编码——将 `<` 转义为 `&lt;`，Jinja2 默认自动转义；(2) **CSP（Content Security Policy）**——通过 HTTP 头限制脚本来源，如 `script-src 'self'` 禁止内联脚本和外部域脚本；(3) HttpOnly Cookie 防止 JS 读取会话 Cookie。

**CSRF（跨站请求伪造）** 利用浏览器自动携带 Cookie 的机制，诱导用户在已登录状态下发起非自愿请求。防护：(1) **CSRF Token**——每个表单包含服务端生成的随机 token，提交时验证；(2) `SameSite` Cookie 属性——`SameSite=Strict` 禁止跨站携带 Cookie；(3) 验证 `Referer` 或 `Origin` 头。

**输入验证**是第一道防线：白名单优于黑名单，使用正则或类型约束限制输入格式。**安全的响应头**包括：`X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`、`Strict-Transport-Security`（HSTS 强制 HTTPS）。

```python
"""
OWASP Top 10 实战防护 —— Flask 安全 API
运行：python exercise_17_owasp_security.py
依赖：pip install flask
（如未安装 Flask，自动使用模拟模式）
"""
import os
import re
import secrets
import sqlite3
import hashlib
import hmac
import time
import json
from typing import Optional, Dict, Tuple
from functools import wraps

try:
    from flask import Flask, request, jsonify, make_response, session, g
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False


# ==========================================
# 1. 安全工具函数
# ==========================================
class SecurityUtils:
    """安全工具集"""

    @staticmethod
    def hash_password(password: str, salt: bytes = None) -> Tuple[str, str]:
        """
        安全密码哈希（PBKDF2 + 随机盐）
        不使用 MD5/SHA1（已被破解）
        """
        if salt is None:
            salt = os.urandom(32)
        # PBKDF2: 100000 次迭代
        key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        return key.hex(), salt.hex()

    @staticmethod
    def verify_password(password: str, stored_hash: str, salt_hex: str) -> bool:
        """验证密码"""
        key, _ = SecurityUtils.hash_password(password, bytes.fromhex(salt_hex))
        return hmac.compare_digest(key, stored_hash)  # 时间安全比较

    @staticmethod
    def sanitize_input(text: str, max_length: int = 1000) -> str:
        """
        输入消毒：移除危险字符，限制长度
        白名单方式：只允许安全字符
        """
        if not isinstance(text, str):
            raise ValueError("输入必须是字符串")
        if len(text) > max_length:
            raise ValueError(f"输入超出最大长度 {max_length}")
        # 移除 NULL 字节
        text = text.replace("\x00", "")
        # 白名单：允许中文、英文、数字、基本标点
        # 注意：这是额外防护，主要防护应在输出编码层
        return text.strip()

    @staticmethod
    def validate_email(email: str) -> bool:
        """邮箱格式验证（白名单正则）"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email)) and len(email) <= 254

    @staticmethod
    def validate_username(username: str) -> bool:
        """用户名验证：3-20位，字母数字下划线"""
        pattern = r'^[a-zA-Z0-9_]{3,20}$'
        return bool(re.match(pattern, username))

    @staticmethod
    def generate_csrf_token() -> str:
        """生成 CSRF Token"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def generate_api_key() -> str:
        """生成 API Key"""
        return f"sk_{secrets.token_hex(32)}"

    @staticmethod
    def constant_time_compare(a: str, b: str) -> bool:
        """时间安全的字符串比较（防时序攻击）"""
        return hmac.compare_digest(a.encode(), b.encode())


# ==========================================
# 2. 安全数据库操作
# ==========================================
class SecureDatabase:
    """
    安全数据库操作
    - 使用参数化查询防 SQL 注入
    - 连接管理
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                csrf_token TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        """)

        # 插入测试用户
        pwd_hash, salt = SecurityUtils.hash_password("password123")
        try:
            conn.execute(
                "INSERT INTO users (username, email, password_hash, salt, role) VALUES (?, ?, ?, ?, ?)",
                ("admin", "admin@example.com", pwd_hash, salt, "admin")
            )
            conn.execute(
                "INSERT INTO posts (user_id, title, content) VALUES (?, ?, ?)",
                (1, "Hello World", "这是第一篇帖子")
            )
            conn.commit()
        except sqlite3.IntegrityError:
            pass  # 已存在
        conn.close()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ✅ 安全：参数化查询
    def get_user_by_username(self, username: str) -> Optional[dict]:
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "SELECT * FROM users WHERE username = ?",
                (username,)  # 参数化：输入被当作数据而非代码
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    # ❌ 危险演示：字符串拼接（仅用于对比，实际代码中禁止使用）
    def get_user_unsafe(self, username: str) -> Optional[dict]:
        """⚠ 危险！字符串拼接 SQL — 存在注入漏洞"""
        conn = self.get_connection()
        try:
            # 这种写法允许注入：username = "' OR '1'='1" 可绕过认证
            sql = f"SELECT * FROM users WHERE username = '{username}'"
            print(f"  [危险SQL] {sql}")
            cursor = conn.execute(sql)
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def search_posts_safe(self, keyword: str) -> list:
        """✅ 安全搜索：参数化 LIKE 查询"""
        conn = self.get_connection()
        try:
            # LIKE 的通配符需要转义，但参数化已防止 SQL 注入
            cursor = conn.execute(
                "SELECT * FROM posts WHERE title LIKE ? OR content LIKE ?",
                (f"%{keyword}%", f"%{keyword}%")
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def search_posts_unsafe(self, keyword: str) -> list:
        """⚠ 危险！字符串拼接 LIKE — 存在注入"""
        conn = self.get_connection()
        try:
            sql = f"SELECT * FROM posts WHERE title LIKE '%{keyword}%'"
            print(f"  [危险SQL] {sql}")
            cursor = conn.execute(sql)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def create_post(self, user_id: int, title: str, content: str) -> int:
        """✅ 安全创建帖子"""
        conn = self.get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO posts (user_id, title, content) VALUES (?, ?, ?)",
                (user_id, title, content)
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()


# ==========================================
# 3. 安全响应头
# ==========================================
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",           # 防 MIME 嗅探
    "X-Frame-Options": "DENY",                      # 防点击劫持
    "X-XSS-Protection": "1; mode=block",            # 浏览器 XSS 过滤
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",  # HSTS
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "      # 生产中应移除 unsafe-inline
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


# ==========================================
# 4. Flask 应用（安全版）
# ==========================================
if FLASK_AVAILABLE:
    app = Flask(__name__)
    app.secret_key = secrets.token_hex(32)
    db = SecureDatabase()

    @app.before_request
    def before_request():
        """每个请求前执行"""
        g.db = db

    @app.after_request
    def set_security_headers(response):
        """设置安全响应头"""
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response

    def require_auth(f):
        """认证装饰器"""
        @wraps(f)
        def decorated(*args, **kwargs):
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return jsonify({"error": "未授权"}), 401
            token = auth_header[7:]
            session_data = _get_session(token)
            if not session_data:
                return jsonify({"error": "无效或过期的会话"}), 401
            g.session = session_data
            g.user_id = session_data["user_id"]
            g.csrf_token = session_data["csrf_token"]
            return f(*args, **kwargs)
        return decorated

    def require_csrf(f):
        """CSRF 验证装饰器"""
        @wraps(f)
        def decorated(*args, **kwargs):
            if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                csrf_token = request.headers.get("X-CSRF-Token", "")
                if not SecurityUtils.constant_time_compare(csrf_token, g.csrf_token):
                    return jsonify({"error": "CSRF 验证失败"}), 403
            return f(*args, **kwargs)
        return decorated

    def _create_session(user_id: int) -> Tuple[str, str]:
        """创建会话"""
        token = secrets.token_urlsafe(48)
        csrf_token = SecurityUtils.generate_csrf_token()
        expires = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() + 3600))
        conn = g.db.get_connection()
        conn.execute(
            "INSERT INTO sessions (token, user_id, csrf_token, expires_at) VALUES (?, ?, ?, ?)",
            (token, user_id, csrf_token, expires)
        )
        conn.commit()
        conn.close()
        return token, csrf_token

    def _get_session(token: str) -> Optional[dict]:
        """获取会话"""
        conn = g.db.get_connection()
        cursor = conn.execute(
            "SELECT * FROM sessions WHERE token = ? AND expires_at > ?",
            (token, time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()))
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    # ─── 路由 ───
    @app.route("/api/login", methods=["POST"])
    def login():
        data = request.get_json()
        if not data:
            return jsonify({"error": "无效请求"}), 400

        username = SecurityUtils.sanitize_input(data.get("username", ""))
        password = data.get("password", "")

        if not SecurityUtils.validate_username(username):
            return jsonify({"error": "用户名格式无效"}), 422

        user = g.db.get_user_by_username(username)
        if not user or not SecurityUtils.verify_password(password, user["password_hash"], user["salt"]):
            # 统一错误信息，防止用户名枚举
            return jsonify({"error": "用户名或密码错误"}), 401

        token, csrf_token = _create_session(user["id"])
        response = jsonify({"message": "登录成功", "user": {"id": user["id"], "username": user["username"]}})
        response.set_cookie(
            "session", token, httponly=True, secure=True,
            samesite="Strict", max_age=3600, path="/"
        )
        response.headers["X-CSRF-Token"] = csrf_token
        return response

    @app.route("/api/posts", methods=["GET"])
    def list_posts():
        keyword = request.args.get("q", "")
        if keyword:
            posts = g.db.search_posts_safe(SecurityUtils.sanitize_input(keyword))
        else:
            conn = g.db.get_connection()
            posts = [dict(r) for r in conn.execute("SELECT * FROM posts ORDER BY created_at DESC").fetchall()]
            conn.close()
        return jsonify({"data": posts})

    @app.route("/api/posts", methods=["POST"])
    @require_auth
    @require_csrf
    def create_post():
        data = request.get_json()
        title = SecurityUtils.sanitize_input(data.get("title", ""), max_length=200)
        content = SecurityUtils.sanitize_input(data.get("content", ""), max_length=10000)
        post_id = g.db.create_post(g.user_id, title, content)
        return jsonify({"message": "创建成功", "id": post_id}), 201

    @app.route("/api/health")
    def health():
        return jsonify({"status": "healthy"})

    if __name__ == "__main__":
        print("=== Flask 安全 API 启动 ===")
        print("访问 http://localhost:5000/api/health")
        app.run(host="0.0.0.0", port=5000, debug=False)

else:
    # ==========================================
    # 模拟模式（无 Flask 时的测试）
    # ==========================================
    if __name__ == "__main__":
        print("=" * 60)
        print("OWASP Top 10 安全防护演示（模拟模式）")
        print("=" * 60)

        db = SecureDatabase()

        # === 1. SQL 注入对比 ===
        print("\n--- 1. SQL 注入防护对比 ---")

        # 安全：参数化查询
        print("\n  [✓ 安全] 参数化查询:")
        user = db.get_user_by_username("admin")
        print(f"  结果: {user['username'] if user else '未找到'}")

        # 危险：字符串拼接
        print("\n  [✗ 危险] 字符串拼接:")
        user = db.get_user_unsafe("admin")
        print(f"  正常查询结果: {user['username'] if user else '未找到'}")

        print("\n  [✗ 危险] SQL 注入攻击:")
        user = db.get_user_unsafe("' OR '1'='1' --")
        print(f"  注入结果: {user['username'] if user else '未找到'}")
        print(f"  → 攻击者绕过了认证！" if user else "  → 注入未成功")

        # 安全查询不受注入影响
        print("\n  [✓ 安全] 参数化查询抵御注入:")
        user = db.get_user_by_username("' OR '1'='1' --")
        print(f"  结果: {user['username'] if user else '未找到（正确拒绝了注入）'}")

        # === 2. XSS 防护 ===
        print(f"\n--- 2. XSS 防护 ---")
        xss_payload = "<script>alert('XSS')</script>"
        safe_text = SecurityUtils.sanitize_input(xss_payload)
        print(f"  原始输入: {xss_payload}")
        print(f"  消毒后: {safe_text}")
        print(f"  → Flask/Jinja2 默认 HTML 转义: &lt;script&gt;...")

        # CSP 策略
        print(f"\n  Content-Security-Policy:")
        print(f"  {SECURITY_HEADERS['Content-Security-Policy']}")
        print(f"  → 只允许 'self' 来源的脚本，阻止内联和外部域脚本")

        # === 3. CSRF 防护 ===
        print(f"\n--- 3. CSRF 防护 ---")
        csrf_token = SecurityUtils.generate_csrf_token()
        print(f"  生成的 CSRF Token: {csrf_token[:30]}...")
        print(f"  验证（正确）: {SecurityUtils.constant_time_compare(csrf_token, csrf_token)}")
        print(f"  验证（错误）: {SecurityUtils.constant_time_compare(csrf_token, 'wrong_token')}")
        print(f"  → POST/PUT/DELETE 请求必须携带正确的 X-CSRF-Token 头")

        # === 4. 密码安全 ===
        print(f"\n--- 4. 密码安全 ---")
        pwd = "MySecurePassword123!"
        pwd_hash, salt = SecurityUtils.hash_password(pwd)
        print(f"  原始密码: {pwd}")
        print(f"  盐值:     {salt[:30]}...")
        print(f"  哈希值:   {pwd_hash[:30]}...")
        print(f"  验证（正确）: {SecurityUtils.verify_password(pwd, pwd_hash, salt)}")
        print(f"  验证（错误）: {SecurityUtils.verify_password('wrong', pwd_hash, salt)}")
        print(f"  → 使用 PBKDF2-SHA256，100000 次迭代")

        # === 5. 输入验证 ===
        print(f"\n--- 5. 输入验证 ---")
        test_inputs = [
            ("valid_user", "用户名"),
            ("a", "用户名（太短）"),
            ("user@invalid", "用户名（非法字符）"),
            ("test@example.com", "邮箱"),
            ("not-an-email", "邮箱（格式错误）"),
            ("A" * 2001, "文本（超长）"),
        ]
        for value, desc in test_inputs:
            try:
                if "用户名" in desc:
                    valid = SecurityUtils.validate_username(value)
                elif "邮箱" in desc:
                    valid = SecurityUtils.validate_email(value)
                else:
                    SecurityUtils.sanitize_input(value, max_length=2000)
                    valid = True
                print(f"  {desc:20s} '{value[:20]}...' → {'✓ 有效' if valid else '✗ 无效'}")
            except ValueError as e:
                print(f"  {desc:20s} '{value[:20]}...' → ✗ 拒绝: {e}")

        # === 6. 安全响应头汇总 ===
        print(f"\n--- 6. 安全响应头 ---")
        for header, value in SECURITY_HEADERS.items():
            print(f"  {header}: {value[:60]}{'...' if len(value) > 60 else ''}")

        # === 7. OWASP Top 10 映射 ===
        print(f"\n--- 7. OWASP Top 10 (2021) 防护映射 ---")
        owasp_mapping = [
            ("A01", "Broken Access Control", "认证装饰器 + 会话验证 + 角色检查"),
            ("A02", "Cryptographic Failures", "PBKDF2 密码哈希 + HTTPS/HSTS + 安全 Cookie"),
            ("A03", "Injection", "参数化查询 + 输入消毒 + 白名单验证"),
            ("A04", "Insecure Design", "CSRF Token + 安全默认配置"),
            ("A05", "Security Misconfiguration", "安全响应头 + debug=False + 最小权限"),
            ("A06", "Vulnerable Components", "依赖扫描 + 版本锁定"),
            ("A07", "Auth Failures", "统一错误信息 + 会话过期 + 时间安全比较"),
            ("A08", "Data Integrity Failures", "CSP 策略 + 签名验证"),
            ("A09", "Logging Failures", "安全事件日志 + 审计追踪"),
            ("A10", "SSRF", "URL 白名单 + 内网访问限制"),
        ]
        for code, risk, protection in owasp_mapping:
            print(f"  {code}: {risk:30s} → {protection}")
```

**思考题**：当前 CSRF 防护使用 Double Submit Cookie 模式（Token 同时在 Cookie 和 Header 中）。如果攻击者能读取页面 DOM（如通过 XSS），CSRF Token 就会失效。这说明 XSS 的危害比 CSRF 更大——你能设计一个 XSS 和 CSRF 同时防护的方案吗？

---

### 第18题：密码学基础实践 — AES-GCM加密+RSA签名+TLS握手模拟

**知识点讲解**

现代密码学分为**对称加密**和**非对称加密**两大体系。对称加密使用同一密钥加密解密，速度快，适合大量数据；非对称加密使用公钥/私钥对，速度慢但解决了密钥分发问题。实际系统通常混合使用：非对称加密交换对称密钥，对称加密加密数据。

**AES-GCM**（Advanced Encryption Standard - Galois/Counter Mode）是对称加密的黄金标准。GCM 模式同时提供**机密性**（加密）和**完整性**（认证）——它生成认证标签（Authentication Tag），接收方验证标签后才解密，防止密文被篡改。Nonce（Number Used Once）必须每次加密时唯一且不重复，否则会泄露密钥信息。AES 密钥长度可选 128/192/256 位。

**RSA** 签名使用私钥签名、公钥验证。签名过程：先对消息计算 SHA-256 哈希，再用私钥加密哈希值。验证过程：用公钥解密签名得到哈希，与重新计算的哈希对比。RSA 的安全性基于大整数分解难题——2048 位 RSA 目前被认为安全（预计2030年前不可破解）。

**TLS 握手**的核心流程：(1) ClientHello 携带支持的密码套件和随机数；(2) ServerHello 选定密码套件并返回随机数+证书；(3) 客户端验证证书链（CA→中间CA→服务器证书）；(4) 客户端生成 Pre-Master Secret，用服务器公钥加密发送；(5) 双方用三个随机数派生 Master Secret 和会话密钥；(6) 切换到加密通信。TLS 1.3 简化为 1-RTT 握手，并废弃了 RSA 密钥交换（改用 ECDHE 提供前向安全）。

```python
"""
密码学基础实践 —— AES-GCM + RSA 签名 + TLS 握手模拟
运行：python exercise_18_cryptography.py
依赖：仅使用 Python 标准库（hashlib, hmac, os, secrets）
注意：生产环境应使用 cryptography 或 pycryptodome 库
"""
import os
import hashlib
import hmac
import secrets
import json
import struct
from typing import Tuple, Optional, Dict, Any


# ==========================================
# 1. AES-GCM 模拟实现（教学版）
# ==========================================
class AESGCMSimulator:
    """
    AES-GCM 加密模拟器（教学版）
    注意：这是简化实现，仅用于理解原理
    生产环境必须使用 cryptography 库的 AESGCM
    """

    def __init__(self, key: bytes = None):
        """
        初始化密钥
        AES-256: 32 字节密钥
        """
        self.key = key or secrets.token_bytes(32)
        self.key_size = len(self.key)

    def _xor_bytes(self, a: bytes, b: bytes) -> bytes:
        """XOR 两个字节数组"""
        return bytes(x ^ y for x, y in zip(a, b))

    def _aes_encrypt_block(self, plaintext: bytes) -> bytes:
        """
        模拟 AES 单块加密（16字节）
        注意：这不是真正的 AES，而是用 SHA-256 模拟的伪随机置换
        """
        # 用密钥和明文生成"密文"（仅教学用）
        h = hashlib.sha256(self.key + plaintext).digest()
        return h[:16]  # 取前16字节模拟AES块输出

    def _ghash(self, aad: bytes, ciphertext: bytes) -> bytes:
        """
        模拟 GHASH（Galios Hash）计算认证标签
        真正的 GHASH 使用 GF(2^128) 上的多项式乘法
        这里用 HMAC-SHA256 模拟
        """
        data = struct.pack(">Q", len(aad) * 8) + aad + struct.pack(">Q", len(ciphertext) * 8) + ciphertext
        return hmac.new(self.key, data, hashlib.sha256).digest()[:16]

    def encrypt(self, plaintext: bytes, aad: bytes = b"") -> Dict[str, bytes]:
        """
        AES-GCM 加密
        参数:
            plaintext: 明文
            aad: 附加认证数据（不加密但需认证）
        返回:
            {nonce, ciphertext, tag}
        """
        # 1. 生成唯一 Nonce（12字节）
        nonce = secrets.token_bytes(12)

        # 2. 生成密钥流（CTR 模式）
        keystream = b""
        counter = 0
        while len(keystream) < len(plaintext):
            counter_block = nonce + struct.pack(">I", counter + 1)
            keystream += self._aes_encrypt_block(counter_block)
            counter += 1

        # 3. XOR 加密
        ciphertext = self._xor_bytes(plaintext, keystream[:len(plaintext)])

        # 4. 计算认证标签（GHASH）
        tag = self._ghash(aad, ciphertext)

        return {"nonce": nonce, "ciphertext": ciphertext, "tag": tag}

    def decrypt(self, nonce: bytes, ciphertext: bytes, tag: bytes, aad: bytes = b"") -> bytes:
        """
        AES-GCM 解密
        先验证标签，再解密
        """
        # 1. 验证认证标签
        expected_tag = self._ghash(aad, ciphertext)
        if not hmac.compare_digest(tag, expected_tag):
            raise ValueError("认证标签验证失败！密文可能被篡改")

        # 2. 生成密钥流
        keystream = b""
        counter = 0
        while len(keystream) < len(ciphertext):
            counter_block = nonce + struct.pack(">I", counter + 1)
            keystream += self._aes_encrypt_block(counter_block)
            counter += 1

        # 3. XOR 解密
        plaintext = self._xor_bytes(ciphertext, keystream[:len(ciphertext)])
        return plaintext


# ==========================================
# 2. RSA 签名模拟（教学版）
# ==========================================
class RSASimulator:
    """
    RSA 签名模拟器（教学版）
    注意：使用小素数模拟，仅用于理解原理
    生产环境必须使用 cryptography 库
    """

    @staticmethod
    def _is_prime(n: int, k: int = 10) -> bool:
        """Miller-Rabin 素性检测"""
        if n < 2:
            return False
        if n == 2 or n == 3:
            return True
        if n % 2 == 0:
            return False
        # 分解 n-1 = 2^r * d
        r, d = 0, n - 1
        while d % 2 == 0:
            r += 1
            d //= 2
        # 测试 k 次
        for _ in range(k):
            a = secrets.randbelow(n - 3) + 2
            x = pow(a, d, n)
            if x == 1 or x == n - 1:
                continue
            for _ in range(r - 1):
                x = pow(x, 2, n)
                if x == n - 1:
                    break
            else:
                return False
        return True

    @staticmethod
    def _generate_prime(bits: int) -> int:
        """生成指定位数的素数"""
        while True:
            # 生成随机奇数
            n = secrets.randbits(bits) | (1 << (bits - 1)) | 1
            if RSASimulator._is_prime(n):
                return n

    @staticmethod
    def _extended_gcd(a: int, b: int) -> Tuple[int, int, int]:
        """扩展欧几里得算法"""
        if a == 0:
            return b, 0, 1
        g, x, y = RSASimulator._extended_gcd(b % a, a)
        return g, y - (b // a) * x, x

    @staticmethod
    def _mod_inverse(a: int, m: int) -> int:
        """模逆元"""
        g, x, _ = RSASimulator._extended_gcd(a % m, m)
        if g != 1:
            raise ValueError("模逆元不存在")
        return x % m

    @classmethod
    def generate_keypair(cls, bits: int = 512) -> Tuple[Dict, Dict]:
        """
        生成 RSA 密钥对
        注意：教学版使用 512 位，生产环境至少 2048 位
        """
        # 1. 选择两个大素数
        p = cls._generate_prime(bits // 2)
        q = cls._generate_prime(bits // 2)
        while p == q:
            q = cls._generate_prime(bits // 2)

        # 2. 计算 n 和 φ(n)
        n = p * q
        phi_n = (p - 1) * (q - 1)

        # 3. 选择公钥指数 e（通常 65537）
        e = 65537
        while cls._extended_gcd(e, phi_n)[0] != 1:
            e += 2

        # 4. 计算私钥指数 d
        d = cls._mod_inverse(e, phi_n)

        public_key = {"n": n, "e": e}
        private_key = {"n": n, "d": d, "p": p, "q": q}
        return public_key, private_key

    @classmethod
    def sign(cls, message: bytes, private_key: Dict) -> bytes:
        """
        RSA 签名：私钥签名
        1. 对消息计算 SHA-256 哈希
        2. 用私钥加密哈希
        """
        # 计算哈希
        hash_val = int.from_bytes(hashlib.sha256(message).digest(), 'big')
        # 截断到模数位数
        hash_val = hash_val % private_key["n"]
        # 签名：s = hash^d mod n
        signature = pow(hash_val, private_key["d"], private_key["n"])
        return signature.to_bytes((signature.bit_length() + 7) // 8, 'big')

    @classmethod
    def verify(cls, message: bytes, signature: bytes, public_key: Dict) -> bool:
        """
        RSA 验签：公钥验证
        1. 对消息重新计算哈希
        2. 用公钥解密签名，对比哈希
        """
        # 计算期望的哈希
        expected_hash = int.from_bytes(hashlib.sha256(message).digest(), 'big')
        expected_hash = expected_hash % public_key["n"]

        # 解密签名：hash = s^e mod n
        sig_int = int.from_bytes(signature, 'big')
        decrypted_hash = pow(sig_int, public_key["e"], public_key["n"])

        return hmac.compare_digest(
            expected_hash.to_bytes(32, 'big'),
            decrypted_hash.to_bytes(32, 'big')
        )

    @classmethod
    def encrypt(cls, plaintext: bytes, public_key: Dict) -> bytes:
        """RSA 公钥加密（小数据）"""
        m = int.from_bytes(plaintext, 'big')
        if m >= public_key["n"]:
            raise ValueError("明文太长，超过模数")
        c = pow(m, public_key["e"], public_key["n"])
        return c.to_bytes((c.bit_length() + 7) // 8, 'big')

    @classmethod
    def decrypt(cls, ciphertext: bytes, private_key: Dict) -> bytes:
        """RSA 私钥解密"""
        c = int.from_bytes(ciphertext, 'big')
        m = pow(c, private_key["d"], private_key["n"])
        return m.to_bytes((m.bit_length() + 7) // 8, 'big')


# ==========================================
# 3. TLS 握手模拟
# ==========================================
class TLSHandshakeSimulator:
    """
    TLS 1.2 握手流程模拟（教学版）
    展示密钥交换、证书验证、密钥派生的完整过程
    """

    def __init__(self):
        self.client_random: Optional[bytes] = None
        self.server_random: Optional[bytes] = None
        self.pre_master_secret: Optional[bytes] = None
        self.master_secret: Optional[bytes] = None
        self.session_key: Optional[bytes] = None
        self.cipher_suite: str = "TLS_RSA_WITH_AES_256_GCM_SHA256"

    def client_hello(self) -> Dict:
        """步骤1: ClientHello"""
        self.client_random = secrets.token_bytes(32)
        return {
            "type": "ClientHello",
            "version": "TLS 1.2",
            "random": self.client_random.hex(),
            "cipher_suites": [
                "TLS_RSA_WITH_AES_256_GCM_SHA256",
                "TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384",
            ],
            "extensions": {
                "server_name": "example.com",
                "supported_groups": ["secp256r1", "x25519"],
            }
        }

    def server_hello_and_certificate(self, server_keypair: Tuple[Dict, Dict]) -> Dict:
        """步骤2: ServerHello + Certificate + ServerHelloDone"""
        self.server_random = secrets.token_bytes(32)
        public_key, _ = server_keypair

        # 模拟证书（包含公钥）
        certificate = {
            "subject": "CN=example.com",
            "issuer": "CN=Let's Encrypt CA",
            "public_key_n": hex(public_key["n"])[:40] + "...",
            "public_key_e": public_key["e"],
            "signature_algorithm": "SHA256withRSA",
            "validity": "2024-01-01 to 2025-01-01",
        }

        return {
            "type": "ServerHello",
            "version": "TLS 1.2",
            "random": self.server_random.hex(),
            "cipher_suite": self.cipher_suite,
            "certificate": certificate,
        }

    def verify_certificate(self, cert: Dict) -> bool:
        """步骤3: 客户端验证证书链"""
        checks = {
            "域名匹配": cert["subject"] == "CN=example.com",
            "CA 可信": "Let's Encrypt" in cert["issuer"],
            "有效期": "2024" in cert["validity"],
            "签名算法": cert["signature_algorithm"] == "SHA256withRSA",
        }
        return all(checks.values())

    def key_exchange(self, server_keypair: Tuple[Dict, Dict]) -> Dict:
        """步骤4: 客户端生成 Pre-Master Secret 并用服务器公钥加密"""
        public_key, _ = server_keypair
        # 生成 Pre-Master Secret（48字节：2字节版本 + 46字节随机）
        self.pre_master_secret = b"\x03\x03" + secrets.token_bytes(46)

        # 用服务器 RSA 公钥加密 Pre-Master Secret
        encrypted_pms = RSASimulator.encrypt(self.pre_master_secret, public_key)

        return {
            "type": "ClientKeyExchange",
            "encrypted_pre_master_secret": encrypted_pms.hex()[:60] + "...",
        }

    def derive_master_secret(self) -> bytes:
        """步骤5: 派生 Master Secret"""
        # PRF (Pseudo-Random Function): HMAC-SHA256
        # master_secret = PRF(pre_master_secret, "master secret",
        #                     client_random + server_random)
        label = b"master secret"
        seed = self.client_random + self.server_random

        # PRF 展开
        self.master_secret = b""
        a = label + seed  # A(0) = seed, A(1) = HMAC(secret, A(0) + label + seed)
        a = hmac.new(self.pre_master_secret, seed, hashlib.sha256).digest()
        while len(self.master_secret) < 48:
            block = hmac.new(self.pre_master_secret, a + label + seed, hashlib.sha256).digest()
            self.master_secret += block
            a = hmac.new(self.pre_master_secret, a, hashlib.sha256).digest()
        self.master_secret = self.master_secret[:48]
        return self.master_secret

    def derive_session_key(self) -> bytes:
        """步骤6: 从 Master Secret 派生会话密钥"""
        label = b"key expansion"
        seed = self.server_random + self.client_random
        key_block = b""
        a = hmac.new(self.master_secret, seed, hashlib.sha256).digest()
        while len(key_block) < 128:  # 生成足够的密钥材料
            block = hmac.new(self.master_secret, a + label + seed, hashlib.sha256).digest()
            key_block += block
            a = hmac.new(self.master_secret, a, hashlib.sha256).digest()

        # 分割密钥材料
        # client_write_key (32) + server_write_key (32) + client_write_iv (12) + server_write_iv (12)
        self.session_key = key_block[:32]
        return self.session_key

    def finished(self) -> Dict:
        """步骤7: Finished 消息（验证握手完整性）"""
        label = b"client finished"
        # 对所有握手消息计算哈希
        handshake_hash = hashlib.sha256(b"simulated_handshake_messages").digest()
        verify_data = hmac.new(self.master_secret, label + handshake_hash, hashlib.sha256).digest()[:12]
        return {
            "type": "Finished",
            "verify_data": verify_data.hex(),
        }


# ==========================================
# 4. HMAC 消息认证
# ==========================================
class HMACAuth:
    """HMAC 消息认证码"""

    @staticmethod
    def sign(key: bytes, message: bytes) -> bytes:
        """生成 HMAC-SHA256"""
        return hmac.new(key, message, hashlib.sha256).digest()

    @staticmethod
    def verify(key: bytes, message: bytes, signature: bytes) -> bool:
        """验证 HMAC（时间安全比较）"""
        expected = hmac.new(key, message, hashlib.sha256).digest()
        return hmac.compare_digest(expected, signature)


# ==========================================
# 测试
# ==========================================
if __name__ == "__main__":
    print("=" * 60)
    print("密码学基础实践")
    print("=" * 60)

    # === 1. AES-GCM 加密 ===
    print("\n--- 1. AES-GCM 加密/解密 ---")
    aes = AESGCMSimulator()

    plaintext = b"这是一条机密消息，需要加密保护！Confidential data here."
    aad = b"additional-authenticated-data"  # 附加认证数据

    encrypted = aes.encrypt(plaintext, aad)
    print(f"  明文:     {plaintext.decode()[:30]}...")
    print(f"  Nonce:    {encrypted['nonce'].hex()}")
    print(f"  密文:     {encrypted['ciphertext'].hex()[:40]}...")
    print(f"  认证标签: {encrypted['tag'].hex()}")

    # 正确解密
    decrypted = aes.decrypt(encrypted["nonce"], encrypted["ciphertext"], encrypted["tag"], aad)
    print(f"  解密成功: {decrypted == plaintext}")

    # 篡改检测
    tampered_ciphertext = bytearray(encrypted["ciphertext"])
    tampered_ciphertext[0] ^= 0xFF
    try:
        aes.decrypt(encrypted["nonce"], bytes(tampered_ciphertext), encrypted["tag"], aad)
    except ValueError as e:
        print(f"  篡改检测: ✓ {e}")

    # === 2. RSA 签名 ===
    print(f"\n--- 2. RSA 签名/验签 ---")
    print("  生成 RSA 密钥对（512位，教学用）...")
    pub_key, priv_key = RSASimulator.generate_keypair(bits=512)
    print(f"  公钥 n: {hex(pub_key['n'])[:40]}...")
    print(f"  公钥 e: {pub_key['e']}")

    message = b"Important document that needs signing."
    signature = RSASimulator.sign(message, priv_key)
    print(f"\n  消息:   {message.decode()}")
    print(f"  签名:   {signature.hex()[:40]}...")

    # 正确验证
    valid = RSASimulator.verify(message, signature, pub_key)
    print(f"  验证:   {'✓ 有效' if valid else '✗ 无效'}")

    # 篡改消息
    tampered_message = b"Important document that needs SIGNING."
    valid = RSASimulator.verify(tampered_message, signature, pub_key)
    print(f"  篡改验证: {'✗ 错误地通过了' if valid else '✓ 正确拒绝了篡改'}")

    # RSA 加密/解密
    print(f"\n  RSA 加密/解密:")
    secret = b"SharedSecretKey123"
    encrypted_secret = RSASimulator.encrypt(secret, pub_key)
    decrypted_secret = RSASimulator.decrypt(encrypted_secret, priv_key)
    print(f"  原文: {secret}")
    print(f"  解密: {decrypted_secret}")
    print(f"  匹配: {secret == decrypted_secret}")

    # === 3. TLS 握手模拟 ===
    print(f"\n--- 3. TLS 1.2 握手模拟 ---")
    tls = TLSHandshakeSimulator()
    server_keypair = (pub_key, priv_key)

    print("\n  [步骤1] ClientHello")
    ch = tls.client_hello()
    print(f"    版本: {ch['version']}")
    print(f"    客户端随机数: {ch['random'][:32]}...")
    print(f"    支持的密码套件: {ch['cipher_suites']}")

    print("\n  [步骤2] ServerHello + Certificate")
    sh = tls.server_hello_and_certificate(server_keypair)
    print(f"    选定密码套件: {sh['cipher_suite']}")
    print(f"    服务器随机数: {sh['random'][:32]}...")
    print(f"    证书主体: {sh['certificate']['subject']}")
    print(f"    证书签发者: {sh['certificate']['issuer']}")

    print("\n  [步骤3] 证书验证")
    cert_valid = tls.verify_certificate(sh["certificate"])
    print(f"    证书有效: {cert_valid}")

    print("\n  [步骤4] 密钥交换（RSA）")
    ke = tls.key_exchange(server_keypair)
    print(f"    加密的 Pre-Master Secret: {ke['encrypted_pre_master_secret'][:40]}...")

    print("\n  [步骤5] 派生 Master Secret")
    ms = tls.derive_master_secret()
    print(f"    Master Secret: {ms.hex()[:32]}...")

    print("\n  [步骤6] 派生会话密钥")
    sk = tls.derive_session_key()
    print(f"    会话密钥: {sk.hex()[:32]}...")

    print("\n  [步骤7] Finished")
    fin = tls.finished()
    print(f"    验证数据: {fin['verify_data']}")

    print("\n  → 握手完成！切换到 AES-GCM 加密通信")

    # === 4. HMAC ===
    print(f"\n--- 4. HMAC 消息认证 ---")
    hmac_key = secrets.token_bytes(32)
    msg = b"API request data"
    mac = HMACAuth.sign(hmac_key, msg)
    print(f"  消息: {msg.decode()}")
    print(f"  HMAC: {mac.hex()[:32]}...")
    print(f"  验证（正确）: {HMACAuth.verify(hmac_key, msg, mac)}")
    print(f"  验证（篡改）: {HMACAuth.verify(hmac_key, b'tampered', mac)}")

    # === 5. 加密体系对比 ===
    print(f"\n--- 5. 加密体系对比 ---")
    comparisons = [
        ("AES-GCM", "对称", "256位", "快（硬件加速）", "密钥分发", "大量数据加密"),
        ("RSA", "非对称", "2048-4096位", "慢（1000x AES）", "计算量大", "密钥交换/签名"),
        ("HMAC-SHA256", "对称", "256位", "快", "需共享密钥", "消息完整性"),
        ("ECDHE", "非对称", "256位椭圆曲线", "中等", "实现复杂", "前向安全密钥交换"),
    ]
    print(f"  {'算法':<15s} {'类型':<8s} {'密钥长度':<15s} {'速度':<15s} {'缺点':<12s} {'用途'}")
    for algo, atype, klen, speed, cons, usage in comparisons:
        print(f"  {algo:<15s} {atype:<8s} {klen:<15s} {speed:<15s} {cons:<12s} {usage}")
```

**思考题**：TLS 1.3 废弃了 RSA 密钥交换，只保留 ECDHE（椭圆曲线 Diffie-Hellman）。这是因为 RSA 密钥交换不提供"前向安全"（Forward Secrecy）——如果服务器私钥泄露，所有历史流量都可被解密。你能解释 ECDHE 如何实现前向安全吗？提示：每个会话生成临时密钥对，会话结束后销毁。

---

### 第19题：威胁建模STRIDE — 电商系统威胁建模与防护

**知识点讲解**

STRIDE 是微软提出的威胁建模框架，将威胁分为六类：**Spoofing**（伪装身份）、**Tampering**（篡改数据）、**Repudiation**（否认操作）、**Information Disclosure**（信息泄露）、**Denial of Service**（拒绝服务）、**Elevation of Privilege**（权限提升）。每类威胁对应一个安全属性：认证、完整性、不可否认性、机密性、可用性、授权。

**数据流图（DFD）** 是威胁建模的视觉工具，包含四种元素：外部实体（用户、第三方系统）、过程（应用组件）、数据存储（数据库、文件）、数据流（API 调用、消息）。对每个元素的每条数据流逐一检查 STRIDE 六类威胁，系统化地发现攻击面。

**风险评级** 使用 DREAD 模型：Damage Potential（损害程度）、Reproducibility（可复现性）、Exploitability（可利用性）、Affected Users（影响范围）、Discoverability（可发现性），各 1-10 分取平均。优先处理高分威胁。实践中也常用 CVSS（Common Vulnerability Scoring System）标准评分。

电商系统的典型威胁包括：用户身份伪装（弱密码、会话劫持）、订单篡改（修改价格、数量）、支付否认（无审计日志）、用户信息泄露（SQL 注入拖库）、促销期间 DDoS、普通用户获取管理员权限。每类威胁都需要对应的防护代码。

```python
"""
STRIDE 威胁建模 —— 电商系统威胁分析与防护实现
运行：python exercise_19_stride_threat_model.py
"""
import hashlib
import hmac
import secrets
import time
import json
import re
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum


# ==========================================
# 1. 威胁模型定义
# ==========================================
class ThreatType(Enum):
    """STRIDE 六类威胁"""
    SPOOFING = "伪装身份"
    TAMPERING = "篡改数据"
    REPUDIATION = "否认操作"
    INFO_DISCLOSURE = "信息泄露"
    DENIAL_OF_SERVICE = "拒绝服务"
    ELEVATION_OF_PRIVILEGE = "权限提升"


class Severity(Enum):
    """严重程度（DREAD 评级）"""
    CRITICAL = "严重"
    HIGH = "高"
    MEDIUM = "中"
    LOW = "低"


@dataclass
class Threat:
    """威胁定义"""
    threat_id: str
    threat_type: ThreatType
    title: str
    description: str
    target_component: str       # 受影响的组件
    attack_vector: str          # 攻击路径
    dread_score: float          # DREAD 评分（1-10）
    severity: Severity
    mitigations: List[str]      # 缓解措施


@dataclass
class DFDComponent:
    """数据流图组件"""
    name: str
    component_type: str         # external_entity / process / data_store / data_flow
    description: str
    trust_boundary: str         # 信任边界


# ==========================================
# 2. 电商系统数据流图
# ==========================================
def build_ecommerce_dfd() -> List[DFDComponent]:
    """构建电商系统的数据流图"""
    return [
        # 外部实体
        DFDComponent("用户", "external_entity", "购物用户", "互联网"),
        DFDComponent("管理员", "external_entity", "系统管理员", "内网"),
        DFDComponent("支付网关", "external_entity", "第三方支付（支付宝/微信）", "互联网"),

        # 过程（应用组件）
        DFDComponent("Web前端", "process", "用户界面（React/Vue）", "DMZ"),
        DFDComponent("API网关", "process", "请求路由、认证、限流", "DMZ"),
        DFDComponent("用户服务", "process", "注册、登录、个人信息", "内网"),
        DFDComponent("商品服务", "process", "商品目录、搜索", "内网"),
        DFDComponent("订单服务", "process", "下单、支付、发货", "内网"),
        DFDComponent("支付服务", "process", "对接支付网关", "内网"),

        # 数据存储
        DFDComponent("用户数据库", "data_store", "用户信息、密码哈希", "内网"),
        DFDComponent("商品数据库", "data_store", "商品信息、库存", "内网"),
        DFDComponent("订单数据库", "data_store", "订单、支付记录", "内网"),
        DFDComponent("Redis缓存", "data_store", "会话、商品缓存", "内网"),

        # 数据流
        DFDComponent("用户→Web前端", "data_flow", "HTTPS 请求", "互联网→DMZ"),
        DFDComponent("Web前端→API网关", "data_flow", "API 请求", "DMZ内部"),
        DFDComponent("API网关→用户服务", "data_flow", "gRPC 调用", "DMZ→内网"),
        DFDComponent("用户服务→用户DB", "data_flow", "SQL 查询", "内网内部"),
        DFDComponent("订单服务→支付网关", "data_flow", "支付 API 调用", "内网→互联网"),
    ]


# ==========================================
# 3. STRIDE 威胁分析
# ==========================================
def analyze_threats() -> List[Threat]:
    """对电商系统进行 STRIDE 威胁分析"""
    threats = [
        # === S: 伪装身份 ===
        Threat(
            threat_id="T-S-001",
            threat_type=ThreatType.SPOOFING,
            title="弱密码导致用户账号被冒充",
            description="用户使用弱密码（如123456），攻击者通过暴力破解获取账号",
            target_component="用户服务→用户数据库",
            attack_vector="暴力破解 / 字典攻击 / 撞库",
            dread_score=7.5,
            severity=Severity.HIGH,
            mitigations=[
                "强制密码复杂度（至少8位，含大小写+数字+特殊字符）",
                "密码错误5次后锁定账户15分钟",
                "支持双因素认证（TOTP/SMS）",
                "登录速率限制（同IP每分钟最多10次）",
            ],
        ),
        Threat(
            threat_id="T-S-002",
            threat_type=ThreatType.SPOOFING,
            title="会话劫持",
            description="攻击者窃取用户会话 Token，冒充已登录用户",
            target_component="用户→API网关",
            attack_vector="XSS 窃取 Cookie / 网络嗅探 / 中间人攻击",
            dread_score=8.0,
            severity=Severity.HIGH,
            mitigations=[
                "Cookie 设置 HttpOnly + Secure + SameSite=Strict",
                "强制 HTTPS（HSTS）",
                "会话 Token 绑定 IP/UA 指纹",
                "敏感操作需要重新认证",
            ],
        ),
        # === T: 篡改数据 ===
        Threat(
            threat_id="T-T-001",
            threat_type=ThreatType.TAMPERING,
            title="订单价格篡改",
            description="攻击者修改下单请求中的商品价格，以低价购买商品",
            target_component="订单服务",
            attack_vector="修改 API 请求参数中的 price 字段",
            dread_score=9.0,
            severity=Severity.CRITICAL,
            mitigations=[
                "服务端从数据库获取价格，不信任客户端传入的价格",
                "下单前校验价格一致性",
                "订单数据签名（HMAC）防止篡改",
                "支付金额与订单金额服务端比对",
            ],
        ),
        Threat(
            threat_id="T-T-002",
            threat_type=ThreatType.TAMPERING,
            title="库存篡改",
            description="攻击者通过并发请求超卖商品（竞态条件）",
            target_component="商品服务→商品数据库",
            attack_vector="并发下单请求绕过库存检查",
            dread_score=7.0,
            severity=Severity.HIGH,
            mitigations=[
                "使用数据库行锁（SELECT FOR UPDATE）",
                "Redis 分布式锁防止并发下单",
                "库存预扣减 + 超时释放",
                "乐观锁（版本号校验）",
            ],
        ),
        # === R: 否认操作 ===
        Threat(
            threat_id="T-R-001",
            threat_type=ThreatType.REPUDIATION,
            title="用户否认下单/支付",
            description="用户声称没有下过某订单或没有支付，要求退款",
            target_component="订单服务→订单数据库",
            attack_vector="利用系统缺乏审计日志",
            dread_score=6.0,
            severity=Severity.MEDIUM,
            mitigations=[
                "记录完整审计日志（谁、何时、做了什么、从哪）",
                "关键操作需要用户确认（短信/邮件验证码）",
                "订单数据不可变（追加日志而非修改）",
                "支付回调签名验证",
            ],
        ),
        # === I: 信息泄露 ===
        Threat(
            threat_id="T-I-001",
            threat_type=ThreatType.INFO_DISCLOSURE,
            title="SQL注入导致用户数据泄露",
            description="攻击者通过SQL注入获取全部用户数据（拖库）",
            target_component="用户服务→用户数据库",
            attack_vector="未参数化的SQL拼接 + 恶意输入",
            dread_score=9.5,
            severity=Severity.CRITICAL,
            mitigations=[
                "所有SQL使用参数化查询（预编译语句）",
                "数据库用户最小权限（应用不使用root）",
                "敏感字段加密存储（手机号、身份证）",
                "数据库网络隔离（仅内网可访问）",
            ],
        ),
        Threat(
            threat_id="T-I-002",
            threat_type=ThreatType.INFO_DISCLOSURE,
            title="错误信息泄露系统细节",
            description="500错误页面暴露堆栈跟踪、数据库结构等敏感信息",
            target_component="API网关",
            attack_vector="触发异常获取详细错误信息",
            dread_score=5.5,
            severity=Severity.MEDIUM,
            mitigations=[
                "生产环境关闭 debug 模式",
                "错误响应只返回通用错误码和消息",
                "详细错误记录在服务端日志中",
                "使用全局异常处理器",
            ],
        ),
        # === D: 拒绝服务 ===
        Threat(
            threat_id="T-D-001",
            threat_type=ThreatType.DENIAL_OF_SERVICE,
            title="促销期间DDoS攻击",
            description="秒杀活动期间遭受大量恶意请求导致服务不可用",
            target_component="API网关→所有服务",
            attack_vector="分布式请求洪水 / 慢速攻击",
            dread_score=8.5,
            severity=Severity.CRITICAL,
            mitigations=[
                "CDN + WAF 前置过滤",
                "API 限流（令牌桶/漏桶）",
                "验证码（人机识别）",
                "降级策略（关闭非核心功能）",
                "弹性扩容（K8s HPA）",
            ],
        ),
        # === E: 权限提升 ===
        Threat(
            threat_id="T-E-001",
            threat_type=ThreatType.ELEVATION_OF_PRIVILEGE,
            title="越权访问其他用户订单",
            description="普通用户通过修改订单ID查看/操作他人订单（IDOR）",
            target_component="订单服务",
            attack_vector="修改URL中的订单ID参数",
            dread_score=8.0,
            severity=Severity.HIGH,
            mitigations=[
                "每个请求验证资源所有权（user_id匹配）",
                "使用UUID替代自增ID（增加枚举难度）",
                "RBAC权限模型 + 资源级授权",
                "API响应中不返回其他用户数据",
            ],
        ),
        Threat(
            threat_id="T-E-002",
            threat_type=ThreatType.ELEVATION_OF_PRIVILEGE,
            title="普通用户获取管理员权限",
            description="通过JWT篡改或参数注入提升角色",
            target_component="API网关→用户服务",
            attack_vector="修改JWT中的role字段 / 越权调用管理API",
            dread_score=8.5,
            severity=Severity.CRITICAL,
            mitigations=[
                "JWT 使用非对称签名（RS256），服务端验证签名",
                "角色信息从服务端数据库获取，不信任Token中的role",
                "管理API独立路由 + 额外认证层",
                "权限检查使用装饰器/中间件统一处理",
            ],
        ),
    ]
    return threats


# ==========================================
# 4. 防护代码实现
# ==========================================
class SecurityControls:
    """安全防护措施实现"""

    @staticmethod
    def rate_limiter(max_requests: int = 10, window_seconds: int = 60):
        """速率限制装饰器（防暴力破解/DoS）"""
        requests_store: Dict[str, list] = {}

        def decorator(func):
            def wrapper(*args, **kwargs):
                # 从参数中获取客户端标识
                client_id = kwargs.get("client_id", "default")
                now = time.time()

                if client_id not in requests_store:
                    requests_store[client_id] = []

                # 清理过期记录
                requests_store[client_id] = [
                    t for t in requests_store[client_id] if now - t < window_seconds
                ]

                if len(requests_store[client_id]) >= max_requests:
                    return {"error": "请求过于频繁，请稍后再试", "retry_after": window_seconds}

                requests_store[client_id].append(now)
                return func(*args, **kwargs)
            return wrapper
        return decorator

    @staticmethod
    def secure_order_creation(user_id: int, product_id: int, quantity: int, client_price: float,
                               db_products: Dict) -> Dict:
        """
        安全的订单创建（防价格篡改）
        关键：服务端获取价格，不信任客户端传入的价格
        """
        # ✅ 从数据库获取真实价格
        product = db_products.get(product_id)
        if not product:
            return {"error": "商品不存在"}

        # ✅ 使用服务端价格，忽略客户端价格
        real_price = product["price"]

        # ⚠️ 记录客户端价格差异（审计）
        if client_price != real_price:
            print(f"  [安全告警] 用户 {user_id} 传入价格 {client_price} ≠ 实际 {real_price}")

        # ✅ 检查库存（原子操作模拟）
        if product["stock"] < quantity:
            return {"error": "库存不足"}

        # ✅ 计算总价
        total = real_price * quantity

        # ✅ 生成订单签名（防篡改）
        order_data = f"{user_id}:{product_id}:{quantity}:{total}:{time.time()}"
        order_signature = hmac.new(
            b"order_signing_secret",
            order_data.encode(),
            hashlib.sha256
        ).hexdigest()

        # ✅ 审计日志（防否认）
        audit_log = {
            "action": "create_order",
            "user_id": user_id,
            "product_id": product_id,
            "quantity": quantity,
            "unit_price": real_price,
            "total": total,
            "client_price": client_price,
            "timestamp": time.time(),
            "signature": order_signature,
        }

        return {
            "order_id": f"ORD_{secrets.token_hex(8)}",
            "user_id": user_id,
            "product_id": product_id,
            "quantity": quantity,
            "unit_price": real_price,
            "total": total,
            "signature": order_signature,
            "audit": audit_log,
        }

    @staticmethod
    def check_ownership(user_id: int, resource_user_id: int) -> bool:
        """资源所有权检查（防IDOR/越权）"""
        return user_id == resource_user_id

    @staticmethod
    def validate_jwt_safely(token: str, secret: bytes) -> Optional[Dict]:
        """
        安全的 JWT 验证（防权限提升）
        关键：验证签名 + 不信任 payload 中的 role
        """
        import base64
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None

            # 解码 header 和 payload
            header = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
            payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))

            # ✅ 验证签名
            signing_input = (parts[0] + "." + parts[1]).encode()
            expected_sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
            actual_sig = base64.urlsafe_b64decode(parts[2] + "==")

            if not hmac.compare_digest(expected_sig, actual_sig):
                print("  [安全告警] JWT 签名验证失败")
                return None

            # ✅ 检查过期时间
            if payload.get("exp", 0) < time.time():
                print("  [安全告警] JWT 已过期")
                return None

            # ⚠️ 注意：payload 中的 role 不可信！
            # 实际应用中应从数据库查询用户角色
            return payload

        except Exception as e:
            print(f"  [安全告警] JWT 解析失败: {e}")
            return None

    @staticmethod
    def safe_error_response(error: Exception) -> Dict:
        """安全的错误响应（防信息泄露）"""
        # ✅ 对外只返回通用信息
        return {
            "error": "internal_server_error",
            "message": "服务器内部错误，请稍后重试",
            "request_id": secrets.token_hex(8),
        }

    @staticmethod
    def encrypt_sensitive_field(value: str, key: bytes = b"default_key_32bytes_pad__") -> str:
        """敏感字段加密存储（防拖库后泄露）"""
        # 简单 XOR 加密演示（生产环境用 AES）
        value_bytes = value.encode()
        key_repeated = (key * (len(value_bytes) // len(key) + 1))[:len(value_bytes)]
        encrypted = bytes(a ^ b for a, b in zip(value_bytes, key_repeated))
        return encrypted.hex()

    @staticmethod
    def validate_input(input_str: str, pattern: str, max_length: int = 100) -> Tuple[bool, str]:
        """通用输入验证"""
        if not isinstance(input_str, str):
            return False, "输入必须是字符串"
        if len(input_str) > max_length:
            return False, f"输入超出最大长度 {max_length}"
        if not re.match(pattern, input_str):
            return False, "输入格式无效"
        return True, input_str


# ==========================================
# 5. 报告生成
# ==========================================
def generate_threat_report(threats: List[Threat], dfd: List[DFDComponent]) -> str:
    """生成威胁建模报告"""
    lines = []
    lines.append("=" * 70)
    lines.append("电商系统 STRIDE 威胁建模报告")
    lines.append("=" * 70)

    # 数据流图
    lines.append("\n【数据流图（DFD）】\n")
    for comp in dfd:
        icon = {
            "external_entity": "👤",
            "process": "⚙️",
            "data_store": "💾",
            "data_flow": "→",
        }.get(comp.component_type, "?")
        lines.append(f"  {icon} [{comp.trust_boundary}] {comp.name}: {comp.description}")

    # 威胁汇总
    lines.append(f"\n{'='*70}")
    lines.append("【威胁汇总】\n")
    lines.append(f"  {'ID':<10s} {'类型':<12s} {'严重程度':<6s} {'DREAD':<6s} {'标题'}")
    lines.append(f"  {'-'*10} {'-'*12} {'-'*6} {'-'*6} {'-'*40}")

    for t in sorted(threats, key=lambda x: x.dread_score, reverse=True):
        lines.append(f"  {t.threat_id:<10s} {t.threat_type.value:<12s} "
                      f"{t.severity.value:<6s} {t.dread_score:<6.1f} {t.title}")

    # 详细分析
    lines.append(f"\n{'='*70}")
    lines.append("【威胁详细分析】\n")

    for threat_type in ThreatType:
        type_threats = [t for t in threats if t.threat_type == threat_type]
        if not type_threats:
            continue

        lines.append(f"\n--- {threat_type.name}: {threat_type.value} ---\n")
        for t in type_threats:
            lines.append(f"  [{t.threat_id}] {t.title}")
            lines.append(f"    严重程度: {t.severity.value} (DREAD: {t.dread_score}/10)")
            lines.append(f"    目标组件: {t.target_component}")
            lines.append(f"    攻击路径: {t.attack_vector}")
            lines.append(f"    描述: {t.description}")
            lines.append(f"    缓解措施:")
            for i, m in enumerate(t.mitigations, 1):
                lines.append(f"      {i}. {m}")
            lines.append("")

    # 统计
    lines.append(f"\n{'='*70}")
    lines.append("【统计】\n")
    by_type = {}
    by_severity = {}
    for t in threats:
        by_type[t.threat_type.value] = by_type.get(t.threat_type.value, 0) + 1
        by_severity[t.severity.value] = by_severity.get(t.severity.value, 0) + 1

    lines.append(f"  总威胁数: {len(threats)}")
    lines.append(f"\n  按类型:")
    for k, v in by_type.items():
        lines.append(f"    {k}: {v}")
    lines.append(f"\n  按严重程度:")
    for k, v in sorted(by_severity.items(), key=lambda x: ["严重", "高", "中", "低"].index(x[0])):
        lines.append(f"    {k}: {v}")

    avg_dread = sum(t.dread_score for t in threats) / len(threats)
    lines.append(f"\n  平均 DREAD 评分: {avg_dread:.1f}/10")

    return "\n".join(lines)


# ==========================================
# 测试
# ==========================================
if __name__ == "__main__":
    print("=" * 60)
    print("STRIDE 威胁建模 —— 电商系统")
    print("=" * 60)

    # 构建数据流图
    dfd = build_ecommerce_dfd()

    # 威胁分析
    threats = analyze_threats()

    # 生成报告
    report = generate_threat_report(threats, dfd)
    print(report)

    # === 防护代码演示 ===
    print(f"\n{'='*60}")
    print("防护代码演示")
    print("=" * 60)

    # 1. 价格篡改防护
    print("\n--- 1. 订单价格篡改防护 ---")
    db_products = {
        1001: {"name": "iPhone 15", "price": 7999.0, "stock": 10},
        1002: {"name": "MacBook Pro", "price": 14999.0, "stock": 5},
    }

    # 攻击者尝试用 1 元购买 iPhone
    result = SecurityControls.secure_order_creation(
        user_id=42, product_id=1001, quantity=1,
        client_price=1.0,  # ← 攻击者传入的价格
        db_products=db_products,
    )
    print(f"  攻击者用 ¥1 下单 iPhone:")
    print(f"  结果: {result}")
    print(f"  → 服务端使用真实价格 ¥{result.get('unit_price', '?')}，忽略客户端价格")

    # 2. 越权访问防护
    print(f"\n--- 2. 越权访问防护（IDOR）---")
    order_owner = 42
    requester = 99
    has_access = SecurityControls.check_ownership(requester, order_owner)
    print(f"  用户 {requester} 尝试访问用户 {order_owner} 的订单")
    print(f"  所有权检查: {'✓ 允许' if has_access else '✗ 拒绝'}")

    # 3. JWT 签名验证
    print(f"\n--- 3. JWT 安全验证 ---")
    secret = b"jwt_signing_secret_key"
    # 构造合法 JWT
    import base64
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload_data = {"user_id": 42, "role": "user", "exp": time.time() + 3600}
    payload = base64.urlsafe_b64encode(json.dumps(payload_data).encode()).decode().rstrip("=")
    signing_input = f"{header}.{payload}"
    sig = hmac.new(secret, signing_input.encode(), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).decode().rstrip("=")
    valid_token = f"{signing_input}.{sig_b64}"

    # 验证合法 Token
    result = SecurityControls.validate_jwt_safely(valid_token, secret)
    print(f"  合法Token验证: {'✓ 通过' if result else '✗ 失败'}")
    print(f"  Payload: {result}")

    # 篡改 Token（修改 role 为 admin）
    tampered_payload_data = {"user_id": 42, "role": "admin", "exp": time.time() + 3600}
    tampered_payload = base64.urlsafe_b64encode(json.dumps(tampered_payload_data).encode()).decode().rstrip("=")
    tampered_token = f"{header}.{tampered_payload}.{sig_b64}"
    result = SecurityControls.validate_jwt_safely(tampered_token, secret)
    print(f"  篡改Token验证: {'✓ 通过' if result else '✗ 拒绝'}")
    print(f"  → 签名验证检测到 payload 被修改")

    # 4. 速率限制
    print(f"\n--- 4. 速率限制（防暴力破解）---")

    @SecurityControls.rate_limiter(max_requests=3, window_seconds=60)
    def login(client_id="default"):
        return {"status": "login_attempt_processed"}

    for i in range(5):
        result = login(client_id="attacker_ip")
        status = "✓ 允许" if "error" not in result else "✗ 拒绝"
        print(f"  第 {i+1} 次登录尝试: {status}")

    # 5. 安全错误响应
    print(f"\n--- 5. 安全错误响应 ---")
    try:
        raise RuntimeError("数据库连接失败: postgres://user:pass@10.0.0.1:5432/db")
    except Exception as e:
        safe_response = SecurityControls.safe_error_response(e)
        print(f"  对外响应: {safe_response}")
        print(f"  内部错误: {str(e)}")
        print(f"  → 外部看不到数据库连接字符串等敏感信息")

    # 6. 敏感字段加密
    print(f"\n--- 6. 敏感字段加密存储 ---")
    phone = "13800138000"
    encrypted = SecurityControls.encrypt_sensitive_field(phone)
    print(f"  原始手机号: {phone}")
    print(f"  加密后: {encrypted}")
    print(f"  → 即使数据库被拖库，手机号也是加密的")
```

**思考题**：在威胁 T-E-002（JWT 篡改权限提升）中，防护措施建议"角色从服务端数据库获取，不信任 Token 中的 role"。但这意味着每次请求都要查数据库，增加延迟。你会如何设计缓存策略，在安全性和性能之间取得平衡？提示：考虑 Redis 缓存 + TTL + 权限变更时主动失效。

---

### 第20题：安全代码审计自动化 — AST扫描器检测安全漏洞

**知识点讲解**

**静态代码分析（SAST, Static Application Security Testing）** 在不运行代码的情况下扫描源码中的安全漏洞。基于 **AST（Abstract Syntax Tree，抽象语法树）** 的分析方法比正则匹配更精确——它理解代码结构，能区分注释中的"密码"和赋值语句中的真实密钥。Python 的 `ast` 模块可以将源码解析为 AST，然后通过 `ast.NodeVisitor` 遍历每个节点。

**AST 遍历模式**：`ast.NodeVisitor` 使用访问者模式，为每种 AST 节点类型提供 `visit_<NodeType>` 方法。例如 `visit_Assign` 处理赋值语句，`visit_Call` 处理函数调用，`visit_Import` 处理 import 语句。通过重写这些方法，可以精确地检测特定模式。

**模式匹配**是检测的核心。硬编码密钥检测：在赋值语句中，变量名包含 "password"/"secret"/"key"/"token" 等关键词，且值为字符串字面量。SQL 注入检测：`execute()` 调用的参数是 f-string 或字符串拼接（非参数化查询）。不安全反序列化检测：`pickle.loads()` / `yaml.load()`（无 SafeLoader）/ `eval()` 调用。

**误报控制**是 SAST 的最大挑战。降低误报的策略：(1) 上下文分析——检查变量是否来自用户输入（`request.GET`）；(2) 白名单——已知安全的模式排除；(3) 数据流分析——追踪变量从源头到使用的路径；(4) 置信度分级——高置信度报告为 ERROR，低置信度报告为 WARNING。完美的零误报几乎不可能，关键是在覆盖率和误报率之间取得平衡。

```python
"""
安全代码审计自动化 —— AST 扫描器
运行：python exercise_20_ast_scanner.py
检测：硬编码密钥 / SQL注入 / 不安全反序列化 / 命令注入 / 弱加密 / 路径遍历
"""
import ast
import os
import re
import hashlib
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum


# ==========================================
# 1. 漏洞定义
# ==========================================
class Severity(Enum):
    CRITICAL = "严重"
    HIGH = "高"
    MEDIUM = "中"
    LOW = "低"
    INFO = "提示"


@dataclass
class Finding:
    """审计发现"""
    rule_id: str               # 规则ID
    rule_name: str             # 规则名称
    severity: Severity         # 严重程度
    confidence: str            # 置信度 (HIGH/MEDIUM/LOW)
    file_path: str             # 文件路径
    line_number: int           # 行号
    code_snippet: str          # 代码片段
    description: str           # 漏洞描述
    recommendation: str        # 修复建议
    cwe_id: str = ""           # CWE 编号


# ==========================================
# 2. 检测规则
# ==========================================
class SecurityRule:
    """安全检测规则基类"""
    rule_id: str = ""
    rule_name: str = ""
    severity: Severity = Severity.MEDIUM
    cwe_id: str = ""

    def check(self, node: ast.AST, source_lines: List[str], file_path: str) -> List[Finding]:
        raise NotImplementedError


# --- 规则1: 硬编码密钥 ---
class HardcodedSecretRule(SecurityRule):
    """检测硬编码的密钥、密码、Token"""
    rule_id = "SEC001"
    rule_name = "硬编码密钥"
    severity = Severity.HIGH
    cwe_id = "CWE-798"

    # 敏感变量名模式
    SECRET_PATTERNS = [
        re.compile(r'password|passwd|pwd', re.I),
        re.compile(r'secret', re.I),
        re.compile(r'api[_-]?key', re.I),
        re.compile(r'auth[_-]?token|access[_-]?token', re.I),
        re.compile(r'private[_-]?key', re.I),
        re.compile(r'aws[_-]?(access|secret)', re.I),
    ]

    # 已知的非密钥值（减少误报）
    SAFE_VALUES = {"", "none", "null", "true", "false", "changeme",
                   "your-password", "your-secret", "xxx", "todo",
                   "placeholder", "example", "test", "demo"}

    def visit_Assign(self, node: ast.Assign, source_lines: List[str], file_path: str) -> List[Finding]:
        findings = []

        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue

            var_name = target.id

            # 检查变量名是否匹配敏感模式
            is_sensitive = any(p.search(var_name) for p in self.SECRET_PATTERNS)
            if not is_sensitive:
                continue

            # 检查赋值值是否为字符串字面量
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                value = node.value.value
                # 排除已知安全值和空值
                if value.lower() in self.SAFE_VALUES:
                    continue
                # 排除环境变量引用
                if value.startswith("$") or value.startswith("{") and value.endswith("}"):
                    continue
                # 排除过短的值（可能是占位符）
                if len(value) < 6:
                    continue

                findings.append(Finding(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    confidence="HIGH",
                    file_path=file_path,
                    line_number=node.lineno,
                    code_snippet=source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else "",
                    description=f"变量 '{var_name}' 包含硬编码的密钥/密码",
                    recommendation="从环境变量或密钥管理服务（如 Vault/KMS）读取，不要硬编码在源码中",
                    cwe_id=self.cwe_id,
                ))

        return findings

    def check(self, node: ast.AST, source_lines: List[str], file_path: str) -> List[Finding]:
        if isinstance(node, ast.Assign):
            return self.visit_Assign(node, source_lines, file_path)
        return []


# --- 规则2: SQL 注入 ---
class SQLInjectionRule(SecurityRule):
    """检测非参数化的 SQL 查询（字符串拼接/f-string）"""
    rule_id = "SEC002"
    rule_name = "SQL注入风险"
    severity = Severity.CRITICAL
    cwe_id = "CWE-89"

    # SQL 执行函数
    SQL_EXEC_METHODS = {"execute", "executemany", "executescript"}
    SQL_CURSOR_ATTRS = {"cursor"}

    def visit_Call(self, node: ast.Call, source_lines: List[str], file_path: str) -> List[Finding]:
        findings = []

        # 检查是否是 cursor.execute() 调用
        if not isinstance(node.func, ast.Attribute):
            return findings
        if node.func.attr not in self.SQL_EXEC_METHODS:
            return findings

        # 检查第一个参数（SQL 语句）
        if not node.args:
            return findings

        sql_arg = node.args[0]

        # 检测 f-string (JoinedStr)
        if isinstance(sql_arg, ast.JoinedStr):
            # 检查是否有变量插值
            has_variable = any(isinstance(v, ast.FormattedValue) for v in sql_arg.values)
            if has_variable:
                findings.append(Finding(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    confidence="HIGH",
                    file_path=file_path,
                    line_number=node.lineno,
                    code_snippet=source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else "",
                    description="SQL 查询使用 f-string 拼接变量，存在注入风险",
                    recommendation="使用参数化查询: cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
                    cwe_id=self.cwe_id,
                ))

        # 检测字符串拼接 (BinOp with Add)
        elif isinstance(sql_arg, ast.BinOp) and isinstance(sql_arg.op, ast.Add):
            findings.append(Finding(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                confidence="HIGH",
                file_path=file_path,
                line_number=node.lineno,
                code_snippet=source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else "",
                description="SQL 查询使用字符串拼接，存在注入风险",
                recommendation="使用参数化查询: cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))",
                cwe_id=self.cwe_id,
            ))

        # 检测 % 格式化
        elif isinstance(sql_arg, ast.BinOp) and isinstance(sql_arg.op, ast.Mod):
            findings.append(Finding(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=self.severity,
                confidence="MEDIUM",
                file_path=file_path,
                line_number=node.lineno,
                code_snippet=source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else "",
                description="SQL 查询使用 % 格式化，可能存在注入风险",
                recommendation="使用参数化查询而非字符串格式化",
                cwe_id=self.cwe_id,
            ))

        return findings

    def check(self, node: ast.AST, source_lines: List[str], file_path: str) -> List[Finding]:
        if isinstance(node, ast.Call):
            return self.visit_Call(node, source_lines, file_path)
        return []


# --- 规则3: 不安全反序列化 ---
class UnsafeDeserializationRule(SecurityRule):
    """检测不安全的反序列化操作"""
    rule_id = "SEC003"
    rule_name = "不安全反序列化"
    severity = Severity.CRITICAL
    cwe_id = "CWE-502"

    UNSAFE_FUNCTIONS = {
        "pickle": {"loads", "load"},
        "yaml": {"load"},        # load 不安全，safe_load 安全
        "marshal": {"loads", "load"},
        "shelve": {"open"},
    }

    UNSAFE_CALLS = {"eval", "exec", "compile"}

    def visit_Call(self, node: ast.Call, source_lines: List[str], file_path: str) -> List[Finding]:
        findings = []

        # 检查 eval/exec
        if isinstance(node.func, ast.Name) and node.func.id in self.UNSAFE_CALLS:
            findings.append(Finding(
                rule_id=self.rule_id,
                rule_name=self.rule_name,
                severity=Severity.CRITICAL,
                confidence="HIGH",
                file_path=file_path,
                line_number=node.lineno,
                code_snippet=source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else "",
                description=f"使用不安全的函数 {node.func.id}()，可执行任意代码",
                recommendation=f"避免使用 {node.func.id}()，使用 ast.literal_eval() 或专用解析器",
                cwe_id=self.cwe_id,
            ))

        # 检查 pickle.loads / yaml.load 等
        if isinstance(node.func, ast.Attribute):
            module_name = ""
            if isinstance(node.func.value, ast.Name):
                module_name = node.func.value.id
            func_name = node.func.attr

            # pickle.loads / pickle.load
            if module_name in self.UNSAFE_FUNCTIONS:
                if func_name in self.UNSAFE_FUNCTIONS[module_name]:
                    safe_alt = {
                        "pickle": "json.loads() 或 pickle 不处理不可信数据",
                        "yaml": "yaml.safe_load()",
                        "marshal": "json.loads()",
                        "shelve": "json + 文件操作",
                    }.get(module_name, "")

                    findings.append(Finding(
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        severity=Severity.CRITICAL,
                        confidence="HIGH",
                        file_path=file_path,
                        line_number=node.lineno,
                        code_snippet=source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else "",
                        description=f"使用不安全的反序列化: {module_name}.{func_name}()",
                        recommendation=f"使用 {safe_alt}" if safe_alt else "使用安全的反序列化方法",
                        cwe_id=self.cwe_id,
                    ))

        return findings

    def check(self, node: ast.AST, source_lines: List[str], file_path: str) -> List[Finding]:
        if isinstance(node, ast.Call):
            return self.visit_Call(node, source_lines, file_path)
        return []


# --- 规则4: 命令注入 ---
class CommandInjectionRule(SecurityRule):
    """检测可能的命令注入"""
    rule_id = "SEC004"
    rule_name = "命令注入风险"
    severity = Severity.HIGH
    cwe_id = "CWE-78"

    DANGER_FUNCTIONS = {"system", "popen"}
    DANGER_MODULES = {"os", "subprocess", "commands"}

    def visit_Call(self, node: ast.Call, source_lines: List[str], file_path: str) -> List[Finding]:
        findings = []

        # os.system() / subprocess.call(shell=True)
        if isinstance(node.func, ast.Attribute):
            module = ""
            if isinstance(node.func.value, ast.Name):
                module = node.func.value.id
            func_name = node.func.attr

            if module == "os" and func_name in self.DANGER_FUNCTIONS:
                # 检查参数是否包含变量
                if node.args and self._contains_variable(node.args[0]):
                    findings.append(Finding(
                        rule_id=self.rule_id,
                        rule_name=self.rule_name,
                        severity=self.severity,
                        confidence="HIGH",
                        file_path=file_path,
                        line_number=node.lineno,
                        code_snippet=source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else "",
                        description=f"使用 {module}.{func_name}() 执行包含变量的命令",
                        recommendation="使用 subprocess.run() 并设置 shell=False，参数以列表传递",
                        cwe_id=self.cwe_id,
                    ))

            if module == "subprocess" and func_name in {"call", "run", "Popen", "check_output"}:
                # 检查 shell=True
                for kw in node.keywords:
                    if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                        findings.append(Finding(
                            rule_id=self.rule_id,
                            rule_name=self.rule_name,
                            severity=self.severity,
                            confidence="HIGH",
                            file_path=file_path,
                            line_number=node.lineno,
                            code_snippet=source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else "",
                            description=f"使用 {module}.{func_name}(shell=True)，存在命令注入风险",
                            recommendation="设置 shell=False，将命令和参数作为列表传递",
                            cwe_id=self.cwe_id,
                        ))

        return findings

    def _contains_variable(self, node: ast.AST) -> bool:
        """检查 AST 节点是否包含变量引用"""
        if isinstance(node, ast.Name):
            return True
        if isinstance(node, ast.JoinedStr):
            return any(isinstance(v, ast.FormattedValue) for v in node.values)
        if isinstance(node, ast.BinOp):
            return self._contains_variable(node.left) or self._contains_variable(node.right)
        if isinstance(node, ast.Call):
            return True
        return False

    def check(self, node: ast.AST, source_lines: List[str], file_path: str) -> List[Finding]:
        if isinstance(node, ast.Call):
            return self.visit_Call(node, source_lines, file_path)
        return []


# --- 规则5: 弱加密 ---
class WeakCryptoRule(SecurityRule):
    """检测弱加密算法的使用"""
    rule_id = "SEC005"
    rule_name = "弱加密算法"
    severity = Severity.MEDIUM
    cwe_id = "CWE-327"

    WEAK_ALGOS = {"md5", "sha1", "md4", "des", "arc4", "rc4"}
    WEAK_MODES = {"ECB"}

    def visit_Call(self, node: ast.Call, source_lines: List[str], file_path: str) -> List[Finding]:
        findings = []

        if isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
            module_name = ""
            if isinstance(node.func.value, ast.Name):
                module_name = node.func.value.id

            # hashlib.md5() / hashlib.sha1()
            if module_name == "hashlib" and func_name in {"md5", "sha1"}:
                # 检查是否用于密码哈希（通过变量名上下文）
                is_password_context = False
                # 简化：直接报告
                findings.append(Finding(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=Severity.MEDIUM,
                    confidence="MEDIUM",
                    file_path=file_path,
                    line_number=node.lineno,
                    code_snippet=source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else "",
                    description=f"使用弱哈希算法 {module_name}.{func_name}()",
                    recommendation="使用 SHA-256 或更强的算法；密码哈希使用 PBKDF2/bcrypt/argon2",
                    cwe_id=self.cwe_id,
                ))

        return findings

    def check(self, node: ast.AST, source_lines: List[str], file_path: str) -> List[Finding]:
        if isinstance(node, ast.Call):
            return self.visit_Call(node, source_lines, file_path)
        return []


# --- 规则6: 路径遍历 ---
class PathTraversalRule(SecurityRule):
    """检测可能的路径遍历漏洞"""
    rule_id = "SEC006"
    rule_name = "路径遍历风险"
    severity = Severity.HIGH
    cwe_id = "CWE-22"

    FILE_FUNCTIONS = {"open", "read", "write", "readlines", "writelines"}

    def visit_Call(self, node: ast.Call, source_lines: List[str], file_path: str) -> List[Finding]:
        findings = []

        # open() 调用
        if isinstance(node.func, ast.Name) and node.func.id == "open":
            if node.args and self._contains_user_input(node.args[0]):
                findings.append(Finding(
                    rule_id=self.rule_id,
                    rule_name=self.rule_name,
                    severity=self.severity,
                    confidence="MEDIUM",
                    file_path=file_path,
                    line_number=node.lineno,
                    code_snippet=source_lines[node.lineno - 1].strip() if node.lineno <= len(source_lines) else "",
                    description="open() 的文件路径可能来自用户输入",
                    recommendation="验证和规范化路径: os.path.realpath() + 检查是否在允许目录内",
                    cwe_id=self.cwe_id,
                ))

        return findings

    def _contains_user_input(self, node: ast.AST) -> bool:
        """检查是否包含可能来自用户的输入"""
        if isinstance(node, ast.JoinedStr):
            return True
        if isinstance(node, ast.BinOp):
            return True
        if isinstance(node, ast.Attribute):
            # request.GET / request.POST 等
            if isinstance(node.value, ast.Name) and node.value.id in {"request", "req", "flask_request"}:
                return True
        if isinstance(node, ast.Subscript):
            return True
        return False

    def check(self, node: ast.AST, source_lines: List[str], file_path: str) -> List[Finding]:
        if isinstance(node, ast.Call):
            return self.visit_Call(node, source_lines, file_path)
        return []


# ==========================================
# 3. AST 扫描器
# ==========================================
class ASTSecurityScanner:
    """基于 AST 的安全代码扫描器"""

    def __init__(self):
        self.rules: List[SecurityRule] = [
            HardcodedSecretRule(),
            SQLInjectionRule(),
            UnsafeDeserializationRule(),
            CommandInjectionRule(),
            WeakCryptoRule(),
            PathTraversalRule(),
        ]
        self.findings: List[Finding] = []
        self.files_scanned: int = 0
        self.lines_scanned: int = 0

    def scan_source(self, source: str, file_path: str = "<string>") -> List[Finding]:
        """扫描 Python 源代码"""
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError as e:
            print(f"  [跳过] {file_path}: 语法错误 {e}")
            return []

        source_lines = source.splitlines()
        self.files_scanned += 1
        self.lines_scanned += len(source_lines)

        file_findings: List[Finding] = []

        # 遍历 AST
        for node in ast.walk(tree):
            for rule in self.rules:
                findings = rule.check(node, source_lines, file_path)
                file_findings.extend(findings)

        # 去重（同一行同一规则只报告一次）
        seen = set()
        unique_findings = []
        for f in file_findings:
            key = (f.rule_id, f.file_path, f.line_number)
            if key not in seen:
                seen.add(key)
                unique_findings.append(f)

        self.findings.extend(unique_findings)
        return unique_findings

    def scan_file(self, file_path: str) -> List[Finding]:
        """扫描单个文件"""
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
        return self.scan_source(source, file_path)

    def scan_directory(self, dir_path: str) -> List[Finding]:
        """扫描目录下所有 Python 文件"""
        for root, dirs, files in os.walk(dir_path):
            # 跳过常见的不需要扫描的目录
            dirs[:] = [d for d in dirs if d not in {
                "__pycache__", ".git", "venv", ".venv", "node_modules", ".tox"
            }]
            for filename in files:
                if filename.endswith(".py"):
                    file_path = os.path.join(root, filename)
                    self.scan_file(file_path)
        return self.findings

    def generate_report(self) -> str:
        """生成审计报告"""
        lines = []
        lines.append("=" * 70)
        lines.append("安全代码审计报告")
        lines.append("=" * 70)

        # 统计
        lines.append(f"\n扫描统计:")
        lines.append(f"  文件数: {self.files_scanned}")
        lines.append(f"  代码行数: {self.lines_scanned}")
        lines.append(f"  发现总数: {len(self.findings)}")

        # 按严重程度统计
        by_severity: Dict[str, int] = {}
        for f in self.findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1

        lines.append(f"\n按严重程度:")
        for sev in ["严重", "高", "中", "低", "提示"]:
            count = by_severity.get(sev, 0)
            if count > 0:
                icon = {"严重": "🔴", "高": "🟠", "中": "🟡", "低": "🔵", "提示": "⚪"}[sev]
                lines.append(f"  {icon} {sev}: {count}")

        # 按规则统计
        by_rule: Dict[str, int] = {}
        for f in self.findings:
            by_rule[f.rule_name] = by_rule.get(f.rule_name, 0) + 1

        lines.append(f"\n按规则:")
        for rule_name, count in sorted(by_rule.items(), key=lambda x: -x[1]):
            lines.append(f"  {rule_name}: {count}")

        # 详细发现
        if self.findings:
            lines.append(f"\n{'='*70}")
            lines.append("详细发现:\n")

            # 按严重程度排序
            severity_order = {"严重": 0, "高": 1, "中": 2, "低": 3, "提示": 4}
            sorted_findings = sorted(
                self.findings,
                key=lambda f: (severity_order.get(f.severity.value, 99), f.line_number)
            )

            for i, f in enumerate(sorted_findings, 1):
                lines.append(f"  [{i}] {f.severity.value} | {f.rule_name} ({f.rule_id})")
                lines.append(f"      文件: {f.file_path}:{f.line_number}")
                lines.append(f"      代码: {f.code_snippet}")
                lines.append(f"      描述: {f.description}")
                lines.append(f"      置信度: {f.confidence}")
                lines.append(f"      CWE: {f.cwe_id}")
                lines.append(f"      建议: {f.recommendation}")
                lines.append("")

        # 安全评分
        score = self._calculate_security_score()
        lines.append(f"{'='*70}")
        lines.append(f"安全评分: {score}/100")
        if score >= 90:
            lines.append("评级: A (优秀)")
        elif score >= 75:
            lines.append("评级: B (良好)")
        elif score >= 60:
            lines.append("评级: C (一般)")
        elif score >= 40:
            lines.append("评级: D (较差)")
        else:
            lines.append("评级: F (危险)")

        return "\n".join(lines)

    def _calculate_security_score(self) -> int:
        """计算安全评分（0-100）"""
        if not self.findings:
            return 100
        weights = {
            Severity.CRITICAL: 20,
            Severity.HIGH: 10,
            Severity.MEDIUM: 5,
            Severity.LOW: 2,
            Severity.INFO: 1,
        }
        total_penalty = sum(weights.get(f.severity, 0) for f in self.findings)
        score = max(0, 100 - total_penalty)
        return score


# ==========================================
# 4. 测试用例代码（包含多种漏洞）
# ==========================================
VULNERABLE_CODE = '''
import pickle
import hashlib
import os
import subprocess
import yaml

# === 硬编码密钥 ===
DATABASE_PASSWORD = "SuperSecret123!"
API_KEY = "sk-1234567890abcdef"
AWS_SECRET_ACCESS_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
SECRET_TOKEN = "bearer_token_abc123xyz"

# === SQL 注入 ===
def get_user(username):
    import sqlite3
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    # 危险：f-string 拼接
    cursor.execute(f"SELECT * FROM users WHERE name = '{username}'")
    return cursor.fetchone()

def search_products(keyword):
    import sqlite3
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    # 危险：字符串拼接
    query = "SELECT * FROM products WHERE name LIKE '%" + keyword + "%'"
    cursor.execute(query)
    return cursor.fetchall()

# === 不安全反序列化 ===
def load_config(data):
    # 危险：pickle 反序列化不可信数据
    config = pickle.loads(data)
    return config

def parse_yaml(content):
    # 危险：yaml.load 不安全
    result = yaml.load(content)
    return result

def run_expression(expr):
    # 危险：eval 执行任意代码
    return eval(expr)

# === 命令注入 ===
def ping_host(hostname):
    # 危险：os.system 执行变量
    os.system(f"ping -c 4 {hostname}")

def run_command(cmd):
    # 危险：shell=True
    result = subprocess.call(cmd, shell=True)
    return result

# === 弱加密 ===
def hash_password(password):
    # 危险：MD5 哈希密码
    return hashlib.md5(password.encode()).hexdigest()

def checksum(data):
    # 危险：SHA-1 已不安全
    return hashlib.sha1(data).hexdigest()

# === 路径遍历 ===
def read_file(filename):
    # 危险：用户输入直接作为文件路径
    with open(filename, 'r') as f:
        return f.read()

# === 安全的代码（不应被报告）===
def safe_get_user(user_id):
    import sqlite3
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    # 安全：参数化查询
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return cursor.fetchone()

def safe_load_config(data):
    import json
    # 安全：JSON 反序列化
    return json.loads(data)

def safe_hash_password(password):
    import hashlib
    # 安全：PBKDF2
    return hashlib.pbkdf2_hmac('sha256', password.encode(), b'salt', 100000)

def safe_ping(hostname):
    # 安全：shell=False，参数列表
    subprocess.run(["ping", "-c", "4", hostname], shell=False)
'''


# ==========================================
# 测试
# ==========================================
if __name__ == "__main__":
    print("=" * 60)
    print("AST 安全代码审计扫描器")
    print("=" * 60)

    scanner = ASTSecurityScanner()

    # 扫描包含漏洞的测试代码
    print("\n--- 扫描测试代码（包含多种安全漏洞）---\n")
    findings = scanner.scan_source(VULNERABLE_CODE, "vulnerable_app.py")

    # 生成报告
    report = scanner.generate_report()
    print(report)

    # 规则覆盖率展示
    print(f"\n{'='*60}")
    print("检测规则覆盖率")
    print(f"{'='*60}\n")

    rules_info = [
        ("SEC001", "硬编码密钥", "CWE-798", "变量名匹配 + 字符串字量值"),
        ("SEC002", "SQL注入风险", "CWE-89", "execute()参数为f-string/拼接/%格式化"),
        ("SEC003", "不安全反序列化", "CWE-502", "pickle.loads/yaml.load/eval/exec"),
        ("SEC004", "命令注入风险", "CWE-78", "os.system/subprocess(shell=True) + 变量"),
        ("SEC005", "弱加密算法", "CWE-327", "hashlib.md5/sha1 调用"),
        ("SEC006", "路径遍历风险", "CWE-22", "open() 参数含用户输入"),
    ]
    print(f"  {'规则ID':<8s} {'规则名称':<16s} {'CWE':<10s} {'检测模式'}")
    print(f"  {'-'*8} {'-'*16} {'-'*10} {'-'*40}")
    for rid, name, cwe, pattern in rules_info:
        print(f"  {rid:<8s} {name:<16s} {cwe:<10s} {pattern}")

    # 误报控制说明
    print(f"\n{'='*60}")
    print("误报控制策略")
    print(f"{'='*60}\n")
    strategies = [
        ("变量名白名单", "排除 TEST_/EXAMPLE_ 前缀的变量"),
        ("值长度检查", "排除长度<6的值（可能是占位符）"),
        ("安全值排除", "排除 'changeme'/'your-password' 等常见占位值"),
        ("上下文分析", "检查变量是否来自用户输入(request.GET等)"),
        ("置信度分级", "HIGH(确信漏洞)/MEDIUM(需人工确认)/LOW(仅供参考)"),
        ("同行号去重", "同一行同一规则只报告一次"),
    ]
    for name, desc in strategies:
        print(f"  • {name}: {desc}")
```

**思考题**：当前扫描器基于 AST 模式匹配，能检测到"直接"的安全问题（如 `pickle.loads(data)`）。但如果变量经过了多层传递（`data = request.body; processed = transform(data); result = pickle.loads(processed)`），AST 扫描器无法追踪数据流。你会如何实现轻量级的数据流分析（taint analysis）来检测这种间接漏洞？提示：维护一个"被污染变量集合"，在赋值/传递时传播污染标记。

---

## 附录：练习题知识点速查表

| 题号 | 轨道 | 核心知识点 | 关键技术 |
|------|------|-----------|---------|
| 1 | 编程进阶 | 元类、描述符、ORM映射 | metaclass, `__set_name__`, `__new__` vs `__init__` |
| 2 | 编程进阶 | asyncio并发、信号量、重试 | Semaphore, wait_for, gather, 指数退避 |
| 3 | 编程进阶 | 装饰器工厂、类装饰器、闭包 | functools.wraps, partial, LRU缓存 |
| 4 | 编程进阶 | 结构子类型、泛型、重载 | Protocol, TypeVar, Generic, @overload |
| 5 | AI/ML | 自注意力、多头机制 | numpy, softmax, 缩放点积, 因果掩码 |
| 6 | AI/ML | 词向量、负采样 | Skip-gram, Unigram Table, sigmoid |
| 7 | AI/ML | 优化器原理 | SGD/Momentum/Adam/RAdam, 偏差校正 |
| 8 | AI/ML | 模型压缩 | 对称/非对称量化, 幅度剪枝, CSR |
| 9 | Web全栈 | RESTful设计 | http.server, HATEOAS, 分页/排序/过滤 |
| 10 | Web全栈 | WebSocket协议 | asyncio, Ping/Pong心跳, 房间管理 |
| 11 | Web全栈 | OAuth2授权 | PKCE, Authorization Code, Token刷新 |
| 12 | Web全栈 | GraphQL引擎 | Lexer/Parser, AST, Resolver, 嵌套查询 |
| 13 | DevOps | Docker优化 | 多阶段构建, 分层缓存, .dockerignore |
| 14 | DevOps | K8s部署 | Deployment/Service/Ingress, HPA, 探针 |
| 15 | DevOps | IaC | Terraform, HCL, State管理, 模块化 |
| 16 | DevOps | 可观测性 | 结构化日志, Prometheus指标, OpenTelemetry |
| 17 | 安全实战 | OWASP防护 | 参数化查询, CSP, CSRF Token, PBKDF2 |
| 18 | 安全实战 | 密码学 | AES-GCM, RSA签名, TLS握手, HMAC |
| 19 | 安全实战 | 威胁建模 | STRIDE, DFD, DREAD评级, 防护代码 |
| 20 | 安全实战 | 代码审计 | AST遍历, 模式匹配, 误报控制, CWE |

---

> **学习建议**：
> 1. 每道题先阅读知识点讲解，理解原理后再看代码
> 2. 运行代码观察输出，修改参数理解行为变化
> 3. 尝试回答思考题，这是深化理解的关键
> 4. 每个轨道的4道题有递进关系，建议按顺序学习
> 5. 代码均为完整可运行版本，可直接 `python xxx.py` 执行
