#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阶段十二：RAG 检索增强生成 — 10 道练习题
==========================================
覆盖向量嵌入、语义搜索、向量数据库、文档分块、混合检索、
端到端 RAG Pipeline、RAGAS 评估、Agent+RAG 融合等核心主题。

运行环境：Python 3.13.x + numpy + scipy + matplotlib
作者：koze（AI 全栈学习笔记）
"""

import os
import re
import math
import json
import time
import hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from collections import Counter, defaultdict

# 可视化图片保存目录
FIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ai_math", "figures_rag")
os.makedirs(FIG_DIR, exist_ok=True)

# 设置字体（兼容不同环境，抑制字体未找到警告）
import logging
logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)
import warnings
warnings.filterwarnings('ignore', message='.*font.*')
plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


# ============================================================
# 第 1 题：向量嵌入与语义搜索 — Embedding 原理
# ============================================================
"""
知识点讲解
-----------

1. 什么是向量嵌入（Embedding）？
   向量嵌入是将文本、图片等非结构化数据映射到高维向量空间的过程。
   核心思想：语义相近的内容在向量空间中距离也近。
   例如 "猫" 和 "狗" 的向量距离会比 "猫" 和 "汽车" 更近。
   常见的嵌入方法有：TF-IDF、Word2Vec、BERT Embedding 等。

2. 三种常见距离/相似度度量：
   - 余弦相似度：衡量向量方向的一致性，取值 [-1, 1]，越接近 1 越相似。
     公式：cos(A, B) = (A · B) / (||A|| × ||B||)
   - 点积：A · B = Σ(ai × bi)，没有归一化，受向量长度影响。
   - 欧式距离：d(A, B) = √(Σ(ai - bi)²)，衡量绝对距离，取值 [0, +∞)。

3. TF-IDF 向量化原理：
   - TF（词频）：某词在文档中出现的频率，TF = 词出现次数 / 文档总词数
   - IDF（逆文档频率）：衡量词的区分能力，IDF = log(N / (1 + DF))
     其中 N 是文档总数，DF 是包含该词的文档数
   - TF-IDF = TF × IDF，高频且稀有的词得分高

4. 语义搜索流程：
   将查询和文档都转换为 TF-IDF 向量 → 计算余弦相似度 → 按相似度排序。
   虽然 TF-IDF 是词袋模型，不理解语义，但它是理解 Embedding 的最佳起点。

5. 可视化向量空间：
   通过降维（如 SVD 奇异值分解）将高维向量投影到 2D 平面，
   直观观察文档在向量空间中的分布和聚类关系。
"""


def exercise_01():
    """第 1 题：向量嵌入与语义搜索"""

    # ---- 1.1 准备语料库 ----
    documents = [
        "Python is a popular programming language for data science",
        "Machine learning models need large datasets for training",
        "The cat sits on the mat in the living room",
        "Deep learning uses neural networks to learn patterns",
        "A dog runs quickly across the green park",
        "Natural language processing analyzes text data",
        "Cats and dogs are common household pets",
        "Python web frameworks include Django and Flask",
    ]

    # ---- 1.2 TF-IDF 向量化（纯 numpy 实现）----
    def tokenize(text):
        """简单分词：转小写 + 按空格分割"""
        return text.lower().split()

    # 构建词汇表
    all_tokens = []
    for doc in documents:
        all_tokens.extend(tokenize(doc))
    vocab = sorted(set(all_tokens))
    vocab_index = {word: i for i, word in enumerate(vocab)}
    print(f"词汇表大小: {len(vocab)}")

    # 计算 TF（词频）
    def compute_tf(tokens, vocab_idx):
        tf = np.zeros(len(vocab_idx))
        counter = Counter(tokens)
        total = len(tokens)
        for word, count in counter.items():
            if word in vocab_idx:
                tf[vocab_idx[word]] = count / total
        return tf

    # 计算 IDF（逆文档频率）
    N = len(documents)
    df = np.zeros(len(vocab))
    for doc in documents:
        tokens = set(tokenize(doc))
        for word in tokens:
            if word in vocab_index:
                df[vocab_index[word]] += 1
    idf = np.log(N / (1 + df))

    # 构建 TF-IDF 矩阵
    tfidf_matrix = np.zeros((N, len(vocab)))
    for i, doc in enumerate(documents):
        tfidf_matrix[i] = compute_tf(tokenize(doc), vocab_index) * idf

    print(f"TF-IDF 矩阵形状: {tfidf_matrix.shape}")

    # ---- 1.3 三种相似度度量对比 ----
    def cosine_similarity(a, b):
        """余弦相似度"""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return np.dot(a, b) / (norm_a * norm_b)

    def dot_product(a, b):
        """点积"""
        return np.dot(a, b)

    def euclidean_distance(a, b):
        """欧式距离"""
        return np.linalg.norm(a - b)

    # 查询文本
    query = "Python programming language"
    query_vec = compute_tf(tokenize(query), vocab_index) * idf

    print(f"\n查询: '{query}'")
    print(f"{'文档':>4} | {'余弦相似度':>12} | {'点积':>10} | {'欧式距离':>10} | 内容预览")
    print("-" * 90)

    results = []
    for i, doc in enumerate(documents):
        cos_sim = cosine_similarity(query_vec, tfidf_matrix[i])
        dot = dot_product(query_vec, tfidf_matrix[i])
        euc = euclidean_distance(query_vec, tfidf_matrix[i])
        results.append((i, cos_sim, doc))
        print(f"{i:>4} | {cos_sim:>12.6f} | {dot:>10.6f} | {euc:>10.6f} | {doc[:40]}")

    # 按余弦相似度排序
    results.sort(key=lambda x: x[1], reverse=True)
    print("\n按余弦相似度排序（Top-3）:")
    for rank, (idx, sim, doc) in enumerate(results[:3], 1):
        print(f"  #{rank}: [sim={sim:.4f}] {doc}")

    # ---- 1.4 可视化向量空间（SVD 降维到 2D）----
    # 使用 SVD 将高维 TF-IDF 向量降维到 2D
    U, S, Vt = np.linalg.svd(tfidf_matrix, full_matrices=False)
    coords_2d = U[:, :2] * S[:2]  # 取前两个主成分

    # 查询文本也降维
    query_2d = query_vec @ Vt[:2].T

    fig, ax = plt.subplots(figsize=(10, 7))
    colors = plt.cm.Set2(np.linspace(0, 1, len(documents)))
    for i, (x, y) in enumerate(coords_2d):
        ax.scatter(x, y, c=[colors[i]], s=120, zorder=5)
        ax.annotate(f"D{i}: {documents[i][:25]}...", (x, y),
                    fontsize=7, xytext=(5, 5), textcoords='offset points')
    # 标记查询
    ax.scatter(query_2d[0], query_2d[1], c='red', s=200, marker='*', zorder=10,
               label=f'Query: "{query}"')
    ax.annotate('Query', (query_2d[0], query_2d[1]), fontsize=9,
                xytext=(10, 10), textcoords='offset points', color='red')

    # 画查询到各文档的连线
    for i, (x, y) in enumerate(coords_2d):
        sim = cosine_similarity(query_vec, tfidf_matrix[i])
        if sim > 0.01:
            ax.plot([query_2d[0], x], [query_2d[1], y],
                    'r--', alpha=min(sim * 3, 0.6), linewidth=0.8)

    ax.set_title('TF-IDF Vector Space (SVD 2D Projection)', fontsize=14)
    ax.set_xlabel('Principal Component 1')
    ax.set_ylabel('Principal Component 2')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, 'ex01_vector_space.png'), dpi=150)
    plt.close()
    print(f"\n[图] 向量空间可视化已保存: {FIG_DIR}/ex01_vector_space.png")

    # ---- 思考题 ----
    print("\n" + "=" * 60)
    print("思考题：")
    print("1. 余弦相似度和欧式距离在什么场景下各有优势？")
    print("   提示：考虑向量长度是否代表重要信息。")
    print("2. TF-IDF 的主要局限是什么？如何改进？")
    print("   提示：词袋模型忽略了词序和语义。")
    print("3. 如果词汇表有 10 万个词，TF-IDF 向量会非常稀疏，")
    print("   有什么方法可以降低维度？")
    print("=" * 60)


# ============================================================
# 第 2 题：RAG 架构全貌 — 从文档到回答
# ============================================================
"""
知识点讲解
-----------

1. RAG（Retrieval-Augmented Generation）三阶段架构：
   RAG 将"检索"和"生成"结合，分为三大阶段：

   阶段一 — Indexing（索引）：
     Load（加载文档）→ Split（分块）→ Embed（向量化）→ Store（存储到向量库）
     这一步是离线预处理，构建可检索的知识库。

   阶段二 — Retrieval（检索）：
     Query（用户提问）→ Embed（查询向量化）→ Search（向量搜索）→ Rank（重排序）
     从知识库中检索与问题最相关的文档片段。

   阶段三 — Generation（生成）：
     Context（拼接检索结果）→ Prompt（构造提示词）→ LLM（大模型生成回答）
     将检索到的上下文和问题一起送入 LLM 生成最终回答。

2. 为什么需要 RAG？
   - 解决 LLM 知识滞后问题（训练数据有截止日期）
   - 减少幻觉（Hallucination）：有据可依
   - 支持私有数据：企业内部文档无需微调模型
   - 可追溯：回答附带来源引用

3. 本题实现一个最简 RAG Pipeline：
   不调用真实 LLM API，用"模板匹配 + 关键词提取"模拟生成模块。
   重点理解数据流转和各模块职责，而非生成质量。

4. RAG vs Fine-tuning：
   - RAG：外部知识注入，无需重新训练，适合频繁更新的知识
   - Fine-tuning：内化知识到模型参数，适合风格/格式学习
   - 两者可以组合使用

5. 数据流图：
   本题将用 matplotlib 绘制完整的 RAG 数据流图，帮助理解架构。
"""


def exercise_02():
    """第 2 题：RAG 架构全貌"""

    # ---- 2.1 最简 RAG Pipeline ----

    class SimpleRAG:
        """最简 RAG 系统（纯 Python 实现，不依赖 LLM API）"""

        def __init__(self):
            self.documents = []
            self.embeddings = []
            self.vocabulary = {}

        # === Indexing 阶段 ===
        def load(self, texts):
            """Load: 加载文档"""
            self.documents = texts
            print(f"  [Indexing] 加载了 {len(texts)} 篇文档")

        def split(self, text, chunk_size=50, overlap=10):
            """Split: 按字符长度分块"""
            chunks = []
            start = 0
            while start < len(text):
                end = start + chunk_size
                chunk = text[start:end]
                chunks.append(chunk)
                start = end - overlap  # 重叠部分
            return chunks

        def build_vocab(self):
            """构建词汇表"""
            all_words = set()
            for doc in self.documents:
                all_words.update(doc.lower().split())
            self.vocabulary = {word: i for i, word in enumerate(sorted(all_words))}

        def embed(self, text):
            """Embed: 简单的 TF 向量化"""
            vec = np.zeros(len(self.vocabulary))
            for word in text.lower().split():
                if word in self.vocabulary:
                    vec[self.vocabulary[word]] += 1
            # L2 归一化
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec

        def store(self):
            """Store: 存储所有文档的向量"""
            self.embeddings = np.array([self.embed(doc) for doc in self.documents])
            print(f"  [Indexing] 存储向量矩阵: {self.embeddings.shape}")

        # === Retrieval 阶段 ===
        def retrieve(self, query, top_k=3):
            """检索：计算余弦相似度，返回 Top-K"""
            query_vec = self.embed(query)
            # 余弦相似度（向量已归一化，点积即为余弦相似度）
            scores = self.embeddings @ query_vec
            ranked = np.argsort(scores)[::-1][:top_k]
            results = []
            for idx in ranked:
                results.append({
                    'doc_id': int(idx),
                    'score': float(scores[idx]),
                    'text': self.documents[idx]
                })
            print(f"  [Retrieval] 查询: '{query}' → Top-{top_k} 检索完成")
            for r in results:
                print(f"    [score={r['score']:.4f}] {r['text'][:50]}...")
            return results

        # === Generation 阶段（模板匹配模拟）===
        def generate(self, query, retrieved_docs):
            """生成：用模板匹配模拟 LLM 生成"""
            print(f"  [Generation] 基于 {len(retrieved_docs)} 条检索结果生成回答...")

            # 提取检索文档中的关键词
            context_words = set()
            for doc in retrieved_docs:
                context_words.update(doc['text'].lower().split())

            # 查询关键词
            query_words = set(query.lower().split())
            # 匹配到的关键词
            matched = query_words & context_words

            # 构造回答（模拟 LLM 生成）
            answer = f"根据知识库检索结果，关于「{query}」的回答如下：\n"
            answer += f"匹配到 {len(matched)} 个关键词：{', '.join(sorted(matched))}\n"
            answer += "参考来源：\n"
            for doc in retrieved_docs[:2]:
                answer += f"  - [文档{doc['doc_id']}, 相关度={doc['score']:.2f}] {doc['text'][:60]}...\n"
            return answer

        def query_pipeline(self, question, top_k=3):
            """完整 RAG 查询流程"""
            print(f"\n>>> 用户提问: {question}")
            # Retrieval
            retrieved = self.retrieve(question, top_k=top_k)
            # Generation
            answer = self.generate(question, retrieved)
            print(f"\n--- RAG 回答 ---\n{answer}")
            return answer

    # ---- 2.2 运行 RAG Pipeline ----
    print("=" * 60)
    print("最简 RAG Pipeline 演示")
    print("=" * 60)

    rag = SimpleRAG()

    # 知识库文档
    knowledge_base = [
        "Python is a versatile programming language used for web development data science and automation",
        "Machine learning is a subset of artificial intelligence that enables systems to learn from data",
        "Vector databases store high dimensional vectors for similarity search in RAG applications",
        "TF-IDF is a numerical statistic that reflects how important a word is to a document in a collection",
        "Chroma is an open source vector database designed for AI applications with embedding storage",
        "Embedding models convert text into dense vectors capturing semantic meaning for retrieval tasks",
    ]

    # Indexing
    rag.load(knowledge_base)
    rag.build_vocab()
    rag.store()

    # 查询演示
    rag.query_pipeline("What is vector database?")
    rag.query_pipeline("How does Python work?")

    # ---- 2.3 绘制 RAG 数据流图 ----
    fig, ax = plt.subplots(figsize=(16, 8))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 8)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.set_title('RAG Architecture: End-to-End Data Flow', fontsize=16, fontweight='bold')

    # 绘制方框的辅助函数
    def draw_box(ax, x, y, w, h, text, color='#4ECDC4', fontsize=9):
        rect = plt.Rectangle((x, y), w, h, facecolor=color, edgecolor='#2C3E50',
                              linewidth=1.5, alpha=0.85, zorder=2)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, text, ha='center', va='center',
                fontsize=fontsize, fontweight='bold', color='white', zorder=3)

    def draw_arrow(ax, x1, y1, x2, y2):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='->', color='#2C3E50', lw=2), zorder=1)

    # === Indexing 阶段 ===
    ax.text(2.5, 7.5, 'Stage 1: Indexing', ha='center', fontsize=12, fontweight='bold', color='#2C3E50')
    draw_box(ax, 0.3, 5.5, 1.5, 1, 'Load\nDocuments', '#3498DB')
    draw_box(ax, 2.3, 5.5, 1.5, 1, 'Split\n(Chunking)', '#3498DB')
    draw_box(ax, 4.3, 5.5, 1.5, 1, 'Embed\n(Vectors)', '#3498DB')
    draw_box(ax, 6.3, 5.5, 1.5, 1, 'Store\n(Vector DB)', '#2980B9')
    draw_arrow(ax, 1.8, 6.0, 2.3, 6.0)
    draw_arrow(ax, 3.8, 6.0, 4.3, 6.0)
    draw_arrow(ax, 5.8, 6.0, 6.3, 6.0)

    # === Retrieval 阶段 ===
    ax.text(2.5, 4.3, 'Stage 2: Retrieval', ha='center', fontsize=12, fontweight='bold', color='#2C3E50')
    draw_box(ax, 0.3, 2.3, 1.5, 1, 'User\nQuery', '#E67E22')
    draw_box(ax, 2.3, 2.3, 1.5, 1, 'Query\nEmbed', '#E67E22')
    draw_box(ax, 4.3, 2.3, 1.5, 1, 'Vector\nSearch', '#E67E22')
    draw_box(ax, 6.3, 2.3, 1.5, 1, 'Rank\n(Top-K)', '#D35400')
    draw_arrow(ax, 1.8, 2.8, 2.3, 2.8)
    draw_arrow(ax, 3.8, 2.8, 4.3, 2.8)
    draw_arrow(ax, 5.8, 2.8, 6.3, 2.8)

    # Vector DB → Search 的连线
    draw_arrow(ax, 7.0, 5.5, 5.0, 3.3)

    # === Generation 阶段 ===
    ax.text(12.5, 7.5, 'Stage 3: Generation', ha='center', fontsize=12, fontweight='bold', color='#2C3E50')
    draw_box(ax, 10.3, 5.5, 1.8, 1, 'Context\nAssembly', '#27AE60')
    draw_box(ax, 12.5, 5.5, 1.8, 1, 'Prompt\nTemplate', '#27AE60')
    draw_box(ax, 14.3, 5.5, 1.5, 1, 'LLM\nGenerate', '#229954')
    draw_arrow(ax, 12.1, 6.0, 12.5, 6.0)
    draw_arrow(ax, 14.3, 6.0, 14.3, 6.0)

    # Rank → Context 的连线
    draw_arrow(ax, 7.0, 2.8, 10.3, 5.5)
    ax.text(8.8, 4.5, 'Top-K\nDocs', ha='center', fontsize=8, color='#7F8C8D',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#ECF0F1', alpha=0.8))

    # Query → Prompt 的连线
    draw_arrow(ax, 1.0, 2.3, 13.0, 5.5)

    # 输出
    draw_box(ax, 14.0, 2.5, 1.8, 1, 'Answer +\nSources', '#8E44AD')
    draw_arrow(ax, 15.0, 5.5, 15.0, 3.5)

    # 阶段分隔线
    ax.axhline(y=4.8, xmin=0.02, xmax=0.55, color='#BDC3C7', linestyle='--', alpha=0.5)
    ax.axhline(y=4.8, xmin=0.60, xmax=0.98, color='#BDC3C7', linestyle='--', alpha=0.5)

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, 'ex02_rag_architecture.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n[图] RAG 架构数据流图已保存: {FIG_DIR}/ex02_rag_architecture.png")

    # ---- 思考题 ----
    print("\n" + "=" * 60)
    print("思考题：")
    print("1. 如果知识库有 100 万篇文档，Indexing 阶段最耗时的步骤是什么？")
    print("   提示：Embedding 模型推理 vs 向量存储。")
    print("2. 在 Retrieval 阶段，除了向量相似度搜索，还能加入什么信息")
    print("   来提升检索质量？")
    print("   提示：关键词匹配、元数据过滤。")
    print("3. RAG 系统中，如果 LLM 忽略了检索到的上下文，如何改进？")
    print("   提示：Prompt 工程、调整上下文位置。")
    print("=" * 60)


# ============================================================
# 第 3 题：Chroma 快速上手 — 轻量向量库（纯 numpy 模拟实现）
# ============================================================
"""
知识点讲解
-----------

