# 从零实现RAG系统：纯NumPy打造向量检索引擎

> **摘要**：RAG（检索增强生成）是当前大模型应用最火热的技术方向之一，但很多人只停留在调用LangChain API的层面。本文基于3000+行的纯NumPy练习代码，从零实现TF-IDF向量嵌入、余弦相似度检索、BM25关键词匹配、RRF混合检索、HNSW/IVF向量索引、文档分块策略、端到端RAG Pipeline以及RAGAS评估指标，帮助开发者真正理解RAG的底层原理。

**关键词**：RAG、向量检索、TF-IDF、BM25、HNSW、RAGAS、NumPy

---

## 一、为什么需要从零实现RAG？

当你使用LangChain的`RetrievalQA.from_chain_type()`一行代码完成RAG查询时，你是否思考过：向量是怎么生成的？相似度是怎么计算的？为什么Top-K=3而不是5？

理解底层原理的价值在于：
1. **调优有据**：知道chunk_size、overlap、top_k每个参数的影响
2. **排查问题**：检索结果不准时，知道从哪个环节入手
3. **技术选型**：FLAT、IVF、HNSW索引各自适合什么场景
4. **成本控制**：理解向量维度和索引类型对内存和延迟的影响

本文所有代码均来自实际练习文件，使用纯NumPy实现，无需安装任何框架。

---

## 二、TF-IDF向量嵌入：一切从词频开始

### 2.1 核心思想

向量嵌入的本质是将文本映射到高维空间，使语义相近的文本在空间中距离也近。TF-IDF是最基础的嵌入方法，虽然不理解语义，但它是理解Word2Vec、BERT Embedding的最佳起点。

- **TF（词频）**：某词在文档中出现的频率，`TF = 词出现次数 / 文档总词数`
- **IDF（逆文档频率）**：衡量词的区分能力，`IDF = log(N / (1 + DF))`，其中N是文档总数，DF是包含该词的文档数
- **TF-IDF = TF × IDF**：高频且稀有的词得分高

### 2.2 纯NumPy实现

```python
import numpy as np
from collections import Counter

# 准备语料库
documents = [
    "Python is a popular programming language for data science",
    "Machine learning models need large datasets for training",
    "The cat sits on the mat in the living room",
    "Deep learning uses neural networks to learn patterns",
]

# 构建词汇表
all_tokens = []
for doc in documents:
    all_tokens.extend(doc.lower().split())
vocab = sorted(set(all_tokens))
vocab_index = {word: i for i, word in enumerate(vocab)}

# 计算 TF
def compute_tf(tokens, vocab_idx):
    tf = np.zeros(len(vocab_idx))
    counter = Counter(tokens)
    total = len(tokens)
    for word, count in counter.items():
        if word in vocab_idx:
            tf[vocab_idx[word]] = count / total
    return tf

# 计算 IDF
N = len(documents)
df = np.zeros(len(vocab))
for doc in documents:
    tokens = set(doc.lower().split())
    for word in tokens:
        if word in vocab_index:
            df[vocab_index[word]] += 1
idf = np.log(N / (1 + df))

# 构建 TF-IDF 矩阵
tfidf_matrix = np.zeros((N, len(vocab)))
for i, doc in enumerate(documents):
    tfidf_matrix[i] = compute_tf(doc.lower().split(), vocab_index) * idf
```

### 2.3 三种相似度度量

```python
def cosine_similarity(a, b):
    """余弦相似度：衡量方向一致性，取值[-1,1]"""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return np.dot(a, b) / (norm_a * norm_b)

def dot_product(a, b):
    """点积：未归一化，受向量长度影响"""
    return np.dot(a, b)

def euclidean_distance(a, b):
    """欧式距离：衡量绝对距离，取值[0,+∞)"""
    return np.linalg.norm(a - b)
```

余弦相似度在文本检索中最常用，因为它不受文档长度影响——长文档和短文档只要方向一致就判定为相似。

---

## 三、RAG架构全貌：三阶段流水线

RAG将"检索"和"生成"结合，分为三大阶段：

```
┌─────────────────────────────────────────────────┐
│  Stage 1: Indexing（索引）                       │
│  Load → Split → Embed → Store                    │
├─────────────────────────────────────────────────┤
│  Stage 2: Retrieval（检索）                      │
│  Query → Embed → Search → Rank                   │
├─────────────────────────────────────────────────┤
│  Stage 3: Generation（生成）                     │
│  Context → Prompt → LLM → Answer + Sources       │
└─────────────────────────────────────────────────┘
```

### 3.1 最简RAG Pipeline

