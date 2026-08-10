# Suyi（溯忆）— 自进化 AI Agent 框架

> **溯忆** — 追溯过往，构建记忆，自我进化。

Suyi 是一个纯 Python 实现的自进化 AI Agent 框架，不依赖 PyTorch / TensorFlow / OpenAI SDK。
核心依赖仅为 `httpx` + `numpy`，设计目标是在保持极简依赖的同时提供生产级的 Agent 能力。

## 核心特性

| 模块 | 说明 |
|------|------|
| **Memory** | 三层记忆系统 — 工作记忆 / 情景记忆 / 语义记忆，支持 TF-IDF 检索与生命周期遗忘 |
| **Core** | ReAct 循环 + 四层上下文组装 + 三维预算管理（轮次 / Token / 时间） |
| **Tools** | 工具基类 + 权限分级（auto / confirm / block）+ 内置工具（Bash / 读写文件 / 搜索） |
| **Skills** | 渐进式披露技能系统 — 菜单 → 加载 → 执行，YAML front-matter + 安全扫描 |
| **Middleware** | 可插拔中间件链 — 压缩 / 记忆注入 / 循环检测 / 澄清 |
| **Multi-Agent** | AgentInstance + OrchestratorAgent + 三种协作模式（Pipeline / Blackboard / Voting） |
| **Evolution** | 自进化引擎 — 行为学习 / 技能自动生成 / 性能评估 / 反馈收集 |

**扩展模块（v0.2.0 — v0.6.0）：**

| 模块 | 版本 | 说明 |
|------|------|------|
| **LLM Adapters** | v0.2.0 | OpenAI / Anthropic 适配器，纯 httpx 实现，支持流式输出 |
| **Config** | v0.2.0 | 类型安全配置系统，支持 YAML / JSON / dict 加载 |
| **CLI** | v0.2.0 | 交互式 REPL，支持 Mock 模式与多提供商切换 |
| **Web API** | v0.2.0 | 标准库 HTTP 服务器（不依赖 Flask / FastAPI），支持 CORS |
| **Persistence** | v0.2.0 | JSON 文件会话持久化，支持创建 / 保存 / 加载 / 列出 / 导出 |
| **Streaming** | v0.2.0 | 异步流式输出处理器，支持逐 token 输出与工具调用中断 |
| **MCP** | v0.3.0 | Model Context Protocol — JSON-RPC 2.0，Server/Client 双向适配，MemoryTransport 测试 |
| **AI Gateway** | v0.3.0 | GatewayRouter + FallbackChain + 令牌桶限流 + 成本追踪，直接实现 LLMInterface |
| **Observability** | v0.3.0 | 结构化日志 + Prometheus 指标 + 分布式追踪 + 中间件集成 |
| **Guardrails** | v0.3.0 | 三档严格度（strict / moderate / lenient），PII 脱敏 + 注入防护 |
| **HITL** | v0.3.0 | Human-in-the-Loop — 连续 3 次批准自动放行，2 次拒绝自动阻止 |
| **Evaluation** | v0.4.0 | 评估框架 — 6 个指标类 + Benchmark 基准测试 + A/B 测试统计引擎（纯 numpy） |
| **Prompts** | v0.4.0 | Prompt 管理 — 模板变量插值 / 继承 / 组合 + 版本管理 / 热重载 + 14 个预置模板 |
| **Memory Refactor** | v0.5.0 | 7 层记忆 — Ground Truth / Structured Facts / Auto Wiki / 四级回退检索链 / 语义去重 / Trust Scoring / Trivial 跳过 |
| **Pre-LLM Inject** | v0.5.0 | Pre-LLM-Call 自动记忆注入中间件 — 并行查询四层记忆 + 相关性阈值过滤 |
| **Agent Pipeline** | v0.5.0 | Agent 接力 Pipeline — 声明式链路 / 数据契约校验 / 条件跳转 |
| **Swarm** | v0.5.0 | Swarm 蜂群自治 — 共享任务板 + 能力标签匹配 + 并行执行 + Guardrails/HITL 集成 |
| **RAG Pipeline** | v0.6.0 | 文档分块（固定/句子/语义）+ RAG 完整管道（ingest→chunk→embed→store→retrieve→augment） |
| **Caching Layer** | v0.6.0 | 精确缓存（SHA-256）+ 语义缓存（TF-IDF 相似度）+ LRU 淘汰 + TTL + JSON 持久化 |
| **Workflow Engine** | v0.6.0 | DAG 工作流引擎 — 条件分支 / 并行执行 / 循环检测 / 失败重试 / 三种失败策略 |
| **Event System** | v0.6.0 | 事件总线 — 同步/异步发布订阅 + fnmatch 通配符 + 15 种标准事件类型 + 事件历史 |
| **Plugin System** | v0.7.0 | 插件系统 — 热加载/卸载 + 依赖图拓扑排序 + 多源加载（文件/包/entry_points） |
| **Deploy Templates** | v0.7.0 | 部署模板 — Docker（Dockerfile + docker-compose）+ K8s（Deployment/Service/Ingress）配置生成 |
| **Vector Store** | v0.7.0 | 向量存储 — 纯 numpy 余弦相似度 + L2 距离 + Top-K 检索 + RAG/Memory 适配器 |
| **Multimodal** | v0.7.0 | 多模态输入 — 统一容器（text/image/audio/video）+ 格式检测 + base64 编解码 |
| **Rate Limiting** | v0.8.0 | 令牌桶限流 + 滑动窗口 + 多维度限流策略 |
| **State Machine** | v0.8.0 | 有限状态机 — 状态转换 / 守卫条件 / 历史追踪 |
| **Cost Tracker** | v0.8.0 | 多提供商成本追踪 + 预算告警 + 用量统计 |
| **Feedback Loop** | v0.8.0 | 反馈闭环收集器 — 显式/隐式反馈信号 + 信号聚合 |
| **OmniRoute Adapter** | v0.9.0 | OmniRoute LLM Gateway 适配器 — 本地 LLM 路由 + 115 模型可用 |
| **SQLite Persistence** | v0.9.0 | SQLite 持久化层 — FTS5 全文搜索 + 迁移管理 + JSON 后端兼容 |
| **Real Tools** | v0.9.0 | WebRequestTool（SSRF 防护）+ CodeSandboxTool（安全执行） |
| **API Auth** | v0.9.0 | JWT + API Key + CORS 认证安全层（纯标准库） |
| **E2E Integration** | v0.9.0 | 5 条完整链路端到端集成测试 |