1. Chroma 简介：
   Chroma（ChromaDB）是开源的 AI 原生向量数据库，专为 RAG 应用设计。
   核心概念：
   - Collection：类似数据库表，存储文档和向量
   - Document：原始文本内容
   - Embedding：文本对应的向量表示
   - Metadata：键值对元数据，用于过滤
   - Embedding Function：将文本转为向量的函数

2. Chroma 的 API 设计（本题用 numpy 模拟）：
   - collection.add(documents, metadatas, ids)  — 添加文档
   - collection.query(query_texts, n_results)   — 语义查询
   - collection.get(ids)                         — 按 ID 获取
   - collection.update(ids, documents)           — 更新文档
   - collection.delete(ids)                      — 删除文档
   - collection.persist()                        — 持久化到磁盘

3. 持久化存储：
   Chroma 支持两种模式：
   - 内存模式（EphemeralClient）：数据仅在内存中，程序结束即丢失
   - 持久化模式（PersistentClient）：数据写入磁盘，重启后可恢复

4. 相似度查询：
   Chroma 默认使用余弦相似度，也支持 L2（欧式距离）和 IP（内积）。
   查询时返回 Top-K 最相似的文档及其距离/相似度分数。

5. 本题由于 chromadb 安装受限，用纯 numpy 完整模拟 Chroma 的核心功能，
   包括 Collection、Metadata 过滤、持久化等。
"""


def exercise_03():
    """第 3 题：Chroma 向量库模拟实现"""

    class ChromaCollection:
        """模拟 ChromaDB Collection 的核心功能"""

        def __init__(self, name="default"):
            self.name = name
            self.documents = []
            self.metadatas = []
            self.ids = []
            self.embeddings = []
            self.vocabulary = {}
            self.idf = None

        def _build_vocab_and_idf(self):
            """构建词汇表和 IDF"""
            all_words = set()
            for doc in self.documents:
                all_words.update(doc.lower().split())
            self.vocabulary = {word: i for i, word in enumerate(sorted(all_words))}

            N = len(self.documents)
            df = np.zeros(len(self.vocabulary))
            for doc in self.documents:
                tokens = set(doc.lower().split())
                for word in tokens:
                    if word in self.vocabulary:
                        df[self.vocabulary[word]] += 1
            self.idf = np.log(N / (1 + df))

        def _embed(self, text):
            """TF-IDF 向量化"""
            if not self.vocabulary:
                return np.zeros(0)
            vec = np.zeros(len(self.vocabulary))
            tokens = text.lower().split()
            counter = Counter(tokens)
            total = len(tokens)
            for word, count in counter.items():
                if word in self.vocabulary:
                    tf = count / total
                    vec[self.vocabulary[word]] = tf * self.idf[self.vocabulary[word]]
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec

        def add(self, documents, metadatas=None, ids=None):
            """添加文档到 Collection"""
            if ids is None:
                start = len(self.ids)
                ids = [f"doc_{start + i}" for i in range(len(documents))]
            if metadatas is None:
                metadatas = [{} for _ in documents]

            for doc, meta, doc_id in zip(documents, metadatas, ids):
                self.documents.append(doc)
                self.metadatas.append(meta)
                self.ids.append(doc_id)

            # 重建词汇表和向量
            self._build_vocab_and_idf()
            self.embeddings = [self._embed(doc) for doc in self.documents]
            print(f"  [Chroma] 添加 {len(documents)} 篇文档到 Collection '{self.name}'")
            return ids

        def query(self, query_texts=None, query_embeddings=None,
                  n_results=5, where=None):
            """语义查询：返回 Top-K 最相似文档"""
            # 计算查询向量
            if query_embeddings is not None:
                q_vecs = query_embeddings
            else:
                q_vecs = [self._embed(qt) for qt in query_texts]

            results = {'ids': [], 'documents': [], 'metadatas': [], 'distances': []}

            for q_vec in q_vecs:
                # 元数据过滤
                filtered_indices = list(range(len(self.documents)))
                if where:
                    filtered_indices = [
                        i for i in filtered_indices
                        if all(self.metadatas[i].get(k) == v for k, v in where.items())
                    ]

                # 计算余弦相似度
                scores = []
                for i in filtered_indices:
                    if len(self.embeddings[i]) == 0:
                        scores.append((i, 0.0))
                    else:
                        sim = np.dot(q_vec, self.embeddings[i])
                        scores.append((i, float(sim)))

                # 排序
                scores.sort(key=lambda x: x[1], reverse=True)
                top_k = scores[:n_results]

                results['ids'].append([self.ids[i] for i, _ in top_k])
                results['documents'].append([self.documents[i] for i, _ in top_k])
                results['metadatas'].append([self.metadatas[i] for i, _ in top_k])
                results['distances'].append([1 - s for _, s in top_k])  # distance = 1 - similarity

            return results

        def get(self, ids=None, where=None):
            """按 ID 或元数据获取文档"""
            indices = []
            if ids:
                id_set = set(ids)
                indices = [i for i, doc_id in enumerate(self.ids) if doc_id in id_set]
            else:
                indices = list(range(len(self.documents)))

            if where:
                indices = [i for i in indices
                           if all(self.metadatas[i].get(k) == v for k, v in where.items())]

            return {
                'ids': [self.ids[i] for i in indices],
                'documents': [self.documents[i] for i in indices],
                'metadatas': [self.metadatas[i] for i in indices],
            }

        def count(self):
            """返回文档数量"""
            return len(self.documents)

        def persist(self, filepath):
            """持久化到 JSON 文件"""
            data = {
                'name': self.name,
                'documents': self.documents,
                'metadatas': self.metadatas,
                'ids': self.ids,
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"  [Chroma] 持久化 {len(self.documents)} 篇文档到 {filepath}")

    # ---- 3.1 创建 Collection 并添加文档 ----
    print("=" * 60)
    print("Chroma 向量库模拟实现")
    print("=" * 60)

    collection = ChromaCollection(name="knowledge_base")

    # 模拟知识库文档
    docs = [
        "SQL injection vulnerability allows attackers to execute malicious SQL queries",
        "Cross site scripting XSS injects malicious scripts into web pages viewed by users",
        "Buffer overflow occurs when a program writes more data to a buffer than it can hold",
        "Authentication bypass vulnerability allows unauthorized access to systems",
        "Remote code execution RCE allows attackers to run arbitrary code on a server",
        "Cross site request forgery CSRF tricks users into performing unwanted actions",
        "Directory traversal vulnerability allows access to files outside the web root",
        "Insecure deserialization can lead to remote code execution attacks",
    ]

    metadatas = [
        {"category": "injection", "severity": "high"},
        {"category": "xss", "severity": "medium"},
        {"category": "memory", "severity": "high"},
        {"category": "auth", "severity": "critical"},
        {"category": "rce", "severity": "critical"},
        {"category": "csrf", "severity": "medium"},
        {"category": "traversal", "severity": "high"},
        {"category": "deserialization", "severity": "critical"},
    ]

    collection.add(documents=docs, metadatas=metadatas)
    print(f"  Collection 文档数: {collection.count()}")

    # ---- 3.2 语义查询 ----
    print("\n--- 语义查询测试 ---")
    queries = [
        "How can an attacker execute code on a server?",
        "What is script injection in web pages?",
        "How to bypass login authentication?",
    ]

    for query in queries:
        print(f"\n查询: '{query}'")
        results = collection.query(query_texts=[query], n_results=3)
        for i, (doc_id, doc, meta, dist) in enumerate(zip(
                results['ids'][0], results['documents'][0],
                results['metadatas'][0], results['distances'][0])):
            print(f"  #{i+1} [{doc_id}] dist={dist:.4f} | {meta}")
            print(f"       {doc[:60]}...")

    # ---- 3.3 元数据过滤查询 ----
    print("\n--- 元数据过滤查询 ---")
    print("过滤条件: severity='critical'")
    results = collection.query(
        query_texts=["code execution attack"],
        n_results=5,
        where={"severity": "critical"}
    )
    for i, (doc_id, doc, meta) in enumerate(zip(
            results['ids'][0], results['documents'][0], results['metadatas'][0])):
        print(f"  #{i+1} [{doc_id}] {meta} | {doc[:50]}...")

    # ---- 3.4 持久化 ----
    persist_path = os.path.join(FIG_DIR, "chroma_mock_persist.json")
    collection.persist(persist_path)

    # 验证持久化数据
    with open(persist_path, 'r') as f:
        loaded = json.load(f)
    print(f"  验证: 从磁盘加载 {len(loaded['documents'])} 篇文档")

    # ---- 思考题 ----
    print("\n" + "=" * 60)
    print("思考题：")
    print("1. Chroma 的 Embedding Function 是如何工作的？")
    print("   如果不提供自定义 embedding function，Chroma 默认用什么模型？")
    print("2. 元数据过滤在什么场景下特别有用？")
    print("   提示：多租户、权限控制、时间范围过滤。")
    print("3. 对比内存模式和持久化模式的性能差异，")
    print("   在什么情况下应该选择持久化模式？")
    print("=" * 60)


# ============================================================
# 第 4 题：pgvector — PostgreSQL 向量扩展（概念+模拟实现）
# ============================================================
"""
知识点讲解
-----------

1. pgvector 简介：
   pgvector 是 PostgreSQL 的开源向量相似度搜索扩展。
   它让 PostgreSQL 可以存储和查询高维向量，支持三种距离度量：
   - L2 距离（欧式距离）：'<->' 操作符
   - 内积（Inner Product）：'<#>' 操作符
   - 余弦距离（Cosine Distance）：'<=>' 操作符

   SQL 示例：
   CREATE TABLE items (id bigserial PRIMARY KEY, embedding vector(1536));
   INSERT INTO items (embedding) VALUES ('[0.1, 0.2, ...]');
   SELECT * FROM items ORDER BY embedding <=> '[0.3, 0.4, ...]' LIMIT 10;

