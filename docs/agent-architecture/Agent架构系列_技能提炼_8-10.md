# Agent架构系列文章技能提炼（8-10）

> 来源：公众号「架构师带你玩转AI」系列三篇，作者 AllenTang
> 提炼目标：可直接用于自进化 Agent 项目开发的实操知识

---

## 一、三篇文章概览

| 序号 | 文章标题 | 核心视角 | 交付物 |
|------|----------|----------|--------|
| 8 | 一文搞懂 Agent开发（从 LangChain 版本演进视角） | 框架演进史 → Harness 定义 | LangChain 四次迭代的架构决策与最终收敛点 |
| 9 | 从零开始理解 Agent开发：LangChain / LangGraph / DeerFlow 小白入门指南 | 三层栈 → 递进式搭建路径 | 三框架的定位、关系与可运行代码 |
| 10 | 写个 Markdown 就叫开发 Agent？三种 Agent 开发方式，你在哪一层？ | 能力分层 → 投入产出判断 | Tier 1-3 能力层级划分与判断标准 |

---

## 二、逐篇技能提炼

### 📄 文章8：一文搞懂 Agent开发（从 LangChain 版本演进视角）

#### 2.1 核心架构决策及理由

| 决策 | 理由 | 版本节点 |
|------|------|----------|
| 初始抽象选 Chain（预定义步骤序列） | 早期 LLM 应用就是"检索+生成"等线性流程，Chain 足够 | v0.0.x |
| 工具调用从 JSON 解析切换到 function calling | 自由文本解析"赌运气"无法用于生产，API 原生支持提升可靠性数量级 | 2023.03 转折点 |
| 建 LangGraph（图执行模型）而非修补 AgentExecutor | AgentExecutor 是黑盒，无法加条件分支/人工审批/重试逻辑 | v0.2 |
| 大量旧 Chain 标记弃用 | 技术债清理，引导用户迁移到 LangGraph / LCEL | v0.3 |
| 所有抽象收敛为唯一 `create_agent` | Agent 核心不是"框架替你做多少事"而是"给你多少控制权"；最小但完整的控制面 | v1.0 |
| Memory 模块被砍掉，由 checkpointer + 中间件取代 | Memory 是关注点之一，应该和其他关注点一样用中间件管理 | v1.0 |

#### 2.2 可复用的设计模式 / 代码模式

**模式1：Harness = Prompt + Tools + Middleware + State**

> Harness 的职责：在正确的时间，为给定任务，把正确的上下文交给模型。它是模型循环周围的一切——提示词、工具、中间件、状态管理——但唯独不包含模型本身。

**模式2：中间件系统——每个中间件处理一个关注点，在正确时机钩入 Agent 循环**

统一取代了之前散落的 `pre_model_hook`、`post_model_hook`、手写 try/except、手动上下文压缩等机制。

**模式3：Agent 核心循环（不变量）**

```
Thought → Action → Observation → Thought → ... → Final Answer
```

无论哪个版本，核心循环始终是这个 ReAct 循环，v1.0 只是把每个环节变成可插拔的中间件挂钩点。

#### 2.3 关键实现细节（含代码片段）

**v1.0 唯一入口 `create_agent`：**

```python
from langchain.agents import create_agent

def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"

agent = create_agent(
    model="openai:gpt-5.5",                    # 统一 "provider:model" 格式
    tools=[get_weather],                        # 任何 Python callable
    system_prompt="You are a helpful assistant",
)
result = agent.invoke({
    "messages": [{"role": "user", "content": "SF天气如何？"}]
})
```

**生产级 Agent 的中间件配置（重点参考）：**

```python
from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelRetryMiddleware, ToolRetryMiddleware,
    SummarizationMiddleware, HumanInTheLoopMiddleware,
)
from deepagents.middleware import (
    FilesystemMiddleware, SubAgentMiddleware,
)
from deepagents.backends import StateBackend

backend = StateBackend()

agent = create_agent(
    model="openai:gpt-5.5",
    tools=[search, write_file, run_code],
    system_prompt="你是一个研究助手",
    middleware=[
        FilesystemMiddleware(backend=backend),                    # 文件系统
        SummarizationMiddleware(model="openai:gpt-5.5",           # 上下文压缩
                                trigger={"tokens": 10000}),
        SubAgentMiddleware(backend=backend,                       # 子 Agent 委派
            subagents=[{"name": "researcher", "tools": [search]}]),
        ModelRetryMiddleware(max_retries=3),                      # 模型容错
        ToolRetryMiddleware(max_retries=2),                       # 工具容错
        HumanInTheLoopMiddleware(                                  # 人类审批
            interrupt_on={"write_file": True}),
    ],
)
```