```python
class SimpleRAG:
    def __init__(self):
        self.documents = []
        self.embeddings = []
        self.vocabulary = {}

    # === Indexing 阶段 ===
    def load(self, texts):
        self.documents = texts

    def split(self, text, chunk_size=50, overlap=10):
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end - overlap  # 重叠部分
        return chunks

    def embed(self, text):
        vec = np.zeros(len(self.vocabulary))
        for word in text.lower().split():
            if word in self.vocabulary:
                vec[self.vocabulary[word]] += 1
        # L2归一化
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def store(self):
        self.embeddings = np.array([self.embed(doc) for doc in self.documents])

    # === Retrieval 阶段 ===
    def retrieve(self, query, top_k=3):
        query_vec = self.embed(query)
        # 向量已归一化，点积即为余弦相似度
        scores = self.embeddings @ query_vec
        ranked = np.argsort(scores)[::-1][:top_k]
        return [{'doc_id': int(idx), 'score': float(scores[idx]),
                 'text': self.documents[idx]} for idx in ranked]

    # === Generation 阶段（模板匹配模拟）===
    def generate(self, query, retrieved_docs):
        context_words = set()
        for doc in retrieved_docs:
            context_words.update(doc['text'].lower().split())
        query_words = set(query.lower().split())
        matched = query_words & context_words
        answer = f"根据知识库检索结果，关于「{query}」的回答如下：\n"
        answer += f"匹配到 {len(matched)} 个关键词：{', '.join(sorted(matched))}\n"
        answer += "参考来源：\n"
        for doc in retrieved_docs[:2]:
            answer += f"  - [文档{doc['doc_id']}, 相关度={doc['score']:.2f}]\n"
        return answer

    def query_pipeline(self, question, top_k=3):
        retrieved = self.retrieve(question, top_k=top_k)
        return self.generate(question, retrieved)
```

这里用模板匹配模拟LLM生成，实际生产中替换为GPT/Claude API即可。关键在于理解数据流转：**查询向量化 → 矩阵乘法计算相似度 → Top-K排序 → 拼接上下文**。

---

## 四、BM25：经典关键词检索算法

### 4.1 BM25原理

BM25（Best Matching 25）是搜索引擎领域最经典的关键词检索算法，相比TF-IDF，它引入了两个关键改进：

- **词频饱和**：词频增长到一定程度后，对分数的贡献递减（防止关键词堆砌）
- **文档长度归一化**：惩罚过长的文档（长文档更容易匹配，但不一定更相关）

核心公式：

```
score(D, Q) = Σ IDF(qi) × (f(qi,D) × (k1+1)) / (f(qi,D) + k1 × (1 - b + b × |D|/avgdl))
```

其中k1控制词频饱和速度（通常1.2~2.0），b控制文档长度归一化强度（通常0.75）。

### 4.2 纯Python实现

```python
class BM25:
    def __init__(self, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.doc_freqs = []
        self.idf = {}
        self.avgdl = 0
        self.doc_len = []
        self.N = 0

    def fit(self, documents):
        self.N = len(documents)
        self.doc_len = [len(doc.split()) for doc in documents]
        self.avgdl = np.mean(self.doc_len) if self.doc_len else 0

        df = defaultdict(int)
        self.doc_freqs = []
        for doc in documents:
            tokens = doc.split()
            freq = Counter(tokens)
            self.doc_freqs.append(freq)
            for word in freq.keys():
                df[word] += 1

        for word, freq in df.items():
            self.idf[word] = math.log((self.N - freq + 0.5) / (freq + 0.5) + 1)

    def search(self, query, k=5):
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
```

---

## 五、RRF混合检索：语义+关键词的双重保险

### 5.1 为什么需要混合检索？

向量检索擅长**语义匹配**（同义词、概念关联），但对精确关键词、专有名词、代码标识符的匹配能力较弱。BM25则正好相反。

混合检索将两者结合，取长补短。

### 5.2 RRF（Reciprocal Rank Fusion）

RRF是一种简单但有效的融合方法，不需要分数归一化，对不同尺度的分数更鲁棒：

```python
def hybrid_search(vector_results, bm25_results, alpha=0.5, k=5):
    """混合检索：RRF融合"""
    scores = defaultdict(float)
    # 向量检索贡献
    for rank, (idx, score) in enumerate(vector_results):
        scores[idx] += alpha * (1.0 / (rank + 1))
    # BM25贡献
    for rank, (idx, score) in enumerate(bm25_results):
        scores[idx] += (1 - alpha) * (1.0 / (rank + 1))

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]
    return [(idx, score) for idx, score in ranked]
```

RRF的核心思想：**排名越靠前的文档得分越高**（第1名得1分，第2名得0.5分，第3名得0.33分...），两个检索系统的排名通过倒数相加融合。

### 5.3 Reranker重排序

混合检索后还可以加一层Reranker精排：

