"""
RAG 练习题 4: 元数据过滤 + 混合搜索 (Metadata Filtering + Hybrid Search)
=========================================================================

学习目标:
  1. 理解元数据过滤的原理和应用场景
  2. 实现 BM25 关键词检索 (全文搜索)
  3. 实现向量语义检索 (语义搜索)
  4. 掌握混合搜索的融合策略 (Reciprocal Rank Fusion, Weighted Fusion)
  5. 理解 pre-filtering vs post-filtering 的区别
  6. 构建端到端的混合搜索 Pipeline

核心概念:
  - 元数据过滤: 在检索前/后根据结构化属性 (日期、标签、来源) 筛选文档
  - BM25: 基于词频和逆文档频率的概率检索模型，擅长精确匹配
  - 向量检索: 基于嵌入相似度的语义检索，擅长理解意图
  - 混合搜索: 融合两种检索方式，兼顾精确匹配和语义理解
  - RRF (Reciprocal Rank Fusion): 无权重融合，根据排名倒数合并
  - 加权融合: 按权重线性组合两种检索的分数

运行方式:
  python 04_metadata_hybrid_search.py
"""

import math
import re
import json
import hashlib
import unittest
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Optional, Any, Set
from dataclasses import dataclass, field


# ============================================================================
# Part 1: 文档数据结构与元数据
# ============================================================================

@dataclass
class Document:
    """带元数据的文档结构"""
    doc_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.doc_id:
            raise ValueError("doc_id cannot be empty")
        if not self.content:
            raise ValueError("content cannot be empty")
    
    def get(self, key: str, default=None):
        """获取元数据字段"""
        return self.metadata.get(key, default)
    
    def matches_filter(self, filters: Dict[str, Any]) -> bool:
        """
        检查文档是否匹配元数据过滤条件
        
        支持的过滤操作:
          - 直接值匹配: {"category": "tech"} → metadata["category"] == "tech"
          - 范围匹配: {"date": {"$gte": "2024-01-01"}} → metadata["date"] >= "2024-01-01"
          - 列表包含: {"tags": {"$in": ["AI", "ML"]}} → any tag in ["AI", "ML"]
          - 存在性检查: {"author": {"$exists": True}} → "author" in metadata
        """
        if not filters:
            return True
        
        for key, condition in filters.items():
            doc_value = self.metadata.get(key)
            
            if isinstance(condition, dict):
                for op, op_value in condition.items():
                    if op == "$eq":
                        if doc_value != op_value:
                            return False
                    elif op == "$ne":
                        if doc_value == op_value:
                            return False
                    elif op == "$gt":
                        if doc_value is None or doc_value <= op_value:
                            return False
                    elif op == "$gte":
                        if doc_value is None or doc_value < op_value:
                            return False
                    elif op == "$lt":
                        if doc_value is None or doc_value >= op_value:
                            return False
                    elif op == "$lte":
                        if doc_value is None or doc_value > op_value:
                            return False
                    elif op == "$in":
                        if doc_value is None:
                            return False
                        if isinstance(doc_value, list):
                            if not any(v in op_value for v in doc_value):
                                return False
                        elif doc_value not in op_value:
                            return False
                    elif op == "$nin":
                        if doc_value is not None:
                            if isinstance(doc_value, list):
                                if any(v in op_value for v in doc_value):
                                    return False
                            elif doc_value in op_value:
                                return False
                    elif op == "$exists":
                        if op_value and doc_value is None:
                            return False
                        if not op_value and doc_value is not None:
                            return False
                    else:
                        raise ValueError(f"Unsupported operator: {op}")
            else:
                if doc_value != condition:
                    return False
        
        return True


# ============================================================================
# Part 2: BM25 关键词检索
# ============================================================================

