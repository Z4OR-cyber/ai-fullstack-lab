---
deprecated: true
replaced_by: ai-learning-suite
deprecated_date: 2026-08-22
---

> **DEPRECATED (2026-08-22)**: Use ai-learning-suite instead. 功能已整合入ai-learning-suite

# AI 全栈学习路线图

## 概述
覆盖 Python 基础到 RAG 管道的 AI 全栈学习路径，共 548 道练习题+248个RAG测试用例，横跨 12 个阶段，每道题均可独立运行并包含测试。

## 阶段划分

| 阶段 | 主题 | 题数 | 关键内容 |
|------|------|------|---------|
| 1-4 | Python 基础 | ~200 | 数据结构、OOP、Web 开发 |
| 5-8 | ML/LLM/Agent | ~150 | 机器学习、深度学习、LLM 基础、Agent 开发 |
| 9-10 | 协议架构+模型工程 | 28 | 系统设计、模型工程实践 |
| 11 | 生产运维 | 14 | DevOps、监控、部署 |
| 12 | RAG | 10+248测试 | 向量嵌入→系统优化全链路 |

## RAG 阶段（Phase 12）详情 — 已完成

### 模块1：基础理论（2题/38测试）
1. **向量嵌入与语义搜索** — 纯numpy实现embedding和余弦相似度（736行/32测试）
2. **RAG向量数据库** — Chroma/pgvector/Milvus三种实现（1483行/6测试）

### 模块2：文档处理（2题/64测试）
3. **文档分块策略** — 6种策略：固定/递归/句子/段落/语义/Token（1201行/23测试）
4. **元数据混合搜索** — BM25+向量+元数据+RRF融合（705行/41测试）

### 模块3：检索优化（3题/132测试）
5. **重排序** — BM25/向量/词法/语义/混合/MMR/CrossEncoder/两阶段（48测试）
6. **查询转换** — 同义词扩展/伪相关反馈/HyDE/多查询分解/路由/RRF（42测试）
7. **RAGAS评估** — 忠实度/答案相关性/上下文精确率/召回/正确性（42测试）

### 模块4：Pipeline实战（3题/116测试）
8. **端到端Pipeline** — 分块→索引→检索→重排→生成→编排（48测试）
9. **高级RAG技术** — 父子分块/句子窗口/自动合并/层次检索（27测试）
10. **系统优化** — LRU+TTL缓存/并行检索/流式组装/监控/自适应（41测试）

## 技术特点
- 每道题独立可运行，包含完整测试
- 纯 numpy 实现，无外部 API 依赖
- 从基础到高级，循序渐进
- GitHub仓库：Z4OR-cyber/ai-fullstack-lab

## 仓库结构
```
python_exercises/   # Python 练习题（阶段1-11）
learning/rag/       # RAG 练习题（阶段12，10个文件）
c_exercises/        # C 语言练习
lang_exercises/     # 其他语言
devops/             # DevOps 实践
docs/               # 文档
tests/              # 测试
```

## 许可
MIT