> **自进化 Agent 项目直接可用**：上述中间件组合覆盖了文件操作、上下文管理、子任务委派、容错重试、人工审批——这是一个生产级 Agent 的最小完整配置模板。

#### 2.4 与其他模块的依赖关系

- `create_agent` 依赖中间件提供扩展能力，中间件之间可自由组合无耦合
- `SubAgentMiddleware` 依赖 `StateBackend` 进行状态共享
- `SummarizationMiddleware` 需要独立指定 model（可与主模型不同）
- `HumanInTheLoopMiddleware` 通过 `interrupt_on` 字典声明哪些工具调用需要人工审批
- v1.0 底层仍依赖 LangGraph 的图执行引擎驱动循环

---

### 📄 文章9：从零开始理解 Agent开发：LangChain / LangGraph / DeerFlow 小白入门指南

#### 2.5 核心架构决策及理由

| 决策 | 理由 |
|------|------|
| 三框架定位为自底向上的三层栈 | 各层职责清晰：LangChain 定义底层能力，LangGraph 做编排，DeerFlow 做运行时 |
| LangGraph 用"图"而非"循环"描述工作流 | 真实场景需要条件分支、并行执行、状态管理、人机交互、检查点恢复 |
| DeerFlow 在 LangGraph 之上加完整工程化能力 | LangGraph 只给零件，DeerFlow 给一辆能开的车——前端、API、沙箱、技能、记忆系统 |
| DeerFlow 技能按需加载，不污染基础上下文 | Agent 基础能力保持精简，领域技能动态挂载 |

#### 2.6 可复用的设计模式 / 代码模式

**模式4：Agent 四核心组件**

| 组件 | 作用 | 类比 |
|------|------|------|
| LLM（大脑） | 理解语言、推理决策 | 人的大脑 |
| Tool（工具） | 执行具体操作 | 手和脚 |
| Memory（记忆） | 记住对话历史和跨会话信息 | 人的记忆 |
| Harness（身体） | 运行环境，管理状态、调度工具 | 人的身体 |

**模式5：StateGraph 工作流编排（节点+边+条件路由+检查点）**

- State：在整个图中流转的数据
- Node：处理状态数据的函数（每个节点只关心自己的输入输出，互不耦合）
- Edge：节点之间的连接，可带条件
- Checkpoint：保存中间状态，支持回滚

**模式6：DeerFlow 子 Agent 架构**

```
Lead Agent（主控）
  ├─ 子 Agent 1：并行搜索资料
  ├─ 子 Agent 2：并行分析数据
  └─ 子 Agent 3：并行生成报告
```

**模式7：DeerFlow 中间件链式执行**

```
用户消息 → [摘要压缩] → [记忆注入] → [计划更新] → LLM → [标题生成] → [记忆排队] → 响应
```

内置中间件清单：
- `SummarizationMiddleware`：自动压缩旧消息，防止上下文溢出
- `MemoryMiddleware`：跨会话记忆注入
- `TodoMiddleware`：计划模式，跟踪任务进度
- `TokenUsageMiddleware`：追踪 Token 用量和成本
- `LoopDetectionMiddleware`：检测死循环

**模式8：DeerFlow 技能系统（SKILL.md 格式）**

```markdown
# skills/custom/weekly-report/SKILL.md
---
name: weekly-report
description: 生成工作周报
category: productivity
---
# 工作周报生成技能
## 指令
当用户请求生成周报时，按以下步骤：
1. 询问本周完成的主要工作
2. 询问下周计划
3. 生成结构化周报
4. 保存为 Markdown 文件
```

> **自进化 Agent 直接可用**：技能用 Markdown 定义，按需加载，与基础 Agent 上下文隔离。自进化 Agent 可用此模式动态注册新技能。

#### 2.7 关键实现细节（含代码片段）

**LangChain 层：10 行跑通第一个 Agent**