```python
def simple_reranker(query, documents, top_indices, top_k=3):
    """简化版Reranker：基于关键词重叠度重排序"""
    query_words = set(query.lower().split())
    reranked = []
    for idx in top_indices:
        doc_words = set(documents[idx].lower().split())
        overlap = len(query_words & doc_words)
        jaccard = overlap / len(query_words | doc_words) if query_words | doc_words else 0
        reranked.append((idx, jaccard))
    reranked.sort(key=lambda x: x[1], reverse=True)
    return reranked[:top_k]
```

生产环境中通常使用Cross-encoder模型（如bge-reranker）做精排，效果远好于基于规则的方法。

---

## 六、向量索引：HNSW与IVF

当文档数量达到百万级，暴力搜索（计算查询与所有文档的相似度）会变得很慢。这时需要近似最近邻（ANN）索引来加速。

### 6.1 HNSW索引

HNSW（Hierarchical Navigable Small World）构建多层图结构：上层稀疏用于快速导航，下层稠密用于精确搜索。查询时从最上层贪婪搜索，逐层下降。

```python
class SimpleHNSW:
    def __init__(self, dim=64, max_m=8, ef_construction=50, ef_search=20, max_layers=4):
        self.dim = dim
        self.max_m = max_m
        self.ef_construction = ef_construction
        self.ef_search = ef_search
        self.max_layers = max_layers
        self.data = []
        self.layers = []
        self.entry_point = None
        self.entry_layer = 0

    def _random_level(self):
        """根据指数分布随机选择层级"""
        level = 0
        while np.random.random() < 0.5 and level < self.max_layers - 1:
            level += 1
        return level

    def add(self, vec):
        node_id = len(self.data)
        self.data.append(vec)
        level = self._random_level()
        # 初始化各层，从顶层向下搜索并连接邻居...
        # （完整实现见源码）

    def search(self, query, k=5):
        if not self.data:
            return []
        entry_points = [self.entry_point]
        # 从顶层搜索到第1层
        for layer in range(self.entry_layer, 0, -1):
            results = self._search_layer(query, entry_points, 1, layer)
            if results:
                entry_points = [results[0][1]]
        # 在第0层精细搜索
        results = self._search_layer(query, entry_points, max(self.ef_search, k), 0)
        results.sort()
        return [(dist, nid) for dist, nid in results[:k]]
```

### 6.2 IVF索引

IVF（Inverted File）用K-Means将向量空间划分为nlist个聚类。查询时只搜索最近的nprobe个聚类，将搜索范围从N缩小到 N × nprobe / nlist。

```python
class IVFIndex:
    def __init__(self, nlist=10, nprobe=3):
        self.nlist = nlist
        self.nprobe = nprobe

    def build(self, data):
        self.data = np.array(data)
        # K-Means聚类
        self.centroids, assignments = self._kmeans(self.data, self.nlist)
        # 构建倒排表
        self.clusters = defaultdict(list)
        for i, cluster_id in enumerate(assignments):
            self.clusters[cluster_id].append(i)

    def search(self, query, k=5):
        # 找到最近的nprobe个聚类
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
```

### 6.3 性能对比实测

在500个64维向量的测试中：

| 方法 | 搜索时间 | 加速比 | 平均召回率 |
|------|---------|--------|-----------|
| 暴力搜索 | 基准 | 1.0x | 100% |
| HNSW | 约为基准的1/3 | ~3x | ~95% |
| IVF(nprobe=5) | 约为基准的1/2 | ~2x | ~90% |

关键发现：**nprobe越大，召回率越高但速度越慢**，需要在精度和性能之间权衡。

---

## 七、文档分块策略

分块（Chunking）是RAG中容易被忽视但影响巨大的环节。

### 7.1 三种分块策略

```python
# 1. 固定大小分块
def fixed_size_split(text, chunk_size=100, overlap=20):
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + chunk_size])
        start = start + chunk_size - overlap
    return [c for c in chunks if c.strip()]

# 2. 递归字符分块（LangChain默认策略）
def recursive_character_split(text, chunk_size=100, overlap=20):
    separators = ["\n\n", "\n", ". ", " ", ""]
    # 按分隔符优先级递归切分，优先在自然边界处切分
    # （完整实现见源码）

# 3. Token分块
def token_based_split(text, chunk_size=80, overlap=15):
    tokens = text.split()
    chunks = []
    start = 0
    while start < len(tokens):
        chunks.append(" ".join(tokens[start:start + chunk_size]))
        start = start + chunk_size - overlap
    return [c for c in chunks if c.strip()]
```

### 7.2 分块策略对检索质量的影响

实测对比三种策略的检索召回率：

| 策略 | 块数 | 平均召回率 |
|------|------|-----------|
| Fixed-Size | 8 | 60% |
| Recursive | 6 | 80% |
| Token-Based | 7 | 70% |

Recursive策略表现最好，因为它优先在段落和句子边界切分，保持了语义完整性。

**经验法则**：overlap设为chunk_size的10%~20%，避免边界信息丢失。

