# Agent架构系列文章技能提炼（5-7）

> 来源：公众号「架构师带你玩转AI」系列，作者 AllenTang
> 覆盖篇目：第五篇（技能系统设计）、第六篇（LangChain 复刻 Claude Code）、第七篇（Deerflow 复刻 Claude Code）

---

## 一、第五篇：技能系统设计

### 1.1 核心架构决策及理由

| 决策 | 选择 | 理由 |
|------|------|------|
| 技能载体 | Markdown 文件夹（SKILL.md + 附件） | 知识的供给端不只有程序员——运维、客服、财务都懂各自流程。写技能只需写 markdown，供给端是所有懂行的人；markdown 改完即生效，进 git 就有版本历史，知识更新成本最低 |
| 加载策略 | 渐进式披露（Progressive Disclosure） | 全量注入有两层成本：①空间成本（100个技能×2000 token=20万 token，未开工已塞满）；②注意力成本（目录越长，模型选对技能越难）。目录模式同样技能库仅占~3000 token |
| 选中依据 | 仅靠 description 一行 | 模型只看 description 决定用哪个技能。正文再好、description 没写好就死在角落；写得太宽泛又被乱触发。**自然语言描述就是接口契约** |

### 1.2 可复用的设计模式

**模式一：技能 = 文件夹 + SKILL.md**

```text
skills/release-checklist/
├── SKILL.md          # frontmatter(name+description) + 指令正文
├── scripts/          # 配套脚本，按需读取
└── references/       # 参考材料，按需读取
```

```markdown
---
name: release-checklist
description: 发版前预检：跑测试、核对变更日志、确认分支状态。用户提到"发版""上线""release"时使用。
---
你是发版守门员。按以下步骤预检：
1. 跑全量测试。
2. 核对 CHANGELOG：每个改动都要有对应条目。
3. 确认分支干净、已同步主干。
判断点：
- 测试失败但只是网络类偶发错误 → 重试一次，仍失败再上报。
- CHANGELOG 缺条目 → 从 git log 补齐，不要放过。
- 任何一步拿不准 → 停下来问人，不要猜。
```

**模式二：渐进式披露三阶段**

1. **启动时只挂目录**：所有技能的 name + description 拼成清单，注入 system prompt。正文一个字不加载。
2. **按需读正文**：模型调用 Skill 工具，传入技能名，完整指令此时才进上下文。
3. **按需取附件**：正文中提到脚本/模板，模型用普通文件工具读取，附件是最后一层。

**模式三：技能编排工具**

技能不提供原子动作（那是工具的事），技能提供**把动作组合成流程的经验**：先做什么、后做什么、岔路口怎么选。技能落地执行时，由模型依次调用 bash、write_file、git 等工具完成。Agent 缺了工具什么都做不了，缺了技能则什么都做不专业。

**模式四：description 写法规范**

好的 description 包含两半：
- **做什么**（给模型匹配任务用）
- **什么时候用**（给模型触发时机用）

```text
坏：description: 发版助手
好：description: 发版前预检：跑测试、核对变更日志、确认分支状态。用户提到"发版""上线""release"时使用。
```

### 1.3 关键实现代码

**skill-loader.ts — 发现与解析技能文件夹**

```typescript
interface SkillDefinition {
  name: string;
  description: string; // 进目录的那一行，决定技能何时被选中
  body: string;        // 完整指令，按需才加载
  dir: string;         // 技能文件夹路径，附件从这里取
}

function loadSkills(skillsDir: string): Map<string, SkillDefinition> {
  const skills = new Map();
  for (const dir of fs.readdirSync(skillsDir)) {
    const file = path.join(skillsDir, dir, 'SKILL.md');
    if (!fs.existsSync(file)) continue;

    const [, frontmatter, body] = fs.readFileSync(file, 'utf-8')
      .match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/)!;
    const meta = parseYaml(frontmatter);
    skills.set(meta.name, { name: meta.name, description: meta.description, body, dir });
  }
  return skills;
}
```

**skill-menu.ts — 目录组装（注入 system prompt）**