class BM25Index:
    """
    BM25 检索索引 (Okapi BM25)
    
    BM25 公式:
      score(D, Q) = Σ IDF(qi) * (f(qi, D) * (k1 + 1)) / (f(qi, D) + k1 * (1 - b + b * |D| / avgdl))
    
    其中:
      - f(qi, D): 词 qi 在文档 D 中的频率
      - |D|: 文档 D 的长度 (词数)
      - avgdl: 语料库平均文档长度
      - k1: 词频饱和参数 (通常 1.2-2.0)
      - b: 长度归一化参数 (通常 0.75)
      - IDF(qi): log((N - n(qi) + 0.5) / (n(qi) + 0.5) + 1)
    """
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.documents: List[Document] = []
        self.doc_tokens: List[List[str]] = []
        self.doc_freqs: List[Counter] = []
        self.doc_lengths: List[int] = []
        self.avgdl: float = 0.0
        self.inverted_index: Dict[str, Set[int]] = defaultdict(set)
        self.df: Dict[str, int] = defaultdict(int)  # document frequency
        self.idf: Dict[str, float] = {}
        self.N: int = 0
    
    @staticmethod
    def tokenize(text: str) -> List[str]:
        """简单分词: 转小写 + 按非字母数字分割"""
        text = text.lower()
        tokens = re.findall(r'[a-z0-9\u4e00-\u9fff]+', text)
        return tokens
    
    def add_documents(self, documents: List[Document]):
        """添加文档到索引"""
        for doc in documents:
            idx = len(self.documents)
            self.documents.append(doc)
            tokens = self.tokenize(doc.content)
            self.doc_tokens.append(tokens)
            freq = Counter(tokens)
            self.doc_freqs.append(freq)
            self.doc_lengths.append(len(tokens))
            
            for term in freq:
                self.inverted_index[term].add(idx)
                self.df[term] += 1
        
        self.N = len(self.documents)
        self.avgdl = sum(self.doc_lengths) / max(self.N, 1)
        self._compute_idf()
    
    def _compute_idf(self):
        """计算每个词的 IDF 值"""
        for term, df in self.df.items():
            # BM25 IDF formula with +1 smoothing
            self.idf[term] = math.log((self.N - df + 0.5) / (df + 0.5) + 1)
    
    def search(self, query: str, top_k: int = 10, 
               filters: Optional[Dict[str, Any]] = None) -> List[Tuple[Document, float]]:
        """
        BM25 检索
        
        Args:
            query: 查询字符串
            top_k: 返回前 K 个结果
            filters: 元数据过滤条件 (pre-filtering)
        
        Returns:
            List of (document, score) tuples, sorted by score descending
        """
        query_tokens = self.tokenize(query)
        if not query_tokens:
            return []
        
        # Pre-filtering: 先过滤文档
        candidate_indices = set()
        if filters:
            for i, doc in enumerate(self.documents):
                if doc.matches_filter(filters):
                    candidate_indices.add(i)
        else:
            candidate_indices = set(range(self.N))
        
        # 计算每个候选文档的 BM25 分数
        scores: Dict[int, float] = defaultdict(float)
        
        for term in query_tokens:
            if term not in self.idf:
                continue
            
            term_idf = self.idf[term]
            posting_list = self.inverted_index.get(term, set())
            
            for doc_idx in posting_list:
                if doc_idx not in candidate_indices:
                    continue
                
                tf = self.doc_freqs[doc_idx].get(term, 0)
                if tf == 0:
                    continue
                
                doc_len = self.doc_lengths[doc_idx]
                # BM25 term score
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / max(self.avgdl, 1))
                term_score = term_idf * (numerator / denominator)
                scores[doc_idx] += term_score
        
        # 排序并返回 top_k
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [(self.documents[idx], score) for idx, score in ranked]
    
    def get_term_freq(self, doc_idx: int, term: str) -> int:
        """获取指定文档中某词的词频"""
        if doc_idx < 0 or doc_idx >= len(self.doc_freqs):
            return 0
        return self.doc_freqs[doc_idx].get(term, 0)


# ============================================================================
# Part 3: 向量语义检索 (简化版)
# ============================================================================

class SimpleVectorIndex:
    """
    简化的向量语义检索索引
    
    使用 TF-IDF 向量 + 余弦相似度作为语义检索的近似。
    实际生产环境中应使用预训练嵌入模型 (如 text-embedding-ada-002)。
    """
    
    def __init__(self):
        self.documents: List[Document] = []
        self.doc_vectors: List[Dict[str, float]] = []
        self.vocabulary: Set[str] = set()
        self.idf: Dict[str, float] = {}
        self.N: int = 0
    
    @staticmethod
    def tokenize(text: str) -> List[str]:
        """与 BM25 共用的分词器"""
        text = text.lower()
        return re.findall(r'[a-z0-9\u4e00-\u9fff]+', text)
    
    def add_documents(self, documents: List[Document]):
        """添加文档并构建 TF-IDF 向量"""
        self.documents = documents
        self.N = len(documents)
        
        # 构建 vocabulary
        doc_token_lists = []
        for doc in documents:
            tokens = self.tokenize(doc.content)
            doc_token_lists.append(tokens)
            self.vocabulary.update(tokens)
        
        # 计算 IDF
        doc_freq = defaultdict(int)
        for tokens in doc_token_lists:
            unique_terms = set(tokens)
            for term in unique_terms:
                doc_freq[term] += 1
        
        for term in self.vocabulary:
            self.idf[term] = math.log((self.N + 1) / (doc_freq.get(term, 0) + 1)) + 1
        
        # 构建 TF-IDF 向量
        for tokens in doc_token_lists:
            vector = {}
            tf_counter = Counter(tokens)
            for term, tf in tf_counter.items():
                vector[term] = tf * self.idf.get(term, 0)
            
            # L2 归一化
            norm = math.sqrt(sum(v ** 2 for v in vector.values()))
            if norm > 0:
                for term in vector:
                    vector[term] /= norm
            
            self.doc_vectors.append(vector)
    
    def _query_to_vector(self, query: str) -> Dict[str, float]:
        """将查询转换为 TF-IDF 向量"""
        tokens = self.tokenize(query)
        vector = {}
        tf_counter = Counter(tokens)
        for term, tf in tf_counter.items():
            if term in self.idf:
                vector[term] = tf * self.idf[term]
        
        # L2 归一化
        norm = math.sqrt(sum(v ** 2 for v in vector.values()))
        if norm > 0:
            for term in vector:
                vector[term] /= norm
        
        return vector
    
    @staticmethod
    def cosine_similarity(v1: Dict[str, float], v2: Dict[str, float]) -> float:
        """计算两个稀疏向量的余弦相似度"""
        # 遍历较小的向量
        if len(v1) > len(v2):
            v1, v2 = v2, v1
        
        dot_product = sum(v * v2.get(k, 0) for k, v in v1.items())
        return dot_product  # 向量已归一化，点积即为余弦相似度
    
    def search(self, query: str, top_k: int = 10,
               filters: Optional[Dict[str, Any]] = None) -> List[Tuple[Document, float]]:
        """
        向量语义检索
        
        Args:
            query: 查询字符串
            top_k: 返回前 K 个结果
            filters: 元数据过滤条件 (pre-filtering)
        
        Returns:
            List of (document, score) tuples, sorted by score descending
        """
        query_vector = self._query_to_vector(query)
        if not query_vector:
            return []
        
        scores = []
        for i, (doc, doc_vector) in enumerate(zip(self.documents, self.doc_vectors)):
            # Pre-filtering
            if filters and not doc.matches_filter(filters):
                continue
            
            sim = self.cosine_similarity(query_vector, doc_vector)
            if sim > 0:
                scores.append((doc, sim))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