2. IVFFlat 索引原理：
   IVF（Inverted File）+ Flat（精确计算）：
   - 训练阶段：用 K-Means 将向量空间划分为 nlist 个聚类（cluster）
   - 查询阶段：先找到最近的 nprobe 个聚类中心，只在这些聚类内精确搜索
   - 优点：查询速度快（减少搜索范围）
   - 缺点：精度有损失（可能漏掉其他聚类中的近邻）
   - 关键参数：nlist（聚类数）、nprobe（探测聚类数）

3. HNSW 索引原理：
   HNSW（Hierarchical Navigable Small World）：
   - 构建多层图结构，上层稀疏（用于快速导航），下层稠密（用于精确搜索）
   - 查询时从最上层开始贪婪搜索，逐层下降
   - 优点：查询速度快、召回率高
   - 缺点：内存占用大、构建速度慢
   - 关键参数：m（每层最大连接数）、ef_construction（构建时搜索宽度）、ef_search（查询时搜索宽度）

4. IVFFlat vs HNSW 对比：
   | 特性       | IVFFlat    | HNSW       |
   |-----------|------------|------------|
   | 构建速度    | 快         | 慢         |
   | 查询速度    | 中         | 快         |
   | 召回率      | 中         | 高         |
   | 内存占用    | 低         | 高         |
   | 适合场景    | 中小规模    | 大规模     |

5. 本题用 numpy 实现简化版 HNSW 索引，理解其核心思想。
"""


def exercise_04():
    """第 4 题：pgvector 模拟与 HNSW 索引实现"""

    # ---- 4.1 简化版 HNSW 索引实现 ----

    class SimpleHNSW:
        """简化版 HNSW（Hierarchical Navigable Small World）索引"""

        def __init__(self, dim=64, max_m=8, ef_construction=50, ef_search=20, max_layers=4):
            self.dim = dim
            self.max_m = max_m          # 每层最大连接数
            self.ef_construction = ef_construction
            self.ef_search = ef_search
            self.max_layers = max_layers
            self.data = []              # 存储所有向量
            self.layers = []            # 多层图结构
            self.entry_point = None     # 入口节点
            self.entry_layer = 0

        def _random_level(self):
            """根据指数分布随机选择层级（层级越高概率越低）"""
            level = 0
            while np.random.random() < 0.5 and level < self.max_layers - 1:
                level += 1
            return level

        def _distance(self, vec1, vec2):
            """欧式距离"""
            return np.linalg.norm(vec1 - vec2)

        def _search_layer(self, query, entry_points, ef, layer):
            """在某一层中搜索最近邻"""
            visited = set()
            candidates = []  # (distance, node_id) 最小堆
            results = []     # (distance, node_id)

            for ep in entry_points:
                dist = self._distance(query, self.data[ep])
                candidates.append((dist, ep))
                visited.add(ep)

            while candidates:
                candidates.sort()
                current_dist, current = candidates[0]
                candidates.pop(0)

                if len(results) >= ef and current_dist > results[-1][0]:
                    break

                results.append((current_dist, current))
                if len(results) > ef:
                    results.sort()
                    results = results[:ef]

                # 搜索邻居
                if layer < len(self.layers) and current < len(self.layers[layer]):
                    for neighbor in self.layers[layer][current]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            dist = self._distance(query, self.data[neighbor])
                            if len(results) < ef or dist < results[-1][0]:
                                candidates.append((dist, neighbor))

            return results

        def add(self, vec):
            """添加向量到索引"""
            node_id = len(self.data)
            self.data.append(vec)
            level = self._random_level()

            # 初始化各层
            while len(self.layers) <= level:
                self.layers.append(defaultdict(list))

            if self.entry_point is None:
                self.entry_point = node_id
                self.entry_layer = level
                return node_id

            # 从顶层向下搜索并连接
            entry_points = [self.entry_point]
            for layer in range(self.entry_layer, level, -1):
                results = self._search_layer(vec, entry_points, 1, layer)
                if results:
                    entry_points = [results[0][1]]

            for layer in range(min(level, self.entry_layer), -1, -1):
                results = self._search_layer(vec, entry_points, self.ef_construction, layer)
                # 选择最近的 max_m 个作为邻居
                results.sort()
                neighbors = [nid for _, nid in results[:self.max_m]]
                self.layers[layer][node_id] = neighbors

                # 双向连接
                for neighbor in neighbors:
                    self.layers[layer][neighbor].append(node_id)
                    # 限制邻居数量
                    if len(self.layers[layer][neighbor]) > self.max_m:
                        self.layers[layer][neighbor] = self.layers[layer][neighbor][-self.max_m:]

                entry_points = [nid for _, nid in results]

            if level > self.entry_layer:
                self.entry_point = node_id
                self.entry_layer = level

            return node_id

        def search(self, query, k=5):
            """搜索 Top-K 最近邻"""
            if not self.data:
                return []

            entry_points = [self.entry_point]
            # 从顶层搜索到第 1 层
            for layer in range(self.entry_layer, 0, -1):
                results = self._search_layer(query, entry_points, 1, layer)
                if results:
                    entry_points = [results[0][1]]

            # 在第 0 层精细搜索
            results = self._search_layer(query, entry_points, max(self.ef_search, k), 0)
            results.sort()
            return [(dist, nid) for dist, nid in results[:k]]

    # ---- 4.2 暴力搜索（基准对比）----
    def brute_force_search(data, query, k=5):
        """暴力搜索 Top-K"""
        distances = [(np.linalg.norm(vec - query), i) for i, vec in enumerate(data)]
        distances.sort()
        return distances[:k]

    # ---- 4.3 实验：HNSW vs 暴力搜索 ----
    print("=" * 60)
    print("pgvector 模拟：HNSW 索引 vs 暴力搜索")
    print("=" * 60)

    np.random.seed(42)
    dim = 64
    n_vectors = 500
    data = [np.random.randn(dim).astype(np.float64) for _ in range(n_vectors)]

    # 构建 HNSW 索引
    print(f"\n构建 HNSW 索引 (dim={dim}, n={n_vectors})...")
    hnsw = SimpleHNSW(dim=dim, max_m=8, ef_construction=30, ef_search=20, max_layers=4)
    t0 = time.time()
    for vec in data:
        hnsw.add(vec)
    build_time = time.time() - t0
    print(f"  构建耗时: {build_time:.3f}s")
    print(f"  入口层级: {hnsw.entry_layer}")

    # 查询对比
    n_queries = 50
    queries = [np.random.randn(dim).astype(np.float64) for _ in range(n_queries)]
    k = 5

    # HNSW 搜索
    t0 = time.time()
    hnsw_results = []
    for q in queries:
        results = hnsw.search(q, k=k)
        hnsw_results.append([nid for _, nid in results])
    hnsw_time = time.time() - t0

    # 暴力搜索
    t0 = time.time()
    bf_results = []
    for q in queries:
        results = brute_force_search(data, q, k=k)
        bf_results.append([nid for _, nid in results])
    bf_time = time.time() - t0

    # 计算召回率
    recall_scores = []
    for hnsw_res, bf_res in zip(hnsw_results, bf_results):
        overlap = len(set(hnsw_res) & set(bf_res))
        recall_scores.append(overlap / k)

    avg_recall = np.mean(recall_scores)

    print(f"\n查询性能对比 (n_queries={n_queries}, k={k}):")
    print(f"  暴力搜索: {bf_time*1000:.2f}ms")
    print(f"  HNSW搜索: {hnsw_time*1000:.2f}ms")
    print(f"  加速比:   {bf_time/max(hnsw_time, 1e-6):.1f}x")
    print(f"  平均召回率: {avg_recall:.2%}")

    # ---- 4.4 可视化 ----
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # 召回率分布
    axes[0].hist(recall_scores, bins=20, color='#3498DB', alpha=0.7, edgecolor='white')
    axes[0].axvline(avg_recall, color='red', linestyle='--', label=f'平均召回率: {avg_recall:.2%}')
    axes[0].set_xlabel('Recall')
    axes[0].set_ylabel('Count')
    axes[0].set_title('HNSW Recall Distribution')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    # 搜索时间对比
    methods = ['Brute Force', 'HNSW']
    times = [bf_time * 1000, hnsw_time * 1000]
    colors = ['#E74C3C', '#2ECC71']
    bars = axes[1].bar(methods, times, color=colors, alpha=0.8, edgecolor='#2C3E50')
    axes[1].set_ylabel('Time (ms)')
    axes[1].set_title(f'Search Time Comparison ({n_queries} queries)')
    for bar, t in zip(bars, times):
        axes[1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                     f'{t:.2f}ms', ha='center', fontsize=11)
    axes[1].grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, 'ex04_hnsw_vs_brute.png'), dpi=150)
    plt.close()
    print(f"\n[图] HNSW vs 暴力搜索对比已保存: {FIG_DIR}/ex04_hnsw_vs_brute.png")

    # ---- 4.5 SQL 语法展示 ----
    sql_examples = """
    -- pgvector SQL 语法示例（概念展示，非可执行代码）
    
    -- 1. 创建带向量列的表
    CREATE TABLE documents (
        id BIGSERIAL PRIMARY KEY,
        content TEXT,
        embedding VECTOR(1536),
        metadata JSONB
    );
    
    -- 2. 创建 HNSW 索引
    CREATE INDEX ON documents USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    
    -- 3. 创建 IVFFlat 索引
    CREATE INDEX ON documents USING ivfflat (embedding vector_l2_ops)
        WITH (lists = 100);
    
    -- 4. 余弦相似度查询（Top-10）
    SELECT id, content, 1 - (embedding <=> '[0.1, 0.2, ...]') AS similarity
    FROM documents
    ORDER BY embedding <=> '[0.1, 0.2, ...]'
    LIMIT 10;
    
    -- 5. 带元数据过滤的向量查询
    SELECT id, content
    FROM documents
    WHERE metadata->>'category' = 'security'
    ORDER BY embedding <=> '[0.1, 0.2, ...]'
    LIMIT 5;
    """
    print("\n--- pgvector SQL 语法示例 ---")
    print(sql_examples)

    # ---- 思考题 ----
    print("=" * 60)
    print("思考题：")
    print("1. HNSW 的分层结构为什么能加速搜索？")
    print("   提示：上层稀疏图用于长距离导航，下层稠密图用于精确搜索。")
    print("2. IVFFlat 中 nprobe 参数如何影响召回率和查询速度？")
    print("   提示：nprobe 越大，搜索范围越广。")
    print("3. 在什么场景下应该选择 pgvector 而不是专用向量数据库？")
    print("   提示：已有 PostgreSQL 基础设施、数据量中等、需要事务支持。")
    print("=" * 60)


# ============================================================
# 第 5 题：Milvus 生产级向量库 — 分布式架构（概念+模拟实现）
# ============================================================
"""
知识点讲解
-----------

1. Milvus 简介：
   Milvus 是开源的分布式向量数据库，专为超大规模向量搜索设计。
   核心架构组件：
   - Proxy：接收客户端请求，路由到对应节点
   - Query Node：执行向量搜索
   - Data Node：处理数据写入和持久化
   - Index Node：构建向量索引
   - Etcd：存储元数据
   - MinIO/S3：对象存储，存放数据文件

2. Milvus 核心概念：
   - Collection：类似数据库表
   - Partition：Collection 的分区，用于数据隔离和查询加速
   - Field Schema：定义字段类型（向量、标量）
   - Index Type：FLAT / IVF_FLAT / IVF_SQ8 / IVF_PQ / HNSW
   - Metric Type：L2 / IP / COSINE

3. 索引类型对比：
   - FLAT：暴力搜索，100% 召回率，适合小数据集（<10万）
   - IVF_FLAT：聚类+精确搜索，平衡速度和精度
   - IVF_SQ8：IVF + 标量量化，压缩存储，降低内存
   - IVF_PQ：IVF + 乘积量化，极致压缩，适合超大规模
   - HNSW：图索引，高召回率，高内存占用

4. IVF 索引原理（本题重点实现）：
   - 训练：用 K-Means 将向量聚为 nlist 个簇
   - 插入：每个向量分配到最近的簇
   - 查询：找到离查询最近的 nprobe 个簇，在这些簇内精确搜索
   - 核心优势：将搜索范围从 N 缩小到 N × nprobe / nlist

5. 标量过滤（Attribute Filtering）：
   Milvus 支持在向量搜索时同时进行标量字段过滤，
   类似 SQL 的 WHERE 子句，实现混合查询。
   例如：search where category == 'security' and year > 2023