**ALA 原创模块（v1.0.0 — Adaptive Loop Architecture）：**

| 模块 | Phase | 说明 |
|------|-------|------|
| **Quality Grading** | 13 | 来源分级(S-D) + 结果分级(Verified-Failed) + 加权混合质量评分 + Ebbinghaus 遗忘曲线 |
| **Forgetting Engine** | 13 | 三级遗忘策略（DEGRADE/COMPRESS/PURGE）+ 安全网（user-pinned 不可删除）+ dry-run 预览 |
| **Anti-Pattern Memory** | 13 | 失败模式提取 + 反面记忆存储 + 检索优先级提升 + 永不自动删除 |
| **Loop Template Memory** | 14 | Loop 结构本身作为可复用记忆 — phases/reflection_points/budgets 模板化 + 变异 + A/B 测试 |
| **Strategy Evolver** | 15 | ProcessReflection 五维反思 + 六种变异策略 + z 检验/Wilson 区间统计显著性验证 |
| **Bilevel Loop** | 16 | 内层 TaskLoop（业务执行）+ 外层 EvolutionLoop（自我进化）+ 四种触发机制 |
| **Evolution Report** | 17 | 进化报告生成器 — to_dict/to_markdown/to_json + 8 部分结构化报告 |
| **E2E Evolution Cycle** | 17 | 12 轮端到端进化循环验证 — 模板积累 + 遗忘压缩 + 策略变异 + A/B 实验 + 反面记忆注册 |

## 架构总览