# ============================================================================
# Part 4: 混合搜索融合策略
# ============================================================================

class HybridSearcher:
    """
    混合搜索引擎: 融合 BM25 关键词检索和向量语义检索
    
    支持两种融合策略:
      1. Reciprocal Rank Fusion (RRF): 无参数融合，根据排名倒数合并
      2. Weighted Fusion: 按权重线性组合归一化分数
    """
    
    def __init__(self, bm25: BM25Index, vector_index: SimpleVectorIndex):
        self.bm25 = bm25
        self.vector_index = vector_index
    
    @staticmethod
    def reciprocal_rank_fusion(
        bm25_results: List[Tuple[Document, float]],
        vector_results: List[Tuple[Document, float]],
        k: int = 60
    ) -> List[Tuple[Document, float]]:
        """
        Reciprocal Rank Fusion (RRF)
        
        公式: RRF_score(d) = Σ 1 / (k + rank_i(d))
        
        RRF 的优势:
          - 不需要分数归一化 (只用排名)
          - 对不同检索器的分数尺度不敏感
          - k 参数控制排名靠后文档的惩罚力度
        
        Args:
            bm25_results: BM25 检索结果 [(doc, score), ...]
            vector_results: 向量检索结果 [(doc, score), ...]
            k: RRF 常数 (通常 60)
        
        Returns:
            融合后的结果列表
        """
        rrf_scores: Dict[str, float] = defaultdict(float)
        doc_map: Dict[str, Document] = {}
        
        # BM25 排名贡献
        for rank, (doc, _) in enumerate(bm25_results, start=1):
            rrf_scores[doc.doc_id] += 1.0 / (k + rank)
            doc_map[doc.doc_id] = doc
        
        # 向量检索排名贡献
        for rank, (doc, _) in enumerate(vector_results, start=1):
            rrf_scores[doc.doc_id] += 1.0 / (k + rank)
            doc_map[doc.doc_id] = doc
        
        # 排序
        ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return [(doc_map[doc_id], score) for doc_id, score in ranked]
    
    @staticmethod
    def _normalize_scores(results: List[Tuple[Document, float]]) -> Dict[str, float]:
        """将分数归一化到 [0, 1] 区间 (min-max normalization)"""
        if not results:
            return {}
        
        scores = [score for _, score in results]
        min_score = min(scores)
        max_score = max(scores)
        
        if max_score == min_score:
            return {doc.doc_id: 1.0 for doc, _ in results}
        
        return {
            doc.doc_id: (score - min_score) / (max_score - min_score)
            for doc, score in results
        }
    
    @staticmethod
    def weighted_fusion(
        bm25_results: List[Tuple[Document, float]],
        vector_results: List[Tuple[Document, float]],
        bm25_weight: float = 0.5,
        vector_weight: float = 0.5
    ) -> List[Tuple[Document, float]]:
        """
        加权融合 (Weighted Fusion)
        
        公式: final_score(d) = w_bm25 * norm_bm25(d) + w_vector * norm_vector(d)
        
        先对每种检索的分数做 min-max 归一化，再按权重线性组合。
        
        Args:
            bm25_results: BM25 检索结果
            vector_results: 向量检索结果
            bm25_weight: BM25 权重 (0-1)
            vector_weight: 向量权重 (0-1)
        
        Returns:
            融合后的结果列表
        """
        if not math.isclose(bm25_weight + vector_weight, 1.0, abs_tol=1e-6):
            raise ValueError("bm25_weight + vector_weight must equal 1.0")
        
        norm_bm25 = HybridSearcher._normalize_scores(bm25_results)
        norm_vector = HybridSearcher._normalize_scores(vector_results)
        
        all_doc_ids = set(norm_bm25.keys()) | set(norm_vector.keys())
        doc_map: Dict[str, Document] = {}
        
        for doc, _ in bm25_results:
            doc_map[doc.doc_id] = doc
        for doc, _ in vector_results:
            doc_map[doc.doc_id] = doc
        
        fused_scores = {}
        for doc_id in all_doc_ids:
            bm25_score = norm_bm25.get(doc_id, 0.0)
            vector_score = norm_vector.get(doc_id, 0.0)
            fused_scores[doc_id] = bm25_weight * bm25_score + vector_weight * vector_score
        
        ranked = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
        return [(doc_map[doc_id], score) for doc_id, score in ranked]
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        fusion: str = "rrf",
        bm25_weight: float = 0.5,
        vector_weight: float = 0.5,
        rrf_k: int = 60
    ) -> List[Tuple[Document, float]]:
        """
        混合搜索主入口
        
        Args:
            query: 查询字符串
            top_k: 返回前 K 个结果
            filters: 元数据过滤条件
            fusion: 融合策略 ("rrf" 或 "weighted")
            bm25_weight: BM25 权重 (weighted 模式)
            vector_weight: 向量权重 (weighted 模式)
            rrf_k: RRF 常数 (rrf 模式)
        
        Returns:
            融合后的检索结果
        """
        # 获取比 top_k 更多的候选，以便融合后有足够结果
        candidate_k = max(top_k * 3, 20)
        
        bm25_results = self.bm25.search(query, top_k=candidate_k, filters=filters)
        vector_results = self.vector_index.search(query, top_k=candidate_k, filters=filters)
        
        if fusion == "rrf":
            fused = self.reciprocal_rank_fusion(bm25_results, vector_results, k=rrf_k)
        elif fusion == "weighted":
            fused = self.weighted_fusion(
                bm25_results, vector_results,
                bm25_weight=bm25_weight,
                vector_weight=vector_weight
            )
        else:
            raise ValueError(f"Unknown fusion strategy: {fusion}. Use 'rrf' or 'weighted'.")
        
        return fused[:top_k]