"""


def exercise_05():
    """第 5 题：Milvus 模拟与 IVF 索引实现"""

    # ---- 5.1 IVF 索引实现 ----

    class IVFIndex:
        """IVF（Inverted File）向量索引"""

        def __init__(self, nlist=10, nprobe=3):
            self.nlist = nlist      # 聚类中心数
            self.nprobe = nprobe    # 查询时探测的聚类数
            self.centroids = None   # 聚类中心
            self.clusters = None    # 每个聚类的向量列表
            self.data = None        # 原始数据
            self.dim = None

        def _kmeans(self, data, k, max_iter=50):
            """简单 K-Means 聚类"""
            n = len(data)
            # 随机初始化中心
            indices = np.random.choice(n, k, replace=False)
            centroids = data[indices].copy()

            for _ in range(max_iter):
                # 分配到最近的中心
                distances = np.array([[np.linalg.norm(d - c) for c in centroids] for d in data])
                assignments = np.argmin(distances, axis=1)

                # 更新中心
                new_centroids = centroids.copy()
                for j in range(k):
                    mask = assignments == j
                    if np.any(mask):
                        new_centroids[j] = data[mask].mean(axis=0)

                # 收敛判断
                if np.allclose(centroids, new_centroids):
                    break
                centroids = new_centroids

            return centroids, assignments

        def build(self, data):
            """构建 IVF 索引"""
            self.data = np.array(data)
            self.dim = self.data.shape[1]
            n = len(data)

            actual_nlist = min(self.nlist, n)
            self.centroids, assignments = self._kmeans(self.data, actual_nlist)

            # 构建倒排表
            self.clusters = defaultdict(list)
            for i, cluster_id in enumerate(assignments):
                self.clusters[cluster_id].append(i)

            print(f"  [IVF] 索引构建完成: {n} 个向量, {actual_nlist} 个聚类")
            for cid, members in sorted(self.clusters.items()):
                print(f"    聚类 {cid}: {len(members)} 个向量")

        def search(self, query, k=5):
            """IVF 搜索"""
            # 找到最近的 nprobe 个聚类
            centroid_distances = [np.linalg.norm(query - c) for c in self.centroids]
            nearest_clusters = np.argsort(centroid_distances)[:self.nprobe]

            # 在这些聚类内精确搜索
            candidates = []
            for cluster_id in nearest_clusters:
                for vec_id in self.clusters[cluster_id]:
                    dist = np.linalg.norm(query - self.data[vec_id])
                    candidates.append((dist, vec_id))

            candidates.sort()
            return candidates[:k]

    class FLATIndex:
        """FLAT 暴力搜索索引"""

        def __init__(self):
            self.data = None

        def build(self, data):
            self.data = np.array(data)

        def search(self, query, k=5):
            distances = [(np.linalg.norm(query - vec), i) for i, vec in enumerate(self.data)]
            distances.sort()
            return distances[:k]

    # ---- 5.2 Milvus Collection 模拟 ----

    class MilvusCollection:
        """模拟 Milvus Collection"""

        def __init__(self, name, dim):
            self.name = name
            self.dim = dim
            self.vectors = []
            self.scalars = []     # 标量字段
            self.ids = []
            self.index_type = None
            self.index = None
            self.partitions = {}  # 分区

        def insert(self, vectors, scalars=None, partition_name="_default"):
            """插入数据"""
            for i, vec in enumerate(vectors):
                self.vectors.append(vec)
                scalar = scalars[i] if scalars else {}
                self.scalars.append(scalar)
                self.ids.append(len(self.ids))

                if partition_name not in self.partitions:
                    self.partitions[partition_name] = []
                self.partitions[partition_name].append(len(self.ids) - 1)

            print(f"  [Milvus] 插入 {len(vectors)} 条数据到 '{self.name}'.{partition_name}")

        def create_index(self, index_type="IVF", nlist=10, nprobe=3):
            """创建索引"""
            self.index_type = index_type
            if index_type == "FLAT":
                self.index = FLATIndex()
                self.index.build(self.vectors)
            elif index_type == "IVF":
                self.index = IVFIndex(nlist=nlist, nprobe=nprobe)
                self.index.build(self.vectors)
            print(f"  [Milvus] 创建 {index_type} 索引")

        def search(self, query, k=5, expr=None):
            """向量搜索（支持标量过滤）"""
            # 标量过滤
            filtered_ids = list(range(len(self.vectors)))
            if expr:
                # 简单的表达式过滤：{"field": "value"}
                filtered_ids = [
                    i for i in filtered_ids
                    if all(self.scalars[i].get(f) == v for f, v in expr.items())
                ]

            # 在过滤后的数据上搜索
            if self.index and not expr:
                results = self.index.search(query, k=k)
            else:
                # 带过滤时使用暴力搜索
                candidates = []
                for vid in filtered_ids:
                    dist = np.linalg.norm(query - self.vectors[vid])
                    candidates.append((dist, vid))
                candidates.sort()
                results = candidates[:k]

            return [
                {'id': self.ids[vid], 'distance': dist, 'scalar': self.scalars[vid]}
                for dist, vid in results
            ]

    # ---- 5.3 实验：IVF vs FLAT 性能对比 ----
    print("=" * 60)
    print("Milvus 模拟：IVF vs FLAT 性能对比")
    print("=" * 60)

    np.random.seed(42)
    dim = 128
    n_vectors = 2000

    # 生成模拟数据（带有 3 个聚类）
    data = []
    scalars = []
    categories = ["security", "network", "crypto"]
    for i in range(n_vectors):
        cluster = i % 3
        center = np.ones(dim) * cluster * 2
        vec = center + np.random.randn(dim) * 0.5
        data.append(vec)
        scalars.append({"category": categories[cluster], "id_num": i})

    # 构建 FLAT 索引
    print("\n--- FLAT 索引 ---")
    flat_coll = MilvusCollection("flat_test", dim)
    flat_coll.insert(data, scalars)
    flat_coll.create_index("FLAT")

    # 构建 IVF 索引
    print("\n--- IVF 索引 ---")
    ivf_coll = MilvusCollection("ivf_test", dim)
    ivf_coll.insert(data, scalars)
    ivf_coll.create_index("IVF", nlist=20, nprobe=5)

    # 查询对比
    n_queries = 100
    queries = [np.random.randn(dim) for _ in range(n_queries)]
    k = 10

    # FLAT 搜索
    t0 = time.time()
    flat_results = []
    for q in queries:
        res = flat_coll.search(q, k=k)
        flat_results.append([r['id'] for r in res])
    flat_time = time.time() - t0

    # IVF 搜索
    t0 = time.time()
    ivf_results = []
    for q in queries:
        res = ivf_coll.search(q, k=k)
        ivf_results.append([r['id'] for r in res])
    ivf_time = time.time() - t0

    # 召回率
    recalls = []
    for fr, ir in zip(flat_results, ivf_results):
        overlap = len(set(fr) & set(ir))
        recalls.append(overlap / k)

    avg_recall = np.mean(recalls)

    print(f"\n性能对比 (n={n_vectors}, dim={dim}, queries={n_queries}, k={k}):")
    print(f"  FLAT: {flat_time*1000:.2f}ms")
    print(f"  IVF:  {ivf_time*1000:.2f}ms")
    print(f"  加速比: {flat_time/max(ivf_time, 1e-6):.1f}x")
    print(f"  IVF 平均召回率: {avg_recall:.2%}")

    # ---- 5.4 标量过滤查询 ----
    print("\n--- 标量过滤查询 ---")
    query = np.random.randn(dim)
    print(f"查询条件: category='security', k=5")
    results = ivf_coll.search(query, k=5, expr={"category": "security"})
    for r in results:
        print(f"  ID={r['id']}, dist={r['distance']:.4f}, {r['scalar']}")

    # ---- 5.5 可视化 ----
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # IVF nprobe 参数对召回率的影响
    nprobe_values = [1, 2, 3, 5, 8, 10, 15, 20]
    recall_vs_nprobe = []
    time_vs_nprobe = []

    for nprobe in nprobe_values:
        ivf_test = IVFIndex(nlist=20, nprobe=nprobe)
        ivf_test.build(data)

        t0 = time.time()
        recalls_np = []
        for q_idx in range(20):  # 取前 20 个查询
            ivf_res = ivf_test.search(queries[q_idx], k=k)
            ivf_ids = [vid for _, vid in ivf_res]
            flat_ids = flat_results[q_idx]
            overlap = len(set(ivf_ids) & set(flat_ids))
            recalls_np.append(overlap / k)
        elapsed = time.time() - t0

        recall_vs_nprobe.append(np.mean(recalls_np))
        time_vs_nprobe.append(elapsed * 1000 / 20)  # 平均每次查询时间

    axes[0].plot(nprobe_values, recall_vs_nprobe, 'bo-', linewidth=2, markersize=8)
    axes[0].set_xlabel('nprobe')
    axes[0].set_ylabel('Recall')
    axes[0].set_title('IVF Recall vs nprobe')
    axes[0].grid(True, alpha=0.3)
    axes[0].set_ylim(0, 1.05)

    axes[1].plot(nprobe_values, time_vs_nprobe, 'rs-', linewidth=2, markersize=8)
    axes[1].set_xlabel('nprobe')
    axes[1].set_ylabel('Avg Search Time (ms)')
    axes[1].set_title('IVF Search Time vs nprobe')
    axes[1].grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, 'ex05_ivf_nprobe_analysis.png'), dpi=150)
    plt.close()
    print(f"\n[图] IVF nprobe 参数分析已保存: {FIG_DIR}/ex05_ivf_nprobe_analysis.png")

    # ---- 思考题 ----
    print("\n" + "=" * 60)
    print("思考题：")
    print("1. IVF 索引的 nlist 和 nprobe 如何选择？")
    print("   提示：nlist ≈ √N，nprobe 越大召回越高但速度越慢。")
    print("2. Milvus 的 Partition 机制在什么场景下有用？")
    print("   提示：按时间/租户/类别分区，查询时只搜索相关分区。")
    print("3. IVF_PQ（乘积量化）是如何在保持可接受召回率的同时")
    print("   大幅压缩向量存储空间的？")
    print("   提示：将高维向量分割为子向量，每个子向量量化编码。")
    print("=" * 60)


# ============================================================
# 第 6 题：文档加载与分块 — Chunking 策略
# ============================================================
"""
知识点讲解
-----------

1. 为什么需要文档分块（Chunking）？
   - Embedding 模型有输入长度限制（如 512 tokens）
   - 过长的文档会稀释语义信息，降低检索精度
   - 分块后可以更精确地定位相关内容
   - 合理的 chunk_size 平衡检索精度和上下文完整性

2. 常见分块策略：
   a) Fixed-size Splitting（固定大小分块）：
      按固定字符数/词数切分，简单但可能切断语义。
   
   b) Recursive Character Text Splitting（递归字符分块）：
      LangChain 的默认策略。按分隔符优先级递归切分：
      ["\\n\\n", "\\n", " ", ""] — 先按段落，再按行，再按词。
      优先在自然边界处切分，保持语义完整性。
   
   c) Token-based Splitting（Token 分块）：
      按 Token 数切分（如 BPE tokenizer），更精确控制输入长度。
      适合对 Embedding 模型输入有严格要求的场景。

3. chunk_size 和 overlap 参数：
   - chunk_size：每个块的大小
   - overlap：相邻块之间的重叠部分
   - overlap 的作用：避免在边界处丢失上下文信息
   - 经验值：overlap = chunk_size × 10%~20%

4. 不同文档格式的处理差异：
   - Markdown：利用标题层级（# ## ###）作为分块边界
   - PDF：按页面/段落切分，需处理表格和图片
   - HTML：利用 DOM 结构（<p>, <div>, <h1>）切分
   - 代码：按函数/类定义切分

5. 分块策略对检索质量的影响：
   本题将对同一篇长文档用 3 种策略分块，
   对比不同策略下的检索召回率。
"""


def exercise_06():
    """第 6 题：文档分块策略对比"""

    # ---- 6.1 三种分块策略实现 ----

    def fixed_size_split(text, chunk_size=100, overlap=20):
        """固定大小分块"""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end - overlap
        return [c for c in chunks if c.strip()]

    def recursive_character_split(text, chunk_size=100, overlap=20):
        """递归字符分块（模拟 LangChain RecursiveCharacterTextSplitter）"""
        separators = ["\n\n", "\n", ". ", " ", ""]

        def split_text(text, separators, chunk_size, overlap):
            if len(text) <= chunk_size:
                return [text] if text.strip() else []

            for i, sep in enumerate(separators):
                if sep == "":
                    # 最后 fallback：按字符切
                    chunks = []
                    start = 0
                    while start < len(text):
                        end = start + chunk_size
                        chunks.append(text[start:end])
                        start = end - overlap
                    return [c for c in chunks if c.strip()]

                splits = text.split(sep)
                if len(splits) > 1:
                    # 合并小片段到 chunk_size
                    chunks = []
                    current = ""
                    for s in splits:
                        candidate = current + sep + s if current else s
                        if len(candidate) <= chunk_size:
                            current = candidate
                        else:
                            if current:
                                chunks.append(current)
                            # 如果单个片段仍然太长，递归切分
                            if len(s) > chunk_size:
                                sub_chunks = split_text(s, separators[i+1:], chunk_size, overlap)
                                chunks.extend(sub_chunks)
                                current = ""
                            else:
                                current = s
                    if current:
                        chunks.append(current)

                    # 添加 overlap
                    if overlap > 0 and len(chunks) > 1:
                        overlapped = [chunks[0]]
                        for j in range(1, len(chunks)):
                            prev_tail = chunks[j-1][-overlap:] if len(chunks[j-1]) > overlap else chunks[j-1]
                            overlapped.append(prev_tail + chunks[j])
                        return overlapped
                    return chunks

            return [text]

        return split_text(text, separators, chunk_size, overlap)

    def token_based_split(text, chunk_size=80, overlap=15):
        """Token 分块（按词模拟 Token）"""
        tokens = text.split()
        chunks = []
        start = 0
        while start < len(tokens):
            end = start + chunk_size
            chunk = " ".join(tokens[start:end])
            chunks.append(chunk)
            start = end - overlap
        return [c for c in chunks if c.strip()]

    # ---- 6.2 准备长文档 ----
    long_document = """
Cross-Site Scripting (XSS) is a security vulnerability that allows attackers to inject malicious scripts into web pages viewed by other users. XSS attacks occur when a web application includes untrusted data in a web page without proper validation or escaping.

There are three main types of XSS attacks. The first type is Stored XSS, where the malicious script is permanently stored on the target server, such as in a database. When a user visits the affected page, the script executes. The second type is Reflected XSS, where the malicious script is embedded in a URL and executed when the user clicks on the link. The third type is DOM-based XSS, where the vulnerability exists in the client-side code rather than the server-side code.

To prevent XSS attacks, developers should always sanitize and validate user input. They should use output encoding to convert special characters to their HTML entities. Content Security Policy (CSP) headers can also help mitigate XSS by restricting the sources from which scripts can be loaded. Additionally, using modern frameworks like React or Angular that automatically escape output can significantly reduce XSS risks.

SQL Injection is another critical web vulnerability. It occurs when an attacker can manipulate SQL queries by injecting malicious SQL code through user input. This can lead to data theft, data modification, or even complete database compromise. Parameterized queries and prepared statements are the most effective defenses against SQL injection.

Buffer overflow vulnerabilities occur when a program writes more data to a buffer than it can hold, causing the excess data to overflow into adjacent memory locations. This can corrupt data, crash the program, or allow arbitrary code execution. Modern programming languages like Rust and Go have built-in memory safety features that prevent buffer overflows by design.