```python
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain.agents import create_react_agent

@tool
def calculate(expression: str) -> str:
    """计算数学表达式，例如 '2 + 3' 或 '100 * 0.85'"""
    try:
        result = eval(expression)
        return f"计算结果: {result}"
    except Exception as e:
        return f"计算错误: {e}"

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
agent = create_react_agent(llm, tools=[calculate])
response = agent.invoke({
    "messages": [{"role": "user", "content": "帮我算一下 15% 的税后 8500 是多少"}]
})
print(response["messages"][-1].content)
```

**LangGraph 层：有状态的研究 Agent（完整工作流）**

```python
from typing import TypedDict, Annotated
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

# 1. 定义状态
class ResearchState(TypedDict):
    messages: Annotated[list, add_messages]  # 消息历史
    research_results: str                    # 研究结果
    report_ready: bool                       # 报告是否就绪

# 2. 定义节点
llm = ChatOpenAI(model="gpt-4o-mini")

def research_node(state: ResearchState):
    messages = state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response], "research_results": response.content}

def write_report_node(state: ResearchState):
    prompt = f"基于以下研究结果，写一份报告:\n\n{state['research_results']}"
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"messages": [response], "report_ready": True}

# 3. 定义条件路由
def should_continue(state: ResearchState):
    if "写报告" in state["messages"][-1].content if state["messages"] else "":
        return "write_report"
    return "research"

# 4. 构建图
graph = StateGraph(ResearchState)
graph.add_node("research", research_node)
graph.add_node("write_report", write_report_node)
graph.add_edge(START, "research")
graph.add_conditional_edges("research", should_continue)
graph.add_edge("write_report", END)

# 5. 编译并运行
app = graph.compile()
result = app.invoke({
    "messages": [HumanMessage(content="帮我研究一下 2026 年 AI Agent 的发展趋势，然后写一份报告")],
    "research_results": "",
    "report_ready": False
})
```

**LangGraph 层：带检查点和流式输出的 Agent**

```python
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

# 带检查点的版本（可恢复）
agent_with_memory = create_react_agent(
    model=ChatOpenAI(model="gpt-4o-mini"),
    tools=[calculate, search_web],
    checkpointer=MemorySaver()
)

# 流式输出
for chunk in agent.stream(
    {"messages": [HumanMessage(content="搜索 LangChain 的最新版本号")]},
    stream_mode="values"
):
    if chunk["messages"]:
        chunk["messages"][-1].pretty_print()
```

#### 2.8 与其他模块的依赖关系

```
LangChain（底层能力：LLM封装 + Tool定义）
    ↑ 依赖
LangGraph（编排：StateGraph + 条件路由 + 检查点）
    ↑ 依赖
DeerFlow（运行时：前端 + API + 沙箱 + 技能 + 记忆 + 子Agent）
```

- LangGraph 的 `create_react_agent` 依赖 LangChain 的 `ChatOpenAI` 和 `@tool`
- DeerFlow 的 Lead Agent 本质是一个 LangGraph 构建的复杂图
- DeerFlow 技能系统与基础 Agent 上下文隔离，通过按需加载机制挂载
- DeerFlow 沙箱分本地沙箱（开发）和 Docker 沙箱（生产）

#### 2.9 DeerFlow 与竞品对比（自进化 Agent 选型参考）

| 对比维度 | DeerFlow | Dify / Coze |
|----------|----------|-------------|
| 定位 | Agent 运行时（开发者向） | Agent 搭建平台（产品向） |
| 目标用户 | 工程师 | 产品经理 / 运营 |
| 定制深度 | 源码级定制 | 配置级定制 |
| 代码控制力 | 完全可控 | 有限 |
| 适合场景 | 需要深度定制的 Agent 平台 | 快速搭建不需要写代码的 Agent |

---

### 📄 文章10：写个 Markdown 就叫开发 Agent？三种 Agent 开发方式，你在哪一层？

#### 2.10 能力层级划分与判断标准

**LangChain 官方纵向分层（抽象层级）：**

| 层级 | 术语 | 写多少代码 | 核心价值 |
|------|------|-----------|----------|
| Harness | 开箱即用的 Agent 运行环境 | 零或极少 | 默认行为已经足够好 |
| Runtime | Agent 执行的基础设施 | 中等 | 持久化、检查点、状态管理 |
| Framework | 构建 Agent 的抽象组件 | 多 | LLM 封装、工具、提示词模板 |

**文章提出的横向分层（投入产出视角）——更实用：**

