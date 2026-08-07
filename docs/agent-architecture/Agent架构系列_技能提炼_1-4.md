# Agent架构系列文章技能提炼（1-4）

> 来源：《万字长文拆解Agent 架构设计》系列（一~四），作者 AllenTang
> 提炼目标：提取可直接用于自进化Agent项目开发的实操知识

---

## 一、记忆系统设计（第一篇）

### 1.1 核心架构决策

| 决策 | 理由 |
|------|------|
| **固定层/条件层分离** | 固定层放最前，利用 Prompt Cache 缓存前缀——只付一次输入费用，后续命中缓存仅10%成本 |
| **路径即相关性（不用向量数据库）** | 用文件系统路径编码规则作用域（global → project → directory），零基础设施成本 |
| **约束→指令（自然语言驱动行为）** | 不直接截断上下文，而是把工程状态翻译成模型能理解的指令，让模型主动调整行为 |

### 1.2 可复用的设计模式

#### 模式1：三层 CLAUDE.md 分层加载
```
全局层 ~/.claude/CLAUDE.md     → 所有项目共享（如"我是全栈工程师"）
项目层 /project/CLAUDE.md      → 跟着仓库走（如"TypeScript strict mode"）
目录层 /project/src/api/CLAUDE.md → 跟着子目录走（如"这个模块用REST"）
```
**关键细节**：拼接时标注来源 `<!-- scope: filePath -->`，让模型判断冲突优先级——越靠近项目目录优先级越高。

#### 模式2：Token 预算三级阈值
```typescript
THRESHOLDS = {
    approaching: 0.70,  // 温和提示："Consider finishing current tasks first."
    critical: 0.85,     // 明确限制："Avoid reading large files."
    compacting: 0.90,   // 紧急压缩："Complete in-progress writes NOW."
}
```
**核心洞察**：`formatForInjection()` 返回的不是数字，而是模型能读懂的指令。这种"把约束翻译成指令"的模式可推广到：API限流→"减少调用频率"、内存用量→"避免处理大文件"、错误率→"更仔细验证输出"。

#### 模式3：XML 标签分隔语义段
```typescript
parts.push(`<identity>...</identity>`);
parts.push(`<project_rules>...</project_rules>`);
```
XML标签帮助模型识别不同段落的边界和语义角色，比纯文本分隔线有效。

#### 模式4：Skills 只注入索引（懒加载）
不注入 skill 完整定义，只给名字+描述。模型需要时才通过工具加载——和浏览器懒加载同一思路。

#### 模式5：情景记忆——对话压缩
```typescript
// 定期把旧消息压缩成摘要（用小模型如 claude-haiku）
对话轮次 1-10 → [LLM 压缩] → "用户重构了 LRU 缓存，使用双重链表方案"
对话轮次 11-20 → 保持原文（最新消息）
```
摘要由 LLM 生成而非简单截取。`importance` 评分用于淘汰低重要性记忆。

### 1.3 关键实现细节

**Token 估算（无需精确，方向即可）**：
```typescript
class TokenCounter {
    private readonly CJK_REGEX = /[一-鿿㐀-䶿豈-﫿]/g;
    count(text: string): number {
        const cjkChars = (text.match(this.CJK_REGEX) ?? []).length;
        const nonCjkChars = text.length - cjkChars;
        return Math.ceil(nonCjkChars / 4 + cjkChars / 1.5);
    }
}
```
英文约4字符/token，中文约1.5字符/token。接口只依赖 `count(text: string): number`，生产环境可换精确 tokenizer。

**消息裁剪策略**：从最新消息开始保留，往旧的丢弃（非 FIFO）。Agent 最需要的是最近的上下文。

### 1.4 与其他模块的依赖关系

- → **工具系统**：Skills 索引注入系统提示，完整 skill 通过工具调用加载
- → **Agent Loop**：`buildContext()` 是 Loop 每轮的第一步，输出 `{ systemPrompt, messages, budgetStatus }`
- → **历史压缩**：重要事实在压缩前应已写入记忆系统，压缩历史不会丢失关键约束

---

## 二、工具系统设计（第二篇）

### 2.1 核心架构决策