```typescript
// 启动时注入 system prompt 的就是这一段——一百个技能也只占一百行
function buildSkillMenu(skills: Map<string, SkillDefinition>): string {
  const lines = [...skills.values()].map(s => `- ${s.name}：${s.description}`);
  return `可用技能：\n${lines.join('\n')}\n需要时调用 skill 工具，传入技能名，获取完整指南。`;
}
```

**skill-tool.ts — Skill 工具（按需取正文）**

```typescript
function createSkillTool(skills: Map<string, SkillDefinition>): AgentTool {
  return {
    name: 'skill',
    description: '按名字加载一个技能的完整指南。技能清单见系统提示中的"可用技能"。',
    parameters: { name: { type: 'string' } },
    async execute(_id, { name }) {
      const skill = skills.get(name);
      if (!skill) return { content: `未知技能：${name}` };
      // 正文 + 附件清单。附件本身不进上下文，要用时模型自己用文件工具读
      const files = fs.readdirSync(skill.dir).filter(f => f !== 'SKILL.md');
      const fileList = files.length ? `\n\n附件（按需读取）：\n${files.join('\n')}` : '';
      return { content: skill.body + fileList };
    },
  };
}
```

**使用示例**

```typescript
const skills = loadSkills('./skills');
systemPrompt += '\n\n' + buildSkillMenu(skills); // 目录上墙
toolRegistry.set('skill', createSkillTool(skills)); // 取阅入口

await agentLoop.run('准备发个版，先帮我预检一下', sessionId);

// 模型的执行流：
// 1. 扫目录，"发版"命中 release-checklist 的 description
// 2. 调 skill 工具取回完整指南（正文这时才进上下文）
// 3. 按指南跑：bash 跑测试 → 发现一个网络类失败 → 命中"判断点"，重试一次
// 4. write_file 补齐 CHANGELOG → 汇报预检结果
```

### 1.4 与其他模块的依赖关系

五个子系统的依赖关系（前五篇总结）：

```
记忆 ──┐
       ├──→ 循环 ←── 协作（子 Agent = 新循环）
工具 ──┘       ↑
               │
              技能（目录注入上下文，正文按需进场，最终仍由工具落地）
```

- **记忆和工具**在最底层，相互独立
- **循环**架在两者之上，组装成每一轮推理
- **协作**是循环的复用（子 Agent 就是一个新循环）
- **技能**是循环的给养（目录注入上下文，正文按需进场，最终仍由工具落地）
- 技能与工具的分工：工具提供原子动作，技能提供编排经验（先做什么、后做什么、岔路口怎么选）

---

## 二、第六篇：用 LangChain 复刻 Claude Code

### 2.1 核心架构决策及理由

| 决策 | 选择 | 理由 |
|------|------|------|
| 架构形态 | 循环 + 可插拔中间件 | 各中间件只管一件事，要什么装什么。压缩、审批、重试都是独立中间件，不侵入核心循环 |
| 子 Agent 载体 | 数据（字典/配置），不是代码 | 新增子 Agent 不需要改代码、不需要重新部署，加一条配置就行。description 字段是模型"派谁去"的唯一依据 |
| 上下文卸载 | 虚拟文件系统（FilesystemMiddleware） | 中间产物写进文件，不堆在对话历史里。子 Agent 是"把资料挪到别的桌子上"，虚拟文件是"把资料挪到抽屉里" |
| 记忆分层 | CompositeBackend 路径路由 | 临时草稿放会话状态、用户偏好跨会话长存、项目文件直通磁盘——分层加载，各归其位 |
| 权限控制 | approve / edit / reject 三档 | 人可以批准、可以改完再批、可以驳回，不是一刀切 |

### 2.2 可复用的设计模式

**模式一：一行代码组装 Claude Code 式 Agent**

```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[read_file, write_file, edit_file, bash, grep, glob],
    system_prompt="You are an expert coding agent...",
)

# create_deep_agent 展开后等价于：
agent = create_agent(
    model="anthropic:claude-sonnet-4-6",
    tools=[read_file, write_file, edit_file, bash, grep, glob],
    system_prompt="You are an expert coding agent...",
    middleware=[
        TodoListMiddleware(),      # 任务清单
        FilesystemMiddleware(),    # 虚拟文件系统
        SubAgentMiddleware(),      # 子 Agent
    ],
)
```

