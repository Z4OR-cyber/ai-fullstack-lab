# 代码 Cookbook — 从496题练习中提炼的可复用代码模式

> 本文档从 AI 全栈学习的 496 道编程练习中，提炼出最实用的可复用代码模式和技巧。
> 每个模式均附有精简代码示例，可直接复制使用。

---

## 一、Python 核心模式

### 1.1 线程安全单例模式（双重检查锁）

**用途**：确保全局唯一实例，适用于数据库连接池、配置管理器
**场景**：多线程环境下需要共享单一资源时

```python
import threading

class DBConnectionPool:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:               # 第一次检查（无锁，快速路径）
            with cls._lock:                      # 加锁
                if cls._instance is None:        # 第二次检查（防止重复创建）
                    cls._instance = super().__new__(cls)
                    cls._instance._pool = []
                    cls._instance._max_size = 5
        return cls._instance

    def get_connection(self):
        if self._pool:
            return self._pool.pop()
        return f"DBConn-{id(self)}"

    def release_connection(self, conn):
        if len(self._pool) < self._max_size:
            self._pool.append(conn)
```

**要点**：双重检查避免每次获取实例都加锁；`__new__` 中初始化属性需注意只执行一次
**来源**：`python_exercises/24_design_patterns.py` Q1

---

### 1.2 建造者模式（链式调用构建复杂对象）

**用途**：分步构建复杂配置对象，避免构造函数参数爆炸
**场景**：LLM 请求构建、API 客户端配置、查询构建器

```python
class LLMRequest:
    def __init__(self):
        self.model = ""
        self.messages = []
        self.temperature = 0.7
        self.max_tokens = 1024
        self.stream = False

class LLMRequestBuilder:
    def __init__(self):
        self._req = LLMRequest()

    def set_model(self, model):
        self._req.model = model
        return self                      # 返回 self 实现链式调用

    def add_message(self, role, content):
        self._req.messages.append({"role": role, "content": content})
        return self

    def set_temperature(self, temp):
        self._req.temperature = temp
        return self

    def build(self):
        if not self._req.model:
            raise ValueError("model is required")
        return self._req

# 使用
req = (LLMRequestBuilder()
       .set_model("gpt-4")
       .add_message("system", "You are helpful")
       .add_message("user", "Hello")
       .set_temperature(0.3)
       .build())
```

**要点**：每个 setter 返回 self；build() 中做参数校验
**来源**：`python_exercises/24_design_patterns.py` Q1

---

### 1.3 装饰器模式（LLM 服务功能叠加）

**用途**：动态给对象添加日志、缓存、限流等功能，无需修改原始类
**场景**：API 调用链增强、中间件叠加

```python
from abc import ABC, abstractmethod

class LLMService(ABC):
    @abstractmethod
    def call(self, prompt: str) -> str: ...

class BaseLLMService(LLMService):
    def call(self, prompt): return f"LLM response: {prompt}"

class LLMDecorator(LLMService):
    def __init__(self, wrapped: LLMService):
        self._wrapped = wrapped
    def call(self, prompt): return self._wrapped.call(prompt)

class CachingDecorator(LLMDecorator):
    def __init__(self, wrapped):
        super().__init__(wrapped)
        self._cache = {}
    def call(self, prompt):
        if prompt in self._cache:
            return f"[CACHED] {self._cache[prompt]}"
        result = self._wrapped.call(prompt)
        self._cache[prompt] = result
        return result

class LoggingDecorator(LLMDecorator):
    def call(self, prompt):
        result = self._wrapped.call(prompt)
        return f"[LOGGED] {result}"

# 链式组合：缓存 → 日志 → 基础服务
service = CachingDecorator(LoggingDecorator(BaseLLMService()))
```

**要点**：装饰器基类持有被装饰对象的引用；可任意组合叠加顺序
**来源**：`python_exercises/24_design_patterns.py` Q2

---

### 1.4 观察者模式（事件总线）

**用途**：实现发布-订阅解耦，组件间通过事件通信
**场景**：用户注册后触发邮件、分析、清理等多个副作用

```python
from typing import Callable, Any

class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = {}

    def subscribe(self, event_type: str, handler: Callable):
        self._subscribers.setdefault(event_type, []).append(handler)

    def publish(self, event_type: str, data: Any):
        for handler in self._subscribers.get(event_type, []):
            handler(data)

# 使用
bus = EventBus()
bus.subscribe("user.created", lambda d: print(f"发邮件给 {d['email']}"))
bus.subscribe("user.created", lambda d: print(f"记录分析: {d['user_id']}"))
bus.subscribe("user.deleted", lambda d: print(f"清理数据: {d['user_id']}"))

bus.publish("user.created", {"user_id": 1, "email": "test@test.com"})
bus.publish("user.deleted", {"user_id": 1})
```

**要点**：发布者无需知道订阅者是谁；支持同一事件多个处理器
**来源**：`python_exercises/24_design_patterns.py` Q3

---

### 1.5 异步并发爬虫模板（Semaphore 限流 + 重试）

**用途**：高并发 IO 密集型任务，控制并发数防止过载
**场景**：批量 API 调用、网页爬取、文件下载

```python
import asyncio
import random

async def fetch_with_retry(url, semaphore, max_retries=3, timeout=2):
    """带指数退避重试 + 并发限制的异步请求"""
    for attempt in range(1, max_retries + 1):
        async with semaphore:                        # 令牌机制限制并发
            try:
                await asyncio.wait_for(
                    asyncio.sleep(random.uniform(0.3, 1.0)),  # 替换为实际请求
                    timeout=timeout
                )
                return {"url": url, "status": 200, "attempt": attempt}
            except asyncio.TimeoutError:
                if attempt == max_retries:
                    return {"url": url, "status": 408, "error": "超时"}
                backoff = 0.5 * (2 ** (attempt - 1))  # 指数退避: 0.5, 1.0, 2.0
                await asyncio.sleep(backoff)

async def crawl_all(urls, max_concurrency=5):
    semaphore = asyncio.Semaphore(max_concurrency)
    results = await asyncio.gather(
        *[fetch_with_retry(url, semaphore) for url in urls]
    )
    return results

# asyncio.run(crawl_all(["url1", "url2", "url3"]))
```

**要点**：Semaphore 控制最大并发数；指数退避避免雪崩；gather 并发执行所有任务
**来源**：`python_exercises/02_async_basics.py` + `02_async_extensions.py`

---

### 1.6 异步上下文管理器（资源生命周期管理）