---

## 八、RAGAS评估：量化RAG系统质量

### 8.1 四大核心指标

RAGAS（RAG Assessment）框架包含四个核心指标：

| 指标 | 含义 | 评估方法 |
|------|------|---------|
| Faithfulness（忠实度） | 回答是否基于检索上下文，没有捏造 | 回答中可从上下文推导的关键词比例 |
| Answer Relevancy（回答相关性） | 回答是否切题 | 回答与问题的关键词重叠度 |
| Context Precision（上下文精确率） | 检索到的上下文有多少相关 | 相关上下文数/检索总上下文数 |
| Context Recall（上下文召回率） | 相关信息是否都被检索到 | 检索到的相关信息/总相关信息 |

### 8.2 简化实现

```python
class SimpleRAGAS:
    def __init__(self):
        self.stop_words = {'the', 'a', 'an', 'is', 'are', 'to', 'of', 'in', ...}

    def _extract_keywords(self, text):
        words = re.findall(r'[a-zA-Z]{2,}', text.lower())
        return set(w for w in words if w not in self.stop_words)

    def faithfulness(self, answer, contexts):
        """忠实度：回答关键词是否来自上下文"""
        answer_kw = self._extract_keywords(answer)
        context_kw = set()
        for ctx in contexts:
            context_kw |= self._extract_keywords(ctx)
        if not answer_kw:
            return 1.0
        return len(answer_kw & context_kw) / len(answer_kw)

    def context_recall(self, ground_truth, contexts):
        """上下文召回率：标准答案关键词是否被覆盖"""
        gt_kw = self._extract_keywords(ground_truth)
        context_kw = set()
        for ctx in contexts:
            context_kw |= self._extract_keywords(ctx)
        if not gt_kw:
            return 1.0
        return len(gt_kw & context_kw) / len(gt_kw)
```

### 8.3 Top-K参数实验

实测不同Top-K值对四项指标的影响：

| K值 | 忠实度 | 回答相关性 | 上下文精确率 | 上下文召回率 |
|-----|--------|-----------|-------------|-------------|
| 1 | 100% | 80% | 100% | 40% |
| 3 | 100% | 80% | 67% | 60% |
| 5 | 100% | 80% | 40% | 80% |
| 7 | 100% | 80% | 29% | 100% |

关键发现：**K增大时，precision下降（更多无关内容），recall上升（覆盖更全）**。需要根据场景选择平衡点，通常K=3~5是较好的折中。

---

## 九、端到端RAG：Bug Bounty知识库实战

将所有组件串联起来，构建一个完整的端到端RAG系统：

```python
# 1. 文档加载
loader = DocumentLoader()
documents = loader.load(BUG_BOUNTY_KB)

# 2. 文本分块
splitter = TextSplitter()
chunks = splitter.split(documents, chunk_size=150, overlap=30)

# 3. 向量化存储
vector_store = VectorStore()
vector_store.add(chunks)

# 4. 检索 + 生成
question = "What is XSS and how to prevent it?"
results = vector_store.search(question, top_k=3)
answer, sources = qa_chain.generate(question, results)
```

输出示例：

```
❓ 问题: What is XSS and how to prevent it?

检索到 3 个相关文档块:
  [0.8543] Cross-Site Scripting (XSS)
  [0.3214] SQL Injection
  [0.2891] CSRF

💡 回答:
根据知识库，关于「What is XSS and how to prevent it?」：
【Cross-Site Scripting (XSS)】
XSS is a vulnerability that allows attackers to inject malicious scripts...

📚 引用来源：
  [1] Cross-Site Scripting (XSS) (相关度: 85.43%)
  [2] SQL Injection (相关度: 32.14%)
  [3] CSRF (相关度: 28.91%)
```

---

## 十、总结

通过纯NumPy从零实现RAG系统，我们深入理解了以下核心概念：

1. **TF-IDF向量嵌入**：词频×逆文档频率，高频且稀有的词权重高
2. **余弦相似度**：归一化后的点积，不受向量长度影响
3. **BM25**：引入词频饱和和文档长度归一化，优于纯TF-IDF
4. **RRF混合检索**：倒数排名融合，无需分数归一化
5. **HNSW/IVF索引**：以少量精度损失换取大幅性能提升
6. **分块策略**：Recursive策略保持语义完整性，overlap防止边界丢失
7. **RAGAS评估**：四指标量化系统质量，Top-K需在precision和recall间权衡

理解了这些底层原理后，再使用LangChain、LlamaIndex等框架时，你会对每个参数的意义有更深的理解，调优也更有方向感。

> 本文所有代码均来自实际练习项目，完整源码包含10道练习题、3049行代码，覆盖向量嵌入到Agent+RAG融合的完整知识体系。

---

*作者：koze | AI全栈学习笔记*