Authentication bypass vulnerabilities allow attackers to gain unauthorized access to systems without valid credentials. Common techniques include brute force attacks, credential stuffing, and exploiting weak password reset mechanisms. Multi-factor authentication and rate limiting are effective countermeasures against authentication bypass attacks.
""".strip()

    print("=" * 60)
    print("文档分块策略对比")
    print("=" * 60)
    print(f"文档总长度: {len(long_document)} 字符, {len(long_document.split())} 词")

    # ---- 6.3 三种策略分块 ----
    chunk_size = 150
    overlap = 30

    strategies = {
        "Fixed-Size": fixed_size_split(long_document, chunk_size, overlap),
        "Recursive": recursive_character_split(long_document, chunk_size, overlap),
        "Token-Based": token_based_split(long_document, 30, 5),  # 30 tokens
    }

    for name, chunks in strategies.items():
        print(f"\n--- {name} 分块 ({len(chunks)} 块) ---")
        for i, chunk in enumerate(chunks[:3]):  # 只显示前 3 块
            print(f"  块 {i} [{len(chunk)} 字符]: {chunk[:60]}...")
        if len(chunks) > 3:
            print(f"  ... 共 {len(chunks)} 块")

    # ---- 6.4 检索召回率对比 ----
    # 构建词汇表和 TF-IDF
    def build_tfidf(chunks):
        all_words = set()
        for chunk in chunks:
            all_words.update(chunk.lower().split())
        vocab = {w: i for i, w in enumerate(sorted(all_words))}
        N = len(chunks)
        df = np.zeros(len(vocab))
        for chunk in chunks:
            tokens = set(chunk.lower().split())
            for w in tokens:
                if w in vocab:
                    df[vocab[w]] += 1
        idf = np.log(N / (1 + df))

        embeddings = np.zeros((len(chunks), len(vocab)))
        for i, chunk in enumerate(chunks):
            tokens = chunk.lower().split()
            counter = Counter(tokens)
            total = len(tokens)
            for w, c in counter.items():
                if w in vocab:
                    embeddings[i, vocab[w]] = (c / total) * idf[vocab[w]]
            norm = np.linalg.norm(embeddings[i])
            if norm > 0:
                embeddings[i] /= norm
        return vocab, idf, embeddings

    def embed_query(query, vocab, idf):
        vec = np.zeros(len(vocab))
        tokens = query.lower().split()
        counter = Counter(tokens)
        total = len(tokens)
        for w, c in counter.items():
            if w in vocab:
                vec[vocab[w]] = (c / total) * idf[vocab[w]]
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm
        return vec

    # 测试查询
    test_queries = [
        ("What is XSS attack?", [0, 1]),          # 答案在前 2 块
        ("How to prevent XSS?", [2]),              # 答案在第 3 块
        ("What is SQL injection?", [3]),           # 答案在第 4 块左右
        ("What is buffer overflow?", [4]),         # 答案在第 5 块左右
        ("How to bypass authentication?", [5]),    # 答案在第 6 块左右
    ]

    print("\n--- 检索召回率对比 ---")
    print(f"{'策略':<15} | {'平均召回率':>10} | {'块数':>6}")
    print("-" * 40)

    strategy_recalls = {}
    for name, chunks in strategies.items():
        vocab, idf, embeddings = build_tfidf(chunks)
        recalls = []
        for query, expected_indices in test_queries:
            q_vec = embed_query(query, vocab, idf)
            scores = embeddings @ q_vec
            top_k = min(3, len(chunks))
            retrieved = set(np.argsort(scores)[::-1][:top_k].tolist())
            expected = set(expected_indices)
            # 召回率 = 检索到相关块的比例
            hit = len(retrieved & expected) / len(expected)
            recalls.append(hit)
        avg_recall = np.mean(recalls)
        strategy_recalls[name] = avg_recall
        print(f"{name:<15} | {avg_recall:>10.2%} | {len(chunks):>6}")

    # ---- 6.5 可视化 ----
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # 块数对比
    names = list(strategies.keys())
    chunk_counts = [len(strategies[n]) for n in names]
    colors = ['#3498DB', '#2ECC71', '#E67E22']
    bars = axes[0].bar(names, chunk_counts, color=colors, alpha=0.8, edgecolor='#2C3E50')
    axes[0].set_ylabel('Number of Chunks')
    axes[0].set_title('Chunk Count by Strategy')
    for bar, count in zip(bars, chunk_counts):
        axes[0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.2,
                     str(count), ha='center', fontsize=12, fontweight='bold')
    axes[0].grid(True, alpha=0.3, axis='y')

    # 召回率对比
    recalls_list = [strategy_recalls[n] for n in names]
    bars = axes[1].bar(names, recalls_list, color=colors, alpha=0.8, edgecolor='#2C3E50')
    axes[1].set_ylabel('Average Recall')
    axes[1].set_title('Retrieval Recall by Strategy')
    axes[1].set_ylim(0, 1.1)
    for bar, recall in zip(bars, recalls_list):
        axes[1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                     f'{recall:.1%}', ha='center', fontsize=12, fontweight='bold')
    axes[1].grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, 'ex06_chunking_comparison.png'), dpi=150)
    plt.close()
    print(f"\n[图] 分块策略对比已保存: {FIG_DIR}/ex06_chunking_comparison.png")

    # ---- 思考题 ----
    print("\n" + "=" * 60)
    print("思考题：")
    print("1. chunk_size 设太大或太小各有什么问题？")
    print("   提示：太大→语义稀释+超出模型限制，太小→上下文不完整。")
    print("2. 为什么 overlap 能提升检索质量？overlap 设多少合适？")
    print("   提示：避免边界信息丢失，通常 10%-20%。")
    print("3. 对于 Markdown 文档，如何利用标题层级来优化分块？")
    print("   提示：按 # ## ### 作为分块边界，保持段落完整性。")
    print("=" * 60)


# ============================================================
# 第 7 题：元数据增强与混合检索 — Metadata + Keyword
# ============================================================
"""
知识点讲解
-----------

1. 元数据（Metadata）在 RAG 中的作用：
   元数据是附加在每个文档块上的结构化信息，如：
   - source: 文档来源（文件名、URL）
   - page: 页码
   - category: 分类标签
   - timestamp: 创建时间
   元数据过滤允许在向量搜索前缩小范围，提升查询效率和精度。

2. BM25 关键词检索算法：
   BM25（Best Matching 25）是经典的关键词检索算法。
   核心思想：词频饱和 + 文档长度归一化。
   
   公式：score(D, Q) = Σ IDF(qi) × (f(qi,D) × (k1+1)) / (f(qi,D) + k1 × (1 - b + b × |D|/avgdl))
   
   其中：
   - f(qi,D)：词 qi 在文档 D 中的频率
   - |D|：文档 D 的长度
   - avgdl：所有文档的平均长度
   - k1：词频饱和参数（通常 1.2~2.0）
   - b：文档长度归一化参数（通常 0.75）

3. 混合检索（Hybrid Search）：
   将向量检索（语义匹配）和 BM25 检索（关键词匹配）结合：
   - 向量检索擅长：语义相似、同义词、概念匹配
   - BM25 擅长：精确关键词匹配、专有名词、代码标识符
   - 融合方法：加权求和、RRF（Reciprocal Rank Fusion）

4. Reranker（重排序）：
   检索后对 Top-K 结果进行二次排序：
   - Cross-encoder 模型：将 query 和 document 一起输入，输出相关性分数
   - 比双塔模型（Bi-encoder）更精确，但速度更慢
   - 通常先检索 Top-50，再用 Reranker 精排到 Top-5

5. 本题将实现完整的 BM25 + 向量检索 + 混合融合 + 重排序流程。
"""


def exercise_07():
    """第 7 题：元数据增强与混合检索"""

    # ---- 7.1 BM25 实现 ----

    class BM25:
        """BM25 关键词检索（纯 Python 实现）"""

        def __init__(self, k1=1.5, b=0.75):
            self.k1 = k1
            self.b = b
            self.doc_freqs = []        # 每篇文档的词频
            self.idf = {}
            self.avgdl = 0
            self.doc_len = []
            self.N = 0

        def fit(self, documents):
            """训练 BM25 模型"""
            self.N = len(documents)
            self.doc_len = [len(doc.split()) for doc in documents]
            self.avgdl = np.mean(self.doc_len) if self.doc_len else 0

            # 计算文档频率
            df = defaultdict(int)
            self.doc_freqs = []
            for doc in documents:
                tokens = doc.split()
                freq = Counter(tokens)
                self.doc_freqs.append(freq)
                for word in freq.keys():
                    df[word] += 1

            # 计算 IDF
            for word, freq in df.items():
                self.idf[word] = math.log((self.N - freq + 0.5) / (freq + 0.5) + 1)

        def search(self, query, k=5):
            """搜索 Top-K 文档"""
            query_tokens = query.split()
            scores = np.zeros(self.N)

            for i in range(self.N):
                score = 0.0
                doc_len = self.doc_len[i]
                for token in query_tokens:
                    if token in self.idf:
                        tf = self.doc_freqs[i].get(token, 0)
                        if tf > 0:
                            idf = self.idf[token]
                            numerator = tf * (self.k1 + 1)
                            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                            score += idf * numerator / denominator
                scores[i] = score

            ranked = np.argsort(scores)[::-1][:k]
            return [(int(idx), float(scores[idx])) for idx in ranked]

    # ---- 7.2 向量检索 ----

    class VectorRetriever:
        """TF-IDF 向量检索"""

        def __init__(self):
            self.vocab = {}
            self.idf = None
            self.embeddings = None

        def fit(self, documents):
            all_words = set()
            for doc in documents:
                all_words.update(doc.lower().split())
            self.vocab = {w: i for i, w in enumerate(sorted(all_words))}
            N = len(documents)
            df = np.zeros(len(self.vocab))
            for doc in documents:
                tokens = set(doc.lower().split())
                for w in tokens:
                    if w in self.vocab:
                        df[self.vocab[w]] += 1
            self.idf = np.log(N / (1 + df))

            self.embeddings = np.zeros((N, len(self.vocab)))
            for i, doc in enumerate(documents):
                tokens = doc.lower().split()
                counter = Counter(tokens)
                total = len(tokens)
                for w, c in counter.items():
                    if w in self.vocab:
                        self.embeddings[i, self.vocab[w]] = (c / total) * self.idf[self.vocab[w]]
                norm = np.linalg.norm(self.embeddings[i])
                if norm > 0:
                    self.embeddings[i] /= norm

        def search(self, query, k=5):
            q_vec = np.zeros(len(self.vocab))
            tokens = query.lower().split()
            counter = Counter(tokens)
            total = len(tokens)
            for w, c in counter.items():
                if w in self.vocab:
                    q_vec[self.vocab[w]] = (c / total) * self.idf[self.vocab[w]]
            norm = np.linalg.norm(q_vec)
            if norm > 0:
                q_vec /= norm

            scores = self.embeddings @ q_vec
            ranked = np.argsort(scores)[::-1][:k]
            return [(int(idx), float(scores[idx])) for idx in ranked]

    # ---- 7.3 混合检索 + Reranker ----

    def hybrid_search(vector_results, bm25_results, alpha=0.5, k=5):
        """混合检索：加权融合"""
        scores = defaultdict(float)
        # 向量检索贡献
        for rank, (idx, score) in enumerate(vector_results):
            # RRF (Reciprocal Rank Fusion)
            scores[idx] += alpha * (1.0 / (rank + 1))
        # BM25 贡献
        for rank, (idx, score) in enumerate(bm25_results):
            scores[idx] += (1 - alpha) * (1.0 / (rank + 1))

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]
        return [(idx, score) for idx, score in ranked]

    def simple_reranker(query, documents, top_indices, top_k=3):
        """简化版 Reranker：基于关键词重叠度重排序"""
        query_words = set(query.lower().split())
        reranked = []
        for idx in top_indices:
            doc_words = set(documents[idx].lower().split())
            overlap = len(query_words & doc_words)
            jaccard = overlap / len(query_words | doc_words) if query_words | doc_words else 0
            reranked.append((idx, jaccard))
        reranked.sort(key=lambda x: x[1], reverse=True)
        return reranked[:top_k]

    # ---- 7.4 实验对比 ----
    print("=" * 60)
    print("元数据增强与混合检索")
    print("=" * 60)

    # Bug Bounty 知识库文档
    documents = [
        "SQL injection vulnerability allows attackers to execute malicious SQL queries through user input fields",
        "Cross site scripting XSS injects malicious JavaScript into web pages viewed by other users browsers",
        "Server side request forgery SSRF tricks a server into making requests to internal network resources",
        "Insecure deserialization vulnerability can lead to remote code execution when untrusted data is deserialized",
        "Cross site request forgery CSRF forces authenticated users to submit unwanted actions without consent",
        "Directory traversal attack allows reading files outside the intended web root directory path",
        "XML external entity XXE injection exploits XML parsers to read internal files and SSRF attacks",
        "Broken authentication allows attackers to compromise passwords keys or session tokens to assume identities",
        "Sensitive data exposure occurs when applications fail to adequately protect sensitive information like passwords",
        "Security misconfiguration includes default accounts unchanged passwords verbose error messages open ports",
    ]

    # 训练 BM25 和向量检索
    bm25 = BM25(k1=1.5, b=0.75)
    bm25.fit(documents)

    vector_retriever = VectorRetriever()
    vector_retriever.fit(documents)

    # 测试查询
    test_queries = [
        "How to execute SQL injection attack?",
        "What is cross site scripting XSS?",
        "How does SSRF work?",
        "Remote code execution through deserialization",
        "How to read internal files through XML?",
    ]

    print(f"\n{'查询':<45} | {'向量检索':>8} | {'BM25':>8} | {'混合检索':>8} | {'Rerank':>8}")
    print("-" * 95)

    all_results = []
    for query in test_queries:
        # 向量检索 Top-5
        v_results = vector_retriever.search(query, k=5)
        # BM25 检索 Top-5
        b_results = bm25.search(query, k=5)
        # 混合检索
        v_ids = [idx for idx, _ in v_results]
        b_ids = [idx for idx, _ in b_results]
        hybrid_results = hybrid_search(v_results, b_results, alpha=0.5, k=5)
        hybrid_ids = [idx for idx, _ in hybrid_results]
        # Reranker
        reranked = simple_reranker(query, documents, hybrid_ids, top_k=3)
        reranked_ids = [idx for idx, _ in reranked]

        all_results.append({
            'query': query,
            'vector': v_ids[0],
            'bm25': b_ids[0],
            'hybrid': hybrid_ids[0],
            'rerank': reranked_ids[0] if reranked_ids else -1,
        })

        print(f"{query[:43]:<45} | {v_ids[0]:>8} | {b_ids[0]:>8} | {hybrid_ids[0]:>8} | {reranked_ids[0] if reranked_ids else -1:>8}")

    # ---- 7.5 元数据过滤演示 ----
    print("\n--- 元数据过滤演示 ---")
    metadatas = [
        {"type": "injection", "owasp": "A03"},
        {"type": "xss", "owasp": "A03"},
        {"type": "ssrf", "owasp": "A10"},
        {"type": "deserialization", "owasp": "A08"},
        {"type": "csrf", "owasp": "A01"},
        {"type": "traversal", "owasp": "A01"},
        {"type": "xxe", "owasp": "A05"},
        {"type": "auth", "owasp": "A07"},
        {"type": "data", "owasp": "A02"},
        {"type": "config", "owasp": "A06"},
    ]

    # 过滤 OWASP A03（注入类漏洞）
    query = "injection attack"
    filtered_indices = [i for i, m in enumerate(metadatas) if m["owasp"] == "A03"]
    print(f"查询: '{query}', 过滤: OWASP=A03")
    print(f"  过滤后候选文档: {filtered_indices}")
    for idx in filtered_indices:
        print(f"    [{idx}] {documents[idx][:50]}...")

    # ---- 7.6 可视化 ----
    fig, ax = plt.subplots(figsize=(12, 6))

    # 三种检索方法的 Top-1 对比
    methods = ['Vector Only', 'BM25 Only', 'Hybrid Search', 'Hybrid + Rerank']
    query_labels = [f"Q{i+1}" for i in range(len(test_queries))]

    # 用文档索引作为得分（越接近预期越好）
    # 这里简化：假设第 i 个查询的正确答案是第 i 个文档
    expected = [0, 1, 2, 3, 6]  # 预期答案文档索引
    hits = {m: [] for m in methods}
    for res in all_results:
        exp = expected[test_queries.index(res['query'])]
        hits['Vector Only'].append(1 if res['vector'] == exp else 0)
        hits['BM25 Only'].append(1 if res['bm25'] == exp else 0)
        hits['Hybrid Search'].append(1 if res['hybrid'] == exp else 0)
        hits['Hybrid + Rerank'].append(1 if res['rerank'] == exp else 0)

    x = np.arange(len(query_labels))
    width = 0.2
    colors = ['#3498DB', '#E67E22', '#2ECC71', '#9B59B6']
    for i, method in enumerate(methods):
        ax.bar(x + i * width, hits[method], width, label=method, color=colors[i], alpha=0.8,
               edgecolor='#2C3E50')

    ax.set_xlabel('Query')
    ax.set_ylabel('Hit (1=Correct, 0=Miss)')
    ax.set_title('Retrieval Accuracy: Vector vs BM25 vs Hybrid vs Rerank')
    ax.set_xticks(x + width * 1.5)
    ax.set_xticklabels(query_labels)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim(-0.1, 1.3)

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, 'ex07_hybrid_search.png'), dpi=150)
    plt.close()
    print(f"\n[图] 混合检索对比已保存: {FIG_DIR}/ex07_hybrid_search.png")

    # ---- 思考题 ----
    print("\n" + "=" * 60)
    print("思考题：")
    print("1. BM25 中的 k1 和 b 参数分别控制什么？")
    print("   提示：k1 控制词频饱和速度，b 控制文档长度归一化强度。")
    print("2. RRF（Reciprocal Rank Fusion）相比加权求和有什么优势？")
    print("   提示：RRF 不需要分数归一化，对不同尺度的分数更鲁棒。")
    print("3. 在什么场景下 BM25 会明显优于向量检索？")
    print("   提示：精确关键词匹配、代码搜索、专有名词查询。")
    print("=" * 60)


# ============================================================
# 第 8 题：端到端 RAG 系统
# ============================================================
"""
知识点讲解
-----------