**用途**：自动管理异步资源的初始化和清理
**场景**：爬虫会话、数据库连接、文件写入

```python
import asyncio
import time

class AsyncCrawlerSession:
    def __init__(self, name, max_concurrency=5):
        self.name = name
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.stats = {"total": 0, "success": 0, "failed": 0}
        self._start_time = None

    async def __aenter__(self):
        self._start_time = time.time()
        print(f"🚀 [{self.name}] 启动")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self._start_time
        print(f"📊 [{self.name}] 完成: 成功{self.stats['success']}, "
              f"失败{self.stats['failed']}, 耗时{elapsed:.2f}s")
        return False  # 不吞掉异常

    async def fetch(self, url):
        async with self.semaphore:
            self.stats["total"] += 1
            try:
                await asyncio.sleep(0.5)
                self.stats["success"] += 1
                return {"url": url, "status": 200}
            except Exception as e:
                self.stats["failed"] += 1
                return {"url": url, "status": 503, "error": str(e)}

# 使用
async def main():
    async with AsyncCrawlerSession("爬虫", max_concurrency=4) as crawler:
        results = await asyncio.gather(
            *[crawler.fetch(f"http://example.com/{i}") for i in range(10)]
        )
```

**要点**：`__aenter__`/`__aexit__` 是异步版本；退出时自动统计和清理
**来源**：`python_exercises/02_async_extensions.py` 扩展5

---

### 1.7 Pandas 数据清洗模板

**用途**：处理脏数据的标准流程
**场景**：ETL 数据预处理、数据质量修复

```python
import pandas as pd
import numpy as np

def clean_dirty_data(df):
    # 1. 字符串去空格
    for col in df.select_dtypes(include='object').columns:
        df[col] = df[col].str.strip()

    # 2. 删除完全重复行
    df = df.drop_duplicates()

    # 3. 数值列转换 + 异常值处理
    df['年龄'] = pd.to_numeric(df['年龄'], errors='coerce')
    df.loc[(df['年龄'] < 0) | (df['年龄'] > 150), '年龄'] = np.nan
    df['年龄'] = df['年龄'].fillna(df['年龄'].median())

    # 4. 字符串数值列统一转换
    df['薪资'] = pd.to_numeric(df['薪资'], errors='coerce')
    df['薪资'] = df['薪资'].fillna(df['薪资'].median())

    # 5. 正则验证（手机号/邮箱）
    df['手机号有效'] = df['手机号'].str.match(r'^1\d{10}$', na=False)
    df['邮箱有效'] = df['邮箱'].str.match(r'^[^@]+@[^@]+\.[^@]+$', na=False)

    return df
```

**要点**：`errors='coerce'` 将无法解析的值转为 NaN；`str.match` 支持正则验证
**来源**：`python_exercises/05_pandas_basics.py` 扩展3

---

### 1.8 Matplotlib 数据看板模板

**用途**：一图多面板展示多维数据
**场景**：运营周报、数据监控大屏

```python
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd

def create_dashboard(df, output_path='dashboard.png'):
    fig = plt.figure(figsize=(16, 10))

    # 左上：趋势折线 + 滚动均值
    ax1 = fig.add_subplot(2, 3, 1)
    df['MA7'] = df['value'].rolling(7).mean()
    ax1.plot(df['date'], df['value'], alpha=0.3, color='blue', label='日数据')
    ax1.plot(df['date'], df['MA7'], color='red', linewidth=2, label='7日均值')
    ax1.set_title('趋势'); ax1.legend(fontsize=8)

    # 中上：饼图（分类占比）
    ax2 = fig.add_subplot(2, 3, 2)
    counts = df['category'].value_counts()
    ax2.pie(counts, labels=counts.index, autopct='%1.1f%%', startangle=90)
    ax2.set_title('分类分布')

    # 右上：直方图 + 均值线
    ax3 = fig.add_subplot(2, 3, 3)
    ax3.hist(df['value'], bins=30, color='green', alpha=0.7, edgecolor='black')
    ax3.axvline(df['value'].mean(), color='red', linestyle='--', label=f'均值: {df["value"].mean():.0f}')
    ax3.set_title('分布'); ax3.legend(fontsize=8)

    # 左下：月度柱状图
    ax4 = fig.add_subplot(2, 3, 4)
    monthly = df.set_index('date')['value'].resample('ME').sum()
    ax4.bar(range(len(monthly)), monthly.values, color='orange', alpha=0.8)
    ax4.set_title('月度汇总')

    # 中下：热力图
    ax5 = fig.add_subplot(2, 3, 5)
    pivot = df.pivot_table(values='value', index='category', columns='month', aggfunc='sum')
    sns.heatmap(pivot, cmap='YlOrRd', ax=ax5, fmt='.0f')
    ax5.set_title('热力图')

    # 右下：关键指标文本
    ax6 = fig.add_subplot(2, 3, 6)
    ax6.axis('off')
    metrics = [f"总量: {df['value'].sum():,.0f}", f"均值: {df['value'].mean():.0f}"]
    for i, m in enumerate(metrics):
        ax6.text(0.1, 0.8 - i*0.15, m, fontsize=12, transform=ax6.transAxes,
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.5))

    plt.suptitle('数据看板', fontsize=16, y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=100, bbox_inches='tight')
    plt.close()
```

**要点**：`fig.add_subplot(行, 列, 位置)` 灵活布局；`bbox_inches='tight'` 防止标签截断
**来源**：`python_exercises/06_matplotlib_basics.py` 扩展5

---

### 1.9 责任链模式（请求处理管道）

**用途**：将请求沿处理链传递，每个处理器决定是否放行
**场景**：API 请求认证→限流→日志的管道处理

```python
from abc import ABC, abstractmethod
from typing import Optional

class Handler(ABC):
    def __init__(self):
        self._next: Optional[Handler] = None

    def set_next(self, handler):
        self._next = handler
        return handler  # 返回下一个handler，支持链式调用

    @abstractmethod
    def handle(self, request: dict) -> str: ...

class AuthHandler(Handler):
    def handle(self, request):
        if not request.get("token"):
            return "❌ 认证失败"
        if self._next:
            return self._next.handle(request)
        return "✅ 通过"

class RateLimitHandler(Handler):
    def __init__(self):
        super().__init__()
        self._count = 0
    def handle(self, request):
        self._count += 1
        if self._count > 3:
            return "❌ 限流"
        if self._next:
            return self._next.handle(request)
        return "✅ 通过"

# 组装链：认证 → 限流
auth = AuthHandler()
rate = RateLimitHandler()
auth.set_next(rate)

print(auth.handle({"token": "abc"}))      # ✅ 通过
print(auth.handle({}))                      # ❌ 认证失败
```