**模式二：TodoListMiddleware — 计划外化**

自动给 Agent 加一个 `write_todos` 工具：做复杂任务前先写待办清单，做完一项勾掉一项。清单写在上下文里，是模型给自己做的备忘，防止长任务跑偏。对应 Claude Code 的 TodoWrite。

**模式三：FilesystemMiddleware — 上下文卸载**

自动加一套虚拟文件系统（write_file / read_file 等），中间产物写进文件，不堆在对话历史里。

**模式四：SubAgentMiddleware — 子 Agent 即配置**

```python
explore_subagent = {
    "name": "explorer",
    "description": "Explore the codebase to find relevant files and code patterns.",
    "system_prompt": "You are a code exploration expert. Use grep and glob...",
    "tools": [grep, glob, read_file],
    "model": "anthropic:claude-haiku-4-5",  # 便宜任务用便宜模型
}
```

**模式五：CompositeBackend — 记忆分层路由**

```python
CompositeBackend(
    default=StateBackend(runtime),                       # 默认：临时文件，跟着会话走
    routes={
        "/memories/": StoreBackend(runtime, store=store), # 跨会话持久存储
        "/project/": FilesystemBackend(root_dir="./project"), # 真实磁盘
    },
)
```

### 2.3 关键实现细节

- **三个默认中间件**：TodoListMiddleware（计划外化）、FilesystemMiddleware（上下文卸载）、SubAgentMiddleware（子 Agent 派发）
- **可选中间件**：审批中间件（approve/edit/reject 三档）、checkpointer（状态持久化，同 thread_id 可续聊）
- **后端路由**：临时草稿 → StateBackend；用户偏好 → StoreBackend 跨会话；项目文件 → FilesystemBackend 直通磁盘。等价于 Claude Code 的 CLAUDE.md 分层加载

### 2.4 与其他模块的依赖关系

```
create_agent (核心循环)
    ↑
    ├── TodoListMiddleware      ← 依赖：注入 write_todos 工具
    ├── FilesystemMiddleware     ← 依赖：注入虚拟文件系统工具集
    ├── SubAgentMiddleware       ← 依赖：注入 task 工具 + 子 Agent 配置
    ├── 审批中间件（可选）        ← 依赖：工具执行拦截
    └── checkpointer             ← 依赖：状态序列化/反序列化
```

### 2.5 框架未标准化的差异点

LangChain 生态已标准化的基础层：循环、压缩、子 Agent、权限、记忆（可插拔中间件）。

尚未标准化的两处：
1. **渐进式披露的技能生态** — 生态问题，远未定论
2. **运行时自动评估的安全深度** — 信任问题，远未定论

> 这两点是接下来几年最值得下注的方向。

---

## 三、第七篇：用 Deerflow 复刻 Claude Code

### 3.1 核心架构决策及理由

| 决策 | 选择 | 理由 |
|------|------|------|
| 框架定位 | Harness（运行时底座），不是 Framework（零件库） | Framework 给零件让用户自己写胶水；Harness 直接打包开箱即用的运行时，底座本身就是编排层 |
| 编排方式 | 涌现式循环（Lead Agent 循环），非固定流水线 | DeerFlow 1.0 是固定流水线（Coordinator→Planner→Researcher→Reporter），2.0 做通用底座时拆掉流水线换成循环——不硬编码工作流，模型临场决定 |
| 循环实现 | 跑在 LangGraph 状态图之上 | 看得见（图上点亮节点）、停得下（任意节点可中断）、续得上（每步存档）、分得出（子任务并行派发） |
| 长时任务看门人 | 三大基础设施：checkpoint + loop detection + clarification | 任务时长超过人的耐心时，工程设施必须接替人做看门人 |

### 3.2 可复用的设计模式

**模式一：Harness 底座组装**