# ============================================================================
# Part 5: Pre-filtering vs Post-filtering
# ============================================================================

class PostFilterHybridSearcher:
    """
    Post-filtering 混合搜索
    
    与 pre-filtering 不同，post-filtering 先检索所有文档，
    然后从结果中过滤掉不匹配的文档。
    
    优势: 检索质量不受过滤条件影响
    劣势: 可能返回少于 top_k 的结果 (过滤后不足)
    """
    
    def __init__(self, bm25: BM25Index, vector_index: SimpleVectorIndex):
        self.bm25 = bm25
        self.vector_index = vector_index
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        fusion: str = "rrf",
        rrf_k: int = 60,
        bm25_weight: float = 0.5,
        vector_weight: float = 0.5
    ) -> List[Tuple[Document, float]]:
        """
        Post-filtering 混合搜索
        
        先无过滤检索，再从结果中过滤
        """
        candidate_k = max(top_k * 5, 50)  # 多取一些以补偿过滤损失
        
        # 无过滤检索
        bm25_results = self.bm25.search(query, top_k=candidate_k, filters=None)
        vector_results = self.vector_index.search(query, top_k=candidate_k, filters=None)
        
        # 融合
        hybrid = HybridSearcher(self.bm25, self.vector_index)
        if fusion == "rrf":
            fused = hybrid.reciprocal_rank_fusion(bm25_results, vector_results, k=rrf_k)
        elif fusion == "weighted":
            fused = hybrid.weighted_fusion(
                bm25_results, vector_results,
                bm25_weight=bm25_weight,
                vector_weight=vector_weight
            )
        else:
            raise ValueError(f"Unknown fusion: {fusion}")
        
        # Post-filtering
        if filters:
            fused = [(doc, score) for doc, score in fused if doc.matches_filter(filters)]
        
        return fused[:top_k]


# ============================================================================
# Part 6: 端到端混合搜索 Pipeline
# ============================================================================

class HybridSearchPipeline:
    """
    端到端混合搜索 Pipeline
    
    整合: 文档管理 + 元数据过滤 + BM25 + 向量检索 + 混合融合
    """
    
    def __init__(self, filtering_mode: str = "pre"):
        """
        Args:
            filtering_mode: "pre" (pre-filtering) 或 "post" (post-filtering)
        """
        self.bm25 = BM25Index(k1=1.5, b=0.75)
        self.vector_index = SimpleVectorIndex()
        self.filtering_mode = filtering_mode
        self.hybrid = HybridSearcher(self.bm25, self.vector_index)
        self.post_filter = PostFilterHybridSearcher(self.bm25, self.vector_index)
        self._indexed = False
    
    def add_documents(self, documents: List[Document]):
        """添加文档到索引"""
        self.bm25.add_documents(documents)
        self.vector_index.add_documents(documents)
        self._indexed = True
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        fusion: str = "rrf",
        **kwargs
    ) -> List[Tuple[Document, float]]:
        """搜索"""
        if not self._indexed:
            raise RuntimeError("No documents indexed. Call add_documents() first.")
        
        if self.filtering_mode == "post" and filters:
            return self.post_filter.search(
                query, top_k=top_k, filters=filters,
                fusion=fusion, **kwargs
            )
        else:
            return self.hybrid.search(
                query, top_k=top_k, filters=filters,
                fusion=fusion, **kwargs
            )
    
    def search_with_explanation(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        fusion: str = "rrf",
        **kwargs
    ) -> Dict[str, Any]:
        """带解释的搜索: 返回各阶段的检索详情"""
        candidate_k = max(top_k * 3, 20)
        
        # 各路检索结果
        bm25_results = self.bm25.search(query, top_k=candidate_k, filters=filters)
        vector_results = self.vector_index.search(query, top_k=candidate_k, filters=filters)
        
        # 融合结果
        if fusion == "rrf":
            fused = self.hybrid.reciprocal_rank_fusion(bm25_results, vector_results, 
                                                        k=kwargs.get("rrf_k", 60))
        else:
            fused = self.hybrid.weighted_fusion(bm25_results, vector_results,
                                                 bm25_weight=kwargs.get("bm25_weight", 0.5),
                                                 vector_weight=kwargs.get("vector_weight", 0.5))
        
        return {
            "query": query,
            "filters": filters,
            "fusion": fusion,
            "bm25_results": [(doc.doc_id, round(score, 4)) for doc, score in bm25_results[:top_k]],
            "vector_results": [(doc.doc_id, round(score, 4)) for doc, score in vector_results[:top_k]],
            "fused_results": [(doc.doc_id, round(score, 4)) for doc, score in fused[:top_k]],
            "bm25_count": len(bm25_results),
            "vector_count": len(vector_results),
            "fused_count": len(fused),
            "top_documents": [
                {
                    "doc_id": doc.doc_id,
                    "score": round(score, 4),
                    "content_preview": doc.content[:100] + "..." if len(doc.content) > 100 else doc.content,
                    "metadata": doc.metadata
                }
                for doc, score in fused[:top_k]
            ]
        }


# ============================================================================
# Part 7: 测试套件
# ============================================================================