**要点**：`set_next` 返回下一个 handler 实现链式组装；每个 handler 可短路返回
**来源**：`python_exercises/24_design_patterns.py` Q3

---

## 二、AI/ML 实战模式

### 2.1 纯 NumPy 实现线性回归（梯度下降）

**用途**：从零理解梯度下降原理，不依赖 sklearn
**场景**：学习ML原理、自定义优化器实验

```python
import numpy as np

# 生成数据: y = 3x + 2 + noise
np.random.seed(42)
X = np.random.uniform(0, 10, 100)
y = 3 * X + 2 + np.random.normal(0, 1, 100)

# 添加偏置项
X_b = np.column_stack([np.ones(len(X)), X])  # shape: (100, 2)

# 梯度下降
w = np.zeros(2)
lr = 0.01
for epoch in range(1000):
    predictions = X_b @ w
    errors = predictions - y
    gradient = X_b.T @ errors / len(y)      # ∇J = (1/n)·Xᵀ(Xw - y)
    w -= lr * gradient

print(f"斜率: {w[1]:.2f} (真实3.0), 截距: {w[0]:.2f} (真实2.0)")
```

**要点**：添加偏置列 `np.ones`；梯度公式 `Xᵀ(Xw-y)/n`；学习率需调参
**来源**：`ai_math/29_ml_model_math.py` 第1题

---

### 2.2 纯 NumPy 实现逻辑回归（数值稳定 sigmoid）

**用途**：二分类模型从零实现
**场景**：理解分类原理、自定义损失函数

```python
import numpy as np

def sigmoid(z):
    """数值稳定的sigmoid：避免大数溢出"""
    return np.where(z >= 0, 1/(1+np.exp(-z)), np.exp(z)/(1+np.exp(z)))

# 生成二分类数据
np.random.seed(42)
n = 100
X = np.vstack([np.random.randn(n//2, 2) + [2, 2],
               np.random.randn(n//2, 2) + [-2, -2]])
y = np.array([1]*(n//2) + [0]*(n//2))
X_b = np.column_stack([np.ones(n), X])

# 梯度下降训练
w = np.zeros(3)
lr = 0.1
for _ in range(1000):
    p = sigmoid(X_b @ w)
    w -= lr * X_b.T @ (p - y) / n           # 梯度: (1/n)·Xᵀ(σ(Xw) - y)

acc = np.mean((sigmoid(X_b @ w) > 0.5) == y)
print(f"准确率: {acc:.2%}, 权重: {w.round(3)}")
```

**要点**：`np.where` 分段计算避免 `exp` 溢出；梯度与线性回归形式相同
**来源**：`ai_math/29_ml_model_math.py` 第2题

---

### 2.3 纯 NumPy 实现 MLP 前向传播 + 反向传播

**用途**：从零理解神经网络训练过程
**场景**：学习深度学习原理、调试自定义网络结构

```python
import numpy as np

def sigmoid(x):
    return 1 / (1 + np.exp(-np.clip(x, -250, 250)))

def sigmoid_deriv(x):
    s = sigmoid(x)
    return s * (1 - s)

# XOR 问题
X = np.array([[0,0], [0,1], [1,0], [1,1]])
y = np.array([[0], [1], [1], [0]])

# 网络: 2 → 4 → 1
np.random.seed(42)
W1 = np.random.randn(2, 4) * 0.5
b1 = np.zeros((1, 4))
W2 = np.random.randn(4, 1) * 0.5
b2 = np.zeros((1, 1))

for epoch in range(2000):
    # 前向传播
    z1 = X @ W1 + b1
    a1 = sigmoid(z1)
    z2 = a1 @ W2 + b2
    a2 = sigmoid(z2)

    # 反向传播
    dz2 = (a2 - y) * sigmoid_deriv(z2)       # 输出层梯度
    dW2 = a1.T @ dz2
    db2 = np.sum(dz2, axis=0, keepdims=True)

    dz1 = dz2 @ W2.T * sigmoid_deriv(z1)     # 隐藏层梯度（链式法则）
    dW1 = X.T @ dz1
    db1 = np.sum(dz1, axis=0, keepdims=True)

    # 参数更新
    W2 -= 1.0 * dW2; b2 -= 1.0 * db2
    W1 -= 1.0 * dW1; b1 -= 1.0 * db1

print(f"XOR预测: {a2.ravel()}")  # ≈ [0, 1, 1, 0]
```

**要点**：`np.clip` 防止 sigmoid 溢出；反向传播核心是链式法则 `dz1 = dz2 @ W2.T * σ'(z1)`
**来源**：`python_exercises/10_dl_basics.py` 练习1

---

### 2.4 TF-IDF 向量化 + 余弦相似度检索

**用途**：不依赖外部库实现文本向量化与语义搜索
**场景**：RAG 系统的基础检索、文档相似度计算

```python
import numpy as np
from collections import Counter

def build_tfidf(documents):
    """构建 TF-IDF 矩阵"""
    # 词汇表
    vocab = sorted(set(w for doc in documents for w in doc.lower().split()))
    vocab_idx = {w: i for i, w in enumerate(vocab)}

    # IDF
    N = len(documents)
    df = np.zeros(len(vocab))
    for doc in documents:
        for w in set(doc.lower().split()):
            if w in vocab_idx:
                df[vocab_idx[w]] += 1
    idf = np.log(N / (1 + df))

    # TF-IDF 矩阵
    matrix = np.zeros((N, len(vocab)))
    for i, doc in enumerate(documents):
        tokens = doc.lower().split()
        counter = Counter(tokens)
        total = len(tokens)
        for w, c in counter.items():
            if w in vocab_idx:
                matrix[i, vocab_idx[w]] = (c / total) * idf[vocab_idx[w]]
        norm = np.linalg.norm(matrix[i])
        if norm > 0:
            matrix[i] /= norm           # L2 归一化，点积即余弦相似度
    return matrix, vocab_idx, idf

def search(query, matrix, vocab_idx, idf, top_k=3):
    """余弦相似度检索"""
    q_vec = np.zeros(len(vocab_idx))
    tokens = query.lower().split()
    counter = Counter(tokens)
    for w, c in counter.items():
        if w in vocab_idx:
            q_vec[vocab_idx[w]] = (c / len(tokens)) * idf[vocab_idx[w]]
    norm = np.linalg.norm(q_vec)
    if norm > 0:
        q_vec /= norm

    scores = matrix @ q_vec             # 已归一化，点积=余弦相似度
    ranked = np.argsort(scores)[::-1][:top_k]
    return [(i, scores[i]) for i in ranked]
```