1. 端到端 RAG Pipeline 的完整流程：
   Document Loader → Text Splitter → Embedding → Vector Store
   → Retriever → QA Chain → Source Citation
   
   每个模块的职责：
   - Loader：从文件/URL/数据库加载原始文档
   - Splitter：将长文档分块
   - Embedding：将文本块转为向量
   - Vector Store：存储向量并支持相似度搜索
   - Retriever：根据查询检索相关文档块
   - QA Chain：将检索结果拼入 Prompt，调用 LLM 生成回答
   - Source Citation：标注回答的信息来源

2. 本题使用 Bug Bounty 知识库作为文档源：
   包含 XSS、SQL注入、SSRF、IDOR 等漏洞的描述和修复建议。
   这些内容安全从业者非常熟悉，适合作为 RAG 演示数据。

3. 引用来源标注的实现思路：
   - 检索时记录每个结果块的文档 ID 和分数
   - 生成回答时附注引用来源
   - 格式：[来源1] 文档名, 相关度=0.85

4. 纯 numpy 模拟实现：
   由于 chromadb 安装受限，本题用 numpy 完整模拟：
   - Vector Store 用 numpy 矩阵存储 TF-IDF 向量
   - Retriever 用矩阵乘法实现 Top-K 检索
   - QA Chain 用模板匹配 + 关键词提取模拟 LLM 生成

5. 生产级 RAG 的额外考虑：
   - 增量更新：新文档加入时如何更新索引
   - 缓存：对相同查询缓存检索结果
   - 并发：多用户同时查询的线程安全
   - 监控：检索质量监控、延迟监控
"""


def exercise_08():
    """第 8 题：端到端 RAG 系统"""

    # ---- 8.1 Bug Bounty 知识库 ----

    BUG_BOUNTY_KB = [
        {
            "title": "Cross-Site Scripting (XSS)",
            "content": "XSS is a vulnerability that allows attackers to inject malicious scripts into web pages. There are three types: Stored XSS persists in the database, Reflected XSS is embedded in URLs, and DOM-based XSS occurs in client-side code. Prevention includes input sanitization, output encoding, and Content Security Policy headers.",
            "category": "injection",
            "severity": "high"
        },
        {
            "title": "SQL Injection",
            "content": "SQL Injection occurs when attackers manipulate SQL queries through user input. It can lead to data theft, modification, or database compromise. Prevention uses parameterized queries, prepared statements, and input validation. Tools like sqlmap can automate detection.",
            "category": "injection",
            "severity": "critical"
        },
        {
            "title": "Server-Side Request Forgery (SSRF)",
            "content": "SSRF tricks a server into making requests to internal network resources. Attackers can access internal services, cloud metadata endpoints, or scan internal networks. Prevention includes URL allowlists, disabling unused URL schemes, and network segmentation.",
            "category": "ssrf",
            "severity": "high"
        },
        {
            "title": "Insecure Direct Object Reference (IDOR)",
            "content": "IDOR allows attackers to access objects by manipulating identifiers in URLs or parameters. For example, changing user_id from 100 to 101 may reveal another user data. Prevention requires proper authorization checks on every object access.",
            "category": "access",
            "severity": "high"
        },
        {
            "title": "Insecure Deserialization",
            "content": "Insecure deserialization occurs when applications deserialize untrusted data without validation. It can lead to remote code execution, privilege escalation, or injection attacks. Prevention includes avoiding deserialization of untrusted data and using safe serialization formats like JSON.",
            "category": "deserialization",
            "severity": "critical"
        },
        {
            "title": "Cross-Site Request Forgery (CSRF)",
            "content": "CSRF forces authenticated users to execute unwanted actions. Attackers craft malicious pages that submit forms to target sites using victim cookies. Prevention uses anti-CSRF tokens, SameSite cookie attribute, and requiring re-authentication for sensitive actions.",
            "category": "csrf",
            "severity": "medium"
        },
        {
            "title": "Security Misconfiguration",
            "content": "Security misconfiguration includes default credentials, verbose error messages, unnecessary enabled features, and missing security headers. Prevention involves security hardening, disabling default accounts, and regular configuration audits.",
            "category": "config",
            "severity": "medium"
        },
        {
            "title": "Broken Authentication",
            "content": "Broken authentication allows attackers to compromise user accounts. Common issues include weak passwords, credential stuffing, session fixation, and missing rate limiting. Prevention uses multi-factor authentication, strong password policies, and session management best practices.",
            "category": "auth",
            "severity": "critical"
        },
    ]

    # ---- 8.2 RAG Pipeline 组件 ----

    class DocumentLoader:
        """文档加载器"""

        def load(self, knowledge_base):
            """加载知识库文档"""
            docs = []
            for item in knowledge_base:
                docs.append({
                    'id': len(docs),
                    'title': item['title'],
                    'content': item['content'],
                    'metadata': {
                        'category': item['category'],
                        'severity': item['severity']
                    }
                })
            print(f"  [Loader] 加载 {len(docs)} 篇文档")
            return docs

    class TextSplitter:
        """文本分块器"""

        def split(self, documents, chunk_size=100, overlap=20):
            """按句子分块"""
            chunks = []
            for doc in documents:
                # 按句子分割
                sentences = re.split(r'(?<=[.!?])\s+', doc['content'])
                current_chunk = ""
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) <= chunk_size:
                        current_chunk += " " + sentence if current_chunk else sentence
                    else:
                        if current_chunk:
                            chunks.append({
                                'chunk_id': len(chunks),
                                'doc_id': doc['id'],
                                'title': doc['title'],
                                'text': current_chunk.strip(),
                                'metadata': doc['metadata']
                            })
                        current_chunk = sentence
                if current_chunk:
                    chunks.append({
                        'chunk_id': len(chunks),
                        'doc_id': doc['id'],
                        'title': doc['title'],
                        'text': current_chunk.strip(),
                        'metadata': doc['metadata']
                    })
            print(f"  [Splitter] 分块完成: {len(chunks)} 个文本块")
            return chunks

    class EmbeddingEngine:
        """TF-IDF 嵌入引擎"""

        def __init__(self):
            self.vocab = {}
            self.idf = None

        def fit(self, chunks):
            all_words = set()
            for chunk in chunks:
                all_words.update(chunk['text'].lower().split())
            self.vocab = {w: i for i, w in enumerate(sorted(all_words))}
            N = len(chunks)
            df = np.zeros(len(self.vocab))
            for chunk in chunks:
                tokens = set(chunk['text'].lower().split())
                for w in tokens:
                    if w in self.vocab:
                        df[self.vocab[w]] += 1
            self.idf = np.log(N / (1 + df))

        def embed(self, text):
            vec = np.zeros(len(self.vocab))
            tokens = text.lower().split()
            counter = Counter(tokens)
            total = len(tokens)
            for w, c in counter.items():
                if w in self.vocab:
                    vec[self.vocab[w]] = (c / total) * self.idf[self.vocab[w]]
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec /= norm
            return vec

    class VectorStore:
        """向量存储（numpy 模拟）"""

        def __init__(self):
            self.chunks = []
            self.embeddings = None
            self.embedding_engine = EmbeddingEngine()

        def add(self, chunks):
            self.chunks = chunks
            self.embedding_engine.fit(chunks)
            self.embeddings = np.array([
                self.embedding_engine.embed(chunk['text']) for chunk in chunks
            ])
            print(f"  [VectorStore] 存储 {len(chunks)} 个向量, dim={self.embeddings.shape[1]}")

        def search(self, query, top_k=3, metadata_filter=None):
            q_vec = self.embedding_engine.embed(query)
            scores = self.embeddings @ q_vec

            # 元数据过滤
            if metadata_filter:
                for i, chunk in enumerate(self.chunks):
                    if not all(chunk['metadata'].get(k) == v for k, v in metadata_filter.items()):
                        scores[i] = -1

            ranked = np.argsort(scores)[::-1][:top_k]
            results = []
            for idx in ranked:
                if scores[idx] > 0:
                    results.append({
                        'chunk': self.chunks[idx],
                        'score': float(scores[idx])
                    })
            return results

    class QAChain:
        """问答链（模拟 LLM 生成）"""

        def generate(self, query, retrieved_chunks):
            """基于检索结果生成回答"""
            if not retrieved_chunks:
                return "抱歉，未找到相关信息。", []

            # 提取关键信息
            top_chunk = retrieved_chunks[0]
            context_text = top_chunk['chunk']['text']
            title = top_chunk['chunk']['title']

            # 模拟 LLM 生成回答
            answer = f"根据知识库，关于「{query}」：\n\n"
            answer += f"【{title}】\n{context_text}\n\n"

            if len(retrieved_chunks) > 1:
                answer += "补充信息：\n"
                for r in retrieved_chunks[1:]:
                    answer += f"  - {r['chunk']['title']}: {r['chunk']['text'][:60]}...\n"

            # 来源引用
            sources = []
            for r in retrieved_chunks:
                sources.append({
                    'title': r['chunk']['title'],
                    'doc_id': r['chunk']['doc_id'],
                    'chunk_id': r['chunk']['chunk_id'],
                    'score': r['score']
                })

            answer += "\n📚 引用来源：\n"
            for i, src in enumerate(sources, 1):
                answer += f"  [{i}] {src['title']} (相关度: {src['score']:.2%})\n"

            return answer, sources

    # ---- 8.3 运行完整 RAG Pipeline ----
    print("=" * 60)
    print("端到端 RAG 系统（Bug Bounty 知识库）")
    print("=" * 60)

    # 初始化组件
    loader = DocumentLoader()
    splitter = TextSplitter()
    vector_store = VectorStore()
    qa_chain = QAChain()

    # Indexing
    print("\n--- Indexing 阶段 ---")
    documents = loader.load(BUG_BOUNTY_KB)
    chunks = splitter.split(documents, chunk_size=150, overlap=30)
    vector_store.add(chunks)

    # 查询演示
    print("\n--- Retrieval + Generation 阶段 ---")
    questions = [
        "What is XSS and how to prevent it?",
        "How does SQL injection work?",
        "What is SSRF vulnerability?",
        "How to prevent CSRF attacks?",
        "What is insecure deserialization?",
    ]

    for question in questions:
        print(f"\n{'='*50}")
        print(f"❓ 问题: {question}")
        print(f"{'='*50}")

        # Retrieval
        results = vector_store.search(question, top_k=3)
        print(f"检索到 {len(results)} 个相关文档块:")
        for r in results:
            print(f"  [{r['score']:.4f}] {r['chunk']['title']}")

        # Generation
        answer, sources = qa_chain.generate(question, results)
        print(f"\n💡 回答:\n{answer}")

    # ---- 8.4 元数据过滤查询 ----
    print(f"\n{'='*50}")
    print("元数据过滤查询: severity='critical'")
    print(f"{'='*50}")
    results = vector_store.search("remote code execution", top_k=5,
                                  metadata_filter={"severity": "critical"})
    for r in results:
        print(f"  [{r['score']:.4f}] {r['chunk']['title']} ({r['chunk']['metadata']})")

    # ---- 思考题 ----
    print("\n" + "=" * 60)
    print("思考题：")
    print("1. 如果知识库文档频繁更新，如何实现增量索引？")
    print("   提示：记录文档 hash，只对变化的文档重新分块和向量化。")
    print("2. Source Citation 在实际产品中有什么价值？")
    print("   提示：可信度、可追溯、合规要求。")
    print("3. 如何评估这个 RAG 系统的回答质量？")
    print("   提示：下一题的 RAGAS 指标体系。")
    print("=" * 60)


# ============================================================
# 第 9 题：RAG 评估与优化 — RAGAS 指标体系
# ============================================================
"""
知识点讲解
-----------

1. RAGAS（RAG Assessment）框架简介：
   RAGAS 是专门评估 RAG 系统质量的框架，包含四个核心指标：
   
   - Faithfulness（忠实度）：回答是否基于检索到的上下文，没有捏造信息。
     分数 = 回答中可从上下文推导的陈述数 / 回答中总陈述数
   
   - Answer Relevancy（回答相关性）：回答是否切题，是否回答了用户问题。
     分数 = 与问题相关的回答内容比例
   
   - Context Precision（上下文精确率）：检索到的上下文中有多少是相关的。
     分数 = 相关上下文数 / 检索到的总上下文数
   
   - Context Recall（上下文召回率）：所有相关信息是否都被检索到。
     分数 = 检索到的相关信息 / 总相关信息