```
┌──────────────────────────────────────────────────────────────────┐
│                 用户 / CLI / Web API / MCP Client                 │
├──────────────────────────────────────────────────────────────────┤
│                   Middleware Chain (8 层)                         │
│  Observability(5) → Summarization(10) → Guardrails(15) →        │
│  MemoryInject(20) → PreLLMInject(25) → LoopDetection(30) →      │
│  HITL(35) → Clarify(40)                                          │
├──────────────────────────────────────────────────────────────────┤
│                      Agent Loop (ReAct)                          │
│  ┌─────────┐   ┌───────────┐   ┌─────────┐   ┌──────────┐      │
│  │ 预算检查  │→│ 上下文组装  │→│ LLM 调用 │→│ 工具执行  │      │
│  └─────────┘   └───────────┘   └─────────┘   └──────────┘      │
├───────────┬─────────────┬──────────────┬────────────────────────┤
│  Memory   │   Tools     │   Skills     │   Multi-Agent          │
│ ┌────────┐│ ┌─────────┐│ ┌──────────┐ │ ┌────────────────┐     │
│ │Working ││ │BashTool ││ │Loader    │ │ │Orchestrator    │     │
│ │Episodic││ │ReadFile ││ │Menu      │ │ │SubAgentManager │     │
│ │Semantic││ │WriteFile││ │Scanner   │ │ │Pipeline        │     │
│ └────────┘│ │Search   ││ └──────────┘ │ │Blackboard      │     │
│           │ │SkillTool││              │ │Voting          │     │
│           │ └─────────┘│              │ └────────────────┘     │
├───────────┴─────────────┴──────────────┴────────────────────────┤
│           Evolution Engine         Evaluation Framework          │
│  ┌──────────┐ ┌────────────┐ ┌───────────┐  ┌──────────────┐   │
│  │ Learner  │→│SkillGenerat│→│ Evaluator │  │ Metrics      │   │
│  └──────────┘ └────────────┘ └───────────┘  │ Benchmark    │   │
│         ↑           ↑                        │ A/B Testing   │   │
│  ┌──────┴──────┐ ┌─┴──────────┐             └──────────────┘   │
│  │FeedbackColl │ │Interaction │                                │
│  └─────────────┘ └────────────┘                                │
├──────────────────────────────────────────────────────────────────┤
│         AI Gateway (Router + Fallback + RateLimit + Cost)        │
├──────────────────────────────────────────────────────────────────┤
│           LLM Adapters (httpx)        Prompt Management          │
│  ┌──────────────┐  ┌────────────────┐  ┌──────────────────┐     │
│  │ OpenAIAdapter│  │AnthropicAdapter│  │ Template Manager │     │
│  │ (DeepSeek等) │  │ (Claude)       │  │ Library (14模板) │     │
│  └──────────────┘  └────────────────┘  └──────────────────┘     │
├──────────────────────────────────────────────────────────────────┤
│ Persistence(JSON)│Streaming│MCP Server│Guardrails│HITL│Observability│
└──────────────────────────────────────────────────────────────────┘
```

## 快速开始

### 安装

```bash
# 从源码安装
git clone https://github.com/your-org/suyi.git
cd suyi
pip install -e .

# 或直接安装依赖
pip install httpx numpy
```

### CLI 交互模式

```bash
# Mock 模式（无需 API key，推荐首次体验）
suyi --mock

# 指定 LLM 提供商
suyi --provider openai --model gpt-4o

# 指定技能库目录
suyi --mock --skills-dir ./my_skills
```

### 配置文件

创建 `config.yaml`：

```yaml
llm:
  provider: openai
  api_key: sk-your-key-here
  model: gpt-4o
  temperature: 0.7
  max_tokens: 4096

memory:
  token_budget: 8192
  storage_dir: ./data/memory

tools:
  enable_bash: true
  enable_file_ops: true

middleware:
  enable_summarization: true
  enable_memory_injection: true
  enable_loop_detection: true
```

加载配置：

```python
from suyi import load_config, get_default_config

# 默认配置
config = get_default_config()

# 从文件加载
config = load_config("config.yaml")
```

## 使用示例

### 基本对话

```python
import asyncio
from suyi import AgentLoop, MockLLM, LLMResponse

async def main():
    llm = MockLLM([LLMResponse.text("你好！我是溯忆。")])
    loop = AgentLoop(llm=llm)
    result = await loop.run("你好")
    print(result.content)  # 你好！我是溯忆。

asyncio.run(main())
```

### 使用工具

```python
import asyncio
from suyi import AgentLoop, MockLLM, LLMResponse, FunctionTool, BudgetTracker, BudgetConfig

async def search(query: str) -> str:
    return f"搜索结果：{query} 的相关信息..."

search_tool = FunctionTool("search", "搜索互联网", search)

async def main():
    llm = MockLLM([
        LLMResponse.action("search", {"query": "Python asyncio"}, content="让我搜索一下。"),
        LLMResponse.text("Python asyncio 是用于编写并发代码的库。"),
    ])
    loop = AgentLoop(
        llm=llm,
        tools=[search_tool],
        budget_tracker=BudgetTracker(BudgetConfig(max_turns=10)),
    )
    result = await loop.run("Python asyncio 是什么？")
    print(result.content)

asyncio.run(main())
```