| Tier | 名称 | 投入 | 产出 | 判断标准 |
|------|------|------|------|----------|
| **Tier 1** | 配置即用 | 写 Markdown 配置文件，零代码 | 让现成 Harness 懂你的项目规则 | "默认行为已经够用，我只需要告诉它我的规则" |
| **Tier 2** | 扩展定制 | 少量代码（TS/Python），在现成 Harness 上加扩展 | 接内部系统、加自定义工具、搭简单 Web 界面 | "Harness 够用但缺几个能力，我加几个插件就行" |
| **Tier 3** | 深度构建 | 大量代码（300+行状态机），基于 Framework/Runtime 从头搭建 | 企业级 Agent 平台：多 Agent 编排、状态管理、生产部署 | "我需要的不是助手，是一个 Agent 平台" |

> **判断你处于哪个 Tier 的，不是你选了什么工具，而是你投入了多少研发。**

#### 2.11 各 Tier 的代表工具与配置方式

| Tier | 工具 | 配置方式 |
|------|------|----------|
| Tier 1 | Claude Code | `CLAUDE.md` + `.claude/` 目录 |
| Tier 1 | Codex (OpenAI) | `AGENTS.md` + 配置文件 |
| Tier 1 | OpenClaw | `AGENTS.md` / `SOUL.md` / `MEMORY.md` |
| Tier 2 | pi-cli + extensions | 少量 TS 扩展 |
| Tier 2 | Claude Code + MCP Servers | 少量 Python/TS |
| Tier 2 | DeerFlow 配置定制 | 零代码改配置 |
| Tier 3 | LangChain | Python/JS 组件库 |
| Tier 3 | LangGraph | Python/JS 状态机+执行引擎 |
| Tier 3 | DeerFlow 2.0 | Python 完整运行时 |
| Tier 3 | CrewAI / AutoGen | Python 多 Agent 协作 |

#### 2.12 可复用的设计模式 / 代码模式

**模式9：Tier 1 — CLAUDE.md 项目指令配置**

```markdown
# Project Instructions
- 使用 TypeScript 严格模式
- 提交前必须运行 `npm run check`
- 不要直接修改 production 分支
- 测试覆盖率不低于 80%
```

**模式10：Tier 1 — 自定义斜杠命令（.claude/commands/）**

```markdown
# review.md
审查当前 git diff 中的代码变更，关注：
1. 类型安全问题
2. 潜在的空指针异常
3. 是否有未处理的边界情况
输出格式：按严重程度排序的问题列表
```

**模式11：Tier 2 — MCP Server 扩展能力**

```python
from mcp.server import Server

server = Server("internal-tools")

@server.tool("query-jira")
async def query_jira(ticket: str):
    """查询 Jira 工单状态"""
    return await jira_api.get(ticket)

@server.tool("send-dingtalk")
async def send_dingtalk(message: str, chat_id: str):
    """发送钉钉消息"""
    return await dingtalk_api.send(message, chat_id)
```

接入配置：
```json
// .claude/mcp.json
{
  "servers": {
    "internal-tools": {
      "command": "python",
      "args": ["mcp_server.py"]
    }
  }
}
```

**模式12：Tier 2 — DeerFlow 配置级定制（不改源码）**

```yaml
# config.yaml
model:
  provider: deepseek
  name: deepseek-chat

tools:
  - group: built-in        # 内置工具
  - group: community       # 社区工具
  - mcp:
      server: internal-db   # MCP 工具
      command: python
      args: ["db_mcp.py"]

skills:
  - name: code-review      # 加载代码审查技能
  - name: test-gen         # 加载测试生成技能
```

**模式13：Tier 3 — LangGraph 条件路由状态机**

```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class AgentState(TypedDict):
    messages: list
    next_action: str
    results: list

def plan_node(state: AgentState) -> AgentState:
    response = llm.invoke("分析任务，制定计划")
    state["next_action"] = response.content
    return state

def execute_node(state: AgentState) -> AgentState:
    result = search_database.invoke(state["next_action"])
    state["results"].append(result)
    return state

def should_continue(state: AgentState) -> str:
    if len(state["results"]) < 3:
        return "plan"
    return END

workflow = StateGraph(AgentState)
workflow.add_node("plan", plan_node)
workflow.add_node("execute", execute_node)
workflow.set_entry_point("plan")
workflow.add_edge("plan", "execute")
workflow.add_conditional_edges("execute", should_continue)

app = workflow.compile()
result = app.invoke({"messages": [], "results": []})
```