2. 评估数据集构建：
   要评估 RAG 系统，需要准备评估数据集：
   - question：用户问题
   - ground_truth：标准答案
   - contexts：RAG 系统检索到的上下文
   - answer：RAG 系统生成的回答

3. 本题的简化实现方案：
   不使用 LLM API，用基于规则的启发式方法模拟 RAGAS 指标：
   - Faithfulness：检查回答中的关键词是否出现在上下文中
   - Answer Relevancy：计算回答与问题的关键词重叠度
   - Context Precision：检查检索上下文中包含答案关键词的比例
   - Context Recall：检查标准答案的关键词是否被上下文覆盖

4. 调优实验设计：
   - chunk overlap 实验：对比 overlap=0/10/20/30 的效果
   - Top-K 实验：对比 K=1/3/5/7 的检索效果
   - 目标：找到最优参数组合

5. 评估报告输出：
   将各指标以表格和图表形式输出，帮助直观理解系统表现。
"""


def exercise_09():
    """第 9 题：RAGAS 评估与优化"""

    # ---- 9.1 简化版 RAGAS 评估器 ----

    class SimpleRAGAS:
        """简化版 RAGAS 评估器（基于规则，不使用 LLM API）"""

        def __init__(self):
            self.stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were',
                               'to', 'of', 'in', 'for', 'on', 'and', 'or',
                               'how', 'what', 'why', 'when', 'where', 'does',
                               'do', 'can', 'could', 'should', 'would', 'it',
                               'this', 'that', 'with', 'from', 'by', 'as', 'at'}

        def _extract_keywords(self, text):
            """提取关键词（去除停用词）"""
            words = re.findall(r'[a-zA-Z]{2,}', text.lower())
            return set(w for w in words if w not in self.stop_words)

        def _split_statements(self, text):
            """将回答拆分为陈述句"""
            sentences = re.split(r'[.!?]+', text)
            return [s.strip() for s in sentences if s.strip()]

        def faithfulness(self, answer, contexts):
            """忠实度：回答中的关键词是否来自上下文"""
            answer_keywords = self._extract_keywords(answer)
            context_keywords = set()
            for ctx in contexts:
                context_keywords |= self._extract_keywords(ctx)

            if not answer_keywords:
                return 1.0

            supported = answer_keywords & context_keywords
            return len(supported) / len(answer_keywords)

        def answer_relevancy(self, question, answer):
            """回答相关性：回答与问题的关键词重叠度"""
            q_keywords = self._extract_keywords(question)
            a_keywords = self._extract_keywords(answer)

            if not q_keywords:
                return 1.0

            relevant = q_keywords & a_keywords
            return len(relevant) / len(q_keywords)

        def context_precision(self, question, contexts):
            """上下文精确率：检索到的上下文有多少与问题相关"""
            q_keywords = self._extract_keywords(question)
            if not contexts:
                return 0.0

            relevant_count = 0
            for ctx in contexts:
                ctx_keywords = self._extract_keywords(ctx)
                overlap = q_keywords & ctx_keywords
                if len(overlap) / max(len(q_keywords), 1) > 0.1:  # 10% 阈值
                    relevant_count += 1

            return relevant_count / len(contexts)

        def context_recall(self, ground_truth, contexts):
            """上下文召回率：标准答案的关键词是否被上下文覆盖"""
            gt_keywords = self._extract_keywords(ground_truth)
            context_keywords = set()
            for ctx in contexts:
                context_keywords |= self._extract_keywords(ctx)

            if not gt_keywords:
                return 1.0

            covered = gt_keywords & context_keywords
            return len(covered) / len(gt_keywords)

        def evaluate(self, question, answer, contexts, ground_truth):
            """完整评估"""
            return {
                'faithfulness': self.faithfulness(answer, contexts),
                'answer_relevancy': self.answer_relevancy(question, answer),
                'context_precision': self.context_precision(question, contexts),
                'context_recall': self.context_recall(ground_truth, contexts),
            }

    # ---- 9.2 准备评估数据集 ----
    print("=" * 60)
    print("RAGAS 评估与优化")
    print("=" * 60)

    # 知识库文档
    kb_documents = [
        "XSS vulnerability allows attackers to inject malicious scripts into web pages viewed by users",
        "SQL injection attack manipulates database queries through user input to steal or modify data",
        "SSRF vulnerability tricks servers into making requests to internal network resources",
        "CSRF attack forces authenticated users to perform unwanted actions without their knowledge",
        "Buffer overflow occurs when programs write beyond allocated buffer causing memory corruption",
        "Directory traversal allows attackers to access files outside the intended web root directory",
        "Insecure deserialization can lead to remote code execution when processing untrusted data",
        "Broken authentication allows attackers to compromise user accounts and session tokens",
    ]

    # 评估数据集
    eval_dataset = [
        {
            "question": "What is XSS vulnerability?",
            "ground_truth": "XSS allows attackers to inject malicious scripts into web pages viewed by users",
            "relevant_doc_idx": 0,
        },
        {
            "question": "How does SQL injection work?",
            "ground_truth": "SQL injection manipulates database queries through user input to steal or modify data",
            "relevant_doc_idx": 1,
        },
        {
            "question": "What is SSRF attack?",
            "ground_truth": "SSRF tricks servers into making requests to internal network resources",
            "relevant_doc_idx": 2,
        },
        {
            "question": "How does CSRF attack work?",
            "ground_truth": "CSRF forces authenticated users to perform unwanted actions without their knowledge",
            "relevant_doc_idx": 3,
        },
        {
            "question": "What is buffer overflow?",
            "ground_truth": "Buffer overflow occurs when programs write beyond allocated buffer causing memory corruption",
            "relevant_doc_idx": 4,
        },
    ]

    # ---- 9.3 简单 RAG 检索器 ----

    def build_tfidf(docs):
        all_words = set()
        for doc in docs:
            all_words.update(doc.lower().split())
        vocab = {w: i for i, w in enumerate(sorted(all_words))}
        N = len(docs)
        df = np.zeros(len(vocab))
        for doc in docs:
            tokens = set(doc.lower().split())
            for w in tokens:
                if w in vocab:
                    df[vocab[w]] += 1
        idf = np.log(N / (1 + df))
        embeddings = np.zeros((N, len(vocab)))
        for i, doc in enumerate(docs):
            tokens = doc.lower().split()
            counter = Counter(tokens)
            total = len(tokens)
            for w, c in counter.items():
                if w in vocab:
                    embeddings[i, vocab[w]] = (c / total) * idf[vocab[w]]
            norm = np.linalg.norm(embeddings[i])
            if norm > 0:
                embeddings[i] /= norm
        return vocab, idf, embeddings

    def retrieve(query, vocab, idf, embeddings, top_k=3):
        q_vec = np.zeros(len(vocab))
        tokens = query.lower().split()
        counter = Counter(tokens)
        total = len(tokens)
        for w, c in counter.items():
            if w in vocab:
                q_vec[vocab[w]] = (c / total) * idf[vocab[w]]
        norm = np.linalg.norm(q_vec)
        if norm > 0:
            q_vec /= norm
        scores = embeddings @ q_vec
        ranked = np.argsort(scores)[::-1][:top_k]
        return [(int(idx), float(scores[idx])) for idx in ranked]

    def generate_answer(query, retrieved_docs, all_docs):
        """模拟生成回答"""
        if not retrieved_docs:
            return "No information found."
        top_doc = retrieved_docs[0]
        return all_docs[top_doc[0]]

    # ---- 9.4 基线评估 ----
    vocab, idf, embeddings = build_tfidf(kb_documents)
    ragas = SimpleRAGAS()

    print("\n--- 基线评估 (top_k=3) ---")
    print(f"{'问题':<35} | {'忠实度':>6} | {'相关性':>6} | {'精确率':>6} | {'召回率':>6}")
    print("-" * 75)

    baseline_scores = []
    for item in eval_dataset:
        retrieved = retrieve(item['question'], vocab, idf, embeddings, top_k=3)
        contexts = [kb_documents[idx] for idx, _ in retrieved]
        answer = generate_answer(item['question'], retrieved, kb_documents)

        scores = ragas.evaluate(item['question'], answer, contexts, item['ground_truth'])
        baseline_scores.append(scores)
        print(f"{item['question'][:33]:<35} | {scores['faithfulness']:>6.2%} | "
              f"{scores['answer_relevancy']:>6.2%} | {scores['context_precision']:>6.2%} | "
              f"{scores['context_recall']:>6.2%}")

    # 平均分
    avg_baseline = {
        k: np.mean([s[k] for s in baseline_scores])
        for k in baseline_scores[0]
    }
    print(f"\n{'平均':<35} | {avg_baseline['faithfulness']:>6.2%} | "
          f"{avg_baseline['answer_relevancy']:>6.2%} | "
          f"{avg_baseline['context_precision']:>6.2%} | "
          f"{avg_baseline['context_recall']:>6.2%}")

    # ---- 9.5 Top-K 实验 ----
    print("\n--- Top-K 选择实验 ---")
    k_values = [1, 2, 3, 5, 7]
    k_experiment = {}

    for k in k_values:
        scores_list = []
        for item in eval_dataset:
            retrieved = retrieve(item['question'], vocab, idf, embeddings, top_k=k)
            contexts = [kb_documents[idx] for idx, _ in retrieved]
            answer = generate_answer(item['question'], retrieved, kb_documents)
            scores = ragas.evaluate(item['question'], answer, contexts, item['ground_truth'])
            scores_list.append(scores)

        avg = {key: np.mean([s[key] for s in scores_list]) for key in scores_list[0]}
        k_experiment[k] = avg
        print(f"  k={k}: 忠实度={avg['faithfulness']:.2%}, 相关性={avg['answer_relevancy']:.2%}, "
              f"精确率={avg['context_precision']:.2%}, 召回率={avg['context_recall']:.2%}")

    # ---- 9.6 可视化 ----
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    # Top-K 实验结果
    metrics = ['faithfulness', 'answer_relevancy', 'context_precision', 'context_recall']
    metric_labels = ['Faithfulness', 'Answer Relevancy', 'Context Precision', 'Context Recall']
    colors = ['#3498DB', '#2ECC71', '#E67E22', '#9B59B6']

    for i, (metric, label) in enumerate(zip(metrics, metric_labels)):
        values = [k_experiment[k][metric] for k in k_values]
        axes[0].plot(k_values, values, 'o-', color=colors[i], linewidth=2,
                     markersize=8, label=label)

    axes[0].set_xlabel('Top-K')
    axes[0].set_ylabel('Score')
    axes[0].set_title('RAGAS Metrics vs Top-K')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    axes[0].set_ylim(0, 1.05)

    # 基线雷达图
    categories = metric_labels
    values = [avg_baseline[m] for m in metrics]
    values += values[:1]  # 闭合
    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    angles += angles[:1]

    ax2 = plt.subplot(1, 2, 2, projection='polar')
    ax2.plot(angles, values, 'o-', linewidth=2, color='#E74C3C')
    ax2.fill(angles, values, alpha=0.25, color='#E74C3C')
    ax2.set_xticks(angles[:-1])
    ax2.set_xticklabels(categories, fontsize=9)
    ax2.set_ylim(0, 1)
    ax2.set_title('Baseline RAGAS Scores', pad=20)
    ax2.grid(True)

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, 'ex09_ragas_evaluation.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n[图] RAGAS 评估报告已保存: {FIG_DIR}/ex09_ragas_evaluation.png")

    # ---- 9.7 评估报告 ----
    print("\n--- RAGAS 评估报告 ---")
    print(f"{'指标':<25} | {'基线得分':>10} | {'最优K':>6} | {'最优得分':>10}")
    print("-" * 60)
    for metric, label in zip(metrics, metric_labels):
        baseline = avg_baseline[metric]
        best_k = max(k_values, key=lambda k: k_experiment[k][metric])
        best_score = k_experiment[best_k][metric]
        print(f"{label:<25} | {baseline:>10.2%} | {best_k:>6} | {best_score:>10.2%}")

    # ---- 思考题 ----
    print("\n" + "=" * 60)
    print("思考题：")
    print("1. RAGAS 的四个指标中，哪个最难用规则方法准确评估？")
    print("   提示：Faithfulness 需要理解因果关系，纯关键词匹配不够。")
    print("2. Top-K 增大时，context_precision 和 context_recall 如何变化？")
    print("   提示：precision 下降（更多无关内容），recall 上升（覆盖更全）。")
    print("3. 除了 RAGAS，还有哪些 RAG 评估方法？")
    print("   提示：人工评估、A/B 测试、LLM-as-a-Judge。")
    print("=" * 60)


# ============================================================
# 第 10 题：Agent + RAG 融合 — 知识增强 Agent
# ============================================================
"""
知识点讲解
-----------

1. Agent + RAG 融合的核心思想：
   传统 RAG 是被动检索：每次查询都检索知识库。
   Agent + RAG 是主动检索：Agent 自主判断是否需要检索，
   选择检索什么内容，并整合多次检索结果。

2. Agent Tool 化 RAG：
   将 RAG 检索封装为一个 Tool（工具），供 Agent 调用：
   - Tool 名称：search_knowledge_base
   - Tool 描述：搜索 Bug Bounty 知识库，返回相关漏洞信息
   - Tool 参数：query (搜索关键词), top_k (返回数量)
   
   Agent 的工作循环：
   接收用户输入 → 判断是否需要检索 → 调用 Tool → 整合结果 → 生成回答

3. 多轮对话中的上下文管理：
   - 短期记忆：当前对话的历史消息
   - 长期记忆：持久化存储的用户偏好和历史结论
   - 上下文窗口管理：当对话过长时，自动摘要或截断
   
   Agent 需要维护对话状态，包括：
   - 历史问答记录
   - 已检索过的知识
   - 当前对话主题

4. Agent 的决策逻辑（简化实现）：
   - 关键词检测：如果用户问题包含特定关键词（如"什么是"、"如何"），
     则触发 RAG 检索
   - 上下文检查：如果上一轮已检索过相关内容，直接复用
   - 回退策略：如果检索结果不相关，尝试重新检索或告知用户

5. 本题实现一个简化版 Bug Bounty 知识库问答 Agent：
   - 具备多轮对话能力
   - 能判断是否需要检索知识库
   - 支持长期记忆持久化
   - 模拟真实 Agent 的工作流程