class TestDocumentMetadata(unittest.TestCase):
    """测试文档元数据结构"""
    
    def setUp(self):
        self.doc = Document(
            doc_id="d1",
            content="Python is a programming language",
            metadata={
                "category": "tech",
                "tags": ["python", "programming"],
                "date": "2024-06-15",
                "author": "Alice",
                "views": 1500
            }
        )
    
    def test_direct_value_match(self):
        self.assertTrue(self.doc.matches_filter({"category": "tech"}))
        self.assertFalse(self.doc.matches_filter({"category": "sports"}))
    
    def test_gte_operator(self):
        self.assertTrue(self.doc.matches_filter({"views": {"$gte": 1000}}))
        self.assertFalse(self.doc.matches_filter({"views": {"$gte": 2000}}))
    
    def test_lte_operator(self):
        self.assertTrue(self.doc.matches_filter({"views": {"$lte": 2000}}))
        self.assertFalse(self.doc.matches_filter({"views": {"$lte": 1000}}))
    
    def test_in_operator(self):
        self.assertTrue(self.doc.matches_filter({"tags": {"$in": ["python", "java"]}}))
        self.assertFalse(self.doc.matches_filter({"tags": {"$in": ["java", "go"]}}))
    
    def test_exists_operator(self):
        self.assertTrue(self.doc.matches_filter({"author": {"$exists": True}}))
        self.assertFalse(self.doc.matches_filter({"publisher": {"$exists": True}}))
    
    def test_multiple_conditions(self):
        filters = {
            "category": "tech",
            "views": {"$gte": 1000},
            "tags": {"$in": ["python"]}
        }
        self.assertTrue(self.doc.matches_filter(filters))
    
    def test_empty_filter(self):
        self.assertTrue(self.doc.matches_filter({}))
        self.assertTrue(self.doc.matches_filter(None))
    
    def test_invalid_doc(self):
        with self.assertRaises(ValueError):
            Document(doc_id="", content="test")
        with self.assertRaises(ValueError):
            Document(doc_id="d1", content="")


class TestBM25Index(unittest.TestCase):
    """测试 BM25 检索索引"""
    
    def setUp(self):
        self.docs = [
            Document("d1", "machine learning algorithms for classification",
                     {"category": "ml", "date": "2024-01-01"}),
            Document("d2", "deep learning neural networks",
                     {"category": "ml", "date": "2024-03-01"}),
            Document("d3", "web development with Python Flask",
                     {"category": "web", "date": "2024-02-01"}),
            Document("d4", "natural language processing with transformers",
                     {"category": "nlp", "date": "2024-04-01"}),
            Document("d5", "learning Python programming basics",
                     {"category": "web", "date": "2024-05-01"}),
        ]
        self.bm25 = BM25Index(k1=1.5, b=0.75)
        self.bm25.add_documents(self.docs)
    
    def test_tokenization(self):
        tokens = BM25Index.tokenize("Hello, World! 123")
        self.assertEqual(tokens, ["hello", "world", "123"])
    
    def test_basic_search(self):
        results = self.bm25.search("machine learning")
        self.assertGreater(len(results), 0)
        # d1 should rank high for "machine learning"
        self.assertEqual(results[0][0].doc_id, "d1")
    
    def test_search_with_filter(self):
        results = self.bm25.search("learning", filters={"category": "web"})
        doc_ids = [doc.doc_id for doc, _ in results]
        # Only web category docs should be returned
        for doc_id in doc_ids:
            self.assertEqual(self.docs[["d1","d2","d3","d4","d5"].index(doc_id)].get("category"), "web")
    
    def test_empty_query(self):
        results = self.bm25.search("")
        self.assertEqual(len(results), 0)
    
    def test_no_match_query(self):
        results = self.bm25.search("zzzznonexistent")
        self.assertEqual(len(results), 0)
    
    def test_idf_computation(self):
        # IDF should be computed for all terms
        self.assertIn("learning", self.bm25.idf)
        self.assertIn("python", self.bm25.idf)
        # Terms in fewer documents should have higher IDF
        idf_python = self.bm25.idf["python"]
        idf_learning = self.bm25.idf["learning"]
        # "python" appears in 2 docs, "learning" in 3 docs
        self.assertGreater(idf_python, idf_learning)
    
    def test_top_k_limit(self):
        results = self.bm25.search("learning", top_k=2)
        self.assertLessEqual(len(results), 2)
    
    def test_term_frequency(self):
        # d1 contains "learning" once
        tf = self.bm25.get_term_freq(0, "learning")
        self.assertEqual(tf, 1)


class TestVectorIndex(unittest.TestCase):
    """测试向量语义检索"""
    
    def setUp(self):
        self.docs = [
            Document("d1", "machine learning algorithms classification"),
            Document("d2", "deep learning neural networks"),
            Document("d3", "web development Python Flask"),
            Document("d4", "natural language processing transformers"),
            Document("d5", "Python programming basics"),
        ]
        self.vi = SimpleVectorIndex()
        self.vi.add_documents(self.docs)
    
    def test_basic_search(self):
        results = self.vi.search("machine learning")
        self.assertGreater(len(results), 0)
    
    def test_cosine_similarity(self):
        v1 = {"a": 0.6, "b": 0.8}
        v2 = {"a": 0.6, "b": 0.8}
        sim = SimpleVectorIndex.cosine_similarity(v1, v2)
        self.assertAlmostEqual(sim, 1.0, places=5)
        
        v3 = {"a": 1.0}
        v4 = {"b": 1.0}
        sim2 = SimpleVectorIndex.cosine_similarity(v3, v4)
        self.assertAlmostEqual(sim2, 0.0, places=5)
    
    def test_search_with_filter(self):
        docs_with_meta = [
            Document("d1", "machine learning", {"category": "ml"}),
            Document("d2", "deep learning", {"category": "ml"}),
            Document("d3", "web development", {"category": "web"}),
        ]
        vi = SimpleVectorIndex()
        vi.add_documents(docs_with_meta)
        results = vi.search("learning", filters={"category": "web"})
        self.assertEqual(len(results), 0)
    
    def test_normalized_vectors(self):
        # All document vectors should be unit length
        for vec in self.vi.doc_vectors:
            norm = math.sqrt(sum(v ** 2 for v in vec.values()))
            if vec:  # non-empty vector
                self.assertAlmostEqual(norm, 1.0, places=5)
    
    def test_empty_query(self):
        results = self.vi.search("")
        self.assertEqual(len(results), 0)


