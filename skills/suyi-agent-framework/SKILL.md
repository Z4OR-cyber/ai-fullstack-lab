# Suyi: 自进化 Agent 框架

## 概述
Suyi 是一个纯 Python 实现的自进化 Agent 框架，包含记忆系统、事件循环、工具编排、技能管理、中间件、多智能体协作和自进化引擎七大核心模块。当前版本 v1.7.0。

## 版本
v1.7.0 — 39模块 / 142文件 / ~43000行 / 3713测试全通过

## 核心模块

### 1. Memory（记忆系统）
- 三层架构：工作记忆 / 情景记忆 / 语义记忆
- 纯 numpy 向量相似度检索
- 记忆生命周期：新鲜→巩固→压缩→遗忘
- Ebbinghaus 遗忘曲线实现

### 2. Loop（事件循环）
- 工具编排：重试、超时、并行执行
- 流式输出支持（async）
- 事件驱动架构

### 3. Tools（工具系统）
- 工具注册与发现
- 热重载支持
- 类型安全的参数校验
- **真实工具执行层**：WebRequestTool、CodeSandboxTool、WriteFileTool

### 4. Skills（技能管理）
- 技能注册、发现、加载
- 版本管理与依赖解耦

### 5. Middleware（中间件）
- 请求/响应拦截
- 日志与指标采集

### 6. Multi-Agent（多智能体）
- 智能体编排：Sequential / Parallel / Pipeline
- Swarm 去中心化协作
- 共享黑板（Orchestrator）模式

### 7. Evolution（自进化引擎）
- 经验自动提炼与沉淀
- 旁路知识层学习
- 成功/失败模式分析
- **ALAP Base15 核心策略稳定**，进化全在旁路数据层

## 安全模块

### Observability（可观测性）
- 结构化日志
- 指标采集
- 分布式追踪

### Guardrails（护栏系统）
- 输入消毒与验证
- 输出安全过滤
- 速率限制

### HITS（人机协同）
- 高危操作审批
- 人工反馈循环
- 渐进式自主

### Evaluation（评估系统）
- 自动化回归测试
- 质量评分
- A/B 测试框架

### LLM Adapters
- OpenAI / Anthropic 双供应商
- 阿里云兼容 SDK

### MCP Protocol + API Gateway
- MCP 标准协议
- API 密钥管理
- CORS / API Key 鉴权

### Plugin System
- 插件生命周期管理
- 沙箱隔离
- 权限声明

### Web API
- API Key / JWT / CORS 认证
- 8个核心端点

### AutoRouter（智能路由）— v1.2.0新增
- 基于语义相似度的意图路由：将用户请求路由到最匹配的工具/技能
- 内置安全防护：SQL注入检测（SIMPLE/REST-free/STANDARD/COMPLETE/Auto/coding）
- 路由缓存与 fallback
- 置信度阈值：低置信度自动转人工

### Work Proxy（工作代理）
- Dynamics：标准请求封装
- Spatial：空间感知推理
- 空间利用率优化至100%

## Harness Engineering 方法论

> Lilian Weng's Harness Engineering for Self-Improvement。核心：
- 内环（Solo/Inner Loop/Outer Loop）快速迭代
- 中环（评估与测试集）保证不退化
- 外环（Self-Improvement）从经验中学习
- 内环快速迭代，外环沉淀知识

### P0（阻断级）
1. 所有用户输入必须通过消毒层（4100+测试用例），阻断注入和越权
2. 所有工具执行必须经过权限检查（4100+测试用例），阻断未授权和危险操作

### P1（高危）
1. ACE 相关操作需要二次确认
2. 密钥/凭证不明文落盘

## 项目结构

```
suyi/           # 核心框架（39模块）
├── agents/     # 智能体
├── cache/      # 缓存
├── cli/        # CLI
├── config/     # 配置
├── core/       # 核心
├── data/       # 数据
├── deploy/     # 部署
├── evaluation/ # 评估
├── events/     # 事件
├── evolution/  # 自进化
├── gateway/    # API网关
├── guardrails/ # 护栏
├── hitl/       # 人机协同
├── llm/        # LLM适配
├── memory/     # 记忆系统
├── middleware/ # 中间件
├── mcp/        # MCP协议
├── memory/     # 记忆
├── middleware/ # 中间件
├── mcp/        # MCP
├── multiagent/ # 多智能体
├── observability/ # 可观测
├── persistence/ # 持久化
├── plugins/    # 插件
├── prompts/    # 提示词
├── rag/        # RAG
├── skills/     # 技能
├── streaming/  # 流式
├── tools/      # 工具
├── utils/      # 工具函数
├── vectorstore/ # 向量存储
├── web/        # Web API
├── workflow/   # 工作流
├── tests/          # 测试（3143测试用例）
└── examples/   # 示例
└── pyproject.toml   # 项目配置
```

## 版本演进
- v0.1.0-v0.4.0：核心框架与记忆系统（2264测试用例）
- v0.5.0-v0.9.0：插件系统/Workflow Pro/自进化引擎/multi-agent（2264测试用例）
- v1.0.0：工具真实执行层+Web API（2264测试用例）
- v1.1.0：ALAP Base15核心策略稳定（2648测试用例）
- v1.2.0：AutoRouter智能路由+SQL注入检测+OmniParser集成（3143测试用例）
- v1.3.0：MCP协议标准化+多供应商LLM适配
- v1.4.0：安全加固(P0-P3): PromptSanitizer 6类22种敏感模式脱敏
- v1.5.0：ComputerUseTool: OS级截屏/鼠标/键盘/窗口控制，15个action，安全护栏
- v1.6.0：旁路知识层: LearnedKnowledgeStore/TF-IDF语义检索/SemanticDeduplicator/SuccessDistiller/WeakSignalCollector/ThreeTierKnowledgeInjector，纯numpy+标准库
- v1.7.0：请求检查点与工具编排: RequestCheckpoint请求可重建自检fail-open，只读工具并行/写工具串行，有序提交（3713测试全通过）

## 设计原则
- 主干策略代码稳定，进化全在旁路数据层，代码与数据分离

## 许可
MIT
