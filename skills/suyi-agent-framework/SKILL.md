# Suyi: 自进化 Agent 框架

## 概述
Suyi 是一个纯 Python 实现的自进化 Agent 框架，包含记忆系统、事件循环、工具编排、技能管理、中间件、多智能体协作和自进化引擎七大核心模块。

## 版本
v0.7.0 — 32模块 / 126文件 / 1661测试全通过

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

### 4. Skills（技能管理）
- 技能注册、发现、加载
- 版本管理与依赖解析

### 5. Middleware（中间件）
- 请求/响应拦截
- 可插拔架构

### 6. Multi-Agent（多智能体）
- 三种协作模式：Sequential / Parallel / Pipeline
- Swarm 群体智能
- 编排者（Orchestrator）协调

### 7. Evolution（自进化引擎）
- 策略变异与评估
- 适应度函数
- 进化历史追踪

## 增强模块

### Observability（可观测性）
- 结构化日志
- 指标收集
- 分布式追踪

### Guardrails（安全护栏）
- 输入/输出过滤
- 敏感信息检测
- 速率限制

### HITL（人工干预）
- 人工审核循环
- 决策回退
- 审批工作流

### Evaluation（评估框架）
- 6项核心指标
- 基准测试
- A/B 测试

### LLM Adapters
- OpenAI / Anthropic 双适配器
- 零第三方 SDK 依赖

### MCP Protocol + AI Gateway
- MCP 协议支持
- AI 网关集成
- 统一 API 接口

### Plugin System
- 插件注册与生命周期管理
- 部署模板
- 向量存储
- 多模态支持

## 技术特点
- 纯 Python 标准库实现，零第三方依赖（除 numpy）
- 完整的测试覆盖（1661 个测试）
- 类型安全（type hints + runtime validation）
- 可扩展架构

## 文件结构
```
suyi/
├── suyi/           # 核心代码
│   ├── agents/     # 多智能体
│   ├── cache/      # 缓存
│   ├── cli/        # 命令行
│   ├── config/     # 配置
│   ├── core/       # 核心循环
│   ├── data/       # 数据
│   ├── deploy/     # 部署模板
│   ├── evaluation/ # 评估框架
│   ├── events/     # 事件
│   ├── evolution/  # 自进化
│   ├── gateway/    # AI网关
│   ├── guardrails/ # 安全护栏
│   ├── hitl/       # 人工干预
│   ├── llm/        # LLM适配器
│   ├── mcp/        # MCP协议
│   ├── memory/     # 记忆系统
│   ├── middleware/ # 中间件
│   ├── multimodal/ # 多模态
│   ├── observability/ # 可观测性
│   ├── persistence/ # 持久化
│   ├── plugins/    # 插件系统
│   ├── prompts/    # 提示词管理
│   ├── rag/        # RAG
│   ├── skills/     # 技能管理
│   ├── streaming/  # 流式输出
│   ├── tools/      # 工具系统
│   ├── utils/      # 工具函数
│   ├── vectorstore/ # 向量存储
│   ├── web/        # Web API
│   └── workflow/   # 工作流
├── tests/          # 测试（1661个）
├── examples/       # 示例
└── pyproject.toml  # 项目配置
```

## 许可
MIT