| 决策 | 理由 |
|------|------|
| **权限内聚进工具本身** | 工具自描述风险画像，不依赖外部配置表，避免配置错误导致安全事故 |
| **签名粒度是命令，不是工具名** | `bash:git status` 而非 `bash`，防止"始终允许"变成全量授权漏洞 |
| **分类器的信息边界是结构性的** | 不传入 `modelReasoning` 是程序级约束（字段根本不构造），而非提示词约束（可被绕过） |

### 2.2 可复用的设计模式

#### 模式1：三档权限分级
```typescript
type ToolPermission = 'auto' | 'confirm' | 'block';
// auto    → 只读/无副作用 → 自动执行
// confirm → 有副作用 → 需用户确认
// block   → 硬限制 → 默认拦截，不可被用户覆盖
```

#### 模式2：权限决策链
```
工具运行时 assessRisk() → 硬限制 block 检查 → 用户白名单检查 → 默认权限
```
```typescript
async decide(tool, input, context): Promise<Decision> {
    // 1. 工具自身的运行时风险评估（最了解自身风险）
    const runtime = await tool.assessRisk?.(input, context) ?? null;
    const effective = runtime ?? tool.defaultPermission;
    // 2. block 是硬限制
    if (effective === 'block') return 'block';
    // 3. 用户白名单（命令级签名）
    if (this.alwaysAllow.has(signature) || this.sessionAllow.has(signature)) return 'execute';
    // 4. 默认权限
    return effective === 'auto' ? 'execute' : 'confirm';
}
```

#### 模式3：运行时风险评估（assessRisk）
```typescript
// bash 工具根据具体命令动态调整权限
async assessRisk(input): Promise<ToolPermission | null> {
    const cmd = input.command;
    if (SAFE_PREFIXES.some(p => cmd.startsWith(p))) return 'auto';   // ls, cat, git status...
    if (DANGEROUS.some(p => cmd.includes(p))) return 'block';        // rm -rf /, mkfs...
    return null;  // 其他使用默认权限
}
```

#### 模式4：两阶段安全分类器
```
99%正常操作 → 第一阶段 Haiku 单token判断（<100ms）→ safe → 直接执行
1%可疑操作  → 第二阶段 Sonnet CoT推理（500-2000ms）→ suspicious/dangerous
```

#### 模式5：子 Agent 即工具（递归性）
```typescript
const agentTool: AgentTool = {
    name: 'agent',
    defaultPermission: 'confirm',  // 生成子Agent需确认
    async execute(input, context) {
        const subAgent = new AgentRunner({
            allowedTools: input.tools ?? [],  // 工具子集
            tokenBudget: context.tokenBudget, // 共享父Agent预算
        });
        return subAgent.run();
    },
};
```

### 2.3 关键实现细节

**命令级签名构建**：
```typescript
private buildSignature(toolName: string, input: unknown): string {
    if (toolName === 'bash' && typeof input === 'object') {
        const cmd = (input as { command?: string }).command ?? '';
        return `bash:${cmd}`;  // 粒度是具体命令
    }
    return toolName;
}
```

**结构性安全约束**：
```typescript
// 分类器输入——刻意不传入 modelReasoning / toolOutput / conversationHistory
interface ClassifierInput {
    userRequest: string;    // ✅
    toolName: string;       // ✅
    toolInput: unknown;     // ✅
    // ❌ modelReasoning: 防止模型"解释说服"分类器
    // ❌ toolOutput: 防止恶意输出影响判断
    // ❌ conversationHistory: 减少 Prompt Injection 攻击面
}
```

### 2.4 与其他模块的依赖关系

- ← **记忆系统**：工具定义注入系统提示（Skills 索引），token 预算从 BudgetManager 获取
- → **Agent Loop**：工具执行是 Loop 中的核心步骤，权限检查在每次工具调用前执行
- → **多Agent协作**：子Agent作为工具被调用，权限不递归放大（工具子集而非超集）

---

## 三、Agent Loop 设计（第三篇）

### 3.1 核心架构决策

| 决策 | 理由 |
|------|------|
| **上下文分层组装** | system prompt / tool defs / memory snapshot / messages 四层分离，稳定前缀命中缓存 |
| **主动分级压缩（非被动截断）** | 按消息年龄分档处理，信息损失摊薄到多轮而非集中断崖 |
| **显式预算终止（非依赖模型自判）** | 防止工具失败→重试→再失败的无限循环，预算耗尽带部分结果返回 |

### 3.2 可复用的设计模式