```python
from langchain.agents import create_agent

agent = create_agent(
    model=make_model(),
    tools=[
        sandbox_tools(),      # 沙箱文件/命令工具
        mcp_tools(),          # MCP 外部系统工具
        task_tool(subagents=[general_purpose, bash, custom_agents]),  # 子 Agent 派发
    ],
    system_prompt=BASE_PROMPT,  # 基座提示词保持通用，专业能力由技能按需注入
    middleware=[
        SummarizationMiddleware(...),     # 历史压缩，排最前
        MemoryMiddleware(...),            # 跨会话记忆注入
        SubagentLimitMiddleware(max=3),   # 并行子 Agent 封顶
        LoopDetectionMiddleware(),        # 死循环检测
        ClarificationMiddleware(),        # 拿不准时正式询问用户，排最后
    ],
)
# 运行时挂 checkpoint：长任务可中断、可恢复
```

**模式二：中间件链排序原则**

```
收到消息
 → 中间件前处理（记忆注入、历史压缩等）
 → 模型推理（直接回答，或发起工具调用）
 → 工具执行（沙箱工具 / 外部工具 / task 工具派子 Agent）
 → 中间件后处理（生成标题等）
 → 循环，或输出最终响应
```

排序讲究：**压缩排最前**（先给上下文减负，后面所有处理都受益），**澄清排最后**（所有中间件处理完再决定要不要问人）。

**模式三：长时任务三大基础设施**

1. **状态图 + checkpoint**：每过一个节点存一次档，恢复就是读档接着走。进程崩了、人隔天回来都从断点继续。
2. **LoopDetectionMiddleware**：模型可能陷进死循环（同一工具反复调、无进展）。人在场时敲回车能打断；长任务人不在场，中间件自动检测、注入警告、强制跳出。
3. **ClarificationMiddleware**：拦截澄清请求，转成面向用户的结构化提问。人不在场不等于人不参与——参与点从"随时打断"变成"被正式询问"。

**模式四：技能加载含安全扫描**

```text
skills/data-analysis/
├── SKILL.md          # frontmatter(name/description) + 指令正文
├── scripts/          # 配套脚本，按需读取
└── references/       # 参考材料
```

加载流程：发现 → 解析 → **安全扫描** → 相关时注入上下文。

> 注意"安全扫描"这一步——技能是别人写的文本，注入前要先过安检，这是低门槛生态必须配的保险。（第五篇未提及此环节，DeerFlow 补上了）

**模式五：扩展全是配置和数据，不碰代码**

- 加技能：一个文件夹加一个 markdown 文件
- 加自定义 Agent：写一份 Agent 配置（名字、description、提示词、可用工具），自动进入 task 工具可选名单
- 接外部系统：配置里挂 MCP 服务器，外部工具进统一注册表，支持 OAuth 鉴权和按需懒加载

### 3.3 关键实现细节

**五大能力与前五篇的对应关系**

| DeerFlow 能力 | 对应篇章 | 实现要点 |
|--------------|---------|---------|
| 子 Agent | 第四篇 | task 工具派发，内置 general-purpose 和 bash 两个子 Agent，支持自定义，并行数由 SubagentLimitMiddleware 封顶 |
| 技能 | 第五篇 | 按需加载，基座保持通用（exactly when relevant and no further） |
| 记忆 | 第一篇 | MemoryMiddleware 会话开始注入持久记忆，会话结束后后台沉淀 |
| 工具与 MCP | 第二篇 | 沙箱工具、社区工具、MCP 工具、技能自带工具统一注册；MCP 是一等公民（OAuth、工具搜索、按需懒加载） |
| 沙箱 | 前五篇无 | 代码执行隔离环境，支持路径映射和自定义挂载，SandboxAuditMiddleware 做审计 |

### 3.4 与其他模块的依赖关系

```
LangGraph 状态图 (底座)
    ↑
    ├── Lead Agent (核心循环，涌现式编排)
    │     ├── 中间件链
    │     │     ├── SummarizationMiddleware   ← 压缩（排最前）
    │     │     ├── MemoryMiddleware          ← 记忆注入
    │     │     ├── SubagentLimitMiddleware   ← 子 Agent 并行封顶
    │     │     ├── LoopDetectionMiddleware   ← 死循环检测
    │     │     └── ClarificationMiddleware   ← 澄清询问（排最后）
    │     ├── 工具注册表
    │     │     ├── sandbox_tools             ← 沙箱（隔离执行）
    │     │     ├── mcp_tools                 ← MCP（外部系统标准协议）
    │     │     └── task_tool                 ← 子 Agent 派发
    │     └── checkpoint                      ← 长任务存档/恢复
    └── DeerFlow App (参考应用，建在底座之上)
```

