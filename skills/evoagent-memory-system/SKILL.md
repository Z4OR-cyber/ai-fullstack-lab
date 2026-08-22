---
name: evoagent-memory-system
description: "[DEPRECATED] Use suyi-agent-framework instead. Memory system embedded in Suyi framework."
deprecated: true
replaced_by: suyi-agent-framework
deprecated_date: 2026-08-22
---

> WARNING: This skill is deprecated as of 2026-08-22. Use `suyi-agent-framework` instead. Memory system embedded in Suyi framework.

# EvoAgent 三层记忆系统

## 概述
基于纯 Python + numpy 实现的三层 Agent 记忆架构，包含工作记忆、情景记忆和语义记忆三个层次，支持记忆生命周期管理与遗忘曲线。

## 文件清单
| 文件 | 行数 | 功能 |
|------|------|------|
| utils/token_counter.py | 137 | 中英文混合 Token 估算（英文4字符/token，中文CJK 1.5字符/token） |
| memory/working.py | 482 | 工作记忆层，动态组装最小对话上下文，迭代式压缩 |
| memory/episodic.py | 542 | 情景记忆层，4级分级压缩（≤5轮原文/≤15轮弃工具输出/≤30轮摘要/>30轮跳过） |
| memory/semantic.py | 669 | 语义记忆层，纯 numpy TF-IDF 向量检索 + 关键词倒排索引 |
| memory/lifecycle.py | 392 | 记忆生命周期，4阶段演进（新鲜→巩固→压缩→遗忘） |
| memory/__init__.py | 474 | MemoryManager 统一入口 |

## 核心特性

### 三层记忆架构
1. **工作记忆（Working Memory）**：短时上下文缓冲，LRU 淘汰策略，保证不超出 Token 预算
2. **情景记忆（Episodic Memory）**：时间戳标记的经验记录，基于消息年龄的4级分级压缩
3. **语义记忆（Semantic Memory）**：概念提取与关系映射，TF-IDF 向量检索

### 记忆生命周期
- **新鲜阶段**：新记忆完整保留
- **巩固阶段**：重要记忆从情景层迁移到语义层
- **压缩阶段**：长尾记忆进行摘要压缩
- **遗忘阶段**：基于 Ebbinghaus 遗忘曲线的指数衰减

### 置信度计算
```
confidence = base_score * time_decay * (1 + success_count*0.1 - fail_count*0.05)
```
时间衰减采用 half_life=7天 的指数衰减。

### 持久化
默认使用 JSON 文件写入 `.evoagent_memory` 目录，无外部数据库依赖。

## 技术特点
- 纯 Python + numpy，无 PyTorch/TensorFlow 依赖
- 43/44 项功能测试通过
- 可独立运行，也可集成到 Suyi 框架

## 许可
MIT
