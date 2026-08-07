# Suyi — 自进化 Agent 技术方案

> 基于10篇Agent架构系列文章提炼 + 6篇自进化Agent文章 + Hermes三层记忆架构 + Claude Code技能系统设计

---

## 一、项目定位

**目标**：构建一个具备自进化能力的 Agent 框架，能从交互中学习、生成新技能、优化自身行为。

**Tier 定位**：Tier 3 深度构建（基于 Framework/Runtime 从头搭建）

**技术栈**：Python + numpy（无PyTorch/TensorFlow）

---

## 二、核心架构

```
┌─────────────────────────────────────────────────────┐
│                   Suyi                           │
│                                                      │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │ Memory      │  │ Agent Loop   │  │ Tools      │ │
│  │ (三层记忆)   │←→│ (ReAct循环)  │←→│ (权限分级)  │ │
│  └──────┬──────┘  └──────┬───────┘  └──────┬─────┘ │
│         │                │                  │       │
│         │          ┌─────┴──────┐          │       │
│         │          │ Middleware  │          │       │
│         │          │ (中间件链)  │          │       │
│         │          └─────┬──────┘          │       │
│         │                │                  │       │
│  ┌──────┴──────┐  ┌─────┴──────┐  ┌──────┴─────┐  │
│  │ Skills      │  │ Multi-Agent │  │ Evolution  │  │
│  │ (技能系统)   │  │ (多Agent)   │  │ (自进化)    │  │
│  └─────────────┘  └────────────┘  └────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

## 三、模块设计

### 3.1 Memory System（记忆系统）

**来源**：文章1(记忆系统) + 文章6(CompositeBackend) + 文章7(MemoryMiddleware) + Hermes三层架构

**三层记忆**：
- **Working Memory**：当前对话上下文，每轮动态组装
- **Episodic Memory**：会话日志，按时间衰减压缩
- **Semantic Memory**：跨会话知识库，TF-IDF + 关键词索引（纯numpy）

**记忆生命周期**：新鲜 → 巩固 → 压缩 → 遗忘
- 置信度 + 成功/失败计数 + 时间衰减实现梯度遗忘
- 高置信度记忆 → 自动巩固为长期知识
- 低置信度 + 长期未访问 → 压缩为摘要 → 最终遗忘

**Token预算三级阈值**：
```python
THRESHOLDS = {
    'approaching': 0.70,  # 温和提示
    'critical': 0.85,     # 明确限制
    'compacting': 0.90,   # 紧急压缩
}
```

**分级压缩策略**：
```
age ≤ 5轮   → 保留原文
age ≤ 15轮  → 丢弃工具输出，保留工具名
age ≤ 30轮  → 小模型摘要
age > 30轮  → 直接跳过
```

### 3.2 Tool System（工具系统）

**来源**：文章2(工具系统) + 文章5(技能落地)

**三档权限**：auto / confirm / block

**权限决策链**：
```
工具.assessRisk() → block硬限制 → 白名单 → defaultPermission
```

**命令级签名**：`bash:git status` 而非 `bash`

**运行时风险评估**：
```python
async def assess_risk(input_data) -> str | None:
    if is_safe(input_data): return 'auto'
    if is_dangerous(input_data): return 'block'
    return None  # 使用默认权限
```

### 3.3 Agent Loop（核心循环）

**来源**：文章3(Agent Loop) + 文章8(ReAct循环)

**四层上下文组装**：
```
systemPrompt（几乎不变 → 缓存友好）
toolDefinitions（工具列表）
memorySnapshot（按需检索）
messages（每轮变化）
```

**三维预算终止**：maxTurns + maxTokens + maxWallClockMs

**循环主体**：
```python
async def run(self, user_message):
    history = [{'role': 'user', 'content': user_message}]
    while True:
        # ① 预算检查
        if self.budget.is_exhausted(): return partial_result
        # ② 组装上下文
        context = await self.assembler.assemble(history)
        # ③ 调用模型
        response = await self.llm.chat(context)
        # ④ 自然终止
        if not response.tool_calls: return response.content
        # ⑤ 执行工具（权限检查 + 重试）
        results = await self.execute_tools(response.tool_calls)
        history.extend(results)
```

### 3.4 Skill System（技能系统）

**来源**：文章5(技能系统) + 文章7(安全扫描) + Claude Code技能设计

**渐进式披露三阶段**：
1. 启动时只挂目录（name + description → system prompt）
2. 按需读正文（Skill工具调用）
3. 按需取附件（文件工具读取）

**技能文件夹结构**：
```
skills/code-review/
├── SKILL.md          # frontmatter(name+description) + 指令正文
├── scripts/          # 配套脚本
└── references/       # 参考材料
```

**安全扫描**：技能是外部文本，注入前先过安检

**自进化关键**：运行时动态生成新技能 → 写入 skills/ 目录 → 自动注册

### 3.5 Multi-Agent（多Agent协作）

**来源**：文章4(多Agent) + 文章6(SubAgent) + 文章7(DeerFlow)

**编排者/执行者分离**：
- 编排者：只读 + 派发工具
- 执行者：有副作用工具，不能再派子Agent

**子Agent即配置**：
```python
subagent_config = {
    'name': 'researcher',
    'description': '搜索和整理信息',
    'system_prompt': '你是信息检索专家...',
    'tools': ['web_search', 'read_file'],
    'model': 'lightweight',  # 便宜任务用便宜模型
}
```

**权限交集**：子Agent工具集 = 定义声明 ∩ 父Agent拥有

**上下文隔离**：子Agent在全新上下文中启动，只交回最后一条消息

### 3.6 Middleware Chain（中间件链）

**来源**：文章6(中间件) + 文章7(DeerFlow中间件) + 文章8(v1.0中间件)

**排序原则**：压缩排最前 → 记忆注入 → 子Agent限制 → 死循环检测 → 澄清排最后

```python
middleware_chain = [
    SummarizationMiddleware(),      # 压缩（最前）
    MemoryMiddleware(),             # 记忆注入
    SubagentLimitMiddleware(max=3), # 子Agent封顶
    LoopDetectionMiddleware(),      # 死循环检测
    ClarificationMiddleware(),      # 澄清（最后）
]
```

**中间件接口**：
```python
class Middleware:
    async def before_llm_call(self, state): ...
    async def after_llm_call(self, state): ...
    async def before_tool_call(self, tool, input, state): ...
    async def after_tool_call(self, tool, input, output, state): ...