class TestHybridSearch(unittest.TestCase):
    """测试混合搜索"""
    
    def setUp(self):
        self.docs = [
            Document("d1", "machine learning algorithms for classification",
                     {"category": "ml", "date": "2024-01-01", "tags": ["ai", "ml"]}),
            Document("d2", "deep learning neural networks architecture",
                     {"category": "ml", "date": "2024-03-01", "tags": ["ai", "dl"]}),
            Document("d3", "web development with Python Flask framework",
                     {"category": "web", "date": "2024-02-01", "tags": ["web", "python"]}),
            Document("d4", "natural language processing transformers model",
                     {"category": "nlp", "date": "2024-04-01", "tags": ["ai", "nlp"]}),
            Document("d5", "learning Python programming basics tutorial",
                     {"category": "web", "date": "2024-05-01", "tags": ["web", "python"]}),
            Document("d6", "reinforcement learning policy gradient methods",
                     {"category": "ml", "date": "2024-06-01", "tags": ["ai", "rl"]}),
            Document("d7", "computer vision image recognition CNN",
                     {"category": "cv", "date": "2024-07-01", "tags": ["ai", "cv"]}),
            Document("d8", "Python data science pandas numpy",
                     {"category": "data", "date": "2024-08-01", "tags": ["python", "data"]}),
        ]
        self.bm25 = BM25Index()
        self.bm25.add_documents(self.docs)
        self.vi = SimpleVectorIndex()
        self.vi.add_documents(self.docs)
        self.hybrid = HybridSearcher(self.bm25, self.vi)
    
    def test_rrf_fusion(self):
        bm25_results = self.bm25.search("machine learning", top_k=5)
        vector_results = self.vi.search("machine learning", top_k=5)
        fused = self.hybrid.reciprocal_rank_fusion(bm25_results, vector_results)
        
        # Fused results should have at most len(bm25) + len(vector) unique docs
        unique_ids = set(doc.doc_id for doc, _ in fused)
        self.assertLessEqual(len(unique_ids), len(bm25_results) + len(vector_results))
    
    def test_rrf_both_retrievers_agree(self):
        """当两个检索器都把同一文档排在第一位时，RRF 应给它最高分"""
        bm25_results = [(self.docs[0], 10.0)]
        vector_results = [(self.docs[0], 0.9)]
        fused = self.hybrid.reciprocal_rank_fusion(bm25_results, vector_results)
        self.assertEqual(fused[0][0].doc_id, "d1")
    
    def test_weighted_fusion(self):
        bm25_results = self.bm25.search("learning", top_k=5)
        vector_results = self.vi.search("learning", top_k=5)
        fused = self.hybrid.weighted_fusion(bm25_results, vector_results,
                                             bm25_weight=0.7, vector_weight=0.3)
        self.assertGreater(len(fused), 0)
    
    def test_weighted_fusion_invalid_weights(self):
        bm25_results = self.bm25.search("learning", top_k=5)
        vector_results = self.vi.search("learning", top_k=5)
        with self.assertRaises(ValueError):
            self.hybrid.weighted_fusion(bm25_results, vector_results,
                                        bm25_weight=0.7, vector_weight=0.5)
    
    def test_hybrid_search_rrf(self):
        results = self.hybrid.search("machine learning", top_k=3, fusion="rrf")
        self.assertLessEqual(len(results), 3)
        self.assertGreater(len(results), 0)
    
    def test_hybrid_search_weighted(self):
        results = self.hybrid.search("Python programming", top_k=3,
                                     fusion="weighted", bm25_weight=0.6, vector_weight=0.4)
        self.assertGreater(len(results), 0)
    
    def test_hybrid_search_with_filter(self):
        results = self.hybrid.search("learning", top_k=5,
                                     filters={"category": "ml"}, fusion="rrf")
        for doc, _ in results:
            self.assertEqual(doc.get("category"), "ml")
    
    def test_hybrid_search_with_tag_filter(self):
        results = self.hybrid.search("ai", top_k=5,
                                     filters={"tags": {"$in": ["ml"]}}, fusion="rrf")
        for doc, _ in results:
            self.assertIn("ml", doc.get("tags", []))
    
    def test_hybrid_search_with_date_filter(self):
        results = self.hybrid.search("learning", top_k=5,
                                     filters={"date": {"$gte": "2024-04-01"}}, fusion="rrf")
        for doc, _ in results:
            self.assertGreaterEqual(doc.get("date"), "2024-04-01")
    
    def test_unknown_fusion(self):
        with self.assertRaises(ValueError):
            self.hybrid.search("test", fusion="unknown")
    
    def test_rrf_k_parameter(self):
        """不同 k 值应产生不同的融合结果"""
        bm25_results = self.bm25.search("learning", top_k=8)
        vector_results = self.vi.search("learning", top_k=8)
        
        fused_k1 = self.hybrid.reciprocal_rank_fusion(bm25_results, vector_results, k=1)
        fused_k60 = self.hybrid.reciprocal_rank_fusion(bm25_results, vector_results, k=60)
        
        # Results should potentially differ with different k
        # At minimum, both should return results
        self.assertGreater(len(fused_k1), 0)
        self.assertGreater(len(fused_k60), 0)