**模式14：Tier 3 — DeerFlow 自定义中间件（记忆注入）**

```python
class MemoryInjectionMiddleware:
    async def before_llm_call(self, state):
        memories = await memory_store.search(state["messages"][-1])
        state["messages"].insert(0, {
            "role": "system",
            "content": f"相关记忆: {memories}"
        })
        return state
```

**模式15：Tier 3 — DeerFlow 自定义子 Agent**

```python
class ResearchSubAgent:
    name = "researcher"
    system_prompt = "你负责信息检索和整理"
    tools = [web_search, read_url]
```

#### 2.13 与其他模块的依赖关系

- Tier 1 依赖 Harness 提供的配置约定（CLAUDE.md / AGENTS.md / SOUL.md）
- Tier 2 的 MCP Server 通过标准协议与任何支持 MCP 的 Harness 通信，解耦
- Tier 2 的 DeerFlow 配置定制依赖 DeerFlow 的 config.yaml 约定
- Tier 3 的 LangGraph 状态机依赖 LangChain 的 LLM 封装和 Tool 定义
- Tier 3 的 DeerFlow 自定义中间件通过 `before_llm_call` / `after_llm_call` 钩入循环

---

## 三、三大框架设计哲学差异与适用场景

### 3.1 设计哲学对比

| 维度 | LangChain | LangGraph | DeerFlow |
|------|-----------|-----------|----------|
| **核心隐喻** | 工具箱（组件库） | 图（状态机） | 运行时（引擎） |
| **设计哲学** | 提供构建 Agent 的抽象组件 | 提供对 Agent 流程的完全控制权 | 把工作流包装成可运行的服务 |
| **抽象层级** | Framework | Runtime | Harness |
| **核心问题** | "怎么和 LLM 对话、怎么定义工具" | "怎么编排复杂工作流、怎么管理状态" | "怎么让 Agent 真正跑起来、怎么部署上线" |
| **扩展机制** | LCEL（LangChain Expression Language） | StateGraph + 条件边 + 检查点 | 中间件 + 技能系统 + 子 Agent |
| **演进方向** | 不断做减法，收敛为 `create_agent` | 成为 Agent 编排的官方推荐方案 | 在 LangGraph 之上构建完整工程化能力 |

### 3.2 适用场景

| 场景 | 推荐框架 | 理由 |
|------|----------|------|
| 快速原型：10行代码跑通一个 Agent | LangChain `create_react_agent` | 最简入口，快速验证想法 |
| 需要条件分支、并行执行、人机交互 | LangGraph `StateGraph` | 图模型天然支持复杂控制流 |
| 需要检查点、状态回滚、流式输出 | LangGraph + `MemorySaver` | 内置 checkpointer 和 stream |
| 需要前端界面、API 网关、沙箱执行 | DeerFlow | 开箱即用的完整运行时 |
| 需要多 Agent 协调、子任务委派 | DeerFlow `SubAgentMiddleware` | 内置子 Agent 自动协调 |
| 需要跨会话记忆、上下文自动压缩 | DeerFlow 中间件 | `MemoryMiddleware` + `SummarizationMiddleware` |
| 需要按需加载领域能力 | DeerFlow 技能系统 | SKILL.md 定义，动态挂载 |
| 需要源码级深度定制 | DeerFlow（源码可改） | 完全可控，不像 Dify/Coze 受限配置 |
| 快速搭建不写代码 | Dify / Coze | 拖拽式，产品向 |

### 3.3 三框架的递进关系（一句话总结）

> **LangChain 让 LLM 能调用工具 → LangGraph 用图编排复杂工作流 → DeerFlow 把工作流包装成可运行的服务**

---

## 四、自进化 Agent 项目可直接复用的实操知识

### 4.1 架构决策清单

1. **Agent 核心定义**：Agent = Model + Harness，Harness = Prompt + Tools + Middleware + State
2. **循环不变量**：所有 Agent 的核心都是 ReAct 循环（Thought → Action → Observation → ...），框架只负责把循环跑起来、把挂钩留给你
3. **中间件优于硬编码**：每个关注点（容错、压缩、审批、记忆）独立为中间件，自由组合——这是 v1.0 最核心的设计决策
4. **图优于循环**：用 StateGraph 而非 while 循环编排工作流，获得条件分支、并行、检查点、回滚能力
5. **技能按需加载**：领域能力用 SKILL.md 定义，动态挂载，不污染基础上下文
6. **子 Agent 委派**：复杂任务拆分为 Lead Agent + 多个专注子 Agent 并行执行

