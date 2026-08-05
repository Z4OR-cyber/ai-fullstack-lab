"""向量检索器模块

基于TF-IDF和余弦相似度实现纯numpy向量检索。
无需外部API Key或预训练模型，完全使用Python标准库和numpy实现。

核心组件：
- TFIDFVectorizer: 将文本转为TF-IDF向量
- VectorRetriever: 构建向量索引并执行相似度检索

参考实现来自 python_exercises/27_rag_system.py 中的 TF-IDF 和余弦相似度方法。
"""

import re
from collections import Counter
from typing import List, Dict, Tuple, Optional

import numpy as np


def tokenize(text: str) -> List[str]:
    """文本分词器

    对中文和英文混合文本进行分词：
    - 英文：按单词切分（连续字母序列）
    - 中文：按单字切分（每个中文字符为一个词）
    - 数字：连续数字作为一个词

    这种分词策略适合TF-IDF在中文知识库上的应用，
    虽然不如专业分词器精确，但无需外部依赖。

    Args:
        text: 输入文本

    Returns:
        分词后的词列表
    """
    text = text.lower()
    # 匹配：英文单词(含数字，如md5/sha256/bcrypt) | 中文字符
    tokens = re.findall(r'[a-z\d]+|[\u4e00-\u9fff]', text)
    return tokens


class TFIDFVectorizer:
    """TF-IDF向量化器（纯numpy实现）

    将文本转换为TF-IDF向量。TF-IDF = TF × IDF，
    其中TF是词频，IDF是逆文档频率。

    工作流程：
    1. fit(): 从文档集合构建词汇表和IDF权重
    2. transform(): 将新文本转为TF-IDF向量

    用法:
        vectorizer = TFIDFVectorizer()
        vectorizer.fit(["文档1内容", "文档2内容"])
        vec = vectorizer.transform("查询文本")
    """

    def __init__(self):
        """初始化向量化器"""
        self.vocabulary: Dict[str, int] = {}
        self.idf: Optional[np.ndarray] = None
        self._fitted = False

    @property
    def vocab_size(self) -> int:
        """词汇表大小"""
        return len(self.vocabulary)

    def fit(self, documents: List[str]) -> "TFIDFVectorizer":
        """拟合：从文档集合构建词汇表和IDF权重

        Args:
            documents: 文档文本列表

        Returns:
            self（支持链式调用）
        """
        # 构建词汇表
        all_words: set = set()
        for doc in documents:
            all_words.update(tokenize(doc))

        self.vocabulary = {word: i for i, word in enumerate(sorted(all_words))}

        if not self.vocabulary:
            self.idf = np.zeros(0)
            self._fitted = True
            return self

        # 计算IDF：log(N / (1 + DF))
        N = len(documents)
        df = np.zeros(len(self.vocabulary))
        for doc in documents:
            tokens = set(tokenize(doc))
            for word in tokens:
                if word in self.vocabulary:
                    df[self.vocabulary[word]] += 1

        self.idf = np.log(N / (1 + df))
        self._fitted = True
        return self

    def transform(self, text: str) -> np.ndarray:
        """将文本转换为TF-IDF向量

        Args:
            text: 输入文本

        Returns:
            TF-IDF向量（L2归一化后的numpy数组）
        """
        if not self._fitted or not self.vocabulary:
            return np.zeros(0)

        vec = np.zeros(len(self.vocabulary))
        tokens = tokenize(text)
        if not tokens:
            return vec

        # 计算TF（词频）
        counter = Counter(tokens)
        total = len(tokens)
        for word, count in counter.items():
            if word in self.vocabulary:
                tf = count / total
                vec[self.vocabulary[word]] = tf * self.idf[self.vocabulary[word]]

        # L2归一化，使余弦相似度等于点积
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm

        return vec

    def fit_transform(self, documents: List[str]) -> np.ndarray:
        """拟合并转换：一步完成训练和向量化

        Args:
            documents: 文档文本列表

        Returns:
            TF-IDF矩阵，形状为 (文档数, 词汇表大小)
        """
        self.fit(documents)
        return np.array([self.transform(doc) for doc in documents])