class TestPostFiltering(unittest.TestCase):
    """测试 Post-filtering 模式"""
    
    def setUp(self):
        self.docs = [
            Document("d1", "machine learning algorithms", {"category": "ml"}),
            Document("d2", "deep learning networks", {"category": "ml"}),
            Document("d3", "web development Python", {"category": "web"}),
            Document("d4", "learning Python basics", {"category": "web"}),
            Document("d5", "reinforcement learning", {"category": "ml"}),
        ]
        self.bm25 = BM25Index()
        self.bm25.add_documents(self.docs)
        self.vi = SimpleVectorIndex()
        self.vi.add_documents(self.docs)
        self.post_filter = PostFilterHybridSearcher(self.bm25, self.vi)
    
    def test_post_filter_search(self):
        results = self.post_filter.search("learning", top_k=5,
                                           filters={"category": "ml"}, fusion="rrf")
        for doc, _ in results:
            self.assertEqual(doc.get("category"), "ml")
    
    def test_post_filter_returns_fewer(self):
        """Post-filtering 可能返回少于 top_k 的结果"""
        # Only 2 web docs, requesting top_k=5
        results = self.post_filter.search("learning", top_k=5,
                                           filters={"category": "web"}, fusion="rrf")
        self.assertLessEqual(len(results), 2)
    
    def test_post_filter_no_filter(self):
        """无过滤条件时应返回全部结果"""
        results = self.post_filter.search("learning", top_k=5, filters=None, fusion="rrf")
        self.assertGreater(len(results), 0)


class TestPipeline(unittest.TestCase):
    """测试端到端 Pipeline"""
    
    def setUp(self):
        self.docs = [
            Document("d1", "Python web development Flask Django",
                     {"category": "web", "date": "2024-01-15", "tags": ["python", "web"]}),
            Document("d2", "machine learning scikit-learn TensorFlow",
                     {"category": "ml", "date": "2024-02-20", "tags": ["python", "ml"]}),
            Document("d3", "data analysis pandas numpy visualization",
                     {"category": "data", "date": "2024-03-10", "tags": ["python", "data"]}),
            Document("d4", "natural language processing spaCy NLTK",
                     {"category": "nlp", "date": "2024-04-05", "tags": ["python", "nlp"]}),
            Document("d5", "Python automation scripting DevOps",
                     {"category": "devops", "date": "2024-05-12", "tags": ["python", "automation"]}),
            Document("d6", "deep learning PyTorch neural networks",
                     {"category": "ml", "date": "2024-06-18", "tags": ["python", "ml"]}),
            Document("d7", "web scraping BeautifulSoup Selenium",
                     {"category": "web", "date": "2024-07-22", "tags": ["python", "scraping"]}),
            Document("d8", "database SQL PostgreSQL MongoDB",
                     {"category": "data", "date": "2024-08-30", "tags": ["python", "database"]}),
        ]
    
    def test_pre_filtering_pipeline(self):
        pipeline = HybridSearchPipeline(filtering_mode="pre")
        pipeline.add_documents(self.docs)
        
        results = pipeline.search("learning", top_k=3, filters={"category": "ml"})
        self.assertGreater(len(results), 0)
        for doc, _ in results:
            self.assertEqual(doc.get("category"), "ml")
    
    def test_post_filtering_pipeline(self):
        pipeline = HybridSearchPipeline(filtering_mode="post")
        pipeline.add_documents(self.docs)
        
        results = pipeline.search("learning", top_k=3, filters={"category": "ml"})
        self.assertGreater(len(results), 0)
        for doc, _ in results:
            self.assertEqual(doc.get("category"), "ml")
    
    def test_search_with_explanation(self):
        pipeline = HybridSearchPipeline()
        pipeline.add_documents(self.docs)
        
        result = pipeline.search_with_explanation("machine learning", top_k=3)
        
        self.assertEqual(result["query"], "machine learning")
        self.assertIn("bm25_results", result)
        self.assertIn("vector_results", result)
        self.assertIn("fused_results", result)
        self.assertIn("top_documents", result)
        self.assertGreater(len(result["fused_results"]), 0)
    
    def test_pipeline_not_indexed(self):
        pipeline = HybridSearchPipeline()
        with self.assertRaises(RuntimeError):
            pipeline.search("test")
    
    def test_multi_filter_search(self):
        pipeline = HybridSearchPipeline()
        pipeline.add_documents(self.docs)
        
        filters = {
            "category": "ml",
            "date": {"$gte": "2024-03-01"},
            "tags": {"$in": ["ml"]}
        }
        results = pipeline.search("learning", top_k=5, filters=filters)
        
        for doc, _ in results:
            self.assertEqual(doc.get("category"), "ml")
            self.assertGreaterEqual(doc.get("date"), "2024-03-01")
            self.assertIn("ml", doc.get("tags", []))
    
    def test_rrf_vs_weighted_difference(self):
        """RRF 和 Weighted 融合可能产生不同排序"""
        pipeline = HybridSearchPipeline()
        pipeline.add_documents(self.docs)
        
        rrf_results = pipeline.search("Python learning", top_k=5, fusion="rrf")
        weighted_results = pipeline.search("Python learning", top_k=5, fusion="weighted",
                                            bm25_weight=0.3, vector_weight=0.7)
        
        # Both should return results
        self.assertGreater(len(rrf_results), 0)
        self.assertGreater(len(weighted_results), 0)
        
        # The set of returned doc IDs should be the same (from same candidate pool)
        rrf_ids = set(doc.doc_id for doc, _ in rrf_results)
        weighted_ids = set(doc.doc_id for doc, _ in weighted_results)
        # They may differ slightly but should overlap significantly
        overlap = rrf_ids & weighted_ids
        self.assertGreater(len(overlap), 0)