### 4.2 生产级 Agent 最小完整配置模板

```python
agent = create_agent(
    model="provider:model-name",
    tools=[tool1, tool2, tool3],
    system_prompt="...",
    middleware=[
        # 上下文管理
        SummarizationMiddleware(model="...", trigger={"tokens": 10000}),
        # 文件系统
        FilesystemMiddleware(backend=StateBackend()),
        # 子 Agent 委派
        SubAgentMiddleware(backend=StateBackend(),
            subagents=[{"name": "researcher", "tools": [search]}]),
        # 容错
        ModelRetryMiddleware(max_retries=3),
        ToolRetryMiddleware(max_retries=2),
        # 人工审批
        HumanInTheLoopMiddleware(interrupt_on={"write_file": True}),
    ],
)
```

### 4.3 状态管理工作流模板

```python
# 1. 用 TypedDict 定义状态
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    results: list
    next_action: str

# 2. 每个节点只关心输入输出，互不耦合
def node_func(state: AgentState) -> AgentState:
    ...

# 3. 用条件边控制流向
def router(state: AgentState) -> str:
    if condition:
        return "next_node"
    return END

# 4. 编译后获得可回滚、可流式输出的执行器
graph = StateGraph(AgentState)
graph.add_node("node", node_func)
graph.add_conditional_edges("node", router)
app = graph.compile(checkpointer=MemorySaver())
```

### 4.4 技能系统模板

```markdown
---
name: skill-name
description: 一句话描述
category: domain
---
# 技能标题
## 指令
当用户请求 X 时，按以下步骤：
1. 步骤一
2. 步骤二
3. 输出格式
```

### 4.5 中间件开发模板

```python
class CustomMiddleware:
    async def before_llm_call(self, state):
        # 在 LLM 调用前注入/修改上下文
        return state

    async def after_llm_call(self, state):
        # 在 LLM 调用后处理输出
        return state
```

### 4.6 能力层级判断标准（自进化 Agent 选型用）

| 你的需求 | 对应 Tier | 推荐路径 |
|----------|-----------|----------|
| 只想配置项目规则，让 AI 懂你的项目 | Tier 1 | 写 CLAUDE.md / AGENTS.md / SOUL.md |
| 想接内部系统、加几个自定义工具 | Tier 2 | 写 MCP Server 或 DeerFlow config.yaml |
| 需要多 Agent 编排、状态管理、生产部署 | Tier 3 | LangChain 造零件 → LangGraph 画流程 → DeerFlow 搭运行时 |
| 需要自进化能力（动态技能加载、子 Agent 委派、记忆注入） | Tier 3 | DeerFlow 中间件 + 技能系统 + 子 Agent |

---

## 五、关键经验总结

1. **Agent 的本质是循环**：不是单次调用，而是"思考→行动→观察"直到任务完成。所有框架差异都在于"怎么管理这个循环"。

2. **框架演进趋势是做减法**：LangChain 从"什么都包"收敛为"模型循环+工具+提示词+中间件挂钩"的 Harness。自进化 Agent 设计也应遵循"最小但完整"原则。

3. **中间件是 Harness 的灵魂**：统一了所有扩展机制。自进化 Agent 的"自进化"能力（学习、记忆、反思）应该实现为中间件。

4. **图模型是复杂 Agent 的必选**：当 Agent 需要条件分支、并行执行、状态回滚时，StateGraph 是唯一可靠的选择。

5. **技能按需加载是上下文管理的关键**：不把所有能力塞进 system prompt，而是用 SKILL.md 定义、动态挂载。自进化 Agent 可以在运行时生成新技能。

6. **子 Agent 委派是规模化的核心**：Lead Agent 负责规划协调，子 Agent 负责专注执行。自进化 Agent 的"分工"能力依赖此模式。

7. **MCP 是连接外部能力的标准协议**：通过 MCP Server 将内部系统暴露给任何 Agent，实现解耦。自进化 Agent 的"工具自发现"可通过 MCP 实现。

8. **投入决定层级，不是工具决定层级**：判断你在哪个 Tier，看的是你投入了多少研发，而不是你选了什么工具。