#### 模式1：上下文四层组装
```
┌─ systemPrompt（几乎不变 → 稳定命中 Prompt Cache）
├─ toolDefinitions（工具列表）
├─ memorySnapshot（按需检索，最近一条用户消息去查询）
└─ messages（每轮都变 → 正常计算）
```
```typescript
class ContextAssembler {
    async assemble(rawHistory, sessionId): Promise<AssembledContext> {
        const lastUserMsg = [...rawHistory].reverse().find(m => m.role === 'user');
        return {
            systemPrompt: STATIC_PROMPT,
            toolDefinitions: getToolDefs(),
            memorySnapshot: lastUserMsg
                ? await memoryStore.retrieveRelevant(lastUserMsg.content, sessionId) : '',
            messages: await compactor.compact(rawHistory),
        };
    }
}
```

#### 模式2：分级压缩策略
```
age ≤ 5轮   → 保留原文
age ≤ 15轮  → 丢弃工具输出，保留工具名
age ≤ 30轮  → 小模型摘要
age > 30轮  → 直接跳过
```
```typescript
for (const msg of history) {
    const age = totalTurns - turnIndexOf(msg);
    if (age <= 5) result.push(msg);
    else if (age <= 15) result.push(stripToolOutput(msg));
    else if (age <= 30) result.push(await summarize(msg));
    // age > 30: 直接跳过
}
```
**关键**：上下文长度曲线平滑——先增长后趋于饱和，而非"缓升→断崖"。

#### 模式3：三维预算终止
```typescript
interface LoopBudget {
    maxTurns: number;       // 最多工具调用轮数
    maxTokens: number;      // token总量上限
    maxWallClockMs: number; // 墙钟时间上限
}
```
- 预算检查放在循环顶部（不分散在循环中间），加新条件只改一处
- 预算耗尽返回文字（不抛异常），上层拿到可用的部分结果

#### 模式4：工具调用失败重试
```typescript
async function executeWithRetry(tool, input, ctx) {
    for (let i = 0; i <= 2; i++) {
        try { return await tool.execute(input, ctx); }
        catch (e) {
            if (i === 2) return `执行失败（重试2次）：${e.message}`;
        }
    }
}
```
错误信息作为工具结果反馈给模型，让模型决定重试/换方式/放弃。

#### 模式5：并行工具调用的部分失败隔离
```typescript
const settled = await Promise.allSettled(
    response.toolCalls.map(call => executeToolCall(call)),
);
```
用 `Promise.allSettled` 而非 `Promise.all`，隔离单个工具调用的失败。

### 3.3 关键实现细节

**Agent Loop 主体**：
```typescript
async run(userMessage: string): Promise {
    let history = [{ role: 'user', content: userMessage }];
    const tracker = new BudgetTracker(budget);
    while (true) {
        // ① 循环顶部统一检查预算
        const { exhausted, reason } = tracker.isExhausted();
        if (exhausted) return `[循环结束：${reason}]`;
        // ② 组装上下文，调用模型
        const context = await assembler.assemble(history, sessionId);
        const response = await llm.chat({ system: [...], messages: context.messages });
        tracker.recordTurn(response.usage.totalTokens);
        // ③ 自然终止：模型不再调用工具
        if (!response.toolCalls?.length) return response.content;
        // ④ 执行工具（经权限检查），结果追加历史
        const results = await Promise.allSettled(
            response.toolCalls.map(call => executeToolCall(call))
        );
        history.push(/* assistant + tool messages */);
    }
}
```

**流式解析优化**：识别出工具名后，在和模型生成参数并行的时间里做权限预检查。

### 3.4 与其他模块的依赖关系

- ← **记忆系统**：ContextAssembler 依赖 MemoryStore 做按需检索；HistoryCompactor 是压缩消费者
- ← **工具系统**：executeToolCall 内部调用 PermissionManager.decide() 做权限检查
- → **多Agent协作**：Loop 支持并发执行多个 task 工具调用（模型即调度器）

---

## 四、多 Agent 协作（第四篇）

### 4.1 核心架构决策

| 决策 | 理由 |
|------|------|
| **编排者/执行者工具集互补** | 编排者只有只读+派发工具，执行者有副作用工具但不能继续派子Agent，防止递归膨胀 |
| **上下文隔离（不共享历史）** | 子Agent在全新上下文中启动，父Agent的历史不传入——切分的不是能力，是上下文 |
| **只交回最后一条消息** | 子Agent中间过程留在自己的上下文里，父Agent桌上少了一万页资料，多了一页结论 |