# ============================================================================
# 主程序: 演示
# ============================================================================

def demo():
    """混合搜索演示"""
    print("=" * 70)
    print("RAG 练习题 4: 元数据过滤 + 混合搜索")
    print("=" * 70)
    
    # 创建示例文档
    documents = [
        Document("d1", "Python web development with Flask and Django frameworks",
                 {"category": "web", "date": "2024-01-15", "tags": ["python", "web"],
                  "author": "Alice", "views": 3200}),
        Document("d2", "Introduction to machine learning with scikit-learn",
                 {"category": "ml", "date": "2024-02-20", "tags": ["python", "ml"],
                  "author": "Bob", "views": 5100}),
        Document("d3", "Data analysis and visualization with pandas numpy matplotlib",
                 {"category": "data", "date": "2024-03-10", "tags": ["python", "data"],
                  "author": "Charlie", "views": 2800}),
        Document("d4", "Natural language processing using transformers and spaCy",
                 {"category": "nlp", "date": "2024-04-05", "tags": ["python", "nlp"],
                  "author": "Alice", "views": 4100}),
        Document("d5", "Deep learning neural networks with PyTorch",
                 {"category": "ml", "date": "2024-06-18", "tags": ["python", "ml"],
                  "author": "Bob", "views": 6700}),
        Document("d6", "Web scraping automation with BeautifulSoup and Selenium",
                 {"category": "web", "date": "2024-07-22", "tags": ["python", "scraping"],
                  "author": "Diana", "views": 1900}),
        Document("d7", "Database design and SQL optimization PostgreSQL",
                 {"category": "data", "date": "2024-08-30", "tags": ["python", "database"],
                  "author": "Charlie", "views": 3500}),
        Document("d8", "DevOps CI CD pipeline automation with Python",
                 {"category": "devops", "date": "2024-09-15", "tags": ["python", "automation"],
                  "author": "Diana", "views": 2200}),
    ]
    
    # 构建 Pipeline
    pipeline = HybridSearchPipeline(filtering_mode="pre")
    pipeline.add_documents(documents)
    
    # 演示 1: 基本混合搜索
    print("\n--- 演示 1: 基本混合搜索 (RRF) ---")
    print(f"查询: 'machine learning Python'")
    results = pipeline.search("machine learning Python", top_k=3, fusion="rrf")
    for i, (doc, score) in enumerate(results, 1):
        print(f"  {i}. [{doc.doc_id}] score={score:.4f} | {doc.content[:60]}...")
    
    # 演示 2: 带元数据过滤
    print("\n--- 演示 2: 元数据过滤 (category=ml) ---")
    print(f"查询: 'learning' | 过滤: category=ml")
    results = pipeline.search("learning", top_k=5, filters={"category": "ml"})
    for i, (doc, score) in enumerate(results, 1):
        print(f"  {i}. [{doc.doc_id}] score={score:.4f} | cat={doc.get('category')} | {doc.content[:50]}...")
    
    # 演示 3: 多条件过滤
    print("\n--- 演示 3: 多条件过滤 ---")
    filters = {
        "date": {"$gte": "2024-04-01"},
        "tags": {"$in": ["ml", "nlp"]},
        "views": {"$gte": 3000}
    }
    print(f"查询: 'Python' | 过滤: date>=2024-04, tags in [ml,nlp], views>=3000")
    results = pipeline.search("Python", top_k=5, filters=filters)
    for i, (doc, score) in enumerate(results, 1):
        print(f"  {i}. [{doc.doc_id}] score={score:.4f} | {doc.get('date')} | views={doc.get('views')} | {doc.content[:40]}...")
    
    # 演示 4: RRF vs Weighted 对比
    print("\n--- 演示 4: RRF vs Weighted 融合对比 ---")
    explanation = pipeline.search_with_explanation("deep learning neural networks", top_k=3)
    print(f"查询: '{explanation['query']}'")
    print(f"  BM25 结果:    {explanation['bm25_results']}")
    print(f"  向量检索结果:  {explanation['vector_results']}")
    print(f"  RRF 融合结果:  {explanation['fused_results']}")
    
    # 演示 5: Post-filtering
    print("\n--- 演示 5: Post-filtering 模式 ---")
    post_pipeline = HybridSearchPipeline(filtering_mode="post")
    post_pipeline.add_documents(documents)
    print(f"查询: 'Python' | 过滤: category=web | 模式: post-filtering")
    results = post_pipeline.search("Python", top_k=5, filters={"category": "web"})
    print(f"  返回 {len(results)} 条结果 (web 类文档共2条)")
    for i, (doc, score) in enumerate(results, 1):
        print(f"  {i}. [{doc.doc_id}] score={score:.4f} | {doc.content[:50]}...")
    
    print("\n" + "=" * 70)
    print("演示完成!")
    print("=" * 70)


if __name__ == "__main__":
    demo()
    print("\n运行测试...\n")
    unittest.main(verbosity=2, exit=False)