```

### 3.7 Evolution Engine（自进化引擎）

**来源**：Hermes 8 Loop + Mem0 v2生命周期 + 自进化方向探讨

**四步自进化闭环**：
1. **学习**：从交互中提取模式（成功路径、失败原因、用户偏好）
2. **生成**：基于学习结果生成新技能或优化现有技能
3. **评估**：使用置信度 + 成功率 + 用户反馈评估新技能
4. **部署**：高置信度技能自动注册，低置信度进入隔离观察

**学习数据源**：
- 对话历史中的工具调用模式
- 任务完成/失败统计
- 用户反馈（显式 + 隐式）
- 记忆检索命中率

**技能生成模板**：
```python
class SkillGenerator:
    async def generate(self, patterns):
        # 1. 从成功路径提取步骤
        # 2. 生成 SKILL.md 草稿
        # 3. 安全扫描
        # 4. 写入 skills/auto_generated/
        # 5. 注册到索引（标记 confidence=0.5）
```

---

## 四、项目结构

```
evoagent/
├── README.md
├── requirements.txt
├── evoagent/
│   ├── __init__.py
│   ├── core/                    # 核心循环
│   │   ├── loop.py              # Agent Loop
│   │   ├── context.py           # 上下文组装器
│   │   └── budget.py            # 预算管理器
│   ├── memory/                  # 记忆系统
│   │   ├── working.py           # 工作记忆
│   │   ├── episodic.py          # 情景记忆
│   │   ├── semantic.py          # 语义记忆（TF-IDF）
│   │   └── lifecycle.py         # 记忆生命周期
│   ├── tools/                   # 工具系统
│   │   ├── base.py              # 工具基类
│   │   ├── permissions.py       # 权限管理器
│   │   └── builtin.py           # 内置工具
│   ├── skills/                  # 技能系统
│   │   ├── loader.py            # 技能加载器
│   │   ├── menu.py              # 目录构建器
│   │   └── scanner.py           # 安全扫描器
│   ├── agents/                  # 多Agent
│   │   ├── orchestrator.py      # 编排者
│   │   ├── subagent.py          # 子Agent运行器
│   │   └── definitions/         # Agent定义(markdown)
│   ├── middleware/              # 中间件
│   │   ├── base.py              # 中间件基类
│   │   ├── summarization.py     # 压缩
│   │   ├── memory_inject.py     # 记忆注入
│   │   ├── loop_detection.py    # 死循环检测
│   │   └── clarification.py     # 澄清
│   ├── evolution/               # 自进化引擎
│   │   ├── learner.py           # 学习器
│   │   ├── skill_generator.py   # 技能生成器
│   │   ├── evaluator.py         # 评估器
│   │   └── feedback.py          # 反馈循环
│   └── utils/                   # 工具函数
│       ├── token_counter.py     # Token估算
│       └── text.py              # 文本处理
├── skills/                      # 技能库
│   └── auto_generated/          # 自进化生成的技能
├── tests/                       # 测试
│   ├── test_loop.py
│   ├── test_memory.py
│   ├── test_tools.py
│   ├── test_skills.py
│   └── test_evolution.py
└── examples/                    # 示例
    ├── basic_agent.py
    ├── multi_agent.py
    └── self_evolve.py
```

---

## 五、开发优先级

**Phase 1（核心框架）**：Memory + Loop + Tools + Token预算
**Phase 2（技能+中间件）**：Skill System + Middleware Chain
**Phase 3（多Agent）**：Orchestrator + SubAgent + 权限交集
**Phase 4（自进化）**：Learner + SkillGenerator + Evaluator + Feedback

---

## 六、设计原则速查

| 原则 | 来源 | 要点 |
|------|------|------|
| 自然语言即接口契约 | 5/6/7篇 | 工具/技能/子Agent都靠description被发现 |
| 结构性约束优于提示词 | 2篇 | 字段物理不传入，而非提示词约束 |
| 分层分级优于二值 | 1/2/3篇 | 三级阈值/三档权限/四级压缩 |
| 内聚优于灵活 | 2/4篇 | 权限内聚在工具，子Agent定义在markdown |
| 渐进式披露 | 5篇 | 目录常驻，正文按需，附件最后 |
| 压缩最前、澄清最后 | 7篇 | 先减负再处理，处理完再问人 |
| 基座通用、专业按需注入 | 7篇 | system_prompt通用，技能/子Agent按需加载 |
| 行为由中间件组合 | 6/7/8篇 | 每个中间件只管一件事，可插拔 |