**核心洞察**：多Agent协作的本质不是能力分工，而是上下文切分。子Agent不比主Agent多懂什么，它强的地方只是"桌子干净"——解决了"资料越多注意力越稀释"和"lost in the middle"问题。

### 4.2 可复用的设计模式

#### 模式1：编排者/执行者角色分离
```typescript
// 编排者：规划、分解、汇总
interface OrchestratorConfig {
    allowedTools: ['task', 'read_file', 'list_dir'];  // 只读 + 派发
    maxSubagents: number;
    subagentBudget: TokenBudget;
}
// 执行者：具体操作，不能再派子Agent
interface SubagentConfig {
    allowedTools: ['bash', 'write_file', 'read_file'];  // 有副作用
    canSpawnSubagents: false;  // 防止无限递归
    inheritedContext: string;  // 从父Agent继承的任务背景
}
```

#### 模式2：派发 = 一次普通工具调用
```typescript
const TaskTool: AgentTool = {
    name: 'task',
    description: '派发子Agent执行独立任务。适合需大量阅读材料、结论简短的广泛调研。',
    async execute(toolCallId, { subagent_type, prompt }) {
        const def = loadAgentDefinition(subagent_type);
        const finalMessage = await runSubagent(def, prompt, signal);
        return { content: finalMessage };  // 只返回最后一条消息
    },
};
```

#### 模式3：Markdown 文件定义子Agent
```markdown
<!-- .claude/agents/code-reviewer.md -->
---
name: code-reviewer
description: 审查代码改动，找bug和安全问题    # 给主Agent看，决定派谁
tools: [read_file, bash, grep]                # 给权限系统看，工具白名单
---
你是一个严格的代码审查员...                    # 给子Agent自己看，是system prompt
```
**三个字段各给不同读者**：description→主Agent模型、tools→权限系统、正文→子Agent。

#### 模式4：权限交集（不递归放大）
```typescript
// 子Agent的工具集 = 定义声明 ∩ 父Agent拥有
const allowedTools = deriveSubagentPermissions(
    [...parent.tools.keys()],  // 父Agent拥有的
    def.tools,                 // 定义声明的
);
```

#### 模式5：模型即调度器
不写专门的调度器——模型在一轮里发出多个 task 调用，Agent Loop 本来就并发执行。哪些并行、哪些串行，是模型的判断。

### 4.3 关键实现细节

**spawn.ts 派发核心**：
```typescript
async function spawnSubagent(parent, def, taskPrompt, signal) {
    // 1. 权限交集 + 默认去掉 task 工具
    const allowedTools = deriveSubagentPermissions([...parent.tools.keys()], def.tools);
    // 2. 全新上下文（没有传递父Agent历史的代码——没有就是设计）
    const loop = new AgentLoop(
        new ContextAssembler(def.systemPrompt, subagentTools, ...),
        allocateSubagentBudget(parent.budget),  // 预算只减不增
    );
    // 3. 返回值 = 最后一条消息
    const finalMessage = await loop.run(taskPrompt, crypto.randomUUID(), signal);
    return { status: 'success', output: finalMessage };
}
```

### 4.4 与其他模块的依赖关系

- ← **记忆系统**：子Agent有独立的MemoryStore，不与父Agent共享
- ← **工具系统**：子Agent走同样的 AgentTool 接口和权限管道
- ← **Agent Loop**：子Agent内部运行一个完整的Agent Loop，无特殊执行路径

---

## 五、跨文章对比与设计思路异同

### 5.1 统一的设计哲学

| 原则 | 在四篇中的体现 |
|------|--------------|
| **自然语言是最好的API** | 记忆→预算注入为自然语言指令；工具→description决定模型调用行为；多Agent→taskPrompt传递全部背景 |
| **结构性约束优于提示词约束** | 工具→分类器输入字段物理不传入；多Agent→子Agent不能获得task工具 |
| **分层/分级优于二值判断** | 记忆→三级Token阈值；工具→三档权限+运行时评估；Loop→按年龄分级压缩 |
| **内聚优于灵活** | 工具权限内聚在工具自身；子Agent定义是单一markdown文件 |

### 5.2 记忆系统 vs 工具系统的交互

