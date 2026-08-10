# ALA：自适应循环架构——让 Agent 的 Loop 本身成为可进化的记忆

> **Suyi（溯忆）** 项目原创架构设计
> GitHub: https://github.com/Z4OR-cyber/ai-fullstack-lab
> 版本: v1.0.0 | 测试: 2774 全通过

---

## 背景：从 Prompt Engineering 到 Loop Engineering

AI 工程经历了四个阶段的演进：

1. **Prompt Engineering** — 精心设计提示词
2. **Context Engineering** — 管理上下文窗口、RAG、记忆
3. **Harness Engineering** — 构建工具调用、安全护栏、人机协作
4. **Loop Engineering** — 让 Agent 在循环中自主完成任务

但现有的 Loop Engineering 存在一个关键缺陷：**Loop 本身是消耗品，不是资产。** 每次 Loop 运行结束后，执行结构、失败模式、策略调整都随风而逝。下次遇到类似任务，Agent 从零开始。

ALA（Adaptive Loop Architecture）要解决的核心问题是：**让 Loop 的执行经验沉淀为可复用、可进化、可遗忘的记忆。**

---

## 五大原创模块

### 1. 质量分级系统 (Phase 13)

不是所有记忆都值得保留。ALA 引入二维质量评分：

**来源分级 (S-D)**：
| 等级 | 含义 | 示例 |
|------|------|------|
| S | 官方文档/权威来源 | API 官方文档 |
| A | 验证过的实践 | 经过测试的代码 |
| B | 推理得出 | LLM 生成的分析 |
| C | 未验证 | 网络搜索结果 |
| D | 已证伪 | 失败的假设 |

**结果分级 (Verified-Failed)**：
- Verified — 经验证正确
| Confirmed — 部分验证
- Unverified — 未验证
| Failed — 已证伪

最终质量分 = 40%来源 + 30%结果 + 20%置信度 + 10%证据比

### 2. 遗忘引擎 (Phase 13)

灵感来自 Ebbinghaus 遗忘曲线：Q(t) = Q₀ × e^(-t/τ)

三级遗忘策略：
- **DEGRADE** (Q > 0.2) — 降低检索优先级，保留全文
- **COMPRESS** (0.05 < Q ≤ 0.2) — 压缩为摘要，释放存储
- **PURGE** (Q ≤ 0.05) — 物理删除

安全网机制：
- `user-pinned` 记忆永不自动删除
- `anti-pattern`（反面记忆）永不自动删除
- 即使用户强制 PURGE，上述两类也会降级为 DEGRADE
- 支持 `is_dry_run` 预览模式

### 3. Loop 模板记忆 (Phase 14)

这是 ALA 的核心创新：**将 Loop 的执行结构本身模板化。**

一个 Loop 模板包含：
```python
@dataclass
class LoopTemplate:
    name: str                    # 模板名称
    task_signature: str          # 任务签名（用于检索匹配）
    phases: list[LoopPhase]      # 执行阶段序列
    reflection_points: list[int] # 在第几轮触发反思
    budgets: dict[str, float]    # 预算配置
    success_rate: float          # 历史成功率
    usage_count: int             # 使用次数
    quality: QualityScore        # 质量评分
```

模板生命周期：
1. **提取** — 从成功的 Loop 运行中自动提取模板
2. **检索** — 新任务通过签名匹配检索最相关模板
3. **注入** — L1 层级，运行时注入上下文引导执行
4. **变异** — L2 层级，六种策略变异生成候选模板
5. **A/B 测试** — 统计显著性验证后保留或淘汰
6. **遗忘** — 低质量模板按遗忘曲线自动清理

### 4. 策略进化器 (Phase 15)

六种变异策略：

| 策略 | 说明 | 风险 |
|------|------|------|
| PHASE_REORDER | 调整阶段顺序 | 低 |
| PHASE_INSERT | 插入新阶段 | 中 |
| PHASE_REMOVE | 移除冗余阶段 | 中 |
| BUDGET_ADJUST | 调整预算分配 | 低 |
| REFLECTION_SHIFT | 移动反思点 | 低 |
| TEMPLATE_MERGE | 合并两个模板 | 高 |

统计验证：
- z 检验 — 比较变异前后成功率
- Wilson 区间 — 小样本置信区间
- 最小样本量 — 至少 5 次实验才纳入统计

五维反思（ProcessReflection）：
1. 效率 — 是否在预算内完成
2. 效果 — 是否达到目标
3. 成本 — Token 消耗
4. 安全 — 是否触发护栏
5. 学习 — 是否产生新模板

### 5. 双层循环 (Phase 16-17)

```
┌──────────────────────────────────────────────┐
│           外层: EvolutionLoop                │
│  ┌────────────────────────────────────────┐  │
│  │  监控内层运行 → 分析模式 → 提取模板    │  │
│  │  → 变异策略 → A/B测试 → 更新模板库     │  │
│  └────────────────────────────────────────┘  │
│  ┌────────────────────────────────────────┐  │
│  │           内层: TaskLoop                │  │
│  │  预算检查 → 上下文组装 → LLM调用        │  │
│  │  → 工具执行 → 结果校验 → 反思          │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

四种触发机制：
1. **PERIODIC** — 固定间隔触发外层循环
2. **THRESHOLD** — 内层累积 N 次后触发
3. **ANOMALY** — 检测到异常模式触发
4. **MANUAL** — 用户手动触发

---

## 与现有方案的对比

| 特性 | Voyager | CodeIt | WebEvolver | **Suyi ALA** |
|------|---------|--------|------------|-------------|
| Loop结构记忆 | ❌ | ❌ | ❌ | ✅ |
| 质量分级遗忘 | ❌ | 优先级回放 | ❌ | ✅ |
| 策略变异进化 | ❌ | ❌ | 隐式 | ✅ 显式 |
| 双层循环 | ❌ | ❌ | ❌ | ✅ |
| 反面记忆 | ❌ | ❌ | ❌ | ✅ |
| 统计显著性验证 | ❌ | ❌ | ❌ | ✅ |
| 纯Python无依赖 | ❌ | ❌ | ❌ | ✅ |

---

## World Proxy 六功能覆盖

ALA 的设计覆盖了 World Proxy 论文（arXiv:2608.02713）提出的六功能×三层级矩阵：

| 功能 | 实现 |
|------|------|
| Dynamics | EnvironmentDynamicsTracker — 环境状态转移建模 |
| Spatial | ServiceTopologyMapper — 服务拓扑图 |
| Execution | CodeSandboxTool + WebRequestTool |
| Memory-Experience | Loop模板记忆 + SQLite FTS5 |
| Skill | Skill加载 + 动态扩展 |
| Reward-Verification | 质量分级 + 统一校验层 |

---

## 技术约束

- 纯 Python + 标准库 + numpy + httpx
- 不依赖 PyTorch / TensorFlow / OpenAI SDK
- LLM 接口可注入（MockLLM 用于无 API 测试）
- SQLite FTS5 全文搜索（无外部数据库）
- 所有模块通过接口暴露可注入 Mock 测试

---

## 未来方向

1. **真实 LLM 集成** — 通过 OmniRoute Gateway 接入真实 LLM 跑进化循环
2. **多 Agent 协同进化** — 多个 Agent 共享模板库，集体进化
3. **跨域迁移** — 将一个领域的 Loop 模板迁移到新领域
4. **因果推断** — 从相关性进化升级为因果性进化

---

*ALA 是 Suyi（溯忆）项目的核心原创架构。溯 = Loop 模板检索，忆 = Loop 模板存储，进化 = 双层循环。*