### 三层记忆系统

```python
from suyi import MemoryManager

mgr = MemoryManager()

# 添加语义记忆
mgr.add_memory("Python GIL 限制了多线程性能", tags=["python", "threading"])

# 检索相关记忆
results = mgr.retrieve_relevant("Python 多线程")
for r in results:
    print(f"[{r['layer']}] {r['content'][:50]}...")

# 巩固与清理
mgr.consolidate()
mgr.cleanup()
```

### 多 Agent 协作

```python
import asyncio
from suyi import AgentInstance, AgentConfig, MockLLM, LLMResponse

async def main():
    researcher = AgentInstance(
        config=AgentConfig(
            name="researcher",
            role="信息检索专家",
            description="负责搜索和整理信息",
        ),
        llm=MockLLM([LLMResponse.text("找到了相关信息。")]),
    )

    writer = AgentInstance(
        config=AgentConfig(
            name="writer",
            role="内容撰写专家",
            description="负责将信息整理成文章",
        ),
        llm=MockLLM([LLMResponse.text("文章已写好。")]),
    )

    r1 = await researcher.run("搜索 Python asyncio 相关信息")
    r2 = await writer.run(f"基于以下信息写文章：{r1.content}")
    print(r2.content)

asyncio.run(main())
```

### 流式输出

```python
import asyncio
from suyi import StreamHandler, MockLLM, LLMResponse

async def main():
    llm = MockLLM([LLMResponse.text("这是一段流式输出的文本。")])
    handler = StreamHandler(llm=llm, chunk_size=3)

    async for chunk in handler.stream("你好"):
        if chunk.type == "token":
            print(chunk.content, end="", flush=True)
        elif chunk.type == "complete":
            print(f"\n--- 完成（{chunk.metadata['turns']} 轮）---")

asyncio.run(main())
```

### 会话持久化

```python
from suyi import SessionManager

mgr = SessionManager(storage_dir="./data")

# 创建会话
sid = mgr.create_session()
mgr.add_message(sid, "user", "你好")
mgr.add_message(sid, "assistant", "你好！有什么可以帮你的？")
mgr.save_session(sid)

# 加载会话
data = mgr.load_session(sid)
print(f"会话 {data.session_id} 有 {len(data.history)} 条消息")
```

### Web API 服务

```python
from suyi import SuyiServer, MockLLM, LLMResponse

# 启动 HTTP API 服务
server = SuyiServer(
    llm=MockLLM([LLMResponse.text("Hello from Suyi!")]),
    host="0.0.0.0",
    port=8080,
)
server.start()
```

API 端点：

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/chat` | 发送消息，获取 Agent 回复 |
| GET | `/memory` | 查看记忆系统状态 |
| GET | `/tools` | 列出已注册工具 |
| POST | `/skills/load` | 加载指定技能 |
| GET | `/health` | 健康检查 |
| GET | `/sessions` | 列出已保存会话 |

### 自进化引擎

```python
from suyi.evolution import (
    LearningEngine, SkillGenerator, BehaviorEvaluator, FeedbackCollector
)

engine = LearningEngine()
engine.record_interaction(record)
patterns = engine.extract_patterns()
engine.update_policy()