**要点**：L2 归一化后点积等价于余弦相似度；IDF 公式 `log(N/(1+df))` 加1平滑
**来源**：`python_exercises/27_rag_system.py` 第1题

---

### 2.5 BM25 关键词检索（纯 Python 实现）

**用途**：经典关键词检索算法，RAG 混合检索的核心组件
**场景**：精确关键词匹配、专有名词检索

```python
import math
import numpy as np
from collections import Counter, defaultdict

class BM25:
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1      # 词频饱和参数
        self.b = b         # 文档长度归一化参数
        self.doc_freqs = []
        self.idf = {}
        self.avgdl = 0
        self.doc_len = []
        self.N = 0

    def fit(self, documents):
        self.N = len(documents)
        self.doc_len = [len(doc.split()) for doc in documents]
        self.avgdl = np.mean(self.doc_len) if self.doc_len else 0

        df = defaultdict(int)
        self.doc_freqs = []
        for doc in documents:
            freq = Counter(doc.split())
            self.doc_freqs.append(freq)
            for word in freq:
                df[word] += 1

        for word, freq in df.items():
            self.idf[word] = math.log((self.N - freq + 0.5) / (freq + 0.5) + 1)

    def search(self, query, k=5):
        query_tokens = query.split()
        scores = np.zeros(self.N)
        for i in range(self.N):
            score = 0.0
            dl = self.doc_len[i]
            for token in query_tokens:
                if token in self.idf:
                    tf = self.doc_freqs[i].get(token, 0)
                    if tf > 0:
                        idf = self.idf[token]
                        num = tf * (self.k1 + 1)
                        den = tf + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                        score += idf * num / den
            scores[i] = score
        ranked = np.argsort(scores)[::-1][:k]
        return [(int(i), float(scores[i])) for i in ranked]
```

**要点**：k1 控制词频饱和（通常1.2-2.0）；b 控制文档长度影响（通常0.75）；IDF 加1平滑
**来源**：`python_exercises/27_rag_system.py` 第7题

---

### 2.6 混合检索 + RRF 融合（RAG 核心）

**用途**：结合向量检索（语义）和 BM25（关键词）的优势
**场景**：RAG 系统检索阶段，提升召回质量

```python
from collections import defaultdict

def hybrid_search_rrf(vector_results, bm25_results, alpha=0.5, k=5):
    """
    RRF (Reciprocal Rank Fusion) 混合检索
    不需要分数归一化，对不同尺度的分数更鲁棒
    """
    scores = defaultdict(float)

    # 向量检索贡献: 1/(rank+1)
    for rank, (idx, _) in enumerate(vector_results):
        scores[idx] += alpha * (1.0 / (rank + 1))

    # BM25 贡献: 1/(rank+1)
    for rank, (idx, _) in enumerate(bm25_results):
        scores[idx] += (1 - alpha) * (1.0 / (rank + 1))

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]
    return [(idx, score) for idx, score in ranked]

def simple_reranker(query, documents, top_indices, top_k=3):
    """基于 Jaccard 相似度的简化重排序"""
    query_words = set(query.lower().split())
    reranked = []
    for idx in top_indices:
        doc_words = set(documents[idx].lower().split())
        overlap = len(query_words & doc_words)
        jaccard = overlap / len(query_words | doc_words) if query_words | doc_words else 0
        reranked.append((idx, jaccard))
    reranked.sort(key=lambda x: x[1], reverse=True)
    return reranked[:top_k]
```

**要点**：RRF 用 `1/(rank+1)` 融合不同检索器的排名，无需分数归一化；alpha 控制两路权重
**来源**：`python_exercises/27_rag_system.py` 第7题

---

### 2.7 交叉验证 + 模型评估模板

**用途**：标准化模型评估流程
**场景**：模型选型、超参数调优后验证

```python
from sklearn.model_selection import cross_val_score, train_test_split, GridSearchCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, precision_score, recall_score,
                             f1_score, confusion_matrix, roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

def evaluate_model(X, y, model=None, cv=5):
    if model is None:
        model = RandomForestClassifier(n_estimators=100, random_state=42)

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

    # Pipeline: 标准化 + 模型
    pipe = Pipeline([('scaler', StandardScaler()), ('model', model)])
    pipe.fit(X_train, y_train)
    y_pred = pipe.predict(X_test)
    y_proba = pipe.predict_proba(X_test)[:, 1] if hasattr(pipe, 'predict_proba') else None

    # 分类指标
    metrics = {
        'accuracy': accuracy_score(y_test, y_pred),
        'precision': precision_score(y_test, y_pred, average='weighted'),
        'recall': recall_score(y_test, y_pred, average='weighted'),
        'f1': f1_score(y_test, y_pred, average='weighted'),
    }
    if y_proba is not None:
        metrics['roc_auc'] = roc_auc_score(y_test, y_proba)

    # 交叉验证
    cv_scores = cross_val_score(pipe, X, y, cv=cv)
    metrics['cv_mean'] = cv_scores.mean()
    metrics['cv_std'] = cv_scores.std()

    # 混淆矩阵
    metrics['confusion_matrix'] = confusion_matrix(y_test, y_pred)

    return metrics
```

**要点**：Pipeline 确保 StandardScaler 在交叉验证中正确使用（不会数据泄露）；`average='weighted'` 处理多分类
**来源**：`python_exercises/09_ml_basics.py` 练习2-3

---

### 2.8 NumPy 向量化 KNN（广播实现）

**用途**：无需循环计算距离矩阵
**场景**：小规模分类、相似度计算

```python
import numpy as np

def knn_predict(X_train, y_train, X_test, k=3):
    """利用广播机制一次性计算所有距离"""
    # X_test: (m, d), X_train: (n, d) → distances: (m, n)
    diff = X_test[:, np.newaxis, :] - X_train[np.newaxis, :, :]
    distances = np.sqrt((diff ** 2).sum(axis=2))

    # 找最近的 k 个邻居
    nearest = np.argsort(distances, axis=1)[:, :k]

    # 投票
    predictions = []
    for i in range(len(X_test)):
        labels = y_train[nearest[i]]
        pred = np.bincount(labels).argmax()
        predictions.append(pred)
    return np.array(predictions)
```