---

## 四、LangChain 方案 vs Deerflow 方案复刻对比

### 4.1 架构差异

| 维度 | LangChain Deep Agents（第六篇） | DeerFlow 2.0（第七篇） |
|------|-------------------------------|----------------------|
| **定位** | 独立中间件层库（deepagents 包），给"长时编码/研究型 Agent"的方案 | Harness 运行时底座 + 参考应用，"构建和运营 Agent 系统的框架" |
| **底座** | create_agent + 中间件 | LangGraph 状态图 + LangChain，Lead Agent 循环 |
| **默认中间件** | 3 个：TodoList、Filesystem、SubAgent | 5+ 个：Summarization、Memory、SubagentLimit、LoopDetection、Clarification |
| **编排方式** | 涌现式循环 | 涌现式循环（2.0 从 1.0 固定流水线演进而来） |
| **长时任务** | checkpointer 做状态持久化 | 状态图 + checkpoint + LoopDetection + Clarification，系统级支持 |
| **子 Agent** | 字典配置，description 驱动派发 | 同样 task 工具 + description 驱动，额外有 SubagentLimit 封顶 |
| **技能** | 未标准化（差异点之一） | 已实现，含安全扫描环节 |
| **沙箱** | 未提及 | 一等公民：隔离代码执行、路径映射、自定义挂载、审计中间件 |
| **外部系统** | 未重点展开 | MCP 是一等公民：OAuth、工具搜索、按需懒加载 |
| **记忆分层** | CompositeBackend 路径路由（临时/跨会话/磁盘） | MemoryMiddleware 会话开始注入 + 会话结束后台沉淀 |
| **审批** | approve/edit/reject 三档中间件 | ClarificationMiddleware（结构化提问，面向长时无人值守场景） |

### 4.2 取舍权衡

**LangChain 方案的取舍**

- **优势**：轻量、简单，一行 `create_deep_agent` 出活。三个默认中间件覆盖核心场景，心智负担低。
- **取舍**：牺牲了长时任务的系统性支持。没有死循环检测、没有结构化澄清、没有沙箱隔离。适合有人盯着的交互式编码场景。
- **未覆盖**：技能生态（渐进式披露）和安全深度评估——明确指出这两处"远没有定论"。

**DeerFlow 方案的取舍**

- **优势**：系统级支持长时无人值守任务。状态图提供可观测性（看得见）、可中断性（停得下）、可恢复性（续得上）、可并行性（分得出）。三大看门人基础设施（checkpoint / loop detection / clarification）解决"人不在场"问题。
- **取舍**：更重、更复杂。从 1.0 的固定流水线（Coordinator→Planner→Researcher→Reporter）演进到 2.0 的涌现式循环，放弃了结构化流程的可预测性，换取了通用性。
- **新增能力**：沙箱（前五篇没有）、MCP 一等公民、技能安全扫描——填补了 Claude Code 源码拆解中未覆盖的盲区。

### 4.3 共识与收敛点

两个方案不约而同收敛到的设计（殊途同归 = 行业共识）：

1. **涌现式循环**：不硬编码工作流，模型临场决定调什么工具、派不派子 Agent
2. **子 Agent 是数据不是代码**：字典/配置定义，description 驱动选派，不改代码就能新增
3. **中间件可插拔**：行为由中间件组合，每一轮穿过中间件链
4. **自然语言描述即接口契约**：工具、子 Agent、技能都靠 description 被发现和选中——系列第四次确认这一设计
5. **上下文分层管理**：压缩、虚拟文件系统、记忆分层——核心思路都是别让主上下文被淹没

---

## 五、可直接用于自进化 Agent 项目开发的实操清单

### 5.1 技能系统实现清单（第五篇）