generator = SkillGenerator()
skills = generator.generate_from_patterns(patterns)
```

## 模块说明

### Memory（七层记忆 v0.5.0）

- **GroundTruth**：最高优先级记忆，冲突检测，不会被遗忘或覆盖
- **StructuredFacts**：实体-属性-值三元组，Trust Scoring（用户陈述 0.95 / Agent 推断 0.6 / 推测 0.3）
- **WorkingMemory**：当前对话上下文，动态组装，Token 预算控制
- **EpisodicMemory**：会话日志，基于时间衰减的分级压缩
- **SemanticMemory**：跨会话知识库，TF-IDF 语义检索
- **AutoWiki**：自动知识整理 — 从会话和事实中提取概念关系，生成 Wiki 页面
- **RetrievalChain**：四级回退检索链 — Hybrid → Dense → Lexical → SQLite
- **SemanticDedup**：Cosine 相似度去重，信息并集合并策略
- **MessageClassifier**：Trivial 消息跳过（"好的""谢谢"等不写入记忆）
- **MemoryLifecycle**：四阶段遗忘 — 新鲜 → 巩固 → 压缩 → 遗忘

### Core（ReAct 循环）

- **AgentLoop**：Thought → Action → Observation → Final Answer 循环
- **ContextAssembler**：四层上下文组装（系统 / 身份 / 记忆 / 对话），支持前缀缓存
- **BudgetTracker**：三维预算 — 轮次 / Token / 墙钟时间，渐进式阈值告警

### Tools（工具系统）

- **AgentTool**：工具基类，支持 `assess_risk()` 运行时风险评估
- **权限分级**：`auto`（自动执行）/ `confirm`（需确认）/ `block`（禁止执行）
- **内置工具**：BashTool / ReadFileTool / WriteFileTool / SearchTool / SkillTool

### Skills（技能系统）

- **渐进式披露**：菜单阶段（~100 token/技能）→ 加载阶段 → 执行阶段
- **SkillLoader**：YAML front-matter 解析，关键词匹配
- **SkillScanner**：安全扫描，检测危险操作模式

### Middleware（中间件链 8 层）

- **ObservabilityMiddleware**（v0.3.0）：结构化日志 + 指标 + 追踪
- **SummarizationMiddleware**：历史压缩
- **GuardrailsMiddleware**（v0.3.0）：PII 脱敏 + 注入防护
- **MemoryInjectMiddleware**：语义记忆注入
- **PreLLMInjectMiddleware**（v0.5.0）：Pre-LLM-Call 并行查询四层记忆 + 相关性阈值过滤
- **LoopDetectionMiddleware**：循环检测
- **HITLMiddleware**（v0.3.0）：Human-in-the-Loop 审批
- **ClarificationMiddleware**：自动澄清

### Multi-Agent（多智能体）

- **AgentInstance**：封装 AgentLoop + Memory + Tools 的独立 Agent
- **OrchestratorAgent**：任务分解 + 并行调度 + 结果聚合
- **Pipeline**：串行流水线（A → B → C）
- **Blackboard**：共享黑板 + 发布订阅
- **Voting**：多数 / 加权 / 置信度投票
- **AgentPipeline**（v0.5.0）：声明式接力链 — 数据契约校验 + 条件跳转 + 上下文传递
- **Swarm**（v0.5.0）：蜂群自治模式 — 共享任务板 + 能力标签匹配 + 并行执行 + Guardrails/HITL 集成

### RAG Pipeline（检索增强生成 v0.6.0）

- **FixedSizeChunker**：固定大小分块，可配置重叠窗口
- **SentenceChunker**：句子边界分块，保持语义完整性
- **SemanticChunker**：Markdown 标题 + 段落语义分块
- **RAGRetriever**：复用 Memory 四级回退检索链，带文档来源标记
- **RAGPipeline**：完整管道 — ingest → chunk → embed → store → retrieve → augment

### Caching Layer（缓存层 v0.6.0）

- **ExactCache**：SHA-256 hash 精确匹配，O(1) 查找
- **SemanticCache**：TF-IDF 相似度语义缓存，模糊命中
- **CacheManager**：整合精确 + 语义缓存，LRU 淘汰策略，大小限制，命中统计，JSON 持久化

### Workflow Engine（工作流引擎 v0.6.0）

- **DAG**：有向无环图定义 — Node / Edge / NodeStatus，条件分支，循环检测（DFS），拓扑排序
- **WorkflowEngine**：拓扑排序执行，asyncio.gather 并行，可配置重试（max_retries），三种失败策略（STOP / CONTINUE / RETRY）

### Event System（事件系统 v0.6.0）

- **EventBus**：同步 / 异步发布订阅，fnmatch 通配符匹配，一次性订阅，事件历史，全局总线单例
- **EventType**：15 种标准事件 — before/after LLM call、before/after tool call、memory_updated、skill_loaded、agent_spawned、error 等

### Plugin System（插件系统 v0.7.0）

- **PluginBase**：抽象基类，定义 init/start/stop 生命周期 + hooks 注册系统
- **PluginRegistry**：插件注册表，依赖图 + 拓扑排序 + 反向依赖追踪 + 安全卸载检查
- **PluginLoader**：多源加载器 — 文件路径 / Python 包 / entry_points，自动检测
- **PluginManager**：全生命周期管理 — 加载/启动/停止/卸载/热重载，依赖排序启动

### Deployment Templates（部署模板 v0.7.0）

- **DeploymentConfig**：部署配置 — 环境变量映射 + 健康检查 + 资源限制 + dev/prod 工厂方法
- **DockerConfigGenerator**：生成 Dockerfile + docker-compose.yml（含健康检查、资源限制、环境变量）
- **K8sConfigGenerator**：生成 Deployment/Service/Ingress YAML（含 liveness/readiness probes、resources、volumes）

### Vector Store（向量存储 v0.7.0）

- **VectorStoreBase**：抽象接口 — add / search / delete
- **InMemoryVectorStore**：纯 numpy 实现 — 余弦相似度 + L2 距离 + 批量插入 + Top-K 检索 + 过滤
- **VectorStoreRetrieverAdapter**：桥接 Memory 模块 RetrievalChain
- **RAGVectorStoreAdapter**：桥接 RAG Pipeline

### Multimodal（多模态输入 v0.7.0）

- **MultimodalInput**：统一输入容器 — text / image / audio / video
- **InputProcessor**：格式检测 + 大小验证 + MIME 类型处理
- **FormatConverter**：base64 编解码 + data URI 转换 + MIME 类型映射

### Evolution（自进化）

- **LearningEngine**：从交互记录中提取行为模式，更新策略
- **SkillGenerator**：识别高频工具序列，自动生成 SKILL.md
- **BehaviorEvaluator**：多维度性能评估 + A/B 版本对比
- **FeedbackCollector**：显式（赞/踩 + 文本）与隐式反馈信号收集

### ALA — Adaptive Loop Architecture（v1.0.0 原创模块）

ALA 是 Suyi 的核心创新 — 让 Loop 本身成为可进化的记忆，实现"溯（检索模板）→ 忆（存储模板）→ 进化（双层循环）"。

**双层循环架构：**
```
┌─────────────────────────────────────────────────────┐
│              BilevelLoop (顶层协调器)                 │
│  ┌───────────────────────────────────────────────┐  │
│  │     TaskLoop (内层 — 业务执行)                  │  │
│  │  检索最优模板 → 按 phases 执行 → 反思 → 记录   │  │
│  └──────────────────────┬────────────────────────┘  │
│                         │ TaskResult                  │
│  ┌──────────────────────▼────────────────────────┐  │
│  │   EvolutionLoop (外层 — 自我进化)               │  │
│  │  过程反思 → 更新模板统计 → 遗忘引擎 →          │  │
│  │  失败注册反面记忆 → 变异模板 → A/B 实验评估    │  │
│  └───────────────────────────────────────────────┘  │
│  触发机制: EVERY_TASK / ACCUMULATED_N /             │
│           PERFORMANCE_DROP / SCHEDULED               │
└─────────────────────────────────────────────────────┘
```

- **QualityGrader**：来源分级(S/D) × 结果分级(Verified→Failed) × 置信度 × 证据比 → 加权混合质量评分
- **ForgettingEngine**：Ebbinghaus 遗忘曲线 Q(t)=Q₀·e^(-t/τ) + 三级策略（DEGRADE > 0.2 / COMPRESS > 0.05 / PURGE < 0.05）+ 安全网（user-pinned 降级为 DEGRADE）
- **AntiPatternStore**：失败模式自动提取 + 反面记忆永久存储 + 检索优先级 ≥ 0.5 + `__len__` 支持
- **LoopTemplateStore**：Loop 结构模板化（phases / reflection_points / budgets / system_prompts）+ 模板变异 + 统计追踪 + SQLite 持久化
- **StrategyEvolver**：ProcessReflection 五维反思（效率/质量/成本/鲁棒性/创新性）+ 六种变异（PHASE_REORDER / BUDGET_REALLOC / REFLECTION_INSERT / PROMPT_REFINE / TOOL_SWAP / PHASE_MERGE）+ A/B z 检验
- **BilevelLoop**：内层 TaskLoop 执行业务 + 外层 EvolutionLoop 自我进化 + 四种触发机制 + ConfigurableTaskLoop 测试辅助
- **EvolutionReportGenerator**：8 部分结构化报告（任务概览 / 模板演化 / 遗忘摘要 / 变异历史 / A/B 结果 / 性能对比 / 关键发现 / 建议）

**原创性声明：**
- 质量分级：RAGAS 最近，但引入记忆生命周期评分
- 遗忘引擎：无现有方案，Ebbinghaus 曲线 + 三级策略
- Loop 模板：CoT 最近，但 Loop 结构本身作为可复用记忆
- 策略进化器：Reflexion 最近，但修改 Loop 本身（非仅 prompt）
- 双层循环：Meta AI 概念论文未开源
- 反面记忆：无现有方案

### LLM Adapters（LLM 适配器）

- **OpenAIAdapter**：支持 OpenAI / DeepSeek / Moonshot / Together / Groq 等兼容 API
- **AnthropicAdapter**：支持 Anthropic Claude Messages API
- 纯 httpx 实现，不依赖官方 SDK
- 支持 `chat()` 同步调用与 `chat_stream()` 流式输出

## 配置说明

配置系统使用 dataclass 定义，支持 YAML / JSON / dict 加载：

```python
from suyi import SuyiConfig, LLMConfig, load_config