class VectorRetriever:
    """向量检索器

    基于TF-IDF向量化和余弦相似度，从知识分块中检索最相关的内容。

    工作流程：
    1. build_index(): 接收知识分块列表，构建TF-IDF向量索引
    2. search(): 接收查询文本，返回最相关的Top-K知识分块

    用法:
        retriever = VectorRetriever()
        retriever.build_index(chunks)
        results = retriever.search("SQL注入修复", top_k=5)
    """

    def __init__(self):
        """初始化检索器"""
        self.vectorizer = TFIDFVectorizer()
        self._chunks: List[Dict] = []
        self._doc_vectors: Optional[np.ndarray] = None
        self._built = False

    @property
    def is_built(self) -> bool:
        """索引是否已构建"""
        return self._built

    @property
    def chunk_count(self) -> int:
        """索引中的分块数量"""
        return len(self._chunks)

    def build_index(self, chunks: List) -> None:
        """构建向量索引

        将知识分块列表转换为TF-IDF向量矩阵，用于后续检索。

        Args:
            chunks: 知识分块列表（KnowledgeChunk对象或含text字段的字典）
        """
        self._chunks = []
        texts = []

        for chunk in chunks:
            # 兼容 KnowledgeChunk 对象和字典
            if hasattr(chunk, "text"):
                text = chunk.text
                doc_id = chunk.doc_id
                title = chunk.title
                chunk_id = chunk.chunk_id
            else:
                text = chunk.get("text", "")
                doc_id = chunk.get("doc_id", "")
                title = chunk.get("title", "")
                chunk_id = chunk.get("chunk_id", "")

            # 构建检索文本：标题 + 正文，提高标题权重
            search_text = f"{title} {title} {text}"
            self._chunks.append({
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "title": title,
                "text": text,
            })
            texts.append(search_text)

        if not texts:
            self._doc_vectors = np.zeros((0, 0))
            self._built = True
            return

        # 构建TF-IDF向量矩阵
        self._doc_vectors = self.vectorizer.fit_transform(texts)
        self._built = True

    def search(self, query: str, top_k: int = 5,
               min_score: float = 0.001) -> List[Dict]:
        """检索最相关的知识分块

        将查询文本转为TF-IDF向量，与所有知识分块计算余弦相似度，
        返回相似度最高的Top-K结果。

        由于TF-IDF向量已L2归一化，余弦相似度等于向量点积。

        Args:
            query: 查询文本
            top_k: 返回的最大结果数
            min_score: 最小相似度阈值，低于此值不返回

        Returns:
            检索结果列表，每项包含 chunk_id, doc_id, title, text, score
        """
        if not self._built or self._doc_vectors is None or len(self._chunks) == 0:
            return []

        # 将查询转为TF-IDF向量
        query_vec = self.vectorizer.transform(query)
        if query_vec.size == 0 or np.linalg.norm(query_vec) == 0:
            return []

        # 计算余弦相似度（向量已归一化，点积即为余弦相似度）
        scores = self._doc_vectors @ query_vec

        # 按相似度降序排序
        ranked_indices = np.argsort(scores)[::-1]

        results = []
        for idx in ranked_indices[:top_k]:
            score = float(scores[idx])
            if score < min_score:
                break
            chunk = self._chunks[idx]
            results.append({
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "title": chunk["title"],
                "text": chunk["text"],
                "score": score,
            })

        return results

    def search_by_doc(self, query: str, doc_id: str,
                      top_k: int = 3, min_score: float = 0.001) -> List[Dict]:
        """在指定文档范围内检索

        仅在指定规则ID的知识分块中检索，适用于已知漏洞类型时的精准检索。

        Args:
            query: 查询文本
            doc_id: 文档ID（规则ID），如 "SC001"
            top_k: 返回的最大结果数
            min_score: 最小相似度阈值

        Returns:
            检索结果列表
        """
        if not self._built or self._doc_vectors is None or len(self._chunks) == 0:
            return []

        query_vec = self.vectorizer.transform(query)
        if query_vec.size == 0 or np.linalg.norm(query_vec) == 0:
            return []

        scores = self._doc_vectors @ query_vec

        # 过滤指定文档的分块
        filtered = [
            (i, float(scores[i]))
            for i in range(len(self._chunks))
            if self._chunks[i]["doc_id"] == doc_id
        ]

        # 按分数排序
        filtered.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in filtered[:top_k]:
            if score < min_score:
                break
            chunk = self._chunks[idx]
            results.append({
                "chunk_id": chunk["chunk_id"],
                "doc_id": chunk["doc_id"],
                "title": chunk["title"],
                "text": chunk["text"],
                "score": score,
            })

        return results