**要点**：`X_test[:, np.newaxis, :] - X_train[np.newaxis, :, :]` 广播生成 (m,n,d) 差值矩阵；大数组需注意内存
**来源**：`python_exercises/04_numpy_basics.py` 扩展5

---

## 三、安全攻防模式

### 3.1 SQL 注入攻击原理与防御

**用途**：理解注入本质，掌握参数化查询防御
**场景**：任何拼接 SQL 的场景

```python
# ❌ 漏洞代码：字符串拼接 SQL
def unsafe_query(username, password):
    sql = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    # 输入 ' OR 1=1 -- 会绕过认证
    return execute(sql)

# ✅ 防御：参数化查询（预编译 + 绑定）
class ParameterizedQuery:
    def prepare(self, template):
        """预编译 SQL 模板，占位符 ? 不会被解析为 SQL"""
        self.template = template
        self.params = []

    def bind(self, value):
        """绑定参数：值被当作纯数据，不会被解释为 SQL 代码"""
        self.params.append(value)

    def execute(self):
        # 数据库引擎将参数作为数据处理，不做 SQL 解析
        # ' OR 1=1 -- 被当作纯字符串 → 认证失败
        return self.template, self.params

# 使用
pq = ParameterizedQuery()
pq.prepare("SELECT * FROM users WHERE username=? AND password=?")
pq.bind("admin")
pq.bind("' OR 1=1 --")  # 被当作普通字符串
```

**要点**：参数化查询将数据与代码完全隔离；预编译后占位符位置固定，无法注入
**来源**：`python_exercises/23_security_attack.py` Q1 + `26_security_defense.py` Q1

---

### 3.2 XSS 攻击与输出编码防御

**用途**：防止用户输入被当作 HTML/JS 执行
**场景**：任何将用户输入渲染到网页的场景

```python
import urllib.parse

class OutputEncoder:
    """四种上下文的输出编码器"""

    @staticmethod
    def html_encode(s):
        """HTML 上下文编码：防止 <script> 标签执行"""
        replacements = {'&': '&amp;', '<': '&lt;', '>': '&gt;',
                        '"': '&quot;', "'": '&#x27;'}
        for char, enc in replacements.items():
            s = s.replace(char, enc)
        return s

    @staticmethod
    def js_encode(s):
        """JavaScript 上下文编码：防止引号逃逸"""
        result = []
        for ch in s:
            code = ord(ch)
            if code < 0x20 or code in (0x22, 0x27, 0x5c, 0x2f, 0x3c, 0x3e):
                result.append(f'\\u{code:04x}')
            else:
                result.append(ch)
        return ''.join(result)

    @staticmethod
    def url_encode(s):
        """URL 上下文编码"""
        return urllib.parse.quote(s, safe='')

    @staticmethod
    def encode(context, s):
        encoders = {'html': OutputEncoder.html_encode,
                    'js': OutputEncoder.js_encode,
                    'url': OutputEncoder.url_encode}
        return encoders.get(context, lambda x: x)(s)

# <script>alert('XSS')</script> → &lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;
```

**要点**：不同上下文需要不同编码；HTML 编码是最常用的防 XSS 手段
**来源**：`python_exercises/26_security_defense.py` Q1

---

### 3.3 WAF 规则引擎 + CSP 策略

**用途**：输入层拦截恶意 payload + 浏览器层限制脚本执行
**场景**：Web 应用安全防护纵深防御

```python
import re
import secrets

class WAFRuleEngine:
    """WAF 规则引擎：正则匹配 + 拦截"""
    RULES = [
        ("SQL注入-UNION",   re.compile(r"union\s+select", re.I), "block"),
        ("SQL注入-OR条件",  re.compile(r"'\s*or\s*'?\d*'?\s*=\s*'?\d*", re.I), "block"),
        ("SQL注入-注释",    re.compile(r"--|/\*|\*/|#"), "block"),
        ("命令注入",        re.compile(r"[|;&`$]|\$\(|\|\||&&"), "block"),
        ("XSS-脚本",        re.compile(r"<script[^>]*>", re.I), "block"),
        ("XSS-事件",        re.compile(r"on\w+\s*=", re.I), "block"),
        ("SSTI-模板",       re.compile(r"\{\{.*\}\}|\{%.*%\}"), "block"),
        ("路径遍历",        re.compile(r"\.\./|\.\.\\", re.I), "block"),
    ]

    @classmethod
    def inspect(cls, payload):
        hits = []
        for name, pattern, action in cls.RULES:
            if pattern.search(payload):
                hits.append({'rule': name, 'action': action})
        return hits

    @classmethod
    def block_or_pass(cls, payload):
        hits = cls.inspect(payload)
        return (False, hits) if hits else (True, [])

class CSPPolicyGenerator:
    """CSP 策略生成器：nonce-based CSP"""
    def __init__(self):
        self.directives = {
            'default-src': ["'self'"],
            'script-src': ["'self'", "'nonce-{nonce}'"],
            'style-src': ["'self'", "'unsafe-inline'"],
            'img-src': ["'self'", 'data:'],
            'object-src': ["'none'"],
            'frame-ancestors': ["'none'"],
        }

    def generate(self, nonce=None):
        n = nonce or secrets.token_hex(8)
        parts = []
        for directive, sources in self.directives.items():
            parts.append(f"{directive} {' '.join(sources).format(nonce=n)}")
        return '; '.join(parts), n
```

**要点**：WAF 是第一道防线（拦截恶意输入）；CSP 是最后一道防线（浏览器限制执行）；nonce-based CSP 比纯白名单更灵活
**来源**：`python_exercises/26_security_defense.py` Q1

---

### 3.4 命令注入与安全执行

**用途**：安全执行系统命令，防止用户输入注入 shell
**场景**：运维工具、CI/CD 脚本中执行外部命令

```python
import subprocess
import re

# ❌ 漏洞代码：shell=True 拼接命令
# subprocess.call(f"ping {user_input}", shell=True)
# 输入 "127.0.0.1; cat /etc/passwd" 会执行额外命令

# ✅ 防御1：参数列表 + shell=False
def safe_ping(ip):
    if not re.match(r'^[\d.]+$', ip):      # 输入校验：只允许数字和点
        raise ValueError(f"Invalid IP: {ip}")
    result = subprocess.run(
        ['ping', '-c', '4', ip],            # 参数列表，不经过 shell
        capture_output=True, text=True, timeout=10
    )
    return result.stdout

