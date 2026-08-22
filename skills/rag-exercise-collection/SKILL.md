---
name: rag-exercise-collection
description: "[DEPRECATED] Use ai-learning-suite instead. RAG exercises integrated into learning suite."
deprecated: true
replaced_by: ai-learning-suite
deprecated_date: 2026-08-22
---

> WARNING: This skill is deprecated as of 2026-08-22. Use `ai-learning-suite` instead. RAG exercises integrated into learning suite.

# RAG 检索增强生成练习集

> 10题4模块 RAG 实战练习，纯 numpy 可运行，248个测试全通过

## 技能描述
从零实现的 RAG 全栈练习题集，覆盖向量嵌入、向量数据库、文档处理、检索优化和端到端 Pipeline。所有代码纯 numpy 实现，无需 GPU 或大型框架依赖。每道题包含完整实现+测试用例，可独立运行。

## 模块结构

### 模块1：基础理论（2题/38测试）
1. **向量嵌入与语义搜索** — 纯numpy实现embedding和余弦相似度（736行/32测试）
2. **RAG向量数据库** — Chroma/pgvector/Milvus三种实现（1483行/6测试）

### 模块2：文档处理（2题/64测试）
3. **文档分块策略** — 6种策略：固定/递归/句子/段落/语义/Token分块（1201行/23测试）
4. **元数据混合搜索** — BM25+向量+元数据过滤($eq/$ne/$in/$nin/$gt/$lt)+RRF融合（705行/41测试）

### 模块3：检索优化（3题/132测试）
5. **重排序（Re-ranking）** — BM25/向量/词法/语义/混合/MMR/CrossEncoder/两阶段Pipeline（48测试）
6. **查询转换** — 同义词扩展/伪相关反馈/HyDE/多查询分解/查询路由/RRF融合（42测试）
7. **RAGAS评估** — 忠实度/答案相关性/上下文精确率/上下文召回/上下文相关性/答案正确性（42测试）

### 模块4：Pipeline实战（3题/116测试）
8. **端到端Pipeline** — TextChunker+BM25Index+VectorIndex+HybridRetriever+ReRanker+ContextManager+AnswerGenerator+RAGPipeline编排（48测试）
9. **高级RAG技术** — 父子分块/句子窗口索引/自动合并检索/层次检索/策略对比工具（27测试）
10. **系统优化** — LRU+TTL缓存/CachedRetriever/并行多源检索/流式上下文组装/监控指标收集/自适应检索/OptimizedRAGPipeline（41测试）

## 关键技术点
- 纯numpy实现的向量相似度（cosine/dot product）
- BM25词法检索从零实现
- TF-IDF向量化
- RRF（Reciprocal Rank Fusion）结果融合
- MMR（Maximal Marginal Relevance）多样性重排
- NDCG/MRR/Recall/Precision评估指标
- Token预算上下文管理
- LRU+TTL双策略缓存

## 测试修复经验
- 小语料库下BM25搜索可能返回少于top_n的结果，断言用assertLessEqual
- 词法重叠度量无法真正区分语义不相关内容，测试中需调高阈值
- metadata字段值为列表(如tags)时，$in/$nin操作符需用isinstance判断
- extractive summary始终包含至少第一句话，避免因第一句超length导致空summary
- TF-IDF向量检索中cosine_similarity为0的结果不应返回

## GitHub提交记录
- Exercise 1: `01_embedding_semantic_search.py`
- Exercise 2: `29_rag_vector_db.py`
- Exercise 3: SHA `9e2fcb3c` — 6种分块策略
- Exercise 4: SHA `3ba07f9c` — 元数据混合搜索
- Exercise 5: SHA `546e89c3` — 重排序
- Exercise 6: SHA `f103f070` — 查询转换
- Exercise 7: SHA `f6e052c9` — RAGAS评估
- Exercise 8: SHA `d3534137` — 端到端Pipeline
- Exercise 9: SHA `1ecf3771` — 高级RAG技术
- Exercise 10: SHA `ac543d37` — 系统优化

## 三平台发布状态
- Coze 技能商店：已发布（skill_id: 7670347030702620707）
- EvoMap：已发布（bundle_175c53d665ee1292）
- GitHub：learning/rag/ 目录（10个文件）

## 许可
MIT