| 维度 | 记忆系统 | 工具系统 |
|------|---------|---------|
| **核心职责** | 管理Agent看到什么 | 管理Agent能做什么 |
| **安全关注点** | 信息泄漏（上下文溢出） | 操作安全（权限控制） |
| **缓存策略** | Prompt Cache前缀优化 | Skills索引懒加载 |
| **交互点** | Skills索引注入system prompt | 工具执行消耗token预算 |
| **共同模式** | 都使用"约束→指令"模式：记忆用预算警告调整行为，工具用权限分级限制操作 |

### 5.3 Agent Loop 作为中枢的连接方式

```
记忆系统 ──buildContext()──→ Agent Loop ──executeToolCall()──→ 工具系统
                                ↑↓                              ↓
                           历史压缩/记忆提取              权限检查/执行
                                ↑
                           多Agent协作 ←── task工具调用（Loop并发执行）
```

- **Loop 对记忆**：每轮调用 `assembler.assemble()` 获取最新上下文；记忆提取在对话中持续进行
- **Loop 对工具**：每次工具调用经 `PermissionManager.decide()` 权限检查
- **Loop 对多Agent**：多个 task 工具调用可并发执行，模型决定并行策略

### 5.4 上下文管理的统一视角

四篇文章本质上都在解决同一个问题：**有限的上下文窗口如何高效利用**。

| 机制 | 解决什么问题 |
|------|------------|
| 固定层/条件层分离 | 不变的信息不要反复花钱 |
| Skills 只注入索引 | 按需加载，不预先占满 |
| 分级压缩 | 信息损失平滑摊薄 |
| 子Agent上下文隔离 | 把资料从父Agent桌上挪走，只留结论 |
| Token预算感知 | 让Agent主动调整行为以适应约束 |

---

## 六、可直接用于自进化Agent项目的实操清单

### 6.1 立即可以实现的

1. **Token 预算管理器**：三级阈值 + 自然语言注入，让 Agent 感知剩余预算并调整行为
2. **三档权限分级**：auto/confirm/block 内聚在工具定义中，配合命令级签名
3. **分级历史压缩**：按消息年龄分4档处理（原文→去输出→摘要→丢弃）
4. **三维预算终止**：maxTurns + maxTokens + maxWallClockMs，统一在循环顶部检查

### 6.2 需要基础设施支撑的

5. **分层规则加载**：基于文件路径的 CLAUDE.md 三层加载（需文件系统支持）
6. **情景记忆压缩**：用小模型定期压缩对话历史为摘要（需额外的 LLM 调用）
7. **两阶段安全分类器**：Haiku 快速过滤 + Sonnet 深度分析（需模型 API）
8. **子 Agent 即工具**：markdown 文件定义 + spawn 函数（需完整的 Agent Loop 实现）

### 6.3 长期演进方向

9. **向量语义检索**：补上路径相关性做不到的"这个任务需要什么历史经验"
10. **重要性评分**：消息级 importance 评分，用于记忆淘汰优先级
11. **流式权限预检查**：识别工具名后并行做权限检查，减少等待
12. **工具插件化**：文件系统自动发现 + 加载工具

---

## 七、核心代码模式速查

### 模式：约束→指令翻译器
```typescript
function formatConstraintAsInstruction(state: SystemState): string | null {
    if (state.level === 'normal') return null;
    return `<constraint status="${state.level}">${getAdvice(state.level)}</constraint>`;
}
// 可推广：限流→"减少调用"、内存→"避免大文件"、错误率→"仔细验证"
```

### 模式：权限决策链
```
runtimeRisk → block硬限制 → 白名单 → defaultPermission
```

### 模式：上下文隔离的"新桌子"
```
父Agent桌上：用户请求 + [子Agent1结论, 子Agent2结论, ...]  （每页薄）
子Agent桌上：任务描述 + 大量资料 → 独立处理 → 交回一页结论
```

### 模式：分级压缩
```typescript
const compressionPipeline = [
    { age: [0, 5],   action: 'keep' },
    { age: [6, 15],  action: 'stripToolOutput' },
    { age: [16, 30], action: 'summarize' },
    { age: [31, ∞],  action: 'drop' },
];
```

---

> 提炼日期：2026-07-15
> 文章原文来源：公众号"架构师带你玩转AI"，作者 AllenTang