# ✅ 防御2：白名单校验
ALLOWED_ACTIONS = {'start', 'stop', 'status'}
def safe_action(action):
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Action not allowed: {action}")
    subprocess.run(['systemctl', action, 'myapp'], check=True)
```

**要点**：`shell=False` + 参数列表是最根本的防御；输入校验是额外保障
**来源**：`python_exercises/23_security_attack.py` Q1 + `26_security_defense.py` Q1

---

### 3.5 路径遍历防御

**用途**：防止 `../` 突破目录限制读取敏感文件
**场景**：文件上传/下载、模板渲染

```python
import os

def safe_file_path(base_dir, filename):
    """安全的文件路径拼接：防止路径遍历"""
    # 1. 规范化路径
    full_path = os.path.join(base_dir, filename)
    real_path = os.path.realpath(full_path)    # 解析所有 ../ 和符号链接

    # 2. 验证路径仍在 base_dir 下
    if not real_path.startswith(os.path.realpath(base_dir)):
        raise ValueError(f"路径遍历攻击: {filename}")

    return real_path

# safe_file_path("/var/www/uploads", "report.pdf")           → 正常
# safe_file_path("/var/www/uploads", "../../../etc/passwd")  → 抛异常
```

**要点**：`os.path.realpath` 解析所有 `../`；必须与 `base_dir` 的 `realpath` 比较
**来源**：`python_exercises/23_security_attack.py` Q3

---

## 四、工程化模式

### 4.1 Docker 多阶段构建模板

**用途**：构建最小化生产镜像，分离构建环境和运行环境
**场景**：Python Web 应用容器化部署

```dockerfile
# ---------- Stage 1: Builder ----------
FROM python:3.13-slim AS builder

WORKDIR /build

# 先复制依赖文件（利用层缓存）
COPY requirements.txt .

# 创建虚拟环境并安装依赖
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ---------- Stage 2: Runtime ----------
FROM python:3.13-slim AS runtime

# 环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# 安装运行时依赖（curl 用于健康检查）
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# 从 builder 复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 创建非 root 用户
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app
COPY --chown=appuser:appuser . .
USER appuser

EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**要点**：builder 阶段安装依赖 → runtime 阶段只复制 venv；非 root 用户运行；`requirements.txt` 先于代码复制以利用缓存
**来源**：`devops/Dockerfile`

---

### 4.2 Docker Compose 多服务编排模板

**用途**：一键启动应用 + 数据库 + 缓存
**场景**：本地开发环境、CI 测试环境

```yaml
services:
  app:
    build: .
    ports:
      - "${APP_PORT:-8000}:8000"
    environment:
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks: [app-network]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres-data:/var/lib/postgresql/data
    networks: [app-network]
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis-data:/data
    networks: [app-network]
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      retries: 5

volumes:
  postgres-data:
  redis-data:

networks:
  app-network:
    driver: bridge
```

**要点**：`depends_on.condition: service_healthy` 确保依赖服务就绪后启动；`restart: unless-stopped` 自动恢复
**来源**：`devops/docker-compose.yml`

---

### 4.3 K8s 部署清单模板（含探针 + HPA）

**用途**：生产级 K8s 部署配置
**场景**：应用上 K8s、自动扩缩容

```yaml
---
# Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myapp
  namespace: production
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1           # 滚动更新最多多1个副本
      maxUnavailable: 0     # 更新期间不允许不可用
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
        - name: myapp
          image: myapp:1.0.0
          ports:
            - containerPort: 8000
          envFrom:
            - configMapRef:
                name: myapp-config
            - secretRef:
                name: myapp-secret
          resources:
            requests:       # 调度依据
              cpu: "100m"
              memory: "128Mi"
            limits:         # 硬上限
              cpu: "500m"
              memory: "256Mi"
          readinessProbe:   # 就绪探针：是否可接收流量
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:    # 存活探针：是否需要重启
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 20
          lifecycle:
            preStop:
              exec:
                command: ["sleep", "5"]  # 等待负载均衡器移除

---
# HPA 自动扩缩容
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: myapp-hpa
  namespace: production
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: myapp
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70    # CPU>70% 扩容
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300  # 缩容冷却5分钟
```

**要点**：readinessProbe 控制流量接入；livenessProbe 控制重启；`preStop: sleep 5` 实现优雅终止；HPA 缩容冷却防止抖动
**来源**：`devops/k8s/k8s-deployment.yaml`

---

### 4.4 GitHub Actions CI/CD 流水线模板

**用途**：自动化代码检查、测试、构建
**场景**：Python 项目持续集成

```yaml
name: CI
on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  workflow_dispatch:

# 同分支新推送取消旧运行
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  lint:
    name: 🔍 代码检查
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-lint-${{ hashFiles('**/requirements*.txt') }}
      - run: pip install flake8
      - run: flake8 . --max-line-length=100 --extend-ignore=E203,W503

  test:
    name: 🧪 测试 (Python ${{ matrix.python-version }})
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ matrix.python-version }}-${{ hashFiles('**/requirements*.txt') }}
      - run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-xdist
      - run: pytest -n auto --cov=. --cov-report=xml --cov-report=term-missing
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: test-results-${{ matrix.python-version }}
          path: coverage.xml

  build:
    name: 📦 构建
    runs-on: ubuntu-latest
    needs: [lint, test]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - run: |
          pip install build
          python -m build
      - uses: actions/upload-artifact@v4
        with:
          name: python-package
          path: dist/
```

**要点**：矩阵测试覆盖多 Python 版本；`fail-fast: false` 确保一个版本失败不影响其他；`concurrency` 取消旧运行节省资源
**来源**：`devops/ci.yml`

---

### 4.5 负载均衡三种策略（Python 模拟）

**用途**：理解不同负载均衡算法的适用场景
**场景**：API 网关、微服务路由

