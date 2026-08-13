---
name: ai-learning-suite
description: AI全栈学习套件。整合AI全栈学习路线图(ai-fullstack-learning-path)和RAG练习题集(rag-exercise-collection)，覆盖Python基础→ML/DL→LLM/Agent→生产运维→RAG全链路，共548道练习题+248个测试用例，12个阶段循序渐进。当用户需要学习AI全栈、练习Python、学习机器学习/深度学习、LLM开发、Agent开发、RAG检索增强生成、准备AI面试时使用此技能。所有练习纯numpy实现，无需GPU或大型框架依赖。
---

# AI全栈学习套件

> 整合自：ai-fullstack-learning-path + rag-exercise-collection
> 覆盖：Python基础 → ML/DL → LLM/Agent → 协议架构 → 生产运维 → RAG
> 总计：548道练习题 + 248个RAG测试用例，全部可独立运行

## 阶段总览

| 阶段 | 主题 | 题数 | 关键内容 |
|------|------|------|---------|
| 1-4 | Python 基础 | ~200 | 数据结构、OOP、Web开发 |
| 5-8 | ML/LLM/Agent | ~150 | 机器学习、深度学习、LLM基础、Agent开发 |
| 9-10 | 协议架构+模型工程 | 28 | 系统设计、模型工程实践 |
| 11 | 生产运维 | 14 | DevOps、监控、部署 |
| 12 | RAG（检索增强生成） | 10+248测试 | 向量嵌入→系统优化全链路 |

## 阶段12：RAG全链路（10题/248测试/纯numpy）

### 模块1：基础理论（2题）
1. **向量嵌入与语义搜索** — 纯numpy实现embedding和余弦相似度（736行/32测试）
2. **RAG向量数据库** — Chroma/pgvector/Milvus三种实现（1483行/6测试）

### 模块2：文档处理（2题）
3. **文档分块策略** — 6种策略：固定/递归/句子/段落/语义/Token（1201行/23测试）
4. **元数据混合搜索** — BM25+向量+元数据过滤+RRF融合（705行/41测试）

### 模块3：检索优化（3题）
5. **重排序（Re-ranking）** — BM25/向量/词法/语义/混合/MMR/CrossEncoder/两阶段（48测试）
6. **查询转换** — 同义词扩展/伪相关反馈/HyDE/多查询分解/查询路由/RRF融合（42测试）
7. **RAGAS评估** — 忠实度/答案相关性/上下文精确率/上下文召回/正确性（42测试）

### 模块4：Pipeline实战（3题）
8. **端到端Pipeline** — 分块→索引→检索→重排→上下文管理→生成→编排（48测试）
9. **高级RAG技术** — 父子分块/句子窗口/自动合并/层次检索/策略对比（27测试）
10. **系统优化** — LRU+TTL缓存/并行多源检索/流式上下文/监控指标/自适应检索（41测试）

## 技术特点
- 每道题独立可运行，包含完整测试
- 纯numpy实现，无外部API依赖
- 从基础到高级，循序渐进
- GitHub仓库：Z4OR-cyber/ai-fullstack-lab

## 仓库结构
```
python_exercises/   # Python练习题（1-11阶段）
learning/rag/       # RAG练习题（阶段12）
  ├── 01_embedding_semantic_search.py
  ├── 29_rag_vector_db.py
  ├── 03_document_chunking.py
  ├── 04_metadata_hybrid_search.py
  ├── 05_reranking.py
  ├── 06_query_transformation.py
  ├── 07_rag_evaluation.py
  ├── 08_end_to_end_pipeline.py
  ├── 09_advanced_rag_techniques.py
  └── 10_rag_optimization.py
c_exercises/        # C语言练习
lang_exercises/     # 其他语言
devops/             # DevOps实践
docs/               # 文档
tests/              # 测试
```

## RAG学习路径推荐
1. 先完成模块1（理解embedding和向量检索基础）
2. 模块2学习文档处理和混合检索
3. 模块3是进阶，学习如何优化检索质量
4. 模块4是实战，把前面学的组装成完整Pipeline
5. 每道题先看测试用例理解目标，再阅读实现，最后自己动手改

## 三平台发布状态
- GitHub：skills/ai-learning-suite/SKILL.md + learning/rag/（10个文件）
- EvoMap：AI Fullstack Learning Path（bundle_04d9c01faeb4e1c9）+ RAG Exercises v2（bundle_175c53d665ee1292）
- 虾评：rag-exercise-collection（skill_id: 7670347030702620707）

## 许可
MIT