- [ ] 技能文件夹结构：`SKILL.md`（frontmatter + 正文）+ `scripts/` + `references/`
- [ ] `loadSkills()`：扫描目录、解析 frontmatter、构建 `Map<name, SkillDefinition>`
- [ ] `buildSkillMenu()`：拼接 name+description 清单，注入 system prompt（常驻）
- [ ] `createSkillTool()`：Skill 工具，按 name 返回正文 + 附件清单（按需）
- [ ] description 写法：两半结构——"做什么" + "什么时候用"
- [ ] 正文中写"判断点"：让模型临场决策（如"网络类偶发错误→重试一次"），而非硬编码逻辑

### 5.2 中间件架构实现清单（第六篇 + 第七篇）

- [ ] 核心循环：`create_agent(model, tools, system_prompt, middleware=[...])`
- [ ] TodoList 中间件：注入 `write_todos` 工具，计划外化
- [ ] Filesystem 中间件：虚拟文件系统，中间产物写文件不堆上下文
- [ ] SubAgent 中间件：task 工具 + 子 Agent 配置（name/description/system_prompt/tools/model）
- [ ] Summarization 中间件：历史压缩，**排中间件链最前**
- [ ] Memory 中间件：会话开始注入 + 会话结束后台沉淀
- [ ] SubagentLimit 中间件：并行子 Agent 封顶（如 max=3）
- [ ] LoopDetection 中间件：检测死循环，自动注入警告/强制跳出
- [ ] Clarification 中间件：拦截澄清请求转结构化提问，**排中间件链最后**
- [ ] Checkpointer：挂载状态图，长任务可中断可恢复

### 5.3 记忆分层路由清单（第六篇）

- [ ] CompositeBackend：default=StateBackend（临时，跟会话走）
- [ ] `/memories/` → StoreBackend（跨会话持久）
- [ ] `/project/` → FilesystemBackend（真实磁盘）

### 5.4 扩展能力清单（第七篇）

- [ ] 加技能：文件夹 + SKILL.md，加载流程含**安全扫描**（技能是别人写的文本，注入前先过安检）
- [ ] 加自定义 Agent：配置 name/description/system_prompt/tools，自动进 task 可选名单
- [ ] 接外部系统：挂 MCP 服务器，支持 OAuth + 按需懒加载
- [ ] 沙箱：隔离代码执行环境，路径映射 + 自定义挂载 + SandboxAuditMiddleware 审计

### 5.5 设计原则速查

| 原则 | 来源 | 要点 |
|------|------|------|
| 渐进式披露 | 第五篇 | 目录常驻 system prompt，正文按需取回，附件最后层 |
| 自然语言描述即接口契约 | 第五/六/七篇 | 工具、子 Agent、技能都靠 description 被发现——写描述是做 API 设计 |
| 子 Agent 是数据不是代码 | 第六/七篇 | 配置定义，不改代码不重新部署 |
| 行为由中间件组合 | 第六/七篇 | 每个中间件只管一件事，可插拔 |
| 压缩排最前、澄清排最后 | 第七篇 | 先减负再处理，处理完再问人 |
| 基座通用、专业能力按需注入 | 第七篇 | system_prompt 保持通用，技能/子 Agent 按需加载专业能力 |
| 长任务看门人三件套 | 第七篇 | checkpoint（看门状态）、loop detection（看门循环）、clarification（看门沟通） |
| 知识用 markdown 承载 | 第五篇 | 供给端是所有懂行的人，改完即生效，进 git 有版本历史 |

---

## 六、系列全篇依赖关系总览（1-7篇）

```
第一篇：记忆系统  ─────────────────────┐
第二篇：工具系统  ─────────────────────┤
                                       ├──→ 第三篇：Agent Loop（组装记忆+工具成每轮推理）
                                       │         ↑
                                       │    第四篇：多 Agent 协作（子 Agent = 新循环）
                                       │         ↑
                                       │    第五篇：技能系统（目录注入上下文，正文按需进场，工具落地）
                                       │
第六篇：LangChain 验证 ─── 殊途同归 ─── 第七篇：DeerFlow 验证
（循环+中间件，3个默认件）              （Harness底座，5+中间件，长时任务三件套）
```

**收敛共识**：循环、压缩、子 Agent、权限、记忆 → 已标准化为可插拔中间件，一行代码组装 Claude Code 式 Agent。

**未收敛方向**：①渐进式披露的技能生态（生态问题）②运行时自动评估的安全深度（信任问题）——接下来几年最值得下注。