# 编程式配置
config = SuyiConfig(
    llm=LLMConfig(provider="openai", model="gpt-4o", api_key="sk-..."),
)

# 从文件加载
config = load_config("config.yaml")

# 保存配置
from suyi import save_config
save_config(config, "config.yaml")
```

配置项：

| 配置节 | 说明 |
|--------|------|
| `llm` | provider / api_key / base_url / model / temperature / max_tokens |
| `memory` | token_budget / storage_dir |
| `tools` | enable_bash / enable_file_ops |
| `middleware` | enable_summarization / enable_memory_injection / enable_loop_detection |
| `agent` | max_turns / max_tool_retries |
| `evolution` | enable_learning / enable_skill_generation / enable_evaluation |

## 开发指南

### 环境准备

```bash
git clone https://github.com/your-org/suyi.git
cd suyi
pip install -e ".[dev]"
```

### 运行测试

```bash
# 全部测试
pytest

# 带覆盖率
pytest --cov=suyi

# 仅运行特定模块测试
pytest tests/test_persistence.py
pytest tests/test_streaming.py
pytest tests/test_web_api.py

# 并行运行
pytest -n auto
```

### 项目结构

```
suyi/
├── suyi/
│   ├── __init__.py          # 顶层导出
│   ├── core/                # ReAct 循环 + 上下文 + 预算
│   ├── memory/              # 三层记忆系统
│   ├── tools/               # 工具系统 + 权限
│   ├── skills/              # 渐进式披露技能系统
│   ├── middleware/          # 可插拔中间件链
│   ├── agents/              # 多 Agent 系统
│   ├── evolution/           # 自进化引擎
│   ├── llm/                 # LLM 适配器 (OpenAI / Anthropic)
│   ├── config/              # 配置系统
│   ├── cli/                 # 交互式 CLI
│   ├── web/                 # HTTP API 服务器
│   ├── persistence/         # 会话持久化 (JSON)
│   ├── streaming/           # 流式输出处理器
│   ├── rag/                 # RAG 管道 (文档分块/检索/增强)
│   ├── cache/               # 缓存层 (精确+语义 LRU)
│   ├── workflow/            # 工作流引擎 (DAG/并行/重试)
│   ├── events/              # 事件系统 (发布订阅/通配符)
│   ├── plugins/             # 插件系统 (热加载/依赖图)
│   ├── deploy/              # 部署模板 (Docker/K8s)
│   ├── vectorstore/         # 向量存储 (numpy余弦相似度)
│   ├── multimodal/          # 多模态输入 (text/image/audio/video)
│   └── utils/               # 工具函数
│   ├── quality/              # ALA: 质量分级 + 遗忘引擎 + 反面记忆 + Loop模板 + 策略进化器 + 双层循环
│   ├── ratelimit/            # 限流模块
│   ├── statemachine/         # 状态机
│   ├── cost/                 # 成本追踪
│   ├── feedback/             # 反馈闭环
│   └── utils/               # 工具函数
├── tests/                   # 测试套件 (2774 个测试)
├── examples/                # 示例代码
├── data/                    # 数据目录
├── pyproject.toml           # 打包配置
└── README.md
```

### 贡献

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/amazing-feature`
3. 编写代码并添加测试
4. 确保所有测试通过：`pytest`
5. 提交 Pull Request

### 编码规范

- Python 3.10+，使用 `from __future__ import annotations`
- 类型注解全覆盖
- 每个公共类和方法都有 docstring
- 测试覆盖所有公共 API

## License

MIT License

Copyright (c) 2025 Suyi Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