```python
import hashlib
import bisect
import threading
from collections import defaultdict

# 1. 轮询（Round Robin）—— 简单均匀分配
class RoundRobinBalancer:
    def __init__(self, servers):
        self.servers = servers
        self._index = 0
        self._lock = threading.Lock()

    def get_server(self):
        with self._lock:
            server = self.servers[self._index % len(self.servers)]
            self._index += 1
            return server

# 2. 最少连接 —— 按实际负载分配
class LeastConnectionsBalancer:
    def __init__(self, servers):
        self.connections = {s: 0 for s in servers}
    def get_server(self):
        return min(self.connections, key=self.connections.get)
    def connect(self, s): self.connections[s] += 1
    def disconnect(self, s): self.connections[s] = max(0, self.connections[s] - 1)

# 3. 一致性哈希 —— 相同 key 固定路由（适合缓存）
class ConsistentHashBalancer:
    def __init__(self, servers, replicas=150):
        self.ring = {}
        self.sorted_keys = []
        for server in servers:
            for i in range(replicas):               # 虚拟节点均衡分布
                key = self._hash(f"{server}:{i}")
                self.ring[key] = server
                bisect.insort(self.sorted_keys, key)

    @staticmethod
    def _hash(s):
        return int(hashlib.md5(s.encode()).hexdigest(), 16)

    def get_server(self, key):
        h = self._hash(key)
        idx = bisect.bisect_right(self.sorted_keys, h)
        if idx >= len(self.sorted_keys):
            idx = 0
        return self.ring[self.sorted_keys[idx]]
```

**要点**：轮询适合无状态服务；最少连接适合长连接；一致性哈希适合缓存场景（节点增减时迁移最少）
**来源**：`python_exercises/25_system_design.py` Q6

---

### 4.6 缓存策略三种模式

**用途**：不同场景选择合适的缓存写入策略
**场景**：高并发读写的缓存架构设计

```python
# 1. Cache Aside（旁路缓存）—— 最常用，读时填充
class CacheAside:
    def __init__(self):
        self.cache = {}
        self.db = {"user:1": "Alice"}
    def get(self, key):
        if key in self.cache:          # 先查缓存
            return self.cache[key]
        val = self.db.get(key)         # 未命中查 DB
        if val is not None:
            self.cache[key] = val      # 回填缓存
        return val
    def set(self, key, val):
        self.db[key] = val             # 先写 DB
        self.cache[key] = val          # 再更新缓存

# 2. Write Through（写穿透）—— 缓存和 DB 同步写
class WriteThrough:
    def __init__(self):
        self.cache = {}
        self.db = {}
    def write(self, key, val):
        self.cache[key] = val          # 同时写
        self.db[key] = val
    def read(self, key):
        return self.cache.get(key)     # 缓存总有最新值

# 3. Write Behind（异步写）—— 先写缓存，异步刷入 DB
class WriteBehind:
    def __init__(self):
        self.cache = {}
        self.db = {}
        self.buffer = []
    def write(self, key, val):
        self.cache[key] = val          # 立即写缓存
        self.buffer.append((key, val)) # 放入缓冲区
    def flush(self):
        for k, v in self.buffer:       # 异步批量写入 DB
            self.db[k] = v
        self.buffer.clear()
```

**要点**：Cache Aside 最通用但有一致性窗口；Write Through 强一致但写入慢；Write Behind 写入快但有数据丢失风险
**来源**：`python_exercises/25_system_design.py` Q6

---

## 五、多语言速查

### 5.1 核心语法对照表

| 特性 | Python | Rust | Go | Java | JavaScript |
|------|--------|------|-----|------|------------|
| **变量声明** | `x = 42` | `let x = 42;` | `var x = 42` / `x := 42` | `int x = 42;` | `let x = 42;` |
| **可变变量** | 默认可变 | 需 `let mut` | `var`（`const` 不可变） | 默认可变 | `let`（`const` 不可变） |
| **函数定义** | `def f(x): return x` | `fn f(x: i32) -> i32 { x }` | `func f(x int) int { return x }` | `int f(int x) { return x; }` | `function f(x) { return x; }` |
| **类/结构体** | `class Foo:` | `struct Foo {}` + `impl` | `type Foo struct {}` | `class Foo {}` | `class Foo {}` (ES6) |
| **错误处理** | `try/except` | `Result<T, E>` + `?` | `if err != nil` | `try/catch` | `try/catch` |
| **空值** | `None` | `Option<T>` | `nil` | `null` | `null` / `undefined` |
| **并发原语** | `asyncio` / `threading` | `thread::spawn` / `async` | `go func()` / `chan` | `Thread` / `CompletableFuture` | `async/await` / `Promise` |
| **泛型** | `T` (类型提示) | `fn f<T>(x: T)` | `func f[T any](x T)` | `<T>` | 无原生泛型 |

### 5.2 Rust — 所有权与借用

**特色模式**：所有权系统是 Rust 的核心，确保内存安全无需 GC

```rust
// 所有权转移
let s1 = String::from("hello");
let s2 = s1;                    // s1 的所有权转移给 s2
// println!("{}", s1);          // 编译错误：s1 已失效

// 借用：不获取所有权
fn borrow(s: &String) {         // & 表示借用（不可变引用）
    println!("{}", s);
}
let s3 = String::from("rust");
borrow(&s3);                    // 借用，s3 仍可用

// 可变借用：同一时间只能有一个
let mut s4 = String::from("hi");
let r = &mut s4;
r.push_str(" there");

// 规则：多个不可变引用 OR 一个可变引用，不可共存
```

**要点**：堆数据赋值=转移，栈数据赋值=复制；`&T` 可多个，`&mut T` 只能一个
**来源**：`lang_exercises/13_rust.rs` 第2题

---

### 5.3 Go — Goroutine + Channel 并发

**特色模式**：CSP 并发模型，通过 Channel 通信而非共享内存

```go
// Goroutine：轻量级线程
go func() {
    fmt.Println("在 goroutine 中运行")
}()

// Channel：协程间通信
ch := make(chan string, 3)      // 带缓冲的 channel

// 生产者
go func() {
    for i := 0; i < 5; i++ {
        ch <- fmt.Sprintf("msg-%d", i)
    }
    close(ch)                   // 关闭 channel
}()

// 消费者
for msg := range ch {           // range 遍历直到 channel 关闭
    fmt.Println("收到:", msg)
}

// select 多路复用
select {
case msg := <-ch:
    fmt.Println("收到:", msg)
case <-time.After(time.Second):
    fmt.Println("超时")
}
```

**要点**：`go func()` 启动协程；`make(chan T, n)` 创建缓冲通道；`close()` 后 `range` 自动退出
**来源**：`lang_exercises/14_go.go`

---

### 5.4 JavaScript — 闭包与模块模式

**特色模式**：IIFE 实现私有变量，闭包保持状态