"""


def exercise_10():
    """第 10 题：Agent + RAG 融合"""

    # ---- 10.1 RAG Tool 封装 ----

    class KnowledgeBaseTool:
        """RAG 检索工具（供 Agent 调用）"""

        def __init__(self, documents):
            self.documents = documents
            self._build_index()
            self.search_count = 0  # 统计调用次数

        def _build_index(self):
            """构建 TF-IDF 索引"""
            all_words = set()
            for doc in self.documents:
                all_words.update(doc.lower().split())
            self.vocab = {w: i for i, w in enumerate(sorted(all_words))}
            N = len(self.documents)
            df = np.zeros(len(self.vocab))
            for doc in self.documents:
                tokens = set(doc.lower().split())
                for w in tokens:
                    if w in self.vocab:
                        df[self.vocab[w]] += 1
            self.idf = np.log(N / (1 + df))

            self.embeddings = np.zeros((N, len(self.vocab)))
            for i, doc in enumerate(self.documents):
                tokens = doc.lower().split()
                counter = Counter(tokens)
                total = len(tokens)
                for w, c in counter.items():
                    if w in self.vocab:
                        w_idx = self.vocab[w]
                        self.embeddings[i, w_idx] = (c / total) * self.idf[w_idx]
                norm = np.linalg.norm(self.embeddings[i])
                if norm > 0:
                    self.embeddings[i] /= norm

        def search(self, query, top_k=3):
            """搜索知识库"""
            self.search_count += 1
            q_vec = np.zeros(len(self.vocab))
            tokens = query.lower().split()
            counter = Counter(tokens)
            total = len(tokens)
            for w, c in counter.items():
                if w in self.vocab:
                    q_vec[self.vocab[w]] = (c / total) * self.idf[self.vocab[w]]
            norm = np.linalg.norm(q_vec)
            if norm > 0:
                q_vec /= norm

            scores = self.embeddings @ q_vec
            ranked = np.argsort(scores)[::-1][:top_k]
            results = []
            for idx in ranked:
                if scores[idx] > 0.01:
                    results.append({
                        'doc_id': int(idx),
                        'score': float(scores[idx]),
                        'text': self.documents[idx]
                    })
            return results

    # ---- 10.2 Agent 实现 ----

    class BugBountyAgent:
        """Bug Bounty 知识库问答 Agent"""

        # 触发检索的关键词
        SEARCH_TRIGGERS = ['what', 'how', 'explain', 'describe', 'tell',
                           'vulnerability', 'attack', 'prevent', 'exploit',
                           'security', 'injection', 'xss', 'sql', 'ssrf',
                           'csrf', 'overflow', 'authentication']

        def __init__(self, knowledge_base_docs):
            self.rag_tool = KnowledgeBaseTool(knowledge_base_docs)
            self.conversation_history = []   # 短期记忆
            self.long_term_memory = {}        # 长期记忆
            self.memory_file = os.path.join(FIG_DIR, "agent_memory.json")
            self._load_memory()

        def _load_memory(self):
            """加载长期记忆"""
            if os.path.exists(self.memory_file):
                try:
                    with open(self.memory_file, 'r') as f:
                        self.long_term_memory = json.load(f)
                except Exception:
                    self.long_term_memory = {}

        def _save_memory(self):
            """保存长期记忆"""
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.long_term_memory, f, ensure_ascii=False, indent=2)

        def _needs_retrieval(self, user_input):
            """判断是否需要检索知识库"""
            input_lower = user_input.lower()
            # 检查是否包含触发关键词
            has_trigger = any(trigger in input_lower for trigger in self.SEARCH_TRIGGERS)
            # 检查是否是简短问候（不需要检索）
            greetings = ['hello', 'hi', 'hey', 'thanks', 'thank', 'bye', 'ok']
            is_greeting = any(input_lower.strip() == g for g in greetings)
            return has_trigger and not is_greeting

        def _check_context(self, user_input):
            """检查上下文是否已有相关信息"""
            for msg in reversed(self.conversation_history):
                if msg['role'] == 'user' and msg.get('retrieved'):
                    # 简单检查是否有共同关键词
                    input_words = set(user_input.lower().split())
                    prev_words = set(msg['content'].lower().split())
                    overlap = input_words & prev_words
                    if len(overlap) >= 2:
                        return msg.get('retrieved', [])
            return None

        def _generate_answer(self, user_input, retrieved_docs):
            """生成回答（模拟 LLM）"""
            if not retrieved_docs:
                return f"我没有找到关于「{user_input}」的相关信息。你能换个方式描述吗？"

            top_doc = retrieved_docs[0]
            answer = f"关于你的问题，我找到了以下信息：\n\n"
            answer += f"📌 {top_doc['text']}\n"

            if len(retrieved_docs) > 1:
                answer += f"\n补充参考：\n"
                for r in retrieved_docs[1:]:
                    answer += f"  • {r['text'][:60]}...\n"

            answer += f"\n（来源：知识库文档 #{top_doc['doc_id']}, 相关度={top_doc['score']:.2%}）"
            return answer

        def chat(self, user_input):
            """Agent 对话主循环"""
            print(f"\n{'='*50}")
            print(f"👤 用户: {user_input}")
            print(f"{'='*50}")

            # Step 1: 判断是否需要检索
            needs_search = self._needs_retrieval(user_input)
            print(f"🤖 Agent 判断: {'需要检索知识库' if needs_search else '无需检索，直接回复'}")

            retrieved_docs = []
            if needs_search:
                # Step 2: 检查上下文是否已有相关信息
                cached = self._check_context(user_input)
                if cached:
                    print(f"🤖 Agent: 从上下文中复用之前的检索结果")
                    retrieved_docs = cached
                else:
                    # Step 3: 调用 RAG Tool 检索
                    print(f"🤖 Agent: 调用 search_knowledge_base(query='{user_input}', top_k=3)")
                    retrieved_docs = self.rag_tool.search(user_input, top_k=3)
                    print(f"🤖 Agent: 检索到 {len(retrieved_docs)} 条结果")
                    for r in retrieved_docs:
                        print(f"   [{r['score']:.4f}] {r['text'][:50]}...")

            # Step 4: 生成回答
            answer = self._generate_answer(user_input, retrieved_docs)
            print(f"\n🤖 Agent 回答:\n{answer}")

            # Step 5: 更新记忆
            self.conversation_history.append({
                'role': 'user',
                'content': user_input,
                'retrieved': retrieved_docs
            })
            self.conversation_history.append({
                'role': 'assistant',
                'content': answer
            })

            # 更新长期记忆（记录用户感兴趣的主题）
            key = hashlib.md5(user_input.encode()).hexdigest()[:8]
            self.long_term_memory[key] = {
                'question': user_input,
                'answer': answer[:100],
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            self._save_memory()

            return answer

        def show_stats(self):
            """显示 Agent 统计信息"""
            print(f"\n{'='*50}")
            print("Agent 统计信息")
            print(f"{'='*50}")
            print(f"  对话轮数: {len(self.conversation_history) // 2}")
            print(f"  RAG 检索次数: {self.rag_tool.search_count}")
            print(f"  长期记忆条目: {len(self.long_term_memory)}")
            print(f"  记忆文件: {self.memory_file}")

    # ---- 10.3 运行 Agent 对话 ----
    print("=" * 60)
    print("Agent + RAG 融合：Bug Bounty 知识库问答机器人")
    print("=" * 60)

    # Bug Bounty 知识库
    kb_docs = [
        "Cross-Site Scripting XSS is a vulnerability that allows attackers to inject malicious scripts into web pages viewed by other users Prevention includes input sanitization and output encoding",
        "SQL Injection occurs when attackers manipulate SQL queries through user input fields to steal modify or delete database data Use parameterized queries to prevent SQL injection attacks",
        "Server-Side Request Forgery SSRF tricks a server into making requests to internal network resources allowing attackers to access internal services and cloud metadata endpoints",
        "Cross-Site Request Forgery CSRF forces authenticated users to execute unwanted actions by exploiting their session cookies Use anti-CSRF tokens and SameSite cookie attribute for prevention",
        "Buffer Overflow occurs when a program writes more data to a buffer than it can hold causing memory corruption and potential remote code execution Use bounds checking and safe functions",
        "Insecure Direct Object Reference IDOR allows attackers to access unauthorized resources by manipulating object identifiers in URLs or parameters Implement proper authorization checks",
        "Insecure Deserialization vulnerability occurs when applications deserialize untrusted data leading to remote code execution or privilege escalation Avoid deserializing untrusted data",
        "Broken Authentication allows attackers to compromise user accounts through weak passwords credential stuffing or session hijacking Implement multi-factor authentication and rate limiting",
    ]

    agent = BugBountyAgent(kb_docs)

    # 模拟多轮对话
    conversations = [
        "Hello, I am learning about web security",
        "What is XSS vulnerability and how to prevent it?",
        "How does SQL injection work?",
        "Can you tell me about CSRF attack?",
        "What is buffer overflow?",
        "Thanks for the information!",
    ]

    for user_input in conversations:
        agent.chat(user_input)

    # 显示统计
    agent.show_stats()

    # ---- 10.4 Agent 决策流程可视化 ----
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis('off')
    ax.set_title('Agent + RAG: Decision Flow', fontsize=16, fontweight='bold')

    def draw_box(ax, x, y, w, h, text, color='#4ECDC4', fontsize=9):
        rect = plt.Rectangle((x, y), w, h, facecolor=color, edgecolor='#2C3E50',
                              linewidth=1.5, alpha=0.85, zorder=2)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, text, ha='center', va='center',
                fontsize=fontsize, fontweight='bold', color='white', zorder=3)

    def draw_arrow(ax, x1, y1, x2, y2, label=''):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='->', color='#2C3E50', lw=2), zorder=1)
        if label:
            mx, my = (x1+x2)/2, (y1+y2)/2
            ax.text(mx+0.2, my, label, fontsize=8, color='#7F8C8D',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))

    def draw_diamond(ax, cx, cy, w, h, text, color='#F39C12', fontsize=8):
        diamond = plt.Polygon([(cx, cy+h/2), (cx+w/2, cy), (cx, cy-h/2), (cx-w/2, cy)],
                               facecolor=color, edgecolor='#2C3E50', linewidth=1.5, alpha=0.85, zorder=2)
        ax.add_patch(diamond)
        ax.text(cx, cy, text, ha='center', va='center', fontsize=fontsize,
                fontweight='bold', color='white', zorder=3)

    # 流程图
    draw_box(ax, 5, 8.5, 4, 1, 'User Input', '#3498DB')
    draw_arrow(ax, 7, 8.5, 7, 7.8)

    draw_diamond(ax, 7, 7.2, 3.5, 1.2, 'Needs\nRetrieval?')
    draw_arrow(ax, 5.2, 7.2, 3.5, 7.2, 'No')
    draw_arrow(ax, 8.8, 7.2, 10.5, 7.2, 'Yes')

    # No 分支
    draw_box(ax, 1, 6.5, 3, 1, 'Direct\nResponse', '#E67E22')
    draw_arrow(ax, 2.5, 6.5, 2.5, 5.5)

    # Yes 分支
    draw_diamond(ax, 11.5, 6.5, 3.5, 1.2, 'Has\nContext?')
    draw_arrow(ax, 10, 6.5, 8.5, 6.5, 'Yes')

    draw_box(ax, 8, 5.5, 3, 1, 'Reuse Cached\nResults', '#27AE60')
    draw_arrow(ax, 13, 6.5, 13, 5.5)
    draw_arrow(ax, 13, 5.5, 13, 4.5)

    draw_box(ax, 11, 4.5, 4, 1, 'Call RAG Tool\n(search_knowledge_base)', '#9B59B6')
    draw_arrow(ax, 11, 5.0, 9.5, 5.0)

    # 汇合
    draw_box(ax, 4, 4, 5, 1.2, 'Generate Answer\n(LLM / Template)', '#16A085')
    draw_arrow(ax, 2.5, 5.5, 4, 4.8)
    draw_arrow(ax, 8, 5.5, 6.5, 4.6)

    draw_box(ax, 4, 2.5, 5, 1, 'Update Memory\n(Short + Long Term)', '#8E44AD')
    draw_arrow(ax, 6.5, 4, 6.5, 3.5)

    draw_box(ax, 4, 1, 5, 1, 'Return Answer\n+ Sources', '#2C3E50')
    draw_arrow(ax, 6.5, 2.5, 6.5, 2)

    plt.tight_layout()
    plt.savefig(os.path.join(FIG_DIR, 'ex10_agent_rag_flow.png'), dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\n[图] Agent+RAG 决策流程图已保存: {FIG_DIR}/ex10_agent_rag_flow.png")

    # ---- 思考题 ----
    print("\n" + "=" * 60)
    print("思考题：")
    print('1. Agent 如何判断"是否需要检索"？除了关键词匹配，')
    print("   还有什么更智能的方法？")
    print("   提示：LLM 意图识别、分类模型。")
    print("2. 多轮对话中，如何避免重复检索相同内容？")
    print("   提示：缓存机制、上下文窗口管理、对话摘要。")
    print("3. 如果知识库很大（百万级文档），Agent 的 RAG Tool")
    print("   应该如何优化？")
    print("   提示：分级检索、缓存热点查询、异步检索。")
    print("=" * 60)


# ============================================================
# 主函数：运行所有练习题
# ============================================================

def main():
    print("=" * 70)
    print("  阶段十二：RAG 检索增强生成 — 10 道练习题")
    print("  覆盖：向量嵌入 | 向量数据库 | 文档分块 | 混合检索 |")
    print("        端到端RAG | RAGAS评估 | Agent+RAG 融合")
    print("=" * 70)

    exercises = [
        ("第 1 题", "向量嵌入与语义搜索", exercise_01),
        ("第 2 题", "RAG 架构全貌", exercise_02),
        ("第 3 题", "Chroma 向量库模拟", exercise_03),
        ("第 4 题", "pgvector 与 HNSW 索引", exercise_04),
        ("第 5 题", "Milvus 与 IVF 索引", exercise_05),
        ("第 6 题", "文档分块策略", exercise_06),
        ("第 7 题", "混合检索与重排序", exercise_07),
        ("第 8 题", "端到端 RAG 系统", exercise_08),
        ("第 9 题", "RAGAS 评估与优化", exercise_09),
        ("第 10 题", "Agent + RAG 融合", exercise_10),
    ]

    for label, title, func in exercises:
        print(f"\n{'#' * 70}")
        print(f"# {label}: {title}")
        print(f"{'#' * 70}")
        try:
            func()
            print(f"\n✅ {label} 运行完成")
        except Exception as e:
            print(f"\n❌ {label} 运行出错: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'=' * 70}")
    print("  所有练习题执行完毕！")
    print(f"  可视化图片保存在: {FIG_DIR}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
