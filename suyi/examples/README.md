# Suyi 示例

本目录包含 Suyi 自进化 Agent 框架的使用示例。所有示例均使用 MockLLM，无需 API key 即可运行。

## 快速开始

```bash
# 在项目根目录下运行
cd /app/data/所有对话/主对话/suyi/

# 1. 基础对话
python examples/basic_chat.py

# 2. 工具使用
python examples/tool_use_demo.py

# 3. 多Agent协作
python examples/multi_agent_demo.py

# 4. 自进化
python examples/evolution_demo.py
```

## 示例说明

### 1. `basic_chat.py` — 基础对话

展示 Suyi Agent 的基本对话能力：

- **单轮对话**：使用 MockLLM 预设响应，演示 AgentLoop 的最简用法
- **多轮对话**：展示多轮对话流程和记忆系统的工作
- **记忆系统**：向语义记忆添加知识，使用 TF-IDF 检索相关内容

关键概念：
- `MockLLM` — 无需 API key 的测试用 LLM
- `LLMResponse.text()` — 创建纯文本响应（最终答案）
- `MemoryManager` — 三层记忆系统（working/episodic/semantic）
- `LoopResult` — AgentLoop 运行结果

### 2. `tool_use_demo.py` — 工具使用

展示 Agent 如何调用工具完成任务：

- **搜索工具**：Agent 先调用 search 工具，再基于结果回答
- **文件读取**：Agent 调用 read_file 工具读取文件内容
- **权限系统**：展示 auto/confirm/block 三种权限级别
  - `ls`, `cat` → auto（自动执行）
  - `rm file.txt` → confirm（需确认）
  - `rm -rf /` → block（禁止执行）
- **自定义工具**：用 `FunctionTool` 包装自定义函数

关键概念：
- `LLMResponse.action()` — 创建带工具调用的响应（Thought + Action）
- `AgentTool` — 工具抽象基类，自描述风险画像
- `FunctionTool` — 将函数包装为工具
- `permission_callback` — 权限确认回调

### 3. `multi_agent_demo.py` — 多Agent协作

展示四种多Agent协作模式：

- **OrchestratorAgent**：任务分解 → 并行调度 → 结果聚合
  - 编排者将复杂任务分解为子任务
  - 子Agent在 ThreadPoolExecutor 中并行执行
  - 权限交集：子Agent工具 = 声明 ∩ 父Agent工具池
- **Pipeline**：串行数据流（提取 → 分析 → 报告）
  - 每个阶段的输出是下一阶段的输入
  - 支持输入变换（transform）
- **Blackboard**：共享黑板模式
  - 分区命名空间隔离
  - 发布/订阅通知机制
  - 线程安全（threading.Lock）
- **Voting**：多Agent投票决策
  - 多数投票（MAJORITY）
  - 加权投票（WEIGHTED）
  - 置信度投票（CONFIDENCE）

关键概念：
- `AgentInstance` / `AgentConfig` — 独立 Agent 实例
- `SubAgentConfig` / `SubAgentManager` — 子Agent管理
- `Pipeline` / `PipelineStage` / `PipelineResult`
- `Blackboard` / `BlackboardEntry`
- `Voting` / `Vote` / `VoteResult` / `VotingStrategy`

### 4. `evolution_demo.py` — 自进化

展示 Agent 的自我学习和优化能力：

- **学习引擎**：从交互记录中提取行为模式
  - N-gram 频率统计（识别高频工具序列）
  - K-means 聚类（发现隐含行为群组）
  - Wilson 置信区间（小样本成功率修正）
- **策略更新**：基于模式更新行为策略
  - 工具偏好分数计算
  - 推荐序列和避免序列
  - 可调参数自动优化
- **经验规则**：高频成功模式巩固为规则
  - frequency >= 3 且 success_rate >= 70%
- **行为评估**：多维度评估 Agent 表现
  - 完成率、效率、质量、用户满意度
  - A/B 版本对比
  - 自动生成改进建议
- **反馈收集**：显式和隐式反馈
  - 显式：thumbs_up/down + 文本评论
  - 隐式：完成状态、重试次数、耗时、工具失败
  - 信号归一化到 [-1, 1]
- **完整进化循环**：EvolutionOrchestrator
  - 学习 → 生成 → 评估 → 反馈 → 更新

关键概念：
- `InteractionRecord` — 交互记录
- `LearningEngine` — 学习引擎
- `Pattern` / `BehaviorPolicy` — 模式和策略
- `BehaviorEvaluator` / `EvaluationReport` / `EvaluationMetrics`
- `FeedbackCollector` / `Feedback` / `FeedbackSignal`
- `EvolutionOrchestrator` / `EvolutionResult`

## CLI 交互模式

除了运行示例脚本，还可以使用交互式 REPL：

```bash
# Mock 模式启动（推荐首次体验）
python -m suyi.cli --mock

# 在 REPL 中可使用斜杠命令：
# /help    — 显示帮助
# /memory  — 查看记忆状态
# /tools   — 列出工具
# /skills  — 列出技能
# /config  — 显示配置
# /clear   — 清空历史
# /reset   — 重置 Agent
# /evolve  — 触发自进化
# /quit    — 退出
```

## 设计原则

1. **纯 Python**：不依赖第三方库（rich/click 等），使用标准库 + ANSI 转义码
2. **MockLLM 优先**：所有示例使用 MockLLM，无需 API key
3. **中文注释**：每一步都有中文注释说明
4. **渐进式展示**：从简单到复杂，逐步引入概念
5. **Windows 兼容**：asyncio 运行，ANSI 颜色在 Windows 10+ 上自动启用