```javascript
// IIFE 创建模块：私有变量 + 公开接口
const counter = (function () {
    let count = 0;              // 私有变量，外部无法直接访问

    return {
        increment() { return ++count; },
        decrement() { return --count; },
        getCount() { return count; }
    };
})();

counter.increment();            // 1
counter.increment();            // 2
counter.getCount();             // 2

// 闭包陷阱：var vs let
// var：所有回调共享同一个 i（输出 3,3,3）
for (var i = 0; i < 3; i++) {
    setTimeout(() => console.log(i), 100);
}
// let：每次迭代创建新绑定（输出 0,1,2）
for (let i = 0; i < 3; i++) {
    setTimeout(() => console.log(i), 100);
}
```

**要点**：IIFE 是 ES6 模块之前的私有化方案；`let` 解决了 `var` 的闭包陷阱
**来源**：`lang_exercises/17_javascript.js` 第1题

---

### 5.5 Java — 泛型与函数式接口

**特色模式**：泛型约束 + Lambda 函数式编程

```java
// 泛型类
class Box<T> {
    private T value;
    public void set(T v) { this.value = v; }
    public T get() { return this.value; }
}

// 函数式接口 + Lambda
@FunctionalInterface
interface MathOperation {
    int operate(int a, int b);
}

MathOperation add = (a, b) -> a + b;
MathOperation mul = (a, b) -> a * b;
System.out.println(add.operate(3, 4));   // 7

// Stream API
List<String> names = List.of("Alice", "Bob", "Charlie");
names.stream()
     .filter(n -> n.length() > 3)
     .map(String::toUpperCase)
     .forEach(System.out::println);      // ALICE, CHARLIE
```

**要点**：`@FunctionalInterface` 标记单方法接口；Stream API 提供声明式集合操作
**来源**：`lang_exercises/16_java.java` 第1-2题

---

### 5.6 各语言特色模式速览

| 语言 | 特色模式 | 一句话说明 |
|------|---------|-----------|
| **Rust** | 所有权 + 借用检查 | 编译期保证内存安全，无需 GC |
| **Go** | Goroutine + Channel | 用通信代替共享内存的 CSP 模型 |
| **C++** | RAII + 智能指针 | 资源获取即初始化，自动管理生命周期 |
| **Java** | 泛型 + Stream | 强类型约束 + 声明式集合处理 |
| **JavaScript** | 闭包 + 事件循环 | 单线程异步靠事件循环 + 回调队列 |
| **C#** | LINQ + async/await | 语言集成查询 + 异步语法糖 |
| **Ruby** | Block + 元编程 | 万物皆对象，Block 是一等公民 |
| **Swift** | Optional + 协议导向 | `?` 强制处理空值，协议替代继承 |
| **Kotlin** | Null 安全 + 扩展函数 | `?` 类型系统 + 给类添加方法无需继承 |
| **Haskell** | 纯函数 + 类型推导 | 无副作用，类型系统极其强大 |
| **Elixir** | Actor 模型 + 热更新 | Erlang VM 上的高并发容错 |
| **R** | 向量化 + 公式语法 | `y ~ x` 公式接口，统计计算专用 |

---

## 附录：模式索引

| 编号 | 模式名称 | 分类 | 来源文件 |
|------|---------|------|---------|
| 1.1 | 线程安全单例模式 | Python核心 | `24_design_patterns.py` |
| 1.2 | 建造者模式 | Python核心 | `24_design_patterns.py` |
| 1.3 | 装饰器模式 | Python核心 | `24_design_patterns.py` |
| 1.4 | 观察者模式（事件总线） | Python核心 | `24_design_patterns.py` |
| 1.5 | 异步并发爬虫模板 | Python核心 | `02_async_basics.py` |
| 1.6 | 异步上下文管理器 | Python核心 | `02_async_extensions.py` |
| 1.7 | Pandas 数据清洗模板 | Python核心 | `05_pandas_basics.py` |
| 1.8 | Matplotlib 数据看板 | Python核心 | `06_matplotlib_basics.py` |
| 1.9 | 责任链模式 | Python核心 | `24_design_patterns.py` |
| 2.1 | 纯NumPy线性回归 | AI/ML | `ai_math/29_ml_model_math.py` |
| 2.2 | 纯NumPy逻辑回归 | AI/ML | `ai_math/29_ml_model_math.py` |
| 2.3 | MLP前向+反向传播 | AI/ML | `10_dl_basics.py` |
| 2.4 | TF-IDF向量检索 | AI/ML | `27_rag_system.py` |
| 2.5 | BM25关键词检索 | AI/ML | `27_rag_system.py` |
| 2.6 | 混合检索+RRF融合 | AI/ML | `27_rag_system.py` |
| 2.7 | 交叉验证+模型评估 | AI/ML | `09_ml_basics.py` |
| 2.8 | NumPy向量化KNN | AI/ML | `04_numpy_basics.py` |
| 3.1 | SQL注入与参数化查询 | 安全攻防 | `23_security_attack.py` |
| 3.2 | XSS与输出编码 | 安全攻防 | `26_security_defense.py` |
| 3.3 | WAF规则+CSP策略 | 安全攻防 | `26_security_defense.py` |
| 3.4 | 命令注入与安全执行 | 安全攻防 | `23_security_attack.py` |
| 3.5 | 路径遍历防御 | 安全攻防 | `23_security_attack.py` |
| 4.1 | Docker多阶段构建 | 工程化 | `devops/Dockerfile` |
| 4.2 | Docker Compose编排 | 工程化 | `devops/docker-compose.yml` |
| 4.3 | K8s部署清单+HPA | 工程化 | `devops/k8s/k8s-deployment.yaml` |
| 4.4 | GitHub Actions CI/CD | 工程化 | `devops/ci.yml` |
| 4.5 | 负载均衡三策略 | 工程化 | `25_system_design.py` |
| 4.6 | 缓存策略三模式 | 工程化 | `25_system_design.py` |
| 5.1 | 多语言语法对照表 | 多语言 | `lang_exercises/*` |
| 5.2 | Rust所有权与借用 | 多语言 | `lang_exercises/13_rust.rs` |
| 5.3 | Go并发模型 | 多语言 | `lang_exercises/14_go.go` |
| 5.4 | JS闭包与模块模式 | 多语言 | `lang_exercises/17_javascript.js` |
| 5.5 | Java泛型与函数式 | 多语言 | `lang_exercises/16_java.java` |
| 5.6 | 各语言特色速览 | 多语言 | `lang_exercises/*` |

---

> **共 35 个模式**，覆盖 Python 核心设计模式、异步编程、数据处理、AI/ML 算法实现、RAG 检索系统、安全攻防、DevOps 工程化、以及多语言编程范式。
> 所有代码均从 496 道练习中提炼，可直接复制使用。
